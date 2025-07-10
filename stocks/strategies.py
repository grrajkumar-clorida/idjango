import pandas as pd

#-------------------------------------------------------------------------------
def moving_average_crossover(df, short_window=50, long_window=200):
    """ Moving Average Crossover Strategy """

    df["SMA_Short"] = df["close"].rolling(window=short_window).mean()
    df["SMA_Long"] = df["close"].rolling(window=long_window).mean()
    
    df["Signal"] = 0  
    df.loc[df["SMA_Short"] > df["SMA_Long"], "Signal"] = 1  # Buy Signal
    df.loc[df["SMA_Short"] < df["SMA_Long"], "Signal"] = -1  # Sell Signal
    
    return df

def rsi_strategy(df, period=14, overbought=70, oversold=30):
    """ RSI Strategy """
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    df["Signal"] = 0
    df.loc[df["RSI"] > overbought, "Signal"] = -1  # Sell Signal
    df.loc[df["RSI"] < oversold, "Signal"] = 1  # Buy Signal
    
    return df

def ma50_strategy(df,  short_window=20, long_window=50):
    """ Moving Average Crossover Strategy """
    df["SMA_Short"] = df["close"].rolling(window=short_window).mean()
    df["SMA_Long"] = df["close"].rolling(window=long_window).mean()
    
    df["Signal"] = 0  
    df.loc[df["SMA_Short"] > df["SMA_Long"], "Signal"] = 1  # Buy Signal
    df.loc[df["SMA_Short"] < df["SMA_Long"], "Signal"] = -1  # Sell Signal
    
    return df
