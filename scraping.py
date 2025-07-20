#https://arabic-telethon.readthedocs.io/en/stable/extra/basic/telegram-client.html
'''

from pyrogram import Client, filters

# Your Telegram API credentials
api_id = 21457317  # Replace with your API ID
api_hash = "b5d41bc198d61c4690b652fa94b46323" # Replace with your API hash

# Create a Pyrogram client session
app = Client("my_session", api_id=api_id, api_hash=api_hash)
print(app.get_me())
# Event handler to capture messages
@app.on_message(filters.group)
def group_message_handler(client, message):
    print(f"[{message.chat.title}] {message.from_user.first_name}: {message.text}")

# Start the app
app.run()

'''
import re
import json
from pyrogram import Client
from telethon import TelegramClient, events, sync

api_id = 21457317
api_hash = "b5d41bc198d61c4690b652fa94b46323" 

def get_halfbat(data):
    '''
    What: Halfbat
    When: May 9, 2025 at 03:26PM
    Extra Data: {"value1":"half bat alert final","value2":"OLECTRA - 1099.1","value3":" @ 3:26 pm"}
    '''
    if re.search(r'What:\s*Halfbat', data, re.IGNORECASE):
        # Extract JSON part after 'Extra Data:'
        match = re.search(r'Extra Data:\s*({.*?})', data, re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                data = json.loads(json_str)
                value2 = data.get("value2")
                print("Extracted value2:", value2)
            except json.JSONDecodeError:
                print("Error: JSON is malformed or invalid.")
        else:
                print("Error: 'Extra Data' JSON not found.")
    else:
        print("Message does not contain 'What: Halfbat'.")


#TelegramClient
client = TelegramClient('Gr8_Rajkumar', api_id, api_hash)
try:
    @client.on(events.NewMessage)
    async def my_event_handler(event):
        if "what" in event.raw_text.lower():
            get_halfbat(event.raw_text)
            await event.reply('Hi! T')

    client.start()
    client.run_until_disconnected()
    #myself = client.get_me()
    #    bhuvi = client.get_entity('Bhuviram24')

    from telethon import utils
    # for message in client.iter_messages('username', limit=10):
    #     print('message !')
    #     print(utils.get_display_name(message.sender), message.message)

    # Dialogs are the conversations you have open
    # for dialog in client.get_dialogs(limit=10):
    #     print(dialog.name, dialog.draft.text)

    # for dd in client.get_participants('Stocks'):
    #     print(dd)

    #print('---------------')
    #print(client.get_messages('Stocks', 10))



    # Default path is the working directory
    #client.download_profile_photo('username')

    
finally:
    client.disconnect()
