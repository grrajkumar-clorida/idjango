# context_processors.py or views.py
from coredata.utils.nifty_cache import get_today_nifty_pe

def coredata_context(request):

    nifty_pe = get_today_nifty_pe()    
    print(f"Today's PE: {nifty_pe}")
    return {
        "nifty_pe": get_today_nifty_pe()
    }
