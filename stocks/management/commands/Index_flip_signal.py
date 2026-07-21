import time
import django
import os
from django.core.management.base import BaseCommand
from infra.utils.infra import nifty_list #fetch_and_store_stock_data
from stocks.models import Stock, StockPrice

'''
    # Old Format to featch stock price. 
    # Now using Google Fiance.
'''
class Command(BaseCommand):
    help = "Fetch one month Nifty, NiftyNext50 stock prices from NSE and find SMA Flip Signals"

    def handle(self, *args, **kwargs):
    	file_path = os.path.join(settings.MEDIA_ROOT, "result_1.html")  # ✅ Correct file system path
    	output_csv = "/home/gr8/Documents/gr8/processed_stock_data.csv"  # Update path
    	self.stdout.write(self.style.SUCCESS("50MA stocks are added"))

print(nifty_list)
# Setup Django environment
#os.environ.setdefault("DJANGO_SETTINGS_MODULE", "idjango.settings")  # Replace with your project
#django.setup()
#bot_txt = ''
#print(nifty_list)
'''
	index_list = Stocks50MA.objects.values_list('script', flat=True)

	list_data = update_gfinance_data("Index_OHLC", stock_list) #SMC-Bhuvi
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
'''