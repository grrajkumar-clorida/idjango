import datetime
import time
from django.core.management.base import BaseCommand
from stocks.breeze_client import BreezeAPI
from data.models import Source, Stocks50MA
#from stock.models import MovingAverage
from data.tasks import calculate_50ma
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
    process_data = Stocks50MA.objects.all().filter(status=0) #.values_list('stock_code', flat=True)

    for icode in process_data:
    	print("icode: ",icode)
    	ma50 = icode.moving_average_50
    	ma20 = icode.moving_average_20
    	stock = icode.stock_code
    	result = breeze.get_live_price(stock, "NSE")
    	status = 0
    	if result.get("Success"):
    		data = result.get("Success")
    		nse_ltp = next((item['ltp'] for item in data if item['exchange_code'] == 'NSE'), None)

    		print(nse_ltp)
    		# Checking 50MA value with cmp.
    		# if
    		percentage = round((( (nse_ltp - ma50) / ma50) * 100), 2)
    		print(percentage, 'Price percentage DIff %')
    		if nse_ltp > ma50:
    			print('Stock crossed 50MA')
    			status = 1
    		elif nse_ltp > ma20:
    			print('MA20 crossed!')
    			status = 2
    		else:
    			print('Invalid 50MA')
    			status = 3
    		try:
	    		icode.status = status
	    		icode.stock_cmp = nse_ltp
	    		icode.cmp_date = timezone.now()  # fixes the warning
	    		icode.save()

	    		# obj, created = MovingAverage.objects.update_or_create(
				#     stock_code=stock,
				#     sma_50=ma50,
				#     sma_20=ma20,
				#     defaults={
				#         'open_price': data['open_price'],
				#         'high_price': data['high_price'],
				#         'low_price': data['low_price'],
				#         'close_price': data['close_price'],
				#         'volume': data['volume'],
				#     }
				# )

	    	except icode.DoesNotExist:
    			obj = icode.objects.create(field=new_value)
    
    trade = breeze.place_order('ITC', "NSE", 1, order_type="MARKET", price=0, product="cash", action="BUY")
    print(trad)
    	
