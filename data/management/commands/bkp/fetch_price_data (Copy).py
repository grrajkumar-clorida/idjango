import datetime
import time
from django.core.management.base import BaseCommand
from stocks.breeze_client import BreezeAPI
from data.models import StockPriceData, Source
from datetime import datetime, timedelta
from data.tasks import calculate_50ma


class Commands(BaseCommand):
    help = "Fetch latest stock prices from NSE and store in DB"
    
    def handle(self, *args, **kwargs):
        self.stdout.write('Fetching latest stock prices...')

    breeze = BreezeAPI()
    breezeStatus = breeze.get_session_status()

    if breezeStatus is False:
        print('Breeze active!')
    
        stocks = StockPriceData.objects.all()
        process_data = Source.objects.all().filter(trade="50MA").filter(market='Equity').values_list('script', flat=True)
        print(process_data)

        for stock in process_data:
            print(stock)
            from datetime import datetime, timedelta
        
            # Calculate start date (1 year ago)
            start_date = (datetime.today() - timedelta(days=365)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
            end_date   = datetime.today().strftime('%Y-%m-%dT%H:%M:%S.000Z')  # Today's date

            #stock_code = "DEVYANI"
            print(" Stock Name: ",stock)

            # Call Breeze API
            response = breeze.get_historical_data(stock, start_date, end_date, "NSE", "1day", "cash")
            print(response)
            
            # Check if response is valid
            if response.get("Success"):
                for entry in response["Success"]:
                    date = entry['datetime'].split(" ")[0]  # Extract date
                    close_price = float(entry["close"])
                    print(stock,entry['stock_code'], close_price, date)
                    # Save to database
                    # StockPriceData.objects.update_or_create(
                    #     stock_code = entry['stock_code'],
                    #     script = stock,
                    #     date = date,
                    #     defaults = {"close_price": close_price}
                    # )
                
                print(f"Stock data for {stock} updated successfully.")
            else:
                print(f"Failed to fetch stock data for {stock}: {response}")
    
    else:
        print('error on API Connection')
        #exit()
    
    # Calcuate 50MA price
    print('call 50MA!')
    df = calculate_50ma()






    