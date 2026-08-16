from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from .models import Source, Stocks50MA, StockPriceData

PAGE_SIZE = 25

STATUS_LABELS = {
    0: "Invalid",
    1: "Over value",
    2: "Stoploss",
    3: "Completed",
    4: "New",
    5: "Update",
    6: "Entry",
    7: "Confirmation",
    8: "Order",
    9: "Target 1",
    10: "Target 2",
    11: "Target 3",
    12: "Above T3",
    13: "Altra",
}


def place_order(request):
    """Legacy 1-qty Breeze buy. Disabled — use /stocks/review/."""
    return JsonResponse(
        {
            "status": "error",
            "message": "Direct /data/place-order/ is disabled. Use /stocks/review/.",
        },
        status=410,
    )


def _live_for(live_map, code):
    code = (code or "").strip()
    if not code:
        return None
    return live_map.get(code) or live_map.get(code.upper())


def sma50_dashboard(request):
    stocks = Stocks50MA.objects.filter(status__gt=3, status__lt=13).order_by(
        "-created_at", "id"
    )

    min_chg = request.GET.get("min_chg")
    max_chg = request.GET.get("max_chg")
    status = request.GET.get("status")
    search = (request.GET.get("search") or "").strip()
    today_only = request.GET.get("today") == "1"

    if min_chg:
        stocks = stocks.filter(percent_50ma__gte=float(min_chg))
    if max_chg:
        stocks = stocks.filter(percent_50ma__lte=float(max_chg))
    if today_only:
        today = timezone.now().date()
        stocks = stocks.filter(created_at__date=today)
    if status:
        stocks = stocks.filter(status=status)
    if search:
        stocks = stocks.filter(
            Q(stock_code__icontains=search)
            | Q(ticker__icontains=search)
            | Q(name__icontains=search)
        )

    status8_count = stocks.filter(status=8).count()
    status7_count = stocks.filter(status=7).count()
    total_stocks = stocks.count()

    paginator = Paginator(stocks, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    page_stocks = list(page_obj.object_list)

    live_data_map = StockPriceData.latest_by_stock_code()
    with_live = 0
    for stock in page_stocks:
        live = _live_for(live_data_map, stock.stock_code)
        if not live:
            stock.live_price = None
            stock.live_change = None
            stock.sma50_range = None
            stock.live50ma = None
            stock.cp50ma = None
            stock.live21ma = None
            stock.live09ma = None
            stock.live921 = None
            stock.status_label = STATUS_LABELS.get(stock.status, "Out of range")
            continue
        stock.live_price = live.close_price
        if live.close_price:
            with_live += 1
        if stock.stock_cmp is not None and live.close_price is not None:
            stock.live_change = round(live.close_price - stock.stock_cmp, 2)
        else:
            stock.live_change = None
        if stock.moving_average_50 is not None and live.close_price is not None:
            stock.sma50_range = round(live.close_price - stock.moving_average_50, 2)
        else:
            stock.sma50_range = None
        stock.live50ma = live.live50ma
        stock.cp50ma = live.cp50ma
        stock.live21ma = live.live21ma
        stock.live09ma = live.live9ma
        stock.live921 = live.live921
        stock.status_label = STATUS_LABELS.get(stock.status, "Out of range")

    params = request.GET.copy()
    params.pop("page", None)
    querystring = params.urlencode()

    context = {
        "stocks": page_stocks,
        "page_obj": page_obj,
        "querystring": querystring,
        "total_stocks": total_stocks,
        "status8_count": status8_count,
        "status7_count": status7_count,
        "with_live": with_live,
        "selected_status": str(status or ""),
        "min_chg": min_chg or "",
        "max_chg": max_chg or "",
        "search": search,
        "today_only": today_only,
        "status_choices": STATUS_LABELS,
        "page_size": PAGE_SIZE,
    }
    if request.htmx:
        return render(request, "data/_stock_table.html", context)

    return render(request, "data/dashboard_htmx.html", context)


def chartink_dashboard(request):
    stocks = Source.objects.all().order_by("-created_at", "-id")

    min_chg = request.GET.get("min_chg")
    max_chg = request.GET.get("max_chg")
    today_only = request.GET.get("today") == "1"
    if min_chg:
        stocks = stocks.filter(percent__gte=float(min_chg))
    if max_chg:
        stocks = stocks.filter(percent__lte=float(max_chg))
    if today_only:
        today = timezone.now().date()
        stocks = stocks.filter(created_at__date=today)

    paginator = Paginator(stocks, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    params = request.GET.copy()
    params.pop("page", None)
    context = {
        "stocks": page_obj.object_list,
        "page_obj": page_obj,
        "querystring": params.urlencode(),
        "page_size": PAGE_SIZE,
    }
    if request.htmx:
        return render(request, "data/_source_table.html", context)

    return render(request, "data/source_htmx.html", context)
