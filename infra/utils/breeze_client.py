from breeze_connect import BreezeConnect
from django.conf import settings
from stocks.models import LiveTrade
from datetime import datetime, timedelta
import time
import pandas as pd
import logging
import base64
import socketio
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)

api_status = False

class BreezeAPI:
    
    def __init__(self):
        self.api = BreezeConnect(api_key=settings.BREEZE_API_KEY)
        self.sio = None   # socket client

        try:
            from coredata.utils.breeze_session import get_breeze_session

            session_token = get_breeze_session()
            logging.info(f"breeze_session : {session_token}")
            logging.info(f"Breeze Secret Key : {settings.BREEZE_SECRET_KEY}")

            if not session_token:
                raise ValueError(
                    "Breeze session missing. Login via ICICI API user home "
                    "so it redirects to this app with ?apisession=<session>"
                )

            dd = self.api.generate_session(
                api_secret=settings.BREEZE_SECRET_KEY,
                session_token=session_token,
            )
            logging.info("Breeze API session established successfully :).")
            global api_status
            api_status = True
            self.api_status = True
        except Exception as e:
            logging.error(f"Sorry Failed to authenticate with Breeze API On : {e}")
            self.api_status = False

    # ------------------------------
    # Websocket / Live streaming
    # ------------------------------
    def get_session_status(self):
        print("BreezeAPI Session active")

        return self.api_status

    # ------------------------------
    # Websocket / Live streaming
    # ------------------------------    
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

    # ------------------------------
    # Websocket / Live streaming
    # ------------------------------
    def modify_order(self, order_id, new_price):
        """ Modify an existing order """
        response = self.api.modify_order(order_id=order_id, price=new_price)
        return response

    # ------------------------------
    # Websocket / Live streaming
    # ------------------------------
    def cancel_order(self, order_id):
        """ Cancel an existing order """
        response = self.api.cancel_order(order_id=order_id)
        return response

    # ------------------------------
    # Websocket / Live streaming
    # ------------------------------
    def get_live_price(self, stock_code, exchange):
        """ Fetch the latest market price """
        isec_code = self.get_isec_stock_code(stock_code, exchange, name=1)
        
        id_code = isec_code[0]
        response = {}
        try:
            response = self.api.get_quotes(stock_code=id_code, exchange_code=exchange, product_type = "cash")
            for item in response['Success']:
                item['isec_name'] = isec_code[1]
                item['isec_code'] = id_code

        except Exception as e:
            print(f"Failed to fetch quotes for {id_code}: {e}")
        
        return response

    # ------------------------------
    # Websocket / Live streaming
    # ------------------------------
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

    # ------------------------------
    # Websocket / Live streaming
    # ------------------------------
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

    # ------------------------------
    # Websocket / Live streaming
    # ------------------------------    # Backtesting
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
    
    # ------------------------------
    # Websocket / Live streaming
    # ------------------------------
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

    # ------------------------------
    # Websocket / Live streaming
    # ------------------------------
    def start_websocket(self, script_codes, channel_name="1SEC", on_ticks=None):
        """
        Start Breeze OHLCV websocket stream.
        
        Args:
            script_codes (list): e.g. ["4.1!1594", "1.1!500209"]
            channel_name (str): "1SEC", "1MIN", "5MIN", "30MIN"
            on_ticks (callable): callback function for incoming ticks
        """
        if not self.api_status:
            raise Exception("Breeze session not active. Please login again.")

        if self.sio and self.sio.connected:
            logging.info("Websocket already connected.")
            return self.sio

        self.sio = socketio.Client()

        # default handler
        def default_ticks(data):
            logging.info(f"Received ticks: {data}")

        tick_handler = on_ticks or default_ticks
        self.sio.on(channel_name, tick_handler)

        # connect to breeze socket
        self.sio.connect(
            "https://breezeapi.icicidirect.com/",
            socketio_path="ohlcvstream",
            headers={"User-Agent": "python-socketio[client]/socket"},
            auth={"user": self.user_id, "token": self.session_token},
            transports="websocket",
            wait_timeout=3,
        )

        # join channel
        self.sio.emit("join", script_codes)
        logging.info(f"Subscribed to {script_codes} on {channel_name}")

        return self.sio

    def unsubscribe(self, script_codes):
        """Unsubscribe from given script codes."""
        if self.sio and self.sio.connected:
            self.sio.emit("leave", script_codes)
            logging.info(f"Unsubscribed from {script_codes}")

    def stop_websocket(self):
        """Disconnect socket client."""
        if self.sio:
            self.sio.disconnect()
            logging.info("Breeze websocket disconnected.")
            self.sio = None

