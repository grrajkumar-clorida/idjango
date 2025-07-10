from celery import shared_task
from .utils import fetch_and_store_stock_data

@shared_task
def scheduled_fetch_stock_data():
    stocks = ["ITC", "IOC", "TCS"]
    for stock in stocks:
        fetch_and_store_stock_data(stock, "NSE", "1day", 30)
    return "Stock data fetched successfully"
