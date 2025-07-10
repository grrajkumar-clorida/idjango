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
    trade = breeze.place_order('SAMMAANCAP', "NSE", 1, order_type="MARKET", price=0, product="cash", action="BUY")
    print('tradestatus: ',trade)
    	
