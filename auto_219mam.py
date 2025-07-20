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
    position = None

    for i in range(1, len(df) - 1):
        row = df.iloc[i]

        # Entry condition with 8% EMA price filter
        if row['Crossover'] == 2:
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

                position = {
                    'entry_price': next_open,
                    'qty': qty,
                    'stop_loss_price': stop_loss_price,
                    'remaining_qty': qty
                }

        # Exit condition: profit booking or SL hit
        if position:
            high = df.iloc[i]['High']
            low = df.iloc[i]['Low']
            entry_price = position['entry_price']
            qty = position['qty']
            stop_loss_price = position['stop_loss_price']
            remaining_qty = position['remaining_qty']

            target1 = entry_price * 1.05
            target2 = entry_price * 1.20

            if high >= target2 and remaining_qty >= int(qty * 0.5):
                sell_price = target2
                sell_qty = int(qty * 0.5)
                trades.append({'Type': 'Sell', 'Date': df.index[i], 'Price': sell_price, 'Qty': sell_qty, 'Reason': '20% Profit'})
                position['remaining_qty'] -= sell_qty
            elif high >= target1 and remaining_qty >= int(qty * 0.2):
                sell_price = target1
                sell_qty = int(qty * 0.2)
                trades.append({'Type': 'Sell', 'Date': df.index[i], 'Price': sell_price, 'Qty': sell_qty, 'Reason': '5% Profit'})
                position['remaining_qty'] -= sell_qty
            elif low <= stop_loss_price:
                sell_price = stop_loss_price
                trades.append({'Type': 'Sell', 'Date': df.index[i], 'Price': sell_price, 'Qty': position['remaining_qty'], 'Reason': 'Stop Loss'})
                position = None

        # Reset on crossover down (forced exit)
        if row['Crossover'] == -2 and position:
            sell_price = df.iloc[i + 1]['Open']
            trades.append({'Type': 'Sell', 'Date': df.index[i + 1], 'Price': sell_price, 'Qty': position['remaining_qty'], 'Reason': 'EMA Cross Exit'})
            position = None

    return pd.DataFrame(trades)

# Run across defined time windows
windows = [
    ("2024-12-05T03:30:00.000Z", "2024-12-11T09:45:00.000Z"),
    ("2025-02-03T03:30:00.000Z", "2025-02-14T09:45:00.000Z"),
    ("2025-03-17T03:30:00.000Z", "2025-05-30T09:45:00.000Z")
]

final_df = pd.DataFrame()

for start, end in windows:
    df_trades = ema_crossover_autotrade("ITC", start, end)
    final_df = pd.concat([final_df, df_trades])

# Clean and export
final_df['Date'] = final_df['Date'].astype(str)
final_df = final_df.fillna('')
final_df = final_df.round(2)

# Calculate performance summary
buy_trades = final_df[final_df['Type'] == 'Buy']
sell_trades = final_df[final_df['Type'] == 'Sell']

invested_amt = (buy_trades['Price'] * buy_trades['Qty']).sum()
realized_amt = (sell_trades['Price'] * sell_trades['Qty']).sum()
pnl = realized_amt - invested_amt

summary = pd.DataFrame({
    'Total Buy Amount': [invested_amt],
    'Total Sell Amount': [realized_amt],
    'Net P&L': [pnl]
})

# Export to Excel and Google Sheets
final_df.to_excel("itc_trade_log242.xlsx", index=False)
sheet.clear()
sheet.update([final_df.columns.values.tolist()] + final_df.values.tolist())

print(final_df)
print("\nSummary:")
print(summary)
