"""
Timezone Utilities
Always use Indian timezone (Asia/Kolkata) for all datetime operations
"""
from datetime import datetime, timedelta
from django.utils import timezone
import pytz

# Indian timezone constant
INDIAN_TZ = pytz.timezone('Asia/Kolkata')


def now_indian():
    """
    Get current time in Indian timezone
    
    Returns:
        timezone-aware datetime in Indian timezone
    """
    return timezone.now().astimezone(INDIAN_TZ)


def today_indian():
    """
    Get today's date in Indian timezone
    
    Returns:
        date object for today in Indian timezone
    """
    return now_indian().date()


def make_indian_aware(dt):
    """
    Convert naive datetime to Indian timezone-aware datetime
    
    Args:
        dt: Naive datetime object
    
    Returns:
        Timezone-aware datetime in Indian timezone
    """
    if dt.tzinfo is None:
        return INDIAN_TZ.localize(dt)
    return dt.astimezone(INDIAN_TZ)


def get_day_start_end(date=None):
    """
    Get start and end of day in Indian timezone
    
    Args:
        date: Date object (defaults to today in Indian timezone)
    
    Returns:
        Tuple of (start_datetime, end_datetime) in Indian timezone
    """
    if date is None:
        date = today_indian()
    
    start_naive = datetime.combine(date, datetime.min.time())
    end_naive = datetime.combine(date, datetime.max.time())
    
    start = INDIAN_TZ.localize(start_naive)
    end = INDIAN_TZ.localize(end_naive)
    
    return start, end


def days_ago_indian(days):
    """
    Get datetime N days ago in Indian timezone
    
    Args:
        days: Number of days to go back
    
    Returns:
        Timezone-aware datetime in Indian timezone
    """
    return now_indian() - timedelta(days=days)
