import datetime
import time
import requests
from decouple import config
from datetime import datetime
from django.conf import settings
from datetime import datetime, timedelta
from data.models import Stocks50MA, StockPriceData
from django.core.management.base import BaseCommand


from oauth2client.service_account import ServiceAccountCredentials
from infra.utils.telegram import send_telegram
from infra.utils.infra import date_format, safe_float
from infra.utils.gfinance import get_gfinance_data, filter_stock, update_gfinance_data

class Command(BaseCommand):
    help = "Fetch latest stock Current Market Prices from Google Fiance and store in Data"
    
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Stocks latest prices Updated'))
    #script = 'JKLAKSHMI'
    stock_list = Stocks50MA.objects.values_list('script', flat=True)
    #stock_list = Stocks50MA.objects.filter(script=script).values_list('script', flat=True)
    print("Total Stocks of 50MA: ", len(stock_list))
    
    '''
    *   Insert Stocks code(sricpt) to GooglFinace Sheet(getCMP)
    *   Fetch CMP (Current Market Price)
    *   Trade day, 52 week High and Low
    *   App Script to fetch data from getCMP to marketPrice sheet.
    *   
    '''    
    # Push stocks to Google Sheet (getCMP)
    list_data = update_gfinance_data("getCMP", stock_list)
    print(f"Get CMP for {len(stock_list)} in google finance: ", list_data)

    # Using AppScript to copy getCMP values to marketPrice Sheet.
    copy_GF_cmp = config('GSHEET_APP_SCRIPT_CMP')

    response = requests.get(copy_GF_cmp)
    print("sheet response:", response)

    # Get SMA50 Value from marketPrice Sheet
    spreadsheet_id, sheet_name, api_key = settings.GSHEET_ID, "marketPrice", settings.GSHEET_KEY
    gsheet_data = get_gfinance_data(spreadsheet_id,sheet_name, api_key)

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
                    "date": date_format(row_dict.get("Trad Date")),
                    "live21ma": row_dict.get("21MA"),
                    "live50ma": row_dict.get("50MA"),
                    "live9ma": row_dict.get("9MA"),
                    "cp50ma": row_dict.get("CP50MA%"),
                    "live921": row_dict.get("Cross921MA")
                }
            )

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

        '''
        cmp_price    - Live closing price
        cmp_21ma     - Live 21SMA
        cmp_50ma     - live 50SMA
        cmp_09ma     - Live 09SMA
        cmp_50pa     - Live 50price diff in %
        cmp_921p     - Live 9,21price diff in %
        sma_price    - SMA price on script
        sma_50ma     - SMA 50 price on script
        sma_50pa     - SMA 50 price %
        sma_range    - SMA price range
        
        status_set = {
        '0 - Invalid', '1 - Over Value', '2 - Stoploss', '3 - Completed', '4 - New', '5 - Update',
        '6 - Entry', '7 - Confirmation', '8 - Order', '9 - Target 1', '10 - Target 2', 
        '11 - Target 3', '12 - Above T3', '13 - Altra'
        }

        '''
        cmp_price   = live_data.close_price  # Replace with your actual field
        cmp_50ma    = live_data.live50ma
        cmp_50pa    = live_data.cp50ma
        sma_price   = stock.stock_cmp
        sma_50ma    = stock.moving_average_50
        sma_50pa    = stock.percent_50ma
        sma_range   = stock.range_50ma
        

        # Step 3: Compare and set status Target Above T3 New updated Entry
        # Status logic based on 50MA strategy:
        # 0: Invalid (CMP < 50MA)
        # 1: Over Value (CP50MA% > 6%)
        # 2: Stoploss (CP50MA% < 1%)
        # 4: New
        # 5: Update
        # 6: Entry (CMP > 50MA but not confirmed)
        # 7: Confirmation (CP50MA% between 2-7%, ready for entry)
        # 8: Order (CMP > SMA price, ready to place order)
        # 9-12: Target levels (updated by position monitor)
        
        # Only update status if stock doesn't have an open position (status < 8)
        # If status >= 8, position monitor will handle status updates
        if stock.status < 8:
            if cmp_price < cmp_50ma:  # CMP below 50MA
                stock.status = 0  # Invalid
            elif cmp_50pa > 6:  # Over valued
                stock.status = 1  # Over Value
            elif cmp_50pa < 1.0:  # Below 50MA by more than 1%
                stock.status = 2  # Stoploss
            elif 2.0 <= cmp_50pa <= 7.0:  # In confirmation range (2-7%)
                stock.status = 7  # Confirmation - ready for entry check
            elif cmp_price > sma_price and 5.0 <= cmp_50pa <= 6.0:  # Entry range (5-6%)
                stock.status = 8  # Order - ready to place order
            elif cmp_price > cmp_50ma:  # Above 50MA but not in entry range
                stock.status = 6  # Entry - watching
            else:
                stock.status = 4  # New/Update
        
        print(f"Status: {stock.script} - c:{cmp_50ma} - sma:{sma_price} - p:{cmp_price} - %:{cmp_50pa} - status:{stock.status}")
        stocks_to_update.append(stock)

    #print(stocks_to_update)
        
    # Step 4: Bulk update all in one DB hit
    Stocks50MA.objects.bulk_update(stocks_to_update, ['status'])

    print(f"✅ Updated {len(stocks_to_update)} stock status values.")

