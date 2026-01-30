"""
Market Hours and Holiday Detection

Uses Polygon.io API to check if US stock market is open.
Prevents unnecessary API calls and respects market schedule.
"""
from datetime import datetime, time, timedelta
from typing import Optional, Dict
import pytz
import logging
import os

logger = logging.getLogger(__name__)

# US Eastern Time Zone (market timezone)
US_EASTERN = pytz.timezone('US/Eastern')

# Default US Market Hours (Eastern Time) - used as fallback
MARKET_OPEN_TIME = time(9, 30)  # 9:30 AM ET
MARKET_CLOSE_TIME = time(16, 0)  # 4:00 PM ET
EARLY_CLOSE_TIME = time(13, 0)  # 1:00 PM ET

# Pre-market and after-hours (for future use)
PRE_MARKET_OPEN = time(4, 0)   # 4:00 AM ET
AFTER_HOURS_CLOSE = time(20, 0)  # 8:00 PM ET

# Cache for market holidays (refreshed daily)
_HOLIDAYS_CACHE = None
_CACHE_TIMESTAMP = None
_CACHE_DURATION = timedelta(hours=24)


def get_current_et_time() -> datetime:
    """
    Get current time in US Eastern timezone

    Returns:
        datetime: Current time in ET
    """
    return datetime.now(US_EASTERN)


def _get_polygon_client():
    """Get Polygon client instance (lazy import to avoid circular deps)"""
    from app.services.polygon_fetcher import PolygonFetcher
    return PolygonFetcher()


def _fetch_market_status_from_polygon() -> Optional[Dict]:
    """
    Fetch current market status directly from Polygon API

    Returns:
        Dict with market status or None if error
    """
    try:
        client = _get_polygon_client()
        status = client.get_market_status()
        return status
    except Exception as e:
        logger.error(f"Error fetching market status from Polygon: {e}")
        return None


def _fetch_market_holidays() -> Dict[str, bool]:
    """
    Fetch market holidays from Polygon.io API

    Returns:
        Dict mapping date strings (YYYY-MM-DD) to True for holidays
    """
    global _HOLIDAYS_CACHE, _CACHE_TIMESTAMP

    # Check cache
    now = datetime.now()
    if _HOLIDAYS_CACHE and _CACHE_TIMESTAMP:
        if now - _CACHE_TIMESTAMP < _CACHE_DURATION:
            logger.debug("Using cached market holidays")
            return _HOLIDAYS_CACHE

    try:
        logger.info("Fetching market holidays from Polygon.io")
        client = _get_polygon_client()
        holidays = client.get_market_holidays()

        if holidays:
            # Convert to dict for fast lookup
            _HOLIDAYS_CACHE = {h['date']: True for h in holidays if h.get('date')}
            _CACHE_TIMESTAMP = now
            logger.info(f"✅ Cached {len(_HOLIDAYS_CACHE)} market holidays")
            return _HOLIDAYS_CACHE
        else:
            logger.warning("No holidays returned from Polygon, using fallback")
            return {}

    except Exception as e:
        logger.error(f"Error fetching market holidays from Polygon: {e}")
        logger.warning("Falling back to empty holidays list")
        return {}


def is_market_holiday(check_date: Optional[datetime] = None) -> bool:
    """
    Check if given date is a US market holiday using Polygon.io API

    Args:
        check_date: Date to check (default: today in ET)

    Returns:
        bool: True if market holiday, False otherwise
    """
    if check_date is None:
        check_date = get_current_et_time()

    # Convert to ET if not already
    if check_date.tzinfo != US_EASTERN:
        check_date = check_date.astimezone(US_EASTERN)

    # Format date as YYYY-MM-DD
    date_str = check_date.strftime('%Y-%m-%d')

    # Fetch holidays (uses cache if available)
    holidays = _fetch_market_holidays()

    return date_str in holidays


def is_weekend(check_date: Optional[datetime] = None) -> bool:
    """
    Check if given date is a weekend (Saturday/Sunday)

    Args:
        check_date: Date to check (default: today in ET)

    Returns:
        bool: True if weekend, False otherwise
    """
    if check_date is None:
        check_date = get_current_et_time()

    # Convert to ET if not already
    if check_date.tzinfo != US_EASTERN:
        check_date = check_date.astimezone(US_EASTERN)

    # Monday=0, Sunday=6
    return check_date.weekday() in [5, 6]  # Saturday or Sunday


