from django.core.management.base import BaseCommand

from infra.utils.telegram import send_telegram


class Command(BaseCommand):
    help = "Send a Telegram status ping using settings.TELEGRAM_* credentials"

    def handle(self, *args, **kwargs):
        send_telegram("Fetching stock data...")
        self.stdout.write(self.style.SUCCESS("Status ping sent."))
