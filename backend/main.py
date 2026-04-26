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
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv
from fastapi import Request

#line notification เอามาไว้ข้างบนเพราะลองเอาไว้ข้างล่างแล้วเหมือนมีโค้ดไหนสักอันมองข้ามไป
load_dotenv()

LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

def send_line_alert(action: str, reason: str, price=None):
    if action not in ["BUY", "SELL"]:
        return

    text = f"""🚨 AI Gold Signal: {action}

ราคา: {price if price else "-"} THB
เหตุผล:
{reason}
"""

    res = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {LINE_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "to": LINE_USER_ID,
            "messages": [{"type": "text", "text": text}],
        },
        timeout=10,
    )

    print("LINE STATUS:", res.status_code)
    print("LINE RESPONSE:", res.text)

# =====================================================================
# 1. MASTER CONFIGURATION
# =====================================================================
app = FastAPI(title="Advanced AI Trading API")
api_router = APIRouter(prefix="/api")

# ดึงคีย์จาก Environment Variables (ปลอดภัย ไม่โดน GitHub บล็อก)
GROQ_API_KEYS = [
    os.getenv("GROQ_API_KEY_1", ""),
    os.getenv("GROQ_API_KEY_2", "")
]
# กรองเอาเฉพาะคีย์ที่ใส่ค่ามาจริงๆ
GROQ_API_KEYS = [k for k in GROQ_API_KEYS if k.strip() != ""]

ENABLE_UNIVERSITY_API = False
TEAM_API_KEY = "6e2755d365cb0e408024ddaca46aadf28756bd9c2a7481de70c82adeff2b436c"
LOG_BASE_URL = "https://goldtrade-logs-api.poonnatuch.workers.dev"

STARTING_THB = 1500.00
TRADE_MIN_THB = 1000.00
PORTFOLIO_FILE = "portfolio.json"
LOG_FILE_NAME = "live_gold_log.json"
CHART_FILE = "chart_history.json"
LANGUAGE = "EN"
BAHT_TO_GRAM = 15.244

GOLD_HISTORY_PERIOD = "3mo"
FOREX_HISTORY_PERIOD = "14d"
EMA_FAST = 14
EMA_SLOW = 50
RSI_PERIOD = 14
URGENCY_MINUTES_THRESHOLD = 60

TRADE_QUOTAS = {
    "WD_Morning": 2, "WD_Afternoon": 2, "WD_Evening": 2, "WD_Late_Night": 0, "WE_Active": 2
}

