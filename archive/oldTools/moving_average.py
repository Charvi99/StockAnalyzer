from core.signal_tool import SignalTool, register_tool
import pandas as pd

@register_tool('ma')
class MovingAverageTool(SignalTool):
    def __init__(self, short_window=20, long_window=50):
        super().__init__()
        self.short_window = short_window
        self.long_window = long_window
        self._signal = None
        self._reason = ""
    
    def analyze(self, data):
        # Compute moving averages
        data['MA_Short'] = data['Close'].rolling(self.short_window).mean()
        data['MA_Long'] = data['Close'].rolling(self.long_window).mean()
        latest = data.iloc[-1]
        # Simple signal logic
        if latest['Close'] > latest['MA_Short']:
            self._signal = 'BUY'
            self._reason = f"Close above MA{self.short_window}"
        else:
            self._signal = 'SELL'
            self._reason = f"Close below MA{self.short_window}"

    def signal(self):
        return self._signal, self._reason

    def plot(self, ax, data):
        ax.plot(data.index, data['Close'], label='Close')
        ax.plot(data.index, data['MA_Short'], label=f'MA{self.short_window}')
        ax.plot(data.index, data['MA_Long'], label=f'MA{self.long_window}')
        ax.set_title('Moving Average Tool')
        ax.legend()
        ax.grid(True, alpha=0.3)
