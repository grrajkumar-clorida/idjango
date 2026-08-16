"""Phase 2 human trading desk: review queue, orders, positions."""
from decimal import Decimal, InvalidOperation
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from data.models import StockPriceData, Stocks50MA
from data.engine.order_executor import OrderExecutor
from stocks.models import LiveTrade, Orders, Stock, TradeReview


def _dec(val):
    if val is None or val == "":
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _int(val, default=None):
    if val is None or val == "":
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _reviewer(request):
    if request.user.is_authenticated:
        return request.user.get_username()[:80]
    return "desk"


def _parse_entry_at(val):
    """Parse desk datetime: 29-Jul-2026 10:47 or HTML datetime-local."""
    if not val:
        return None
    text = str(val).strip()
    if not text:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%d-%b-%Y %H:%M",
        "%d-%b-%Y %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M",
    ):
        try:
            naive = datetime.strptime(text, fmt)
            return timezone.make_aware(naive, timezone.get_current_timezone())
        except ValueError:
            continue
    return None


def _stock_suggestion_rows(q="", limit=20):
    q = (q or "").strip()
    rows = []
    seen = set()

    def add(code, name="", ticker=""):
        code = (code or "").strip().upper()
        if not code or code in seen:
            return
        seen.add(code)
        extra = (name or ticker or "").strip()
        rows.append({
            "code": code,
            "label": f"{code} — {extra}" if extra else code,
        })

    ma_qs = Stocks50MA.objects.all()
    stock_qs = Stock.objects.all()
    if q:
        ma_qs = ma_qs.filter(
            Q(stock_code__icontains=q)
            | Q(ticker__icontains=q)
            | Q(name__icontains=q)
        )
        stock_qs = stock_qs.filter(
            Q(stock_code__icontains=q)
            | Q(script__icontains=q)
            | Q(company_name__icontains=q)
        )
    for s in ma_qs.order_by("stock_code")[: limit * 15]:
        add(s.stock_code, s.name or "", s.ticker or "")
        if len(rows) >= limit:
            return rows
    for s in stock_qs.order_by("stock_code")[:limit]:
        add(s.stock_code, s.company_name or "", s.script or "")
        if len(rows) >= limit:
            return rows
    if q:
        for code in (
            StockPriceData.objects.filter(stock_code__icontains=q)
            .values_list("stock_code", flat=True)
            .distinct()[:limit]
        ):
            add(code)
            if len(rows) >= limit:
                break
        for code in (
            LiveTrade.objects.filter(stock_code__icontains=q)
            .values_list("stock_code", flat=True)
            .distinct()[:limit]
        ):
            add(code)
            if len(rows) >= limit:
                break
    return rows


@require_GET
def stock_suggest(request):
    q = request.GET.get("q") or ""
    return JsonResponse({"results": _stock_suggestion_rows(q, limit=20)})


def _live_row(live_map, code):
    code = (code or "").strip()
    if not code:
        return None
    return live_map.get(code) or live_map.get(code.upper())


def _upsert_live_cmp(stock_code, close_price):
    """Write today's CMP so positions / monitor can mark P/L."""
    code = (stock_code or "").strip().upper()
    price = _dec(close_price)
    if not code or price is None or price <= 0:
        return None
    obj, _ = StockPriceData.objects.update_or_create(
        stock_code=code,
        date=timezone.now().date(),
        defaults={"close_price": float(price)},
    )
    return obj


def _breeze_ltp(stock_code, exchange="NSE", breeze=None):
    from infra.utils.breeze_client import BreezeAPI

    if breeze is None:
        breeze = BreezeAPI()
    if not getattr(breeze, "api_status", False):
        return None
    resp = breeze.get_live_price(stock_code, exchange)
    data = (resp or {}).get("Success") or []
    if isinstance(data, dict):
        data = [data]
    if not data:
        return None
    row = data[-1]
    raw = row.get("ltp") or row.get("last") or row.get("close")
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    return val if val > 0 else None