def is_early_close_day(check_date: Optional[datetime] = None) -> bool:
    """
    Check if given date is an early close day (market closes at 1:00 PM ET)

    Note: Polygon.io holidays API includes early close information.
    This function checks the Polygon data for early close status.

    Args:
        check_date: Date to check (default: today in ET)

    Returns:
        bool: True if early close day, False otherwise
    """
    if check_date is None:
        check_date = get_current_et_time()

    # Convert to ET if not already
    if check_date.tzinfo != US_EASTERN:
        check_date = check_date.astimezone(US_EASTERN)

    # Format date as YYYY-MM-DD
    date_str = check_date.strftime('%Y-%m-%d')

    # Check Polygon holidays data for early close status
    try:
        client = _get_polygon_client()
        holidays = client.get_market_holidays()

        if holidays:
            for holiday in holidays:
                if holiday.get('date') == date_str:
                    # Check if it's an early close (status != 'closed')
                    status = holiday.get('status', '').lower()
                    return 'early' in status or status == 'early-close'
    except Exception as e:
        logger.debug(f"Could not check early close from Polygon: {e}")

    # Fallback: Common early close days (day before major holidays)
    # Black Friday (day after Thanksgiving), Christmas Eve, July 3rd
    month_day = (check_date.month, check_date.day)
    common_early_closes = [
        (7, 3),   # Day before Independence Day
        (11, 28), # Black Friday (approximate)
        (11, 29), # Black Friday (approximate)
        (12, 24), # Christmas Eve
    ]

    return month_day in common_early_closes


def get_market_close_time(check_date: Optional[datetime] = None) -> time:
    """
    Get market close time for given date (4:00 PM normal, 1:00 PM early close)

    Args:
        check_date: Date to check (default: today in ET)

    Returns:
        time: Market close time
    """
    if is_early_close_day(check_date):
        return EARLY_CLOSE_TIME
    return MARKET_CLOSE_TIME


def is_market_open(check_time: Optional[datetime] = None, include_extended: bool = False, use_polygon: bool = True) -> bool:
    """
    Check if US stock market is currently open

    Args:
        check_time: Time to check (default: current time in ET)
        include_extended: If True, includes pre-market and after-hours (default: False)
        use_polygon: If True, tries to fetch real-time status from Polygon (default: True)

    Returns:
        bool: True if market is open, False otherwise
    """
    if check_time is None:
        check_time = get_current_et_time()

    # Convert to ET if not already
    if check_time.tzinfo != US_EASTERN:
        check_time = check_time.astimezone(US_EASTERN)

    # Try to get real-time status from Polygon if checking current time
    if use_polygon and check_time is None or (datetime.now(US_EASTERN) - check_time).total_seconds() < 60:
        try:
            polygon_status = _fetch_market_status_from_polygon()
            if polygon_status and 'exchanges' in polygon_status:
                # Check NYSE status (primary US stock exchange)
                nyse = polygon_status.get('exchanges', {}).get('nyse', None)
                nasdaq = polygon_status.get('exchanges', {}).get('nasdaq', None)

                if nyse or nasdaq:
                    # If either exchange reports open, market is open
                    return nyse == 'open' or nasdaq == 'open'
        except Exception as e:
            logger.debug(f"Failed to get Polygon market status, using fallback: {e}")

    # Fallback to local time-based check
    # Check if weekend
    if is_weekend(check_time):
        return False

    # Check if holiday
    if is_market_holiday(check_time):
        return False

    current_time = check_time.time()

    if include_extended:
        # Pre-market: 4:00 AM - 9:30 AM ET
        # Regular: 9:30 AM - 4:00 PM ET (or 1:00 PM on early close days)
        # After-hours: 4:00 PM - 8:00 PM ET
        close_time = get_market_close_time(check_time)

        return (PRE_MARKET_OPEN <= current_time < MARKET_OPEN_TIME or
                MARKET_OPEN_TIME <= current_time < close_time or
                close_time <= current_time < AFTER_HOURS_CLOSE)
    else:
        # Regular market hours only: 9:30 AM - 4:00 PM ET (or 1:00 PM on early close)
        close_time = get_market_close_time(check_time)
        return MARKET_OPEN_TIME <= current_time < close_time


