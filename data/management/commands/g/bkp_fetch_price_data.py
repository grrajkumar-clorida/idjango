import datetime
import time
from django.core.management.base import BaseCommand
from stocks.breeze_client import BreezeAPI
from data.models import StockPriceData, Import
from datetime import datetime, timedelta

class Command(BaseCommand):
    help = "Fetch latest stock prices from NSE and store in DB"
    
    def handle(self, *args, **kwargs):
        self.stdout.write('Fetching latest stock prices...')
        #while True:
        #    self.stdout.write('Fetching latest stock prices...')
            # Call your stock price fetching function here
            #time.sleep(60)  # Sleep for 60 seconds before fetching again

    breeze = BreezeAPI()
    breezeStatus = breeze.get_session_status()

    if breezeStatus is True:
        print('Breeze active!')
        # start_date = (datetime.today() - timedelta(days=365)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
        # end_date = datetime.today().strftime('%Y-%m-%dT%H:%M:%S.000Z')  # Today's date
        # response = breeze.get_historical_data("ITC", start_date, end_date)
        # print(df)
    
        stocks = StockPriceData.objects.all()
        process_data = Import.objects.all().filter(trade="50MA").filter(market='Equity').values_list('script', flat=True)
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
            #stock_name = breeze.get_isec_stock_code(stock_code)
            
            response = breeze.get_historical_data(stock, start_date, end_date, "NSE", "1day", "cash")
            print(response)
            
            # Check if response is valid
            if response.get("Success"):
                for entry in response["Success"]:
                    date = entry['datetime'].split(" ")[0]  # Extract date
                    close_price = float(entry["close"])

                    # Save to database
                    StockPriceData.objects.update_or_create(
                        stock_code = entry['stock_code'],
                        date = date,
                        defaults = {"close_price": close_price}
                    )
                
                print(f"Stock data for {stock} updated successfully.")
            else:
                print(f"Failed to fetch stock data for {stock}: {response}")
    
    else:
        print('error on API Connection')
        exit()

    get_stock_50ma()
    
    def fetch_stock_data(stock_code):
        """Fetches historical stock data from Breeze API and stores it in the database"""
        from datetime import datetime, timedelta
        
        # Calculate start date (1 year ago)
        start_date = (datetime.today() - timedelta(days=5)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
        end_date   = datetime.today().strftime('%Y-%m-%dT%H:%M:%S.000Z')  # Today's date

        #stock_code = "DEVYANI"
        print(" Stock Name: ",stock_code)

        # Call Breeze API
        #stock_name = breeze.get_isec_stock_code(stock_code)
        
        response = breeze.get_historical_data(stock_code, start_date, end_date, "NSE", "1day", "cash")
        
        # Check if response is valid
        if response.get("Success"):
            for entry in response["Success"]:
                date = entry['datetime'].split(" ")[0]  # Extract date
                close_price = float(entry["close"])

                # Save to database
                StockPriceData.objects.update_or_create(
                    stock_code = entry['stock_code'],
                    date = date,
                    defaults = {"close_price": close_price}
                )
            
            print(f"Stock data for {stock_code} updated successfully.")
        else:
            print(f"Failed to fetch stock data for {stock_code}: {response}")




    