import requests
import json
from .models import Stock, StockPrice
from datetime import datetime

NSE_URL = "https://www.nseindia.com/api/quote-equity?symbol={symbol}"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en",
    "Accept-Encoding": "gzip, deflate, br",
}

def fetch_nse_stock_data(symbol):
    try:
        print(NSE_URL, 'URRR')
        response = requests.get(NSE_URL.format(symbol=symbol), headers=HEADERS)
        data = response.json()
        print(data) 
        exit()
        last_trade_price = data['priceInfo']['lastPrice']
        open_price = data['priceInfo']['open']
        high_price = data['priceInfo']['intraDayHighLow']['max']
        low_price = data['priceInfo']['intraDayHighLow']['min']
        volume = data['marketDeptOrderBook']['tradeInfo']['totalTradedVolume']

        return {
            "symbol": symbol,
            "date": datetime.today().date(),
            "open_price": open_price,
            "high_price": high_price,
            "low_price": low_price,
            "close_price": last_trade_price,
            "volume": volume
        }
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None
