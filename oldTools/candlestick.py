"""
candlestick.py

Basic candlestick pattern recognition tool (e.g. Bullish/Bearish Engulfing, Hammer, Shooting Star).
"""

from core.signal_tool import SignalTool, register_tool

@register_tool('candle')
class CandlestickPatternTool(SignalTool):
    def __init__(self):
        super().__init__()
        self._signal = None
        self._reason = ""
        self.last_pattern = ""

    def analyze(self, data):
        # Detect only the last day's pattern (expand as needed!)
        patterns = []
        for i in range(1, len(data)):
            row = data.iloc[i]
            prev = data.iloc[i - 1]
            body = abs(row['Close'] - row['Open'])
            prev_body = abs(prev['Close'] - prev['Open'])
            high = row['High']
            low = row['Low']
            open_ = row['Open']
            close = row['Close']

            if (prev['Close'] < prev['Open']) and (close > open_) and (close > prev['Open']) and (open_ < prev['Close']):
                patterns.append('Bullish Engulfing')
            elif (prev['Close'] > prev['Open']) and (close < open_) and (open_ > prev['Close']) and (close < prev['Open']):
                patterns.append('Bearish Engulfing')
            elif (body < (high - low) * 0.5) and ((close - low) / (0.001 + high - low) > 0.6) and (abs(close - open_) < body * 0.5):
                patterns.append('Hammer')
            elif (body < (high - low) * 0.5) and ((high - open_) / (0.001 + high - low) > 0.6) and (abs(close - open_) < body * 0.5):
                patterns.append('Shooting Star')
            else:
                patterns.append('')
        patterns.insert(0, '')
        data['Candlestick_Pattern'] = patterns

        last_pattern = data['Candlestick_Pattern'].iloc[-1]
        self.last_pattern = last_pattern

        if last_pattern == 'Bullish Engulfing' or last_pattern == 'Hammer':
            self._signal = 'BUY'
            self._reason = f"Detected {last_pattern} pattern"
        elif last_pattern == 'Bearish Engulfing' or last_pattern == 'Shooting Star':
            self._signal = 'SELL'
            self._reason = f"Detected {last_pattern} pattern"
        else:
            self._signal = 'HOLD'
            self._reason = "No strong pattern"

    def signal(self):
        return self._signal, self._reason

    def plot(self, ax, data):
        # Just plot the close and mark detected patterns
        ax.plot(data.index, data['Close'], label='Close', color='black')
        patterns = data[data['Candlestick_Pattern'] != '']
        ax.scatter(patterns.index, patterns['Close'], marker='o', color='red', label='Pattern')
        for idx, row in patterns.iterrows():
            ax.annotate(row['Candlestick_Pattern'], (idx, row['Close']), textcoords="offset points", xytext=(0,10), ha='center', fontsize=8)
        ax.set_title('Candlestick Patterns Detected')
        ax.legend()
        ax.grid(True, alpha=0.3)
