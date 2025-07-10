from django.shortcuts import render
from django.utils import timezone
from django.conf import settings
from django.db.models import Q
from .models import Source, Stocks50MA
from .utils import get_50ma_google_sheet_data, filter_stock, update_google_sheet  # 👈 import here
from django.forms.models import model_to_dict
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

def sma50_dashboard(request):
	stocks = Stocks50MA.objects.all()
	
	# Attach CMP info dynamically to each stock object
	for stock in stocks:
		script = stock.script.upper()
		#google_fin = filter_stock(sheet_data, script)

		# 	stock.cmp = google_fin.get('Cmp', "-")
		# 	stock.sma50 = google_fin.get('50MA', "-")
		# 	stock.range50 = google_fin.get('Range50', "-")
		# 	stock.persent = google_fin.get('Persentage	', "-")
		# 	stock.t1 = google_fin.get('T1', "-")
		# 	stock.t2 = google_fin.get('T2', "-")
		# 	stock.t3 = google_fin.get('T3', "-")
		# 	stock.t4 = google_fin.get('T4', "-")
		# print(type(stock))


	#print(data_dict)
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
		return render(request, "_stock_table.html", {"stocks": stocks})
	
	return render(request, "dashboard_htmx.html", {
        "stocks": stocks,
    })
    #return render(request, "dashboard_htmx.html", {"stocks": stocks})


def chartink_dashboard(request):
	stocks = Source.objects.all()
	
	# Attach CMP info dynamically to each stock object
	# for stock in stocks:
	# 	symbol = stock.symbol.upper()
	# 	stock.cmp = cmp_data.get(symbol, {}).get("cmp", "-")
	# 	stock.cmp_date = cmp_data.get(symbol, {}).get("date", "-")


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
		return render(request, "_stock_table.html", {"stocks": stocks})

	return render(request, "source_htmx.html", {
        "stocks": stocks,
    })
    #return render(request, "dashboard_htmx.html", {"stocks": stocks})


def place_order():
	print('ff')
