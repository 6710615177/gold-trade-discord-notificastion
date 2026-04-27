import os
import json
import sqlite3
import requests
import feedparser
import asyncio
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, time as dt_time, timedelta
from fastapi import FastAPI, APIRouter, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

import config
import lstm_model
from analytics_engine import AdvancedTradingAnalytics, parse_logs_to_metrics

load_dotenv()

DISCORD_BUY_WEBHOOK_URL = os.getenv("DISCORD_BUY_WEBHOOK_URL")
DISCORD_SELL_WEBHOOK_URL = os.getenv("DISCORD_SELL_WEBHOOK_URL")
LAST_SIGNAL_FILE = "last_signal.json"


def send_discord_alert(action: str, reason: str, price=None):
    if action not in ["BUY", "SELL"]:
        return

    webhook_url = (
        DISCORD_BUY_WEBHOOK_URL if action == "BUY" else DISCORD_SELL_WEBHOOK_URL
    )

    if not webhook_url:
        print(f"Discord Alert Error: webhook for {action} is not set")
        return

    clean_reason = (
        reason.replace("<strong>", "")
        .replace("</strong>", "")
        .replace("<br/>", "\n")
        .replace("<i>", "")
        .replace("</i>", "")
    )

    color = 0x2ECC71 if action == "BUY" else 0xE74C3C

    payload = {
        "username": "Gold Trading AI",
        "embeds": [
            {
                "title": f"🚨 AI Gold Signal: {action}",
                "color": color,
                "fields": [
                    {
                        "name": "ราคา",
                        "value": f"{price if price else '-'} THB",
                        "inline": False,
                    },
                    {
                        "name": "เหตุผล",
                        "value": clean_reason[:1000],
                        "inline": False,
                    },
                ],
            }
        ],
    }

    try:
        res = requests.post(webhook_url, json=payload, timeout=10)
        if res.status_code not in [200, 204]:
            print(f"Discord Alert Error: {res.status_code} {res.text}")
    except Exception as e:
        print(f"Discord Alert Error: {e}")


app = FastAPI(title="Trinity Advanced AI Trading API")
api_router = APIRouter(prefix="/api")

GROQ_API_KEYS = [
    os.getenv("GROQ_API_KEY_1", ""),
    os.getenv("GROQ_API_KEY_2", ""),
    os.getenv("GROQ_API_KEY_3", ""),
    os.getenv("GROQ_API_KEY_4", ""),
]
GROQ_API_KEYS = [k for k in GROQ_API_KEYS if k.strip() != ""]

conn = sqlite3.connect("logs.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute(
    "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT, price REAL, reason TEXT, timestamp TEXT)"
)
conn.commit()

LANGUAGE = "EN"

# 🎯 ตัวแปรเก็บสัญญาณที่ AI วิเคราะห์ได้ (รอหน้าเว็บมารับ)
pending_signal = None


class ExecuteRequest(BaseModel):
    ai_action: str
    ai_reason: str
    ai_amount_thb: str
    user_action: str


class PortfolioUpdate(BaseModel):
    THB_Balance: float
    Gold_Gram: float


PROMPTS = {
    "EN": {
        "system": "You are a highly logical Quantitative Gold Trading AI. You must STRICTLY obey the critical rules without exception.",
        "trader": """Analyze the following Gold Market data:
- Current HSH Buy: {hsh_buy:,.2f} THB
- Current HSH Sell: {hsh_sell:,.2f} THB
- Global Gold: ${xau_price:,.2f}
- RSI ({rsi_period}): {rsi:.2f}
- EMA Trend: {ema_signal}
- USD/THB Rate: {current_thb:.3f}
- LSTM AI Prediction: {lstm_pred:,.2f} THB
- Headlines: {news}

Portfolio Status:
- Cash Balance: {balance:,.2f} THB
- Gold Holding: {gold_gram:.4f} Grams

CRITICAL RULES (MUST OBEY):
1. IF Cash Balance < {trade_min:,.2f} THB, you are FORBIDDEN from choosing BUY. You MUST choose HOLD (Reason: Insufficient funds) or SELL.
2. IF Gold Holding <= 0.0000, you are FORBIDDEN from choosing SELL.
{quota_instruction}

FORMAT STRICTLY:
ACTION: [BUY / SELL / HOLD]
AMOUNT_THB: [Enter number e.g., {trade_min}, or ALL]
REASONING: [Provide a 1-2 sentence logical reason.]""",
        "error_groq": "ACTION: HOLD\nAMOUNT_THB: 0\nREASONING: Emergency fallback. Groq API limits reached or offline.",
    }
}


