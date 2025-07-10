import os
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from stocks.utils import send_telegram_message

class Command(BaseCommand):
    help = "Fetch 50ma-setup data from chartink using selenium, store in database"

    def handle(self, *args, **kwargs):
        file_path = os.path.join(settings.MEDIA_ROOT, "result_1.html")  # ✅ Correct file system path
        output_csv = "/home/gr8/Documents/gr8/processed_stock_data.csv"  # Update path


TELEGRAM_BOT_TOKEN = "7404294331:AAGw8COsKG-1Aaz_8puYWW2HaQCfLgTEZjg"
TELEGRAM_CHAT_ID = "4629998605"

def ssend_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    result  = requests.post(url, data=data)
    print(result)

#ssend_telegram_message('Testing Demo')
# send_telegram_message("/start")
#send_telegram_message("🔄 Fetching stock data...")

# # Your stock fetching logic here...
# send_telegram_message("✅ Stock data fetched successfully.")
'''
#https://api.telegram.org/bot7404294331:AAGw8COsKG-1Aaz_8puYWW2HaQCfLgTEZjg/getUpdates
https://api.telegram.org/bot7404294331:AAGw8COsKG-1Aaz_8puYWW2HaQCfLgTEZjg/getMe
'''


from telegram import Bot
from telegram.error import Forbidden

bot_token = "7404294331:AAGw8COsKG-1Aaz_8puYWW2HaQCfLgTEZjg"
chat_id = "4629998605"
message_text = "Hello!"

try:
    bot = Bot(token=bot_token)
    bot.send_message(chat_id=chat_id, text=message_text)
    print("Message sent successfully!")
except Forbidden as e:
    print(f"Failed to send Telegram message: {e}")
    if e.description == "Forbidden: bot was blocked by the user":
        print("The bot was blocked by the user.")
    elif e.description == "Forbidden: bot is not a member of the group chat":
        print("The bot is not a member of the group chat.")
    elif e.description == "Forbidden: bot is not an admin in the supergroup chat":
        print("The bot is not an admin in the supergroup chat with posting rights.")
    # Add more specific checks for other Forbidden reasons
except Exception as e:
    print(f"An unexpected error occurred: {e}")