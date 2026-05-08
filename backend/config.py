import os
from dotenv import load_dotenv

# โหลดค่าจากไฟล์ .env
load_dotenv()

# 🎯 สร้างตัวแปรบังคับตำแหน่งไฟล์ ให้อยู่ในโฟลเดอร์เดียวกับ config.py (คือโฟลเดอร์ backend เสมอ)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# API Keys (ดึงจากตัวแปร Environment)
GROQ_API_KEYS = [
    os.getenv("GROQ_API_KEY_1", ""),
    os.getenv("GROQ_API_KEY_2", ""),
    os.getenv("GROQ_API_KEY_3", ""),
    os.getenv("GROQ_API_KEY_4", ""),
    os.getenv("GROQ_API_KEY_5", ""),
    os.getenv("GROQ_API_KEY_6", ""),
    os.getenv("GROQ_API_KEY_7", ""),
    os.getenv("GROQ_API_KEY_8", ""),
]
GROQ_API_KEYS = [k for k in GROQ_API_KEYS if k.strip() != ""]

ENABLE_UNIVERSITY_API = True
TEAM_API_KEY = os.getenv("TEAM_API_KEY", "")
LOG_BASE_URL = "https://goldtrade-logs-api.poonnatuch.workers.dev"

# 🎯 Portfolio & File Settings (แก้ให้ใช้ BASE_DIR ล็อกเป้าหมาย)
STARTING_THB = 1500.00
TRADE_MIN_THB = 1000.00
PORTFOLIO_FILE = os.path.join(BASE_DIR, "portfolio.json")
LOG_FILE_NAME = os.path.join(BASE_DIR, "live_gold_log.json")
HISTORICAL_CSV = os.path.join(BASE_DIR, "gold_historical_2568_2569_combined.csv")
DEALS_CSV_FILE = os.path.join(BASE_DIR, "CN240_Deals_Record.csv")
BAHT_TO_GRAM = 15.244

# Market Settings
GOLD_HISTORY_PERIOD = "3mo"
FOREX_HISTORY_PERIOD = "14d"
EMA_FAST = 14
EMA_SLOW = 50
RSI_PERIOD = 14
RSI_BUY_THRESHOLD = 40
RSI_SELL_THRESHOLD = 60

# System Timers
RUN_EVERY_MINUTES = 2
DECISION_TIMEOUT_SECONDS = 15

# Trading Quotas
TRADE_QUOTAS = {
    "WD_Morning": 2,
    "WD_Afternoon": 2,
    "WD_Evening": 2,
    "WD_Late_Night": 0,
    "WE_Active": 2,
}