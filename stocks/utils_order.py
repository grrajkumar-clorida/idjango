"""Legacy Breeze experiment. Do not place orders from here — use the Review desk."""
from django.conf import settings


def fetch_stock_data(symbol):
    raise RuntimeError(
        "stocks.utils_order is disabled. Use /stocks/review/ (paper) or OrderExecutor. "
        "Rotate any Breeze keys that were previously hardcoded in this file."
    )


# Never store live Breeze credentials in source. Read from idirect/.env only.
BREEZE_API_KEY = getattr(settings, "BREEZE_API_KEY", "")
BREEZE_SECRET_KEY = getattr(settings, "BREEZE_SECRET_KEY", "")
BREEZE_SESSION_KEY = getattr(settings, "BREEZE_SESSION", "")
