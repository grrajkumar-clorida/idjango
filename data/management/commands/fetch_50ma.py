from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Disabled. Use fetch_price_data (Path A CMP + status)."

    def handle(self, *args, **kwargs):
        raise CommandError(
            "fetch_50ma is disabled (import-time Breeze / live-order risk). "
            "Use: python manage.py fetch_price_data"
        )
