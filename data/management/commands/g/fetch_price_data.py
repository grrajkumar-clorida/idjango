from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Disabled legacy backup. Use fetch_price_data."

    def handle(self, *args, **kwargs):
        raise CommandError(
            "Legacy g/fetch_price_data is disabled (wrong status logic + import-time sheet writes). "
            "Use: python manage.py fetch_price_data"
        )