def _attach_live(rows, code_attr="stock_code"):
    live_map = StockPriceData.latest_by_stock_code()
    sma_rows = list(
        Stocks50MA.objects.exclude(stock_code__isnull=True).exclude(stock_code="")
        .only("stock_code", "stock_cmp")
    )
    sma_cmp = {
        (s.stock_code or "").upper(): s.stock_cmp
        for s in sma_rows
        if s.stock_cmp
    }
    sma_codes = {(s.stock_code or "").upper() for s in sma_rows}
    for row in rows:
        code = getattr(row, code_attr)
        live = _live_row(live_map, code)
        price = live.close_price if live else None
        if not price:
            price = sma_cmp.get((code or "").strip().upper())
        row.live_price = price if price else None
        row.live_50 = live.live50ma if live else None
        row.live_cp50 = live.cp50ma if live else None
        key = (code or "").strip().upper()
        if row.live_price:
            row.live_hint = ""
        elif key in sma_codes:
            row.live_hint = (
                "On the 50MA list but no CMP yet. Wait for the 5-min sheet fetch, "
                "or type Live CMP / Refresh (Breeze)."
            )
        else:
            row.live_hint = (
                "Not on the ChartInk 50MA sheet. Type Live CMP from TradingView/broker "
                "and Save, or Refresh (Breeze LTP)."
            )
        entry = float(
            getattr(row, "entry_price", None)
            or getattr(row, "price", None)
            or 0
        )
        qty = 0
        if hasattr(row, "open_qty"):
            qty = row.open_qty()
        elif getattr(row, "quantity", None):
            qty = row.quantity
        if row.live_price and entry and qty:
            if getattr(row, "action", "BUY") == "SELL":
                row.mark_pl = (entry - float(row.live_price)) * qty
            else:
                row.mark_pl = (float(row.live_price) - entry) * qty
            row.mark_pl_pct = (row.mark_pl / (entry * qty)) * 100 if entry * qty else 0
        else:
            row.mark_pl = float(getattr(row, "profit_loss", 0) or 0)
            row.mark_pl_pct = 0
    return rows


def review_queue(request):
    """Status-8 / pending human review. Approve with qty + price range."""
    executor = OrderExecutor()
    executor.queue_status_8_for_review()

    pending = list(
        TradeReview.objects.filter(status__in=["pending", "approved", "failed"])
    )
    _attach_live(pending)

    status8 = Stocks50MA.objects.filter(status=8).order_by("-updated_at", "-id")
    recent = TradeReview.objects.filter(
        status__in=["placed", "rejected"]
    )[:15]

    return render(request, "stocks/desk_review.html", {
        "pending": pending,
        "status8_count": status8.count(),
        "recent": recent,
        "paper": getattr(settings, "PAPER_TRADING_MODE", True),
    })


def _apply_review_post(review, request):
    review.qty = _int(request.POST.get("qty"), review.qty) or 1
    review.order_type = request.POST.get("order_type") or review.order_type or "MARKET"
    review.price_min = _dec(request.POST.get("price_min"))
    review.price_max = _dec(request.POST.get("price_max"))
    review.limit_price = _dec(request.POST.get("limit_price"))
    review.stop_loss = _dec(request.POST.get("stop_loss"))
    review.take_profit = _dec(request.POST.get("take_profit"))
    review.take_profit_qty = _int(request.POST.get("take_profit_qty"), review.take_profit_qty)
    review.notes = (request.POST.get("notes") or review.notes or "")[:255]
    review.reviewed_by = _reviewer(request)
    review.reviewed_at = timezone.now()


@require_POST
def review_approve(request, pk):
    review = get_object_or_404(TradeReview, pk=pk)
    _apply_review_post(review, request)
    if review.qty < 1:
        messages.error(request, "Qty must be at least 1.")
        return redirect("desk_review")
    review.status = "approved"
    review.last_error = ""
    review.save()
    messages.success(
        request,
        f"{review.stock_code} approved (qty {review.qty}). "
        "Executor will place when CMP is inside your price range.",
    )
    return redirect("desk_review")


@require_POST
def review_place(request, pk):
    review = get_object_or_404(TradeReview, pk=pk)
    _apply_review_post(review, request)
    if review.qty < 1:
        messages.error(request, "Qty must be at least 1.")
        return redirect("desk_review")
    review.status = "approved"
    review.save()

    result = OrderExecutor().place_approved_review(review)
    if result.get("success"):
        messages.success(
            request,
            f"{review.stock_code} order placed: {result.get('order_id')} "
            f"qty={result.get('quantity')} @ {result.get('price')}",
        )
        return redirect("desk_orders")
    messages.warning(request, f"{review.stock_code}: {result.get('message')}")
    return redirect("desk_review")


