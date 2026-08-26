"""Parse IDirect equity order-book / contract-note CSVs and upsert LiveTrades."""
import csv
import io
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from data.engine.order_executor import OrderExecutor
from stocks.models import LiveTrade


_MONTHS = {
    name: i
    for i, name in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        1,
    )
}
_DATE_RE = re.compile(
    r"^(\d{1,2})-([A-Za-z]{3})-(\d{2,4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?$"
)


def parse_idirect_datetime(val):
    text = str(val or "").strip().strip('"')
    if not text:
        return None
    match = _DATE_RE.match(text)
    if match:
        day, mon, year, hour, minute, second = match.groups()
        month = _MONTHS.get(mon.title())
        if month:
            year_i = int(year)
            if year_i < 100:
                year_i += 2000
            naive = datetime(
                year_i,
                month,
                int(day),
                int(hour or 0),
                int(minute or 0),
                int(second or 0),
            )
            return timezone.make_aware(naive, timezone.get_current_timezone())
    for fmt in (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            naive = datetime.strptime(text, fmt)
            return timezone.make_aware(naive, timezone.get_current_timezone())
        except ValueError:
            continue
    return None


def _dec(val):
    text = str(val or "").strip().replace(",", "").strip('"')
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _int(val, default=None):
    text = str(val or "").strip().replace(",", "").strip('"')
    if not text:
        return default
    try:
        return int(Decimal(text))
    except (InvalidOperation, ValueError, TypeError):
        return default


def parse_idirect_orderbook(file_or_text):
    """
    IDirect equity CSV columns include Date, Stock, Action, Qty, Price, Order Ref.
    Returns a list of fill dicts (oldest first).
    """
    if hasattr(file_or_text, "read"):
        raw = file_or_text.read()
    else:
        raw = file_or_text
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")
    else:
        raw = str(raw).lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(raw))
    rows = []
    for row in reader:
        stock = (row.get("Stock") or row.get("Scrip") or "").strip().strip('"').upper()
        action = (row.get("Action") or row.get("Transaction") or "").strip().strip('"').upper()
        if action in ("B", "BUY"):
            action = "BUY"
        elif action in ("S", "SELL"):
            action = "SELL"
        qty = _int(row.get("Qty") or row.get("Quantity"))
        price = _dec(row.get("Price") or row.get("Avg. Price") or row.get("Average Price"))
        if not stock or action not in ("BUY", "SELL") or not qty or not price:
            continue
        rows.append({
            "stock_code": stock,
            "action": action,
            "qty": qty,
            "price": price,
            "when": parse_idirect_datetime(row.get("Date") or row.get("Order Date")),
            "order_ref": (row.get("Order Ref.") or row.get("Order Ref") or row.get("Order ID") or "").strip().strip('"'),
            "exchange": (row.get("Exchange") or "NSE").strip().strip('"') or "NSE",
        })
    rows.sort(key=lambda r: r["when"] or timezone.now())
    return rows


def apply_idirect_fills(fills, reviewed_by="idirect-csv"):
    """
    Upsert tracked buys from the CSV. Sells close matching open qty.
    Existing remaining qty (partial books) is preserved when buy qty matches.
    """
    executor = OrderExecutor()
    created = 0
    updated = 0
    closed = 0
    skipped = 0
    errors = []
    details = []

    for fill in fills:
        code = fill["stock_code"]
        action = fill["action"]
        qty = fill["qty"]
        price = fill["price"]
        when = fill.get("when") or timezone.now()
        notes = f"IDirect CSV {fill.get('order_ref') or ''}".strip()

        if action == "BUY":
            trade = (
                LiveTrade.objects.filter(stock_code=code, status="Executed", action="BUY")
                .order_by("-timestamp")
                .first()
            )
            if trade:
                changed = []
                if trade.entry_price != price or trade.price != price:
                    sold = (trade.quantity or 0) - trade.open_qty()
                    trade.entry_price = price
                    trade.price = price
                    if sold > 0 and trade.exit_price:
                        pnl = (float(trade.exit_price) - float(price)) * sold
                        trade.profit_loss = Decimal(str(round(pnl, 2)))
                    changed.append(f"entry {price}")
                if (trade.quantity or 0) < qty:
                    extra = qty - (trade.quantity or 0)
                    trade.quantity = qty
                    trade.remaining_quantity = trade.open_qty() + extra
                    changed.append(f"qty {qty}")
                if fill.get("when") and trade.entry_time != fill["when"]:
                    trade.entry_time = fill["when"]
                    changed.append("time")
                if changed:
                    trade.notes = (notes or trade.notes or "")[:255]
                    trade.save()
                    updated += 1
                    details.append(f"{code} updated ({', '.join(changed)})")
                else:
                    skipped += 1
                    details.append(f"{code} already matches")
                continue

            result = executor.record_tracked_fill(
                stock_code=code,
                qty=qty,
                entry_price=price,
                entry_time=when,
                notes=notes,
                reviewed_by=reviewed_by,
            )
            if result.get("success"):
                LiveTrade.objects.filter(pk=result["trade_id"]).update(
                    exchange=(fill.get("exchange") or "NSE")[:10]
                )
                created += 1
                details.append(f"{code} added qty {qty} @ {price}")
            else:
                errors.append(f"{code}: {result.get('message')}")
            continue

        result = executor.record_broker_exit(
            stock_code=code,
            qty=qty,
            exit_price=price,
            exit_time=when,
            notes=notes,
            reviewed_by=reviewed_by,
        )
        if result.get("success"):
            closed += 1
            details.append(result.get("message") or f"{code} sell booked")
        else:
            errors.append(f"{code} sell: {result.get('message')}")

    return {
        "created": created,
        "updated": updated,
        "closed": closed,
        "skipped": skipped,
        "errors": errors,
        "details": details,
    }
