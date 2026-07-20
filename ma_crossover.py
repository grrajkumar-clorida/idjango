import pandas as pd
import yfinance as yf
import os

FAST_LENGTH = 9
SLOW_LENGTH = 21
MA_TYPE = 'SMA'  # Options: SMA, EMA, WMA, VWMA

def calculate_ma(df, length, ma_type):
    if ma_type == 'SMA':
        return df['Close'].rolling(window=length).mean()
    elif ma_type == 'EMA':
        return df['Close'].ewm(span=length, adjust=False).mean()
    elif ma_type == 'WMA':
        weights = range(1, length + 1)
        return df['Close'].rolling(length).apply(lambda prices: sum(weights[i] * prices[i] for i in range(length)) / sum(weights), raw=True)
    elif ma_type == 'VWMA':
        return (df['Close'] * df['Volume']).rolling(window=length).sum() / df['Volume'].rolling(window=length).sum()
    else:
        raise ValueError("Unsupported MA type")

def backtest(df):
    df['FastMA'] = calculate_ma(df, FAST_LENGTH, MA_TYPE)
    df['SlowMA'] = calculate_ma(df, SLOW_LENGTH, MA_TYPE)
    
    df['Signal'] = 0
    df.loc[df['FastMA'] > df['SlowMA'], 'Signal'] = 1
    df.loc[df['FastMA'] < df['SlowMA'], 'Signal'] = 0
    df['Position'] = df['Signal'].diff()
    
    buy_signals = df[df['Position'] == 1]
    sell_signals = df[df['Position'] == -1]

    initial_cash = 100000
    cash = initial_cash
    position = 0
    portfolio = []
    
    for i in range(len(df)):
        if df['Position'].iloc[i] == 1:
            price = df['Close'].iloc[i]
            qty = cash // price
            position = qty
            cash -= qty * price
            print("df Index: ",df.index[i])
            print("df Price: ", type(price))
            print("**************")
            portfolio.append((df.index[i], 'BUY', price, qty))
        elif df['Position'].iloc[i] == -1: #and position > 0:
            price = df['Close'].iloc[i]
            cash += position * price
            portfolio.append((df.index[i], 'SELL', price, position))
            position = 0

    final_value = cash + (position * df['Close'].iloc[-1])
    profit = final_value - initial_cash
    return portfolio, profit

def main():
    with open('stocks.txt') as f:
        symbols = [line.strip() for line in f if line.strip()]

    for symbol in symbols:
        print(f"\n📊 Backtesting {symbol}...")
        df = yf.download(symbol, period="6mo", interval="1d", auto_adjust=True)
        if df.empty:
            print(f"⚠️ No data for {symbol}")
            continue

        trades, profit = backtest(df)
        print(f"Profit :: {profit}", type(profit))
        for trade in trades:
            #print(type(trade))
            for t in trade:
                print(t)
            exit()
            #print(trade[0],trade[1],trade[2],trade[3] )
            # print(f"T1: {trade[0]}")
            # print(f"T2: {trade[1]}")
            # print(f"T3: {trade[2]}")
            # print(f"T4: {trade[3]}")
            # print('=======')
            #print(f"{trade[0].date()} | {trade[1]} | Price: {trade[2]} | Qty: {trade[3]}")
        #print(f"💰 Final Profit for {symbol}: - ₹{profit}")

if __name__ == "__main__":
    main()

'''
📊 Backtesting ITC.NS...
[*********************100%***********************]  1 of 1 completed
2025-03-13 | BUY | Price: Ticker
ITC.NS    404.595276
Name: 2025-03-13 00:00:00, dtype: float64 | Qty: Ticker
ITC.NS    247.0
Name: 2025-03-13 00:00:00, dtype: float64
2025-05-30 | SELL | Price: Ticker
ITC.NS    418.049988
Name: 2025-05-30 00:00:00, dtype: float64 | Qty: Ticker
ITC.NS    247.0
Name: 2025-03-13 00:00:00, dtype: float64
2025-07-15 | BUY | Price: Ticker
ITC.NS    422.100006
Name: 2025-07-15 00:00:00, dtype: float64 | Qty: Ticker
ITC.NS    244.0
dtype: float64
💰 Final Profit for ITC.NS: - ₹Ticker
ITC.NS    3213.510864
dtype: float64
'''