# Setup SQLite Database
conn = sqlite3.connect("logs.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT, price REAL,
    reason TEXT, timestamp TEXT
)
""")
conn.commit()

# =====================================================================
# 2. MODELS & PROMPTS
# =====================================================================
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
        "system": "You are a senior quantitative commodities strategist. Respond strictly in English.",
        "eco": "Chief Economist. Analyze headlines:\n{news}\nWrite 2-sentence sentiment report. End with SENTIMENT SCORE: (1-10).",
        "quant": "Quant Analyst. Analyze Global Gold (XAUUSD):\nGlobal Price: ${xau_price:,.2f}\nRSI ({rsi_period}): {rsi:.4f}\nEMA ({ema_fast}/{ema_slow}): {ema_signal}\nLive HSH Arbitrage Spread: {hsh_spread:.2f} THB (Premium: {premium:.2f} THB)\nWrite 2-sentence technical summary. End with MOMENTUM SCORE: (1-10).",
        "currency": "Currency Analyst (Forex). Analyze USD/THB:\nCurrent Rate: {current_thb:.3f} THB per USD\n{forex_period} Trend: {thb_trend} (Slope: {thb_slope:.4f})\nWrite 2-sentence analysis on how this affects THB Gold prices. End with CURRENCY RISK SCORE: (1-10).",
        "manager": "Portfolio Manager. Cash: {balance:,.2f} THB. Gold Held: {gold_gram:.4f} Grams.\nBuy Price: {price_per_gram_buy:,.2f} THB | Sell Price: {price_per_gram_sell:,.2f} THB.\n\n--- SESSION INFO ---\nPeriod: {period_name}\nTime Remaining: {minutes_remaining} Minutes\nTrades done: {trades_count} / {target_trades}\n\n--- REPORTS ---\n{eco}\n{quant}\n{currency}\n\nRules:\n1. Constraint: You CANNOT BUY if Cash < {trade_min:,.2f} THB. You CANNOT SELL if Gold Held is 0.\n{quota_instruction}\nFORMAT STRICTLY:\nACTION: [BUY / SELL / HOLD]\nAMOUNT_THB: [Enter number e.g., 1000, 1500, or ALL]\nREASONING: [1 sentence logic.]",
        "error_groq": "ACTION: HOLD\nAMOUNT_THB: 0\nREASONING: Emergency fallback. Groq API limits reached, offline, or keys not configured properly."
    }
}

# =====================================================================
# 3. HELPER FUNCTIONS & MATH ENGINE
# =====================================================================
def get_thai_time():
    return datetime.utcnow() + timedelta(hours=7)

def get_trading_period(now):
    weekday = now.weekday()
    current_time = now.time()
    current_date = now.date()

    if dt_time(0, 0) <= current_time <= dt_time(1, 59, 59):
        logical_date = current_date - timedelta(days=1)
        if logical_date.weekday() < 5:
            return "WD_Late_Night", "Weekday Late Night", True, datetime.combine(current_date, dt_time(1, 59, 59))

    if weekday < 5:
        if dt_time(6, 0) <= current_time <= dt_time(11, 59, 59):
            return "WD_Morning", "Weekday Morning", True, datetime.combine(current_date, dt_time(11, 59, 59))
        elif dt_time(12, 0) <= current_time <= dt_time(17, 59, 59):
            return "WD_Afternoon", "Weekday Afternoon", True, datetime.combine(current_date, dt_time(17, 59, 59))
        elif dt_time(18, 0) <= current_time <= dt_time(23, 59, 59):
            return "WD_Evening", "Weekday Evening", True, datetime.combine(current_date, dt_time(23, 59, 59))
    else:
        if dt_time(9, 30) <= current_time <= dt_time(17, 29, 59):
            return "WE_Active", "Weekend Active", True, datetime.combine(current_date, dt_time(17, 29, 59))
    return "CLOSED", "Out of Trading Hours", False, None

def load_portfolio():
    default_state = {"THB_Balance": STARTING_THB, "Gold_Gram": 0.0, "Current_Date": str(get_thai_time().date()), "Current_Period": "NONE", "Trades_Count": 0}
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f:
            try:
                data = json.load(f)
                for k, v in default_state.items():
                    if k not in data: data[k] = v
                return data
            except: pass
    return default_state

def save_portfolio(portfolio):
    with open(PORTFOLIO_FILE, "w") as f: json.dump(portfolio, f, indent=4)

def load_chart_history():
    if os.path.exists(CHART_FILE):
        with open(CHART_FILE, "r") as f:
            try: return json.load(f)
            except: pass
    return []

def save_chart_history(history):
    with open(CHART_FILE, "w") as f: json.dump(history, f)

def get_live_hsh_data():
    try:
        url = "https://apicheckpricev3.huasengheng.com/api/Values/GetPriceSeacon"
        data = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
        hsh_buy, hsh_sell = float(data.get('Bid965', 0)), float(data.get('Ask965', 0))
        assoc_buy, assoc_sell = float(data.get('BidAssociation', 0)), float(data.get('AskAssociation', 0))
        if hsh_sell == 0 or assoc_sell == 0: return None
        return {'HSH_Buy': hsh_buy, 'HSH_Sell': hsh_sell, 'Assoc_Buy': assoc_buy, 'Assoc_Sell': assoc_sell, 'HSH_Spread': hsh_sell - hsh_buy, 'HSH_Premium': hsh_sell - assoc_sell}
    except: return None

def get_global_markets():
    try:
        gold_hist = None
        for ticker in ["GC=F", "MGC=F"]:
            try:
                temp_hist = yf.Ticker(ticker).history(period=GOLD_HISTORY_PERIOD)['Close']
                if len(temp_hist) >= EMA_SLOW: gold_hist = temp_hist; break
            except: continue
        if gold_hist is None: return None
        
        ema_fast_val = gold_hist.ewm(span=EMA_FAST, adjust=False).mean().iloc[-1]
        ema_slow_val = gold_hist.ewm(span=EMA_SLOW, adjust=False).mean().iloc[-1]
        ema_signal = "BULLISH (Uptrend)" if ema_fast_val > ema_slow_val else "BEARISH (Downtrend)"
        
        delta = gold_hist.diff()
        up = delta.clip(lower=0).ewm(alpha=1/RSI_PERIOD, adjust=False).mean()
        down = -1 * delta.clip(upper=0).ewm(alpha=1/RSI_PERIOD, adjust=False).mean()
        rsi = 100 - (100 / (1 + (up / down))).iloc[-1]
        
        thb_hist = yf.Ticker("THB=X").history(period=FOREX_HISTORY_PERIOD)['Close']
        current_thb = thb_hist.iloc[-1]
        x = np.arange(len(thb_hist))
        thb_slope, _ = np.polyfit(x, thb_hist.values, 1)
        thb_trend = "WEAKENING BAHT" if thb_slope > 0 else "STRONG BAHT"
        
        return {"xau_price": gold_hist.iloc[-1], "rsi": rsi, "ema_signal": ema_signal, "current_thb": current_thb, "thb_slope": thb_slope, "thb_trend": thb_trend}
    except: return None

def get_news():
    try:
        feed = feedparser.parse("https://www.bangkokpost.com/rss/data/business.xml")
        return "\n".join([f"- {e.get('title')}" for e in feed.entries[:3]])
    except: return "News feed offline."

def ask_groq(prompt):
    models = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"]
    
    if not GROQ_API_KEYS:
        return PROMPTS[LANGUAGE]["error_groq"]

    for api_key in GROQ_API_KEYS:
        try:
            client = Groq(api_key=api_key)
            res = client.chat.completions.create(
                messages=[{"role": "system", "content": PROMPTS[LANGUAGE]["system"]}, {"role": "user", "content": prompt}],
                model=models[0], temperature=0.1, max_tokens=600
            )
            return res.choices[0].message.content
        except: continue
    return PROMPTS[LANGUAGE]["error_groq"]

def log_to_json(log_entry):
    logs = []
    if os.path.isfile(LOG_FILE_NAME):
        with open(LOG_FILE_NAME, "r", encoding="utf-8") as f:
            try: logs = json.load(f)
            except: pass
    logs.append(log_entry)
    with open(LOG_FILE_NAME, "w", encoding="utf-8") as f: json.dump(logs[-50:], f, indent=4, ensure_ascii=False)

def push_log_to_server(action, price, reason, amount, current_nav, ai_action, user_action):
    if not ENABLE_UNIVERSITY_API: return
    payload = {"action": action, "price": "MARKET" if price == "MARKET" else float(price), "reason": reason, "executed_amount": amount, "net_asset_value": current_nav, "signal_source": "AI_Agent_WebApp", "ai_intended_action": ai_action, "user_override_action": user_action}
    try: requests.post(f"{LOG_BASE_URL}/logs", headers={"Authorization": f"Bearer {TEAM_API_KEY}"}, json=payload, timeout=5)
    except: pass

# =====================================================================
# 3.5 BACKGROUND TASKS (ดึงกราฟกลาง)
# =====================================================================
async def poll_chart_data():
    while True:
        try:
            url = "https://apicheckpricev3.huasengheng.com/api/Values/GetPriceSeacon"
            res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
            if res and 'Ask965' in res and 'Bid965' in res:
                sell_price = float(str(res['Ask965']).replace(',', ''))
                buy_price = float(str(res['Bid965']).replace(',', ''))
                
                history = load_chart_history()
                now_str = get_thai_time().isoformat()
                
                history.append({
                    "timestamp": now_str,
                    "price": sell_price,
                    "buy": buy_price
                })
                history = history[-60:] # เก็บย้อนหลัง 60 นาที
                save_chart_history(history)
        except Exception as e:
            print(f"Chart Poll Error: {e}")
        
        await asyncio.sleep(60) # ดึงทุก 60 วินาที

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(poll_chart_data())


# =====================================================================
# 4. API ENDPOINTS
# =====================================================================
@api_router.get("/chart")
def get_chart_data():
    return {"status": "success", "data": load_chart_history()}

@api_router.get("/news")
def get_latest_news_api():
    try:
        feed = feedparser.parse("https://www.bangkokpost.com/rss/data/business.xml")
        news_list = [{"title": e.get('title'), "link": e.get('link')} for e in feed.entries[:5]]
        return {"status": "success", "news": news_list}
    except Exception as e:
        return {"status": "error", "news": []}

@api_router.get("/status")
def get_status():
    now = get_thai_time()
    portfolio = load_portfolio()
    market = get_live_hsh_data()
    period_key, period_name, is_active, end_time = get_trading_period(now)

    if portfolio.get("Current_Date") != str(now.date()) or portfolio.get("Current_Period") != period_key:
        portfolio["Current_Date"] = str(now.date())
        portfolio["Current_Period"] = period_key
        portfolio["Trades_Count"] = 0
        save_portfolio(portfolio)

    nav = (
        portfolio["THB_Balance"] + (portfolio["Gold_Gram"] * (market["HSH_Buy"] / BAHT_TO_GRAM))
        if market
        else portfolio["THB_Balance"]
    )

    #ถ้ามีข้อมูลจริง ลบ mock up นี้ออก
    performance = {
        "total_closed_trade": 18,
        "win_rate": 66.67,
        "total_profit": 12500.50,
        "unrealized_pl": 2300.00,

        "avg_win": 1850.75,
        "avg_loss": -920.25,
        "expectancy": 923.40,

        "best_trade": 14.82,
        "worst_trade": -6.35,
        "median_trade": 3.75,
        "top10_trade": 12.40,
        "bottom10_trade": -4.90,

        "xirr": 18.25,
        "avg_capital_year": 85000.00,
        "sharpe_ratio": 1.42,
    }
    
    return {
        "portfolio": portfolio,
        "market": market,
        "net_asset_value": nav,
        "period": {
            "name": period_name,
            "is_active": is_active,
            "trades_done": portfolio["Trades_Count"],
        },
        "performance": performance, #ถ้ามีข้อมูลจริง แก้ฟังก์ชั่นนี้ เช่น performance = calculate_performance_from_trades()
    }

@api_router.post("/portfolio")
def update_portfolio(req: PortfolioUpdate):
    portfolio = load_portfolio()
    portfolio['THB_Balance'] = req.THB_Balance
    portfolio['Gold_Gram'] = req.Gold_Gram
    save_portfolio(portfolio)
    return {"status": "success"}

@api_router.post("/analyze")
def trigger_analysis():
    now = get_thai_time()
    portfolio = load_portfolio()
    market = get_live_hsh_data()
    global_math = get_global_markets()
    news = get_news()
    period_key, period_name, is_active, end_time = get_trading_period(now)

    if not is_active or not market or not global_math:
        return {"error": "Market Closed/Offline", "ai_action": "HOLD", "ai_reason": "Out of Trading Hours or Data Unavailable"}

    p_buy_gram = market['HSH_Sell'] / BAHT_TO_GRAM
    p_sell_gram = market['HSH_Buy'] / BAHT_TO_GRAM
    
    target_trades = TRADE_QUOTAS.get(period_key, 0)
    current_trades = portfolio['Trades_Count']
    minutes_remaining = int((end_time - now).total_seconds() / 60)

    weekend_rule = f" WEEKEND MODE: Use minimum amount (AMOUNT_THB: {TRADE_MIN_THB:.2f})." if "WE_" in period_key else ""
    if target_trades == 0: dynamic_quota = "No strict quota. Trade on clear convergence." + weekend_rule
    elif current_trades < target_trades and minutes_remaining <= URGENCY_MINUTES_THRESHOLD:
        dynamic_quota = f"URGENT: MUST trade NOW to pass limit ({minutes_remaining} mins left). Use AMOUNT_THB: {TRADE_MIN_THB:.2f}." + weekend_rule
    else: dynamic_quota = f"Quota Status: {current_trades}/{target_trades}. Trade normally." + weekend_rule

    # Multi-Persona Analysis
    eco_out = ask_groq(PROMPTS[LANGUAGE]["eco"].format(news=news))
    quant_out = ask_groq(PROMPTS[LANGUAGE]["quant"].format(xau_price=global_math['xau_price'], rsi=global_math['rsi'], ema_signal=global_math['ema_signal'], hsh_spread=market['HSH_Spread'], premium=market['HSH_Premium'], rsi_period=RSI_PERIOD, ema_fast=EMA_FAST, ema_slow=EMA_SLOW))
    currency_out = ask_groq(PROMPTS[LANGUAGE]["currency"].format(current_thb=global_math['current_thb'], thb_trend=global_math['thb_trend'], thb_slope=global_math['thb_slope'], forex_period=FOREX_HISTORY_PERIOD))

    decision = ask_groq(PROMPTS[LANGUAGE]["manager"].format(
        balance=portfolio['THB_Balance'], gold_gram=portfolio['Gold_Gram'], price_per_gram_buy=p_buy_gram, price_per_gram_sell=p_sell_gram,
        eco=eco_out, quant=quant_out, currency=currency_out, trade_min=TRADE_MIN_THB, period_name=period_name,
        trades_count=current_trades, target_trades=target_trades, minutes_remaining=minutes_remaining, quota_instruction=dynamic_quota
    ))

    ai_act, ai_reason, ai_amt = "HOLD", "Default Hold", "ALL"
    for line in decision.split('\n'):
        line_u = line.upper()
        if "ACTION:" in line_u: ai_act = line_u.split(":", 1)[1].strip()
        elif "AMOUNT_THB:" in line_u: ai_amt = line.split(":", 1)[1].strip().replace(',', '')
        elif "REASONING:" in line_u: ai_reason = line.split(":", 1)[1].strip()

    full_reason = f"<strong>AI Reason:</strong> {ai_reason}<br/><br/><i>[Quant]</i> {quant_out}<br/><i>[Currency]</i> {currency_out}"
    
     # ส่ง LINE เมื่อ AI trigger BUY/SELL
    if ai_act in ["BUY", "SELL"]:
        send_line_alert(
            ai_act,
            ai_reason,
            market["HSH_Sell"] if ai_act == "BUY" else market["HSH_Buy"]
        )

    return {"ai_action": ai_act, "ai_amount_thb": ai_amt, "ai_reason": full_reason}

@api_router.post("/execute")
def execute_trade(req: ExecuteRequest):
    now = get_thai_time()
    portfolio = load_portfolio()
    market = get_live_hsh_data()
    period_key, _, _, _ = get_trading_period(now)
    
    p_buy_gram = market['HSH_Sell'] / BAHT_TO_GRAM
    p_sell_gram = market['HSH_Buy'] / BAHT_TO_GRAM
    
    final_act = req.ai_action if req.user_action == "TIMEOUT" else req.user_action
    act, exec_price, exec_amt_str = "HOLD", "MARKET", "0"
    
    # Fractional Execution Engine
    if final_act == "BUY" and portfolio['THB_Balance'] >= TRADE_MIN_THB:
        target_thb = portfolio['THB_Balance']
        if req.ai_amount_thb != "ALL":
            try: target_thb = max(TRADE_MIN_THB, min(float(req.ai_amount_thb), portfolio['THB_Balance']))
            except: pass
        
        gram_bought = round(target_thb / p_buy_gram, 4)
        portfolio['Gold_Gram'] += gram_bought
        portfolio['THB_Balance'] -= target_thb
        portfolio['Trades_Count'] += 1
        act, exec_price, exec_amt_str = "BUY", market['HSH_Sell'], f"{gram_bought}g ({target_thb} THB)"
        
    elif final_act == "SELL" and portfolio['Gold_Gram'] > 0:
        current_val = portfolio['Gold_Gram'] * p_sell_gram
        target_thb = current_val
        if req.ai_amount_thb != "ALL":
            try: target_thb = min(float(req.ai_amount_thb), current_val)
            except: pass

        gram_sold = min(round(target_thb / p_sell_gram, 4), portfolio['Gold_Gram'])
        cash_returned = round(gram_sold * p_sell_gram, 2)
        
        portfolio['THB_Balance'] += cash_returned
        portfolio['Gold_Gram'] -= gram_sold
        portfolio['Trades_Count'] += 1
        act, exec_price, exec_amt_str = "SELL", market['HSH_Buy'], f"Sold {gram_sold}g ({cash_returned} THB)"

    save_portfolio(portfolio)
    nav = portfolio['THB_Balance'] + (portfolio['Gold_Gram'] * p_sell_gram)

    # Logging
    log_entry = {"date": now.strftime('%Y-%m-%d %H:%M:%S'), "period": period_key, "action": req.ai_action, "user_action": req.user_action, "executed_action": act, "price": exec_price, "reason": req.ai_reason, "amount": exec_amt_str, "total_asset_value": nav}
    log_to_json(log_entry)
    push_log_to_server(act, exec_price, req.ai_reason, exec_amt_str, nav, req.ai_action, req.user_action)
    cursor.execute("INSERT INTO logs (action, price, reason, timestamp) VALUES (?, ?, ?, ?)", (act, exec_price if act != "HOLD" else 0, req.ai_reason, now.isoformat()))
    conn.commit()

    return {"status": "success", "executed_action": act, "net_asset_value": nav}

# DEBUG ONLY
# @api_router.get("/test-line")
# def test_line():
#     send_line_alert("BUY", "ทดสอบแจ้งเตือน")
#     return {"ok": True}

app.include_router(api_router)

# =====================================================================
# 5. FRONTEND PROXY & SERVING (Deploy ready for Render)
# =====================================================================
@app.get("/hsh-api/{path:path}")
def proxy_hsh(path: str):
    url = f"https://apicheckpricev3.huasengheng.com/{path}"
    try: return requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
    except: return {}

FRONTEND_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("hsh-api/"): raise HTTPException(status_code=404)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
    
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)