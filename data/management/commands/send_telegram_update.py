from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from infra.utils.telegram import send_telegram


class Command(BaseCommand):
    help = "Send a Telegram test/update using TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID"

    def add_arguments(self, parser):
        parser.add_argument(
            "message",
            nargs="?",
            default="Daily stock update: Market is open.",
            help="Message text to send",
        )

    def handle(self, *args, **options):
        token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
        chat_id = getattr(settings, "TELEGRAM_CHAT_ID", "") or ""
        if not token or not chat_id:
            raise CommandError(
                "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in idirect/.env"
            )
        ok = send_telegram(options["message"])
        if not ok:
            raise CommandError("Telegram send failed. Check token, chat id, and logs.")
        self.stdout.write(self.style.SUCCESS("Telegram message sent."))
