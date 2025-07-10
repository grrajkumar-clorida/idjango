from django.core.management.base import BaseCommand
from stocks.breeze_client import BreezeAPI

class Command(BaseCommand):
    help = "Check live prices and update trailing stop-loss"

    def handle(self, *args, **kwargs):
        breeze = BreezeAPI()
        breeze.update_trailing_stop_loss()
