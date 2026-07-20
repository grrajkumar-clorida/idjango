from django.core.management.base import BaseCommand
from infra.utils.breeze_client import BreezeAPI
from django.conf import settings

class Command(BaseCommand):
    help = "Run Breeze WebSocket for live stock data"

    breeze = BreezeAPI()
    def start_stream():
        breeze = BreezeAPI()

    def handle_ticks(ticks):
        # Here you can save to DB
        # e.g., LiveTrade.objects.create(...)
        print("Got tick:", ticks)

    sio = breeze.start_websocket(
        script_codes=["4.1!1594"], 
        channel_name="1SEC", 
        on_ticks=handle_ticks
    )

    # Later when you want to stop
    # breeze.unsubscribe(["4.1!1594"])
    # breeze.stop_websocket()
