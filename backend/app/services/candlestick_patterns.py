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

        for i in range(1, len(df)):
            # Previous trend should be downward
            if i < 3 or df['close'].iloc[i-3:i].is_monotonic_decreasing == False:
                continue

            candle = df.iloc[i]

            # Hammer criteria
            is_hammer = (
                candle['lower_shadow'] >= 2 * candle['body'] and
                candle['upper_shadow'] <= 0.1 * candle['total_range'] and
                candle['body'] < 0.3 * candle['total_range'] and
                candle['body'] > 0
            )

            if is_hammer:
                patterns.append({
                    'pattern_name': 'Hammer',
                    'pattern_type': 'bullish',
                    'timestamp': candle['timestamp'],
                    'confidence_score': 0.75,
                    'candle_data': self._get_candle_data(i, 1)
                })

        return patterns

    def detect_inverted_hammer(self) -> List[Dict]:
        """Inverted Hammer: Small body at bottom, long upper shadow, bullish reversal"""
        patterns = []
        df = self.df

        for i in range(1, len(df)):
            if i < 3:
                continue

            candle = df.iloc[i]

            is_inverted_hammer = (
                candle['upper_shadow'] >= 2 * candle['body'] and
                candle['lower_shadow'] <= 0.1 * candle['total_range'] and
                candle['body'] < 0.3 * candle['total_range']
            )

            if is_inverted_hammer:
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

        for i in range(len(df)):
            candle = df.iloc[i]

            is_bullish_marubozu = (
                candle['is_bullish'] and
                candle['body_ratio'] >= 0.9 and
                candle['upper_shadow'] <= 0.05 * candle['total_range'] and
                candle['lower_shadow'] <= 0.05 * candle['total_range']
            )

            if is_bullish_marubozu:
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

        for i in range(len(df)):
            candle = df.iloc[i]

            is_dragonfly_doji = (
                candle['body'] <= 0.05 * candle['total_range'] and
                candle['lower_shadow'] >= 0.7 * candle['total_range'] and
                candle['upper_shadow'] <= 0.1 * candle['total_range']
            )

            if is_dragonfly_doji:
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

        for i in range(1, len(df)):
            prev_candle = df.iloc[i-1]
            curr_candle = df.iloc[i]

            is_bullish_engulfing = (
                prev_candle['is_bearish'] and
                curr_candle['is_bullish'] and
                curr_candle['open'] < prev_candle['close'] and
                curr_candle['close'] > prev_candle['open'] and
                curr_candle['body'] > prev_candle['body']
            )

            if is_bullish_engulfing:
                patterns.append({
                    'pattern_name': 'Bullish Engulfing',
                    'pattern_type': 'bullish',
                    'timestamp': curr_candle['timestamp'],
                    'confidence_score': 0.85,
                    'candle_data': self._get_candle_data(i, 2)
                })

        return patterns

    def detect_piercing_line(self) -> List[Dict]:
        """Piercing Line: Bullish candle closes above midpoint of previous bearish candle"""
        patterns = []
        df = self.df

        for i in range(1, len(df)):
            prev_candle = df.iloc[i-1]
            curr_candle = df.iloc[i]

            prev_midpoint = (prev_candle['open'] + prev_candle['close']) / 2

            is_piercing_line = (
                prev_candle['is_bearish'] and
                curr_candle['is_bullish'] and
                curr_candle['open'] < prev_candle['close'] and
                curr_candle['close'] > prev_midpoint and
                curr_candle['close'] < prev_candle['open']
            )

            if is_piercing_line:
                patterns.append({
                    'pattern_name': 'Piercing Line',
                    'pattern_type': 'bullish',
                    'timestamp': curr_candle['timestamp'],
                    'confidence_score': 0.80,
                    'candle_data': self._get_candle_data(i, 2)
                })

        return patterns

    def detect_tweezer_bottom(self) -> List[Dict]:
        """Tweezer Bottom: Two candles with matching lows"""
        patterns = []
        df = self.df

        for i in range(1, len(df)):
            prev_candle = df.iloc[i-1]
            curr_candle = df.iloc[i]

            low_diff = abs(prev_candle['low'] - curr_candle['low'])
            avg_range = (prev_candle['total_range'] + curr_candle['total_range']) / 2

            is_tweezer_bottom = (
                low_diff <= 0.02 * avg_range and
                prev_candle['is_bearish'] and
                curr_candle['is_bullish']
            )

            if is_tweezer_bottom:
                patterns.append({
                    'pattern_name': 'Tweezer Bottom',
                    'pattern_type': 'bullish',
                    'timestamp': curr_candle['timestamp'],
                    'confidence_score': 0.70,
                    'candle_data': self._get_candle_data(i, 2)
                })

        return patterns

    def detect_bullish_kicker(self) -> List[Dict]:
        """Bullish Kicker: Gap up from bearish to bullish candle"""
        patterns = []
        df = self.df

        for i in range(1, len(df)):
            prev_candle = df.iloc[i-1]
            curr_candle = df.iloc[i]

            is_bullish_kicker = (
                prev_candle['is_bearish'] and
                curr_candle['is_bullish'] and
                curr_candle['open'] > prev_candle['open'] and
                curr_candle['body_ratio'] >= 0.7 and
                prev_candle['body_ratio'] >= 0.7
            )

            if is_bullish_kicker:
                patterns.append({
                    'pattern_name': 'Bullish Kicker',
                    'pattern_type': 'bullish',
                    'timestamp': curr_candle['timestamp'],
                    'confidence_score': 0.85,
                    'candle_data': self._get_candle_data(i, 2)
                })

        return patterns

    def detect_bullish_harami(self) -> List[Dict]:
        """Bullish Harami: Small bullish candle within previous bearish candle"""
        patterns = []
        df = self.df

        for i in range(1, len(df)):
            prev_candle = df.iloc[i-1]
            curr_candle = df.iloc[i]

            is_bullish_harami = (
                prev_candle['is_bearish'] and
                curr_candle['is_bullish'] and
                curr_candle['open'] > prev_candle['close'] and
                curr_candle['close'] < prev_candle['open'] and
                curr_candle['body'] < prev_candle['body'] * 0.5
            )

            if is_bullish_harami:
                patterns.append({
                    'pattern_name': 'Bullish Harami',
                    'pattern_type': 'bullish',
                    'timestamp': curr_candle['timestamp'],
                    'confidence_score': 0.75,
                    'candle_data': self._get_candle_data(i, 2)
                })

        return patterns

    def detect_bullish_counterattack(self) -> List[Dict]:
        """Bullish Counterattack: Bullish candle closes at same level as previous bearish"""
        patterns = []
        df = self.df

        for i in range(1, len(df)):
            prev_candle = df.iloc[i-1]
            curr_candle = df.iloc[i]

            close_diff = abs(prev_candle['close'] - curr_candle['close'])

            is_bullish_counterattack = (
                prev_candle['is_bearish'] and
                curr_candle['is_bullish'] and
                close_diff <= 0.02 * prev_candle['total_range'] and
                curr_candle['body'] >= prev_candle['body'] * 0.8
            )

            if is_bullish_counterattack:
                patterns.append({
                    'pattern_name': 'Bullish Counterattack',
                    'pattern_type': 'bullish',
                    'timestamp': curr_candle['timestamp'],
                    'confidence_score': 0.75,
                    'candle_data': self._get_candle_data(i, 2)
                })

        return patterns

    def detect_morning_star(self) -> List[Dict]:
        """Morning Star: Bearish candle, small body, bullish candle"""
        patterns = []
        df = self.df

        for i in range(2, len(df)):
            candle1 = df.iloc[i-2]
            candle2 = df.iloc[i-1]
            candle3 = df.iloc[i]

            is_morning_star = (
                candle1['is_bearish'] and
                candle2['body'] < candle1['body'] * 0.3 and
                candle3['is_bullish'] and
                candle3['close'] > (candle1['open'] + candle1['close']) / 2 and
                candle2['high'] < candle1['close'] and
                candle2['high'] < candle3['open']
            )

            if is_morning_star:
                patterns.append({
                    'pattern_name': 'Morning Star',
                    'pattern_type': 'bullish',
                    'timestamp': candle3['timestamp'],
                    'confidence_score': 0.90,
                    'candle_data': self._get_candle_data(i, 3)
                })

        return patterns

    def detect_morning_doji_star(self) -> List[Dict]:
        """Morning Doji Star: Bearish candle, doji, bullish candle"""
        patterns = []
        df = self.df

        for i in range(2, len(df)):
            candle1 = df.iloc[i-2]
            candle2 = df.iloc[i-1]
            candle3 = df.iloc[i]

            is_doji = candle2['body'] <= 0.1 * candle2['total_range']

            is_morning_doji_star = (
                candle1['is_bearish'] and
                is_doji and
                candle3['is_bullish'] and
                candle3['close'] > (candle1['open'] + candle1['close']) / 2
            )

            if is_morning_doji_star:
                patterns.append({
                    'pattern_name': 'Morning Doji Star',
                    'pattern_type': 'bullish',
                    'timestamp': candle3['timestamp'],
                    'confidence_score': 0.85,
                    'candle_data': self._get_candle_data(i, 3)
                })

        return patterns

    def detect_three_white_soldiers(self) -> List[Dict]:
        """Three White Soldiers: Three consecutive bullish candles with higher closes"""
        patterns = []
        df = self.df

        for i in range(2, len(df)):
            candle1 = df.iloc[i-2]
            candle2 = df.iloc[i-1]
            candle3 = df.iloc[i]

            is_three_white_soldiers = (
                candle1['is_bullish'] and
                candle2['is_bullish'] and
                candle3['is_bullish'] and
                candle2['close'] > candle1['close'] and
                candle3['close'] > candle2['close'] and
                candle2['open'] > candle1['open'] and
                candle2['open'] < candle1['close'] and
                candle3['open'] > candle2['open'] and
                candle3['open'] < candle2['close']
            )

            if is_three_white_soldiers:
                patterns.append({
                    'pattern_name': 'Three White Soldiers',
                    'pattern_type': 'bullish',
                    'timestamp': candle3['timestamp'],
                    'confidence_score': 0.90,
                    'candle_data': self._get_candle_data(i, 3)
                })

        return patterns

    def detect_three_inside_up(self) -> List[Dict]:
        """Three Inside Up: Bullish harami followed by bullish candle"""
        patterns = []
        df = self.df

        for i in range(2, len(df)):
            candle1 = df.iloc[i-2]
            candle2 = df.iloc[i-1]
            candle3 = df.iloc[i]

            # First two candles form bullish harami
            is_harami = (
                candle1['is_bearish'] and
                candle2['is_bullish'] and
                candle2['open'] > candle1['close'] and
                candle2['close'] < candle1['open']
            )

            is_three_inside_up = (
                is_harami and
                candle3['is_bullish'] and
                candle3['close'] > candle2['close']
            )

            if is_three_inside_up:
                patterns.append({
                    'pattern_name': 'Three Inside Up',
                    'pattern_type': 'bullish',
                    'timestamp': candle3['timestamp'],
                    'confidence_score': 0.85,
                    'candle_data': self._get_candle_data(i, 3)
                })

        return patterns

    def detect_three_outside_up(self) -> List[Dict]:
        """Three Outside Up: Bullish engulfing followed by bullish candle"""
        patterns = []
        df = self.df

        for i in range(2, len(df)):
            candle1 = df.iloc[i-2]
            candle2 = df.iloc[i-1]
            candle3 = df.iloc[i]

            # First two candles form bullish engulfing
            is_engulfing = (
                candle1['is_bearish'] and
                candle2['is_bullish'] and
                candle2['open'] < candle1['close'] and
                candle2['close'] > candle1['open']
            )

            is_three_outside_up = (
                is_engulfing and
                candle3['is_bullish'] and
                candle3['close'] > candle2['close']
            )

            if is_three_outside_up:
                patterns.append({
                    'pattern_name': 'Three Outside Up',
                    'pattern_type': 'bullish',
                    'timestamp': candle3['timestamp'],
                    'confidence_score': 0.85,
                    'candle_data': self._get_candle_data(i, 3)
                })

        return patterns

    def detect_bullish_abandoned_baby(self) -> List[Dict]:
        """Bullish Abandoned Baby: Doji gaps below bearish and above bullish candle"""
        patterns = []
        df = self.df

        for i in range(2, len(df)):
            candle1 = df.iloc[i-2]
            candle2 = df.iloc[i-1]
            candle3 = df.iloc[i]

            is_doji = candle2['body'] <= 0.1 * candle2['total_range']
            gap_down = candle2['high'] < candle1['low']
            gap_up = candle2['low'] > candle3['high']

            is_bullish_abandoned_baby = (
                candle1['is_bearish'] and
                is_doji and
                gap_down and
                candle3['is_bullish'] and
                gap_up
            )

            if is_bullish_abandoned_baby:
                patterns.append({
                    'pattern_name': 'Bullish Abandoned Baby',
                    'pattern_type': 'bullish',
                    'timestamp': candle3['timestamp'],
                    'confidence_score': 0.95,
                    'candle_data': self._get_candle_data(i, 3)
                })

        return patterns

    def detect_rising_three_methods(self) -> List[Dict]:
        """Rising Three Methods: Bullish, 3 small bearish within range, bullish"""
        patterns = []
        df = self.df

        for i in range(4, len(df)):
            candle1 = df.iloc[i-4]
            candle2 = df.iloc[i-3]
            candle3 = df.iloc[i-2]
            candle4 = df.iloc[i-1]
            candle5 = df.iloc[i]

            # Middle 3 candles are small and bearish, within first candle range
            middle_in_range = (
                candle2['high'] <= candle1['high'] and
                candle2['low'] >= candle1['low'] and
                candle3['high'] <= candle1['high'] and
                candle3['low'] >= candle1['low'] and
                candle4['high'] <= candle1['high'] and
                candle4['low'] >= candle1['low']
            )

            is_rising_three_methods = (
                candle1['is_bullish'] and
                candle2['is_bearish'] and
                candle3['is_bearish'] and
                candle4['is_bearish'] and
                middle_in_range and
                candle5['is_bullish'] and
                candle5['close'] > candle1['close']
            )

            if is_rising_three_methods:
                patterns.append({
                    'pattern_name': 'Rising Three Methods',
                    'pattern_type': 'bullish',
                    'timestamp': candle5['timestamp'],
                    'confidence_score': 0.80,
                    'candle_data': self._get_candle_data(i, 5)
                })

        return patterns

    def detect_upside_tasuki_gap(self) -> List[Dict]:
        """Upside Tasuki Gap: Two bullish with gap, bearish partially fills gap"""
        patterns = []
        df = self.df

        for i in range(2, len(df)):
            candle1 = df.iloc[i-2]
            candle2 = df.iloc[i-1]
            candle3 = df.iloc[i]

            gap = candle2['low'] > candle1['high']

            is_upside_tasuki_gap = (
                candle1['is_bullish'] and
                candle2['is_bullish'] and
                gap and
                candle3['is_bearish'] and
                candle3['open'] < candle2['close'] and
                candle3['open'] > candle2['open'] and
                candle3['close'] > candle1['close'] and
                candle3['close'] < candle2['open']
            )

            if is_upside_tasuki_gap:
                patterns.append({
                    'pattern_name': 'Upside Tasuki Gap',
                    'pattern_type': 'bullish',
                    'timestamp': candle3['timestamp'],
                    'confidence_score': 0.75,
                    'candle_data': self._get_candle_data(i, 3)
                })

        return patterns

    def detect_mat_hold(self) -> List[Dict]:
        """Mat Hold: Bullish, 3 small bearish, strong bullish breakout"""
        patterns = []
        df = self.df

        for i in range(4, len(df)):
            candle1 = df.iloc[i-4]
            candle5 = df.iloc[i]

            # Check if middle candles are consolidating
            middle_range = df.iloc[i-3:i]['close'].max() - df.iloc[i-3:i]['close'].min()

            is_mat_hold = (
                candle1['is_bullish'] and
                candle1['body_ratio'] >= 0.7 and
                middle_range < candle1['body'] * 0.5 and
                candle5['is_bullish'] and
                candle5['close'] > candle1['close'] and
                candle5['body_ratio'] >= 0.7
            )

            if is_mat_hold:
                patterns.append({
                    'pattern_name': 'Mat Hold',
                    'pattern_type': 'bullish',
                    'timestamp': candle5['timestamp'],
                    'confidence_score': 0.80,
                    'candle_data': self._get_candle_data(i, 5)
                })

        return patterns

    def detect_rising_window(self) -> List[Dict]:
        """Rising Window: Gap up between two candles"""
        patterns = []
        df = self.df

        for i in range(1, len(df)):
            prev_candle = df.iloc[i-1]
            curr_candle = df.iloc[i]

            gap = curr_candle['low'] > prev_candle['high']

            if gap:
                patterns.append({
                    'pattern_name': 'Rising Window',
                    'pattern_type': 'bullish',
                    'timestamp': curr_candle['timestamp'],
                    'confidence_score': 0.70,
                    'candle_data': self._get_candle_data(i, 2)
                })

        return patterns

    # ==================== BEARISH PATTERNS ====================

    def detect_hanging_man(self) -> List[Dict]:
        """Hanging Man: Like hammer but at top of uptrend"""
        patterns = []
        df = self.df

        for i in range(3, len(df)):
            # Check for uptrend
            if df['close'].iloc[i-3:i].is_monotonic_increasing == False:
                continue

            candle = df.iloc[i]

            is_hanging_man = (
                candle['lower_shadow'] >= 2 * candle['body'] and
                candle['upper_shadow'] <= 0.1 * candle['total_range'] and
                candle['body'] < 0.3 * candle['total_range'] and
                candle['body'] > 0
            )

            if is_hanging_man:
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

        for i in range(3, len(df)):
            candle = df.iloc[i]

            is_shooting_star = (
                candle['upper_shadow'] >= 2 * candle['body'] and
                candle['lower_shadow'] <= 0.1 * candle['total_range'] and
                candle['body'] < 0.3 * candle['total_range']
            )

            if is_shooting_star:
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

        for i in range(len(df)):
            candle = df.iloc[i]

            is_bearish_marubozu = (
                candle['is_bearish'] and
                candle['body_ratio'] >= 0.9 and
                candle['upper_shadow'] <= 0.05 * candle['total_range'] and
                candle['lower_shadow'] <= 0.05 * candle['total_range']
            )

            if is_bearish_marubozu:
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

        for i in range(len(df)):
            candle = df.iloc[i]

            is_gravestone_doji = (
                candle['body'] <= 0.05 * candle['total_range'] and
                candle['upper_shadow'] >= 0.7 * candle['total_range'] and
                candle['lower_shadow'] <= 0.1 * candle['total_range']
            )

            if is_gravestone_doji:
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

        for i in range(1, len(df)):
            prev_candle = df.iloc[i-1]
            curr_candle = df.iloc[i]

            is_bearish_engulfing = (
                prev_candle['is_bullish'] and
                curr_candle['is_bearish'] and
                curr_candle['open'] > prev_candle['close'] and
                curr_candle['close'] < prev_candle['open'] and
                curr_candle['body'] > prev_candle['body']
            )

            if is_bearish_engulfing:
                patterns.append({
                    'pattern_name': 'Bearish Engulfing',
                    'pattern_type': 'bearish',
                    'timestamp': curr_candle['timestamp'],
                    'confidence_score': 0.85,
                    'candle_data': self._get_candle_data(i, 2)
                })

        return patterns

    def detect_dark_cloud_cover(self) -> List[Dict]:
        """Dark Cloud Cover: Bearish candle closes below midpoint of previous bullish"""
        patterns = []
        df = self.df

        for i in range(1, len(df)):
            prev_candle = df.iloc[i-1]
            curr_candle = df.iloc[i]

            prev_midpoint = (prev_candle['open'] + prev_candle['close']) / 2

            is_dark_cloud_cover = (
                prev_candle['is_bullish'] and
                curr_candle['is_bearish'] and
                curr_candle['open'] > prev_candle['close'] and
                curr_candle['close'] < prev_midpoint and
                curr_candle['close'] > prev_candle['open']
            )

            if is_dark_cloud_cover:
                patterns.append({
                    'pattern_name': 'Dark Cloud Cover',
                    'pattern_type': 'bearish',
                    'timestamp': curr_candle['timestamp'],
                    'confidence_score': 0.80,
                    'candle_data': self._get_candle_data(i, 2)
                })

        return patterns

    def detect_tweezer_top(self) -> List[Dict]:
        """Tweezer Top: Two candles with matching highs"""
        patterns = []
        df = self.df

        for i in range(1, len(df)):
            prev_candle = df.iloc[i-1]
            curr_candle = df.iloc[i]

            high_diff = abs(prev_candle['high'] - curr_candle['high'])
            avg_range = (prev_candle['total_range'] + curr_candle['total_range']) / 2

            is_tweezer_top = (
                high_diff <= 0.02 * avg_range and
                prev_candle['is_bullish'] and
                curr_candle['is_bearish']
            )

            if is_tweezer_top:
                patterns.append({
                    'pattern_name': 'Tweezer Top',
                    'pattern_type': 'bearish',
                    'timestamp': curr_candle['timestamp'],
                    'confidence_score': 0.70,
                    'candle_data': self._get_candle_data(i, 2)
                })

        return patterns

    def detect_bearish_kicker(self) -> List[Dict]:
        """Bearish Kicker: Gap down from bullish to bearish candle"""
        patterns = []
        df = self.df

        for i in range(1, len(df)):
            prev_candle = df.iloc[i-1]
            curr_candle = df.iloc[i]

            is_bearish_kicker = (
                prev_candle['is_bullish'] and
                curr_candle['is_bearish'] and
                curr_candle['open'] < prev_candle['open'] and
                curr_candle['body_ratio'] >= 0.7 and
                prev_candle['body_ratio'] >= 0.7
            )

            if is_bearish_kicker:
                patterns.append({
                    'pattern_name': 'Bearish Kicker',
                    'pattern_type': 'bearish',
                    'timestamp': curr_candle['timestamp'],
                    'confidence_score': 0.85,
                    'candle_data': self._get_candle_data(i, 2)
                })

        return patterns

    def detect_bearish_harami(self) -> List[Dict]:
        """Bearish Harami: Small bearish candle within previous bullish"""
        patterns = []
        df = self.df

        for i in range(1, len(df)):
            prev_candle = df.iloc[i-1]
            curr_candle = df.iloc[i]

            is_bearish_harami = (
                prev_candle['is_bullish'] and
                curr_candle['is_bearish'] and
                curr_candle['open'] < prev_candle['close'] and
                curr_candle['close'] > prev_candle['open'] and
                curr_candle['body'] < prev_candle['body'] * 0.5
            )

            if is_bearish_harami:
                patterns.append({
                    'pattern_name': 'Bearish Harami',
                    'pattern_type': 'bearish',
                    'timestamp': curr_candle['timestamp'],
                    'confidence_score': 0.75,
                    'candle_data': self._get_candle_data(i, 2)
                })

        return patterns

    def detect_bearish_counterattack(self) -> List[Dict]:
        """Bearish Counterattack: Bearish candle closes at same level as previous bullish"""
        patterns = []
        df = self.df

        for i in range(1, len(df)):
            prev_candle = df.iloc[i-1]
            curr_candle = df.iloc[i]

            close_diff = abs(prev_candle['close'] - curr_candle['close'])

            is_bearish_counterattack = (
                prev_candle['is_bullish'] and
                curr_candle['is_bearish'] and
                close_diff <= 0.02 * prev_candle['total_range'] and
                curr_candle['body'] >= prev_candle['body'] * 0.8
            )

            if is_bearish_counterattack:
                patterns.append({
                    'pattern_name': 'Bearish Counterattack',
                    'pattern_type': 'bearish',
                    'timestamp': curr_candle['timestamp'],
                    'confidence_score': 0.75,
                    'candle_data': self._get_candle_data(i, 2)
                })

        return patterns

    def detect_evening_star(self) -> List[Dict]:
        """Evening Star: Bullish candle, small body, bearish candle"""
        patterns = []
        df = self.df

        for i in range(2, len(df)):
            candle1 = df.iloc[i-2]
            candle2 = df.iloc[i-1]
            candle3 = df.iloc[i]

            is_evening_star = (
                candle1['is_bullish'] and
                candle2['body'] < candle1['body'] * 0.3 and
                candle3['is_bearish'] and
                candle3['close'] < (candle1['open'] + candle1['close']) / 2 and
                candle2['low'] > candle1['close'] and
                candle2['low'] > candle3['open']
            )

            if is_evening_star:
                patterns.append({
                    'pattern_name': 'Evening Star',
                    'pattern_type': 'bearish',
                    'timestamp': candle3['timestamp'],
                    'confidence_score': 0.90,
                    'candle_data': self._get_candle_data(i, 3)
                })

        return patterns

    def detect_evening_doji_star(self) -> List[Dict]:
        """Evening Doji Star: Bullish candle, doji, bearish candle"""
        patterns = []
        df = self.df

        for i in range(2, len(df)):
            candle1 = df.iloc[i-2]
            candle2 = df.iloc[i-1]
            candle3 = df.iloc[i]

            is_doji = candle2['body'] <= 0.1 * candle2['total_range']

            is_evening_doji_star = (
                candle1['is_bullish'] and
                is_doji and
                candle3['is_bearish'] and
                candle3['close'] < (candle1['open'] + candle1['close']) / 2
            )

            if is_evening_doji_star:
                patterns.append({
                    'pattern_name': 'Evening Doji Star',
                    'pattern_type': 'bearish',
                    'timestamp': candle3['timestamp'],
                    'confidence_score': 0.85,
                    'candle_data': self._get_candle_data(i, 3)
                })

        return patterns

    def detect_three_black_crows(self) -> List[Dict]:
        """Three Black Crows: Three consecutive bearish candles with lower closes"""
        patterns = []
        df = self.df

        for i in range(2, len(df)):
            candle1 = df.iloc[i-2]
            candle2 = df.iloc[i-1]
            candle3 = df.iloc[i]

            is_three_black_crows = (
                candle1['is_bearish'] and
                candle2['is_bearish'] and
                candle3['is_bearish'] and
                candle2['close'] < candle1['close'] and
                candle3['close'] < candle2['close'] and
                candle2['open'] < candle1['open'] and
                candle2['open'] > candle1['close'] and
                candle3['open'] < candle2['open'] and
                candle3['open'] > candle2['close']
            )

            if is_three_black_crows:
                patterns.append({
                    'pattern_name': 'Three Black Crows',
                    'pattern_type': 'bearish',
                    'timestamp': candle3['timestamp'],
                    'confidence_score': 0.90,
                    'candle_data': self._get_candle_data(i, 3)
                })

        return patterns

    def detect_three_inside_down(self) -> List[Dict]:
        """Three Inside Down: Bearish harami followed by bearish candle"""
        patterns = []
        df = self.df

        for i in range(2, len(df)):
            candle1 = df.iloc[i-2]
            candle2 = df.iloc[i-1]
            candle3 = df.iloc[i]

            # First two candles form bearish harami
            is_harami = (
                candle1['is_bullish'] and
                candle2['is_bearish'] and
                candle2['open'] < candle1['close'] and
                candle2['close'] > candle1['open']
            )

            is_three_inside_down = (
                is_harami and
                candle3['is_bearish'] and
                candle3['close'] < candle2['close']
            )

            if is_three_inside_down:
                patterns.append({
                    'pattern_name': 'Three Inside Down',
                    'pattern_type': 'bearish',
                    'timestamp': candle3['timestamp'],
                    'confidence_score': 0.85,
                    'candle_data': self._get_candle_data(i, 3)
                })

        return patterns

    def detect_three_outside_down(self) -> List[Dict]:
        """Three Outside Down: Bearish engulfing followed by bearish candle"""
        patterns = []
        df = self.df

        for i in range(2, len(df)):
            candle1 = df.iloc[i-2]
            candle2 = df.iloc[i-1]
            candle3 = df.iloc[i]

            # First two candles form bearish engulfing
            is_engulfing = (
                candle1['is_bullish'] and
                candle2['is_bearish'] and
                candle2['open'] > candle1['close'] and
                candle2['close'] < candle1['open']
            )

            is_three_outside_down = (
                is_engulfing and
                candle3['is_bearish'] and
                candle3['close'] < candle2['close']
            )

            if is_three_outside_down:
                patterns.append({
                    'pattern_name': 'Three Outside Down',
                    'pattern_type': 'bearish',
                    'timestamp': candle3['timestamp'],
                    'confidence_score': 0.85,
                    'candle_data': self._get_candle_data(i, 3)
                })

        return patterns

    def detect_bearish_abandoned_baby(self) -> List[Dict]:
        """Bearish Abandoned Baby: Doji gaps above bullish and below bearish candle"""
        patterns = []
        df = self.df

        for i in range(2, len(df)):
            candle1 = df.iloc[i-2]
            candle2 = df.iloc[i-1]
            candle3 = df.iloc[i]

            is_doji = candle2['body'] <= 0.1 * candle2['total_range']
            gap_up = candle2['low'] > candle1['high']
            gap_down = candle2['high'] < candle3['low']

            is_bearish_abandoned_baby = (
                candle1['is_bullish'] and
                is_doji and
                gap_up and
                candle3['is_bearish'] and
                gap_down
            )

            if is_bearish_abandoned_baby:
                patterns.append({
                    'pattern_name': 'Bearish Abandoned Baby',
                    'pattern_type': 'bearish',
                    'timestamp': candle3['timestamp'],
                    'confidence_score': 0.95,
                    'candle_data': self._get_candle_data(i, 3)
                })

        return patterns

    def detect_falling_three_methods(self) -> List[Dict]:
        """Falling Three Methods: Bearish, 3 small bullish within range, bearish"""
        patterns = []
        df = self.df

        for i in range(4, len(df)):
            candle1 = df.iloc[i-4]
            candle2 = df.iloc[i-3]
            candle3 = df.iloc[i-2]
            candle4 = df.iloc[i-1]
            candle5 = df.iloc[i]

            # Middle 3 candles are small and bullish, within first candle range
            middle_in_range = (
                candle2['high'] <= candle1['high'] and
                candle2['low'] >= candle1['low'] and
                candle3['high'] <= candle1['high'] and
                candle3['low'] >= candle1['low'] and
                candle4['high'] <= candle1['high'] and
                candle4['low'] >= candle1['low']
            )

            is_falling_three_methods = (
                candle1['is_bearish'] and
                candle2['is_bullish'] and
                candle3['is_bullish'] and
                candle4['is_bullish'] and
                middle_in_range and
                candle5['is_bearish'] and
                candle5['close'] < candle1['close']
            )

            if is_falling_three_methods:
                patterns.append({
                    'pattern_name': 'Falling Three Methods',
                    'pattern_type': 'bearish',
                    'timestamp': candle5['timestamp'],
                    'confidence_score': 0.80,
                    'candle_data': self._get_candle_data(i, 5)
                })

        return patterns

    def detect_downside_tasuki_gap(self) -> List[Dict]:
        """Downside Tasuki Gap: Two bearish with gap, bullish partially fills gap"""
        patterns = []
        df = self.df

        for i in range(2, len(df)):
            candle1 = df.iloc[i-2]
            candle2 = df.iloc[i-1]
            candle3 = df.iloc[i]

            gap = candle2['high'] < candle1['low']

            is_downside_tasuki_gap = (
                candle1['is_bearish'] and
                candle2['is_bearish'] and
                gap and
                candle3['is_bullish'] and
                candle3['open'] > candle2['close'] and
                candle3['open'] < candle2['open'] and
                candle3['close'] < candle1['close'] and
                candle3['close'] > candle2['open']
            )

            if is_downside_tasuki_gap:
                patterns.append({
                    'pattern_name': 'Downside Tasuki Gap',
                    'pattern_type': 'bearish',
                    'timestamp': candle3['timestamp'],
                    'confidence_score': 0.75,
                    'candle_data': self._get_candle_data(i, 3)
                })

        return patterns

    def detect_on_neck_line(self) -> List[Dict]:
        """On Neck Line: Bearish candle, bullish closes at previous low"""
        patterns = []
        df = self.df

        for i in range(1, len(df)):
            prev_candle = df.iloc[i-1]
            curr_candle = df.iloc[i]

            close_diff = abs(prev_candle['low'] - curr_candle['close'])

            is_on_neck_line = (
                prev_candle['is_bearish'] and
                curr_candle['is_bullish'] and
                close_diff <= 0.02 * prev_candle['total_range'] and
                curr_candle['open'] < prev_candle['close']
            )

            if is_on_neck_line:
                patterns.append({
                    'pattern_name': 'On Neck Line',
                    'pattern_type': 'bearish',
                    'timestamp': curr_candle['timestamp'],
                    'confidence_score': 0.70,
                    'candle_data': self._get_candle_data(i, 2)
                })

        return patterns

    def detect_falling_window(self) -> List[Dict]:
        """Falling Window: Gap down between two candles"""
        patterns = []
        df = self.df

        for i in range(1, len(df)):
            prev_candle = df.iloc[i-1]
            curr_candle = df.iloc[i]

            gap = curr_candle['high'] < prev_candle['low']

            if gap:
                patterns.append({
                    'pattern_name': 'Falling Window',
                    'pattern_type': 'bearish',
                    'timestamp': curr_candle['timestamp'],
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
