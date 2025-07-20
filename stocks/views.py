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
    positions = Orders.objects.all() #filter(status=1)

    return render(request, 'stocks/open_positions.html', {"positions":positions})

def stock_dashboard(request):
    stocks = StockData.objects.filter(symbol="ITC").order_by("date")
    
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