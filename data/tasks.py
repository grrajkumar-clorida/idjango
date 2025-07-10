import pandas as pd
from celery import shared_task
from data.models import StockPriceData, Stocks50MA

@shared_task
def calculate_50ma(tf=50):
    print("calc 50Ma fun")
    """Calculates the 50-day moving average for all stocks"""
    stock_codes = StockPriceData.objects.values_list("stock_code", flat=True).distinct()

    for symbol in stock_codes:
        stock_data = StockPriceData.objects.filter(stock_code=symbol).order_by('-date')[:tf]
        print(symbol, stock_data)
        if len(stock_data) < tf:
            continue  # Skip if not enough data

        # Convert to DataFrame
        df = pd.DataFrame.from_records(stock_data.values('date', 'close_price', 'script'))
        if tf >= 50:
            df['50MA'] = df['close_price'].rolling(window=50, min_periods=50).mean()

        df['20MA'] = df['close_price'].rolling(window=20, min_periods=20).mean()
        
        # Get the latest 50MA value
        latest_ma = df.iloc[-1]

        Stocks50MA.objects.update_or_create(
            stock_code = symbol,
            script = latest_ma['script'],
            date = latest_ma['date'],
            defaults = {'moving_average_50': round(latest_ma['50MA'], 2), 'moving_average_20': round(latest_ma['20MA'], 2)}
        )

    return "50MA Calculation Done"
