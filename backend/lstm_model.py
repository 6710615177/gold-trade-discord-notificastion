import os

os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import pandas as pd
import numpy as np
import warnings
import holidays
import config
from datetime import datetime
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
from tensorflow.keras.callbacks import EarlyStopping

warnings.filterwarnings('ignore')
MODEL_PATH = "lstm_gold_model.keras"


def build_and_train_full_model():
    """ฟังก์ชันสำหรับ Train รอบแรกแบบจำกัดเวลา (ถึงแค่ 31 ธ.ค. 68)"""
    print(f"[TRAINER] Loading data from {config.HISTORICAL_CSV}...")
    if not os.path.exists(config.HISTORICAL_CSV):
        print("❌ Error: Historical CSV not found!")
        return False

    df = pd.read_csv(config.HISTORICAL_CSV)
    df['Date'] = pd.to_datetime(df['Date'])

    # โหลดวันหยุดประเทศไทย
    thai_holidays = holidays.TH(years=[2025, 2026])

    # 🎯 Feature Engineering: ฤดูกาลและพฤติกรรม (อัปเดตใหม่)
    df['Month'] = df['Date'].dt.month
    df['Day_of_Week'] = df['Date'].dt.dayofweek  # 0=Mon, 6=Sun
    df['Is_Holiday'] = df['Date'].apply(lambda x: 1 if x in thai_holidays else 0)
    df['Is_High_Variation'] = 0
    df['Is_School_Break'] = 0

    for index, row in df.iterrows():
        month = row['Month']
        # วันหยุดยาว ปีใหม่ ตรุษจีน สงกรานต์ (Variation สูง)
        if month in [1, 2, 4, 12]:
            df.at[index, 'Is_High_Variation'] = 1

        # ปิดเทอมใหญ่ (มี.ค.-พ.ค.) และปิดเทอมเล็ก (ต.ค.)
        if month in [3, 4, 5, 10]:
            df.at[index, 'Is_School_Break'] = 1

    # กรองข้อมูลให้ Train ถึงแค่สิ้นปี 68
    df = df[df['Date'] < '2026-01-01'].reset_index(drop=True)
    print(f"[TRAINER] Data filtered: Training strictly from {df['Date'].min()} to {df['Date'].max()}")

    features = [
        'Buy_Price', 'Sell_Price', 'XAUUSD', 'THB_USD', 'RSI',
        'Month', 'Day_of_Week', 'Is_Holiday', 'Is_High_Variation', 'Is_School_Break'
    ]

    target_idx = features.index('Buy_Price')
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(df[features])

    lookback = 10
    X, y = [], []
    for i in range(len(scaled_data) - lookback):
        X.append(scaled_data[i:(i + lookback), :])
        y.append(scaled_data[i + lookback, target_idx])
    X, y = np.array(X), np.array(y)

    print(f"[TRAINER] Training deep model with {len(X)} samples and {len(features)} features...")
    model = Sequential([
        Input(shape=(X.shape[1], X.shape[2])),
        LSTM(50, return_sequences=True),
        Dropout(0.2),
        LSTM(50, return_sequences=False),
        Dropout(0.2),
        Dense(1)
    ])
    model.compile(optimizer='adam', loss='mean_squared_error')

    early_stop = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)

    model.fit(X, y, batch_size=32, epochs=100, validation_split=0.2, callbacks=[early_stop], verbose=1)

    model.save(MODEL_PATH)
    print(f"✅ [TRAINER] Model saved to {MODEL_PATH}")
    return True


def predict_next_price_with_lstm(live_data):
    """ฟังก์ชันสำหรับ Main Agent ใช้ทำนายราคา (Real-time Prediction & Online Learning)"""
    try:
        if not os.path.exists(MODEL_PATH):
            print("[LSTM] Model file not found. Running initial training...")
            build_and_train_full_model()

        model = load_model(MODEL_PATH)
        df = pd.read_csv(config.HISTORICAL_CSV)
        df['Date'] = pd.to_datetime(df['Date'])

        thai_holidays = holidays.TH(years=[2025, 2026])

        # เตรียม Features ให้กับข้อมูลประวัติศาสตร์
        df['Month'] = df['Date'].dt.month
        df['Day_of_Week'] = df['Date'].dt.dayofweek
        df['Is_Holiday'] = df['Date'].apply(lambda x: 1 if x in thai_holidays else 0)
        df['Is_High_Variation'] = 0
        df['Is_School_Break'] = 0
        for index, row in df.iterrows():
            month = row['Month']
            if month in [1, 2, 4, 12]: df.at[index, 'Is_High_Variation'] = 1
            if month in [3, 4, 5, 10]: df.at[index, 'Is_School_Break'] = 1

        features = [
            'Buy_Price', 'Sell_Price', 'XAUUSD', 'THB_USD', 'RSI',
            'Month', 'Day_of_Week', 'Is_Holiday', 'Is_High_Variation', 'Is_School_Break'
        ]

        # เตรียม Features ให้กับข้อมูลปัจจุบัน (Live Data)
        now = datetime.now()
        month_now = now.month
        day_of_week_now = now.weekday()
        is_holiday_now = 1 if now.date() in thai_holidays else 0
        is_hv = 1 if month_now in [1, 2, 4, 12] else 0
        is_sb = 1 if month_now in [3, 4, 5, 10] else 0

        new_row = pd.DataFrame([{
            'Date': now,
            'Buy_Price': live_data['HSH_Buy'],
            'Sell_Price': live_data['HSH_Sell'],
            'XAUUSD': live_data['xau_price'],
            'THB_USD': live_data['current_thb'],
            'RSI': live_data['rsi'],
            'Month': month_now,
            'Day_of_Week': day_of_week_now,
            'Is_Holiday': is_holiday_now,
            'Is_High_Variation': is_hv,
            'Is_School_Break': is_sb
        }])

        # นำข้อมูลปัจจุบันไปต่อท้าย และเก็บแค่ 1000 แถวล่าสุดเพื่อความรวดเร็ว
        df = pd.concat([df, new_row], ignore_index=True).tail(1000).reset_index(drop=True)

        target_idx = features.index('Buy_Price')
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaled_data = scaler.fit_transform(df[features])

        # Online Learning: ให้โมเดลเรียนรู้จากข้อมูลล่าสุด 1 Step (1 Epoch)
        lookback = 10
        X_live = np.array([scaled_data[-lookback - 1:-1, :]])
        y_live = np.array([scaled_data[-1, target_idx]])
        model.fit(X_live, y_live, epochs=1, verbose=0)
        model.save(MODEL_PATH)

        # Predict อนาคต
        last_window = scaled_data[-lookback:].reshape(1, lookback, len(features))
        predicted_scaled = model.predict(last_window, verbose=0)

        dummy = np.zeros((1, len(features)))
        dummy[0, target_idx] = predicted_scaled[0, 0]
        return float(scaler.inverse_transform(dummy)[0, target_idx])

    except Exception as e:
        print(f"[LSTM] Error: {e}")
        return None