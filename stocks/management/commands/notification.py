import requests
import telebot
from django.core.management.base import BaseCommand
from django.conf import settings
from stocks.utils.telegram_bot import send_telegram_message

class Command(BaseCommand):
    help = "Fetch 50ma-setup data from chartink using selenium, store in database"

    def handle(self, *args, **kwargs):
        #file_path = os.path.join(settings.MEDIA_ROOT, "result_1.html")  # ✅ Correct file system path
        output_csv = "/home/gr8/Documents/gr8/processed_stock_data.csv"  # Update path


BOT_TOKEN = "7404294331:AAGw8COsKG-1Aaz_8puYWW2HaQCfLgTEZjg"
message = "Hi Idrect"

TELEGRAM_BOT_TOKEN = "7404294331:AAGw8COsKG-1Aaz_8puYWW2HaQCfLgTEZjg"
TELEGRAM_CHAT_ID = "-4629998605"

def ssend_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    result  = requests.post(url, data=data)
    print("Result: ",result)

ssend_telegram_message('Testing Demo')