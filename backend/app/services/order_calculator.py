"""
Order Calculator Service

Combines chart patterns, candlestick patterns, and technical indicators
to calculate recommended entry, stop loss, and take profit levels
"""

from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import logging

from app.models.stock import Stock, StockPrice, ChartPattern, CandlestickPattern
from app.services.technical_indicators import TechnicalIndicators

logger = logging.getLogger(__name__)


class OrderCalculatorService:
    """Calculate order parameters based on technical analysis"""

    def __init__(self, db: Session):
        self.db = db

    def calculate_order_parameters(
        self,
        stock_id: int,
        account_size: float = 10000.0,
        risk_percentage: float = 2.0
    ) -> Dict:
        """
        Calculate recommended order parameters

        Args:
            stock_id: Stock ID
            account_size: Total account size in currency
            risk_percentage: Maximum risk per trade as percentage (default 2%)

        Returns:
            Dictionary with order parameters
        """
        stock = self.db.query(Stock).filter(Stock.id == stock_id).first()
        if not stock:
            raise ValueError(f"Stock {stock_id} not found")

        # Get latest price
        latest_price_obj = self.db.query(StockPrice).filter(
            StockPrice.stock_id == stock_id
        ).order_by(StockPrice.timestamp.desc()).first()

        if not latest_price_obj:
            raise ValueError(f"No price data for stock {stock_id}")

        current_price = float(latest_price_obj.close)

        # Get recent chart patterns (last 30 days)
        recent_patterns = self._get_recent_chart_patterns(stock_id, days=30)

        # Get recent candlestick patterns (last 14 days)
        recent_candles = self._get_recent_candlestick_patterns(stock_id, days=14)

        # PHASE 1: Swing Trading Improvements
        # 1. Get daily price data for swing analysis (90 days for swing context)
        daily_prices = self._get_daily_prices(stock_id, days=90)

        # 2. Detect swing highs and lows on daily timeframe
        swing_levels = self._detect_swing_levels(daily_prices)

        # 3. Calculate ATR and volatility percentile
        atr = self._calculate_atr(stock_id, period=14)
        volatility_context = self._calculate_volatility_percentile(daily_prices, current_atr=atr)

        # 4. Calculate volume-weighted support/resistance
        volume_weighted_sr = self._calculate_volume_weighted_sr(daily_prices, current_price)

        # 4b. Calculate Volume Profile for precise S/R levels
        volume_profile = self._calculate_volume_profile(daily_prices, current_price)

        # 5. Calculate moving average context
        ma_context = self._calculate_ma_context(daily_prices, current_price)

        # 6. Check weekly trend
        weekly_trend = self._check_weekly_trend(stock_id)

        # Calculate support and resistance levels (legacy method still useful)
        support_resistance = self._calculate_support_resistance(stock_id, lookback_days=90)

        # PHASE 2A: Get overall recommendation (includes weekly trend filter)
        # Import here to avoid circular dependency
        from app.api.routes.analysis import _get_recommendation_for_stock

        try:
            overall_rec = _get_recommendation_for_stock(stock, self.db)

            # Count patterns from actual data
            bullish_chart = sum(1 for p in recent_patterns if p.signal == 'bullish')
            bearish_chart = sum(1 for p in recent_patterns if p.signal == 'bearish')
            bullish_candle = sum(1 for p in recent_candles if p.pattern_type == 'bullish')
            bearish_candle = sum(1 for p in recent_candles if p.pattern_type == 'bearish')

            pattern_bias = {
                'recommendation': overall_rec.final_recommendation,
                'confidence': overall_rec.overall_confidence,
                'bullish_chart_count': bullish_chart,
                'bearish_chart_count': bearish_chart,
                'bullish_candle_count': bullish_candle,
                'bearish_candle_count': bearish_candle,
                'weekly_conflict': False  # Already handled in overall recommendation
            }
        except Exception as e:
            # Fallback to pattern-only bias if overall recommendation fails
            logger.warning(f"Could not get overall recommendation for stock {stock_id}, falling back to pattern bias: {e}")
            pattern_bias = self._determine_pattern_bias(recent_patterns, recent_candles)

            # Override recommendation if weekly trend conflicts (fallback logic)
            if pattern_bias['recommendation'] == 'BUY' and weekly_trend['trend'] == 'bearish':
                pattern_bias['recommendation'] = 'HOLD'
                pattern_bias['confidence'] = pattern_bias['confidence'] * 0.5
                pattern_bias['weekly_conflict'] = True

        # Calculate entry, stop loss, and take profit with swing trading context
        order_params = self._calculate_levels_v2(
            current_price=current_price,
            pattern_bias=pattern_bias,
            chart_patterns=recent_patterns,
            atr=atr,
            volatility_context=volatility_context,
            swing_levels=swing_levels,
            volume_sr=volume_weighted_sr,
            volume_profile=volume_profile,
            ma_context=ma_context,
            weekly_trend=weekly_trend
        )

        # Calculate position sizing
        risk_amount = account_size * (risk_percentage / 100)
        stop_loss_distance = abs(order_params['entry_price'] - order_params['stop_loss'])

        if stop_loss_distance > 0:
            position_size = risk_amount / stop_loss_distance
            position_value = position_size * order_params['entry_price']
        else:
            position_size = 0
            position_value = 0

        # Calculate risk/reward
        profit_distance = abs(order_params['take_profit'] - order_params['entry_price'])
        risk_reward = profit_distance / stop_loss_distance if stop_loss_distance > 0 else 0

        return {
            'symbol': stock.symbol,
            'current_price': current_price,
            'recommendation': pattern_bias['recommendation'],
            'confidence': pattern_bias['confidence'],
            'entry_price': order_params['entry_price'],
            'stop_loss': order_params['stop_loss'],
            'take_profit': order_params['take_profit'],
            'risk_reward_ratio': round(risk_reward, 2),
            'position_size': round(position_size, 2),
            'position_value': round(position_value, 2),
            'risk_amount': round(risk_amount, 2),
            'stop_loss_percentage': round((stop_loss_distance / current_price) * 100, 2),
            'take_profit_percentage': round((profit_distance / current_price) * 100, 2),
            'atr': round(atr, 2) if atr else None,
            'nearest_support': support_resistance['nearest_support'],
            'nearest_resistance': support_resistance['nearest_resistance'],
            'pattern_summary': {
                'bullish_chart_patterns': pattern_bias['bullish_chart_count'],
                'bearish_chart_patterns': pattern_bias['bearish_chart_count'],
                'bullish_candlestick_patterns': pattern_bias['bullish_candle_count'],
                'bearish_candlestick_patterns': pattern_bias['bearish_candle_count'],
            },
            'reasoning': order_params['reasoning'],
            # Phase 1 Swing Trading Metrics
            'swing_trading_metrics': {
                'last_swing_low': swing_levels['last_swing_low'],
                'last_swing_high': swing_levels['last_swing_high'],
                'volatility_status': volatility_context['status'],
                'volatility_percentile': volatility_context['percentile'],
                'ma_trend': ma_context['ma_trend'],
                'sma_20': ma_context['sma_20'],
                'sma_50': ma_context['sma_50'],
                'sma_200': ma_context['sma_200'],
                'distance_from_sma200': ma_context['distance_from_sma200'],
                'overextended': ma_context['overextended'],
                'weekly_trend': weekly_trend['trend'],
                'weekly_sma_50': weekly_trend.get('weekly_sma_50'),
                'volume_support': volume_weighted_sr['volume_support'],
                'volume_resistance': volume_weighted_sr['volume_resistance'],
            },
            # Volume Profile Analysis
            'volume_profile': {
                'poc': volume_profile['poc'],
                'value_area_high': volume_profile['value_area_high'],
                'value_area_low': volume_profile['value_area_low'],
                'nearest_hvn': volume_profile['nearest_hvn'],
                'nearest_lvn': volume_profile['nearest_lvn'],
                'position_in_profile': volume_profile['position_in_profile'],
            },
            'timestamp': datetime.utcnow()
        }

    def _get_recent_chart_patterns(self, stock_id: int, days: int = 30) -> List[ChartPattern]:
        """Get recent chart patterns"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        patterns = self.db.query(ChartPattern).filter(
            ChartPattern.stock_id == stock_id,
            ChartPattern.created_at >= cutoff_date
        ).order_by(ChartPattern.created_at.desc()).all()
        return patterns

    def _get_recent_candlestick_patterns(self, stock_id: int, days: int = 14) -> List[CandlestickPattern]:
        """Get recent candlestick patterns"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        patterns = self.db.query(CandlestickPattern).filter(
            CandlestickPattern.stock_id == stock_id,
            CandlestickPattern.timestamp >= cutoff_date
        ).order_by(CandlestickPattern.timestamp.desc()).all()
        return patterns

    def _calculate_atr(self, stock_id: int, period: int = 14) -> Optional[float]:
        """Calculate Average True Range for volatility"""
        prices = self.db.query(StockPrice).filter(
            StockPrice.stock_id == stock_id
        ).order_by(StockPrice.timestamp.desc()).limit(period + 1).all()

        if len(prices) < period:
            return None

        df = pd.DataFrame([{
            'high': float(p.high),
            'low': float(p.low),
            'close': float(p.close)
        } for p in reversed(prices)])

        # Calculate True Range
        df['prev_close'] = df['close'].shift(1)
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['prev_close'])
        df['tr3'] = abs(df['low'] - df['prev_close'])
        df['true_range'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)

        # Calculate ATR
        atr = df['true_range'].tail(period).mean()
        return float(atr)

    def _calculate_support_resistance(self, stock_id: int, lookback_days: int = 90) -> Dict:
        """Calculate nearest support and resistance levels"""
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
        prices = self.db.query(StockPrice).filter(
            StockPrice.stock_id == stock_id,
            StockPrice.timestamp >= cutoff_date
        ).order_by(StockPrice.timestamp.desc()).all()

        if not prices:
            return {'nearest_support': None, 'nearest_resistance': None}

        current_price = float(prices[0].close)

        # Get highs and lows
        highs = [float(p.high) for p in prices]
        lows = [float(p.low) for p in prices]

        # Find support (recent lows below current price)
        support_levels = [low for low in lows if low < current_price]
        nearest_support = max(support_levels) if support_levels else min(lows)

        # Find resistance (recent highs above current price)
        resistance_levels = [high for high in highs if high > current_price]
        nearest_resistance = min(resistance_levels) if resistance_levels else max(highs)

        return {
            'nearest_support': round(nearest_support, 2),
            'nearest_resistance': round(nearest_resistance, 2)
        }

    def _determine_pattern_bias(
        self,
        chart_patterns: List[ChartPattern],
        candlestick_patterns: List[CandlestickPattern]
    ) -> Dict:
        """Determine overall bias from patterns"""
        bullish_chart = sum(1 for p in chart_patterns if p.signal == 'bullish')
        bearish_chart = sum(1 for p in chart_patterns if p.signal == 'bearish')

        bullish_candle = sum(1 for p in candlestick_patterns if p.pattern_type == 'bullish')
        bearish_candle = sum(1 for p in candlestick_patterns if p.pattern_type == 'bearish')

        total_bullish = bullish_chart + bullish_candle
        total_bearish = bearish_chart + bearish_candle
        total_patterns = total_bullish + total_bearish

        if total_patterns == 0:
            return {
                'recommendation': 'HOLD',
                'confidence': 0.5,
                'bullish_chart_count': 0,
                'bearish_chart_count': 0,
                'bullish_candle_count': 0,
                'bearish_candle_count': 0
            }

        bullish_ratio = total_bullish / total_patterns

        if bullish_ratio >= 0.65:
            recommendation = 'BUY'
            confidence = min(bullish_ratio, 0.95)
        elif bullish_ratio <= 0.35:
            recommendation = 'SELL'
            confidence = min(1 - bullish_ratio, 0.95)
        else:
            recommendation = 'HOLD'
            confidence = 0.5 + abs(0.5 - bullish_ratio)

        return {
            'recommendation': recommendation,
            'confidence': round(confidence, 2),
            'bullish_chart_count': bullish_chart,
            'bearish_chart_count': bearish_chart,
            'bullish_candle_count': bullish_candle,
            'bearish_candle_count': bearish_candle
        }

    def _get_daily_prices(self, stock_id: int, days: int = 90) -> pd.DataFrame:
        """Get daily price data for swing trading analysis"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        prices = self.db.query(StockPrice).filter(
            StockPrice.stock_id == stock_id,
            StockPrice.timestamp >= cutoff_date
        ).order_by(StockPrice.timestamp.asc()).all()

        if not prices:
            return pd.DataFrame()

        df = pd.DataFrame([{
            'timestamp': p.timestamp,
            'open': float(p.open),
            'high': float(p.high),
            'low': float(p.low),
            'close': float(p.close),
            'volume': int(p.volume)
        } for p in prices])

        return df

    def _detect_swing_levels(self, df: pd.DataFrame, lookback: int = 5) -> Dict:
        """
        Detect swing highs and lows on daily timeframe
        Returns the most recent 3 swing lows and highs
        """
        if df.empty or len(df) < lookback * 2:
            return {'swing_lows': [], 'swing_highs': [], 'last_swing_low': None, 'last_swing_high': None}

        swing_lows = []
        swing_highs = []

        # Find swing lows (local minimums)
        for i in range(lookback, len(df) - lookback):
            is_swing_low = True
            current_low = df.iloc[i]['low']

            # Check if it's lower than surrounding bars
            for j in range(1, lookback + 1):
                if current_low >= df.iloc[i - j]['low'] or current_low >= df.iloc[i + j]['low']:
                    is_swing_low = False
                    break

            if is_swing_low:
                swing_lows.append({
                    'price': current_low,
                    'index': i,
                    'timestamp': df.iloc[i]['timestamp']
                })

        # Find swing highs (local maximums)
        for i in range(lookback, len(df) - lookback):
            is_swing_high = True
            current_high = df.iloc[i]['high']

            # Check if it's higher than surrounding bars
            for j in range(1, lookback + 1):
                if current_high <= df.iloc[i - j]['high'] or current_high <= df.iloc[i + j]['high']:
                    is_swing_high = False
                    break

            if is_swing_high:
                swing_highs.append({
                    'price': current_high,
                    'index': i,
                    'timestamp': df.iloc[i]['timestamp']
                })

        # Get most recent swing lows (last 3)
        recent_swing_lows = sorted(swing_lows, key=lambda x: x['index'], reverse=True)[:3]
        recent_swing_highs = sorted(swing_highs, key=lambda x: x['index'], reverse=True)[:3]

        return {
            'swing_lows': recent_swing_lows,
            'swing_highs': recent_swing_highs,
            'last_swing_low': recent_swing_lows[0]['price'] if recent_swing_lows else None,
            'last_swing_high': recent_swing_highs[0]['price'] if recent_swing_highs else None
        }

    def _calculate_volatility_percentile(self, df: pd.DataFrame, current_atr: Optional[float]) -> Dict:
        """Calculate where current volatility sits in historical context"""
        if df.empty or current_atr is None or len(df) < 20:
            return {'percentile': 50, 'status': 'normal', 'atr_avg': current_atr}

        # Calculate True Range for each day
        df = df.copy()
        df['prev_close'] = df['close'].shift(1)
        df['tr'] = df[['high', 'low']].apply(lambda x: x['high'] - x['low'], axis=1)
        df['tr'] = df[['tr', 'high', 'prev_close']].apply(
            lambda x: max(x['tr'], abs(x['high'] - x['prev_close'])) if pd.notna(x['prev_close']) else x['tr'],
            axis=1
        )

        # Calculate 14-day ATR for each period
        atrs = []
        for i in range(14, len(df)):
            period_atr = df.iloc[i-14:i]['tr'].mean()
            atrs.append(period_atr)

        if not atrs:
            return {'percentile': 50, 'status': 'normal', 'atr_avg': current_atr}

        # Calculate percentile
        atrs_array = np.array(atrs)
        percentile = (np.sum(atrs_array < current_atr) / len(atrs_array)) * 100

        # Determine status
        if percentile >= 80:
            status = 'very_high'
        elif percentile >= 60:
            status = 'high'
        elif percentile >= 40:
            status = 'normal'
        elif percentile >= 20:
            status = 'low'
        else:
            status = 'very_low'

        return {
            'percentile': round(percentile, 1),
            'status': status,
            'atr_avg': np.mean(atrs),
            'atr_current': current_atr
        }

    def _calculate_volume_weighted_sr(self, df: pd.DataFrame, current_price: float) -> Dict:
        """
        Calculate support/resistance based on volume accumulation at price levels
        For swing trading, we look at where most volume traded
        """
        if df.empty or len(df) < 30:
            return {'volume_support': None, 'volume_resistance': None, 'high_volume_zones': []}

        # Create price bins (1% intervals)
        df = df.copy()
        price_min = df['low'].min()
        price_max = df['high'].max()
        num_bins = 50
        bin_size = (price_max - price_min) / num_bins

        # Accumulate volume by price level
        volume_by_price = {}
        for _, row in df.iterrows():
            # Average price for the day weighted by position in range
            avg_price = (row['high'] + row['low'] + row['close']) / 3
            bin_idx = int((avg_price - price_min) / bin_size) if bin_size > 0 else 0
            bin_idx = min(bin_idx, num_bins - 1)
            bin_price = price_min + (bin_idx * bin_size)

            if bin_price not in volume_by_price:
                volume_by_price[bin_price] = 0
            volume_by_price[bin_price] += row['volume']

        # Find high volume zones
        sorted_volume = sorted(volume_by_price.items(), key=lambda x: x[1], reverse=True)
        high_volume_zones = [{'price': round(price, 2), 'volume': vol} for price, vol in sorted_volume[:5]]

        # Find nearest volume support (below current price)
        volume_support = None
        for price, vol in sorted_volume:
            if price < current_price * 0.97:  # At least 3% below
                volume_support = round(price, 2)
                break

        # Find nearest volume resistance (above current price)
        volume_resistance = None
        for price, vol in sorted_volume:
            if price > current_price * 1.03:  # At least 3% above
                volume_resistance = round(price, 2)
                break

        return {
            'volume_support': volume_support,
            'volume_resistance': volume_resistance,
            'high_volume_zones': high_volume_zones
        }

    def _calculate_volume_profile(self, df: pd.DataFrame, current_price: float, num_bins: int = 100) -> Dict:
        """
        Calculate Volume Profile for swing trading

        Returns:
        - POC (Point of Control): Price level with highest volume
        - Value Area High (VAH): Top of 70% volume area
        - Value Area Low (VAL): Bottom of 70% volume area
        - High Volume Nodes (HVN): Price levels with high acceptance
        - Low Volume Nodes (LVN): Price levels with low volume (gaps, rejection zones)
        """
        if df.empty or len(df) < 30:
            return {
                'poc': None,
                'value_area_high': None,
                'value_area_low': None,
                'high_volume_nodes': [],
                'low_volume_nodes': [],
                'nearest_hvn': None,
                'nearest_lvn': None,
                'position_in_profile': 'unknown'
            }

        df = df.copy()

        # Define price range and create bins
        price_min = df['low'].min()
        price_max = df['high'].max()
        price_range = price_max - price_min
        bin_size = price_range / num_bins

        if bin_size == 0:
            return {
                'poc': current_price,
                'value_area_high': current_price,
                'value_area_low': current_price,
                'high_volume_nodes': [],
                'low_volume_nodes': [],
                'nearest_hvn': None,
                'nearest_lvn': None,
                'position_in_profile': 'unknown'
            }

        # Create price bins
        bins = [price_min + (i * bin_size) for i in range(num_bins + 1)]

        # Accumulate volume in each price bin
        volume_profile_data = {bins[i]: 0 for i in range(num_bins)}

        for _, row in df.iterrows():
            # For each bar, distribute its volume across the price range it covered
            bar_low = row['low']
            bar_high = row['high']
            bar_volume = row['volume']

            # Find which bins this bar touches
            for i in range(num_bins):
                bin_low = bins[i]
                bin_high = bins[i + 1]

                # Check if this bin overlaps with the bar's range
                overlap_low = max(bin_low, bar_low)
                overlap_high = min(bin_high, bar_high)

                if overlap_high > overlap_low:
                    # Calculate proportion of bar's range that overlaps with this bin
                    bar_range = bar_high - bar_low
                    if bar_range > 0:
                        overlap_ratio = (overlap_high - overlap_low) / bar_range
                    else:
                        overlap_ratio = 1.0

                    # Add proportional volume to this bin
                    volume_profile_data[bin_low] += bar_volume * overlap_ratio

        # Sort by volume to find POC
        sorted_profile = sorted(volume_profile_data.items(), key=lambda x: x[1], reverse=True)

        # POC (Point of Control) - price with highest volume
        poc_price = sorted_profile[0][0] if sorted_profile else current_price
        poc_volume = sorted_profile[0][1] if sorted_profile else 0

        # Calculate Value Area (70% of total volume)
        total_volume = sum(volume_profile_data.values())
        value_area_volume = total_volume * 0.70

        # Start from POC and expand outward until we capture 70% of volume
        cumulative_volume = poc_volume
        value_area_prices = [poc_price]

        # Get all prices sorted by volume
        remaining_prices = [(p, v) for p, v in sorted_profile[1:]]

        for price, volume in remaining_prices:
            if cumulative_volume >= value_area_volume:
                break
            value_area_prices.append(price)
            cumulative_volume += volume

        # Value Area High and Low
        value_area_high = max(value_area_prices) if value_area_prices else poc_price
        value_area_low = min(value_area_prices) if value_area_prices else poc_price

        # Identify High Volume Nodes (HVN) - top 20% volume bins
        volume_threshold_hvn = np.percentile([v for _, v in sorted_profile], 80)
        high_volume_nodes = [
            {'price': round(price, 2), 'volume': volume}
            for price, volume in sorted_profile
            if volume >= volume_threshold_hvn
        ][:10]  # Top 10 HVNs

        # Identify Low Volume Nodes (LVN) - bottom 20% volume bins
        volume_threshold_lvn = np.percentile([v for _, v in sorted_profile], 20)
        low_volume_nodes = [
            {'price': round(price, 2), 'volume': volume}
            for price, volume in sorted_profile
            if volume <= volume_threshold_lvn and volume > 0
        ][:10]  # Top 10 LVNs

        # Find nearest HVN to current price
        hvn_above = [node for node in high_volume_nodes if node['price'] > current_price]
        hvn_below = [node for node in high_volume_nodes if node['price'] < current_price]

        nearest_hvn_above = min(hvn_above, key=lambda x: abs(x['price'] - current_price))['price'] if hvn_above else None
        nearest_hvn_below = max(hvn_below, key=lambda x: abs(x['price'] - current_price))['price'] if hvn_below else None

        # Choose nearest HVN overall
        nearest_hvn = None
        if nearest_hvn_above and nearest_hvn_below:
            nearest_hvn = nearest_hvn_above if abs(nearest_hvn_above - current_price) < abs(nearest_hvn_below - current_price) else nearest_hvn_below
        elif nearest_hvn_above:
            nearest_hvn = nearest_hvn_above
        elif nearest_hvn_below:
            nearest_hvn = nearest_hvn_below

        # Find nearest LVN to current price
        lvn_above = [node for node in low_volume_nodes if node['price'] > current_price]
        lvn_below = [node for node in low_volume_nodes if node['price'] < current_price]

        nearest_lvn_above = min(lvn_above, key=lambda x: abs(x['price'] - current_price))['price'] if lvn_above else None
        nearest_lvn_below = max(lvn_below, key=lambda x: abs(x['price'] - current_price))['price'] if lvn_below else None

        # Choose nearest LVN overall
        nearest_lvn = None
        if nearest_lvn_above and nearest_lvn_below:
            nearest_lvn = nearest_lvn_above if abs(nearest_lvn_above - current_price) < abs(nearest_lvn_below - current_price) else nearest_lvn_below
        elif nearest_lvn_above:
            nearest_lvn = nearest_lvn_above
        elif nearest_lvn_below:
            nearest_lvn = nearest_lvn_below

        # Determine position in profile
        position_in_profile = 'unknown'
        if value_area_high and value_area_low:
            if current_price > value_area_high:
                position_in_profile = 'above_value_area'
            elif current_price < value_area_low:
                position_in_profile = 'below_value_area'
            elif abs(current_price - poc_price) / current_price < 0.01:  # Within 1% of POC
                position_in_profile = 'at_poc'
            else:
                position_in_profile = 'inside_value_area'

        return {
            'poc': round(poc_price, 2),
            'value_area_high': round(value_area_high, 2),
            'value_area_low': round(value_area_low, 2),
            'high_volume_nodes': high_volume_nodes[:5],  # Top 5 for response
            'low_volume_nodes': low_volume_nodes[:5],   # Top 5 for response
            'nearest_hvn': round(nearest_hvn, 2) if nearest_hvn else None,
            'nearest_lvn': round(nearest_lvn, 2) if nearest_lvn else None,
            'position_in_profile': position_in_profile
        }

    def _calculate_ma_context(self, df: pd.DataFrame, current_price: float) -> Dict:
        """
        Calculate moving average context for swing trading
        Checks 20, 50, 200 SMA on daily chart
        """
        if df.empty or len(df) < 200:
            return {
                'sma_20': None,
                'sma_50': None,
                'sma_200': None,
                'distance_from_sma200': None,
                'ma_trend': 'unknown',
                'overextended': False
            }

        df = df.copy()
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_50'] = df['close'].rolling(window=50).mean()
        df['sma_200'] = df['close'].rolling(window=200).mean()

        latest = df.iloc[-1]
        sma_20 = latest['sma_20'] if pd.notna(latest['sma_20']) else None
        sma_50 = latest['sma_50'] if pd.notna(latest['sma_50']) else None
        sma_200 = latest['sma_200'] if pd.notna(latest['sma_200']) else None

        # Calculate distance from 200 SMA
        distance_from_sma200 = None
        overextended = False
        if sma_200:
            distance_from_sma200 = ((current_price - sma_200) / sma_200) * 100
            overextended = abs(distance_from_sma200) > 12  # More than 12% away

        # Determine MA trend
        ma_trend = 'unknown'
        if sma_20 and sma_50 and sma_200:
            if sma_20 > sma_50 > sma_200:
                ma_trend = 'bullish'
            elif sma_20 < sma_50 < sma_200:
                ma_trend = 'bearish'
            else:
                ma_trend = 'mixed'

        return {
            'sma_20': round(sma_20, 2) if sma_20 else None,
            'sma_50': round(sma_50, 2) if sma_50 else None,
            'sma_200': round(sma_200, 2) if sma_200 else None,
            'distance_from_sma200': round(distance_from_sma200, 2) if distance_from_sma200 else None,
            'ma_trend': ma_trend,
            'overextended': overextended
        }

    def _check_weekly_trend(self, stock_id: int) -> Dict:
        """
        Check weekly trend for swing trading context
        Sample weekly bars from daily data
        """
        # Get 1 year of daily data to construct weekly bars
        cutoff_date = datetime.utcnow() - timedelta(days=365)
        prices = self.db.query(StockPrice).filter(
            StockPrice.stock_id == stock_id,
            StockPrice.timestamp >= cutoff_date
        ).order_by(StockPrice.timestamp.asc()).all()

        if not prices or len(prices) < 50:
            return {'trend': 'unknown', 'weekly_sma_50': None}

        df = pd.DataFrame([{
            'timestamp': p.timestamp,
            'close': float(p.close),
            'high': float(p.high),
            'low': float(p.low),
            'volume': int(p.volume)
        } for p in prices])

        # Resample to weekly (using Friday as week end, or last trading day)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        weekly = df.resample('W').agg({
            'close': 'last',
            'high': 'max',
            'low': 'min',
            'volume': 'sum'
        }).dropna()

        if len(weekly) < 50:
            return {'trend': 'unknown', 'weekly_sma_50': None}

        # Calculate 50-week SMA
        weekly['sma_50'] = weekly['close'].rolling(window=50).mean()

        latest_week = weekly.iloc[-1]
        weekly_close = latest_week['close']
        weekly_sma_50 = latest_week['sma_50']

        # Determine trend
        if pd.notna(weekly_sma_50):
            trend = 'bullish' if weekly_close > weekly_sma_50 else 'bearish'
        else:
            trend = 'unknown'

        return {
            'trend': trend,
            'weekly_sma_50': round(weekly_sma_50, 2) if pd.notna(weekly_sma_50) else None,
            'weekly_close': round(weekly_close, 2)
        }

    def _calculate_levels_v2(
        self,
        current_price: float,
        pattern_bias: Dict,
        chart_patterns: List[ChartPattern],
        atr: Optional[float],
        volatility_context: Dict,
        swing_levels: Dict,
        volume_sr: Dict,
        volume_profile: Dict,
        ma_context: Dict,
        weekly_trend: Dict
    ) -> Dict:
        """
        Enhanced stop loss and take profit calculation for swing trading
        Uses Phase 1 improvements including Volume Profile analysis
        """
        reasoning = []

        # Entry price (use current price as baseline)
        entry_price = current_price

        # Skip if not a BUY signal (no shorting for swing trading)
        if pattern_bias['recommendation'] != 'BUY':
            return {
                'entry_price': round(entry_price, 2),
                'stop_loss': round(entry_price * 0.95, 2),
                'take_profit': round(entry_price * 1.05, 2),
                'reasoning': ['Not a BUY signal - calculated placeholder levels']
            }

        # Get pattern-based levels if available
        pattern_stop_loss = None
        pattern_take_profit = None

        if chart_patterns:
            for pattern in chart_patterns:
                if pattern.stop_loss and pattern.target_price:
                    pattern_stop_loss = float(pattern.stop_loss)
                    pattern_take_profit = float(pattern.target_price)
                    reasoning.append(f"Using {pattern.pattern_name} pattern levels")
                    break

        # ==== STOP LOSS CALCULATION ====
        # Priority: Swing Low > VAL (Value Area Low) > Pattern > Volume Support > ATR-based

        stop_loss = None

        # 1. Try swing low (highest priority for swing trading)
        if swing_levels['last_swing_low']:
            # ATR multiplier based on volatility
            atr_multiplier = 1.0
            if volatility_context['status'] == 'very_high':
                atr_multiplier = 1.5
            elif volatility_context['status'] == 'high':
                atr_multiplier = 1.2

            # Place SL below last swing low with ATR buffer
            buffer = (atr * atr_multiplier) if atr else (swing_levels['last_swing_low'] * 0.02)
            stop_loss = swing_levels['last_swing_low'] - buffer
            reasoning.append(f"SL below swing low with {atr_multiplier}x ATR buffer (volatility: {volatility_context['status']})")

        # 2. Try Value Area Low (VAL) from Volume Profile
        elif volume_profile and volume_profile.get('value_area_low'):
            val = volume_profile['value_area_low']
            # Only use VAL if price is above it (it acts as support)
            if current_price > val:
                buffer = (atr * 0.5) if atr else (val * 0.015)
                stop_loss = val - buffer
                reasoning.append(f"SL below Value Area Low (VAL at ${val:.2f}) - high volume support")

                # Also check if there's a High Volume Node (HVN) below that could be better support
                if volume_profile.get('nearest_hvn') and volume_profile['nearest_hvn'] < current_price:
                    hvn_below = volume_profile['nearest_hvn']
                    # If HVN is close to VAL, prefer it (institutional support)
                    if abs(hvn_below - val) / val < 0.02:  # Within 2% of VAL
                        stop_loss = hvn_below - buffer
                        reasoning.append(f"SL adjusted to HVN at ${hvn_below:.2f} (strong institutional support)")

        # 3. Fallback to pattern SL
        elif pattern_stop_loss and pattern_stop_loss < entry_price:
            stop_loss = pattern_stop_loss
            reasoning.append("SL from chart pattern")

        # 4. Fallback to volume support
        elif volume_sr['volume_support']:
            buffer = (atr * 0.5) if atr else (volume_sr['volume_support'] * 0.02)
            stop_loss = volume_sr['volume_support'] - buffer
            reasoning.append("SL below volume-weighted support")

        # 5. Fallback to ATR-based
        elif atr:
            multiplier = 2.0
            if volatility_context['status'] == 'very_high':
                multiplier = 2.5
            stop_loss = entry_price - (atr * multiplier)
            reasoning.append(f"SL using {multiplier}x ATR")

        # 6. Final fallback
        else:
            stop_loss = entry_price * 0.96  # 4% default
            reasoning.append("SL using 4% default")

        # Ensure SL is reasonable (max 8% for swing trading)
        max_sl = entry_price * 0.92
        if stop_loss < max_sl:
            stop_loss = max_sl
            reasoning.append("SL capped at 8% max loss")

        # ==== TAKE PROFIT CALCULATION ====
        # Priority: Pattern Target > VAH (Value Area High) > Volume Resistance > Risk/Reward

        take_profit = None

        # 1. Try pattern target
        if pattern_take_profit and pattern_take_profit > entry_price:
            take_profit = pattern_take_profit
            reasoning.append("TP from chart pattern target")

        # 2. Try Value Area High (VAH) from Volume Profile
        elif volume_profile and volume_profile.get('value_area_high'):
            vah = volume_profile['value_area_high']
            # Only use VAH if price is below it (it acts as resistance)
            if current_price < vah:
                take_profit = vah
                reasoning.append(f"TP at Value Area High (VAH at ${vah:.2f}) - high volume resistance")

                # Also check if there's a High Volume Node (HVN) above that could be better target
                if volume_profile.get('nearest_hvn') and volume_profile['nearest_hvn'] > current_price:
                    hvn_above = volume_profile['nearest_hvn']
                    # If HVN is beyond VAH and not too far, prefer it (institutional resistance)
                    if hvn_above > vah and (hvn_above - entry_price) / entry_price < 0.15:  # Max 15% gain
                        take_profit = hvn_above
                        reasoning.append(f"TP extended to HVN at ${hvn_above:.2f} (strong institutional resistance)")

                # Special case: if at POC (Point of Control), expect mean reversion to VAH
                if volume_profile.get('position_in_profile') == 'at_poc':
                    reasoning.append("Price at POC - expecting mean reversion to VAH")

        # 3. Try volume resistance
        elif volume_sr['volume_resistance']:
            take_profit = volume_sr['volume_resistance']
            reasoning.append("TP at volume-weighted resistance")

        # 4. Fallback to risk/reward
        else:
            risk_reward = 2.5 # Better R:R for swing trading
            if weekly_trend['trend'] == 'bullish' and ma_context['ma_trend'] == 'bullish':
                risk_reward = 3.0  # Extend target when both weekly and daily are bullish
                reasoning.append("TP using 3:1 R:R (strong trend alignment)")
            else:
                reasoning.append("TP using 2.5:1 R:R")

            stop_distance = abs(entry_price - stop_loss)
            take_profit = entry_price + (stop_distance * risk_reward)

        # Cap TP if overextended from 200 SMA
        if take_profit and ma_context['overextended'] and ma_context['distance_from_sma200'] and ma_context['distance_from_sma200'] > 10:
            max_tp = entry_price * 1.10  # Max 10% gain when overextended
            if take_profit > max_tp:
                take_profit = max_tp
                reasoning.append("TP capped - price overextended from 200 SMA")

        # Cap TP if price is above value area (extended from normal trading range)
        if take_profit and volume_profile and volume_profile.get('position_in_profile') == 'above_value_area':
            max_tp_vp = entry_price * 1.08  # Max 8% gain when above value area
            if take_profit > max_tp_vp:
                take_profit = max_tp_vp
                reasoning.append("TP capped - price above value area (trading at premium)")

        # Final safety check - ensure take_profit is never None
        if take_profit is None:
            stop_distance = abs(entry_price - stop_loss)
            take_profit = entry_price + (stop_distance * 2.5)
            reasoning.append("TP calculated using 2.5:1 R:R (fallback)")

        return {
            'entry_price': round(entry_price, 2),
            'stop_loss': round(stop_loss, 2),
            'take_profit': round(take_profit, 2),
            'reasoning': reasoning
        }

    def _calculate_levels(
        self,
        current_price: float,
        pattern_bias: Dict,
        chart_patterns: List[ChartPattern],
        atr: Optional[float],
        support_resistance: Dict
    ) -> Dict:
        """Calculate entry, stop loss, and take profit levels (legacy method, kept for backwards compatibility)"""
        reasoning = []

        # Entry price (use current price as baseline)
        entry_price = current_price

        # Get pattern-based levels if available
        pattern_stop_loss = None
        pattern_take_profit = None

        if chart_patterns:
            # Use the most recent pattern with defined levels
            for pattern in chart_patterns:
                if pattern.stop_loss and pattern.target_price:
                    pattern_stop_loss = float(pattern.stop_loss)
                    pattern_take_profit = float(pattern.target_price)
                    reasoning.append(f"Using {pattern.pattern_name} pattern levels")
                    break

        # Calculate stop loss
        if pattern_stop_loss:
            stop_loss = pattern_stop_loss
        elif atr:
            # Use ATR-based stop loss (2x ATR)
            atr_multiplier = 2.0
            if pattern_bias['recommendation'] == 'BUY':
                stop_loss = current_price - (atr * atr_multiplier)
            else:
                stop_loss = current_price + (atr * atr_multiplier)
            reasoning.append(f"Stop loss based on {atr_multiplier}x ATR")
        elif support_resistance['nearest_support']:
            # Use support/resistance
            if pattern_bias['recommendation'] == 'BUY':
                stop_loss = support_resistance['nearest_support'] * 0.98  # 2% below support
            else:
                stop_loss = support_resistance['nearest_resistance'] * 1.02  # 2% above resistance
            reasoning.append("Stop loss based on support/resistance")
        else:
            # Fallback to percentage-based (3%)
            if pattern_bias['recommendation'] == 'BUY':
                stop_loss = current_price * 0.97
            else:
                stop_loss = current_price * 1.03
            reasoning.append("Stop loss based on 3% default")

        # Calculate take profit
        if pattern_take_profit:
            take_profit = pattern_take_profit
        else:
            # Use risk/reward ratio of 2:1
            risk_reward = 2.0
            stop_distance = abs(entry_price - stop_loss)

            if pattern_bias['recommendation'] == 'BUY':
                take_profit = entry_price + (stop_distance * risk_reward)
            else:
                take_profit = entry_price - (stop_distance * risk_reward)
            reasoning.append(f"Take profit based on {risk_reward}:1 risk/reward ratio")

        # Ensure logical order
        if pattern_bias['recommendation'] == 'BUY':
            stop_loss = min(stop_loss, entry_price * 0.95)  # Max 5% stop loss
            take_profit = max(take_profit, entry_price * 1.02)  # Min 2% profit target
        else:
            stop_loss = max(stop_loss, entry_price * 1.05)  # Max 5% stop loss
            take_profit = min(take_profit, entry_price * 0.98)  # Min 2% profit target

        return {
            'entry_price': round(entry_price, 2),
            'stop_loss': round(stop_loss, 2),
            'take_profit': round(take_profit, 2),
            'reasoning': reasoning
        }
