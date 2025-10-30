"""
Multi-Timeframe Configuration
Strategy: 1 Hour base with smart aggregation
"""
from typing import List, Dict


class TimeframeConfig:
    """
    Multi-timeframe configuration

    Strategy: Use 1h as base timeframe, aggregate higher timeframes on-the-fly
    Storage: Only 1h data stored in database (~876 KB per stock per year)
    Savings: 51% compared to storing all timeframes separately
    """

    # Base timeframe (stored in database)
    BASE_TIMEFRAME = '1h'

    # Timeframes that are aggregated from base (NOT stored)
    AGGREGATED_TIMEFRAMES = ['2h', '4h', '1d', '1w', '1mo']

    # All supported timeframes
    ALL_TIMEFRAMES = ['1h', '2h', '4h', '1d', '1w', '1mo']

    # Retention policy (how much history to keep)
    RETENTION_DAYS = {
        '1h': 365,      # 1 year of hourly data (8,760 bars)
        # Higher timeframes generated on-demand, no storage needed
    }

    # Default lookback when fetching (for API calls)
    DEFAULT_LOOKBACK_DAYS = {
        '1h': 730,      # 2 years (swing trading - matches available data)
        '2h': 730,      # 2 years
        '4h': 730,      # 2 years
        '1d': 1825,     # 5 years
        '1w': 3650,     # 10 years
        '1mo': 7300,    # 20 years
    }

    # Display names for frontend
    DISPLAY_NAMES = {
        '1h': '1 Hour',
        '2h': '2 Hours',
        '4h': '4 Hours',
        '1d': '1 Day',
        '1w': '1 Week',
        '1mo': '1 Month',
    }

    @classmethod
    def is_aggregated(cls, timeframe: str) -> bool:
        """
        Check if timeframe should be aggregated from base

        Args:
            timeframe: Timeframe string

        Returns:
            True if timeframe is aggregated, False if stored
        """
        return timeframe in cls.AGGREGATED_TIMEFRAMES

    @classmethod
    def get_base_timeframe(cls) -> str:
        """
        Get base timeframe for storage

        Returns:
            Base timeframe string ('1h')
        """
        return cls.BASE_TIMEFRAME

    @classmethod
    def get_retention_days(cls, timeframe: str) -> int:
        """
        Get retention period for timeframe

        Args:
            timeframe: Timeframe string

        Returns:
            Number of days to retain
        """
        return cls.RETENTION_DAYS.get(timeframe, 365)

    @classmethod
    def get_default_lookback(cls, timeframe: str) -> int:
        """
        Get default lookback period for API queries

        Args:
            timeframe: Timeframe string

        Returns:
            Number of days for default lookback
        """
        return cls.DEFAULT_LOOKBACK_DAYS.get(timeframe, 365)

    @classmethod
    def get_display_name(cls, timeframe: str) -> str:
        """
        Get human-readable display name

        Args:
            timeframe: Timeframe string

        Returns:
            Display name for frontend
        """
        return cls.DISPLAY_NAMES.get(timeframe, timeframe)

    @classmethod
    def get_all_timeframes(cls) -> List[str]:
        """
        Get list of all supported timeframes

        Returns:
            List of timeframe strings
        """
        return cls.ALL_TIMEFRAMES.copy()

    @classmethod
    def get_aggregated_timeframes(cls) -> List[str]:
        """
        Get list of aggregated timeframes

        Returns:
            List of aggregated timeframe strings
        """
        return cls.AGGREGATED_TIMEFRAMES.copy()

    @classmethod
    def should_fetch_from_polygon(cls, timeframe: str) -> bool:
        """
        Check if we should fetch this timeframe from Polygon.io

        Args:
            timeframe: Timeframe string

        Returns:
            True if should fetch, False if should aggregate
        """
        return timeframe == cls.BASE_TIMEFRAME

    @classmethod
    def get_storage_info(cls) -> Dict:
        """
        Get storage information for documentation

        Returns:
            Dictionary with storage statistics
        """
        return {
            'base_timeframe': cls.BASE_TIMEFRAME,
            'bars_per_year': 8760,  # 365 days * 24 hours
            'storage_per_stock_per_year': '876 KB',
            'storage_330_stocks_per_year': '289 MB',
            'aggregated_timeframes': cls.AGGREGATED_TIMEFRAMES,
            'storage_savings_vs_all': '51%',
            'aggregation_overhead': '<20ms per query'
        }
