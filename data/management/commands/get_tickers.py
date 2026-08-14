import datetime
import time
from django.core.management.base import BaseCommand
from infra.utils.breeze_client import BreezeAPI
from data.models import Stocks50MA
from datetime import datetime, timedelta
from django.utils import timezone

class Command(BaseCommand):
    help = "update Tricker as Idirect format value eg: IOC => INDOIL"
    
    def handle(self, *args, **kwargs):
        self.stdout.write('Update Tricker as Idirect format value eg: IOC => INDOIL')

    breeze = BreezeAPI()
    breezeStatus = breeze.get_session_status()

    if breezeStatus is True:
        print('Breeze active!')
    else:
    	print('Breeze Access Error!')
    	exit()

    #stocks = StockPriceData.objects.all()
    process_data = Stocks50MA.objects.all()#.filter(pre_data__isnull=True)
    for icode in process_data:
    	print("icode: ",icode)
    	stock = icode.stock_code
    	idsecCode = breeze.get_isec_stock_code(stock, "NSE")
    	try:
    		Stocks50MA.objects.filter(stock_code=stock).update(ticker=idsecCode)
    	except icode.DoesNotExist:
    		print('Error')
    	#exit()
