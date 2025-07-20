import gspread
import requests
from django.conf import settings
from django.core.mail import send_mail
from data.models import Stocks50MA
from django.conf import settings
from datetime import datetime

def safe_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.00

def date_format(date):
    cmp_date_str = date.strip()
    try:
        cmp_date = datetime.strptime(cmp_date_str, "%Y-%m-%d").date()
    except ValueError:
        cmp_date = None  # fallback

    # Return
    date
    return cmp_date