from django.shortcuts import render, redirect
from django.shortcuts import render, get_object_or_404, redirect
from datetime import datetime, timedelta
from .models import Stock, StockData, LiveTrade, BacktestResult, Orders
from django.http import JsonResponse
from infra.utils.breeze_client import BreezeAPI
from django.core.mail import send_mail
from django.conf import settings
#import
import json
import requests

def home(request):
#    user = authenticate(username='bhuvi', password='demo@123')
    # if user is not None:
    #     print("User authenticated successfully")
    # else:
    #     print("Invalid username or password")
    # #employees = User.objects.all()
    return render(request, 'home.html')

def open_positions(request):
    """Display open positions with filtering, pagination, and statistics"""
    from django.core.paginator import Paginator
    from django.db.models import Sum, Q, Avg, Count
    
    # Get filter parameters
    status_filter = request.GET.get('status', '0')  # Default to open positions
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort', '-created_at')
    
    # Base queryset - filter by status
    if status_filter == 'all':
        positions = Orders.objects.all()
    elif status_filter == '0':
        positions = Orders.objects.filter(status=0)  # Open positions
    elif status_filter == '1':
        positions = Orders.objects.filter(status=1)  # Closed positions
    else:
        positions = Orders.objects.filter(status=int(status_filter))
    
    # Apply search filter
    if search_query:
        positions = positions.filter(
            Q(ticker__icontains=search_query) |
            Q(script__icontains=search_query) |
            Q(order_id__icontains=search_query)
        )
    
    # Apply sorting
    valid_sort_fields = ['created_at', '-created_at', 'ticker', '-ticker', 'overall_pl', '-overall_pl', 'invested_value', '-invested_value']
    if sort_by in valid_sort_fields:
        positions = positions.order_by(sort_by)
    else:
        positions = positions.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(positions, 25)  # 25 positions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate statistics for current filtered set
    total_positions = positions.count()
    total_invested = positions.aggregate(total=Sum('invested_value'))['total'] or 0.0
    total_current_value = positions.aggregate(total=Sum('current_value'))['total'] or 0.0
    total_pl = positions.aggregate(total=Sum('overall_pl'))['total'] or 0.0
    total_day_pl = positions.aggregate(total=Sum('day_pl'))['total'] or 0.0
    
    # Calculate average P/L percentage
    if total_invested > 0:
        avg_pl_percent = (total_pl / total_invested) * 100
    else:
        avg_pl_percent = 0.0
    
    # Count winning vs losing positions
    winning_positions = positions.filter(overall_pl__gt=0).count()
    losing_positions = positions.filter(overall_pl__lt=0).count()
    breakeven_positions = positions.filter(overall_pl=0).count()
    
    # Calculate P/L percentage for each position (for template display)
    positions_list = list(page_obj)
    for position in positions_list:
        if position.invested_value and position.invested_value > 0:
            position.pl_percent = (position.overall_pl / position.invested_value) * 100
        else:
            position.pl_percent = 0.0
    
    context = {
        'positions': page_obj,
        'total_positions': total_positions,
        'total_invested': total_invested,
        'total_current_value': total_current_value,
        'total_pl': total_pl,
        'total_day_pl': total_day_pl,
        'avg_pl_percent': avg_pl_percent,
        'winning_positions': winning_positions,
        'losing_positions': losing_positions,
        'breakeven_positions': breakeven_positions,
        'status_filter': status_filter,
        'search_query': search_query,
        'sort_by': sort_by,
    }
    
    return render(request, 'stocks/open_positions.html', context)

def stock_dashboard(request):
    # Use 'stock' field instead of 'symbol'
    stocks = StockData.objects.filter(stock="ITC").order_by("date")
    
    dates = [str(stock.date) for stock in stocks]
    prices = [stock.close_price for stock in stocks]

    context = {
        "dates": json.dumps(dates),
        "prices": json.dumps(prices)
    }
    return render(request, "stocks/dashboard.html", context)


def place_trade(request):
    if request.method == "POST":
        stock = request.POST["stock"]
        quantity = int(request.POST["quantity"])
        action = request.POST["action"]  # BUY or SELL
        order_type = request.POST["order_type"]  # MARKET or LIMIT
        price = float(request.POST["price"]) if order_type == "LIMIT" else 0

        response = breeze.place_order(stock, "NSE", quantity, order_type, price, "cash", action)

        if response["Status"] == "Success":
            trade = LiveTrade.objects.create(
                stock_code=stock,
                quantity=quantity,
                order_type=order_type,
                price=price,
                action=action,
                status="Executed",
                order_id=response["order_id"]
            )
            return JsonResponse({"message": "Trade Executed", "order_id": response["order_id"]})
        else:
            return JsonResponse({"error": response["ErrorMessage"]})

def cancel_trade(request, order_id):
    response = breeze.cancel_order(order_id)
    if response["Status"] == "Success":
        LiveTrade.objects.filter(order_id=order_id).update(status="Canceled")
        return JsonResponse({"message": "Trade Canceled"})
    return JsonResponse({"error": response["ErrorMessage"]})

def modify_trade(request, order_id):
    if request.method == "POST":
        new_price = float(request.POST["new_price"])
        response = breeze.modify_order(order_id, new_price)
        if response["Status"] == "Success":
            LiveTrade.objects.filter(order_id=order_id).update(price=new_price)
            return JsonResponse({"message": "Trade Modified"})
        return JsonResponse({"error": response["ErrorMessage"]})

def backtest_results(request):
    results = BacktestResult.objects.all().order_by("-timestamp")
    return render(request, "stocks/backtest_results.html", {"results": results})


    #Backtest result
def backtest_results_view(request):
    # Fetch latest 10 backtest results
    backtest_results = BacktestResult.objects.order_by('-id')[:10]
    
    # Convert data to JSON format for Chart.js
    data = {
        "dates": [bt.start_date.strftime('%Y-%m-%d') for bt in backtest_results],
        "profit_factor": [bt.profit_factor if bt.profit_factor is not None else 0 for bt in backtest_results],
        "max_drawdown": [bt.max_drawdown if bt.max_drawdown is not None else 0 for bt in backtest_results],
        "total_trades": [bt.total_trades for bt in backtest_results],
    }

    return render(request, 'stocks/backtest_view.html', {"data": data})

def get_live_price(request):
    breeze = BreezeAPI()

    # Fetch live market data for ITC (NSE)
    response = breeze.get_live_price("ITC", "NSE")

    if response: #and "Success" in response.get("Status", "200"):
        data = response.get("Success", [])
        if data:
            #nse_data = [entry for entry in data if entry.get("exchange_code") == "NSE"]
            latest_data = next((entry for entry in reversed(data) if entry.get("exchange_code") == "NSE"), None)
            
            return JsonResponse({'NSE_PRICE':latest_data.get('ltp', 'N/A')})
    
    return JsonResponse({"error": "Failed to fetch live price"})

def get_web_data(request):
    return render(request, 'web.html')

def send_trade_alert(symbol, action):
    """Send trade alerts via email and Telegram."""
    
    # Email Alert
    subject = f"{action} Alert for {symbol}"
    message = f"Stock: {symbol}\nAction: {action}\nCheck your dashboard for more details."
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, ['bhuviram2426@gmail.com'])

    # Telegram Alert
    TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"
    TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"
    telegram_message = f"🚨 {action} Alert for {symbol} 🚨\nCheck your dashboard!"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': telegram_message})