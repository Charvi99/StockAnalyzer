"""
rsi.py

Relative Strength Index strategy.
"""

from core.signal_tool import SignalTool, register_tool
import pandas as pd

@register_tool('rsi')
class RSITool(SignalTool):
    def __init__(self, period=14):
        super().__init__()
        self.period = period
        self._signal = None
        self._reason = ""

    def analyze(self, data):
        # Calculate RSI
        delta = data['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(self.period).mean()
        loss = -delta.where(delta < 0, 0).rolling(self.period).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        latest = data.iloc[-1]

        if latest['RSI'] < 30:
            self._signal = 'BUY'
            self._reason = f"RSI={latest['RSI']:.2f} (Oversold)"
        elif latest['RSI'] > 70:
            self._signal = 'SELL'
            self._reason = f"RSI={latest['RSI']:.2f} (Overbought)"
        else:
            self._signal = 'HOLD'
            self._reason = f"RSI={latest['RSI']:.2f} (Neutral)"

    def signal(self):
        return self._signal, self._reason

    def plot(self, ax, data):
        ax.plot(data.index, data['RSI'], label='RSI', color='purple')
        ax.axhline(70, color='red', linestyle='--', alpha=0.7, label='Overbought')
        ax.axhline(30, color='green', linestyle='--', alpha=0.7, label='Oversold')
        ax.set_ylim(0, 100)
        ax.set_title('RSI (Relative Strength Index)')
        ax.legend()
        ax.grid(True, alpha=0.3)
