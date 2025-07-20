# Required packages
from breeze_connect import BreezeConnect
import pandas as pd
import datetime as dt
import time
import math
import openpyxl
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Breeze API login
breeze = BreezeConnect(api_key="7(#37242uZ313x83183830920d7063Vt")
breeze.generate_session(
    api_secret="622(60u2XJ01148688u269830A50DG57",
    session_token="52277948"
)

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("secrets/idjango-888-4e0163c2f1b5.json", scope)
client = gspread.authorize(creds)
sheet = client.open("idjango").sheet1

# Utility: Position Sizing
def get_buy_quantity(price):
    if price > 500:
        return 5
    elif price <= 500:
        return 10
    else:
        return 0

# Fetch historical data
def fetch_breeze_data(stock_code, from_date, to_date):
    df = breeze.get_historical_data_v2(
        interval="1day",
        from_date= from_date,
        to_date= to_date, #"2025-02-03T09:22:00.000Z",
        stock_code=stock_code,
        exchange_code="NSE",
        product_type="cash"
    )
    candles = pd.DataFrame(df['Success'])
    candles['datetime'] = pd.to_datetime(candles['datetime'])
    candles.set_index('datetime', inplace=True)
    candles = candles[['open', 'high', 'low', 'close', 'volume']]
    candles.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    return candles

# Strategy with signal logic + execution
def ema_crossover_autotrade(stock_code, from_date, to_date):
    df = fetch_breeze_data(stock_code, from_date, to_date)
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['Signal'] = 0
    df.loc[df['EMA9'] > df['EMA21'], 'Signal'] = 1
    df.loc[df['EMA9'] < df['EMA21'], 'Signal'] = -1
    df['Crossover'] = df['Signal'].diff()

    trades = []
    in_position = False
    entry_price = 0
    qty = 0
    stop_loss_price = 0

    for i in range(1, len(df) - 1):
        row = df.iloc[i]

        # Entry condition with 8% EMA price filter
        if row['Crossover'] == 2 and not in_position:
            next_open = df.iloc[i + 1]['Open']
            ema9_value = df.iloc[i]['EMA9']
            distance_from_ema = abs(next_open - ema9_value) / ema9_value

            if distance_from_ema <= 0.08:
                qty = get_buy_quantity(next_open)
                stop_loss_price = next_open * 0.90

                trades.append({
                    'Type': 'Buy',
                    'Date': df.index[i + 1],
                    'Price': next_open,
                    'Qty': qty,
                    'Stop Loss': stop_loss_price,
                    'EMA9': ema9_value
                })

                in_position = True
                entry_price = next_open
                remaining_qty = qty

        # Exit condition: profit booking or SL hit (trailing disabled)
        elif in_position:
            high = df.iloc[i]['High']
            low = df.iloc[i]['Low']
            target1 = entry_price * 1.05
            target2 = entry_price * 1.20

            if high >= target2 and remaining_qty >= int(qty * 0.5):
                sell_price = target2
                sell_qty = int(qty * 0.5)
                trades.append({'Type': 'Sell', 'Date': df.index[i], 'Price': sell_price, 'Qty': sell_qty, 'Reason': '20% Profit'})
                remaining_qty -= sell_qty
            elif high >= target1 and remaining_qty >= int(qty * 0.2):
                sell_price = target1
                sell_qty = int(qty * 0.2)
                trades.append({'Type': 'Sell', 'Date': df.index[i], 'Price': sell_price, 'Qty': sell_qty, 'Reason': '5% Profit'})
                remaining_qty -= sell_qty
            elif low <= stop_loss_price:
                sell_price = stop_loss_price
                trades.append({'Type': 'Sell', 'Date': df.index[i], 'Price': sell_price, 'Qty': remaining_qty, 'Reason': 'Stop Loss'})
                in_position = False

    return pd.DataFrame(trades)

# Run the strategy and sync to Excel and Google Sheets
df_trades = ema_crossover_autotrade("ITC", "2024-01-01T03:30:00.000Z", "2025-07-18T09:45:00.000Z")
df_trades.to_excel("itc_trade_log24.xlsx")
sheet.clear()
#sheet.update([df_trades.columns.values.tolist()] + df_trades.values.tolist())

# Clean up NaN and Timestamp issues before sending to Google Sheets
df_trades_clean = df_trades.copy()

# Convert Timestamps to strings
df_trades_clean['Date'] = df_trades_clean['Date'].astype(str)

# Replace NaN with blank or zero (your choice)
df_trades_clean = df_trades_clean.fillna('')  # or use .fillna(0)

# Optional: round numbers
df_trades_clean = df_trades_clean.round(2)

# Now update Google Sheet
sheet.update([df_trades_clean.columns.values.tolist()] + df_trades_clean.values.tolist())

print(df_trades)
