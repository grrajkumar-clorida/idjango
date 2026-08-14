import datetime
import time
from django.core.management.base import BaseCommand
from infra.utils.breeze_client import BreezeAPI
from data.models import Source, Stocks50MA
#from stock.models import MovingAverage
#from data.tasks import calculate_50ma
from datetime import datetime, timedelta
from django.utils import timezone

class Command(BaseCommand):
    help = "Fetch latest stock prices from NSE and store in DB"
    
    def handle(self, *args, **kwargs):
        self.stdout.write('Fetch stock 50MA prices status...')

    breeze = BreezeAPI()
    breezeStatus = breeze.get_session_status()

    if breezeStatus is True:
        print('Breeze active!')
    else:
    	print('Breeze Access Error!')
    	exit()

    #stocks = StockPriceData.objects.all()
    process_data = Stocks50MA.objects.all().filter(status=5) #.values_list('stock_code', flat=True)

    for ticker in process_data:
    	print("ticker: ",ticker)
    	ma50 = ticker.moving_average_50
    	ma20 = ticker.moving_average_20
    	stock = ticker.ticker
    	result = breeze.get_live_price(stock, "NSE")
    	#icode =	breeze.get_isec_stock_code(stock_code, exchange)
    	print(result);
    	
    	status = 0
    	if result.get("Success"):
    		data = result.get("Success")
    		nse_ltp = next((item['ltp'] for item in data if item['exchange_code'] == 'NSE'), None)
    		idcode = data[0]['isec_code'];
    		print(nse_ltp)
    		
    		# Checking 50MA value with cmp.
    		# if
    		percentage = round((( (nse_ltp - ma50) / ma50) * 100), 2)
    		print(percentage, 'Price percentage DIff %')
    		if nse_ltp > ma50:
    			print('Stock crossed 50MA')
    			status = 6
    		elif nse_ltp > ma20:
    			print('MA20 crossed!')
    			status = 7
    		else:
    			print('Invalid 50MA')
    			status = 1
    		try:
	    		ticker.status = status
	    		ticker.ticker = idcode
	    		ticker.stock_cmp = nse_ltp
	    		ticker.cmp_date = timezone.now()  # fixes the warning
	    		ticker.save()

	    	except ticker.DoesNotExist:
    			obj = ticker.objects.create(field=new_value)
    
    #trade = breeze.place_order('ITC', "NSE", 1, order_type="MARKET", price=0, product="cash", action="BUY")
    #print(trad)
    	
