"""
Timeframe definitions for multi-timeframe support
"""
from enum import Enum
from typing import Tuple


class Timeframe(str, Enum):
    """Supported timeframes for OHLCV data"""

    # Intraday
    ONE_MINUTE = "1m"
    FIVE_MINUTE = "5m"
    FIFTEEN_MINUTE = "15m"
    THIRTY_MINUTE = "30m"
    ONE_HOUR = "1h"
    TWO_HOUR = "2h"
    FOUR_HOUR = "4h"

    # Daily and above
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1mo"

    @classmethod
    def is_intraday(cls, timeframe: str) -> bool:
        """Check if timeframe is intraday (< 1 day)"""
        intraday_tfs = [
            cls.ONE_MINUTE, cls.FIVE_MINUTE, cls.FIFTEEN_MINUTE,
            cls.THIRTY_MINUTE, cls.ONE_HOUR, cls.TWO_HOUR, cls.FOUR_HOUR
        ]
        return timeframe in [tf.value for tf in intraday_tfs]

    @classmethod
    def to_polygon_params(cls, timeframe: str) -> Tuple[int, str]:
        """
        Convert timeframe to Polygon.io API parameters

        Args:
            timeframe: Timeframe string (e.g., '1h', '1d')

        Returns:
            Tuple of (multiplier, timespan) for Polygon API
        """
        timeframe_map = {
            cls.ONE_MINUTE.value: (1, 'minute'),
            cls.FIVE_MINUTE.value: (5, 'minute'),
            cls.FIFTEEN_MINUTE.value: (15, 'minute'),
            cls.THIRTY_MINUTE.value: (30, 'minute'),
            cls.ONE_HOUR.value: (1, 'hour'),
            cls.TWO_HOUR.value: (2, 'hour'),
            cls.FOUR_HOUR.value: (4, 'hour'),
            cls.ONE_DAY.value: (1, 'day'),
            cls.ONE_WEEK.value: (1, 'week'),
            cls.ONE_MONTH.value: (1, 'month'),
        }
        return timeframe_map.get(timeframe, (1, 'day'))

    @classmethod
    def get_default_lookback(cls, timeframe: str) -> int:
        """
        Get recommended lookback period (in days) for each timeframe

        Args:
            timeframe: Timeframe string

        Returns:
            Number of days to fetch for this timeframe
        """
        lookback_map = {
            cls.ONE_MINUTE.value: 7,      # 1 week for 1m bars
            cls.FIVE_MINUTE.value: 14,    # 2 weeks
            cls.FIFTEEN_MINUTE.value: 30, # 1 month
            cls.THIRTY_MINUTE.value: 60,  # 2 months
            cls.ONE_HOUR.value: 90,       # 3 months
            cls.TWO_HOUR.value: 180,      # 6 months
            cls.FOUR_HOUR.value: 365,     # 1 year
            cls.ONE_DAY.value: 1825,      # 5 years
            cls.ONE_WEEK.value: 3650,     # 10 years
            cls.ONE_MONTH.value: 7300,    # 20 years
        }
        return lookback_map.get(timeframe, 365)

    @classmethod
    def get_all_values(cls) -> list:
        """Get list of all timeframe values"""
        return [tf.value for tf in cls]

    @classmethod
    def get_display_name(cls, timeframe: str) -> str:
        """
        Get human-readable display name

        Args:
            timeframe: Timeframe string

        Returns:
            Display name (e.g., '1 Hour', '4 Hours', '1 Day')
        """
        display_map = {
            cls.ONE_MINUTE.value: '1 Minute',
            cls.FIVE_MINUTE.value: '5 Minutes',
            cls.FIFTEEN_MINUTE.value: '15 Minutes',
            cls.THIRTY_MINUTE.value: '30 Minutes',
            cls.ONE_HOUR.value: '1 Hour',
            cls.TWO_HOUR.value: '2 Hours',
            cls.FOUR_HOUR.value: '4 Hours',
            cls.ONE_DAY.value: '1 Day',
            cls.ONE_WEEK.value: '1 Week',
            cls.ONE_MONTH.value: '1 Month',
        }
        return display_map.get(timeframe, timeframe)

    @classmethod
    def get_sorting_order(cls, timeframe: str) -> int:
        """
        Get sorting order for timeframes (smallest to largest)

        Returns:
            Integer for sorting (lower = shorter timeframe)
        """
        order_map = {
            cls.ONE_MINUTE.value: 1,
            cls.FIVE_MINUTE.value: 2,
            cls.FIFTEEN_MINUTE.value: 3,
            cls.THIRTY_MINUTE.value: 4,
            cls.ONE_HOUR.value: 5,
            cls.TWO_HOUR.value: 6,
            cls.FOUR_HOUR.value: 7,
            cls.ONE_DAY.value: 8,
            cls.ONE_WEEK.value: 9,
            cls.ONE_MONTH.value: 10,
        }
        return order_map.get(timeframe, 999)
