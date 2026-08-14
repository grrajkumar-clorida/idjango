from django.core.management.base import BaseCommand, CommandError

from data.models import Stocks50MA
from infra.utils.breeze_client import BreezeAPI


class Command(BaseCommand):
    help = "Update ticker to ICICI Direct isec code, e.g. IOC => INDOIL"

    def handle(self, *args, **kwargs):
        self.stdout.write("Update ticker as ICICI Direct format, e.g. IOC => INDOIL")

        breeze = BreezeAPI()
        if not breeze.get_session_status():
            raise CommandError("Breeze session is not active. Login via ?apisession= first.")

        self.stdout.write(self.style.SUCCESS("Breeze active."))

        updated = 0
        skipped = 0
        for row in Stocks50MA.objects.exclude(stock_code__isnull=True).exclude(stock_code=""):
            stock = row.stock_code
            idsec_code = breeze.get_isec_stock_code(stock, "NSE")
            if not idsec_code:
                skipped += 1
                self.stdout.write(self.style.WARNING(f"No isec code for {stock}"))
                continue
            Stocks50MA.objects.filter(stock_code=stock).update(ticker=idsec_code)
            updated += 1
            self.stdout.write(f"{stock} -> {idsec_code}")

        self.stdout.write(self.style.SUCCESS(
            f"Tickers updated: {updated}, skipped: {skipped}"
        ))
