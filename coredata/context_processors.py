# context_processors.py or views.py
from coredata.utils.nifty_cache import get_today_nifty_pe

def coredata_context(request):

    print('test')
    tt = get_today_nifty_pe()
    print(tt)
    print('end test')
    return {
        "nifty_pe": get_today_nifty_pe()
    }
