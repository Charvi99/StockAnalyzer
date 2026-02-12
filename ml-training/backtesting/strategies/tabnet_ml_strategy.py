"""
TabNet ML Strategy - Uses trained TabNet model.

TabNet: Attentive Interpretable Tabular Learning
Supports both binary and 3-class classification models.
"""
from datetime import date, timedelta
from typing import Dict, List
import pandas as pd
import numpy as np
import json

# Import from local modules
from strategies.base import BaseStrategy, Signal
from core.portfolio import Portfolio
from config import BacktestConfig

try:
    from pytorch_tabnet.tab_model import TabNetClassifier
    TABNET_AVAILABLE = True
except ImportError:
    TABNET_AVAILABLE = False


class TabNetMLStrategy(BaseStrategy):
    """
    TabNet Classification ML Strategy

    - Uses trained TabNet model to predict stock movements
    - Supports binary (BUY/DON'T BUY) and 3-class (SELL/HOLD/BUY) models
    - Only enters when confidence >= threshold
    - Exits based on: profit target (+3%), stop loss (-2%), or time (20 days)
    """

    def __init__(self, config: BacktestConfig, model_path: str,
                 confidence_threshold: float = 0.5,
                 buy_class: int = None):
        """
        Args:
            config: BacktestConfig
            model_path: Path to trained TabNet model directory
            confidence_threshold: Minimum confidence to enter trade
            buy_class: Which class to treat as BUY signal
                      - For binary: 1 (BUY)
                      - For 3-class: 2 (BUY), or None to auto-detect
        """
        super().__init__(config)

        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.buy_class = buy_class
        self.model = None
        self.feature_cols = None
        self.num_classes = None
        self.class_names = None

        # Track entry prices and dates for exit logic
        self.position_entries: Dict[str, dict] = {}

        # Load model
        self._load_model()

        # Determine which class is BUY
        if self.buy_class is None:
            if self.num_classes == 2:
                self.buy_class = 1  # Binary: BUY is class 1
            elif self.num_classes == 3:
                self.buy_class = 2  # 3-class: BUY is class 2
            else:
                raise ValueError(f"Unsupported number of classes: {self.num_classes}")

        print(f"TabNet ML Strategy initialized:")
        print(f"  Model: TabNet ({self.num_classes}-class)")
        print(f"  Path: {model_path}")
        print(f"  BUY class: {self.buy_class} ({self._get_class_name(self.buy_class)})")
        print(f"  Confidence threshold: {confidence_threshold:.2%}")
        print(f"  Exit rules: +{config.binary_exit.profit_target:.1%} / {config.binary_exit.stop_loss:.1%} / {config.binary_exit.max_hold_days}d")

    def _get_class_name(self, class_idx: int) -> str:
        """Get human-readable class name"""
        if self.num_classes == 2:
            return {0: "DON'T BUY", 1: "BUY"}.get(class_idx, f"Class {class_idx}")
        elif self.num_classes == 3:
            return {0: "SELL", 1: "HOLD", 2: "BUY"}.get(class_idx, f"Class {class_idx}")
        elif self.num_classes == 5:
            return {0: "STRONG SELL", 1: "SELL", 2: "HOLD", 3: "BUY", 4: "STRONG BUY"}.get(class_idx, f"Class {class_idx}")
        return f"Class {class_idx}"

    def _load_model(self):
        """Load trained TabNet model and metadata"""
        import pathlib

        model_dir = pathlib.Path(self.model_path)

        # Load metadata first (handle incomplete metadata gracefully)
        metadata_path = model_dir / 'metadata.json'
        if metadata_path.exists():
            try:
                with open(metadata_path) as f:
                    content = f.read()
                    # Try to parse, if fails due to incomplete JSON, fix it
                    try:
                        metadata = json.loads(content)
                    except json.JSONDecodeError:
                        # Fix incomplete JSON by closing it properly
                        if '"optimizer_fn":' in content:
                            # Find where params should end and close it
                            content = content.split('"optimizer_fn":')[0] + '"optimizer_fn": "<torch.optim.Adam>",'
                            # Add missing fields and close
                            content += '\n    "output_dim": 3,\n    "seed": 42\n  },\n  "num_classes": 3\n}'
                            metadata = json.loads(content)

                    self.feature_cols = metadata.get('feature_cols', None)

                    # Infer number of classes from params or metadata
                    params = metadata.get('params', {})
                    self.num_classes = params.get('output_dim', None) or metadata.get('num_classes', 3)
            except Exception as e:
                import logging
                logging.warning(f"Could not load metadata: {e}, using defaults")
                self.feature_cols = None
                self.num_classes = 3  # Default to 3-class

        # Try different file naming possibilities
        possible_files = [
            model_dir / 'tabnet_model.zip',
            model_dir / 'tabnet_model.zip.zip',  # Bug in some versions
            model_dir / 'model.zip',
        ]

        model_file = None
        for f in possible_files:
            if f.exists():
                model_file = str(f)
                break

        if model_file is None:
            raise FileNotFoundError(f"No TabNet model file found in {model_dir}")

        # Load model
        if not TABNET_AVAILABLE:
            raise ImportError("pytorch-tabnet is not installed")

        self.model = TabNetClassifier()
        self.model.load_model(model_file)

        print(f"Model loaded successfully from: {model_file}")
        if self.feature_cols:
            print(f"Features: {len(self.feature_cols)}")
        print(f"Classes: {self.num_classes}")

    def generate_signals(self, current_date: date,
                        data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """
        Generate trading signals using TabNet model

        Args:
            current_date: Current simulation date
            data: Dictionary of symbol -> DataFrame with OHLCV and features

        Returns:
            List of BUY signals
        """
        signals = []

        # Debug: Log some predictions
        debug_logged = False
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
                    if not debug_logged:
                        print(f"    DEBUG: {symbol} - Features preparation returned None")
                        debug_logged = True
                    continue

                # Get prediction probabilities
                probs = self.model.predict_proba(features)[0]

                # Debug first few predictions
                if not debug_logged:
                    print(f"    DEBUG: {symbol} - Probs: {probs}, BUY class {self.buy_class}: {probs[self.buy_class]:.3f}, Threshold: {self.confidence_threshold:.3f}")
                    debug_logged = True

                # Use buy_class confidence
                prob_buy = probs[self.buy_class]

                # Check confidence threshold
                if prob_buy >= self.confidence_threshold:
                    signals.append(Signal(
                        symbol=symbol,
                        action='buy',
                        confidence=prob_buy,
                        reason=f'tabnet_buy_{self._get_class_name(self.buy_class)}_{prob_buy:.2f}'
                    ))

            except Exception as e:
                # Skip this symbol if prediction fails
                import logging
                logging.debug(f"Prediction failed for {symbol}: {e}")
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
            Feature array ready for prediction, or None if features missing
        """
        row = current_data.iloc[0]

        # If we have feature_cols from metadata, use only those
        # Filter to only include features that actually exist in the data
        if self.feature_cols:
            try:
                # Get available features that exist in both the model and data
                available_features = [col for col in self.feature_cols if col in row.index]
                if len(available_features) < len(self.feature_cols):
                    # Some features missing - log and skip
                    missing = set(self.feature_cols) - set(available_features)
                    if len(available_features) < 100:  # Only log if many missing
                        import logging
                        logging.debug(f"Missing {len(missing)} features, have {len(available_features)}")
                    if len(available_features) < 100:  # Too many missing, skip this stock
                        return None

                features = [float(row[col]) for col in available_features]
            except (KeyError, ValueError) as e:
                # Missing or invalid feature column, skip this stock
                return None
        else:
            # Use all numeric columns except OHLCV and metadata
            exclude_cols = {
                'open', 'high', 'low', 'close', 'volume',
                'symbol', 'date', 'timestamp', 'stock_id',
                'label', 'label_binary', 'label_3class', 'label_5class'
            }
            feature_cols = [c for c in row.index if c not in exclude_cols and pd.api.types.is_numeric_dtype(row[c])]
            features = [float(row[col]) for col in feature_cols]

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
