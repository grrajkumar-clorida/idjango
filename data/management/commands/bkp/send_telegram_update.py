from django.core.management.base import BaseCommand
from yourapp.utils.telegram_bot import send_telegram_message
#https://api.telegram.org/bot7404294331:AAGw8COsKG-1Aaz_8puYWW2HaQCfLgTEZjg/getMe
#{"ok":true,"result":{"id":7404294331,"is_bot":true,"first_name":"Gr8-Stocks","username":"IDjango_bot","can_join_groups":true,"can_read_all_group_messages":false,"supports_inline_queries":false,"can_connect_to_business":false,"has_main_web_app":false}}
class Command(BaseCommand):
    help = "Send Telegram updates"

    def handle(self, *args, **kwargs):
        send_telegram_message("📊 Daily stock update: Market is open!")
'''
import requests

BOT_TOKEN = "7404294331:AAGw8COsKG-1Aaz_8puYWW2HaQCfLgTEZjg"
CHAT_ID = "7404294331"  # Replace with your actual chat ID

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
payload = {
    "chat_id": CHAT_ID,
    "text": "Hello, this is a test message!"
}

response = requests.post(url, json=payload)
print(response.json())  # Debug output

'''