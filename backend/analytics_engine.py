import os
import json
import numpy as np
import pandas as pd
from datetime import datetime
import config


class AdvancedTradingAnalytics:
    @staticmethod
    def calculate_days_held(buy_date, sell_date):
        fmt = "%Y-%m-%d %H:%M:%S"
        b_date = datetime.strptime(buy_date, fmt) if isinstance(buy_date, str) else buy_date
        s_date = datetime.strptime(sell_date, fmt) if isinstance(sell_date, str) else sell_date
        days = (s_date - b_date).total_seconds() / 86400.0
        return max(days, 0.0001)

    @staticmethod
    def calculate_annualized_return(profit_pct, days_held):
        r = profit_pct / 100.0
        safe_days = max(days_held, 1.0)
        return (((1 + r) ** (365.0 / safe_days)) - 1) * 100.0

    @staticmethod
    def generate_full_report(closed_trades, unrealized_pl, current_nav, first_date):
        if not closed_trades:
            return {
                "Total Closed Trade": 0,
                "Win Rate (%)": 0.0,
                "Total Profit (THB)": 0.0,
                "Unrealized P/L (THB)": round(unrealized_pl, 2),
                "Average Win (THB)": 0.0,
                "Average Loss (THB)": 0.0,
                "Expectancy per Trade (THB)": 0.0,
                "Best Annualized Trade (%)": 0.0,
                "Worst Annualized Trade (%)": 0.0,
                "Median Annualized Trade (%)": 0.0,
                "Top 10% Annualized Trade (%)": 0.0,
                "Bottom 10% Annualized Trade (%)": 0.0,
                "XIRR (%)": 0.0,
                "Avg Capital/Year (THB)": 0.0,
                "Sharpe Ratio": 0.0
            }

        total_trades = len(closed_trades)
        profits = [t['sell_amount'] - t['buy_amount'] for t in closed_trades]
        winning_trades = [p for p in profits if p > 0]
        losing_trades = [p for p in profits if p <= 0]

        total_profit = sum(profits)
        win_rate = (len(winning_trades) / total_trades) * 100
        avg_win = np.mean(winning_trades) if winning_trades else 0
        avg_loss = abs(np.mean(losing_trades)) if losing_trades else 0

        win_prob = win_rate / 100.0
        expectancy = (win_prob * avg_win) - ((1.0 - win_prob) * avg_loss)

        ann_returns = []
        for t in closed_trades:
            p_pct = ((t['sell_amount'] - t['buy_amount']) / t['buy_amount']) * 100 if t['buy_amount'] > 0 else 0
            ann_returns.append(AdvancedTradingAnalytics.calculate_annualized_return(p_pct, t['days_held']))

        ann_returns.sort()
        returns_array = np.array(ann_returns)
        excess_returns = returns_array - 2.0
        std_dev = np.std(excess_returns, ddof=1) if len(excess_returns) > 1 else 0
        sharpe = np.mean(excess_returns) / std_dev if std_dev != 0 else 0.0

        median_ann = np.median(ann_returns)

        n_10_percent = max(1, int(len(ann_returns) * 0.10))
        top_10_ann = np.mean(ann_returns[-n_10_percent:])
        bottom_10_ann = np.mean(ann_returns[:n_10_percent])

        avg_capital_year = sum((t['buy_amount'] * t['days_held']) / 365.0 for t in closed_trades)

        fmt = "%Y-%m-%d %H:%M:%S"
        try:
            start_dt = datetime.strptime(first_date, fmt)
        except:
            start_dt = datetime.now()

        days_total = max((datetime.now() - start_dt).total_seconds() / 86400.0, 1.0)
        xirr = (((current_nav / config.STARTING_THB) ** (365.0 / days_total)) - 1) * 100.0

        return {
            "Total Closed Trade": total_trades,
            "Win Rate (%)": round(win_rate, 2),
            "Total Profit (THB)": round(total_profit, 2),
            "Unrealized P/L (THB)": round(unrealized_pl, 2),
            "Average Win (THB)": round(avg_win, 2),
            "Average Loss (THB)": round(avg_loss, 2),
            "Expectancy per Trade (THB)": round(expectancy, 2),
            "Best Annualized Trade (%)": round(max(ann_returns), 2),
            "Worst Annualized Trade (%)": round(min(ann_returns), 2),
            "Median Annualized Trade (%)": round(median_ann, 2),
            "Top 10% Annualized Trade (%)": round(top_10_ann, 2),
            "Bottom 10% Annualized Trade (%)": round(bottom_10_ann, 2),
            "XIRR (%)": round(xirr, 2),
            "Avg Capital/Year (THB)": round(avg_capital_year, 2),
            "Sharpe Ratio": round(sharpe, 2)
        }


