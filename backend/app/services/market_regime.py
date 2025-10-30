"""
Market Regime Detection Service

Detects market regimes using TCR (Trend/Channel/Range) framework combined with MA slope analysis.
Also includes volatility regime detection.

Regimes:
- Trend: Strong directional movement (ADX > 25)
- Channel: Moderate directional movement (ADX 20-25)
- Range: Sideways movement (ADX < 20)

Direction:
- Bullish: MA20 and MA50 slopes positive
- Bearish: MA20 and MA50 slopes negative
- Neutral: Mixed signals

Volatility:
- Low: ATR below 33rd percentile
- Normal: ATR between 33rd and 67th percentile
- High: ATR above 67th percentile
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.stock import StockPrice


class MarketRegimeService:
    """Service for detecting market regimes using TCR + MA + Volatility"""

    def __init__(self, db: Session):
        self.db = db

    def calculate_adx(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        Calculate Average Directional Index (ADX)

        ADX measures trend strength on a scale of 0-100:
        - 0-20: Weak trend or ranging market
        - 20-25: Moderate trend (channeling)
        - 25-50: Strong trend
        - 50-100: Very strong trend

        Args:
            df: DataFrame with high, low, close columns
            period: Lookback period (default: 14)

        Returns:
            DataFrame with ADX, +DI, -DI columns added
        """
        # Calculate True Range
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = abs(df['high'] - df['close'].shift(1))
        df['low_close'] = abs(df['low'] - df['close'].shift(1))
        df['true_range'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)

        # Calculate Directional Movement
        df['up_move'] = df['high'] - df['high'].shift(1)
        df['down_move'] = df['low'].shift(1) - df['low']

        # Positive and Negative Directional Movement
        df['plus_dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
        df['minus_dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)

        # Smoothed TR and DM
        df['atr'] = df['true_range'].rolling(window=period, min_periods=1).mean()
        df['plus_di'] = 100 * (df['plus_dm'].rolling(window=period, min_periods=1).mean() / df['atr'])
        df['minus_di'] = 100 * (df['minus_dm'].rolling(window=period, min_periods=1).mean() / df['atr'])

        # Calculate DX and ADX
        df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
        df['adx'] = df['dx'].rolling(window=period, min_periods=1).mean()

        # Clean up intermediate columns
        df.drop(['high_low', 'high_close', 'low_close', 'true_range',
                 'up_move', 'down_move', 'plus_dm', 'minus_dm', 'dx'], axis=1, inplace=True)

        return df

    def calculate_ma_slope(self, series: pd.Series, period: int = 5) -> float:
        """
        Calculate the slope of a moving average

        Uses linear regression on the last 'period' points to determine slope.
        Positive slope = upward movement, Negative slope = downward movement

        Args:
            series: Price series (e.g., MA20, MA50)
            period: Number of points to use for slope calculation (default: 5)

        Returns:
            Slope value (positive = up, negative = down)
        """
        if len(series) < period:
            return 0.0

        # Use last 'period' points
        y = series.iloc[-period:].values
        x = np.arange(len(y))

        # Linear regression: y = mx + b, we only need m (slope)
        slope = np.polyfit(x, y, 1)[0]

        # Normalize by price to get percentage slope
        avg_price = np.mean(y)
        if avg_price > 0:
            slope_pct = (slope / avg_price) * 100
        else:
            slope_pct = 0.0

        return slope_pct

    def calculate_moving_averages(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate MA20 and MA50

        Args:
            df: DataFrame with close prices

        Returns:
            DataFrame with ma20 and ma50 columns added
        """
        df['ma20'] = df['close'].rolling(window=20, min_periods=1).mean()
        df['ma50'] = df['close'].rolling(window=50, min_periods=1).mean()
        return df

    def detect_tcr_regime(
        self,
        adx: float,
        plus_di: float,
        minus_di: float,
        ma20_slope: float,
        ma50_slope: float
    ) -> Dict[str, str]:
        """
        Detect TCR regime and direction

        Args:
            adx: Average Directional Index value
            plus_di: Positive Directional Indicator
            minus_di: Negative Directional Indicator
            ma20_slope: Slope of 20-period MA (percentage)
            ma50_slope: Slope of 50-period MA (percentage)

        Returns:
            Dict with regime, direction, and full_regime
        """
        # Determine market structure (TCR)
        if adx >= 25:
            regime = 'trend'
        elif adx >= 20:
            regime = 'channel'
        else:
            regime = 'range'

        # Determine direction using both DI and MA slopes
        # MA slopes have more weight for reliability
        slope_threshold = 0.05  # 0.05% per day threshold

        # Direction signals
        di_bullish = plus_di > minus_di
        di_bearish = minus_di > plus_di
        ma20_bullish = ma20_slope > slope_threshold
        ma20_bearish = ma20_slope < -slope_threshold
        ma50_bullish = ma50_slope > slope_threshold
        ma50_bearish = ma50_slope < -slope_threshold

        # Combine signals (MA slopes are primary, DI is confirmatory)
        if ma20_bullish and ma50_bullish and di_bullish:
            direction = 'bullish'
        elif ma20_bearish and ma50_bearish and di_bearish:
            direction = 'bearish'
        elif ma20_bullish and di_bullish:
            direction = 'bullish_weak'  # MA50 not confirming
        elif ma20_bearish and di_bearish:
            direction = 'bearish_weak'  # MA50 not confirming
        else:
            direction = 'neutral'

        # Create full regime description
        full_regime = f"{direction}_{regime}"

        return {
            'regime': regime,
            'direction': direction,
            'full_regime': full_regime
        }

    def calculate_volatility_percentile(self, atr_series: pd.Series, lookback: int = 100) -> float:
        """
        Calculate ATR percentile to determine volatility regime

        Args:
            atr_series: Series of ATR values
            lookback: Number of periods to use for percentile calculation

        Returns:
            Percentile value (0-100)
        """
        if len(atr_series) < lookback:
            lookback = len(atr_series)

        if lookback < 2:
            return 50.0  # Default to middle if not enough data

        recent_atr = atr_series.iloc[-lookback:]
        current_atr = atr_series.iloc[-1]

        # Calculate percentile rank
        percentile = (recent_atr < current_atr).sum() / len(recent_atr) * 100

        return percentile

    def detect_volatility_regime(self, atr_percentile: float) -> str:
        """
        Classify volatility regime based on ATR percentile

        Args:
            atr_percentile: ATR percentile (0-100)

        Returns:
            Volatility regime: 'low_vol', 'normal_vol', or 'high_vol'
        """
        if atr_percentile < 33:
            return 'low_vol'
        elif atr_percentile < 67:
            return 'normal_vol'
        else:
            return 'high_vol'

    def get_regime_recommendation(
        self,
        regime: str,
        direction: str,
        volatility: str
    ) -> Dict[str, str]:
        """
        Provide trading recommendations based on detected regime

        Args:
            regime: TCR regime (trend/channel/range)
            direction: Direction (bullish/bearish/neutral)
            volatility: Volatility regime (low_vol/normal_vol/high_vol)

        Returns:
            Dict with recommendation, reasoning, and risk_level
        """
        recommendations = {
            ('trend', 'bullish', 'normal_vol'): {
                'recommendation': 'Strong Buy - Follow the trend',
                'reasoning': 'Strong uptrend with normal volatility - ideal for momentum trades',
                'risk_level': 'medium',
                'suggested_strategy': 'Momentum/Trend Following'
            },
            ('trend', 'bullish', 'high_vol'): {
                'recommendation': 'Buy with Caution - Volatile trend',
                'reasoning': 'Strong uptrend but high volatility - use wider stops',
                'risk_level': 'high',
                'suggested_strategy': 'Momentum with wider stops'
            },
            ('trend', 'bullish', 'low_vol'): {
                'recommendation': 'Buy - Steady trend',
                'reasoning': 'Stable uptrend with low volatility - safe momentum play',
                'risk_level': 'low',
                'suggested_strategy': 'Trend Following'
            },
            ('trend', 'bearish', 'normal_vol'): {
                'recommendation': 'Strong Sell or Short',
                'reasoning': 'Strong downtrend with normal volatility',
                'risk_level': 'medium',
                'suggested_strategy': 'Short/Avoid'
            },
            ('trend', 'bearish', 'high_vol'): {
                'recommendation': 'Avoid or Short with Caution',
                'reasoning': 'Strong downtrend with high volatility - risky environment',
                'risk_level': 'high',
                'suggested_strategy': 'Stay in cash or hedge'
            },
            ('range', 'neutral', 'low_vol'): {
                'recommendation': 'Range Trading - Buy support, sell resistance',
                'reasoning': 'Sideways market with low volatility - ideal for mean reversion',
                'risk_level': 'low',
                'suggested_strategy': 'Mean Reversion'
            },
            ('range', 'neutral', 'high_vol'): {
                'recommendation': 'Avoid - Choppy market',
                'reasoning': 'Ranging market with high volatility - difficult to trade',
                'risk_level': 'high',
                'suggested_strategy': 'Stay in cash'
            },
            ('channel', 'bullish', 'normal_vol'): {
                'recommendation': 'Buy pullbacks to channel bottom',
                'reasoning': 'Upward channel - buy dips, sell rallies',
                'risk_level': 'medium',
                'suggested_strategy': 'Channel Trading'
            },
            ('channel', 'bearish', 'normal_vol'): {
                'recommendation': 'Short rallies to channel top',
                'reasoning': 'Downward channel - short rallies',
                'risk_level': 'medium',
                'suggested_strategy': 'Short channel rallies'
            },
        }

        # Try exact match
        key = (regime, direction.replace('_weak', ''), volatility)
        if key in recommendations:
            return recommendations[key]

        # Fallback recommendations
        if regime == 'trend' and 'bullish' in direction:
            return {
                'recommendation': 'Buy - Uptrend detected',
                'reasoning': f'Market in {direction} {regime}',
                'risk_level': 'medium',
                'suggested_strategy': 'Trend Following'
            }
        elif regime == 'trend' and 'bearish' in direction:
            return {
                'recommendation': 'Sell or Short',
                'reasoning': f'Market in {direction} {regime}',
                'risk_level': 'medium',
                'suggested_strategy': 'Avoid or Short'
            }
        else:
            return {
                'recommendation': 'Wait for clearer signal',
                'reasoning': f'Market regime: {regime}, direction: {direction}, volatility: {volatility}',
                'risk_level': 'medium',
                'suggested_strategy': 'Wait and observe'
            }

    def detect_market_regime(
        self,
        stock_id: int,
        lookback_periods: int = 100
    ) -> Dict:
        """
        Main function to detect market regime for a stock

        Args:
            stock_id: Stock ID
            lookback_periods: Number of periods to analyze (default: 100)

        Returns:
            Dict with complete regime analysis
        """
        # Fetch price data
        prices = self.db.query(StockPrice).filter(
            StockPrice.stock_id == stock_id
        ).order_by(StockPrice.timestamp.desc()).limit(lookback_periods).all()

        if len(prices) < 50:
            raise ValueError(f"Insufficient data: need at least 50 bars, got {len(prices)}")

        # Convert to DataFrame
        df = pd.DataFrame([
            {
                'timestamp': p.timestamp,
                'open': float(p.open),
                'high': float(p.high),
                'low': float(p.low),
                'close': float(p.close),
                'volume': float(p.volume)
            }
            for p in reversed(prices)
        ])

        # Calculate indicators
        df = self.calculate_moving_averages(df)
        df = self.calculate_adx(df, period=14)

        # Get current values
        current_adx = float(df['adx'].iloc[-1])
        current_plus_di = float(df['plus_di'].iloc[-1])
        current_minus_di = float(df['minus_di'].iloc[-1])
        current_atr = float(df['atr'].iloc[-1])
        current_ma20 = float(df['ma20'].iloc[-1])
        current_ma50 = float(df['ma50'].iloc[-1])
        current_price = float(df['close'].iloc[-1])

        # Calculate MA slopes
        ma20_slope = self.calculate_ma_slope(df['ma20'], period=5)
        ma50_slope = self.calculate_ma_slope(df['ma50'], period=5)

        # Detect TCR regime
        tcr_result = self.detect_tcr_regime(
            adx=current_adx,
            plus_di=current_plus_di,
            minus_di=current_minus_di,
            ma20_slope=ma20_slope,
            ma50_slope=ma50_slope
        )

        # Detect volatility regime
        atr_percentile = self.calculate_volatility_percentile(df['atr'], lookback=100)
        volatility_regime = self.detect_volatility_regime(atr_percentile)

        # Get recommendation
        recommendation = self.get_regime_recommendation(
            regime=tcr_result['regime'],
            direction=tcr_result['direction'],
            volatility=volatility_regime
        )

        # Compile results
        result = {
            # Current values
            'current_price': round(current_price, 2),
            'current_ma20': round(current_ma20, 2),
            'current_ma50': round(current_ma50, 2),

            # TCR regime
            'regime': tcr_result['regime'],
            'direction': tcr_result['direction'],
            'full_regime': tcr_result['full_regime'],

            # Indicators
            'adx': round(current_adx, 2),
            'plus_di': round(current_plus_di, 2),
            'minus_di': round(current_minus_di, 2),
            'atr': round(current_atr, 2),

            # MA slopes
            'ma20_slope': round(ma20_slope, 4),
            'ma50_slope': round(ma50_slope, 4),

            # Volatility
            'volatility_regime': volatility_regime,
            'atr_percentile': round(atr_percentile, 2),

            # Recommendation
            'recommendation': recommendation['recommendation'],
            'reasoning': recommendation['reasoning'],
            'risk_level': recommendation['risk_level'],
            'suggested_strategy': recommendation['suggested_strategy'],

            # Metadata
            'timestamp': df['timestamp'].iloc[-1].isoformat(),
            'bars_analyzed': len(df)
        }

        return result
