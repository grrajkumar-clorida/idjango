import datetime
import time
import os
from django.core.management.base import BaseCommand
from infra.utils.breeze_client import BreezeAPI
from data.models import Source, Stocks50MA
#from stock.models import MovingAverage
#from data.tasks import calculate_50ma
from datetime import datetime, timedelta
from django.utils import timezone
from decouple import config
from infra.utils.infra import date_format

class Command(BaseCommand):
    help = "Fetch latest stock prices from NSE and store in DB"
    
    def handle(self, *args, **kwargs):
        api_key = config('SMA_API_KEY')
        self.stdout.write('Fetch stock 50MA prices status...')

        self.stdout.write(self.style.SUCCESS(f'Using API Key: {api_key}'))
    #print(os.environ['ALLOWED_HOSTS'])
    breeze = BreezeAPI()
    breezeStatus = breeze.get_session_status()
    t_date = date_format('2025-07-10')
    print('TEST Using infra utils:',t_date)
    if breezeStatus is True:
        print('Breeze active!')
    else:
    	print('Breeze Access Error!')
    	exit()

    #stocks = StockPriceData.objects.all()
    # print('tradestatus: ',trade)
    	
