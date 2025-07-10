from yourapp.utils.telegram_bot import send_telegram_message

def fetch_stock_data():
    try:
        send_telegram_message("🔄 Fetching stock data...")

        # Your stock fetching logic here...

        send_telegram_message("✅ Stock data fetched successfully.")
    except Exception as e:
        send_telegram_message(f"❌ Error fetching stock data: {e}")

'''
import requests

BOT_TOKEN = "7404294331:AAGw8COsKG-1Aaz_8puYWW2HaQCfLgTEZjg"
CHAT_ID = "7404294331"
MESSAGE = "Hello, this is a test!"

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
payload = {
    "chat_id": CHAT_ID,
    "text": MESSAGE
}

response = requests.post(url, json=payload)
print(response.json())  # Print response for debugging

'''