"""
bollinger.py

Bollinger Bands strategy.
"""

from core.signal_tool import SignalTool, register_tool

@register_tool('bb')
class BollingerBandsTool(SignalTool):
    def __init__(self, window=20):
        super().__init__()
        self.window = window
        self._signal = None
        self._reason = ""

    def analyze(self, data):
        # Calculate Bollinger Bands
        data['BB_Middle'] = data['Close'].rolling(self.window).mean()
        data['BB_Std'] = data['Close'].rolling(self.window).std()
        data['BB_Upper'] = data['BB_Middle'] + (data['BB_Std'] * 2)
        data['BB_Lower'] = data['BB_Middle'] - (data['BB_Std'] * 2)
        latest = data.iloc[-1]

        if latest['Close'] > latest['BB_Upper']:
            self._signal = 'SELL'
            self._reason = f"Close above upper band"
        elif latest['Close'] < latest['BB_Lower']:
            self._signal = 'BUY'
            self._reason = f"Close below lower band"
        else:
            self._signal = 'HOLD'
            self._reason = "Close inside bands"

    def signal(self):
        return self._signal, self._reason

    def plot(self, ax, data):
        ax.plot(data.index, data['Close'], label='Close', linewidth=2)
        ax.plot(data.index, data['BB_Upper'], label='Upper Band', alpha=0.7)
        ax.plot(data.index, data['BB_Lower'], label='Lower Band', alpha=0.7)
        ax.fill_between(data.index, data['BB_Lower'], data['BB_Upper'], alpha=0.1)
        ax.set_title('Bollinger Bands')
        ax.legend()
        ax.grid(True, alpha=0.3)
