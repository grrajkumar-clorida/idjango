from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Backup stub. Telegram credentials belong in idirect/.env, not in this file."

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("bkp command is a stub. Use send_telegram_update."))
