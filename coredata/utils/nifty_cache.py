# utils/nifty_cache.py
from datetime import date
from coredata.utils.pe_scraper import fetch_nifty_pe
from coredata.models import Config

def get_today_nifty_pe():
    today = date.today()
    obj = Config.objects.filter(fetched_at=today).first()
    pe_ratio = []

    if obj:
        pe = float(obj.value)
        pe_ratio.append(pe)
    else:
        pe = fetch_nifty_pe()
        if pe:
            Config.objects.create(attribute='PE', value=pe, fetched_at=today)
            pe_ratio.append(pe)

    if pe > 32:
        pe_ratio.append('Take Vacation :)')
    elif pe > 25 and pe < 30 :
        pe_ratio.append('Do Research for good fundamental stocks!')
    elif pe > 23 and pe < 25:
        pe_ratio.append('Short list stocks for investing !')
    elif pe > 20 and pe < 23:
        pe_ratio.append('Start investing on reversal stocks!')
    elif pe > 17 and pe < 20:
        pe_ratio.append('Increase investing')
    elif pe > 15 and pe < 17:
        pe_ratio.append('Break your all saving, FD, MF and investing in stocks')
    else:
        pe_ratio.append('Beg, Barrow, and investing in stocks')

    return pe_ratio


def get_nifty_ticker():
    nifty_50 = "https://www.screener.in/company/NIFTY/?sort=name&order=asc&limit=50"
    nxt_nifty50 = "https://www.screener.in/company/NIFTYJR/?sort=name&order=asc&limit=50"
    fetch_nifty_tickers(nifty_50, name='50')