def get_thai_time():
    return datetime.utcnow() + timedelta(hours=7)


def get_trading_period(now):
    weekday = now.weekday()
    current_time = now.time()
    current_date = now.date()
    if dt_time(0, 0) <= current_time <= dt_time(1, 59, 59):
        logical_date = current_date - timedelta(days=1)
        if logical_date.weekday() < 5:
            return (
                "WD_Late_Night",
                "Weekday Late Night",
                True,
                datetime.combine(current_date, dt_time(1, 59, 59)),
            )
    if weekday < 5:
        if dt_time(6, 0) <= current_time <= dt_time(11, 59, 59):
            return (
                "WD_Morning",
                "Weekday Morning",
                True,
                datetime.combine(current_date, dt_time(11, 59, 59)),
            )
        elif dt_time(12, 0) <= current_time <= dt_time(17, 59, 59):
            return (
                "WD_Afternoon",
                "Weekday Afternoon",
                True,
                datetime.combine(current_date, dt_time(17, 59, 59)),
            )
        elif dt_time(18, 0) <= current_time <= dt_time(23, 59, 59):
            return (
                "WD_Evening",
                "Weekday Evening",
                True,
                datetime.combine(current_date, dt_time(23, 59, 59)),
            )
    else:
        if dt_time(9, 30) <= current_time <= dt_time(17, 29, 59):
            return (
                "WE_Active",
                "Weekend Active",
                True,
                datetime.combine(current_date, dt_time(17, 29, 59)),
            )
    return "CLOSED", "Out of Trading Hours", False, None


def load_portfolio():
    default_state = {
        "THB_Balance": config.STARTING_THB,
        "Gold_Gram": 0.0,
        "Current_Date": str(get_thai_time().date()),
        "Current_Period": "NONE",
        "Trades_Count": 0,
    }
    if os.path.exists(config.PORTFOLIO_FILE):
        with open(config.PORTFOLIO_FILE, "r") as f:
            try:
                data = json.load(f)
                for k, v in default_state.items():
                    if k not in data:
                        data[k] = v
                return data
            except:
                pass
    return default_state


def save_portfolio(portfolio):
    with open(config.PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f, indent=4)


