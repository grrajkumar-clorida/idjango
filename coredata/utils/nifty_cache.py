# utils/nifty_cache.py
import logging
from datetime import date

from coredata.models import Config
from coredata.utils.pe_scraper import fetch_nifty_pe

logger = logging.getLogger(__name__)


def get_today_nifty_pe():
    today = date.today()
    obj = Config.objects.filter(fetched_at=today).first()
    pe_ratio = []
    pe = None

    if obj:
        try:
            pe = float(obj.value)
        except (TypeError, ValueError):
            pe = None
    else:
        try:
            pe = fetch_nifty_pe()
        except Exception:
            logger.exception("fetch_nifty_pe failed")
            pe = None
        if pe:
            Config.objects.create(attribute="PE", value=pe, fetched_at=today)

    if pe is None:
        return ["N/A", "PE unavailable"]

    pe_ratio.append(pe)

    if pe > 32:
        pe_ratio.append("Take Vacation :)")
    elif 25 < pe < 30:
        pe_ratio.append("Do Research for good fundamental stocks!")
    elif 23 < pe < 25:
        pe_ratio.append("Short list stocks for investing !")
    elif 20 < pe < 23:
        pe_ratio.append("Start investing on reversal stocks!")
    elif 17 < pe < 20:
        pe_ratio.append("Increase investing")
    elif 15 < pe < 17:
        pe_ratio.append("Break your all saving, FD, MF and investing in stocks")
    else:
        pe_ratio.append("Beg, Barrow, and investing in stocks")

    return pe_ratio


def get_nifty_ticker():
    from coredata.utils.pe_scraper import fetch_nifty_tickers

    nifty_50 = "https://www.screener.in/company/NIFTY/?sort=name&order=asc&limit=50"
    fetch_nifty_tickers(nifty_50, name="50")
