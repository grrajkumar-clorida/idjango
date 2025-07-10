import datetime
import time
import requests
from django.core.management.base import BaseCommand
from stocks.breeze_client import BreezeAPI
from data.models import Stocks50MA, StockPriceData, Source
from datetime import datetime, timedelta
from data.tasks import calculate_50ma
from django.conf import settings
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from data.utils import send_telegram_message, safe_float, get_google_sheet_data,  update_google_sheet  # 👈 import here

class Command(BaseCommand):
    help = "Fetch latest stock Current Market Prices from Google Fiance and store in Data"
    
    def handle(self, *args, **kwargs):
        self.stdout.write('Fetched latest stock prices...')
    
    #stocks = Stocks50MA.objects.all()
    stock_list = Stocks50MA.objects.values_list('script', flat=True)
    print("Total Stocks of 50MA: ", len(stock_list))
    
    '''
    *   Insert Stocks code(sricpt) to GooglFinace Sheet(getCMP)
    *   Fetch CMP (Current Market Price)
    *   Trade day, 52 week High and Low
    *   App Script to fetch data from getCMP to marketPrice sheet.
    *   
    '''    
    # Push stocks to Google Sheet (getCMP)
    list_result = update_google_sheet("getCMP", stock_list)
    print(f"Get CMP for {len(stock_list)} in google finance: ", list_result)
'''
    # Using AppScript to copy getCMP values to marketPrice Sheet.
    copyGF_cmp = "https://script.google.com/macros/s/AKfycbyoKhcfb7ehHKe_VuL6ENv6Hg-oautHDbMQlCamkQgRyF9uakhpulCPQqiLDKJUSGw7/exec?sheet=getCMP"

    response = requests.get(copyGF_cmp)
    print("sheet response:", response)

    # Get SMA50 Value from marketPrice Sheet
    spreadsheet_id, sheet_name, api_key = settings.GSHEET_ID, "marketPrice", settings.GSHEET_KEY
    gsheet_data = get_google_sheet_data(spreadsheet_id,sheet_name, api_key)
    print(gsheet_data)
    rows = gsheet_data.get("values", [])
    headers = rows[0]

    for row in rows[1:]:
        row_dict = dict(zip(headers, row))
        script = row_dict.get("Script")
             
        if(script):
            obj, created = StockPriceData.objects.update_or_create(
                script = script,
                defaults= {
                    "stock_code": script,
                    "close_price": safe_float(row_dict.get("CMP")),
                    "date": row_dict.get("Trad Date"),
                    "live21ma": row_dict.get("21MA"),
                    "live50ma": row_dict.get("50MA"),
                    "live9ma": row_dict.get("9MA"),
                    "cp50ma": row_dict.get("CP50MA%"),
                }
            )
'''
for i in range(1):
    print(i)
    # Step 1: Create a script:cmp dict from StockPriceData
    sma_map = {
        live_price.stock_code: live_price for live_price in StockPriceData.objects.all()
    }

    # Step 2: Prepare list of Stocks50MA objects to update
    stocks_to_update = []

    for stock in Stocks50MA.objects.all():
        live_data = sma_map.get(stock.script)
        if live_data.live50ma is None:
            continue  # No price data available, skip

        cmp_price = live_data.close_price  # Replace with your actual field
        sma_price = live_data.live50ma
        crr_50sma = live_data.cp50ma
        print(f"CMP: {stock.script} - {stock.status} - {cmp_price} - {sma_price}")

        # Step 3: Compare and set status Target Above T3 New updated Entry
        status_set = {'0 - Invalid', '1 - Over Value', '2- Stoploss', '3- Completed', '4- New', '5- Update', '6- Entry', '7- Confirmation', '8- Order', '9- Target 1', '10- Target 2', '11- Target 3', '12- Above T3'}
        if sma_price > cmp_price : #0
            stock.status = 0
        elif crr_50sma > 6: #1
            stock.status = 1
        elif sma_price < cmp_price:
            stock.status = 8
        else:
            stock.status = 6
        
        print(f"Status: {stock.script} - c:{crr_50sma} - sma:{sma_price} - p:{cmp_price} - status:{stock.status}")
        stocks_to_update.append(stock)

    #print(stocks_to_update)
        
    # Step 4: Bulk update all in one DB hit
    Stocks50MA.objects.bulk_update(stocks_to_update, ['status'])

    print(f"✅ Updated {len(stocks_to_update)} stock status values.")

