from breeze_connect import BreezeConnect
from django.conf import settings
from .models import LiveTrade
from datetime import datetime, timedelta
import time
import pandas as pd
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)

api_status = False

class BreezeAPI:
    
    def __init__(self):
        self.api = BreezeConnect(api_key=settings.BREEZE_API_KEY)
        #self.api.generate_session(api_secret=settings.BREEZE_SECRET_KEY, session_token=settings.BREEZE_SESSION)
        try:
            dd = self.api.generate_session(api_secret=settings.BREEZE_SECRET_KEY, session_token=settings.BREEZE_SESSION)
            logging.info("Breeze API session established successfully :).")
            global api_status 
            api_status = True
            print("API Status: ", api_status)
            
        except Exception as e:
            logging.error(f"Sorry Failed to authenticate with Breeze API: {e}")

    def get_session_status(self):
        print("BreezeAPI Session active")

        return api_status

    def place_order(self, stock_code, exchange, quantity, order_type="MARKET", price=0, product="cash", action="BUY"):

        #check Stock code as per Isecure code
        icode = self.get_isec_stock_code(stock_code, exchange)
        print(f"Fetch stock as isecure code: {icode}")

        """ Place a live trade order """
        try:
            response = self.api.place_order(
                stock_code = stock_code,
                exchange_code = exchange,
                product = product,
                action = action,  # BUY or SELL
                order_type = order_type,  # MARKET or LIMIT
                stoploss = "",
                quantity = quantity,
                price = price,
                validity = "day"
            )
            #print("Order Response:", response)
        except Exception as e:
            print("Exception:", str(e))
        
        return response

    def modify_order(self, order_id, new_price):
        """ Modify an existing order """
        response = self.api.modify_order(order_id=order_id, price=new_price)
        return response

    def cancel_order(self, order_id):
        """ Cancel an existing order """
        response = self.api.cancel_order(order_id=order_id)
        return response

    def get_live_price(self, stock_code, exchange):
        """ Fetch the latest market price """
        isec_code = self.get_isec_stock_code(stock_code, exchange, name=1)
        id_code = isec_code[0]
        response = {}
        try:
            response = self.api.get_quotes(stock_code=id_code, exchange_code=exchange, product_type = "cash")
            for item in response['Success']:
                item['isec_name'] = isec_code[1]
            print(response)
        except Exception as e:
            print(f"Failed to fetch quotes for {id_code}: {e}")
        
        return response

    def update_trailing_stop_loss(self):
        """ Adjust TSL based on market price movements """
        trades = LiveTrade.objects.filter(status="Executed", trailing_stop_loss__isnull=False)
        for trade in trades:
            live_price = self.get_live_price(trade.stock_code, trade.exchange)

            if trade.action == "BUY":
                new_tsl = live_price - (live_price * (trade.tsl_percentage / 100))
                if new_tsl > trade.trailing_stop_loss:
                    trade.trailing_stop_loss = new_tsl
                    trade.save()
                    print(f"TSL Updated for {trade.stock_code}: {trade.trailing_stop_loss}")

            elif trade.action == "SELL":
                new_tsl = live_price + (live_price * (trade.tsl_percentage / 100))
                if new_tsl < trade.trailing_stop_loss:
                    trade.trailing_stop_loss = new_tsl
                    trade.save()
                    print(f"TSL Updated for {trade.stock_code}: {trade.trailing_stop_loss}")

    def update_profit_loss(self):
        trades = LiveTrade.objects.filter(status="Executed")
        for trade in trades:
            live_price = self.get_live_price(trade.stock_code, trade.exchange)
            if trade.action == "BUY":
                pnl = (live_price - trade.price) * trade.quantity
            else:  
                pnl = (trade.price - live_price) * trade.quantity

            trade.profit_loss = pnl
            trade.save()
            print(f"Updated P/L for {trade.stock_code}: {pnl}")

    # Backtesting
    def get_historical_data(self, stock_code, start_date, end_date, exchange="NSE", interval="1day", product_type="cash"):
        """ Fetch historical stock data from Breeze API """
        
        #check Stock code as per Isecure code
        icode = self.get_isec_stock_code(stock_code, exchange)
        print(f"Fetch stock  as isecure code: {icode}")

        #Brezze Api
        response = self.api.get_historical_data( 
            interval=interval,
            from_date=start_date, #.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            to_date=end_date, #.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            stock_code=icode,
            exchange_code=exchange,
            product_type="cash"
        )
        
        return response #pd.DataFrame(response)
    
    #get stock code        
    def get_isec_stock_code(self, stock_code, exchange_code = 'NSE', name=0):
        try:
            response = self.api.get_names(exchange_code, stock_code)
            if name == 1:
                isec_data = [response.get('isec_stock_code'), response.get('company name')]
            else:
                isec_data = response.get('isec_stock_code')

            return isec_data
        except Exception as e:
            logging.error(f"Sorry Failed fetch Stock Name: {e}")


