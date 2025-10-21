"""
Extended Chart Pattern Detection Methods
To be added to ChartPatternDetector class
"""

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
        neckline = self._calculate_trendline(trough_indices, trough_prices)

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
        neckline = self._calculate_trendline(peak_indices, peak_prices)

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

        resistance_line = self._calculate_trendline(peak_indices, peak_prices)
        support_line = self._calculate_trendline(trough_indices, trough_prices)

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

        window_peaks = window[window['is_peak']]
        window_troughs = window[window['is_trough']]

        if len(window_peaks) < 2 or len(window_troughs) < 2:
            continue

        # Calculate trendlines
        peak_indices = window_peaks.index.values
        peak_prices = window_peaks['high'].values
        resistance_line = self._calculate_trendline(peak_indices, peak_prices)

        trough_indices = window_troughs.index.values
        trough_prices = window_troughs['low'].values
        support_line = self._calculate_trendline(trough_indices, trough_prices)

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

        window_peaks = window[window['is_peak']]
        window_troughs = window[window['is_trough']]

        if len(window_peaks) < 2 or len(window_troughs) < 2:
            continue

        peak_indices = window_peaks.index.values
        peak_prices = window_peaks['high'].values
        resistance_line = self._calculate_trendline(peak_indices, peak_prices)

        trough_indices = window_troughs.index.values
        trough_prices = window_troughs['low'].values
        support_line = self._calculate_trendline(trough_indices, trough_prices)

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