def should_fetch_data(priority: str = 'high') -> dict:
    """
    Determine if data fetching should proceed based on current market status

    Args:
        priority: Stock priority ('high', 'medium', 'low')

    Returns:
        dict: {
            'should_fetch': bool,
            'reason': str,
            'market_status': str,
            'current_time_et': str,
            'next_open': str (optional)
        }
    """
    now_et = get_current_et_time()
    current_time_str = now_et.strftime('%Y-%m-%d %H:%M:%S %Z')

    # Check if weekend
    if is_weekend(now_et):
        return {
            'should_fetch': False,
            'reason': 'Market closed - Weekend',
            'market_status': 'closed_weekend',
            'current_time_et': current_time_str,
            'next_open': 'Monday 9:30 AM ET'
        }

    # Check if holiday
    if is_market_holiday(now_et):
        return {
            'should_fetch': False,
            'reason': 'Market closed - Holiday',
            'market_status': 'closed_holiday',
            'current_time_et': current_time_str,
            'next_open': 'Next trading day 9:30 AM ET'
        }

    # Check if during market hours
    current_time = now_et.time()
    close_time = get_market_close_time(now_et)

    if MARKET_OPEN_TIME <= current_time < close_time:
        # Market is open
        if priority == 'high':
            # High priority: Fetch during market hours
            return {
                'should_fetch': True,
                'reason': 'Market open - High priority fetch',
                'market_status': 'open',
                'current_time_et': current_time_str
            }
        else:
            # Medium/low priority: Can wait until market close or scheduled time
            return {
                'should_fetch': True,
                'reason': f'{priority.capitalize()} priority fetch - Market open',
                'market_status': 'open',
                'current_time_et': current_time_str
            }
    elif current_time < MARKET_OPEN_TIME:
        # Before market open
        return {
            'should_fetch': False,
            'reason': f'Market not yet open (opens at {MARKET_OPEN_TIME.strftime("%H:%M")} ET)',
            'market_status': 'pre_market',
            'current_time_et': current_time_str,
            'next_open': f'Today {MARKET_OPEN_TIME.strftime("%H:%M")} ET'
        }
    else:
        # After market close
        # Allow fetching after market close for end-of-day data
        return {
            'should_fetch': True,
            'reason': 'Market closed - Fetching end-of-day data',
            'market_status': 'after_hours',
            'current_time_et': current_time_str
        }


def get_market_status_info() -> dict:
    """
    Get comprehensive market status information from Polygon.io

    Returns:
        dict: Market status details including real-time exchange status
    """
    now_et = get_current_et_time()

    # Try to get real-time status from Polygon
    polygon_status = _fetch_market_status_from_polygon()
    polygon_data = {}

    if polygon_status:
        # Convert exchanges object to dict for JSON serialization
        exchanges = polygon_status.get('exchanges', {})
        if hasattr(exchanges, '__dict__'):
            # It's a Polygon object, convert to dict
            exchanges_dict = {
                'nyse': getattr(exchanges, 'nyse', None),
                'nasdaq': getattr(exchanges, 'nasdaq', None),
                'otc': getattr(exchanges, 'otc', None)
            }
        elif isinstance(exchanges, dict):
            exchanges_dict = exchanges
        else:
            exchanges_dict = {}

        polygon_data = {
            'exchanges': exchanges_dict,
            'server_time': polygon_status.get('serverTime', None),
            'early_hours': polygon_status.get('early_hours', False),
            'after_hours': polygon_status.get('after_hours', False)
        }

    # Calculate status using our logic (with Polygon integration)
    is_open = is_market_open(now_et, use_polygon=True)
    is_holiday = is_market_holiday(now_et)
    is_weekend_day = is_weekend(now_et)
    is_early_close = is_early_close_day(now_et)

    status = 'open' if is_open else 'closed'

    if is_weekend_day:
        status_detail = 'Weekend'
    elif is_holiday:
        status_detail = 'Holiday'
    elif is_open:
        if is_early_close:
            status_detail = f'Open (early close at {EARLY_CLOSE_TIME.strftime("%H:%M")} ET)'
        else:
            status_detail = 'Regular Trading Hours'
    else:
        current_time = now_et.time()
        if current_time < MARKET_OPEN_TIME:
            status_detail = 'Before Market Open'
        else:
            status_detail = 'After Market Close'

    result = {
        'status': status,
        'is_open': is_open,
        'is_holiday': is_holiday,
        'is_weekend': is_weekend_day,
        'is_early_close': is_early_close,
        'status_detail': status_detail,
        'current_time_et': now_et.strftime('%Y-%m-%d %H:%M:%S %Z'),
        'market_open_time': MARKET_OPEN_TIME.strftime('%H:%M'),
        'market_close_time': get_market_close_time(now_et).strftime('%H:%M')
    }

    # Add Polygon real-time data if available
    if polygon_data:
        result['polygon'] = polygon_data

    return result
