"""Desk positions: IDirect fill recording and realized P/L."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from data.engine.order_executor import OrderExecutor
from stocks.models import LiveTrade
from stocks.utils.idirect_import import apply_idirect_fills, parse_idirect_orderbook


IDIRECT_CSV = """Date,Stock,Action,Qty,Price,Trade Value,Order Ref.,Settlement,Segment,DP Id - Client DP Id,Exchange,STT,Transaction and SEBI Turnover charges,Stamp Duty,Brokerage + Service Tax,Brokerage Incl. Taxes
"28-Jul-26","SKYGOLD","Buy","2","670.7","1341.4","20260728T700028773","2026140","Rolling T1","IN303028-64387359","NSE","1","0.04","0","4.6","5.64"
"06-Aug-26","TATAGOLD","Buy","50","14.34","717","20260806T700042659","2026147","Rolling T1","IN303028-64387359","NSE","0","0.02","0","2.46","2.48"
"""


class IDirectCsvImportTestCase(TestCase):
    def test_parse_and_apply_buys(self):
        fills = parse_idirect_orderbook("\ufeff" + IDIRECT_CSV)
        self.assertEqual(len(fills), 2)
        self.assertEqual(fills[0]["stock_code"], "SKYGOLD")
        self.assertIsNotNone(fills[0]["when"])
        self.assertEqual(fills[0]["qty"], 2)
        self.assertEqual(fills[0]["price"], Decimal("670.7"))

        result = apply_idirect_fills(fills)
        self.assertEqual(result["created"], 2)
        sky = LiveTrade.objects.get(stock_code="SKYGOLD", status="Executed")
        self.assertEqual(sky.open_qty(), 2)
        self.assertEqual(float(sky.entry_price), 670.7)

    def test_updates_entry_and_recomputes_partial_pnl(self):
        LiveTrade.objects.create(
            stock_code="SKYGOLD",
            quantity=2,
            remaining_quantity=1,
            order_type="LIMIT",
            price=Decimal("670.95"),
            entry_price=Decimal("670.95"),
            exit_price=Decimal("796.15"),
            action="BUY",
            status="Executed",
            profit_loss=Decimal("125.20"),
            source="tracked",
        )
        result = apply_idirect_fills(parse_idirect_orderbook(IDIRECT_CSV))
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["created"], 1)
        sky = LiveTrade.objects.get(stock_code="SKYGOLD", status="Executed")
        self.assertEqual(float(sky.entry_price), 670.7)
        self.assertEqual(sky.open_qty(), 1)
        self.assertEqual(float(sky.profit_loss), 125.45)

    def test_upload_view_imports_csv(self):
        User = get_user_model()
        user = User.objects.create_user(username="desk", password="x")
        self.client.force_login(user)
        upload = SimpleUploadedFile(
            "orderBook.csv", IDIRECT_CSV.encode("utf-8"), content_type="text/csv"
        )
        resp = self.client.post(
            reverse("desk_position_import"),
            {"orderbook": upload},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(LiveTrade.objects.filter(stock_code="TATAGOLD").exists())


class RecordBrokerExitTestCase(TestCase):
    def setUp(self):
        self.executor = OrderExecutor()

    def test_close_open_buy_sets_pnl(self):
        trade = LiveTrade.objects.create(
            stock_code="SKYGOLD",
            exchange="NSE",
            quantity=1,
            remaining_quantity=1,
            order_type="LIMIT",
            price=Decimal("790.00"),
            entry_price=Decimal("790.00"),
            action="BUY",
            status="Executed",
            source="tracked",
        )
        result = self.executor.record_broker_exit(
            stock_code="SKYGOLD",
            qty=1,
            exit_price=Decimal("796.15"),
            exit_time=timezone.now(),
            trade=trade,
            notes="IDirect DELIVERY limit sell",
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["closed"])
        self.assertEqual(result["pnl"], 6.15)
        trade.refresh_from_db()
        self.assertEqual(trade.status, "Closed")
        self.assertEqual(trade.remaining_quantity, 0)
        self.assertEqual(float(trade.exit_price), 796.15)
        self.assertEqual(float(trade.profit_loss), 6.15)

    def test_round_trip_without_open_position(self):
        result = self.executor.record_broker_exit(
            stock_code="SKYGOLD",
            qty=1,
            exit_price=Decimal("796.15"),
            entry_price=Decimal("790.00"),
            notes="IDirect sell",
        )
        self.assertTrue(result["success"])
        closed = LiveTrade.objects.get(pk=result["trade_id"])
        self.assertEqual(closed.status, "Closed")
        self.assertEqual(closed.stock_code, "SKYGOLD")
        self.assertEqual(float(closed.profit_loss), 6.15)

    def test_sell_without_open_or_entry_fails(self):
        result = self.executor.record_broker_exit(
            stock_code="SKYGOLD",
            qty=1,
            exit_price=Decimal("796.15"),
        )
        self.assertFalse(result["success"])
        self.assertIn("original buy price", result["message"])


class PositionFillViewTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="desk", password="x")
        self.client.force_login(self.user)

    def test_record_idirect_sell_round_trip(self):
        resp = self.client.post(
            reverse("desk_position_record_fill"),
            {
                "stock_code": "SKYGOLD",
                "action": "SELL",
                "qty": "1",
                "fill_price": "796.15",
                "fill_at": "24-Aug-2026 10:06",
                "entry_price": "790.00",
                "notes": "IDirect DELIVERY limit sell",
            },
        )
        self.assertEqual(resp.status_code, 302)
        closed = LiveTrade.objects.get(stock_code="SKYGOLD")
        self.assertEqual(closed.status, "Closed")
        self.assertEqual(float(closed.exit_price), 796.15)
        self.assertEqual(float(closed.profit_loss), 6.15)

    def test_positions_page_shows_closed_row(self):
        LiveTrade.objects.create(
            stock_code="SKYGOLD",
            quantity=1,
            remaining_quantity=0,
            order_type="LIMIT",
            price=Decimal("790.00"),
            entry_price=Decimal("790.00"),
            exit_price=Decimal("796.15"),
            action="BUY",
            status="Closed",
            profit_loss=Decimal("6.15"),
            exit_time=timezone.now(),
            source="tracked",
        )
        resp = self.client.get(reverse("desk_positions"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "SKYGOLD")
        self.assertContains(resp, "796.15")
        self.assertContains(resp, "sort=pl")
        self.assertContains(resp, "sort=entry")
        self.assertContains(resp, "sort=live")
        self.assertContains(resp, "c-live")
        self.assertNotContains(resp, "Not on the ChartInk 50MA sheet")


class PositionSortTestCase(TestCase):
    def test_sort_stock_entry_live_pl(self):
        from stocks.trading_views import _sort_positions

        class Row:
            def __init__(self, code, entry, live, pl):
                self.stock_code = code
                self.entry_price = entry
                self.price = entry
                self.live_price = live
                self.mark_pl = pl

        rows = [
            Row("SKYGOLD", 670.7, 854.25, 183.55),
            Row("ITC", 286.75, 273.15, -68.0),
            Row("TATAGOLD", 14.34, 15.63, 64.5),
        ]
        _sort_positions(rows, "stock", "asc")
        self.assertEqual([r.stock_code for r in rows], ["ITC", "SKYGOLD", "TATAGOLD"])
        _sort_positions(rows, "entry", "desc")
        self.assertEqual([r.stock_code for r in rows], ["SKYGOLD", "ITC", "TATAGOLD"])
        _sort_positions(rows, "price", "desc")
        self.assertEqual([r.stock_code for r in rows], ["SKYGOLD", "ITC", "TATAGOLD"])
        _sort_positions(rows, "pl", "desc")
        self.assertEqual([r.stock_code for r in rows], ["SKYGOLD", "TATAGOLD", "ITC"])

