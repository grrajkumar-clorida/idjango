"""
Order executor for Path A.

Status 8 is a green signal only. Humans approve qty + price range on
TradeReview; this module queues those reviews and places fills for approved
rows (Celery beat or the Review page "Approve & Place" button).
"""
import logging
from decimal import Decimal
from typing import Dict, Optional

from django.conf import settings
from django.utils import timezone

from data.models import Stocks50MA, StockPriceData
from data.strategies.ma50_strategy import MA50Strategy
from infra.utils.breeze_client import BreezeAPI
from stocks.models import LiveTrade, Orders, TradeReview

logger = logging.getLogger(__name__)


def _dec(val, default="0"):
    if val is None or val == "":
        return Decimal(default)
    return Decimal(str(val))


def _in_price_range(cmp_price, price_min, price_max) -> bool:
    if price_min is not None and cmp_price < float(price_min):
        return False
    if price_max is not None and cmp_price > float(price_max):
        return False
    return True


class OrderExecutor:
    """Queues status-8 reviews and executes human-approved orders."""

    def __init__(self):
        self._breeze = None
        self.strategy = MA50Strategy()
        self.paper_trading = getattr(settings, "PAPER_TRADING_MODE", True)
        self.max_position_size = getattr(settings, "MAX_POSITION_SIZE", 100000)

    @property
    def breeze(self):
        if self._breeze is None:
            self._breeze = BreezeAPI()
        return self._breeze

    def execute_orders_for_status_8(self) -> Dict:
        """
        Path A beat entry: queue new status-8 names for human review,
        then place any approved reviews whose CMP is still in range.
        """
        queued = self.queue_status_8_for_review()
        placed = self.execute_approved_reviews()
        return {
            "queued": queued.get("created", 0),
            "updated_reviews": queued.get("updated", 0),
            "executed": placed.get("executed", 0),
            "skipped": placed.get("skipped", 0),
            "failed": placed.get("failed", 0),
            "details": queued.get("details", []) + placed.get("details", []),
        }

    def queue_status_8_for_review(self) -> Dict:
        """Create/update pending TradeReview rows for status-8 stocks."""
        stocks = Stocks50MA.objects.filter(status=8)
        live_map = StockPriceData.latest_by_stock_code()
        created = 0
        updated = 0
        details = []

        for stock in stocks:
            if LiveTrade.objects.filter(stock_code=stock.stock_code, status="Executed").exists():
                continue

            open_review = TradeReview.objects.filter(
                stock_code=stock.stock_code,
                status__in=["pending", "approved"],
            ).first()

            live = live_map.get(stock.stock_code)
            cmp = None
            if live and live.close_price:
                cmp = Decimal(str(live.close_price))
            elif stock.stock_cmp:
                cmp = Decimal(str(stock.stock_cmp))

            if open_review:
                if cmp and open_review.status == "pending":
                    open_review.suggested_price = cmp
                    if live:
                        open_review.live_50ma = live.live50ma
                        open_review.cp50ma_percent = live.cp50ma
                    open_review.save(update_fields=[
                        "suggested_price", "live_50ma", "cp50ma_percent", "updated_at",
                    ])
                    updated += 1
                continue

            tp = None
            if cmp:
                tp = (cmp * Decimal("1.10")).quantize(Decimal("0.01"))
            sl = None
            if cmp:
                sl = (cmp * Decimal("0.95")).quantize(Decimal("0.01"))

            TradeReview.objects.create(
                stock_code=stock.stock_code,
                ticker=stock.ticker or "",
                name=stock.name or "",
                source="signal",
                status="pending",
                suggested_price=cmp,
                live_50ma=live.live50ma if live else stock.moving_average_50,
                cp50ma_percent=live.cp50ma if live else stock.percent_50ma,
                qty=1,
                order_type="MARKET",
                price_min=(cmp * Decimal("0.99")).quantize(Decimal("0.01")) if cmp else None,
                price_max=(cmp * Decimal("1.01")).quantize(Decimal("0.01")) if cmp else None,
                stop_loss=sl,
                take_profit=tp,
                take_profit_qty=1,
                notes="50MA status 8 — awaiting human qty/price",
            )
            created += 1
            details.append({
                "script": stock.stock_code,
                "status": "queued",
                "reason": "Pending human review",
            })

        logger.info("Queued %s new status-8 reviews (%s updated)", created, updated)
        return {"created": created, "updated": updated, "details": details}

    def execute_approved_reviews(self) -> Dict:
        reviews = TradeReview.objects.filter(status="approved")
        results = {
            "total": reviews.count(),
            "executed": 0,
            "skipped": 0,
            "failed": 0,
            "details": [],
        }
        for review in reviews:
            result = self.place_approved_review(review)
            key = "executed" if result.get("success") else (
                "skipped" if result.get("skipped") else "failed"
            )
            results[key] += 1
            results["details"].append({
                "script": review.stock_code,
                "status": key,
                "reason": result.get("message", ""),
                "order_id": result.get("order_id"),
            })
        return results

    def place_approved_review(self, review: TradeReview) -> Dict:
        """Place one human-approved review. Safe to call from the web desk."""
        if review.status not in ("approved", "failed"):
            return {"success": False, "skipped": True, "message": f"Status is {review.status}"}

        if LiveTrade.objects.filter(stock_code=review.stock_code, status="Executed").exists():
            review.status = "placed"
            review.last_error = "Already have an open position"
            review.save(update_fields=["status", "last_error", "updated_at"])
            return {"success": False, "skipped": True, "message": "Already have open position"}

        live_map = StockPriceData.latest_by_stock_code()
        live = live_map.get(review.stock_code)
        cmp = float(live.close_price) if live and live.close_price else None
        if cmp is None and review.suggested_price:
            cmp = float(review.suggested_price)
        if cmp is None:
            review.last_error = "No live CMP"
            review.save(update_fields=["last_error", "updated_at"])
            return {"success": False, "skipped": True, "message": "No live CMP"}

        if not _in_price_range(cmp, review.price_min, review.price_max):
            msg = (
                f"CMP {cmp} outside human range "
                f"{review.price_min}–{review.price_max}"
            )
            review.last_error = msg
            review.save(update_fields=["last_error", "updated_at"])
            return {"success": False, "skipped": True, "message": msg}

        qty = int(review.qty or 1)
        if qty < 1:
            return {"success": False, "message": "Qty must be >= 1"}

        order_type = review.order_type or "MARKET"
        if order_type == "LIMIT":
            fill_price = float(review.limit_price or review.suggested_price or cmp)
        else:
            fill_price = cmp

        order_value = fill_price * qty
        if order_value > self.max_position_size:
            qty = max(1, int(self.max_position_size / fill_price))
            order_value = fill_price * qty

        stock = Stocks50MA.objects.filter(stock_code=review.stock_code).first()
        targets = self.strategy.get_target_prices(fill_price)
        stop_loss = float(review.stop_loss) if review.stop_loss else fill_price * 0.95
        take_profit = float(review.take_profit) if review.take_profit else targets["target_2"]
        tp_qty = review.take_profit_qty if review.take_profit_qty else qty

        breeze_price = 0
        if order_type == "LIMIT":
            breeze_price = fill_price

        order_id = None
        if self.paper_trading:
            order_id = f"PAPER_{review.stock_code}_{review.id}_{timezone.now().strftime('%H%M%S')}"
            logger.info(
                "PAPER: BUY %s qty=%s price=%s range=%s-%s",
                review.stock_code, qty, fill_price, review.price_min, review.price_max,
            )
        else:
            try:
                response = self.breeze.place_order(
                    stock_code=review.stock_code,
                    exchange="NSE",
                    quantity=qty,
                    order_type=order_type,
                    price=breeze_price,
                    product="cash",
                    action="BUY",
                )
            except Exception as exc:
                review.status = "failed"
                review.last_error = str(exc)[:255]
                review.save(update_fields=["status", "last_error", "updated_at"])
                return {"success": False, "message": str(exc)}

            ok = response.get("Status") in ("Success", 200) if isinstance(response, dict) else False
            if not ok:
                err = (response or {}).get("ErrorMessage", "Unknown Breeze error")
                review.status = "failed"
                review.last_error = str(err)[:255]
                review.save(update_fields=["status", "last_error", "updated_at"])
                return {"success": False, "message": str(err)}
            order_id = (
                response.get("order_id")
                or (response.get("Success") or {}).get("order_id")
                or ""
            )

        now = timezone.now()
        trade = LiveTrade.objects.create(
            stock_code=review.stock_code,
            exchange="NSE",
            quantity=qty,
            remaining_quantity=qty,
            order_type=order_type,
            price=Decimal(str(fill_price)),
            entry_price=Decimal(str(fill_price)),
            entry_time=now,
            action="BUY",
            status="Executed",
            order_id=order_id,
            stop_loss=Decimal(str(stop_loss)),
            take_profit=Decimal(str(take_profit)),
            profit_book_price=Decimal(str(take_profit)),
            profit_book_qty=tp_qty,
            price_min=review.price_min,
            price_max=review.price_max,
            source=review.source or "signal",
            review=review,
            entry_reason=review.notes or "Human-approved 50MA entry",
        )
        Orders.objects.create(
            ticker=review.stock_code[:15],
            script=(review.ticker or review.stock_code)[:15],
            order_id=(order_id or "")[:30],
            position="BUY",
            stop_loss=stop_loss,
            qty=str(qty),
            price=fill_price,
            invested_value=order_value,
            current_value=order_value,
            day_pl=0.0,
            overall_pl=0.0,
            targets={
                "target_1": targets["target_1"],
                "target_2": targets["target_2"],
                "target_3": targets["target_3"],
                "entry_price": fill_price,
                "take_profit": take_profit,
                "take_profit_qty": tp_qty,
                "review_id": review.id,
            },
            status=1,
            message="Human-approved entry",
            user_remark=(review.reviewed_by or "")[:15],
        )

        review.status = "placed"
        review.placed_at = now
        review.last_error = ""
        review.save(update_fields=["status", "placed_at", "last_error", "updated_at"])

        if stock and stock.status < 8:
            stock.status = 8
            stock.save(update_fields=["status"])

        return {
            "success": True,
            "message": "Paper trade executed" if self.paper_trading else "Order executed",
            "order_id": order_id,
            "quantity": qty,
            "price": fill_price,
            "trade_id": trade.id,
        }

    def record_tracked_fill(
        self,
        *,
        stock_code: str,
        qty: int,
        entry_price: Decimal,
        entry_time,
        take_profit=None,
        take_profit_qty=None,
        stop_loss=None,
        notes="",
        ticker="",
        name="",
        reviewed_by="",
    ) -> Dict:
        """
        Record an already-filled trade for P/L tracking. Does not call Breeze.
        Example: TATATECH qty 1 @ 745.35 on 29-Jul-2026 10:47.
        """
        stock_code = (stock_code or "").strip().upper()
        qty = int(qty or 0)
        if not stock_code or qty < 1 or entry_price is None:
            return {"success": False, "message": "Stock, qty, and buy price are required"}

        fill_price = float(entry_price)
        if fill_price <= 0:
            return {"success": False, "message": "Buy price must be > 0"}

        if entry_time is None:
            entry_time = timezone.now()

        tp = float(take_profit) if take_profit is not None else None
        sl = float(stop_loss) if stop_loss is not None else round(fill_price * 0.95, 2)
        tp_qty = int(take_profit_qty) if take_profit_qty else qty
        order_value = fill_price * qty
        order_id = f"TRACK_{stock_code}_{entry_time.strftime('%Y%m%d%H%M')}"[:50]

        review = TradeReview.objects.create(
            stock_code=stock_code,
            ticker=(ticker or "")[:50],
            name=(name or "")[:200],
            source="tracked",
            status="placed",
            suggested_price=entry_price,
            qty=qty,
            order_type="MARKET",
            stop_loss=Decimal(str(sl)) if sl else None,
            take_profit=Decimal(str(tp)) if tp else None,
            take_profit_qty=tp_qty,
            notes=(notes or "Imported for position tracking")[:255],
            reviewed_by=(reviewed_by or "")[:80],
            reviewed_at=timezone.now(),
            placed_at=entry_time,
        )

        trade = LiveTrade.objects.create(
            stock_code=stock_code[:10],
            exchange="NSE",
            quantity=qty,
            remaining_quantity=qty,
            order_type="MARKET",
            price=Decimal(str(fill_price)),
            entry_price=Decimal(str(fill_price)),
            entry_time=entry_time,
            timestamp=entry_time,
            action="BUY",
            status="Executed",
            order_id=order_id,
            stop_loss=Decimal(str(sl)) if sl else None,
            take_profit=Decimal(str(tp)) if tp else None,
            profit_book_price=Decimal(str(tp)) if tp else None,
            profit_book_qty=tp_qty,
            source="tracked",
            review=review,
            entry_reason=notes or f"Tracked fill {stock_code} qty {qty} @ {fill_price}",
        )
        Orders.objects.create(
            ticker=stock_code[:15],
            script=(ticker or stock_code)[:15],
            order_id=order_id[:30],
            position="BUY",
            stop_loss=sl or 0,
            qty=str(qty),
            price=fill_price,
            invested_value=order_value,
            current_value=order_value,
            day_pl=0.0,
            overall_pl=0.0,
            targets={
                "entry_price": fill_price,
                "take_profit": tp,
                "take_profit_qty": tp_qty,
                "tracked": True,
            },
            status=1,
            message="Tracked external fill",
            user_remark=(reviewed_by or "track")[:15],
        )
        logger.info(
            "Tracked fill %s qty=%s price=%s at %s",
            stock_code, qty, fill_price, entry_time,
        )
        return {
            "success": True,
            "message": "Position added for tracking",
            "order_id": order_id,
            "quantity": qty,
            "price": fill_price,
            "trade_id": trade.id,
        }
