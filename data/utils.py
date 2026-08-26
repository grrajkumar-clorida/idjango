import gspread
import requests
"secrets/your_google_credentials.json"
from oauth2client.service_account import ServiceAccountCredentials
from django.conf import settings
from django.core.mail import send_mail
from .models import Stocks50MA
from django.conf import settings
from datetime import datetime

def send_telegram_message(message):
    """Send a message to the Telegram bot."""
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": message
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to send Telegram message: {e}")

def get_cmp_data_from_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "secrets/gr8-n8n-automation-projects-d2ab9ab07004.json",  # place this JSON in your base dir or a `secrets/` folder
        scope
    )
    client = gspread.authorize(creds)

    sheet = client.open("chartink").sheet1  # Change to your actual sheet name
    rows = sheet.get_all_records()

    # Return dict: { 'SYMBOL': { 'cmp': 123, 'date': '2025-04-09' } }
    cmp_data = {
        row["Symbol"].upper(): {
            "cmp": row["CMP"],
            "date": row["Date"]
        }
        for row in rows
    }
    return cmp_data


def update_google_sheet(sheet, stock_list, new_data=''):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    creds = ServiceAccountCredentials.from_json_keyfile_name("secrets/gr8-n8n-automation-projects-d2ab9ab07004.json", scope)
    client = gspread.authorize(creds)

    spreadsheet = client.open("idjango")
    sheet = spreadsheet.worksheet(sheet)  # Or use .get_worksheet(0)

    sheet.batch_clear(["C2:C"])
    values = [[stock] for stock in stock_list]

    start_row = 2
    end_row = start_row + len(stock_list) - 1
    range_string = f"C{start_row}:C{end_row}"
    
    # Update the range with new data; using RAW value input mode.
    sheet.update(range_string, values, value_input_option="RAW")

    return("✅ Stock data column updated successfully!")

#
def get_google_sheet_data(spreadsheet_id, sheet_name, api_key):

    # Construct the URL for the Google Sheets API
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{sheet_name}!A1:Z?alt=json&key={api_key}'

    try:
        # Make a GET request to retrieve data from the Google Sheets API
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Parse the JSON response
        data = response.json()
        
        return data

    except requests.exceptions.RequestException as e:
        # Handle any errors that occur during the request
        print(f"An error occurred: {e}")

        return None

def safe_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.00

def moving_average(sheet_data):
    rows = sheet_data.get("values", [])
    headers = rows[0]
    data_rows = rows[1:]
    
    # Get the column indexes for 50MA and Range 50
    try:
        stock_col = headers.index("Stock")
        cmp_col = headers.index("CMP")
        closeyest = headers.index("Closeyest")
        changes= headers.index("Changes")
        changepct = headers.index("changepct")
        ma50_col = headers.index("50MA")
        range_col = headers.index("Range 50MA")
        percent_col = headers.index("Percent 50SMA")
        target_1 = headers.index("Target 1")
        target_2 = headers.index("Target 2")
        target_3 = headers.index("Target 3")
        target_4 = headers.index("Target 4")
        
    except ValueError:
        return None  # If column names not found

    # Find matching row
    sma_50 = []
    for row in data_rows:
        print(row[stock_col])
        # return {
        #     "Stock": row[stock_col],
        #     "Cmp": row[cmp_col],
        #     "50MA": row[ma50_col],
        #     "Range50": row[range_col],
        #     "Persentage":row[percent_col],
        #     "T1":row[target_1],
        #     "T2":row[target_2],
        #     "T3":row[target_3],
        #     "T4":row[target_4],
        # }

    return None  # If stock not found


def filter_stock(sheet_data, stock_code):

    rows = sheet_data.get("values", [])
    headers = rows[0]
    data_rows = rows[1:]
    
    # Get the column indexes for 50MA and Range 50
    try:
        stock_col = headers.index("Stock")
        cmp_col = headers.index("CMP")
        ma50_col = headers.index("50MA")
        range_col = headers.index("Range 50MA")
        percent_col = headers.index("Percent 50SMA")
        target_1 = headers.index("Target 1")
        target_2 = headers.index("Target 2")
        target_3 = headers.index("Target 3")
        target_4 = headers.index("Target 4")
        
    except ValueError:
        return None  # If column names not found

    # Find matching row
    for row in data_rows:
        
        if len(row) > stock_col and row[stock_col].strip().upper() == stock_code.strip().upper():
            return {
                "Stock": row[stock_col],
                "Cmp": row[cmp_col],
                "50MA": row[ma50_col],
                "Range50": row[range_col],
                "Persentage":row[percent_col],
                "T1":row[target_1],
                "T2":row[target_2],
                "T3":row[target_3],
                "T4":row[target_4],
            }
    return None  # If stock not found

def place_order(request):
    """Legacy 1-qty Breeze buy. Disabled — use the Review desk."""
    from django.http import JsonResponse

    return JsonResponse(
        {
            "status": "error",
            "message": "Direct place_order is disabled. Use /stocks/review/.",
        },
        status=410,
    )

# def place_orders(data):
#     payload = json.dumps({
#         "stock_code": data['code'],
#         "exchange_code": "NSE",
#         "product": "cash",
#         "action": "buy",
#         "order_type": "market",
#         "quantity": "1",
#         "price": "263.15",
#         "validity": "ioc"
#     })

#     stock = request.POST["stock"]
#     quantity = int(request.POST["quantity"])
#     action = request.POST["action"]  # BUY or SELL
#     order_type = request.POST["order_type"]  # MARKET or LIMIT
#     price = float(request.POST["price"]) if order_type == "LIMIT" else 0

#     response = breeze.place_order(stock, "NSE", quantity, order_type, price, "cash", action)

#     if response["Status"] == "Success":
#         trade = LiveTrade.objects.create(
#             stock_code=stock,
#             quantity=quantity,
#             order_type=order_type,
#             price=price,
#             action=action,
#             status="Executed",
#             order_id=response["order_id"]
#         )
#         return JsonResponse({"message": "Trade Executed", "order_id": response["order_id"]})
#     else:
#         return JsonResponse({"error": response["ErrorMessage"]})

def date_format(date):
    cmp_date_str = date.strip()
    try:
        cmp_date = datetime.strptime(cmp_date_str, "%Y-%m-%d").date()
    except ValueError:
        cmp_date = None  # fallback

    # Return
    date