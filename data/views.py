from django.shortcuts import render
from django.utils import timezone
from django.conf import settings
from django.db.models import Q
from .models import Source, Stocks50MA, StockPriceData
from .utils import get_google_sheet_data, filter_stock, update_google_sheet, place_order
from django.forms.models import model_to_dict
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

def sma50_dashboard(request):
	stocks = Stocks50MA.objects.all().filter(status__gt=3).filter(status__lt=13).order_by('-created_at', 'id')

	# Create a dictionary mapping script codes to live data
	live_data_map = {
		spd.script: spd for spd in StockPriceData.objects.all()
	}
	#print(stocks)
	# Attach CMP info dynamically to each stock object
	for stock in stocks:
		script = stock.script.upper()
		live = live_data_map.get(stock.script)
		if live:
			stock.live_price = live.close_price
			stock.live_change = round(live.close_price - stock.stock_cmp, 2)
			stock.sma50_range = round(live.close_price - stock.moving_average_50, 2)
			stock.live50ma = live.live50ma
			stock.cp50ma = live.cp50ma
			stock.live21ma = live.live21ma
			stock.live09ma = live.live9ma

	min_chg = request.GET.get("min_chg")
	max_chg = request.GET.get("max_chg")
	status = request.GET.get('status')

	today_only = request.GET.get("today") == "1"
	if min_chg:
		stocks = stocks.filter(percent_50sma__gte=float(min_chg))
	if max_chg:
		stocks = stocks.filter(percent_50sma__lte=float(max_chg))
	if today_only:
		today = timezone.now().date()
		stocks = stocks.filter(created_at__date=today)
	if status:
		stocks = stocks.filter(status=status)
	if request.htmx:
		return render(request, "data/_stock_table.html", {
			"stocks": stocks,
			"total_stocks": stocks.count(),	
		})
		
	return render(request, "data/dashboard_htmx.html", {
        "stocks": stocks,
        "total_stocks": stocks.count(),
    })
    #return render(request, "dashboard_htmx.html", {"stocks": stocks})


def chartink_dashboard(request):
	stocks = Source.objects.all()

	min_chg = request.GET.get("min_chg")
	max_chg = request.GET.get("max_chg")
	today_only = request.GET.get("today") == "1"
	if min_chg:
		stocks = stocks.filter(chg_percent__gte=float(min_chg))
	if max_chg:
		stocks = stocks.filter(chg_percent__lte=float(max_chg))
	if today_only:
		today = timezone.now().date()
		stocks = stocks.filter(created_at__date=today)

	if request.htmx:
		return render(request, "data/_stock_table.html", {"stocks": stocks})

	return render(request, "data/source_htmx.html", {
        "stocks": stocks,
    })
    #return render(request, "dashboard_htmx.html", {"stocks": stocks})
