# context_processors.py
import logging

from coredata.utils.nifty_cache import get_today_nifty_pe

logger = logging.getLogger(__name__)


def coredata_context(request):
    # Must never break page renders (Selenium/Chrome is optional on VPS).
    try:
        nifty_pe = get_today_nifty_pe()
    except Exception:
        logger.exception("nifty_pe context failed")
        nifty_pe = ["N/A", "PE unavailable"]
    return {"nifty_pe": nifty_pe}
