import requests
import json
import urllib
from .models import Stock, StockPrice
from datetime import datetime
from breeze_connect import BreezeConnect


BREEZE_API_KEY = "7(#37242uZ313x83183830920d7063Vt"
BREEZE_SECRET_KEY = "622(60u2XJ01148688u269830A50DG57"
BREEZE_SESSION_KEY = ""

def fetch_stock_data(symbol):
    # Initialize SDK50661165
    STOCK = "{symbol}"

    try:
        
        api = BreezeConnect(api_key="7(#37242uZ313x83183830920d7063Vt")
        api.generate_session(api_secret="622(60u2XJ01148688u269830A50DG57", session_token="50661165")
    #breeze_connect.breeze_connect.BreezeConnect object at 0x789e29793620> respons 
        if(api):
            STOCK = api.get_names('NSE', 'INVENTURE')['isec_stock_code']
            order_info = api.place_order(stock_code=STOCK,
                    exchange_code="NSE",product="cash",action="buy",
                    order_type="market",stoploss="",quantity="1",price="",validity="day")
            
            print('orde:', order_info)
            if "Status" in order_info and order_info["Status"] == "200":
                return {
                    "symbol": symbol,
                    "last_price": data["data"]["last_price"],
                    "high": data["data"]["high_price"],
                    "low": data["data"]["low_price"],
                    "open": data["data"]["open_price"],
                    "volume": data["data"]["volume"]
                }
        #{'Success': None, 'Status': 500, 'Error': 'Cannot place orders when exchange is in Expiry.:'}
            elif "Status" in order_info and order_info["Status"] == "500":
                return {
                    "symbol": symbol,
                    ""
                }
            else :
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None
    #Error fetching data for TITAN: Unexpected error: Session key is expired.
    #STOCK = api.get_names('NSE', STOCK)['isec_stock_code']
""" 
    orderinfo = api.place_order(stock_code=STOCK,
                exchange_code="NSE",product="cash",action="buy",
                order_type="market",stoploss="",quantity="1",price="",validity="day")
    print(orderinfo)


    breeze = BreezeConnect(api_key="{BREEZE_API_KEY}")
    print("https://api.icicidirect.com/apiuser/login?api_key="+urllib.parse.quote_plus("your_api_key"))

    # Generate Session
    breeze.generate_session(api_secret="{BREEZE_SECRET_KEY}",
                        session_token="{BREEZE_SESSION_KEY}")

    # Generate ISO8601 Date/DateTime String
    import datetime
    iso_date_string = datetime.datetime.strptime("28/02/2021","%d/%m/%Y").isoformat()[:10] + 'T05:30:00.000Z'
    iso_date_time_string = datetime.datetime.strptime("28/02/2021 23:59:59","%d/%m/%Y %H:%M:%S").isoformat()[:19] + '.000Z'


    url = "https://api.icicidirect.com/breezeapi/api/v1/market/quote"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BREEZE_API_KEY}",
    }
    payload = {"symbol": symbol, "exchange": "NSE", "securityType": "EQ"}

    response = requests.post(url, json=payload, headers=headers)
    data = response.json()

    if "status" in data and data["status"] == "success":
        return {
            "symbol": symbol,
            "last_price": data["data"]["last_price"],
            "high": data["data"]["high_price"],
            "low": data["data"]["low_price"],
            "open": data["data"]["open_price"],
            "volume": data["data"]["volume"]
        }
    else:
        print(f"Error fetching data for {symbol}: {data.get('message', 'Unknown error')}")
        return None


"""