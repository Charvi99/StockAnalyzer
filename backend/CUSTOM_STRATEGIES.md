# Creating Custom Trading Strategies

This guide explains how to create your own custom trading strategies using the BaseStrategy framework.

## Overview

The strategy framework provides a base class (`BaseStrategy`) that you can extend to create custom trading strategies. The framework handles:
- Technical indicator calculation
- Data validation
- Position sizing
- Backtesting
- Strategy execution

## Quick Start

### 1. Create Your Strategy Class

Create a new file in `backend/app/services/` (e.g., `my_strategies.py`):

```python
from typing import Dict, Tuple, Any
import pandas as pd
from .base_strategy import BaseStrategy


class MyCustomStrategy(BaseStrategy):
    """
    Your custom strategy description here.
    """

    def __init__(self):
        super().__init__(
            name="My Custom Strategy",
            description="What your strategy does",
            parameters={
                'param1': 10,
                'param2': 20.0
            }
        )

    def analyze(
        self,
        prices: pd.DataFrame,
        indicators: Dict[str, Any]
    ) -> Tuple[str, float, Dict[str, Any]]:
        """
        Main strategy logic - implement your trading rules here.
        """
        # Validate data
        if not self.validate_data(prices):
            return 'HOLD', 0.0, {'reason': 'Insufficient data'}

        # Get current price
        current_price = prices.iloc[-1]['close']

        # Get indicators you need
        rsi = indicators.get('RSI', {}).get('value', 50)
        macd_data = indicators.get('MACD', {})

        # Your strategy logic
        if rsi < 30:  # Example: Buy when RSI oversold
            return 'BUY', 0.8, {
                'entry_price': current_price,
                'stop_loss': current_price * 0.95,
                'take_profit': current_price * 1.10,
                'reason': f'RSI oversold at {rsi:.1f}'
            }
        elif rsi > 70:  # Example: Sell when RSI overbought
            return 'SELL', 0.8, {
                'exit_price': current_price,
                'reason': f'RSI overbought at {rsi:.1f}'
            }
        else:
            return 'HOLD', 0.3, {'reason': 'No signal'}
```

### 2. Register Your Strategy

In `backend/app/services/strategy_manager.py`, add your strategy:

```python
from .my_strategies import MyCustomStrategy

class StrategyManager:
    def _register_builtin_strategies(self):
        builtin_strategies = [
            # ... existing strategies ...
            MyCustomStrategy(),  # Add your strategy here
        ]
```

### 3. Use Your Strategy

Your strategy is now available via the API:

```bash
# List all strategies
GET /api/v1/strategies/list

# Execute your strategy
POST /api/v1/strategies/{stock_id}/execute
{
    "strategy_name": "My Custom Strategy",
    "parameters": {
        "param1": 15
    }
}

# Backtest your strategy
POST /api/v1/strategies/{stock_id}/backtest
{
    "strategy_name": "My Custom Strategy",
    "initial_balance": 10000
}
```

## Available Indicators

When you implement `analyze()`, you receive pre-calculated indicators:

### Trend Indicators
```python
# Moving Averages
ma_data = indicators.get('Moving_Averages', {})
ma_short = ma_data.get('ma_short', 0)  # Default: 20-period
ma_long = ma_data.get('ma_long', 0)    # Default: 50-period

# MACD
macd_data = indicators.get('MACD', {})
macd = macd_data.get('macd', 0)
signal_line = macd_data.get('signal_line', 0)
histogram = macd_data.get('histogram', 0)

# ADX (Trend Strength)
adx_data = indicators.get('ADX', {})
adx = adx_data.get('value', 0)
plus_di = adx_data.get('plus_di', 0)
minus_di = adx_data.get('minus_di', 0)

# Parabolic SAR
psar_data = indicators.get('Parabolic_SAR', {})
psar = psar_data.get('value', 0)
trend = psar_data.get('trend', 0)  # 1=up, -1=down
```

### Momentum Indicators
```python
# RSI
rsi_data = indicators.get('RSI', {})
rsi = rsi_data.get('value', 50)

# Stochastic
stoch_data = indicators.get('Stochastic', {})
k = stoch_data.get('k', 50)
d = stoch_data.get('d', 50)

# CCI
cci_data = indicators.get('CCI', {})
cci = cci_data.get('value', 0)
```

### Volatility Indicators
```python
# Bollinger Bands
bb_data = indicators.get('Bollinger_Bands', {})
bb_upper = bb_data.get('upper', 0)
bb_middle = bb_data.get('middle', 0)
bb_lower = bb_data.get('lower', 0)

# ATR
atr_data = indicators.get('ATR', {})
atr = atr_data.get('value', 0)

# Keltner Channels
kc_data = indicators.get('Keltner_Channels', {})
kc_upper = kc_data.get('upper', 0)
kc_middle = kc_data.get('middle', 0)
kc_lower = kc_data.get('lower', 0)
```

