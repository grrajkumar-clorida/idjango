from django.shortcuts import render
from django.utils import timezone

from .models import Source, Stocks50MA, StockPriceData
from .utils import place_order  # noqa: F401  — wired in data.urls


def sma50_dashboard(request):
    stocks = Stocks50MA.objects.filter(status__gt=3, status__lt=13).order_by(
        "-created_at", "id"
    )

    min_chg = request.GET.get("min_chg")
    max_chg = request.GET.get("max_chg")
    status = request.GET.get("status")
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

    live_data_map = StockPriceData.latest_by_stock_code()
    for stock in stocks:
        live = live_data_map.get(stock.stock_code)
        if not live:
            continue
        stock.live_price = live.close_price
        if stock.stock_cmp is not None:
            stock.live_change = round(live.close_price - stock.stock_cmp, 2)
        if stock.moving_average_50 is not None:
            stock.sma50_range = round(live.close_price - stock.moving_average_50, 2)
        stock.live50ma = live.live50ma
        stock.cp50ma = live.cp50ma
        stock.live21ma = live.live21ma
        stock.live09ma = live.live9ma

    context = {
        "stocks": stocks,
        "total_stocks": stocks.count(),
        "selected_status": status or "",
        "min_chg": min_chg or "",
        "max_chg": max_chg or "",
        "today_only": today_only,
    }
    if request.htmx:
        return render(request, "data/_stock_table.html", context)

    return render(request, "data/dashboard_htmx.html", context)


def chartink_dashboard(request):
    stocks = Source.objects.all()

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

    if request.htmx:
        return render(request, "data/_stock_table.html", {"stocks": stocks})

    return render(request, "data/source_htmx.html", {"stocks": stocks})
