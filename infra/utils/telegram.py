import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_telegram(message, parse_mode='Markdown'):
    """
    Send a message to the Telegram bot.
    
    Args:
        message: Message text (supports Markdown formatting)
        parse_mode: Parse mode ('Markdown' or 'HTML' or None)
    """
    try:
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": message
        }
        
        if parse_mode:
            payload["parse_mode"] = parse_mode
        
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False