### Volume Indicators
```python
# OBV
obv_data = indicators.get('OBV', {})
obv = obv_data.get('value', 0)

# VWAP
vwap_data = indicators.get('VWAP', {})
vwap = vwap_data.get('value', 0)

# A/D Line
ad_data = indicators.get('AD_Line', {})
ad_line = ad_data.get('value', 0)
```

## Price Data Structure

The `prices` DataFrame has these columns:
- `timestamp`: DateTime
- `open`: Opening price
- `high`: Highest price
- `low`: Lowest price
- `close`: Closing price
- `volume`: Trading volume

```python
# Access latest price data
latest = prices.iloc[-1]
current_price = latest['close']
current_volume = latest['volume']

# Access previous prices
previous = prices.iloc[-2]
previous_close = previous['close']

# Calculate price changes
price_change = (current_price - previous_close) / previous_close
```

## Return Values

Your `analyze()` method must return a tuple:

```python
return (signal, confidence, details)
```

### Signal
- `'BUY'`: Buy signal
- `'SELL'`: Sell signal
- `'HOLD'`: No action

### Confidence
- Float between 0.0 and 1.0
- 0.0 = No confidence
- 1.0 = Maximum confidence

### Details
Dictionary with additional information:

```python
{
    'entry_price': 150.50,      # Recommended entry price
    'stop_loss': 145.00,        # Stop loss price
    'take_profit': 160.00,      # Take profit target
    'reason': 'RSI oversold',   # Explanation
    # Add any other relevant data
}
```

## Advanced Features

### Custom Parameters

Define configurable parameters:

```python
def __init__(self):
    super().__init__(
        name="My Strategy",
        description="Description",
        parameters={
            'rsi_threshold': 30,
            'stop_loss_pct': 0.05,
            'take_profit_pct': 0.10
        }
    )
```

Users can override these via API:

```json
{
    "strategy_name": "My Strategy",
    "parameters": {
        "rsi_threshold": 25
    }
}
```

### Minimum Data Points

Specify how much historical data you need:

```python
def get_min_data_points(self) -> int:
    return 50  # Need at least 50 price bars
```

### Position Sizing

Use built-in position sizing:

```python
shares = self.calculate_position_size(
    account_balance=10000,
    risk_per_trade=0.02,  # Risk 2% per trade
    entry_price=150,
    stop_loss=145
)
```

## Example Strategies

See `backend/app/services/example_strategies.py` for complete examples:

1. **RSIOversoldOverboughtStrategy** - Simple RSI-based strategy
2. **MACDCrossoverStrategy** - MACD signal crossovers
3. **MovingAverageCrossoverStrategy** - Golden/Death cross
4. **BollingerBandsMeanReversionStrategy** - Mean reversion at bands
5. **TrendFollowingStrategy** - Multi-indicator trend following

## Testing Your Strategy

### Via API

```bash
# Execute on a stock
curl -X POST http://localhost:8000/api/v1/strategies/1/execute \
  -H "Content-Type: application/json" \
  -d '{"strategy_name": "My Custom Strategy"}'

# Run backtest
curl -X POST http://localhost:8000/api/v1/strategies/1/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "My Custom Strategy",
    "initial_balance": 10000
  }'
```

### Backtest Results

Backtests return:
- `total_return`: Overall return percentage
- `total_trades`: Number of completed trades
- `winning_trades`: Number of profitable trades
- `losing_trades`: Number of losing trades
- `win_rate`: Percentage of winning trades
- `max_drawdown`: Maximum drawdown percentage
- `equity_curve`: List of account values over time

## Best Practices

1. **Always validate data** - Use `self.validate_data(prices)`
2. **Handle missing indicators** - Use `.get()` with defaults
3. **Return meaningful confidence** - Scale based on signal strength
4. **Include stop losses** - Protect capital
5. **Provide clear reasons** - Help users understand signals
6. **Test thoroughly** - Backtest before using real money
7. **Keep it simple** - Complex != Better

## Tips

- Start with simple strategies and iterate
- Combine multiple indicators for confirmation
- Use confidence levels to filter weak signals
- Test different parameters via backtesting
- Monitor win rate and drawdown carefully
- Consider market conditions (trending vs. ranging)

## Common Patterns

### Trend Following
```python
if ma_short > ma_long and adx > 25:
    return 'BUY', confidence, details
```

### Mean Reversion
```python
if price < bb_lower:
    return 'BUY', confidence, details
```

### Breakout
```python
if price > resistance and volume > avg_volume * 1.5:
    return 'BUY', confidence, details
```

### Momentum
```python
if rsi < 30 and macd > signal_line:
    return 'BUY', confidence, details
```

## Need Help?

- Check `base_strategy.py` for complete API documentation
- Review `example_strategies.py` for working examples
- Use `/docs` endpoint for API documentation
- Test strategies in sandbox mode first

Happy Strategy Building! 🚀📈
