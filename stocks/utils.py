from stocks.breeze_client import BreezeAPI
from django.conf import settings
from datetime import datetime, timedelta
from django.utils import timezone
from .models import StockData
from data.models import Stocks50MA
from data.models import *
from django.http import JsonResponse
from django.conf import settings
#import
import pandas as pd
import requests



def send_telegram_message(message):
    """Send a message to the Telegram bot."""
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": message
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to send Telegram message: {e}")

def get_live_price(stock):
    breeze = BreezeAPI()
    
    # Fetch live market data for ITC (NSE)
    response = breeze.get_live_price(stock, "NSE")

    # Fetch live market data for NSE Stock
    if response: #and "Success" in response.get("Status", "200"):
        data = response.get("Success", [])
        if data:
            latest_data = next((entry for entry in reversed(data) if entry.get("exchange_code") == "NSE"), None)
            current_price = latest_data.get('ltp', 'N/A')

            #Stocks50MA.objects.filter(stock_code={stock}).update(stock_cmp=current_price).save()
            s50ma = Stocks50MA.objects.get(stock_code=stock)
            s50ma.stock_cmp = current_price
            s50ma.cmp_date = timezone.now()
            s50ma.save()
    
            return current_price #JsonResponse({'NSE_PRICE':latest_data.get('ltp', 'N/A')})


#settings.BREEZE_SECRET_KEY, session_token=settings.BREEZE_SESSION
def fetch_and_store_stock_data(symbol, exchange="NSE", interval="1day", days=30):
    try:
        breeze = BreezeAPI()
        breezeStatus = breeze.get_session_status()
        
        if breezeStatus is True:

            # Get Date Range
            current_time = datetime.now()
            from_date = current_time - timedelta(days=days)

        # Fetch Historical Data
        #data = breeze.get_historical_data_v2(
        data = breeze.get_historical_data(
            interval=interval,
            from_date=from_date.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            to_date=current_time.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            stock_code=symbol,
            exchange_code=exchange,
            product_type="cash"
        )

        # Convert Data to Pandas DataFrame
        df = pd.DataFrame(data["Success"])
        #df['datetime'] = pd.to_datetime(df['datetime'])

        # Convert to timezone-aware datetime
        #naive_date = datetime.strptime(df['datetime'].split(" ")[0], "%Y-%m-%d")
        #aware_date = timezone.make_aware(naive_date, timezone.get_current_timezone())
        #print(aware_date, df['datetime'])
        #exit()
        # Store in Django Model
        '''
        for _, row in df.iterrows():
            print(row)
            StockData.objects.update_or_create(
                symbol=symbol,
                exchange=exchange,
                interval=interval,
                #date=row['datetime'],
                defaults={
                    "open_price": float(row["open"]),
                    "high_price": float(row["high"]),
                    "low_price": float(row["low"]),
                    "close_price": float(row["close"]),
                    "volume": int(row["volume"]),
                }
            ) '''
        print(f"✅ Data stored for {symbol} - {exchange} ({interval})")
        return df
    except Exception as e:
        print(f"❌ Error fetching the data for {symbol}: {e}")
