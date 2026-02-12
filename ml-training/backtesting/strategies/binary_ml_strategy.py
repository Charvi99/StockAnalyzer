"""
Binary ML Strategy - Uses trained CatBoost/XGBoost model.

Generates BUY signals when model predicts BUY with confidence > threshold.
Exits based on target rules (profit target, stop loss, time exit).
"""
from datetime import date, timedelta
from typing import Dict, List
import pandas as pd
import numpy as np

# Import from local modules
from strategies.base import BaseStrategy, Signal
from core.portfolio import Portfolio
from config import BacktestConfig

try:
    import catboost as cb
    CATBOOST_AVAILABLE = True
except ImportError:
    CATBOOST_AVAILABLE = False

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False


class BinaryMLStrategy(BaseStrategy):
    """
    Binary Classification ML Strategy

    - Uses trained model to predict BUY/DON'T BUY
    - Only enters when confidence >= threshold
    - Exits based on: profit target (+3%), stop loss (-2%), or time (20 days)
    """

    def __init__(self, config: BacktestConfig, model_path: str,
                 model_type: str = 'catboost',
                 confidence_threshold: float = 0.6):
        """
        Args:
            config: BacktestConfig
            model_path: Path to trained model file
            model_type: 'catboost' or 'xgboost'
            confidence_threshold: Minimum confidence to enter trade
        """
        super().__init__(config)

        self.model_path = model_path
        self.model_type = model_type.lower()
        self.confidence_threshold = confidence_threshold
        self.model = None
        self.feature_cols = None

        # Track entry prices and dates for exit logic
        self.position_entries: Dict[str, dict] = {}

        # Load model
        self._load_model()

        print(f"Binary ML Strategy initialized:")
        print(f"  Model: {self.model_type.upper()}")
        print(f"  Path: {model_path}")
        print(f"  Confidence threshold: {confidence_threshold:.2%}")
        print(f"  Exit rules: +{config.binary_exit.profit_target:.1%} / {config.binary_exit.stop_loss:.1%} / {config.binary_exit.max_hold_days}d")

    def _load_model(self):
        """Load trained model and metadata"""
        model_file = self.model_path

        if self.model_type == 'catboost':
            if not CATBOOST_AVAILABLE:
                raise ImportError("CatBoost not installed")

            # Load model
            self.model = cb.CatBoostClassifier()
            self.model.load_model(model_file)

            # Try to load feature names from metadata
            import json
            metadata_path = str(model_file).replace('model.cbm', 'metadata.json')
            try:
                with open(metadata_path) as f:
                    metadata = json.load(f)
                    self.feature_cols = metadata.get('feature_cols', None)
            except:
                self.feature_cols = None

        elif self.model_type == 'xgboost':
            if not XGBOOST_AVAILABLE:
                raise ImportError("XGBoost not installed")

            # Load model
            self.model = xgb.XGBClassifier()
            self.model.load_model(model_file)

            # Get feature names from model
            self.feature_cols = self.model.get_booster().feature_names

        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

        print(f"Model loaded successfully")
        if self.feature_cols:
            print(f"Features: {len(self.feature_cols)}")

    def generate_signals(self, current_date: date,
                        data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """
        Generate trading signals using ML model

        Args:
            current_date: Current simulation date
            data: Dictionary of symbol -> DataFrame with OHLCV and features

        Returns:
            List of BUY signals
        """
        signals = []

        for symbol, df in data.items():
            # Skip if we already have a position
            if symbol in self.position_entries:
                continue

            # Get current data point
            current_ts = pd.Timestamp(current_date)

            # Try exact match first
            if current_ts in df.index:
                current_data = df.loc[[current_ts]]
            else:
                # Find nearest date on or before current_date
                mask = df.index <= current_ts
                if not mask.any():
                    continue
                nearest_idx = df.index[mask].max()
                current_data = df.loc[[nearest_idx]]

            if len(current_data) == 0:
                continue

            price = current_data['close'].iloc[0]
            volume = current_data['volume'].iloc[0]

            # Validate stock
            if not self.validate_stock(symbol, price, volume):
                continue

            # Prepare features for prediction
            try:
                features = self._prepare_features(current_data, df)
                if features is None:
                    continue

                # Get prediction
                if self.model_type == 'catboost':
                    # Returns array of [prob_class_0, prob_class_1]
                    probs = self.model.predict_proba(features)[0]
                    prob_buy = probs[1]  # Probability of BUY (class 1)
                else:  # xgboost
                    probs = self.model.predict_proba(features)[0]
                    prob_buy = probs[1]

                # Check confidence threshold
                if prob_buy >= self.confidence_threshold:
                    signals.append(Signal(
                        symbol=symbol,
                        action='buy',
                        confidence=prob_buy,
                        reason=f'ml_buy_{prob_buy:.2f}'
                    ))

            except Exception as e:
                # Skip this symbol if prediction fails
                continue

        return signals

    def _prepare_features(self, current_data: pd.DataFrame,
                          full_df: pd.DataFrame) -> np.ndarray:
        """
        Prepare features for model prediction

        Args:
            current_data: Current row data
            full_df: Full DataFrame for symbol

        Returns:
            Feature array ready for prediction
        """
        row = current_data.iloc[0]

        # If we have feature_cols, use only those
        if self.feature_cols:
            try:
                features = [row[col] for col in self.feature_cols]
            except KeyError as e:
                # Missing feature column, skip this stock
                return None
        else:
            # Use all numeric columns except OHLCV
            exclude_cols = {'open', 'high', 'low', 'close', 'volume',
                           'symbol', 'date', 'timestamp', 'stock_id'}
            feature_cols = [c for c in row.index if c not in exclude_cols]
            features = [row[col] for col in feature_cols]

        return np.array(features).reshape(1, -1)

    def execute_signals(self, signals: List[Signal],
                       portfolio: Portfolio,
                       prices: Dict[str, float],
                       current_date: date) -> List:
        """
        Execute signals and track entries for exit logic

        Args:
            signals: List of signals
            portfolio: Current portfolio
            prices: Current prices
            current_date: Current date

        Returns:
            List of executed fills
        """
        executed = super().execute_signals(signals, portfolio, prices, current_date)

        # Track entry info for positions we just opened
        for fill in executed:
            if fill.side.value == 'buy':
                self.position_entries[fill.symbol] = {
                    'entry_price': fill.fill_price,
                    'entry_date': current_date
                }

        return executed

    def check_exits(self, portfolio: Portfolio,
                   prices: Dict[str, float],
                   current_date: date) -> List:
        """
        Check if positions should be closed based on target rules

        Exit rules:
        - Profit target: +3% (or configured)
        - Stop loss: -2% (or configured)
        - Time exit: 20 days (or configured)

        Args:
            portfolio: Current portfolio
            prices: Current prices
            current_date: Current date

        Returns:
            List of executed exit trades
        """
        exits = []

        for symbol in list(portfolio.positions.keys()):
            if symbol not in self.position_entries:
                continue

            position = portfolio.positions[symbol]
            if not position.is_open:
                # Clean up closed positions
                del self.position_entries[symbol]
                continue

            entry_info = self.position_entries[symbol]
            entry_price = entry_info['entry_price']
            entry_date = entry_info['entry_date']

            # Calculate P&L
            current_price = prices.get(symbol, entry_price)
            pnl_pct = (current_price - entry_price) / entry_price
            days_held = (current_date - entry_date).days

            # Check exit conditions
            should_exit, reason = self.config.binary_exit.should_exit(pnl_pct, days_held)

            if should_exit:
                # Sell the position
                portfolio.sell(symbol, current_price, current_date, reason)
                exits.append(symbol)

                # Clean up
                del self.position_entries[symbol]

                print(f"    EXIT {symbol}: {reason} (P&L: {pnl_pct:+.2%}, held: {days_held}d)")

        return exits
