"""
Chart Pattern Recognition Service
Detects chart patterns like Head & Shoulders, Triangles, Cup & Handle, etc.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from scipy.signal import find_peaks, argrelextrema
from sklearn.linear_model import LinearRegression


class ChartPatternDetector:
    """Detects chart patterns in OHLC data"""

    def __init__(self, df: pd.DataFrame, min_pattern_length: int = 20,
                 peak_order: int = 5, min_confidence: float = 0.0, min_r_squared: float = 0.0):
        """
        Initialize with OHLC dataframe

        Args:
            df: DataFrame with columns: open, high, low, close, volume, timestamp
            min_pattern_length: Minimum number of candles for a pattern
            peak_order: Order parameter for peak detection (higher = less sensitive, fewer peaks)
            min_confidence: Minimum confidence score to keep a pattern (0.0-1.0)
            min_r_squared: Minimum R² for trendline quality (0.0-1.0)
        """
        self.df = df.copy()
        self.min_pattern_length = min_pattern_length
        self.peak_order = peak_order
        self.min_confidence = min_confidence
        self.min_r_squared = min_r_squared
        self._find_peaks_and_troughs()

    def _find_peaks_and_troughs(self):
        """Identify peaks (highs) and troughs (lows) in the price data"""
        # Use scipy to find local maxima and minima
        high_indices = argrelextrema(self.df['high'].values, np.greater, order=self.peak_order)[0]
        low_indices = argrelextrema(self.df['low'].values, np.less, order=self.peak_order)[0]

        self.df['is_peak'] = False
        self.df['is_trough'] = False
        self.df.loc[self.df.index[high_indices], 'is_peak'] = True
        self.df.loc[self.df.index[low_indices], 'is_trough'] = True

        # Store peak/trough info
        self.peaks = self.df[self.df['is_peak']].copy()
        self.troughs = self.df[self.df['is_trough']].copy()

    def _calculate_trendline(self, x_values: np.ndarray, y_values: np.ndarray, start_idx: int = None) -> Dict:
        """
        Calculate trendline using linear regression

        Args:
            x_values: Absolute indices from DataFrame
            y_values: Price values
            start_idx: Starting index of the pattern (to convert to relative indices)

        Returns:
            Dict with slope, intercept (relative to pattern start), and r_squared
        """
        if len(x_values) < 2:
            return None

        # Convert absolute indices to relative indices (starting from 0)
        if start_idx is not None:
            x_relative = x_values - start_idx
        else:
            # If no start_idx provided, assume x_values are already relative
            x_relative = x_values

        x = x_relative.reshape(-1, 1)
        y = y_values

        model = LinearRegression()
        model.fit(x, y)

        slope = model.coef_[0]
        intercept = model.intercept_
        r_squared = model.score(x, y)

        return {
            'slope': float(slope),
            'intercept': float(intercept),
            'r_squared': float(r_squared)
        }

    def _calculate_atr(self, window: int = 14) -> pd.Series:
        """Calculate Average True Range for volatility measurement"""
        high = self.df['high']
        low = self.df['low']
        close = self.df['close'].shift(1)

        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=window).mean()

        return atr

    def _detect_prior_trend(self, start_idx: int, end_idx: int) -> Dict:
        """Detect trend strength before a pattern for reversal validation"""
        if start_idx < 20:
            return {'trend': 'neutral', 'strength': 0.0}

        window = self.df.iloc[start_idx-20:start_idx]

        # Calculate price change
        price_change = (window.iloc[-1]['close'] - window.iloc[0]['close']) / window.iloc[0]['close']

        # Calculate linear regression slope on closing prices
        indices = np.arange(len(window))
        closes = window['close'].values

        if len(closes) < 2:
            return {'trend': 'neutral', 'strength': 0.0}

        trendline = self._calculate_trendline(indices, closes)

        if not trendline:
            return {'trend': 'neutral', 'strength': 0.0}

        # Determine trend direction and strength
        r_squared = trendline['r_squared']

        if price_change > 0.05 and trendline['slope'] > 0:
            return {'trend': 'uptrend', 'strength': float(r_squared)}
        elif price_change < -0.05 and trendline['slope'] < 0:
            return {'trend': 'downtrend', 'strength': float(r_squared)}
        else:
            return {'trend': 'neutral', 'strength': 0.0}

    def _analyze_volume_profile(self, window: pd.DataFrame) -> Dict:
        """Analyze volume behavior within a pattern window"""
        if 'volume' not in window.columns or window['volume'].isna().all():
            return {
                'volume_trend': 'unknown',
                'avg_volume': 0,
                'volume_score': 0.5  # Neutral score if no volume data
            }

        volumes = window['volume'].values

        # Calculate average volume
        avg_volume = np.mean(volumes)

        # Calculate volume trend (declining is typical during consolidation)
        first_half_avg = np.mean(volumes[:len(volumes)//2])
        second_half_avg = np.mean(volumes[len(volumes)//2:])

        volume_change = (second_half_avg - first_half_avg) / first_half_avg if first_half_avg > 0 else 0

        # Volume should decline during pattern formation (consolidation)
        if volume_change < -0.1:  # 10% decline
            volume_trend = 'declining'
            volume_score = 0.8
        elif volume_change > 0.1:  # 10% increase
            volume_trend = 'increasing'
            volume_score = 0.4  # Less ideal
        else:
            volume_trend = 'stable'
            volume_score = 0.6

        return {
            'volume_trend': volume_trend,
            'avg_volume': float(avg_volume),
            'volume_score': volume_score
        }

    def _calculate_pattern_quality(self, pattern_data: Dict) -> float:
        """
        Calculate overall pattern quality score (0.0 to 1.0)

        Factors:
        - Trendline fit quality (R²)
        - Volume behavior
        - Pattern symmetry
        - Prior trend strength (for reversals)
        """
        scores = []
        weights = []

        # Trendline fit quality (R²)
        if 'trendlines' in pattern_data and pattern_data['trendlines']:
            r_squared_values = []
            for line_data in pattern_data['trendlines'].values():
                if isinstance(line_data, dict) and 'r_squared' in line_data:
                    r_squared_values.append(line_data['r_squared'])

            if r_squared_values:
                avg_r_squared = np.mean(r_squared_values)
                scores.append(avg_r_squared)
                weights.append(0.35)  # 35% weight

        # Volume profile score
        if 'volume_profile' in pattern_data:
            volume_score = pattern_data['volume_profile'].get('volume_score', 0.5)
            scores.append(volume_score)
            weights.append(0.25)  # 25% weight

        # Prior trend strength (for reversal patterns)
        if pattern_data.get('pattern_type') == 'reversal' and 'prior_trend' in pattern_data:
            trend_strength = pattern_data['prior_trend'].get('strength', 0.0)
            scores.append(trend_strength)
            weights.append(0.20)  # 20% weight
        else:
            weights.append(0.0)  # Not applicable for continuation patterns

        # Pattern-specific quality factors
        base_confidence = pattern_data.get('confidence_score', 0.7)
        scores.append(base_confidence)
        weights.append(0.20)  # 20% weight

        # Calculate weighted average
        if sum(weights) > 0:
            weighted_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
        else:
            weighted_score = base_confidence

        return float(np.clip(weighted_score, 0.0, 1.0))

    def _patterns_overlap(self, pattern1: Dict, pattern2: Dict, overlap_threshold: float = 0.3) -> bool:
        """
        Check if two patterns overlap significantly

        Args:
            pattern1: First pattern dict with start_date and end_date
            pattern2: Second pattern dict with start_date and end_date
            overlap_threshold: Minimum fraction of overlap to consider patterns overlapping (0.0-1.0)

        Returns:
            True if patterns overlap more than threshold
        """
        start1 = pattern1['start_date']
        end1 = pattern1['end_date']
        start2 = pattern2['start_date']
        end2 = pattern2['end_date']

        # Calculate overlap
        latest_start = max(start1, start2)
        earliest_end = min(end1, end2)

        if latest_start >= earliest_end:
            return False  # No overlap

        overlap_duration = (earliest_end - latest_start).total_seconds()

        # Calculate pattern durations
        duration1 = (end1 - start1).total_seconds()
        duration2 = (end2 - start2).total_seconds()

        # Check if overlap is significant relative to either pattern
        if duration1 > 0:
            overlap_ratio1 = overlap_duration / duration1
            if overlap_ratio1 >= overlap_threshold:
                return True

        if duration2 > 0:
            overlap_ratio2 = overlap_duration / duration2
            if overlap_ratio2 >= overlap_threshold:
                return True

        return False

    def _remove_overlapping_patterns(self, patterns: List[Dict], overlap_threshold: float = 0.3) -> List[Dict]:
        """
        Remove overlapping patterns, keeping only the highest confidence one in each overlapping group

        Args:
            patterns: List of pattern dictionaries
            overlap_threshold: Minimum overlap fraction to consider patterns as overlapping

        Returns:
            Filtered list with overlaps removed
        """
        if not patterns:
            return patterns

        # Sort by confidence score (descending)
        sorted_patterns = sorted(patterns, key=lambda p: p['confidence_score'], reverse=True)

        kept_patterns = []

        for pattern in sorted_patterns:
            # Check if this pattern overlaps with any already kept pattern
            overlaps = False
            for kept in kept_patterns:
                if self._patterns_overlap(pattern, kept, overlap_threshold):
                    overlaps = True
                    break

            # If no overlap, keep this pattern
            if not overlaps:
                kept_patterns.append(pattern)

        # Sort by start date for return
        kept_patterns.sort(key=lambda p: p['start_date'])

        return kept_patterns

    def detect_all_patterns(self, exclude_patterns: List[str] = None, remove_overlaps: bool = True,
                           overlap_threshold: float = 0.1) -> List[Dict]:
        """
        Detect all chart patterns

        Args:
            exclude_patterns: List of pattern names to exclude (e.g., ['Rounding Top', 'Rounding Bottom'])
            remove_overlaps: Whether to remove overlapping patterns (keeps highest confidence)
            overlap_threshold: Minimum overlap fraction (0.0-1.0) to consider patterns as overlapping

        Returns:
            List of detected patterns
        """
        patterns = []

        if exclude_patterns is None:
            exclude_patterns = []

        # Reversal Patterns
        if 'Head and Shoulders' not in exclude_patterns:
            patterns.extend(self.detect_head_and_shoulders())
        if 'Inverse Head and Shoulders' not in exclude_patterns:
            patterns.extend(self.detect_inverse_head_and_shoulders())
        if 'Double Top' not in exclude_patterns:
            patterns.extend(self.detect_double_top())
        if 'Double Bottom' not in exclude_patterns:
            patterns.extend(self.detect_double_bottom())
        if 'Triple Top' not in exclude_patterns:
            patterns.extend(self.detect_triple_top())
        if 'Triple Bottom' not in exclude_patterns:
            patterns.extend(self.detect_triple_bottom())
        if 'Rounding Top' not in exclude_patterns:
            patterns.extend(self.detect_rounding_top())
        if 'Rounding Bottom' not in exclude_patterns:
            patterns.extend(self.detect_rounding_bottom())

        # Triangle Patterns
        if 'Ascending Triangle' not in exclude_patterns:
            patterns.extend(self.detect_ascending_triangle())
        if 'Descending Triangle' not in exclude_patterns:
            patterns.extend(self.detect_descending_triangle())
        if 'Symmetrical Triangle' not in exclude_patterns:
            patterns.extend(self.detect_symmetrical_triangle())

        # Continuation Patterns
        if 'Cup and Handle' not in exclude_patterns:
            patterns.extend(self.detect_cup_and_handle())
        if 'Flag' not in exclude_patterns:
            patterns.extend(self.detect_flag())
        if 'Pennant' not in exclude_patterns:
            patterns.extend(self.detect_pennant())
        if 'Rising Wedge' not in exclude_patterns:
            patterns.extend(self.detect_rising_wedge())
        if 'Falling Wedge' not in exclude_patterns:
            patterns.extend(self.detect_falling_wedge())

        # Channel/Rectangle Patterns
        if 'Rectangle' not in exclude_patterns:
            patterns.extend(self.detect_rectangle())
        if 'Ascending Channel' not in exclude_patterns:
            patterns.extend(self.detect_ascending_channel())
        if 'Descending Channel' not in exclude_patterns:
            patterns.extend(self.detect_descending_channel())

        # Remove overlapping patterns if requested
        if remove_overlaps:
            patterns = self._remove_overlapping_patterns(patterns, overlap_threshold)

        # Apply quality filters
        if self.min_confidence > 0:
            patterns = [p for p in patterns if p.get('confidence_score', 0) >= self.min_confidence]

        if self.min_r_squared > 0:
            patterns = [p for p in patterns if self._check_trendline_quality(p)]

        return patterns

    def _check_trendline_quality(self, pattern: Dict) -> bool:
        """Check if pattern meets minimum R² requirement"""
        if 'trendlines' not in pattern or not pattern['trendlines']:
            return True  # No trendlines to check

        r_squared_values = []
        for line_data in pattern['trendlines'].values():
            if isinstance(line_data, dict) and 'r_squared' in line_data:
                r_squared_values.append(line_data['r_squared'])

        if not r_squared_values:
            return True  # No R² values to check

        avg_r_squared = np.mean(r_squared_values)
        return avg_r_squared >= self.min_r_squared

    # ==================== REVERSAL PATTERNS ====================

    def detect_head_and_shoulders(self) -> List[Dict]:
        """Head and Shoulders: Three peaks with middle highest (bearish reversal)"""
        patterns = []
        peaks_list = self.peaks.index.tolist()

        if len(peaks_list) < 3:
            return patterns

        for i in range(len(peaks_list) - 2):
            left_shoulder_idx = peaks_list[i]
            head_idx = peaks_list[i + 1]
            right_shoulder_idx = peaks_list[i + 2]
            start_idx = left_shoulder_idx  # Pattern starting index

            left_shoulder = self.df.loc[left_shoulder_idx]
            head = self.df.loc[head_idx]
            right_shoulder = self.df.loc[right_shoulder_idx]

            # Head must be highest
            if head['high'] <= left_shoulder['high'] or head['high'] <= right_shoulder['high']:
                continue

            # Shoulders should be roughly equal (within 5%)
            shoulder_diff = abs(left_shoulder['high'] - right_shoulder['high']) / left_shoulder['high']
            if shoulder_diff > 0.05:
                continue

            # Find troughs between peaks for neckline
            troughs_between = self.df.loc[left_shoulder_idx:right_shoulder_idx][self.df['is_trough']]
            if len(troughs_between) < 2:
                continue

            trough1 = troughs_between.iloc[0]
            trough2 = troughs_between.iloc[-1]

            # Calculate neckline
            neckline_indices = np.array([left_shoulder_idx, right_shoulder_idx])
            neckline_prices = np.array([trough1['low'], trough2['low']])
            neckline = self._calculate_trendline(neckline_indices, neckline_prices, start_idx)

            if not neckline:
                continue

            # Filter low-quality trendlines (R² < 0.7)
            if neckline['r_squared'] < 0.7:
                continue

            # Pattern height (head to neckline)
            pattern_height = head['high'] - ((trough1['low'] + trough2['low']) / 2)
            neckline_price = (trough1['low'] + trough2['low']) / 2

            # Get pattern window for analysis
            pattern_window = self.df.loc[left_shoulder_idx:right_shoulder_idx]

            # Analyze volume profile
            volume_profile = self._analyze_volume_profile(pattern_window)

            # Check prior trend (should be uptrend for H&S reversal)
            prior_trend = self._detect_prior_trend(left_shoulder_idx, left_shoulder_idx)

            # Build pattern data
            pattern_data = {
                'pattern_name': 'Head and Shoulders',
                'pattern_type': 'reversal',
                'signal': 'bearish',
                'start_date': left_shoulder['timestamp'],
                'end_date': right_shoulder['timestamp'],
                'breakout_price': float(neckline_price),
                'target_price': float(neckline_price - pattern_height),
                'stop_loss': float(head['high']),
                'confidence_score': 0.80,
                'key_points': {
                    'left_shoulder': {'timestamp': str(left_shoulder['timestamp']), 'price': float(left_shoulder['high'])},
                    'head': {'timestamp': str(head['timestamp']), 'price': float(head['high'])},
                    'right_shoulder': {'timestamp': str(right_shoulder['timestamp']), 'price': float(right_shoulder['high'])},
                    'neckline_price': float(neckline_price)
                },
                'trendlines': {
                    'neckline': neckline
                },
                'volume_profile': volume_profile,
                'prior_trend': prior_trend
            }

            # Calculate quality score
            quality_score = self._calculate_pattern_quality(pattern_data)

            # Update confidence with quality score
            pattern_data['confidence_score'] = quality_score

            # Filter out low-quality patterns (below 0.5)
            if quality_score >= 0.5:
                patterns.append(pattern_data)

        return patterns

    def detect_inverse_head_and_shoulders(self) -> List[Dict]:
        """Inverse Head and Shoulders: Three troughs with middle lowest (bullish reversal)"""
        patterns = []
        troughs_list = self.troughs.index.tolist()

        if len(troughs_list) < 3:
            return patterns

        for i in range(len(troughs_list) - 2):
            left_shoulder_idx = troughs_list[i]
            head_idx = troughs_list[i + 1]
            right_shoulder_idx = troughs_list[i + 2]
            start_idx = left_shoulder_idx  # Pattern starting index

            left_shoulder = self.df.loc[left_shoulder_idx]
            head = self.df.loc[head_idx]
            right_shoulder = self.df.loc[right_shoulder_idx]

            # Head must be lowest
            if head['low'] >= left_shoulder['low'] or head['low'] >= right_shoulder['low']:
                continue

            # Shoulders should be roughly equal (within 5%)
            shoulder_diff = abs(left_shoulder['low'] - right_shoulder['low']) / left_shoulder['low']
            if shoulder_diff > 0.05:
                continue

            # Find peaks between troughs for neckline
            peaks_between = self.df.loc[left_shoulder_idx:right_shoulder_idx][self.df['is_peak']]
            if len(peaks_between) < 2:
                continue

            peak1 = peaks_between.iloc[0]
            peak2 = peaks_between.iloc[-1]

            # Calculate neckline using linear regression
            neckline_indices = np.array([left_shoulder_idx, right_shoulder_idx])
            neckline_prices = np.array([peak1['high'], peak2['high']])
            neckline = self._calculate_trendline(neckline_indices, neckline_prices, start_idx)

            if not neckline:
                continue

            # Filter low-quality trendlines (R² < 0.7)
            if neckline['r_squared'] < 0.7:
                continue

            # Pattern height (neckline to head)
            neckline_price = (peak1['high'] + peak2['high']) / 2
            pattern_height = neckline_price - head['low']

            # Get pattern window for analysis
            pattern_window = self.df.loc[left_shoulder_idx:right_shoulder_idx]

            # Analyze volume profile
            volume_profile = self._analyze_volume_profile(pattern_window)

            # Check prior trend (should be downtrend for inverse H&S reversal)
            prior_trend = self._detect_prior_trend(left_shoulder_idx, left_shoulder_idx)

            # Build pattern data
            pattern_data = {
                'pattern_name': 'Inverse Head and Shoulders',
                'pattern_type': 'reversal',
                'signal': 'bullish',
                'start_date': left_shoulder['timestamp'],
                'end_date': right_shoulder['timestamp'],
                'breakout_price': float(neckline_price),
                'target_price': float(neckline_price + pattern_height),
                'stop_loss': float(head['low']),
                'confidence_score': 0.80,
                'key_points': {
                    'left_shoulder': {'timestamp': str(left_shoulder['timestamp']), 'price': float(left_shoulder['low'])},
                    'head': {'timestamp': str(head['timestamp']), 'price': float(head['low'])},
                    'right_shoulder': {'timestamp': str(right_shoulder['timestamp']), 'price': float(right_shoulder['low'])},
                    'neckline_price': float(neckline_price)
                },
                'trendlines': {
                    'neckline': neckline
                },
                'volume_profile': volume_profile,
                'prior_trend': prior_trend
            }

            # Calculate quality score
            quality_score = self._calculate_pattern_quality(pattern_data)

            # Update confidence with quality score
            pattern_data['confidence_score'] = quality_score

            # Filter out low-quality patterns (below 0.5)
            if quality_score >= 0.5:
                patterns.append(pattern_data)

        return patterns

    def detect_double_top(self) -> List[Dict]:
        """Double Top: Two peaks at similar price (bearish reversal)"""
        patterns = []
        peaks_list = self.peaks.index.tolist()

        if len(peaks_list) < 2:
            return patterns

        for i in range(len(peaks_list) - 1):
            peak1_idx = peaks_list[i]
            peak2_idx = peaks_list[i + 1]
            start_idx = peak1_idx  # Pattern starting index

            peak1 = self.df.loc[peak1_idx]
            peak2 = self.df.loc[peak2_idx]

            # Peaks should be at similar price (within 3%)
            price_diff = abs(peak1['high'] - peak2['high']) / peak1['high']
            if price_diff > 0.03:
                continue

            # Find trough between peaks
            troughs_between = self.df.loc[peak1_idx:peak2_idx][self.df['is_trough']]
            if len(troughs_between) == 0:
                continue

            trough = troughs_between.iloc[0]
            support_level = trough['low']
            pattern_height = ((peak1['high'] + peak2['high']) / 2) - support_level

            # Calculate resistance line (peaks)
            peak_indices = np.array([peak1_idx, peak2_idx])
            peak_prices = np.array([peak1['high'], peak2['high']])
            resistance_line = self._calculate_trendline(peak_indices, peak_prices, start_idx)

            if not resistance_line:
                continue

            # Filter low-quality patterns (R² < 0.7)
            if resistance_line['r_squared'] < 0.7:
                continue

            # Get pattern window for analysis
            pattern_window = self.df.loc[peak1_idx:peak2_idx]

            # Analyze volume profile
            volume_profile = self._analyze_volume_profile(pattern_window)

            # Check prior trend (should be uptrend for double top reversal)
            prior_trend = self._detect_prior_trend(peak1_idx, peak1_idx)

            # Build pattern data
            pattern_data = {
                'pattern_name': 'Double Top',
                'pattern_type': 'reversal',
                'signal': 'bearish',
                'start_date': peak1['timestamp'],
                'end_date': peak2['timestamp'],
                'breakout_price': float(support_level),
                'target_price': float(support_level - pattern_height),
                'stop_loss': float((peak1['high'] + peak2['high']) / 2),
                'confidence_score': 0.75,
                'key_points': {
                    'peak1': {'timestamp': str(peak1['timestamp']), 'price': float(peak1['high'])},
                    'peak2': {'timestamp': str(peak2['timestamp']), 'price': float(peak2['high'])},
                    'support': float(support_level)
                },
                'trendlines': {
                    'resistance': resistance_line
                },
                'volume_profile': volume_profile,
                'prior_trend': prior_trend
            }

            # Calculate quality score
            quality_score = self._calculate_pattern_quality(pattern_data)

            # Update confidence with quality score
            pattern_data['confidence_score'] = quality_score

            # Filter out low-quality patterns (below 0.5)
            if quality_score >= 0.5:
                patterns.append(pattern_data)

        return patterns

    def detect_double_bottom(self) -> List[Dict]:
        """Double Bottom: Two troughs at similar price (bullish reversal)"""
        patterns = []
        troughs_list = self.troughs.index.tolist()

        if len(troughs_list) < 2:
            return patterns

        for i in range(len(troughs_list) - 1):
            trough1_idx = troughs_list[i]
            trough2_idx = troughs_list[i + 1]
            start_idx = trough1_idx  # Pattern starting index

            trough1 = self.df.loc[trough1_idx]
            trough2 = self.df.loc[trough2_idx]

            # Troughs should be at similar price (within 3%)
            price_diff = abs(trough1['low'] - trough2['low']) / trough1['low']
            if price_diff > 0.03:
                continue

            # Find peak between troughs
            peaks_between = self.df.loc[trough1_idx:trough2_idx][self.df['is_peak']]
            if len(peaks_between) == 0:
                continue

            peak = peaks_between.iloc[0]
            resistance_level = peak['high']
            pattern_height = resistance_level - ((trough1['low'] + trough2['low']) / 2)

            # Calculate support line (troughs)
            trough_indices = np.array([trough1_idx, trough2_idx])
            trough_prices = np.array([trough1['low'], trough2['low']])
            support_line = self._calculate_trendline(trough_indices, trough_prices, start_idx)

            if not support_line:
                continue

            # Filter low-quality patterns (R² < 0.7)
            if support_line['r_squared'] < 0.7:
                continue

            # Get pattern window for analysis
            pattern_window = self.df.loc[trough1_idx:trough2_idx]

            # Analyze volume profile
            volume_profile = self._analyze_volume_profile(pattern_window)

            # Check prior trend (should be downtrend for double bottom reversal)
            prior_trend = self._detect_prior_trend(trough1_idx, trough1_idx)

            # Build pattern data
            pattern_data = {
                'pattern_name': 'Double Bottom',
                'pattern_type': 'reversal',
                'signal': 'bullish',
                'start_date': trough1['timestamp'],
                'end_date': trough2['timestamp'],
                'breakout_price': float(resistance_level),
                'target_price': float(resistance_level + pattern_height),
                'stop_loss': float((trough1['low'] + trough2['low']) / 2),
                'confidence_score': 0.75,
                'key_points': {
                    'trough1': {'timestamp': str(trough1['timestamp']), 'price': float(trough1['low'])},
                    'trough2': {'timestamp': str(trough2['timestamp']), 'price': float(trough2['low'])},
                    'resistance': float(resistance_level)
                },
                'trendlines': {
                    'support': support_line
                },
                'volume_profile': volume_profile,
                'prior_trend': prior_trend
            }

            # Calculate quality score
            quality_score = self._calculate_pattern_quality(pattern_data)

            # Update confidence with quality score
            pattern_data['confidence_score'] = quality_score

            # Filter out low-quality patterns (below 0.5)
            if quality_score >= 0.5:
                patterns.append(pattern_data)

        return patterns

    # ==================== TRIANGLE PATTERNS ====================

    def detect_ascending_triangle(self) -> List[Dict]:
        """Ascending Triangle: Flat resistance, rising support (bullish)"""
        patterns = []

        if len(self.df) < self.min_pattern_length:
            return patterns

        # Look for patterns in sliding windows
        for i in range(len(self.df) - self.min_pattern_length):
            window = self.df.iloc[i:i + self.min_pattern_length]
            start_idx = self.df.index[i]  # Get the actual starting index

            # Get peaks and troughs in window
            window_peaks = window[window['is_peak']]
            window_troughs = window[window['is_trough']]

            if len(window_peaks) < 2 or len(window_troughs) < 2:
                continue

            # Check if resistance is flat (peaks at similar level)
            peak_prices = window_peaks['high'].values
            peak_std = np.std(peak_prices)
            peak_mean = np.mean(peak_prices)

            if peak_std / peak_mean > 0.02:  # More than 2% variation
                continue

            # Check if support is rising
            trough_indices = window_troughs.index.values
            trough_prices = window_troughs['low'].values
            support_line = self._calculate_trendline(trough_indices, trough_prices, start_idx)

            if not support_line or support_line['slope'] <= 0:
                continue

            # Filter low-quality trendlines (R² < 0.7)
            if support_line['r_squared'] < 0.7:
                continue

            resistance_level = peak_mean
            pattern_height = resistance_level - trough_prices[-1]

            # Analyze volume profile
            volume_profile = self._analyze_volume_profile(window)

            # Collect all peaks and troughs with their timestamps and prices
            peaks_data = [{
                'timestamp': str(window_peaks.iloc[j]['timestamp']),
                'price': float(window_peaks.iloc[j]['high']),
                'index': int(window_peaks.index[j])
            } for j in range(len(window_peaks))]

            troughs_data = [{
                'timestamp': str(window_troughs.iloc[j]['timestamp']),
                'price': float(window_troughs.iloc[j]['low']),
                'index': int(window_troughs.index[j])
            } for j in range(len(window_troughs))]

            # Build pattern data
            pattern_data = {
                'pattern_name': 'Ascending Triangle',
                'pattern_type': 'continuation',
                'signal': 'bullish',
                'start_date': window.iloc[0]['timestamp'],
                'end_date': window.iloc[-1]['timestamp'],
                'breakout_price': float(resistance_level),
                'target_price': float(resistance_level + pattern_height),
                'stop_loss': float(trough_prices[-1]),
                'confidence_score': 0.70,
                'key_points': {
                    'resistance_level': float(resistance_level),
                    'support_slope': support_line['slope'],
                    'peaks': peaks_data,
                    'troughs': troughs_data
                },
                'trendlines': {
                    'resistance': {'slope': 0, 'intercept': float(resistance_level), 'r_squared': 1.0},
                    'support': support_line
                },
                'volume_profile': volume_profile
            }

            # Calculate quality score
            quality_score = self._calculate_pattern_quality(pattern_data)

            # Update confidence with quality score
            pattern_data['confidence_score'] = quality_score

            # Filter out low-quality patterns (below 0.5)
            if quality_score >= 0.5:
                patterns.append(pattern_data)

        return patterns

    def detect_descending_triangle(self) -> List[Dict]:
        """Descending Triangle: Falling resistance, flat support (bearish)"""
        patterns = []

        if len(self.df) < self.min_pattern_length:
            return patterns

        for i in range(len(self.df) - self.min_pattern_length):
            window = self.df.iloc[i:i + self.min_pattern_length]
            start_idx = self.df.index[i]  # Pattern starting index

            window_peaks = window[window['is_peak']]
            window_troughs = window[window['is_trough']]

            if len(window_peaks) < 2 or len(window_troughs) < 2:
                continue

            # Check if support is flat
            trough_prices = window_troughs['low'].values
            trough_std = np.std(trough_prices)
            trough_mean = np.mean(trough_prices)

            if trough_std / trough_mean > 0.02:
                continue

            # Check if resistance is falling
            peak_indices = window_peaks.index.values
            peak_prices = window_peaks['high'].values
            resistance_line = self._calculate_trendline(peak_indices, peak_prices, start_idx)

            if not resistance_line or resistance_line['slope'] >= 0:
                continue

            # Filter low-quality trendlines (R² < 0.7)
            if resistance_line['r_squared'] < 0.7:
                continue

            support_level = trough_mean
            pattern_height = peak_prices[-1] - support_level

            # Analyze volume profile
            volume_profile = self._analyze_volume_profile(window)

            # Collect peaks and troughs
            peaks_data = [{
                'timestamp': str(window_peaks.iloc[j]['timestamp']),
                'price': float(window_peaks.iloc[j]['high']),
                'index': int(window_peaks.index[j])
            } for j in range(len(window_peaks))]

            troughs_data = [{
                'timestamp': str(window_troughs.iloc[j]['timestamp']),
                'price': float(window_troughs.iloc[j]['low']),
                'index': int(window_troughs.index[j])
            } for j in range(len(window_troughs))]

            # Build pattern data
            pattern_data = {
                'pattern_name': 'Descending Triangle',
                'pattern_type': 'continuation',
                'signal': 'bearish',
                'start_date': window.iloc[0]['timestamp'],
                'end_date': window.iloc[-1]['timestamp'],
                'breakout_price': float(support_level),
                'target_price': float(support_level - pattern_height),
                'stop_loss': float(peak_prices[-1]),
                'confidence_score': 0.70,
                'key_points': {
                    'support_level': float(support_level),
                    'resistance_slope': resistance_line['slope'],
                    'peaks': peaks_data,
                    'troughs': troughs_data
                },
                'trendlines': {
                    'support': {'slope': 0, 'intercept': float(support_level), 'r_squared': 1.0},
                    'resistance': resistance_line
                },
                'volume_profile': volume_profile
            }

            # Calculate quality score
            quality_score = self._calculate_pattern_quality(pattern_data)

            # Update confidence with quality score
            pattern_data['confidence_score'] = quality_score

            # Filter out low-quality patterns (below 0.5)
            if quality_score >= 0.5:
                patterns.append(pattern_data)

        return patterns

    def detect_symmetrical_triangle(self) -> List[Dict]:
        """Symmetrical Triangle: Converging trendlines (neutral, breakout determines direction)"""
        patterns = []

        if len(self.df) < self.min_pattern_length:
            return patterns

        for i in range(len(self.df) - self.min_pattern_length):
            window = self.df.iloc[i:i + self.min_pattern_length]
            start_idx = self.df.index[i]  # Pattern starting index

            window_peaks = window[window['is_peak']]
            window_troughs = window[window['is_trough']]

            if len(window_peaks) < 2 or len(window_troughs) < 2:
                continue

            # Calculate resistance line (should be descending)
            peak_indices = window_peaks.index.values
            peak_prices = window_peaks['high'].values
            resistance_line = self._calculate_trendline(peak_indices, peak_prices, start_idx)

            # Calculate support line (should be ascending)
            trough_indices = window_troughs.index.values
            trough_prices = window_troughs['low'].values
            support_line = self._calculate_trendline(trough_indices, trough_prices, start_idx)

            if not resistance_line or not support_line:
                continue

            # Lines should be converging
            if resistance_line['slope'] >= 0 or support_line['slope'] <= 0:
                continue

            # Filter low-quality trendlines (R² < 0.7)
            if resistance_line['r_squared'] < 0.7 or support_line['r_squared'] < 0.7:
                continue

            mid_price = (peak_prices[-1] + trough_prices[-1]) / 2
            pattern_height = peak_prices[0] - trough_prices[0]

            # Analyze volume profile
            volume_profile = self._analyze_volume_profile(window)

            # Collect all peaks and troughs with their timestamps and prices
            peaks_data = [{
                'timestamp': str(window_peaks.iloc[j]['timestamp']),
                'price': float(window_peaks.iloc[j]['high']),
                'index': int(window_peaks.index[j])
            } for j in range(len(window_peaks))]

            troughs_data = [{
                'timestamp': str(window_troughs.iloc[j]['timestamp']),
                'price': float(window_troughs.iloc[j]['low']),
                'index': int(window_troughs.index[j])
            } for j in range(len(window_troughs))]

            # Build pattern data
            pattern_data = {
                'pattern_name': 'Symmetrical Triangle',
                'pattern_type': 'continuation',
                'signal': 'neutral',
                'start_date': window.iloc[0]['timestamp'],
                'end_date': window.iloc[-1]['timestamp'],
                'breakout_price': float(mid_price),
                'target_price': float(mid_price + pattern_height * 0.5),
                'stop_loss': float(trough_prices[-1]),
                'confidence_score': 0.65,
                'key_points': {
                    'apex_estimate': str(window.iloc[-1]['timestamp']),
                    'peaks': peaks_data,
                    'troughs': troughs_data
                },
                'trendlines': {
                    'resistance': resistance_line,
                    'support': support_line
                },
                'volume_profile': volume_profile
            }

            # Calculate quality score
            quality_score = self._calculate_pattern_quality(pattern_data)

            # Update confidence with quality score
            pattern_data['confidence_score'] = quality_score

            # Filter out low-quality patterns (below 0.5)
            if quality_score >= 0.5:
                patterns.append(pattern_data)

        return patterns

    # ==================== CONTINUATION PATTERNS ====================

    def detect_cup_and_handle(self) -> List[Dict]:
        """Cup and Handle: U-shaped recovery with small consolidation (bullish)"""
        patterns = []

        if len(self.df) < 30:  # Minimum 30 candles
            return patterns

        for i in range(len(self.df) - 30):
            window = self.df.iloc[i:i + 30]
            start_idx = self.df.index[i]  # Pattern starting index

            # Find the U-shape (cup)
            window_lows = window['low'].values
            min_idx = np.argmin(window_lows)

            if min_idx < 5 or min_idx > 20:  # Bottom should be in middle region
                continue

            left_rim = window.iloc[0]['high']
            right_rim = window.iloc[-1]['high']
            bottom = window_lows[min_idx]

            # Rims should be at similar height
            if abs(left_rim - right_rim) / left_rim > 0.05:
                continue

            # Cup depth should be significant (at least 10%)
            cup_depth = left_rim - bottom
            if cup_depth / left_rim < 0.10:
                continue

            # Look for handle (small consolidation near right rim)
            handle_window = window.iloc[-10:]
            handle_depth = handle_window['high'].max() - handle_window['low'].min()

            # Handle should be shallow (< 50% of cup depth)
            if handle_depth > cup_depth * 0.5:
                continue

            patterns.append({
                'pattern_name': 'Cup and Handle',
                'pattern_type': 'continuation',
                'signal': 'bullish',
                'start_date': window.iloc[0]['timestamp'],
                'end_date': window.iloc[-1]['timestamp'],
                'breakout_price': float(right_rim),
                'target_price': float(right_rim + cup_depth),
                'stop_loss': float(handle_window['low'].min()),
                'confidence_score': 0.75,
                'key_points': {
                    'cup_bottom': {'timestamp': str(window.iloc[min_idx]['timestamp']), 'price': float(bottom)},
                    'cup_depth': float(cup_depth),
                    'handle_depth': float(handle_depth)
                },
                'trendlines': {}
            })

        return patterns

    def detect_flag(self) -> List[Dict]:
        """Flag: Sharp move followed by parallel consolidation (continuation)"""
        patterns = []

        if len(self.df) < 15:
            return patterns

        for i in range(10, len(self.df) - 5):
            # Look for sharp move (pole)
            pole_window = self.df.iloc[i-10:i]
            pole_move = pole_window.iloc[-1]['close'] - pole_window.iloc[0]['close']
            pole_pct = pole_move / pole_window.iloc[0]['close']

            # Pole must be significant (> 10%)
            if abs(pole_pct) < 0.10:
                continue

            # Flag consolidation
            flag_window = self.df.iloc[i:i+5]
            flag_range = flag_window['high'].max() - flag_window['low'].min()
            flag_pct = flag_range / flag_window.iloc[0]['close']

            # Flag should be small consolidation (< 5%)
            if flag_pct > 0.05:
                continue

            is_bullish = pole_pct > 0
            signal = 'bullish' if is_bullish else 'bearish'

            patterns.append({
                'pattern_name': f'{signal.capitalize()} Flag',
                'pattern_type': 'continuation',
                'signal': signal,
                'start_date': pole_window.iloc[0]['timestamp'],
                'end_date': flag_window.iloc[-1]['timestamp'],
                'breakout_price': float(flag_window['high'].max() if is_bullish else flag_window['low'].min()),
                'target_price': float(pole_window.iloc[-1]['close'] + pole_move if is_bullish else pole_window.iloc[-1]['close'] + pole_move),
                'stop_loss': float(flag_window['low'].min() if is_bullish else flag_window['high'].max()),
                'confidence_score': 0.70,
                'key_points': {
                    'pole_height': float(abs(pole_move)),
                    'pole_percent': float(pole_pct)
                },
                'trendlines': {}
            })

        return patterns

    def detect_pennant(self) -> List[Dict]:
        """Pennant: Sharp move followed by converging consolidation (continuation)"""
        patterns = []

        if len(self.df) < 20:
            return patterns

        for i in range(10, len(self.df) - 10):
            # Sharp move (pole)
            pole_window = self.df.iloc[i-10:i]
            pole_move = pole_window.iloc[-1]['close'] - pole_window.iloc[0]['close']
            pole_pct = pole_move / pole_window.iloc[0]['close']

            if abs(pole_pct) < 0.10:
                continue

            # Pennant (converging triangle)
            pennant_window = self.df.iloc[i:i+10]
            pennant_peaks = pennant_window[pennant_window['is_peak']]
            pennant_troughs = pennant_window[pennant_window['is_trough']]

            if len(pennant_peaks) < 2 or len(pennant_troughs) < 2:
                continue

            # Check if range is converging
            early_range = pennant_window.iloc[:5]['high'].max() - pennant_window.iloc[:5]['low'].min()
            late_range = pennant_window.iloc[5:]['high'].max() - pennant_window.iloc[5:]['low'].min()

            if late_range >= early_range:  # Should be converging
                continue

            is_bullish = pole_pct > 0
            signal = 'bullish' if is_bullish else 'bearish'

            patterns.append({
                'pattern_name': f'{signal.capitalize()} Pennant',
                'pattern_type': 'continuation',
                'signal': signal,
                'start_date': pole_window.iloc[0]['timestamp'],
                'end_date': pennant_window.iloc[-1]['timestamp'],
                'breakout_price': float(pennant_window.iloc[-1]['close']),
                'target_price': float(pennant_window.iloc[-1]['close'] + pole_move),
                'stop_loss': float(pennant_window['low'].min() if is_bullish else pennant_window['high'].max()),
                'confidence_score': 0.70,
                'key_points': {
                    'pole_height': float(abs(pole_move))
                },
                'trendlines': {}
            })

        return patterns

    def detect_rising_wedge(self) -> List[Dict]:
        """Rising Wedge: Converging uptrend lines (bearish reversal/continuation)"""
        patterns = []

        if len(self.df) < self.min_pattern_length:
            return patterns

        for i in range(len(self.df) - self.min_pattern_length):
            window = self.df.iloc[i:i + self.min_pattern_length]
            start_idx = self.df.index[i]  # Pattern starting index

            window_peaks = window[window['is_peak']]
            window_troughs = window[window['is_trough']]

            if len(window_peaks) < 2 or len(window_troughs) < 2:
                continue

            # Both lines should be rising
            peak_indices = window_peaks.index.values
            peak_prices = window_peaks['high'].values
            resistance_line = self._calculate_trendline(peak_indices, peak_prices, start_idx)

            trough_indices = window_troughs.index.values
            trough_prices = window_troughs['low'].values
            support_line = self._calculate_trendline(trough_indices, trough_prices, start_idx)

            if not resistance_line or not support_line:
                continue

            # Both should have positive slope, and converging
            if resistance_line['slope'] <= 0 or support_line['slope'] <= 0:
                continue

            if support_line['slope'] >= resistance_line['slope']:  # Must be converging
                continue

            # Filter low-quality trendlines (R² < 0.7)
            if resistance_line['r_squared'] < 0.7 or support_line['r_squared'] < 0.7:
                continue

            # Analyze volume profile
            volume_profile = self._analyze_volume_profile(window)

            # Check prior trend (should be uptrend for bearish rising wedge reversal)
            start_idx = window.index[0]
            prior_trend = self._detect_prior_trend(start_idx, start_idx)

            # Collect all peaks and troughs with their timestamps and prices
            peaks_data = [{
                'timestamp': str(window_peaks.iloc[j]['timestamp']),
                'price': float(window_peaks.iloc[j]['high']),
                'index': int(window_peaks.index[j])
            } for j in range(len(window_peaks))]

            troughs_data = [{
                'timestamp': str(window_troughs.iloc[j]['timestamp']),
                'price': float(window_troughs.iloc[j]['low']),
                'index': int(window_troughs.index[j])
            } for j in range(len(window_troughs))]

            # Build pattern data
            pattern_data = {
                'pattern_name': 'Rising Wedge',
                'pattern_type': 'reversal',
                'signal': 'bearish',
                'start_date': window.iloc[0]['timestamp'],
                'end_date': window.iloc[-1]['timestamp'],
                'breakout_price': float(trough_prices[-1]),
                'target_price': float(trough_prices[-1] - (peak_prices[0] - trough_prices[0])),
                'stop_loss': float(peak_prices[-1]),
                'confidence_score': 0.65,
                'key_points': {
                    'peaks': peaks_data,
                    'troughs': troughs_data
                },
                'trendlines': {
                    'resistance': resistance_line,
                    'support': support_line
                },
                'volume_profile': volume_profile,
                'prior_trend': prior_trend
            }

            # Calculate quality score
            quality_score = self._calculate_pattern_quality(pattern_data)

            # Update confidence with quality score
            pattern_data['confidence_score'] = quality_score

            # Filter out low-quality patterns (below 0.5)
            if quality_score >= 0.5:
                patterns.append(pattern_data)

        return patterns

    def detect_falling_wedge(self) -> List[Dict]:
        """Falling Wedge: Converging downtrend lines (bullish reversal/continuation)"""
        patterns = []

        if len(self.df) < self.min_pattern_length:
            return patterns

        for i in range(len(self.df) - self.min_pattern_length):
            window = self.df.iloc[i:i + self.min_pattern_length]
            start_idx = self.df.index[i]  # Pattern starting index

            window_peaks = window[window['is_peak']]
            window_troughs = window[window['is_trough']]

            if len(window_peaks) < 2 or len(window_troughs) < 2:
                continue

            # Both lines should be falling
            peak_indices = window_peaks.index.values
            peak_prices = window_peaks['high'].values
            resistance_line = self._calculate_trendline(peak_indices, peak_prices, start_idx)

            trough_indices = window_troughs.index.values
            trough_prices = window_troughs['low'].values
            support_line = self._calculate_trendline(trough_indices, trough_prices, start_idx)

            if not resistance_line or not support_line:
                continue

            # Both should have negative slope, and converging
            if resistance_line['slope'] >= 0 or support_line['slope'] >= 0:
                continue

            if resistance_line['slope'] <= support_line['slope']:  # Must be converging
                continue

            # Filter low-quality trendlines (R² < 0.7)
            if resistance_line['r_squared'] < 0.7 or support_line['r_squared'] < 0.7:
                continue

            # Analyze volume profile
            volume_profile = self._analyze_volume_profile(window)

            # Check prior trend (should be downtrend for bullish falling wedge reversal)
            start_idx = window.index[0]
            prior_trend = self._detect_prior_trend(start_idx, start_idx)

            # Collect all peaks and troughs with their timestamps and prices
            peaks_data = [{
                'timestamp': str(window_peaks.iloc[j]['timestamp']),
                'price': float(window_peaks.iloc[j]['high']),
                'index': int(window_peaks.index[j])
            } for j in range(len(window_peaks))]

            troughs_data = [{
                'timestamp': str(window_troughs.iloc[j]['timestamp']),
                'price': float(window_troughs.iloc[j]['low']),
                'index': int(window_troughs.index[j])
            } for j in range(len(window_troughs))]

            # Build pattern data
            pattern_data = {
                'pattern_name': 'Falling Wedge',
                'pattern_type': 'reversal',
                'signal': 'bullish',
                'start_date': window.iloc[0]['timestamp'],
                'end_date': window.iloc[-1]['timestamp'],
                'breakout_price': float(peak_prices[-1]),
                'target_price': float(peak_prices[-1] + (peak_prices[0] - trough_prices[0])),
                'stop_loss': float(trough_prices[-1]),
                'confidence_score': 0.65,
                'key_points': {
                    'peaks': peaks_data,
                    'troughs': troughs_data
                },
                'trendlines': {
                    'resistance': resistance_line,
                    'support': support_line
                },
                'volume_profile': volume_profile,
                'prior_trend': prior_trend
            }

            # Calculate quality score
            quality_score = self._calculate_pattern_quality(pattern_data)

            # Update confidence with quality score
            pattern_data['confidence_score'] = quality_score

            # Filter out low-quality patterns (below 0.5)
            if quality_score >= 0.5:
                patterns.append(pattern_data)

        return patterns
    def detect_triple_top(self) -> List[Dict]:
        """Triple Top: Three peaks at similar levels (bearish reversal)"""
        patterns = []
    
        if len(self.df) < self.min_pattern_length:
            return patterns
    
        peaks_list = self.peaks.index.tolist()
    
        # Need at least 3 peaks
        if len(peaks_list) < 3:
            return patterns
    
        for i in range(len(peaks_list) - 2):
            peak1_idx = peaks_list[i]
            peak2_idx = peaks_list[i + 1]
            peak3_idx = peaks_list[i + 2]
            start_idx = peak1_idx  # Pattern starting index

            peak1_price = self.df.loc[peak1_idx, 'high']
            peak2_price = self.df.loc[peak2_idx, 'high']
            peak3_price = self.df.loc[peak3_idx, 'high']
    
            # All three peaks should be at similar levels (within 3%)
            avg_peak = (peak1_price + peak2_price + peak3_price) / 3
            tolerance = avg_peak * 0.03
    
            if (abs(peak1_price - avg_peak) > tolerance or
                    abs(peak2_price - avg_peak) > tolerance or
                    abs(peak3_price - avg_peak) > tolerance):
                continue
    
            # Find troughs between peaks
            troughs_between = self.troughs[(self.troughs.index > peak1_idx) &
                                           (self.troughs.index < peak3_idx)]
    
            if len(troughs_between) < 2:
                continue
    
            # Check pattern length
            pattern_start = peak1_idx
            pattern_end = peak3_idx
    
            if pattern_end - pattern_start < self.min_pattern_length:
                continue
    
            window = self.df.loc[pattern_start:pattern_end]
    
            # Neckline (support formed by troughs)
            trough_indices = troughs_between.index.values
            trough_prices = troughs_between['low'].values
            neckline = self._calculate_trendline(trough_indices, trough_prices, start_idx)
    
            if not neckline or neckline['r_squared'] < 0.5:
                continue
    
            # Analyze volume (should decline through pattern formation)
            volume_profile = self._analyze_volume_profile(window)
    
            # Check prior trend (should be uptrend for reversal)
            prior_trend = self._detect_prior_trend(pattern_start, pattern_end)
    
            # Build pattern data
            pattern_data = {
                'pattern_name': 'Triple Top',
                'pattern_type': 'reversal',
                'signal': 'bearish',
                'start_date': self.df.loc[pattern_start, 'timestamp'],
                'end_date': self.df.loc[pattern_end, 'timestamp'],
                'breakout_price': float(min(trough_prices)),
                'target_price': float(min(trough_prices) - (avg_peak - min(trough_prices))),
                'stop_loss': float(avg_peak * 1.02),
                'confidence_score': 0.70,
                'key_points': {
                    'peaks': [
                        {'timestamp': str(self.df.loc[peak1_idx, 'timestamp']),
                         'price': float(peak1_price), 'index': int(peak1_idx)},
                        {'timestamp': str(self.df.loc[peak2_idx, 'timestamp']),
                         'price': float(peak2_price), 'index': int(peak2_idx)},
                        {'timestamp': str(self.df.loc[peak3_idx, 'timestamp']),
                         'price': float(peak3_price), 'index': int(peak3_idx)}
                    ],
                    'troughs': [
                        {'timestamp': str(troughs_between.iloc[j]['timestamp']),
                         'price': float(troughs_between.iloc[j]['low']),
                         'index': int(troughs_between.index[j])}
                        for j in range(len(troughs_between))
                    ]
                },
                'trendlines': {
                    'neckline': neckline
                },
                'volume_profile': volume_profile,
                'prior_trend': prior_trend
            }
    
            # Calculate quality score
            quality_score = self._calculate_pattern_quality(pattern_data)
            pattern_data['confidence_score'] = quality_score
    
            if quality_score >= 0.5:
                patterns.append(pattern_data)
    
        return patterns
    
    
    def detect_triple_bottom(self) -> List[Dict]:
        """Triple Bottom: Three troughs at similar levels (bullish reversal)"""
        patterns = []
    
        if len(self.df) < self.min_pattern_length:
            return patterns
    
        troughs_list = self.troughs.index.tolist()
    
        if len(troughs_list) < 3:
            return patterns
    
        for i in range(len(troughs_list) - 2):
            trough1_idx = troughs_list[i]
            trough2_idx = troughs_list[i + 1]
            trough3_idx = troughs_list[i + 2]
            start_idx = trough1_idx  # Pattern starting index

            trough1_price = self.df.loc[trough1_idx, 'low']
            trough2_price = self.df.loc[trough2_idx, 'low']
            trough3_price = self.df.loc[trough3_idx, 'low']
    
            # All three troughs should be at similar levels (within 3%)
            avg_trough = (trough1_price + trough2_price + trough3_price) / 3
            tolerance = avg_trough * 0.03
    
            if (abs(trough1_price - avg_trough) > tolerance or
                    abs(trough2_price - avg_trough) > tolerance or
                    abs(trough3_price - avg_trough) > tolerance):
                continue
    
            # Find peaks between troughs
            peaks_between = self.peaks[(self.peaks.index > trough1_idx) &
                                       (self.peaks.index < trough3_idx)]
    
            if len(peaks_between) < 2:
                continue
    
            pattern_start = trough1_idx
            pattern_end = trough3_idx
    
            if pattern_end - pattern_start < self.min_pattern_length:
                continue
    
            window = self.df.loc[pattern_start:pattern_end]
    
            # Neckline (resistance formed by peaks)
            peak_indices = peaks_between.index.values
            peak_prices = peaks_between['high'].values
            neckline = self._calculate_trendline(peak_indices, peak_prices, start_idx)
    
            if not neckline or neckline['r_squared'] < 0.5:
                continue
    
            volume_profile = self._analyze_volume_profile(window)
            prior_trend = self._detect_prior_trend(pattern_start, pattern_end)
    
            pattern_data = {
                'pattern_name': 'Triple Bottom',
                'pattern_type': 'reversal',
                'signal': 'bullish',
                'start_date': self.df.loc[pattern_start, 'timestamp'],
                'end_date': self.df.loc[pattern_end, 'timestamp'],
                'breakout_price': float(max(peak_prices)),
                'target_price': float(max(peak_prices) + (max(peak_prices) - avg_trough)),
                'stop_loss': float(avg_trough * 0.98),
                'confidence_score': 0.70,
                'key_points': {
                    'troughs': [
                        {'timestamp': str(self.df.loc[trough1_idx, 'timestamp']),
                         'price': float(trough1_price), 'index': int(trough1_idx)},
                        {'timestamp': str(self.df.loc[trough2_idx, 'timestamp']),
                         'price': float(trough2_price), 'index': int(trough2_idx)},
                        {'timestamp': str(self.df.loc[trough3_idx, 'timestamp']),
                         'price': float(trough3_price), 'index': int(trough3_idx)}
                    ],
                    'peaks': [
                        {'timestamp': str(peaks_between.iloc[j]['timestamp']),
                         'price': float(peaks_between.iloc[j]['high']),
                         'index': int(peaks_between.index[j])}
                        for j in range(len(peaks_between))
                    ]
                },
                'trendlines': {
                    'neckline': neckline
                },
                'volume_profile': volume_profile,
                'prior_trend': prior_trend
            }
    
            quality_score = self._calculate_pattern_quality(pattern_data)
            pattern_data['confidence_score'] = quality_score
    
            if quality_score >= 0.5:
                patterns.append(pattern_data)
    
        return patterns
    
    
    def detect_rounding_top(self) -> List[Dict]:
        """Rounding Top (Dome): Gradual arc formation (bearish reversal)"""
        patterns = []
    
        if len(self.df) < self.min_pattern_length * 2:  # Needs longer window
            return patterns
    
        for i in range(len(self.df) - self.min_pattern_length * 2):
            window = self.df.iloc[i:i + self.min_pattern_length * 2]
            start_idx = self.df.index[i]  # Pattern starting index
    
            # Get highs in the window
            highs = window['high'].values
            indices = np.arange(len(highs))
    
            # Fit a polynomial (quadratic) to detect rounded shape
            try:
                from numpy.polynomial import polynomial as P
                coefs = P.polyfit(indices, highs, 2)
    
                # For rounding top, second-degree coefficient should be negative
                if coefs[2] >= 0:
                    continue
    
                # Calculate R² for fit quality
                fitted_values = P.polyval(indices, coefs)
                ss_res = np.sum((highs - fitted_values) ** 2)
                ss_tot = np.sum((highs - np.mean(highs)) ** 2)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
    
                if r_squared < 0.6:
                    continue
    
            except:
                continue
    
            # Find the peak (highest point)
            peak_idx = window['high'].idxmax()
            peak_price = window.loc[peak_idx, 'high']
    
            # Volume should typically decline during rounding
            volume_profile = self._analyze_volume_profile(window)
            prior_trend = self._detect_prior_trend(window.index[0], window.index[-1])
    
            pattern_data = {
                'pattern_name': 'Rounding Top',
                'pattern_type': 'reversal',
                'signal': 'bearish',
                'start_date': window.iloc[0]['timestamp'],
                'end_date': window.iloc[-1]['timestamp'],
                'breakout_price': float(window.iloc[-1]['close']),
                'target_price': float(window.iloc[-1]['close'] - (peak_price - window.iloc[0]['close'])),
                'stop_loss': float(peak_price * 1.02),
                'confidence_score': 0.60,
                'key_points': {
                    'peak': {
                        'timestamp': str(window.loc[peak_idx, 'timestamp']),
                        'price': float(peak_price),
                        'index': int(peak_idx)
                    },
                    'fit_quality': float(r_squared)
                },
                'trendlines': {
                    'polynomial_fit': {
                        'coefficients': [float(c) for c in coefs],
                        'r_squared': float(r_squared)
                    }
                },
                'volume_profile': volume_profile,
                'prior_trend': prior_trend
            }
    
            quality_score = self._calculate_pattern_quality(pattern_data)
            pattern_data['confidence_score'] = quality_score
    
            if quality_score >= 0.5:
                patterns.append(pattern_data)
    
        return patterns
    
    
    def detect_rounding_bottom(self) -> List[Dict]:
        """Rounding Bottom (Saucer): Gradual U-shape formation (bullish reversal)"""
        patterns = []
    
        if len(self.df) < self.min_pattern_length * 2:
            return patterns
    
        for i in range(len(self.df) - self.min_pattern_length * 2):
            window = self.df.iloc[i:i + self.min_pattern_length * 2]
            start_idx = self.df.index[i]  # Pattern starting index
    
            lows = window['low'].values
            indices = np.arange(len(lows))
    
            try:
                from numpy.polynomial import polynomial as P
                coefs = P.polyfit(indices, lows, 2)
    
                # For rounding bottom, second-degree coefficient should be positive
                if coefs[2] <= 0:
                    continue
    
                fitted_values = P.polyval(indices, coefs)
                ss_res = np.sum((lows - fitted_values) ** 2)
                ss_tot = np.sum((lows - np.mean(lows)) ** 2)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
    
                if r_squared < 0.6:
                    continue
    
            except:
                continue
    
            trough_idx = window['low'].idxmin()
            trough_price = window.loc[trough_idx, 'low']
    
            volume_profile = self._analyze_volume_profile(window)
            prior_trend = self._detect_prior_trend(window.index[0], window.index[-1])
    
            pattern_data = {
                'pattern_name': 'Rounding Bottom',
                'pattern_type': 'reversal',
                'signal': 'bullish',
                'start_date': window.iloc[0]['timestamp'],
                'end_date': window.iloc[-1]['timestamp'],
                'breakout_price': float(window.iloc[-1]['close']),
                'target_price': float(window.iloc[-1]['close'] + (window.iloc[0]['close'] - trough_price)),
                'stop_loss': float(trough_price * 0.98),
                'confidence_score': 0.60,
                'key_points': {
                    'trough': {
                        'timestamp': str(window.loc[trough_idx, 'timestamp']),
                        'price': float(trough_price),
                        'index': int(trough_idx)
                    },
                    'fit_quality': float(r_squared)
                },
                'trendlines': {
                    'polynomial_fit': {
                        'coefficients': [float(c) for c in coefs],
                        'r_squared': float(r_squared)
                    }
                },
                'volume_profile': volume_profile,
                'prior_trend': prior_trend
            }
    
            quality_score = self._calculate_pattern_quality(pattern_data)
            pattern_data['confidence_score'] = quality_score
    
            if quality_score >= 0.5:
                patterns.append(pattern_data)
    
        return patterns
    
    
    def detect_rectangle(self) -> List[Dict]:
        """Rectangle: Horizontal consolidation with parallel support/resistance"""
        patterns = []
    
        if len(self.df) < self.min_pattern_length:
            return patterns
    
        for i in range(len(self.df) - self.min_pattern_length):
            window = self.df.iloc[i:i + self.min_pattern_length]
            start_idx = self.df.index[i]  # Pattern starting index
    
            window_peaks = window[window['is_peak']]
            window_troughs = window[window['is_trough']]
    
            if len(window_peaks) < 2 or len(window_troughs) < 2:
                continue
    
            # Check if peaks are at similar levels (horizontal resistance)
            peak_prices = window_peaks['high'].values
            peak_avg = np.mean(peak_prices)
            peak_std = np.std(peak_prices)
    
            # Check if troughs are at similar levels (horizontal support)
            trough_prices = window_troughs['low'].values
            trough_avg = np.mean(trough_prices)
            trough_std = np.std(trough_prices)
    
            # Both should be relatively flat (low standard deviation)
            if peak_std > peak_avg * 0.02 or trough_std > trough_avg * 0.02:
                continue
    
            # Calculate trendlines
            peak_indices = window_peaks.index.values
            trough_indices = window_troughs.index.values
    
            resistance_line = self._calculate_trendline(peak_indices, peak_prices, start_idx)
            support_line = self._calculate_trendline(trough_indices, trough_prices, start_idx)
    
            if not resistance_line or not support_line:
                continue
    
            # Both slopes should be near zero (horizontal)
            if abs(resistance_line['slope']) > 0.1 or abs(support_line['slope']) > 0.1:
                continue
    
            volume_profile = self._analyze_volume_profile(window)
            prior_trend = self._detect_prior_trend(window.index[0], window.index[-1])
    
            # Signal depends on where price breaks out (unknown during formation)
            height = peak_avg - trough_avg
    
            pattern_data = {
                'pattern_name': 'Rectangle',
                'pattern_type': 'continuation',
                'signal': 'neutral',
                'start_date': window.iloc[0]['timestamp'],
                'end_date': window.iloc[-1]['timestamp'],
                'breakout_price': float(peak_avg),  # Potential upside breakout
                'target_price': float(peak_avg + height),  # If breaks up
                'stop_loss': float(trough_avg),
                'confidence_score': 0.65,
                'key_points': {
                    'resistance_level': float(peak_avg),
                    'support_level': float(trough_avg),
                    'height': float(height),
                    'peaks': [
                        {'timestamp': str(window_peaks.iloc[j]['timestamp']),
                         'price': float(window_peaks.iloc[j]['high']),
                         'index': int(window_peaks.index[j])}
                        for j in range(len(window_peaks))
                    ],
                    'troughs': [
                        {'timestamp': str(window_troughs.iloc[j]['timestamp']),
                         'price': float(window_troughs.iloc[j]['low']),
                         'index': int(window_troughs.index[j])}
                        for j in range(len(window_troughs))
                    ]
                },
                'trendlines': {
                    'resistance': resistance_line,
                    'support': support_line
                },
                'volume_profile': volume_profile,
                'prior_trend': prior_trend
            }
    
            quality_score = self._calculate_pattern_quality(pattern_data)
            pattern_data['confidence_score'] = quality_score
    
            if quality_score >= 0.5:
                patterns.append(pattern_data)
    
        return patterns
    
    
    def detect_ascending_channel(self) -> List[Dict]:
        """Ascending Channel: Uptrend with parallel support and resistance lines"""
        patterns = []
    
        if len(self.df) < self.min_pattern_length:
            return patterns
    
        for i in range(len(self.df) - self.min_pattern_length):
            window = self.df.iloc[i:i + self.min_pattern_length]
            start_idx = self.df.index[i]  # Pattern starting index
    
            window_peaks = window[window['is_peak']]
            window_troughs = window[window['is_trough']]
    
            if len(window_peaks) < 2 or len(window_troughs) < 2:
                continue
    
            # Calculate trendlines
            peak_indices = window_peaks.index.values
            peak_prices = window_peaks['high'].values
            resistance_line = self._calculate_trendline(peak_indices, peak_prices, start_idx)
    
            trough_indices = window_troughs.index.values
            trough_prices = window_troughs['low'].values
            support_line = self._calculate_trendline(trough_indices, trough_prices, start_idx)
    
            if not resistance_line or not support_line:
                continue
    
            # Both should have positive slope (uptrend)
            if resistance_line['slope'] <= 0 or support_line['slope'] <= 0:
                continue
    
            # Slopes should be similar (parallel)
            slope_diff = abs(resistance_line['slope'] - support_line['slope'])
            avg_slope = (resistance_line['slope'] + support_line['slope']) / 2
    
            if slope_diff > avg_slope * 0.3:  # 30% tolerance
                continue
    
            # Good fit quality
            if resistance_line['r_squared'] < 0.7 or support_line['r_squared'] < 0.7:
                continue
    
            volume_profile = self._analyze_volume_profile(window)
            prior_trend = self._detect_prior_trend(window.index[0], window.index[-1])
    
            pattern_data = {
                'pattern_name': 'Ascending Channel',
                'pattern_type': 'continuation',
                'signal': 'bullish',
                'start_date': window.iloc[0]['timestamp'],
                'end_date': window.iloc[-1]['timestamp'],
                'breakout_price': float(peak_prices[-1]),
                'target_price': float(peak_prices[-1] + (peak_prices[-1] - trough_prices[-1])),
                'stop_loss': float(trough_prices[-1]),
                'confidence_score': 0.70,
                'key_points': {
                    'peaks': [
                        {'timestamp': str(window_peaks.iloc[j]['timestamp']),
                         'price': float(window_peaks.iloc[j]['high']),
                         'index': int(window_peaks.index[j])}
                        for j in range(len(window_peaks))
                    ],
                    'troughs': [
                        {'timestamp': str(window_troughs.iloc[j]['timestamp']),
                         'price': float(window_troughs.iloc[j]['low']),
                         'index': int(window_troughs.index[j])}
                        for j in range(len(window_troughs))
                    ]
                },
                'trendlines': {
                    'resistance': resistance_line,
                    'support': support_line
                },
                'volume_profile': volume_profile,
                'prior_trend': prior_trend
            }
    
            quality_score = self._calculate_pattern_quality(pattern_data)
            pattern_data['confidence_score'] = quality_score
    
            if quality_score >= 0.5:
                patterns.append(pattern_data)
    
        return patterns
    
    
    def detect_descending_channel(self) -> List[Dict]:
        """Descending Channel: Downtrend with parallel support and resistance lines"""
        patterns = []
    
        if len(self.df) < self.min_pattern_length:
            return patterns
    
        for i in range(len(self.df) - self.min_pattern_length):
            window = self.df.iloc[i:i + self.min_pattern_length]
            start_idx = self.df.index[i]  # Pattern starting index
    
            window_peaks = window[window['is_peak']]
            window_troughs = window[window['is_trough']]
    
            if len(window_peaks) < 2 or len(window_troughs) < 2:
                continue
    
            peak_indices = window_peaks.index.values
            peak_prices = window_peaks['high'].values
            resistance_line = self._calculate_trendline(peak_indices, peak_prices, start_idx)
    
            trough_indices = window_troughs.index.values
            trough_prices = window_troughs['low'].values
            support_line = self._calculate_trendline(trough_indices, trough_prices, start_idx)
    
            if not resistance_line or not support_line:
                continue
    
            # Both should have negative slope (downtrend)
            if resistance_line['slope'] >= 0 or support_line['slope'] >= 0:
                continue
    
            # Slopes should be similar (parallel)
            slope_diff = abs(resistance_line['slope'] - support_line['slope'])
            avg_slope = abs((resistance_line['slope'] + support_line['slope']) / 2)
    
            if slope_diff > avg_slope * 0.3:
                continue
    
            if resistance_line['r_squared'] < 0.7 or support_line['r_squared'] < 0.7:
                continue
    
            volume_profile = self._analyze_volume_profile(window)
            prior_trend = self._detect_prior_trend(window.index[0], window.index[-1])
    
            pattern_data = {
                'pattern_name': 'Descending Channel',
                'pattern_type': 'continuation',
                'signal': 'bearish',
                'start_date': window.iloc[0]['timestamp'],
                'end_date': window.iloc[-1]['timestamp'],
                'breakout_price': float(trough_prices[-1]),
                'target_price': float(trough_prices[-1] - (peak_prices[-1] - trough_prices[-1])),
                'stop_loss': float(peak_prices[-1]),
                'confidence_score': 0.70,
                'key_points': {
                    'peaks': [
                        {'timestamp': str(window_peaks.iloc[j]['timestamp']),
                         'price': float(window_peaks.iloc[j]['high']),
                         'index': int(window_peaks.index[j])}
                        for j in range(len(window_peaks))
                    ],
                    'troughs': [
                        {'timestamp': str(window_troughs.iloc[j]['timestamp']),
                         'price': float(window_troughs.iloc[j]['low']),
                         'index': int(window_troughs.index[j])}
                        for j in range(len(window_troughs))
                    ]
                },
                'trendlines': {
                    'resistance': resistance_line,
                    'support': support_line
                },
                'volume_profile': volume_profile,
                'prior_trend': prior_trend
            }
    
            quality_score = self._calculate_pattern_quality(pattern_data)
            pattern_data['confidence_score'] = quality_score
    
            if quality_score >= 0.5:
                patterns.append(pattern_data)
    
        return patterns
    
