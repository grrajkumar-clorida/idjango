"""
Standalone Halfbat Telegram listener.

Credentials come from the environment — never commit api_id / api_hash.

  TELEGRAM_API_ID
  TELEGRAM_API_HASH
  TELEGRAM_SESSION_NAME  (optional, default Gr8_Rajkumar)

Run: python scraping.py
"""
import json
import os
import re
import sys

from telethon import TelegramClient, events


def get_halfbat(data):
    """
    What: Halfbat
    When: May 9, 2025 at 03:26PM
    Extra Data: {"value1":"half bat alert final","value2":"OLECTRA - 1099.1","value3":" @ 3:26 pm"}
    """
    if not re.search(r"What:\s*Halfbat", data, re.IGNORECASE):
        print("Message does not contain 'What: Halfbat'.")
        return None

    match = re.search(r"Extra Data:\s*({.*?})", data, re.DOTALL)
    if not match:
        print("Error: 'Extra Data' JSON not found.")
        return None

    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        print("Error: JSON is malformed or invalid.")
        return None

    value2 = payload.get("value2")
    print("Extracted value2:", value2)
    return value2


def main():
    api_id = os.environ.get("TELEGRAM_API_ID", "").strip()
    api_hash = os.environ.get("TELEGRAM_API_HASH", "").strip()
    session_name = os.environ.get("TELEGRAM_SESSION_NAME", "Gr8_Rajkumar").strip()

    if not api_id or not api_hash:
        print(
            "Set TELEGRAM_API_ID and TELEGRAM_API_HASH in the environment "
            "(or idirect/.env). Do not hardcode them.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = TelegramClient(session_name, int(api_id), api_hash)

    @client.on(events.NewMessage)
    async def my_event_handler(event):
        if "what" in (event.raw_text or "").lower():
            get_halfbat(event.raw_text)

    with client:
        client.run_until_disconnected()


if __name__ == "__main__":
    main()
