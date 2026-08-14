import gspread
import requests
from django.conf import settings
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime

# utils.py

#Stock status List
STATUS_DICT = {
    0: "Invalid",
    1: "Over Value",
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


def status_list(output_type = "keys"):
    """
    Returns status in different formats.
    
    Parameters:
        output_type (str): "options", "list", "keys"
    
    Returns:
        str | list[int]
    """

    if output_type == "options":
        # Return <option> HTML
        return "\n".join(
            [f'<option value="{k}">{v}</option>' for k, v in STATUS_DICT.items()]
        )

    elif output_type == "list":
        # Return <ul> HTML
        items = "\n".join([f"<li>{k} - {v}</li>" for k, v in STATUS_DICT.items()])
        return f"<ul>\n{items}\n</ul>"

    elif output_type == "keys":
        # Return only keys (0–13)
        return list(STATUS_DICT.keys())

    else:
        raise ValueError("Invalid output_type. Use 'options', 'list', or 'keys'.")


def safe_float(val):
    if val is None or val == "":
        return 0.00
    if isinstance(val, (int, float)):
        return float(val)
    try:
        cleaned = str(val).strip().replace(",", "").replace("%", "")
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.00

def date_format(date):
    if date is None:
        return None
    cmp_date_str = str(date).strip()
    if not cmp_date_str:
        return None
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(cmp_date_str, fmt).date()
        except ValueError:
            continue
    return None

def status_list():
    print('o')

def nifty_list():
    nifty50 = [
        "TCS", "INFY", "HDFCBANK", "ICICIBANK", "LT", "ITC", "SBIN", "AXISBANK", "KOTAKBANK",
        "HINDUNILVR", "BHARTIARTL", "MARUTI", "ASIANPAINT", "BAJFINANCE", "WIPRO", "NTPC", "ONGC", "SUNPHARMA", "POWERGRID",
        "TITAN", "HCLTECH", "ULTRACEMCO", "TECHM", "NESTLEIND", "COALINDIA", "BAJAJFINSV", "GRASIM", "HINDALCO", "JSWSTEEL",
        "TATASTEEL", "ADANIENT", "ADANIPORTS", "M&M", "CIPLA", "DRREDDY", "DIVISLAB", "BPCL", "HEROMOTOCO", "EICHERMOT",
        "SBILIFE", "BAJAJ-AUTO", "BATAINDIA", "APOLLOHOSP", "BRITANNIA", "UPL", "INDUSINDBK", "SHREECEM", "LTIM", "DMART", "HDFCLIFE",
        "ABB", "AUROPHARMA", "BANKBARODA", "BEL", "BERGEPAINT", "BHEL", "BIOCON", "CANBK", "CHOLAFIN", "DLF",
        "GAIL", "GMRINFRA", "GODREJCP", "HAVELLS", "ICICIPRULI", "INDIGO", "INDUSTOWER", "IOC", "IRCTC", "LICHSGFIN",
        "MARICO", "MUTHOOTFIN", "NAUKRI", "PAGEIND", "PIDILITIND", "PNB", "RECLTD", "SAIL", "SBICARD", "SIEMENS",
        "SRF", "TORNTPHARM", "TRENT", "TVSMOTOR", "UBL", "VOLTAS", "ZEEL", "PIIND", "OFSS", "PETRONET",
        "ADANIGREEN", "ADANITRANS", "ACC", "ALKEM", "COLPAL", "ICICIGI", "LUPIN", "NMDC", "SHRIRAMFIN", "ZYDUSLIFE", "RELIANCE",
    ]

    return nifty50