@require_POST
def review_reject(request, pk):
    review = get_object_or_404(TradeReview, pk=pk)
    review.status = "rejected"
    review.reviewed_by = _reviewer(request)
    review.reviewed_at = timezone.now()
    review.notes = (request.POST.get("notes") or review.notes or "Rejected")[:255]
    review.save()
    stock = Stocks50MA.objects.filter(stock_code=review.stock_code, status=8).first()
    if stock:
        stock.status = 7
        stock.save(update_fields=["status"])
    messages.info(request, f"{review.stock_code} rejected.")
    return redirect("desk_review")


@require_POST
def review_manual(request):
    stock_code = (request.POST.get("stock_code") or "").strip().upper()
    if not stock_code:
        messages.error(request, "Stock code is required.")
        return redirect("desk_review")

    mode = (request.POST.get("mode") or "order").strip().lower()
    live_map = StockPriceData.latest_by_stock_code()
    live = live_map.get(stock_code)
    stock = Stocks50MA.objects.filter(stock_code=stock_code).first()
    qty = _int(request.POST.get("qty"), 1) or 1

    if mode == "track":
        entry_price = _dec(request.POST.get("entry_price")) or _dec(
            request.POST.get("suggested_price")
        )
        entry_time = _parse_entry_at(
            request.POST.get("entry_at")
            or request.POST.get("entry_at_text")
            or request.POST.get("entry_at_local")
        )
        if entry_price is None or entry_price <= 0:
            messages.error(request, "Buy / book price is required for tracking.")
            return redirect("desk_review")
        if entry_time is None:
            messages.error(
                request,
                "Entry time is required (e.g. 29-Jul-2026 10:47).",
            )
            return redirect("desk_review")

        result = OrderExecutor().record_tracked_fill(
            stock_code=stock_code,
            qty=qty,
            entry_price=entry_price,
            entry_time=entry_time,
            take_profit=_dec(request.POST.get("take_profit")),
            take_profit_qty=_int(request.POST.get("take_profit_qty"), qty),
            stop_loss=_dec(request.POST.get("stop_loss")),
            notes=(request.POST.get("notes") or "")[:255],
            ticker=(stock.ticker if stock else "") or "",
            name=(stock.name if stock else "") or "",
            reviewed_by=_reviewer(request),
        )
        if result.get("success"):
            messages.success(
                request,
                f"Tracking {stock_code} qty {result['quantity']} @ "
                f"{result['price']} on {entry_time.strftime('%d-%b-%Y %H:%M')}.",
            )
            return redirect("desk_positions")
        messages.error(request, result.get("message") or "Could not add tracking row.")
        return redirect("desk_review")

    cmp = _dec(request.POST.get("suggested_price"))
    if cmp is None and live:
        cmp = _dec(live.close_price)

    review = TradeReview.objects.create(
        stock_code=stock_code,
        ticker=(stock.ticker if stock else "") or "",
        name=(stock.name if stock else "") or "",
        source="manual",
        status="pending",
        suggested_price=cmp,
        live_50ma=live.live50ma if live else None,
        cp50ma_percent=live.cp50ma if live else None,
        qty=qty,
        order_type=request.POST.get("order_type") or "MARKET",
        price_min=_dec(request.POST.get("price_min")),
        price_max=_dec(request.POST.get("price_max")),
        limit_price=_dec(request.POST.get("limit_price")),
        stop_loss=_dec(request.POST.get("stop_loss")),
        take_profit=_dec(request.POST.get("take_profit")),
        take_profit_qty=_int(request.POST.get("take_profit_qty"), qty),
        notes=(request.POST.get("notes") or "Manual desk entry")[:255],
        reviewed_by=_reviewer(request),
    )
    messages.success(request, f"Manual review created for {stock_code} (qty {qty}).")
    if request.POST.get("place_now"):
        review.status = "approved"
        review.reviewed_at = timezone.now()
        review.save()
        result = OrderExecutor().place_approved_review(review)
        if result.get("success"):
            messages.success(request, f"{stock_code} placed: {result.get('order_id')}")
            return redirect("desk_orders")
        messages.warning(request, result.get("message") or "Place failed")
    return redirect("desk_review")


