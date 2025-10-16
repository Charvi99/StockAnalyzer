"""
macd.py

MACD (Moving Average Convergence Divergence) strategy.
"""

from core.signal_tool import SignalTool, register_tool

@register_tool('macd')
class MACDTool(SignalTool):
    def __init__(self, fast=12, slow=26, signal=9):
        super().__init__()
        self.fast = fast
        self.slow = slow
        self.signal_period = signal
        self._signal = None
        self._reason = ""

    def analyze(self, data):
        # Calculate MACD line, signal line, histogram
        data['EMA_Fast'] = data['Close'].ewm(span=self.fast, adjust=False).mean()
        data['EMA_Slow'] = data['Close'].ewm(span=self.slow, adjust=False).mean()
        data['MACD'] = data['EMA_Fast'] - data['EMA_Slow']
        data['MACD_Signal'] = data['MACD'].ewm(span=self.signal_period, adjust=False).mean()
        data['MACD_Hist'] = data['MACD'] - data['MACD_Signal']
        latest = data.iloc[-1]

        if latest['MACD'] > latest['MACD_Signal']:
            self._signal = 'BUY'
            self._reason = f"MACD above Signal Line"
        elif latest['MACD'] < latest['MACD_Signal']:
            self._signal = 'SELL'
            self._reason = f"MACD below Signal Line"
        else:
            self._signal = 'HOLD'
            self._reason = "MACD equals Signal Line"

    def signal(self):
        return self._signal, self._reason

    def plot(self, ax, data):
        ax.plot(data.index, data['MACD'], label='MACD', color='blue')
        ax.plot(data.index, data['MACD_Signal'], label='Signal', color='red')
        ax.bar(data.index, data['MACD_Hist'], label='Histogram', alpha=0.3)
        ax.set_title('MACD')
        ax.legend()
        ax.grid(True, alpha=0.3)
