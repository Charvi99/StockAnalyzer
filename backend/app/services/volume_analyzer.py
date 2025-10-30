"""
Volume Analysis Service

Provides volume-based pattern validation and confirmation:
- VWAP (Volume-Weighted Average Price)
- Volume profile analysis
- Breakout volume confirmation
- Volume-based confidence adjustments
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class VolumeAnalyzer:
    """
    Volume analysis for pattern validation

    Key metrics:
    - VWAP: Dynamic support/resistance
    - Volume ratio: Current vs average
    - Volume profile: High-volume price levels
    - Breakout confirmation: Volume surge validation
    """

    def __init__(self, df: pd.DataFrame):
        """
        Initialize volume analyzer

        Args:
            df: DataFrame with OHLCV data (index = timestamp or 'timestamp' column)
        """
        self.df = df.copy()

        # Ensure timestamp is the index and is datetime
        if 'timestamp' in self.df.columns:
            self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
            self.df.set_index('timestamp', inplace=True)

        # Ensure index is datetime
        if not isinstance(self.df.index, pd.DatetimeIndex):
            self.df.index = pd.to_datetime(self.df.index)

        # Ensure we have volume data
        if 'volume' not in self.df.columns:
            raise ValueError("DataFrame must contain 'volume' column")

        # Calculate VWAP
        self._calculate_vwap()

        # Calculate volume statistics
        self._calculate_volume_stats()

    def _calculate_vwap(self):
        """
        Calculate Volume-Weighted Average Price

        VWAP = Cumulative(Price * Volume) / Cumulative(Volume)

        VWAP is a dynamic support/resistance level:
        - Price above VWAP = bullish
        - Price below VWAP = bearish
        """
        # Typical price (HL/2 or HLC/3)
        self.df['typical_price'] = (
            self.df['high'] +
            self.df['low'] +
            self.df['close']
        ) / 3

        # Calculate VWAP
        self.df['vwap'] = (
            (self.df['typical_price'] * self.df['volume']).cumsum() /
            self.df['volume'].cumsum()
        )

        # Calculate distance from VWAP
        self.df['vwap_distance'] = (
            (self.df['close'] - self.df['vwap']) /
            self.df['vwap']
        ) * 100  # Percentage distance

        logger.debug(f"VWAP calculated: range {self.df['vwap'].min():.2f} - {self.df['vwap'].max():.2f}")

    def _calculate_volume_stats(self):
        """
        Calculate volume statistics

        - Average volume (20-day, 50-day)
        - Volume ratio (current / average)
        - Volume percentile
        """
        # 20-day average volume
        self.df['volume_avg_20'] = self.df['volume'].rolling(window=20, min_periods=1).mean()

        # 50-day average volume
        self.df['volume_avg_50'] = self.df['volume'].rolling(window=50, min_periods=1).mean()

        # Volume ratio (current / 20-day average)
        self.df['volume_ratio'] = self.df['volume'] / self.df['volume_avg_20']

        # Volume percentile (0-100)
        self.df['volume_percentile'] = self.df['volume'].rolling(
            window=100, min_periods=20
        ).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100)

        logger.debug(f"Volume stats calculated: avg 20d = {self.df['volume_avg_20'].iloc[-1]:,.0f}")

    def get_vwap_at_date(self, date: datetime) -> Optional[float]:
        """
        Get VWAP value at specific date

        Args:
            date: Date to get VWAP

        Returns:
            VWAP value or None
        """
        try:
            idx = self.df.index.get_loc(date, method='nearest')
            return float(self.df['vwap'].iloc[idx])
        except KeyError:
            return None

    def get_volume_ratio_at_date(self, date: datetime) -> Optional[float]:
        """
        Get volume ratio at specific date

        Args:
            date: Date to check

        Returns:
            Volume ratio (current / 20-day avg) or None
        """
        try:
            idx = self.df.index.get_loc(date, method='nearest')
            return float(self.df['volume_ratio'].iloc[idx])
        except KeyError:
            return None

    def validate_breakout(
        self,
        breakout_date: datetime,
        min_volume_increase: float = 1.5
    ) -> Dict:
        """
        Validate breakout with volume confirmation

        Args:
            breakout_date: Date of breakout
            min_volume_increase: Minimum volume increase required (default 1.5x = 50%)

        Returns:
            Dictionary with validation results
        """
        try:
            idx = self.df.index.get_loc(breakout_date, method='nearest')

            breakout_volume = self.df['volume'].iloc[idx]
            avg_volume = self.df['volume_avg_20'].iloc[idx]
            volume_ratio = breakout_volume / avg_volume

            # Determine validation status
            is_valid = volume_ratio >= min_volume_increase

            # Calculate confidence adjustment
            if volume_ratio >= 2.0:
                # Very strong volume (2x+)
                confidence_multiplier = 1.3
                quality = 'excellent'
            elif volume_ratio >= min_volume_increase:
                # Good volume (1.5x+)
                confidence_multiplier = 1.15
                quality = 'good'
            elif volume_ratio >= 1.0:
                # Average volume
                confidence_multiplier = 1.0
                quality = 'average'
            else:
                # Low volume - red flag
                confidence_multiplier = 0.7
                quality = 'weak'

            return {
                'is_valid': is_valid,
                'volume_ratio': float(volume_ratio),
                'breakout_volume': int(breakout_volume),
                'avg_volume': int(avg_volume),
                'confidence_multiplier': confidence_multiplier,
                'quality': quality,
                'message': self._get_volume_message(volume_ratio, quality)
            }

        except Exception as e:
            logger.error(f"Error validating breakout: {e}")
            return {
                'is_valid': False,
                'volume_ratio': 0.0,
                'confidence_multiplier': 1.0,
                'quality': 'unknown',
                'message': 'Volume data unavailable'
            }

    def _get_volume_message(self, ratio: float, quality: str) -> str:
        """Generate human-readable volume message"""
        if quality == 'excellent':
            return f"Strong breakout with {ratio:.1f}x average volume"
        elif quality == 'good':
            return f"Valid breakout with {ratio:.1f}x average volume"
        elif quality == 'average':
            return f"Moderate volume ({ratio:.1f}x average)"
        elif quality == 'weak':
            return f"Low volume breakout ({ratio:.1f}x average) - caution"
        else:
            return "Volume data unavailable"

    def calculate_volume_score(
        self,
        start_date: datetime,
        end_date: datetime,
        pattern_type: str = 'breakout'
    ) -> Dict:
        """
        Calculate comprehensive volume score for pattern

        Args:
            start_date: Pattern start date
            end_date: Pattern end date (breakout date)
            pattern_type: Type of pattern ('breakout', 'reversal', 'continuation')

        Returns:
            Dictionary with volume analysis
        """
        try:
            # Convert dates to pandas timestamps to match index
            start_date = pd.Timestamp(start_date)
            end_date = pd.Timestamp(end_date)

            # Remove timezone info if present (to match index)
            if start_date.tz is not None:
                start_date = start_date.tz_localize(None)
            if end_date.tz is not None:
                end_date = end_date.tz_localize(None)

            # Get date range indices
            mask = (self.df.index >= start_date) & (self.df.index <= end_date)
            pattern_df = self.df[mask]

            if len(pattern_df) < 2:
                return self._empty_volume_score()

            # Volume metrics
            avg_volume = pattern_df['volume'].mean()
            end_volume = pattern_df['volume'].iloc[-1]
            max_volume = pattern_df['volume'].max()

            # Calculate volume trend
            volume_trend = self._calculate_volume_trend(pattern_df)

            # Volume at breakout/completion
            end_idx = self.df.index.get_loc(end_date, method='nearest')
            breakout_volume_ratio = float(self.df['volume_ratio'].iloc[end_idx])

            # VWAP position at completion
            end_price = float(self.df['close'].iloc[end_idx])
            end_vwap = float(self.df['vwap'].iloc[end_idx])
            vwap_position = 'above' if end_price > end_vwap else 'below'
            vwap_distance = ((end_price - end_vwap) / end_vwap) * 100

            # Calculate overall volume score (0-1)
            volume_score = self._calculate_overall_score(
                volume_ratio=breakout_volume_ratio,
                volume_trend=volume_trend,
                pattern_type=pattern_type
            )

            # Confidence multiplier
            confidence_multiplier = 1.0 + (volume_score - 0.5) * 0.6  # Range: 0.7 - 1.3
            confidence_multiplier = max(0.7, min(1.3, confidence_multiplier))

            return {
                'volume_score': float(volume_score),
                'confidence_multiplier': float(confidence_multiplier),
                'avg_volume': int(avg_volume),
                'end_volume': int(end_volume),
                'volume_ratio': float(breakout_volume_ratio),
                'volume_trend': volume_trend,
                'max_volume': int(max_volume),
                'vwap_position': vwap_position,
                'vwap_distance_pct': float(vwap_distance),
                'quality': self._get_quality_label(volume_score)
            }

        except Exception as e:
            logger.error(f"Error calculating volume score: {e}")
            return self._empty_volume_score()

    def _calculate_volume_trend(self, df: pd.DataFrame) -> str:
        """
        Calculate volume trend (increasing/decreasing/stable)

        Args:
            df: DataFrame subset

        Returns:
            Trend label
        """
        if len(df) < 5:
            return 'stable'

        # Split into first half and second half
        mid = len(df) // 2
        first_half_avg = df['volume'].iloc[:mid].mean()
        second_half_avg = df['volume'].iloc[mid:].mean()

        ratio = second_half_avg / first_half_avg

        if ratio >= 1.2:
            return 'increasing'
        elif ratio <= 0.8:
            return 'decreasing'
        else:
            return 'stable'

    def _calculate_overall_score(
        self,
        volume_ratio: float,
        volume_trend: str,
        pattern_type: str
    ) -> float:
        """
        Calculate overall volume score (0-1)

        Higher is better
        """
        score = 0.5  # Start at neutral

        # Volume ratio contribution (0-0.4)
        if volume_ratio >= 2.0:
            score += 0.4
        elif volume_ratio >= 1.5:
            score += 0.3
        elif volume_ratio >= 1.0:
            score += 0.1
        else:
            score -= 0.2

        # Volume trend contribution (0-0.2)
        if pattern_type == 'breakout':
            # For breakouts, increasing volume is positive
            if volume_trend == 'increasing':
                score += 0.2
            elif volume_trend == 'decreasing':
                score -= 0.1
        elif pattern_type == 'reversal':
            # For reversals, volume spike at end is positive
            if volume_ratio >= 1.5:
                score += 0.2

        # Clamp to 0-1
        return max(0.0, min(1.0, score))

    def _get_quality_label(self, score: float) -> str:
        """Get quality label from score"""
        if score >= 0.8:
            return 'excellent'
        elif score >= 0.6:
            return 'good'
        elif score >= 0.4:
            return 'average'
        else:
            return 'weak'

    def _empty_volume_score(self) -> Dict:
        """Return empty volume score"""
        return {
            'volume_score': 0.5,
            'confidence_multiplier': 1.0,
            'avg_volume': 0,
            'end_volume': 0,
            'volume_ratio': 1.0,
            'volume_trend': 'unknown',
            'max_volume': 0,
            'vwap_position': 'unknown',
            'vwap_distance_pct': 0.0,
            'quality': 'unknown'
        }

    def get_volume_profile(
        self,
        start_date: datetime,
        end_date: datetime,
        num_bins: int = 20
    ) -> Dict:
        """
        Calculate volume profile (volume distribution by price level)

        Identifies:
        - Point of Control (POC): Price level with highest volume
        - Value Area (VA): Price range containing 70% of volume
        - High/Low volume nodes

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period
            num_bins: Number of price bins

        Returns:
            Volume profile data
        """
        try:
            # Convert dates to pandas timestamps to match index
            start_date = pd.Timestamp(start_date)
            end_date = pd.Timestamp(end_date)

            # Remove timezone info if present (to match index)
            if start_date.tz is not None:
                start_date = start_date.tz_localize(None)
            if end_date.tz is not None:
                end_date = end_date.tz_localize(None)

            # Get date range
            mask = (self.df.index >= start_date) & (self.df.index <= end_date)
            period_df = self.df[mask]

            if len(period_df) < 2:
                return {'error': 'Insufficient data'}

            # Create price bins
            price_min = period_df['low'].min()
            price_max = period_df['high'].max()
            bins = np.linspace(price_min, price_max, num_bins + 1)

            # Assign volume to bins based on typical price
            volume_by_price = np.zeros(num_bins)

            for idx, row in period_df.iterrows():
                typical_price = (row['high'] + row['low'] + row['close']) / 3
                bin_idx = np.digitize(typical_price, bins) - 1
                bin_idx = max(0, min(num_bins - 1, bin_idx))
                volume_by_price[bin_idx] += row['volume']

            # Find Point of Control (highest volume bin)
            poc_idx = np.argmax(volume_by_price)
            poc_price = (bins[poc_idx] + bins[poc_idx + 1]) / 2

            # Calculate Value Area (70% of volume)
            total_volume = volume_by_price.sum()
            target_volume = total_volume * 0.70

            # Start from POC and expand outward
            va_volume = volume_by_price[poc_idx]
            va_low_idx = poc_idx
            va_high_idx = poc_idx

            while va_volume < target_volume:
                # Check which side to expand
                low_vol = volume_by_price[va_low_idx - 1] if va_low_idx > 0 else 0
                high_vol = volume_by_price[va_high_idx + 1] if va_high_idx < num_bins - 1 else 0

                if low_vol > high_vol and va_low_idx > 0:
                    va_low_idx -= 1
                    va_volume += low_vol
                elif va_high_idx < num_bins - 1:
                    va_high_idx += 1
                    va_volume += high_vol
                else:
                    break

            va_low = bins[va_low_idx]
            va_high = bins[va_high_idx + 1]

            return {
                'poc_price': float(poc_price),
                'value_area_low': float(va_low),
                'value_area_high': float(va_high),
                'price_range': (float(price_min), float(price_max)),
                'total_volume': int(total_volume),
                'value_area_volume_pct': float((va_volume / total_volume) * 100)
            }

        except Exception as e:
            logger.error(f"Error calculating volume profile: {e}")
            return {'error': str(e)}

    def is_price_at_high_volume_node(
        self,
        price: float,
        start_date: datetime,
        end_date: datetime,
        tolerance_pct: float = 2.0
    ) -> bool:
        """
        Check if price is near a high-volume node

        Args:
            price: Price to check
            start_date: Analysis start
            end_date: Analysis end
            tolerance_pct: Price tolerance (% of price)

        Returns:
            True if price is near high-volume area
        """
        profile = self.get_volume_profile(start_date, end_date)

        if 'error' in profile:
            return False

        # Check if price is near POC or within Value Area
        poc = profile['poc_price']
        va_low = profile['value_area_low']
        va_high = profile['value_area_high']

        tolerance = price * (tolerance_pct / 100)

        # Near POC
        if abs(price - poc) <= tolerance:
            return True

        # Within Value Area
        if va_low <= price <= va_high:
            return True

        return False