def order_list(request):
    """All placed orders (LiveTrade fills)."""
    status = request.GET.get("status", "all")
    search = request.GET.get("search", "").strip()
    trades = LiveTrade.objects.all().order_by("-timestamp")
    if status and status != "all":
        trades = trades.filter(status=status)
    if search:
        trades = trades.filter(
            Q(stock_code__icontains=search) | Q(order_id__icontains=search)
        )
    trades = list(trades[:200])
    _attach_live(trades)

    invested = 0.0
    open_pl = 0.0
    for t in trades:
        entry = float(t.entry_price or t.price or 0)
        invested += entry * t.open_qty()
        open_pl += float(getattr(t, "mark_pl", 0) or t.profit_loss or 0)

    return render(request, "stocks/desk_orders.html", {
        "trades": trades,
        "status": status,
        "search": search,
        "total": len(trades),
        "invested": invested,
        "open_pl": open_pl,
        "ledger": Orders.objects.all().order_by("-created_at")[:100],
    })


def position_list(request):
    """Open positions with live P/L. Human can set profit-book price/qty."""
    positions = list(
        LiveTrade.objects.filter(status="Executed").order_by("-timestamp")
    )
    _attach_live(positions)

    total_pl = sum(float(getattr(p, "mark_pl", 0) or 0) for p in positions)
    invested = 0.0
    for p in positions:
        entry = float(p.entry_price or p.price or 0)
        invested += entry * p.open_qty()
    winners = sum(1 for p in positions if float(getattr(p, "mark_pl", 0) or 0) > 0)
    losers = sum(1 for p in positions if float(getattr(p, "mark_pl", 0) or 0) < 0)

    missing_live = sum(1 for p in positions if not getattr(p, "live_price", None))

    return render(request, "stocks/desk_positions.html", {
        "positions": positions,
        "total": len(positions),
        "total_pl": total_pl,
        "invested": invested,
        "current_value": invested + total_pl,
        "avg_pl_percent": (total_pl / invested * 100) if invested else 0,
        "winners": winners,
        "losers": losers,
        "missing_live": missing_live,
    })


@require_POST
def position_update(request, pk):
    trade = get_object_or_404(LiveTrade, pk=pk, status="Executed")
    trade.profit_book_price = _dec(request.POST.get("profit_book_price"))
    trade.take_profit = trade.profit_book_price
    trade.profit_book_qty = _int(request.POST.get("profit_book_qty"), trade.profit_book_qty)
    if trade.profit_book_qty is not None and trade.profit_book_qty < 1:
        trade.profit_book_qty = 1
    if trade.profit_book_qty and trade.profit_book_qty > trade.open_qty():
        trade.profit_book_qty = trade.open_qty()
    trade.stop_loss = _dec(request.POST.get("stop_loss")) or trade.stop_loss
    trade.notes = (request.POST.get("notes") or trade.notes or "")[:255]
    trade.save()

    live_saved = _upsert_live_cmp(trade.stock_code, request.POST.get("live_price"))
    extra = f" · live {live_saved.close_price}" if live_saved else ""
    messages.success(
        request,
        f"{trade.stock_code}: profit book {trade.profit_book_price} "
        f"qty {trade.profit_book_qty or trade.open_qty()}{extra}",
    )
    return redirect("desk_positions")


@require_POST
def position_refresh_prices(request):
    """Pull Breeze LTP for open positions that have no usable CMP."""
    positions = list(LiveTrade.objects.filter(status="Executed"))
    _attach_live(positions)
    missing = [t for t in positions if not getattr(t, "live_price", None)]
    if not missing:
        messages.info(request, "All open positions already have a live CMP.")
        return redirect("desk_positions")

    from infra.utils.breeze_client import BreezeAPI

    try:
        breeze = BreezeAPI()
    except Exception:
        breeze = None
    if not breeze or not getattr(breeze, "api_status", False):
        messages.warning(
            request,
            "Breeze session is not active. Type Live CMP on the row and Save. "
            "Missing: " + ", ".join(t.stock_code for t in missing) + ".",
        )
        return redirect("desk_positions")

    updated = []
    failed = []
    for trade in missing:
        ltp = _breeze_ltp(trade.stock_code, trade.exchange or "NSE", breeze=breeze)
        if ltp and _upsert_live_cmp(trade.stock_code, ltp):
            updated.append(f"{trade.stock_code} @ {ltp}")
        else:
            failed.append(trade.stock_code)

    if updated:
        messages.success(request, "Live CMP updated: " + ", ".join(updated))
    if failed:
        messages.warning(
            request,
            "No live quote for: " + ", ".join(failed) + ". Type Live CMP and Save.",
        )
    return redirect("desk_positions")
