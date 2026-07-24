"""
Candlestick Pattern Recognition Service
Implements 40 patterns from scratch (20 bullish, 20 bearish)
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from datetime import datetime


class CandlestickPatternDetector:
    """Detects candlestick patterns in OHLC data"""

    def __init__(self, df: pd.DataFrame):
        """
        Initialize with OHLC dataframe

        Args:
            df: DataFrame with columns: open, high, low, close, volume, timestamp
        """
        self.df = df.copy()
        self._calculate_candle_properties()
        # Cache numpy column views for the detect_* hot loops (built once). The
        # candle properties are already columns (see _calculate_candle_properties);
        # these are just O(1) array reads instead of per-bar ``df.iloc[i]`` Series
        # creation (the pandas overhead that dominated precompute). Output-identical.
        self._prepare_arrays()

    def _prepare_arrays(self) -> None:
        """Cache numpy column views for the detect_* hot loops. Output-identical to
        reading ``self.df``; just faster access (no per-bar Series creation)."""
        df = self.df
        self._open = df["open"].to_numpy()
        self._high = df["high"].to_numpy()
        self._low = df["low"].to_numpy()
        self._close = df["close"].to_numpy()
        self._volume = df["volume"].to_numpy()
        self._body = df["body"].to_numpy()
        self._upper_shadow = df["upper_shadow"].to_numpy()
        self._lower_shadow = df["lower_shadow"].to_numpy()
        self._total_range = df["total_range"].to_numpy()
        self._body_ratio = df["body_ratio"].to_numpy()
        self._is_bullish = df["is_bullish"].to_numpy()
        self._is_bearish = df["is_bearish"].to_numpy()
        self._volume_ratio = df["volume_ratio"].to_numpy()
        self._n = len(df)

    def _calculate_candle_properties(self):
        """Calculate additional candle properties for pattern detection"""
        df = self.df

        # Body and shadow calculations
        df['body'] = abs(df['close'] - df['open'])
        df['upper_shadow'] = df['high'] - df[['close', 'open']].max(axis=1)
        df['lower_shadow'] = df[['close', 'open']].min(axis=1) - df['low']
        df['total_range'] = df['high'] - df['low']

        # Candle direction
        df['is_bullish'] = df['close'] > df['open']
        df['is_bearish'] = df['close'] < df['open']

        # Body ratio to total range
        df['body_ratio'] = df['body'] / df['total_range'].replace(0, 1)

        # Average body size for reference (20-period rolling)
        df['avg_body'] = df['body'].rolling(window=20, min_periods=1).mean()

        # PHASE 1.1: Volume confirmation metrics
        # Average volume over 20 periods
        df['avg_volume'] = df['volume'].rolling(window=20, min_periods=1).mean()
        # Volume ratio (current vs average)
        df['volume_ratio'] = df['volume'] / df['avg_volume'].replace(0, 1)

    def _calculate_volume_confidence_boost(self, candle_idx: int, pattern_type: str) -> Tuple[float, str]:
        """
        Calculate volume-based confidence boost for a pattern

        Args:
            candle_idx: Index of the pattern candle
            pattern_type: 'bullish' or 'bearish'

        Returns:
            Tuple of (confidence_multiplier, volume_quality_label)
        """
        df = self.df
        candle = df.iloc[candle_idx]

        volume_ratio = candle['volume_ratio']

        # Volume quality tiers (matching your chart pattern system)
        if volume_ratio >= 2.0:
            # Excellent: 2x+ average volume, strong confirmation
            multiplier = 1.3
            quality = 'excellent'
        elif volume_ratio >= 1.5:
            # Good: 1.5-2x average volume, decent support
            multiplier = 1.15
            quality = 'good'
        elif volume_ratio >= 1.0:
            # Average: 1-1.5x average volume, moderate
            multiplier = 1.0
            quality = 'average'
        else:
            # Weak: <1x average volume, CAUTION
            multiplier = 0.7
            quality = 'weak'

        # For reversal patterns, check if next 1-2 candles have increasing volume
        # (confirming the reversal)
        if candle_idx < len(df) - 2:
            next_candle_volume = df.iloc[candle_idx + 1]['volume']
            if next_candle_volume > candle['volume'] * 1.1:
                # Follow-through volume increases confidence
                multiplier *= 1.05

        return multiplier, quality

    def detect_all_patterns(self) -> List[Dict]:
        """Detect all 40 candlestick patterns"""
        patterns = []

        # Bullish patterns
        patterns.extend(self.detect_hammer())
        patterns.extend(self.detect_inverted_hammer())
        patterns.extend(self.detect_bullish_marubozu())
        patterns.extend(self.detect_dragonfly_doji())
        patterns.extend(self.detect_bullish_engulfing())
        patterns.extend(self.detect_piercing_line())
        patterns.extend(self.detect_tweezer_bottom())
        patterns.extend(self.detect_bullish_kicker())
        patterns.extend(self.detect_bullish_harami())
        patterns.extend(self.detect_bullish_counterattack())
        patterns.extend(self.detect_morning_star())
        patterns.extend(self.detect_morning_doji_star())
        patterns.extend(self.detect_three_white_soldiers())
        patterns.extend(self.detect_three_inside_up())
        patterns.extend(self.detect_three_outside_up())
        patterns.extend(self.detect_bullish_abandoned_baby())
        patterns.extend(self.detect_rising_three_methods())
        patterns.extend(self.detect_upside_tasuki_gap())
        patterns.extend(self.detect_mat_hold())
        patterns.extend(self.detect_rising_window())

        # Bearish patterns
        patterns.extend(self.detect_hanging_man())
        patterns.extend(self.detect_shooting_star())
        patterns.extend(self.detect_bearish_marubozu())
        patterns.extend(self.detect_gravestone_doji())
        patterns.extend(self.detect_bearish_engulfing())
        patterns.extend(self.detect_dark_cloud_cover())
        patterns.extend(self.detect_tweezer_top())
        patterns.extend(self.detect_bearish_kicker())
        patterns.extend(self.detect_bearish_harami())
        patterns.extend(self.detect_bearish_counterattack())
        patterns.extend(self.detect_evening_star())
        patterns.extend(self.detect_evening_doji_star())
        patterns.extend(self.detect_three_black_crows())
        patterns.extend(self.detect_three_inside_down())
        patterns.extend(self.detect_three_outside_down())
        patterns.extend(self.detect_bearish_abandoned_baby())
        patterns.extend(self.detect_falling_three_methods())
        patterns.extend(self.detect_downside_tasuki_gap())
        patterns.extend(self.detect_on_neck_line())
        patterns.extend(self.detect_falling_window())

        return patterns

    # ==================== BULLISH PATTERNS ====================

    def detect_hammer(self) -> List[Dict]:
        """Hammer: Small body at top, long lower shadow (2x body), bullish reversal"""
        patterns = []
        df = self.df
        body = self._body; upper_shadow = self._upper_shadow; lower_shadow = self._lower_shadow
        total_range = self._total_range; close = self._close; n = self._n
        # dec3[i] True iff close[i-3:i] is monotonically non-increasing (i>=3) — the
        # "prior downtrend" guard. Vectorized once instead of a per-bar pandas slice.
        dec3 = np.zeros(n, dtype=bool)
        if n > 3:
            dec3[3:] = (close[:-3] >= close[1:-2]) & (close[1:-2] >= close[2:-1])

        for i in range(1, n):
            # Previous trend should be downward
            if not dec3[i]:
                continue

            # Hammer criteria (array reads — no per-bar Series creation).
            if not (lower_shadow[i] >= 2 * body[i] and
                    upper_shadow[i] <= 0.1 * total_range[i] and
                    body[i] < 0.3 * total_range[i] and
                    body[i] > 0):
                continue

            # Pattern qualifies — fetch the row for the (unchanged) dict assembly.
            candle = df.iloc[i]
            # PHASE 1.1: Apply volume confirmation
            base_confidence = 0.75
            volume_multiplier, volume_quality = self._calculate_volume_confidence_boost(i, 'bullish')
            final_confidence = min(base_confidence * volume_multiplier, 0.95)

            patterns.append({
                'pattern_name': 'Hammer',
                'pattern_type': 'bullish',
                'timestamp': candle['timestamp'],
                'confidence_score': final_confidence,
                'base_confidence': base_confidence,  # NEW: Original confidence
                'volume_quality': volume_quality,    # NEW: Volume quality label
                'volume_ratio': float(candle['volume_ratio']),  # NEW: Volume ratio
                'candle_data': self._get_candle_data(i, 1)
            })

        return patterns

    def detect_inverted_hammer(self) -> List[Dict]:
        """Inverted Hammer: Small body at bottom, long upper shadow, bullish reversal"""
        patterns = []
        df = self.df
        body = self._body; upper_shadow = self._upper_shadow; lower_shadow = self._lower_shadow
        total_range = self._total_range

        for i in range(3, self._n):
            if not (upper_shadow[i] >= 2 * body[i] and
                    lower_shadow[i] <= 0.1 * total_range[i] and
                    body[i] < 0.3 * total_range[i]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Inverted Hammer',
                'pattern_type': 'bullish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.70,
                'candle_data': self._get_candle_data(i, 1)
            })

        return patterns

    def detect_bullish_marubozu(self) -> List[Dict]:
        """Bullish Marubozu: Large bullish body, little/no shadows"""
        patterns = []
        df = self.df
        is_bullish = self._is_bullish; body_ratio = self._body_ratio
        upper_shadow = self._upper_shadow; lower_shadow = self._lower_shadow
        total_range = self._total_range

        for i in range(self._n):
            if not (bool(is_bullish[i]) and
                    body_ratio[i] >= 0.9 and
                    upper_shadow[i] <= 0.05 * total_range[i] and
                    lower_shadow[i] <= 0.05 * total_range[i]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Bullish Marubozu',
                'pattern_type': 'bullish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.80,
                'candle_data': self._get_candle_data(i, 1)
            })

        return patterns

    def detect_dragonfly_doji(self) -> List[Dict]:
        """Dragonfly Doji: No/tiny body, long lower shadow, no upper shadow"""
        patterns = []
        df = self.df
        body = self._body; upper_shadow = self._upper_shadow; lower_shadow = self._lower_shadow
        total_range = self._total_range

        for i in range(self._n):
            if not (body[i] <= 0.05 * total_range[i] and
                    lower_shadow[i] >= 0.7 * total_range[i] and
                    upper_shadow[i] <= 0.1 * total_range[i]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Dragonfly Doji',
                'pattern_type': 'bullish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.75,
                'candle_data': self._get_candle_data(i, 1)
            })

        return patterns

    def detect_bullish_engulfing(self) -> List[Dict]:
        """Bullish Engulfing: Large bullish candle engulfs previous bearish candle"""
        patterns = []
        df = self.df
        is_bearish = self._is_bearish; is_bullish = self._is_bullish
        open_ = self._open; close = self._close; body = self._body

        for i in range(1, self._n):
            if not (is_bearish[i - 1] and is_bullish[i] and
                    open_[i] < close[i - 1] and
                    close[i] > open_[i - 1] and
                    body[i] > body[i - 1]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Bullish Engulfing',
                'pattern_type': 'bullish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.85,
                'candle_data': self._get_candle_data(i, 2)
            })

        return patterns

    def detect_piercing_line(self) -> List[Dict]:
        """Piercing Line: Bullish candle closes above midpoint of previous bearish candle"""
        patterns = []
        df = self.df
        is_bearish = self._is_bearish; is_bullish = self._is_bullish
        open_ = self._open; close = self._close

        for i in range(1, self._n):
            prev_midpoint = (open_[i - 1] + close[i - 1]) / 2

            if not (is_bearish[i - 1] and is_bullish[i] and
                    open_[i] < close[i - 1] and
                    close[i] > prev_midpoint and
                    close[i] < open_[i - 1]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Piercing Line',
                'pattern_type': 'bullish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.80,
                'candle_data': self._get_candle_data(i, 2)
            })

        return patterns

    def detect_tweezer_bottom(self) -> List[Dict]:
        """Tweezer Bottom: Two candles with matching lows"""
        patterns = []
        df = self.df
        low = self._low; total_range = self._total_range
        is_bearish = self._is_bearish; is_bullish = self._is_bullish

        for i in range(1, self._n):
            low_diff = abs(low[i - 1] - low[i])
            avg_range = (total_range[i - 1] + total_range[i]) / 2

            if not (low_diff <= 0.02 * avg_range and
                    is_bearish[i - 1] and is_bullish[i]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Tweezer Bottom',
                'pattern_type': 'bullish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.70,
                'candle_data': self._get_candle_data(i, 2)
            })

        return patterns

    def detect_bullish_kicker(self) -> List[Dict]:
        """Bullish Kicker: Gap up from bearish to bullish candle"""
        patterns = []
        df = self.df
        is_bearish = self._is_bearish; is_bullish = self._is_bullish
        open_ = self._open; body_ratio = self._body_ratio

        for i in range(1, self._n):
            if not (is_bearish[i - 1] and is_bullish[i] and
                    open_[i] > open_[i - 1] and
                    body_ratio[i] >= 0.7 and
                    body_ratio[i - 1] >= 0.7):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Bullish Kicker',
                'pattern_type': 'bullish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.85,
                'candle_data': self._get_candle_data(i, 2)
            })

        return patterns

    def detect_bullish_harami(self) -> List[Dict]:
        """Bullish Harami: Small bullish candle within previous bearish candle"""
        patterns = []
        df = self.df
        is_bearish = self._is_bearish; is_bullish = self._is_bullish
        open_ = self._open; close = self._close; body = self._body

        for i in range(1, self._n):
            if not (is_bearish[i - 1] and is_bullish[i] and
                    open_[i] > close[i - 1] and
                    close[i] < open_[i - 1] and
                    body[i] < body[i - 1] * 0.5):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Bullish Harami',
                'pattern_type': 'bullish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.75,
                'candle_data': self._get_candle_data(i, 2)
            })

        return patterns

    def detect_bullish_counterattack(self) -> List[Dict]:
        """Bullish Counterattack: Bullish candle closes at same level as previous bearish"""
        patterns = []
        df = self.df
        is_bearish = self._is_bearish; is_bullish = self._is_bullish
        close = self._close; total_range = self._total_range; body = self._body

        for i in range(1, self._n):
            close_diff = abs(close[i - 1] - close[i])

            if not (is_bearish[i - 1] and is_bullish[i] and
                    close_diff <= 0.02 * total_range[i - 1] and
                    body[i] >= body[i - 1] * 0.8):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Bullish Counterattack',
                'pattern_type': 'bullish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.75,
                'candle_data': self._get_candle_data(i, 2)
            })

        return patterns

    def detect_morning_star(self) -> List[Dict]:
        """Morning Star: Bearish candle, small body, bullish candle"""
        patterns = []
        df = self.df
        is_bearish = self._is_bearish; is_bullish = self._is_bullish
        open_ = self._open; close = self._close; high = self._high; body = self._body

        for i in range(2, self._n):
            if not (is_bearish[i - 2] and
                    body[i - 1] < body[i - 2] * 0.3 and
                    is_bullish[i] and
                    close[i] > (open_[i - 2] + close[i - 2]) / 2 and
                    high[i - 1] < close[i - 2] and
                    high[i - 1] < open_[i]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Morning Star',
                'pattern_type': 'bullish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.90,
                'candle_data': self._get_candle_data(i, 3)
            })

        return patterns

    def detect_morning_doji_star(self) -> List[Dict]:
        """Morning Doji Star: Bearish candle, doji, bullish candle"""
        patterns = []
        df = self.df
        is_bearish = self._is_bearish; is_bullish = self._is_bullish
        open_ = self._open; close = self._close; body = self._body; total_range = self._total_range

        for i in range(2, self._n):
            is_doji = body[i - 1] <= 0.1 * total_range[i - 1]

            if not (is_bearish[i - 2] and is_doji and is_bullish[i] and
                    close[i] > (open_[i - 2] + close[i - 2]) / 2):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Morning Doji Star',
                'pattern_type': 'bullish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.85,
                'candle_data': self._get_candle_data(i, 3)
            })

        return patterns

    def detect_three_white_soldiers(self) -> List[Dict]:
        """Three White Soldiers: Three consecutive bullish candles with higher closes"""
        patterns = []
        df = self.df
        is_bullish = self._is_bullish; open_ = self._open; close = self._close

        for i in range(2, self._n):
            if not (is_bullish[i - 2] and is_bullish[i - 1] and is_bullish[i] and
                    close[i - 1] > close[i - 2] and
                    close[i] > close[i - 1] and
                    open_[i - 1] > open_[i - 2] and
                    open_[i - 1] < close[i - 2] and
                    open_[i] > open_[i - 1] and
                    open_[i] < close[i - 1]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Three White Soldiers',
                'pattern_type': 'bullish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.90,
                'candle_data': self._get_candle_data(i, 3)
            })

        return patterns

    def detect_three_inside_up(self) -> List[Dict]:
        """Three Inside Up: Bullish harami followed by bullish candle"""
        patterns = []
        df = self.df
        is_bearish = self._is_bearish; is_bullish = self._is_bullish
        open_ = self._open; close = self._close

        for i in range(2, self._n):
            # First two candles form bullish harami
            is_harami = (is_bearish[i - 2] and is_bullish[i - 1] and
                         open_[i - 1] > close[i - 2] and
                         close[i - 1] < open_[i - 2])

            if not (is_harami and is_bullish[i] and close[i] > close[i - 1]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Three Inside Up',
                'pattern_type': 'bullish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.85,
                'candle_data': self._get_candle_data(i, 3)
            })

        return patterns

    def detect_three_outside_up(self) -> List[Dict]:
        """Three Outside Up: Bullish engulfing followed by bullish candle"""
        patterns = []
        df = self.df
        is_bearish = self._is_bearish; is_bullish = self._is_bullish
        open_ = self._open; close = self._close

        for i in range(2, self._n):
            # First two candles form bullish engulfing
            is_engulfing = (is_bearish[i - 2] and is_bullish[i - 1] and
                            open_[i - 1] < close[i - 2] and
                            close[i - 1] > open_[i - 2])

            if not (is_engulfing and is_bullish[i] and close[i] > close[i - 1]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Three Outside Up',
                'pattern_type': 'bullish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.85,
                'candle_data': self._get_candle_data(i, 3)
            })

        return patterns

    def detect_bullish_abandoned_baby(self) -> List[Dict]:
        """Bullish Abandoned Baby: Doji gaps below bearish and above bullish candle"""
        patterns = []
        df = self.df
        is_bearish = self._is_bearish; is_bullish = self._is_bullish
        high = self._high; low = self._low; body = self._body; total_range = self._total_range

        for i in range(2, self._n):
            is_doji = body[i - 1] <= 0.1 * total_range[i - 1]
            gap_down = high[i - 1] < low[i - 2]
            gap_up = low[i - 1] > high[i]

            if not (is_bearish[i - 2] and is_doji and gap_down and
                    is_bullish[i] and gap_up):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Bullish Abandoned Baby',
                'pattern_type': 'bullish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.95,
                'candle_data': self._get_candle_data(i, 3)
            })

        return patterns

    def detect_rising_three_methods(self) -> List[Dict]:
        """Rising Three Methods: Bullish, 3 small bearish within range, bullish"""
        patterns = []
        df = self.df
        is_bullish = self._is_bullish; is_bearish = self._is_bearish
        high = self._high; low = self._low; close = self._close

        for i in range(4, self._n):
            # Middle 3 candles are small and bearish, within first candle range
            middle_in_range = (
                high[i - 3] <= high[i - 4] and low[i - 3] >= low[i - 4] and
                high[i - 2] <= high[i - 4] and low[i - 2] >= low[i - 4] and
                high[i - 1] <= high[i - 4] and low[i - 1] >= low[i - 4]
            )

            if not (is_bullish[i - 4] and is_bearish[i - 3] and is_bearish[i - 2] and
                    is_bearish[i - 1] and middle_in_range and
                    is_bullish[i] and close[i] > close[i - 4]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Rising Three Methods',
                'pattern_type': 'bullish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.80,
                'candle_data': self._get_candle_data(i, 5)
            })

        return patterns

    def detect_upside_tasuki_gap(self) -> List[Dict]:
        """Upside Tasuki Gap: Two bullish with gap, bearish partially fills gap"""
        patterns = []
        df = self.df
        is_bullish = self._is_bullish; is_bearish = self._is_bearish
        high = self._high; low = self._low; open_ = self._open; close = self._close

        for i in range(2, self._n):
            gap = low[i - 1] > high[i - 2]

            if not (is_bullish[i - 2] and is_bullish[i - 1] and gap and
                    is_bearish[i] and
                    open_[i] < close[i - 1] and
                    open_[i] > open_[i - 1] and
                    close[i] > close[i - 2] and
                    close[i] < open_[i - 1]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Upside Tasuki Gap',
                'pattern_type': 'bullish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.75,
                'candle_data': self._get_candle_data(i, 3)
            })

        return patterns

    def detect_mat_hold(self) -> List[Dict]:
        """Mat Hold: Bullish, 3 small bearish, strong bullish breakout"""
        patterns = []
        df = self.df
        is_bullish = self._is_bullish; body_ratio = self._body_ratio
        body = self._body; close = self._close

        for i in range(4, self._n):
            # Check if middle candles are consolidating (close of candles i-3,i-2,i-1)
            mid = close[i - 3:i]
            middle_range = np.nanmax(mid) - np.nanmin(mid)

            if not (is_bullish[i - 4] and
                    body_ratio[i - 4] >= 0.7 and
                    middle_range < body[i - 4] * 0.5 and
                    is_bullish[i] and
                    close[i] > close[i - 4] and
                    body_ratio[i] >= 0.7):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Mat Hold',
                'pattern_type': 'bullish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.80,
                'candle_data': self._get_candle_data(i, 5)
            })

        return patterns

    def detect_rising_window(self) -> List[Dict]:
        """Rising Window: Gap up between two candles"""
        patterns = []
        df = self.df
        low = self._low; high = self._high

        for i in range(1, self._n):
            gap = low[i] > high[i - 1]

            if gap:
                candle = df.iloc[i]
                patterns.append({
                    'pattern_name': 'Rising Window',
                    'pattern_type': 'bullish',
                    'timestamp': candle['timestamp'],
                    'confidence_score': 0.70,
                    'candle_data': self._get_candle_data(i, 2)
                })

        return patterns

    # ==================== BEARISH PATTERNS ====================

    def detect_hanging_man(self) -> List[Dict]:
        """Hanging Man: Like hammer but at top of uptrend"""
        patterns = []
        df = self.df
        body = self._body; upper_shadow = self._upper_shadow; lower_shadow = self._lower_shadow
        total_range = self._total_range; close = self._close; n = self._n
        # inc3[i] True iff close[i-3:i] is monotonically non-decreasing (i>=3) — the
        # "prior uptrend" guard (pandas is_monotonic_increasing uses <=). Vectorized
        # once instead of a per-bar ``df['close'].iloc[i-3:i].is_monotonic_increasing``.
        inc3 = np.zeros(n, dtype=bool)
        if n > 3:
            inc3[3:] = (close[:-3] <= close[1:-2]) & (close[1:-2] <= close[2:-1])

        for i in range(3, n):
            # Check for uptrend
            if not inc3[i]:
                continue

            if not (lower_shadow[i] >= 2 * body[i] and
                    upper_shadow[i] <= 0.1 * total_range[i] and
                    body[i] < 0.3 * total_range[i] and
                    body[i] > 0):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Hanging Man',
                'pattern_type': 'bearish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.70,
                'candle_data': self._get_candle_data(i, 1)
            })

        return patterns

    def detect_shooting_star(self) -> List[Dict]:
        """Shooting Star: Small body at bottom, long upper shadow"""
        patterns = []
        df = self.df
        upper_shadow = self._upper_shadow; lower_shadow = self._lower_shadow
        body = self._body; total_range = self._total_range

        for i in range(3, self._n):
            if not (upper_shadow[i] >= 2 * body[i] and
                    lower_shadow[i] <= 0.1 * total_range[i] and
                    body[i] < 0.3 * total_range[i]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Shooting Star',
                'pattern_type': 'bearish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.75,
                'candle_data': self._get_candle_data(i, 1)
            })

        return patterns

    def detect_bearish_marubozu(self) -> List[Dict]:
        """Bearish Marubozu: Large bearish body, little/no shadows"""
        patterns = []
        df = self.df
        is_bearish = self._is_bearish; body_ratio = self._body_ratio
        upper_shadow = self._upper_shadow; lower_shadow = self._lower_shadow
        total_range = self._total_range

        for i in range(self._n):
            if not (bool(is_bearish[i]) and
                    body_ratio[i] >= 0.9 and
                    upper_shadow[i] <= 0.05 * total_range[i] and
                    lower_shadow[i] <= 0.05 * total_range[i]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Bearish Marubozu',
                'pattern_type': 'bearish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.80,
                'candle_data': self._get_candle_data(i, 1)
            })

        return patterns

    def detect_gravestone_doji(self) -> List[Dict]:
        """Gravestone Doji: No/tiny body, long upper shadow, no lower shadow"""
        patterns = []
        df = self.df
        body = self._body; upper_shadow = self._upper_shadow; lower_shadow = self._lower_shadow
        total_range = self._total_range

        for i in range(self._n):
            if not (body[i] <= 0.05 * total_range[i] and
                    upper_shadow[i] >= 0.7 * total_range[i] and
                    lower_shadow[i] <= 0.1 * total_range[i]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Gravestone Doji',
                'pattern_type': 'bearish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.75,
                'candle_data': self._get_candle_data(i, 1)
            })

        return patterns

    def detect_bearish_engulfing(self) -> List[Dict]:
        """Bearish Engulfing: Large bearish candle engulfs previous bullish"""
        patterns = []
        df = self.df
        is_bullish = self._is_bullish; is_bearish = self._is_bearish
        open_ = self._open; close = self._close; body = self._body

        for i in range(1, self._n):
            if not (is_bullish[i - 1] and is_bearish[i] and
                    open_[i] > close[i - 1] and
                    close[i] < open_[i - 1] and
                    body[i] > body[i - 1]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Bearish Engulfing',
                'pattern_type': 'bearish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.85,
                'candle_data': self._get_candle_data(i, 2)
            })

        return patterns

    def detect_dark_cloud_cover(self) -> List[Dict]:
        """Dark Cloud Cover: Bearish candle closes below midpoint of previous bullish"""
        patterns = []
        df = self.df
        is_bullish = self._is_bullish; is_bearish = self._is_bearish
        open_ = self._open; close = self._close

        for i in range(1, self._n):
            prev_midpoint = (open_[i - 1] + close[i - 1]) / 2

            if not (is_bullish[i - 1] and is_bearish[i] and
                    open_[i] > close[i - 1] and
                    close[i] < prev_midpoint and
                    close[i] > open_[i - 1]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Dark Cloud Cover',
                'pattern_type': 'bearish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.80,
                'candle_data': self._get_candle_data(i, 2)
            })

        return patterns

    def detect_tweezer_top(self) -> List[Dict]:
        """Tweezer Top: Two candles with matching highs"""
        patterns = []
        df = self.df
        high = self._high; total_range = self._total_range
        is_bullish = self._is_bullish; is_bearish = self._is_bearish

        for i in range(1, self._n):
            high_diff = abs(high[i - 1] - high[i])
            avg_range = (total_range[i - 1] + total_range[i]) / 2

            if not (high_diff <= 0.02 * avg_range and
                    is_bullish[i - 1] and is_bearish[i]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Tweezer Top',
                'pattern_type': 'bearish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.70,
                'candle_data': self._get_candle_data(i, 2)
            })

        return patterns

    def detect_bearish_kicker(self) -> List[Dict]:
        """Bearish Kicker: Gap down from bullish to bearish candle"""
        patterns = []
        df = self.df
        is_bullish = self._is_bullish; is_bearish = self._is_bearish
        open_ = self._open; body_ratio = self._body_ratio

        for i in range(1, self._n):
            if not (is_bullish[i - 1] and is_bearish[i] and
                    open_[i] < open_[i - 1] and
                    body_ratio[i] >= 0.7 and
                    body_ratio[i - 1] >= 0.7):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Bearish Kicker',
                'pattern_type': 'bearish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.85,
                'candle_data': self._get_candle_data(i, 2)
            })

        return patterns

    def detect_bearish_harami(self) -> List[Dict]:
        """Bearish Harami: Small bearish candle within previous bullish"""
        patterns = []
        df = self.df
        is_bullish = self._is_bullish; is_bearish = self._is_bearish
        open_ = self._open; close = self._close; body = self._body

        for i in range(1, self._n):
            if not (is_bullish[i - 1] and is_bearish[i] and
                    open_[i] < close[i - 1] and
                    close[i] > open_[i - 1] and
                    body[i] < body[i - 1] * 0.5):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Bearish Harami',
                'pattern_type': 'bearish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.75,
                'candle_data': self._get_candle_data(i, 2)
            })

        return patterns

    def detect_bearish_counterattack(self) -> List[Dict]:
        """Bearish Counterattack: Bearish candle closes at same level as previous bullish"""
        patterns = []
        df = self.df
        is_bullish = self._is_bullish; is_bearish = self._is_bearish
        close = self._close; total_range = self._total_range; body = self._body

        for i in range(1, self._n):
            close_diff = abs(close[i - 1] - close[i])

            if not (is_bullish[i - 1] and is_bearish[i] and
                    close_diff <= 0.02 * total_range[i - 1] and
                    body[i] >= body[i - 1] * 0.8):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Bearish Counterattack',
                'pattern_type': 'bearish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.75,
                'candle_data': self._get_candle_data(i, 2)
            })

        return patterns

    def detect_evening_star(self) -> List[Dict]:
        """Evening Star: Bullish candle, small body, bearish candle"""
        patterns = []
        df = self.df
        is_bullish = self._is_bullish; is_bearish = self._is_bearish
        open_ = self._open; close = self._close; low = self._low; body = self._body

        for i in range(2, self._n):
            if not (is_bullish[i - 2] and
                    body[i - 1] < body[i - 2] * 0.3 and
                    is_bearish[i] and
                    close[i] < (open_[i - 2] + close[i - 2]) / 2 and
                    low[i - 1] > close[i - 2] and
                    low[i - 1] > open_[i]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Evening Star',
                'pattern_type': 'bearish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.90,
                'candle_data': self._get_candle_data(i, 3)
            })

        return patterns

    def detect_evening_doji_star(self) -> List[Dict]:
        """Evening Doji Star: Bullish candle, doji, bearish candle"""
        patterns = []
        df = self.df
        is_bullish = self._is_bullish; is_bearish = self._is_bearish
        open_ = self._open; close = self._close; body = self._body; total_range = self._total_range

        for i in range(2, self._n):
            is_doji = body[i - 1] <= 0.1 * total_range[i - 1]

            if not (is_bullish[i - 2] and is_doji and is_bearish[i] and
                    close[i] < (open_[i - 2] + close[i - 2]) / 2):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Evening Doji Star',
                'pattern_type': 'bearish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.85,
                'candle_data': self._get_candle_data(i, 3)
            })

        return patterns

    def detect_three_black_crows(self) -> List[Dict]:
        """Three Black Crows: Three consecutive bearish candles with lower closes"""
        patterns = []
        df = self.df
        is_bearish = self._is_bearish; open_ = self._open; close = self._close

        for i in range(2, self._n):
            if not (is_bearish[i - 2] and is_bearish[i - 1] and is_bearish[i] and
                    close[i - 1] < close[i - 2] and
                    close[i] < close[i - 1] and
                    open_[i - 1] < open_[i - 2] and
                    open_[i - 1] > close[i - 2] and
                    open_[i] < open_[i - 1] and
                    open_[i] > close[i - 1]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Three Black Crows',
                'pattern_type': 'bearish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.90,
                'candle_data': self._get_candle_data(i, 3)
            })

        return patterns

    def detect_three_inside_down(self) -> List[Dict]:
        """Three Inside Down: Bearish harami followed by bearish candle"""
        patterns = []
        df = self.df
        is_bullish = self._is_bullish; is_bearish = self._is_bearish
        open_ = self._open; close = self._close

        for i in range(2, self._n):
            # First two candles form bearish harami
            is_harami = (is_bullish[i - 2] and is_bearish[i - 1] and
                         open_[i - 1] < close[i - 2] and
                         close[i - 1] > open_[i - 2])

            if not (is_harami and is_bearish[i] and close[i] < close[i - 1]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Three Inside Down',
                'pattern_type': 'bearish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.85,
                'candle_data': self._get_candle_data(i, 3)
            })

        return patterns

    def detect_three_outside_down(self) -> List[Dict]:
        """Three Outside Down: Bearish engulfing followed by bearish candle"""
        patterns = []
        df = self.df
        is_bullish = self._is_bullish; is_bearish = self._is_bearish
        open_ = self._open; close = self._close

        for i in range(2, self._n):
            # First two candles form bearish engulfing
            is_engulfing = (is_bullish[i - 2] and is_bearish[i - 1] and
                            open_[i - 1] > close[i - 2] and
                            close[i - 1] < open_[i - 2])

            if not (is_engulfing and is_bearish[i] and close[i] < close[i - 1]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Three Outside Down',
                'pattern_type': 'bearish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.85,
                'candle_data': self._get_candle_data(i, 3)
            })

        return patterns

    def detect_bearish_abandoned_baby(self) -> List[Dict]:
        """Bearish Abandoned Baby: Doji gaps above bullish and below bearish candle"""
        patterns = []
        df = self.df
        is_bullish = self._is_bullish; is_bearish = self._is_bearish
        high = self._high; low = self._low; body = self._body; total_range = self._total_range

        for i in range(2, self._n):
            is_doji = body[i - 1] <= 0.1 * total_range[i - 1]
            gap_up = low[i - 1] > high[i - 2]
            gap_down = high[i - 1] < low[i]

            if not (is_bullish[i - 2] and is_doji and gap_up and
                    is_bearish[i] and gap_down):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Bearish Abandoned Baby',
                'pattern_type': 'bearish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.95,
                'candle_data': self._get_candle_data(i, 3)
            })

        return patterns

    def detect_falling_three_methods(self) -> List[Dict]:
        """Falling Three Methods: Bearish, 3 small bullish within range, bearish"""
        patterns = []
        df = self.df
        is_bullish = self._is_bullish; is_bearish = self._is_bearish
        high = self._high; low = self._low; close = self._close

        for i in range(4, self._n):
            # Middle 3 candles are small and bullish, within first candle range
            middle_in_range = (
                high[i - 3] <= high[i - 4] and low[i - 3] >= low[i - 4] and
                high[i - 2] <= high[i - 4] and low[i - 2] >= low[i - 4] and
                high[i - 1] <= high[i - 4] and low[i - 1] >= low[i - 4]
            )

            if not (is_bearish[i - 4] and is_bullish[i - 3] and is_bullish[i - 2] and
                    is_bullish[i - 1] and middle_in_range and
                    is_bearish[i] and close[i] < close[i - 4]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Falling Three Methods',
                'pattern_type': 'bearish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.80,
                'candle_data': self._get_candle_data(i, 5)
            })

        return patterns

    def detect_downside_tasuki_gap(self) -> List[Dict]:
        """Downside Tasuki Gap: Two bearish with gap, bullish partially fills gap"""
        patterns = []
        df = self.df
        is_bullish = self._is_bullish; is_bearish = self._is_bearish
        high = self._high; low = self._low; open_ = self._open; close = self._close

        for i in range(2, self._n):
            gap = high[i - 1] < low[i - 2]

            if not (is_bearish[i - 2] and is_bearish[i - 1] and gap and
                    is_bullish[i] and
                    open_[i] > close[i - 1] and
                    open_[i] < open_[i - 1] and
                    close[i] < close[i - 2] and
                    close[i] > open_[i - 1]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'Downside Tasuki Gap',
                'pattern_type': 'bearish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.75,
                'candle_data': self._get_candle_data(i, 3)
            })

        return patterns

    def detect_on_neck_line(self) -> List[Dict]:
        """On Neck Line: Bearish candle, bullish closes at previous low"""
        patterns = []
        df = self.df
        is_bearish = self._is_bearish; is_bullish = self._is_bullish
        low = self._low; close = self._close; open_ = self._open; total_range = self._total_range

        for i in range(1, self._n):
            close_diff = abs(low[i - 1] - close[i])

            if not (is_bearish[i - 1] and is_bullish[i] and
                    close_diff <= 0.02 * total_range[i - 1] and
                    open_[i] < close[i - 1]):
                continue

            candle = df.iloc[i]
            patterns.append({
                'pattern_name': 'On Neck Line',
                'pattern_type': 'bearish',
                'timestamp': candle['timestamp'],
                'confidence_score': 0.70,
                'candle_data': self._get_candle_data(i, 2)
            })

        return patterns

    def detect_falling_window(self) -> List[Dict]:
        """Falling Window: Gap down between two candles"""
        patterns = []
        df = self.df
        low = self._low; high = self._high

        for i in range(1, self._n):
            gap = high[i] < low[i - 1]

            if gap:
                candle = df.iloc[i]
                patterns.append({
                    'pattern_name': 'Falling Window',
                    'pattern_type': 'bearish',
                    'timestamp': candle['timestamp'],
                    'confidence_score': 0.70,
                    'candle_data': self._get_candle_data(i, 2)
                })

        return patterns

    # ==================== HELPER METHODS ====================

    def _get_candle_data(self, index: int, num_candles: int) -> Dict:
        """Extract candle data for pattern storage"""
        start_idx = max(0, index - num_candles + 1)
        candles = self.df.iloc[start_idx:index + 1].copy()

        # Convert timestamp to ISO format string for JSON serialization
        candles['timestamp'] = candles['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')

        return {
            'candles': candles[['timestamp', 'open', 'high', 'low', 'close', 'volume']].to_dict('records')
        }
