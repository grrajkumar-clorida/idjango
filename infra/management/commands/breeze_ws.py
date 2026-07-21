from django.core.management.base import BaseCommand
from infra.utils.breeze_client import BreezeAPI
from django.conf import settings
import urllib

# API_KEY = "your_api_key"
# API_SECRET = "your_secret_key"
# SESSION_TOKEN = "your_api_session"

class Command(BaseCommand):
    help = "Run Breeze WebSocket for live stock data"
    print('Initialize Breeze API!')
    def handle(self, *args, **options):
        # Initialize SDK
        breeze = BreezeAPI()
        breezeStatus = breeze.get_session_status()

        if breezeStatus is True:
            print('Breeze active!')
        else:
            print('Breeze Access Error!')
            exit()
        #self.api.generate_session(api_secret=settings.BREEZE_SECRET_KEY, session_token=settings.BREEZE_SESSION)


        # Connect WebSocket
        breeze.ws_connect()

        # Define tick callback
        def on_ticks(ticks):
            print("Ticks:", ticks)
            # TODO: Save to DB for dashboard updates

        breeze.on_ticks = on_ticks

        # Subscribe to stock (replace token & interval)
        breeze.subscribe_feeds(
            stock_token="4.1!2885",  # Example: TCS
            interval="1minute"
        )

        # Keep alive
        try:
            while True:
                pass
        except KeyboardInterrupt:
            breeze.ws_disconnect()