def parse_logs_to_metrics(current_sell_price_per_g):
    logs = []
    if os.path.isfile(config.LOG_FILE_NAME):
        with open(config.LOG_FILE_NAME, "r", encoding="utf-8") as f:
            try:
                logs = json.load(f)
            except:
                pass

    open_lots = []
    closed_trades = []
    csv_rows = []  # 🎯 ตัวแปรสำหรับเก็บข้อมูลลง CSV

    first_date = logs[0].get("date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")) if logs else datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S")

    for log in logs:
        act = log.get("executed_action")
        date_str = log.get("date")
        amt_str = str(log.get("amount", ""))

        if act == "BUY":
            try:
                grams = float(amt_str.split(" ")[0])
                thb = float(amt_str.split("(")[1].split(" ")[0].replace(",", ""))
                price_per_g = thb / grams
                open_lots.append({"grams": grams, "thb": thb, "price_per_g": price_per_g, "date": date_str})
            except:
                pass

        elif act == "SELL":
            try:
                grams_sold = float(amt_str.split("Sold ")[1].split(" ")[0])
                thb_received = float(amt_str.split("(")[1].split(" ")[0].replace(",", ""))
                sell_price_per_g = thb_received / grams_sold

                while grams_sold > 0 and open_lots:
                    lot = open_lots[0]

                    # กำหนดตัวแปรสำหรับประมวลผล
                    buy_price_baht = lot["price_per_g"] * config.BAHT_TO_GRAM
                    sell_price_baht = sell_price_per_g * config.BAHT_TO_GRAM

                    if lot["grams"] <= grams_sold:
                        buy_amt = lot["thb"]
                        sell_amt = lot["grams"] * sell_price_per_g
                        days_held = AdvancedTradingAnalytics.calculate_days_held(lot["date"], date_str)
                        closed_trades.append({"buy_amount": buy_amt, "sell_amount": sell_amt, "days_held": days_held})

                        # คำนวณตาราง CN240
                        profit = sell_amt - buy_amt
                        profit_pct = (profit / buy_amt) * 100 if buy_amt > 0 else 0
                        ann_return = AdvancedTradingAnalytics.calculate_annualized_return(profit_pct, days_held)
                        cap_days_year = (buy_amt * days_held) / 365.0

                        csv_rows.append({
                            "Buy_Price/Gold_Baht": round(buy_price_baht, 2),
                            "Buy Date": lot["date"],
                            "Buy Amount": round(buy_amt, 2),
                            "Buy Weight (g)": round(lot["grams"], 4),
                            "Sell_Price/Gold_Baht": round(sell_price_baht, 2),
                            "Sell Date": date_str,
                            "Sell Amount": round(sell_amt, 2),
                            "Profit": round(profit, 2),
                            "Days Held": max(1, int(days_held)),
                            "%Profit/Deal": f"{round(profit_pct, 2)}%",
                            "%Profit/Year (Annual)": f"{round(ann_return, 2)}%",
                            "Capital x days/year": round(cap_days_year, 2)
                        })

                        grams_sold -= lot["grams"]
                        open_lots.pop(0)
                    else:
                        buy_amt = grams_sold * lot["price_per_g"]
                        sell_amt = grams_sold * sell_price_per_g
                        days_held = AdvancedTradingAnalytics.calculate_days_held(lot["date"], date_str)
                        closed_trades.append({"buy_amount": buy_amt, "sell_amount": sell_amt, "days_held": days_held})

                        # คำนวณตาราง CN240
                        profit = sell_amt - buy_amt
                        profit_pct = (profit / buy_amt) * 100 if buy_amt > 0 else 0
                        ann_return = AdvancedTradingAnalytics.calculate_annualized_return(profit_pct, days_held)
                        cap_days_year = (buy_amt * days_held) / 365.0

                        csv_rows.append({
                            "Buy_Price/Gold_Baht": round(buy_price_baht, 2),
                            "Buy Date": lot["date"],
                            "Buy Amount": round(buy_amt, 2),
                            "Buy Weight (g)": round(grams_sold, 4),
                            "Sell_Price/Gold_Baht": round(sell_price_baht, 2),
                            "Sell Date": date_str,
                            "Sell Amount": round(sell_amt, 2),
                            "Profit": round(profit, 2),
                            "Days Held": max(1, int(days_held)),
                            "%Profit/Deal": f"{round(profit_pct, 2)}%",
                            "%Profit/Year (Annual)": f"{round(ann_return, 2)}%",
                            "Capital x days/year": round(cap_days_year, 2)
                        })

                        lot["grams"] -= grams_sold
                        lot["thb"] -= buy_amt
                        grams_sold = 0
            except:
                pass

    # 🎯 สร้าง Rows สำหรับไม้ที่ยังคงถืออยู่ (Open Trades)
    current_date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    unrealized_pl = 0
    for lot in open_lots:
        current_value = lot["grams"] * current_sell_price_per_g
        profit = current_value - lot["thb"]
        unrealized_pl += profit

        buy_price_baht = lot["price_per_g"] * config.BAHT_TO_GRAM
        days_held = AdvancedTradingAnalytics.calculate_days_held(lot["date"], current_date_str)
        profit_pct = (profit / lot["thb"]) * 100 if lot["thb"] > 0 else 0

        csv_rows.append({
            "Buy_Price/Gold_Baht": round(buy_price_baht, 2),
            "Buy Date": lot["date"],
            "Buy Amount": round(lot["thb"], 2),
            "Buy Weight (g)": round(lot["grams"], 4),
            "Sell_Price/Gold_Baht": "",
            "Sell Date": "",
            "Sell Amount": "",
            "Profit": round(profit, 2),
            "Days Held": max(1, int(days_held)),
            "%Profit/Deal": f"{round(profit_pct, 2)}%",
            "%Profit/Year (Annual)": "",
            "Capital x days/year": ""
        })

    # 🎯 บันทึกลงไฟล์ CSV ตามลำดับ Column เป๊ะๆ
    cols = ['Buy_Price/Gold_Baht', 'Buy Date', 'Buy Amount', 'Buy Weight (g)', 'Sell_Price/Gold_Baht', 'Sell Date',
            'Sell Amount', 'Profit', 'Days Held', '%Profit/Deal', '%Profit/Year (Annual)', 'Capital x days/year']
    df_csv = pd.DataFrame(csv_rows)
    if not df_csv.empty:
        df_csv = df_csv[cols]
        df_csv.to_csv(config.DEALS_CSV_FILE, index=False, encoding='utf-8-sig')
    else:
        pd.DataFrame(columns=cols).to_csv(config.DEALS_CSV_FILE, index=False, encoding='utf-8-sig')

    return closed_trades, unrealized_pl, first_date