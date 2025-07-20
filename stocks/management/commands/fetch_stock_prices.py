from django.core.management.base import BaseCommand
from stocks.utils import get_live_price #fetch_and_store_stock_data
from stocks.models import Stock, StockPrice
'''
    # Old Format to featch stock price. 
    # Now using Google Fiance.
'''
class Command(BaseCommand):
    help = "Fetch latest stock prices from NSE and store in DB"

    def handle(self, *args, **kwargs):
        stocks = Stock.objects.all()
        for stock in stocks:
            print(stock.symbol)
            #data =fetch_and_store_stock_data("ITC", "NSE", "1day", 30)
            data = get_live_price(stock.symbol)
            print("cmd eee: \n", data)
            stock_code = 'ITC'
            # #if data:
            # StockPrice.objects.update_or_create(
            #     symbol=stock_code,
            #     date=data["datetime"],
            #     defaults={
            #         "open_price": data["open"],
            #         "high_price": data["high"],
            #         "low_price": data["low"],
            #         "close_price": data["close"],/home/gr8/snap/Django/idjango/stocks/management/commands/fetch_stock_prices.py
            #         "volume": data["volume"],
            #     },
            # )

            self.stdout.write(self.style.SUCCESS(f"Updated: {stock.symbol}"))

