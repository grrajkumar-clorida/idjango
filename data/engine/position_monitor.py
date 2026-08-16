"""
Position monitor for Path A / human desk.

Uses the human profit-booking price and qty on LiveTrade when set.
Falls back to the 50MA 8–10% rule. Always refreshes P/L from latest CMP.
"""
import logging
from decimal import Decimal
from typing import Dict

from django.conf import settings
from django.utils import timezone

from data.models import Stocks50MA, StockPriceData
from data.strategies.ma50_strategy import MA50Strategy
from infra.utils.breeze_client import BreezeAPI
from stocks.models import LiveTrade, Orders

logger = logging.getLogger(__name__)


class PositionMonitor:
    """Monitors open positions, books human TP, updates P/L."""

    def __init__(self):
        self._breeze = None
        self.strategy = MA50Strategy()
        self.paper_trading = getattr(settings, "PAPER_TRADING_MODE", True)

    @property
    def breeze(self):
        if self._breeze is None:
            self._breeze = BreezeAPI()
        return self._breeze

    def monitor_all_positions(self) -> Dict:
        open_trades = LiveTrade.objects.filter(status="Executed")
        live_data_map = StockPriceData.latest_by_stock_code()

        results = {
            "total": open_trades.count(),
            "updated": 0,
            "exited": 0,
            "details": [],
        }

        for trade in open_trades:
            code = (trade.stock_code or "").strip()
            live_data = live_data_map.get(code) or live_data_map.get(code.upper())
            if not live_data or not live_data.close_price:
                continue

            current_price = float(live_data.close_price)
            entry_price = float(trade.entry_price or trade.price or 0)
            if not entry_price:
                continue

            stock = Stocks50MA.objects.filter(stock_code=trade.stock_code).first()
            exit_check = self._exit_plan(trade, current_price, entry_price, stock, live_data)

            if stock:
                new_status = self.strategy.update_status_based_on_price(
                    stock, live_data, entry_price
                )
                if new_status != stock.status:
                    stock.status = new_status
                    stock.save(update_fields=["status"])
                    results["updated"] += 1
                    results["details"].append({
                        "script": trade.stock_code,
                        "old_status": trade.status,
                        "new_status": new_status,
                        "current_price": current_price,
                        "profit_percent": exit_check.get("profit_percent", 0),
                    })

            if exit_check.get("should_exit"):
                exit_result = self.execute_exit(trade, exit_check, current_price)
                if exit_result.get("success"):
                    results["exited"] += 1
                    results["details"].append({
                        "script": trade.stock_code,
                        "action": "exited",
                        "exit_type": exit_check.get("exit_type"),
                        "exit_percent": exit_check.get("exit_percent"),
                    })

            # Re-read qty after possible partial exit
            trade.refresh_from_db()
            if trade.status == "Executed":
                self.update_profit_loss(trade, current_price, entry_price)

        return results

    def _exit_plan(self, trade, current_price, entry_price, stock, live_data) -> Dict:
        """Stop-loss first, then human TP, then 50MA strategy bands."""
        profit_percent = ((current_price - entry_price) / entry_price) * 100
        open_qty = trade.open_qty()

        sl = trade.stop_loss
        if sl and open_qty > 0:
            sl = float(sl)
            hit_sl = (
                current_price <= sl
                if getattr(trade, "action", "BUY") == "BUY"
                else current_price >= sl
            )
            if hit_sl:
                return {
                    "should_exit": True,
                    "exit_type": "full",
                    "exit_percent": 100,
                    "exit_qty": open_qty,
                    "profit_percent": profit_percent,
                    "reason": f"Stop loss at {sl}",
                }

        tp_price = trade.profit_book_price or trade.take_profit
        if tp_price and current_price >= float(tp_price) and open_qty > 0:
            book_qty = trade.profit_book_qty or open_qty
            book_qty = min(int(book_qty), open_qty)
            exit_type = "full" if book_qty >= open_qty else "partial"
            return {
                "should_exit": True,
                "exit_type": exit_type,
                "exit_percent": (book_qty / open_qty) * 100 if open_qty else 100,
                "exit_qty": book_qty,
                "profit_percent": profit_percent,
                "reason": f"Human profit book at {tp_price}",
            }

        if stock and live_data:
            is_bottom = self.strategy.is_bottom_entry(stock, live_data)
            strategy_exit = self.strategy.check_exit_condition(
                entry_price, current_price, is_bottom
            )
            if strategy_exit.get("should_exit"):
                pct = strategy_exit.get("exit_percent") or 100
                qty = open_qty if pct >= 100 else max(1, int(open_qty * pct / 100))
                strategy_exit["exit_qty"] = qty
                return strategy_exit

        return {
            "should_exit": False,
            "exit_type": None,
            "exit_percent": 0,
            "exit_qty": 0,
            "profit_percent": profit_percent,
            "reason": "Hold",
        }

    def execute_exit(self, trade: LiveTrade, exit_check: Dict, current_price: float) -> Dict:
        exit_type = exit_check.get("exit_type")
        open_qty = trade.open_qty()
        exit_quantity = int(exit_check.get("exit_qty") or 0)
        if exit_quantity <= 0:
            if exit_type == "full":
                exit_quantity = open_qty
            else:
                pct = exit_check.get("exit_percent") or 0
                exit_quantity = int(open_qty * (pct / 100))
        exit_quantity = min(exit_quantity, open_qty)

        if exit_quantity <= 0:
            return {"success": False, "message": "Exit quantity is 0"}

        if not self.paper_trading and not getattr(settings, "TRADING_ENABLED", False):
            return {
                "success": False,
                "message": "TRADING_ENABLED is off — live exit blocked",
            }

        if not self.paper_trading:
            try:
                response = self.breeze.place_order(
                    stock_code=trade.stock_code,
                    exchange=trade.exchange,
                    quantity=exit_quantity,
                    order_type="MARKET",
                    price=0,
                    product="cash",
                    action="SELL",
                )
            except Exception as exc:
                logger.error("Exit failed for %s: %s", trade.stock_code, exc)
                return {"success": False, "message": str(exc)}

            ok = response.get("Status") in ("Success", 200) if isinstance(response, dict) else False
            if not ok:
                err = (response or {}).get("ErrorMessage", "Unknown error")
                return {"success": False, "message": str(err)}

        logger.info(
            "EXIT %s qty=%s/%s type=%s paper=%s",
            trade.stock_code, exit_quantity, open_qty, exit_type, self.paper_trading,
        )

        remaining = open_qty - exit_quantity
        trade.remaining_quantity = remaining
        if remaining <= 0:
            trade.status = "Closed"
            trade.exit_price = Decimal(str(current_price))
            trade.exit_time = timezone.now()
            trade.exit_reason = exit_check.get("reason") or ""
        trade.save()

        order_record = Orders.objects.filter(
            ticker=trade.stock_code, status=1
        ).order_by("-created_at").first()
        if order_record:
            if remaining <= 0:
                order_record.status = 0
                order_record.qty = "0"
            else:
                order_record.qty = str(remaining)
            order_record.save()

        return {
            "success": True,
            "message": f"Exit executed ({exit_type})",
            "exit_quantity": exit_quantity,
        }

    def update_profit_loss(self, trade: LiveTrade, current_price: float, entry_price: float):
        qty = trade.open_qty()
        if trade.action == "BUY":
            pnl = (current_price - entry_price) * qty
        else:
            pnl = (entry_price - current_price) * qty

        trade.profit_loss = Decimal(str(round(pnl, 2)))
        trade.save(update_fields=["profit_loss"])

        order_record = Orders.objects.filter(
            ticker=trade.stock_code, status=1
        ).order_by("-created_at").first()
        if order_record:
            order_record.current_value = current_price * qty
            order_record.overall_pl = float(pnl)
            order_record.day_pl = float(pnl)
            order_record.save(update_fields=["current_value", "overall_pl", "day_pl"])
