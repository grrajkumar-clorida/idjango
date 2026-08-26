import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from data.models import StockPriceData, Stocks50MA
from data.strategies.ma50_strategy import MA50Strategy
from infra.utils.gfinance import get_gfinance_data, update_gfinance_data
from infra.utils.infra import date_format, safe_float
from stocks.models import LiveTrade


class Command(BaseCommand):
    help = "Fetch latest CMPs from Google Finance and update 50MA statuses"

    def handle(self, *args, **kwargs):
        stock_list = list(
            Stocks50MA.objects.exclude(stock_code__isnull=True)
            .exclude(stock_code="")
            .values_list("stock_code", flat=True)
            .distinct()
        )
        open_codes = list(
            LiveTrade.objects.filter(status="Executed")
            .exclude(stock_code__isnull=True)
            .exclude(stock_code="")
            .values_list("stock_code", flat=True)
            .distinct()
        )
        seen = set()
        merged = []
        for code in stock_list + open_codes:
            key = (code or "").strip().upper()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(key)
        stock_list = merged
        self.stdout.write(
            f"Total Stocks of 50MA + open positions: {len(stock_list)} "
            f"(open {len(open_codes)})"
        )
        if not stock_list:
            self.stdout.write(self.style.WARNING("No Stocks50MA rows — nothing to fetch."))
            return

        list_data = update_gfinance_data("getCMP", stock_list)
        self.stdout.write(f"Get CMP for {len(stock_list)} in google finance: {list_data}")

        copy_gf_cmp = str(getattr(settings, "GSHEET_APP_SCRIPT_CMP", "") or "").strip()
        if copy_gf_cmp:
            self.stdout.write("Triggering CMP Apps Script...")
            try:
                response = requests.get(copy_gf_cmp, timeout=60)
                self.stdout.write(f"sheet response: {response.status_code}")
                wait_time = 15
                self.stdout.write(f"Waiting {wait_time}s for Apps Script to fill marketPrice...")
                time.sleep(wait_time)
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"Apps Script CMP trigger failed: {exc}"))
        else:
            self.stdout.write(self.style.WARNING(
                "GSHEET_APP_SCRIPT_CMP not configured — reading marketPrice as-is."
            ))

        spreadsheet_id = settings.GSHEET_ID
        api_key = settings.GSHEET_KEY
        gsheet_data = get_gfinance_data(spreadsheet_id, "marketPrice", api_key)
        if not gsheet_data:
            self.stdout.write(self.style.ERROR("marketPrice sheet returned no data."))
            return

        rows = gsheet_data.get("values", [])
        if not rows:
            self.stdout.write(self.style.ERROR("marketPrice sheet has no rows."))
            return

        headers = rows[0]
        today = timezone.now().date()
        saved = 0
        for row in rows[1:]:
            row_dict = dict(zip(headers, row))
            script = (row_dict.get("Script") or "").strip()
            if not script:
                continue

            trade_date = date_format(row_dict.get("Trad Date")) or today
            StockPriceData.objects.update_or_create(
                stock_code=script,
                date=trade_date,
                defaults={
                    "close_price": safe_float(row_dict.get("CMP")),
                    "live21ma": safe_float(row_dict.get("21MA")),
                    "live50ma": safe_float(row_dict.get("50MA")),
                    "live9ma": safe_float(row_dict.get("9MA")),
                    "cp50ma": safe_float(row_dict.get("CP50MA%")),
                    "live921": row_dict.get("Cross921MA"),
                },
            )
            saved += 1

        self.stdout.write(self.style.SUCCESS(f"Upserted {saved} StockPriceData rows."))

        strategy = MA50Strategy()
        sma_map = StockPriceData.latest_by_stock_code()
        open_trades = {}
        for trade in LiveTrade.objects.filter(status="Executed"):
            key = (trade.stock_code or "").strip().upper()
            if key and key not in open_trades:
                open_trades[key] = trade
        stocks_to_update = []

        for stock in Stocks50MA.objects.all():
            live_data = sma_map.get(stock.stock_code) or sma_map.get(
                (stock.stock_code or "").upper()
            )
            if not live_data or live_data.live50ma is None:
                continue

            code = (stock.stock_code or "").strip().upper()
            trade = open_trades.get(code)
            if trade:
                entry = float(trade.entry_price or trade.price or 0) or None
                new_status = strategy.update_status_based_on_price(
                    stock, live_data, entry
                )
            else:
                new_status = strategy.assign_pre_trade_status(stock, live_data)
            stock.status = new_status
            stocks_to_update.append(stock)
            self.stdout.write(
                f"Status: {stock.stock_code} - c:{live_data.live50ma} - "
                f"sma:{stock.stock_cmp} - p:{live_data.close_price} - "
                f"%:{live_data.cp50ma} - status:{stock.status}"
            )

        if stocks_to_update:
            Stocks50MA.objects.bulk_update(stocks_to_update, ["status"])

        self.stdout.write(self.style.SUCCESS(
            f"Updated {len(stocks_to_update)} stock status values."
        ))
