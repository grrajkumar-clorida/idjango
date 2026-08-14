from django.core.management.base import BaseCommand

from infra.utils.telegram import send_telegram


class Command(BaseCommand):
    help = "Send a Telegram notification using settings.TELEGRAM_* credentials"

    def add_arguments(self, parser):
        parser.add_argument(
            "message",
            nargs="?",
            default="Idirect notification",
            help="Message text to send",
        )

    def handle(self, *args, **options):
        if send_telegram(options["message"]):
            self.stdout.write(self.style.SUCCESS("Telegram message sent."))
        else:
            self.stdout.write(self.style.ERROR("Telegram send failed."))