def load_last_signal():
    if os.path.exists(LAST_SIGNAL_FILE):
        with open(LAST_SIGNAL_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                pass
    return {"last_action": "HOLD"}


def save_last_signal(action: str):
    with open(LAST_SIGNAL_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_action": action}, f, ensure_ascii=False, indent=2)


def load_chart_history():
    if os.path.exists("chart_history.json"):
        with open("chart_history.json", "r") as f:
            try:
                return json.load(f)
            except:
                pass
    return []


def save_chart_history(history):
    with open("chart_history.json", "w") as f:
        json.dump(history, f)


def get_live_hsh_data():
    try:
        url = "https://apicheckpricev3.huasengheng.com/api/Values/GetPriceSeacon"
        data = requests.get(
            url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5
        ).json()
        hsh_buy, hsh_sell = float(data.get("Bid965", 0)), float(data.get("Ask965", 0))
        assoc_buy, assoc_sell = (
            float(data.get("BidAssociation", 0)),
            float(data.get("AskAssociation", 0)),
        )
        if hsh_sell == 0 or assoc_sell == 0:
            return None
        return {
            "HSH_Buy": hsh_buy,
            "HSH_Sell": hsh_sell,
            "Assoc_Buy": assoc_buy,
            "Assoc_Sell": assoc_sell,
            "HSH_Spread": hsh_sell - hsh_buy,
            "HSH_Premium": hsh_sell - assoc_sell,
        }
    except:
        return None


def get_global_markets():
    try:
        gold_hist = None
        for ticker in ["GC=F", "MGC=F"]:
            try:
                temp_hist = yf.Ticker(ticker).history(
                    period=config.GOLD_HISTORY_PERIOD
                )["Close"]
                if len(temp_hist) >= config.EMA_SLOW:
                    gold_hist = temp_hist
                    break
            except:
                continue
        if gold_hist is None:
            return None
        ema_fast_val = gold_hist.ewm(span=config.EMA_FAST, adjust=False).mean().iloc[-1]
        ema_slow_val = gold_hist.ewm(span=config.EMA_SLOW, adjust=False).mean().iloc[-1]
        ema_signal = (
            "BULLISH (Uptrend)"
            if ema_fast_val > ema_slow_val
            else "BEARISH (Downtrend)"
        )
        delta = gold_hist.diff()
        up = delta.clip(lower=0).ewm(alpha=1 / config.RSI_PERIOD, adjust=False).mean()
        down = (
            -1
            * delta.clip(upper=0).ewm(alpha=1 / config.RSI_PERIOD, adjust=False).mean()
        )
        rsi = 100 - (100 / (1 + (up / down))).iloc[-1]
        thb_hist = yf.Ticker("THB=X").history(period=config.FOREX_HISTORY_PERIOD)[
            "Close"
        ]
        current_thb = thb_hist.iloc[-1]
        x = np.arange(len(thb_hist))
        thb_slope, _ = np.polyfit(x, thb_hist.values, 1)
        thb_trend = "WEAKENING BAHT" if thb_slope > 0 else "STRONG BAHT"
        return {
            "xau_price": gold_hist.iloc[-1],
            "rsi": rsi,
            "ema_signal": ema_signal,
            "current_thb": current_thb,
            "thb_slope": thb_slope,
            "thb_trend": thb_trend,
        }
    except:
        return None


def get_news():
    news_items = []
    feeds = [
        ("Bangkok Post", "https://www.bangkokpost.com/rss/data/business.xml"),
        ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
        ("MarketWatch", "http://feeds.marketwatch.com/marketwatch/topstories/"),
        ("WSJ Markets", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
    ]
    for source, url in feeds:
        try:
            response = requests.get(
                url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8
            )
            for entry in feedparser.parse(response.content).entries[:2]:
                news_items.append(f"[{source}] - {entry.get('title')}")
        except:
            continue
    return "\n".join(news_items) if news_items else "News feed offline."


def ask_groq(prompt):
    models = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"]
    if not GROQ_API_KEYS:
        return PROMPTS[LANGUAGE]["error_groq"]
    for api_key in GROQ_API_KEYS:
        try:
            return (
                Groq(api_key=api_key)
                .chat.completions.create(
                    messages=[
                        {"role": "system", "content": PROMPTS[LANGUAGE]["system"]},
                        {"role": "user", "content": prompt},
                    ],
                    model=models[0],
                    temperature=0.1,
                    max_tokens=600,
                )
                .choices[0]
                .message.content
            )
        except:
            continue
    return PROMPTS[LANGUAGE]["error_groq"]


def log_to_json(log_entry):
    logs = []
    if os.path.isfile(config.LOG_FILE_NAME):
        with open(config.LOG_FILE_NAME, "r", encoding="utf-8") as f:
            try:
                logs = json.load(f)
            except:
                pass
    logs.append(log_entry)
    with open(config.LOG_FILE_NAME, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=4, ensure_ascii=False)


# 🎯 ฟังก์ชันหลักสำหรับให้ AI วิเคราะห์ตลาด
def run_ai_analysis_logic():
    now = get_thai_time()
    portfolio = load_portfolio()
    market = get_live_hsh_data()
    global_math = get_global_markets()
    news = get_news()
    period_key, period_name, is_active, end_time = get_trading_period(now)

    if not is_active or not market or not global_math:
        return None

    target_trades = config.TRADE_QUOTAS.get(period_key, 0)
    current_trades = portfolio["Trades_Count"]
    minutes_remaining = int((end_time - now).total_seconds() / 60)
    weekend_rule = (
        f" WEEKEND MODE: Use minimum amount (AMOUNT_THB: {config.TRADE_MIN_THB:.2f})."
        if "WE_" in period_key
        else ""
    )

    if target_trades == 0:
        dynamic_quota = "No strict quota. Trade on clear convergence." + weekend_rule
    elif current_trades < target_trades and minutes_remaining <= 60:
        dynamic_quota = (
            f"URGENT: MUST trade NOW to pass limit ({minutes_remaining} mins left). Use AMOUNT_THB: {config.TRADE_MIN_THB:.2f}."
            + weekend_rule
        )
    else:
        dynamic_quota = (
            f"Quota Status: {current_trades}/{target_trades}. Trade normally."
            + weekend_rule
        )

    lstm_live_data = {
        "HSH_Buy": market["HSH_Buy"],
        "HSH_Sell": market["HSH_Sell"],
        "xau_price": global_math["xau_price"],
        "current_thb": global_math["current_thb"],
        "rsi": global_math["rsi"],
    }
    predicted_price = lstm_model.predict_next_price_with_lstm(lstm_live_data)
    if predicted_price is None:
        predicted_price = market["HSH_Buy"]

    prompt_content = PROMPTS[LANGUAGE]["trader"].format(
        hsh_buy=market["HSH_Buy"],
        hsh_sell=market["HSH_Sell"],
        xau_price=global_math["xau_price"],
        rsi=global_math["rsi"],
        rsi_period=config.RSI_PERIOD,
        ema_signal=global_math["ema_signal"],
        current_thb=global_math["current_thb"],
        lstm_pred=predicted_price,
        news=news[:600],
        balance=portfolio["THB_Balance"],
        gold_gram=portfolio["Gold_Gram"],
        trade_min=config.TRADE_MIN_THB,
        quota_instruction=dynamic_quota,
    )

    decision = ask_groq(prompt_content)
    ai_act, ai_reason, ai_amt = "HOLD", "Default Hold", "ALL"
    for line in decision.split("\n"):
        line_u = line.upper()
        if "ACTION:" in line_u:
            ai_act = line_u.split(":", 1)[1].strip()
        elif "AMOUNT_THB:" in line_u:
            ai_amt = line.split(":", 1)[1].strip().replace(",", "")
        elif "REASONING:" in line_u:
            ai_reason = line.split(":", 1)[1].strip()

    return {
        "ai_action": ai_act,
        "ai_amount_thb": ai_amt,
        "ai_reason": f"<strong>AI Reason:</strong> {ai_reason}",
        "current_market_price": market["HSH_Sell"]
        if ai_act == "BUY"
        else market["HSH_Buy"],
    }


# 🎯 Background Task 1: ดึงกราฟ
async def poll_chart_data():
    while True:
        try:
            url = "https://apicheckpricev3.huasengheng.com/api/Values/GetPriceSeacon"
            res = requests.get(
                url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5
            ).json()
            if res and "Ask965" in res and "Bid965" in res:
                history = load_chart_history()
                history.append(
                    {
                        "timestamp": get_thai_time().isoformat(),
                        "price": float(str(res["Ask965"]).replace(",", "")),
                        "buy": float(str(res["Bid965"]).replace(",", "")),
                    }
                )
                save_chart_history(history[-60:])
        except:
            pass
        await asyncio.sleep(60)


# 🎯 Background Task 2: ให้ AI วิเคราะห์อัตโนมัติ (Autonomous AI)
async def auto_analysis_loop():
    global pending_signal

    while True:
        try:
            now = get_thai_time()

            if now.minute % config.RUN_EVERY_MINUTES == 0 and now.second < 10:
                print(
                    f"[{now.strftime('%H:%M:%S')}] 🤖 Backend: Running Autonomous AI Analysis..."
                )

                result = run_ai_analysis_logic()

                if result:
                    ai_act = result.get("ai_action", "HOLD")

                    # last_signal = load_last_signal()
                    # ast_action = last_signal.get("last_action", "HOLD")

                    # ส่ง LINE เฉพาะตอนเปลี่ยนเป็น BUY/SELL
                    if ai_act in ["BUY", "SELL"]:
                        print(f"🔥 Signal Alert: {ai_act}")

                        pending_signal = result

                        send_discord_alert(
                            ai_act,
                            result.get("ai_reason", ""),
                            result.get("current_market_price"),
                        )

                    # จำ signal ล่าสุดไว้
                    # save_last_signal(ai_act)

                await asyncio.sleep(60)

        except Exception as e:
            print(f"Auto Analysis Error: {e}")

        await asyncio.sleep(5)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(poll_chart_data())
    asyncio.create_task(auto_analysis_loop())


@api_router.get("/chart")
def get_chart_data():
    return {"status": "success", "data": load_chart_history()}


@api_router.get("/news")
def get_latest_news_api():
    try:
        return {
            "status": "success",
            "news": [
                {"title": e.get("title"), "link": e.get("link")}
                for e in feedparser.parse(
                    "https://www.bangkokpost.com/rss/data/business.xml"
                ).entries[:5]
            ],
        }
    except:
        return {"status": "error", "news": []}


@api_router.get("/status")
def get_status():
    now = get_thai_time()
    portfolio = load_portfolio()
    market = get_live_hsh_data()
    period_key, period_name, is_active, end_time = get_trading_period(now)

    if (
        portfolio.get("Current_Date") != str(now.date())
        or portfolio.get("Current_Period") != period_key
    ):
        portfolio["Current_Date"] = str(now.date())
        portfolio["Current_Period"] = period_key
        portfolio["Trades_Count"] = 0
        save_portfolio(portfolio)

    price_g = (market["HSH_Buy"] / config.BAHT_TO_GRAM) if market else 0
    nav = portfolio["THB_Balance"] + (portfolio["Gold_Gram"] * price_g)
    closed, unrealized, first_date = parse_logs_to_metrics(price_g)
    report = AdvancedTradingAnalytics.generate_full_report(
        closed, unrealized, nav, first_date
    )

    return {
        "portfolio": portfolio,
        "market": market,
        "net_asset_value": nav,
        "period": {
            "name": period_name,
            "is_active": is_active,
            "trades_done": portfolio["Trades_Count"],
        },
        "performance": {
            "total_closed_trade": report["Total Closed Trade"],
            "win_rate": report["Win Rate (%)"],
            "total_profit": report["Total Profit (THB)"],
            "unrealized_pl": report["Unrealized P/L (THB)"],
            "avg_win": report["Average Win (THB)"],
            "avg_loss": report["Average Loss (THB)"],
            "expectancy": report["Expectancy per Trade (THB)"],
            "best_trade": report["Best Annualized Trade (%)"],
            "worst_trade": report["Worst Annualized Trade (%)"],
            "median_trade": report["Median Annualized Trade (%)"],
            "top10_trade": report["Top 10% Annualized Trade (%)"],
            "bottom10_trade": report["Bottom 10% Annualized Trade (%)"],
            "xirr": report["XIRR (%)"],
            "avg_capital_year": report["Avg Capital/Year (THB)"],
            "sharpe_ratio": report["Sharpe Ratio"],
        },
    }


@api_router.post("/portfolio")
def update_portfolio(req: PortfolioUpdate):
    portfolio = load_portfolio()
    portfolio["THB_Balance"] = req.THB_Balance
    portfolio["Gold_Gram"] = req.Gold_Gram
    save_portfolio(portfolio)
    return {"status": "success"}


# 🎯 API ใหม่สำหรับหน้าเว็บมาเช็คสัญญาณที่ AI วิเคราะห์ทิ้งไว้
@api_router.get("/pending-signal")
def get_pending_signal():
    global pending_signal
    return {"signal": pending_signal}


# ยังคงเก็บ route เดิมไว้เผื่อกดวิเคราะห์ด้วยมือในอนาคต
@api_router.post("/analyze")
def trigger_analysis():
    result = run_ai_analysis_logic()
    if not result:
        return {"error": "Market Offline"}

    ai_act = result["ai_action"]
    ai_reason = result["ai_reason"]
    market_price = result["current_market_price"]

    # last_signal = load_last_signal()
    # last_action = last_signal.get("last_action", "HOLD")

    if ai_act in ["BUY", "SELL"]:
        print(f"🔥 Signal Alert: {ai_act}")
        send_discord_alert(ai_act, ai_reason, market_price)

    # save_last_signal(ai_act)

    return result


@api_router.post("/execute")
def execute_trade(req: ExecuteRequest):
    global pending_signal
    now = get_thai_time()
    portfolio = load_portfolio()
    market = get_live_hsh_data()
    period_key, _, _, _ = get_trading_period(now)
    p_buy_gram = market["HSH_Sell"] / config.BAHT_TO_GRAM
    p_sell_gram = market["HSH_Buy"] / config.BAHT_TO_GRAM
    final_act = "HOLD" if req.user_action == "TIMEOUT" else req.user_action
    act, exec_price, exec_amt_str = "HOLD", "MARKET", "0"

    if final_act == "BUY" and portfolio["THB_Balance"] >= config.TRADE_MIN_THB:
        target_thb = portfolio["THB_Balance"]
        if req.ai_amount_thb != "ALL":
            try:
                target_thb = max(
                    config.TRADE_MIN_THB,
                    min(float(req.ai_amount_thb), portfolio["THB_Balance"]),
                )
            except:
                pass
        gram_bought = round(target_thb / p_buy_gram, 4)
        portfolio["Gold_Gram"] += gram_bought
        portfolio["THB_Balance"] -= target_thb
        portfolio["Trades_Count"] += 1
        act, exec_price, exec_amt_str = (
            "BUY",
            market["HSH_Sell"],
            f"{gram_bought} g ({target_thb} THB)",
        )

    elif final_act == "SELL" and portfolio["Gold_Gram"] > 0:
        current_val = portfolio["Gold_Gram"] * p_sell_gram
        target_thb = current_val
        if req.ai_amount_thb != "ALL":
            try:
                target_thb = min(float(req.ai_amount_thb), current_val)
            except:
                pass
        gram_sold = min(round(target_thb / p_sell_gram, 4), portfolio["Gold_Gram"])
        cash_returned = round(gram_sold * p_sell_gram, 2)
        portfolio["THB_Balance"] += cash_returned
        portfolio["Gold_Gram"] -= gram_sold
        portfolio["Trades_Count"] += 1
        act, exec_price, exec_amt_str = (
            "SELL",
            market["HSH_Buy"],
            f"Sold {gram_sold} g ({cash_returned} THB)",
        )

    save_portfolio(portfolio)
    nav = portfolio["THB_Balance"] + (portfolio["Gold_Gram"] * p_sell_gram)
    log_to_json(
        {
            "date": now.strftime("%Y-%m-%d %H:%M:%S"),
            "period": period_key,
            "action": req.ai_action,
            "user_action": req.user_action,
            "executed_action": act,
            "price": exec_price,
            "reason": req.ai_reason,
            "amount": exec_amt_str,
            "total_asset_value": nav,
        }
    )
    parse_logs_to_metrics(p_sell_gram)
    cursor.execute(
        "INSERT INTO logs (action, price, reason, timestamp) VALUES (?, ?, ?, ?)",
        (act, exec_price if act != "HOLD" else 0, req.ai_reason, now.isoformat()),
    )
    conn.commit()

    # 🎯 เคลียร์สัญญาณหลังจากตัดสินใจเรียบร้อยแล้ว
    pending_signal = None
    return {"status": "success", "executed_action": act, "net_asset_value": nav}

    # เผื่อ debug
    # @api_router.get("/test-discord")
    # def test_discord():
    results = {}

    webhooks = {
        "BUY": DISCORD_BUY_WEBHOOK_URL,
        "SELL": DISCORD_SELL_WEBHOOK_URL,
    }

    for action, webhook_url in webhooks.items():
        if not webhook_url:
            results[action] = {
                "status": "error",
                "message": f"{action} webhook is not set",
            }
            continue

        try:
            res = requests.post(
                webhook_url,
                json={"content": f"🚀 Discord {action} webhook connected successfully"},
                timeout=10,
            )

            if res.status_code in [200, 204]:
                results[action] = {
                    "status": "success",
                    "message": f"{action} test sent",
                }
            else:
                results[action] = {
                    "status": "error",
                    "code": res.status_code,
                    "message": res.text,
                }

        except Exception as e:
            results[action] = {
                "status": "error",
                "message": str(e),
            }

    return results


@api_router.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(api_router)


@app.get("/hsh-api/{path:path}")
def proxy_hsh(path: str):
    try:
        return requests.get(
            f"https://apicheckpricev3.huasengheng.com/{path}",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5,
        ).json()
    except:
        return {}


FRONTEND_DIST = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
)
if os.path.exists(FRONTEND_DIST):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")),
        name="assets",
    )

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("hsh-api/"):
            raise HTTPException(status_code=404)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", 10000)))
