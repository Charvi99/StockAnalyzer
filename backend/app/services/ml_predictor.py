"""
ml_predictor.py

Machine Learning prediction service adapted from oldTools/ai_predictor.py
Provides LSTM, Transformer, CNN, and hybrid models for stock price prediction.
"""

import os
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
import joblib
import ta
from ta.utils import dropna
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# Try to import talib, but continue without it if not available
try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False
    print("Warning: TA-Lib not available. Candlestick patterns will be skipped.")

# Feature sets for technical indicators
INDICATOR_SETS = {
    "trend": [
        'trend_macd', 'trend_macd_signal', 'trend_macd_diff',
        'trend_psar_signal', 'trend_psar_distance',
        'trend_adx', 'trend_adx_pos', 'trend_adx_neg',
        'trend_aroon_up', 'trend_aroon_down', 'trend_aroon_ind',
        'ma_20_slope', 'ma_50_slope'
    ],
    "momentum": [
        'momentum_rsi', 'momentum_stoch_k', 'momentum_williams_r',
        'momentum_stoch_d', 'momentum_uo', 'momentum_roc',
        'momentum_cci', 'momentum_tsi', 'momentum_ao'
    ],
    "volatility": [
        'volatility_bb_width', 'volatility_bb_hband_indicator',
        'volatility_bb_lband_indicator', 'volatility_atr',
        'volatility_kc_width', 'volatility_dc_width'
    ],
    "volume": [
        'volume_obv', 'volume_cmf', 'volume_fi', 'volume_mfi',
        'volume_eom', 'volume_vwap'
    ],
    "candlestick": [
        'candle_bullish_hammer', 'candle_bullish_morningstar', 'candle_bullish_3whitesoldiers',
        'candle_bullish_engulfing', 'candle_bullish_piercing', 'candle_bearish_hangingman',
        'candle_bearish_eveningstar', 'candle_bearish_3blackcrows', 'candle_bearish_engulfing',
        'candle_bearish_darkcloudcover'
    ],
    "market_context": [
        'market_close', 'market_return'
    ]
}

# ========================================
# Dataset Class
# ========================================

class StockDataset(Dataset):
    """PyTorch Dataset for stock price sequences"""
    def __init__(self, features, targets, seq_length=30):
        self.features = features
        self.targets = targets
        self.seq_length = seq_length

    def __len__(self):
        return len(self.features) - self.seq_length

    def __getitem__(self, idx):
        x = self.features[idx : idx + self.seq_length]
        y = self.targets[idx + self.seq_length - 1]
        return torch.tensor(x, dtype=torch.float32), torch.tensor(y, dtype=torch.long)


# ========================================
# Neural Network Architectures
# ========================================

class LSTMPredictor(nn.Module):
    """LSTM model for stock prediction"""
    def __init__(self, feature_size, hidden_size=128, num_layers=3, num_classes=3, dropout=0.3):
        super(LSTMPredictor, self).__init__()

        self.lstm = nn.LSTM(
            input_size=feature_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=False
        )

        self.bn = nn.BatchNorm1d(hidden_size)
        self.relu = nn.ReLU()
        self.final_dropout = nn.Dropout(p=dropout)
        self.fc_out = nn.Linear(hidden_size, num_classes)

    def forward(self, src):
        lstm_out, _ = self.lstm(src)
        last_time_step_out = lstm_out[:, -1, :]

        out = self.bn(last_time_step_out)
        out = self.relu(out)
        out = self.final_dropout(out)
        out = self.fc_out(out)

        return out


class TimeSeriesTransformer(nn.Module):
    """Transformer model for stock prediction"""
    def __init__(self, feature_size, num_classes=3, d_model=64, nhead=4, num_layers=2,
                 dim_feedforward=256, dropout=0.15, seq_length=30):
        super(TimeSeriesTransformer, self).__init__()
        self.input_fc = nn.Linear(feature_size, d_model)
        self.pos_embedding = nn.Parameter(torch.zeros(1, seq_length, d_model))
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            activation="relu",
            batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.fc_out = nn.Linear(d_model, num_classes)

    def forward(self, src):
        src = self.input_fc(src) + self.pos_embedding
        encoded = self.transformer_encoder(src)
        return self.fc_out(encoded[:, -1, :])


class CNNPredictor(nn.Module):
    """1D CNN for stock prediction"""
    def __init__(self, feature_size, num_classes=3, seq_length=30):
        super(CNNPredictor, self).__init__()

        self.conv1 = nn.Conv1d(in_channels=feature_size, out_channels=32, kernel_size=3, padding=1)
        self.relu1 = nn.ReLU()
        self.pool1 = nn.MaxPool1d(kernel_size=2)

        self.conv2 = nn.Conv1d(in_channels=32, out_channels=64, kernel_size=3, padding=1)
        self.relu2 = nn.ReLU()
        self.pool2 = nn.MaxPool1d(kernel_size=2)

        flattened_size = 64 * (seq_length // 4)

        self.fc1 = nn.Linear(flattened_size, 100)
        self.relu3 = nn.ReLU()
        self.fc2 = nn.Linear(100, num_classes)

    def forward(self, src):
        src = src.permute(0, 2, 1)

        out = self.conv1(src)
        out = self.relu1(out)
        out = self.pool1(out)

        out = self.conv2(out)
        out = self.relu2(out)
        out = self.pool2(out)

        out = out.flatten(start_dim=1)
        out = self.fc1(out)
        out = self.relu3(out)
        out = self.fc2(out)

        return out


class CNNLSTMPredictor(nn.Module):
    """Hybrid CNN-LSTM model"""
    def __init__(self, feature_size, num_classes=3, seq_length=30,
                 cnn_out_channels=64, lstm_hidden_size=128, lstm_num_layers=2, dropout=0.3):
        super(CNNLSTMPredictor, self).__init__()

        self.cnn_extractor = nn.Sequential(
            nn.Conv1d(in_channels=feature_size, out_channels=cnn_out_channels, kernel_size=5, padding=2),
            nn.BatchNorm1d(cnn_out_channels),
            nn.ReLU(),
            nn.MaxPool1d(kernel_size=2)
        )

        cnn_output_seq_length = seq_length // 2
        cnn_output_feature_size = cnn_out_channels

        self.lstm = nn.LSTM(
            input_size=cnn_output_feature_size,
            hidden_size=lstm_hidden_size,
            num_layers=lstm_num_layers,
            batch_first=True,
            dropout=dropout if lstm_num_layers > 1 else 0
        )

        self.fc_out = nn.Linear(lstm_hidden_size, num_classes)
        self.dropout = nn.Dropout(p=dropout)

    def forward(self, src):
        cnn_in = src.permute(0, 2, 1)
        cnn_out = self.cnn_extractor(cnn_in)
        lstm_in = cnn_out.permute(0, 2, 1)

        lstm_out, _ = self.lstm(lstm_in)
        last_time_step_out = lstm_out[:, -1, :]

        out = self.dropout(last_time_step_out)
        out = self.fc_out(out)

        return out


# ========================================
# Feature Engineering Functions
# ========================================

def add_candlestick_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """Add candlestick pattern indicators using talib (if available)"""
    if not HAS_TALIB:
        # Add zero-filled columns if talib is not available
        pattern_names = [
            'candle_bullish_hammer', 'candle_bullish_morningstar', 'candle_bullish_3whitesoldiers',
            'candle_bullish_engulfing', 'candle_bullish_piercing', 'candle_bearish_hangingman',
            'candle_bearish_eveningstar', 'candle_bearish_3blackcrows', 'candle_bearish_engulfing',
            'candle_bearish_darkcloudcover'
        ]
        for pattern in pattern_names:
            df[pattern] = 0
        return df

    # Bullish patterns
    df['candle_bullish_hammer'] = talib.CDLHAMMER(df['open'], df['high'], df['low'], df['close'])
    df['candle_bullish_morningstar'] = talib.CDLMORNINGSTAR(df['open'], df['high'], df['low'], df['close'], penetration=0)
    df['candle_bullish_3whitesoldiers'] = talib.CDL3WHITESOLDIERS(df['open'], df['high'], df['low'], df['close'])
    df['candle_bullish_engulfing'] = talib.CDLENGULFING(df['open'], df['high'], df['low'], df['close'])
    df['candle_bullish_piercing'] = talib.CDLPIERCING(df['open'], df['high'], df['low'], df['close'])

    # Bearish patterns
    df['candle_bearish_hangingman'] = talib.CDLHANGINGMAN(df['open'], df['high'], df['low'], df['close'])
    df['candle_bearish_eveningstar'] = talib.CDLEVENINGSTAR(df['open'], df['high'], df['low'], df['close'], penetration=0)
    df['candle_bearish_3blackcrows'] = talib.CDL3BLACKCROWS(df['open'], df['high'], df['low'], df['close'])
    df['candle_bearish_engulfing'] = talib.CDLENGULFING(df['open'], df['high'], df['low'], df['close'])
    df['candle_bearish_darkcloudcover'] = talib.CDLDARKCLOUDCOVER(df['open'], df['high'], df['low'], df['close'], penetration=0)

    # Split engulfing into bullish and bearish
    df['candle_bullish_engulfing'] = df['candle_bullish_engulfing'].apply(lambda x: 100 if x == 100 else 0)
    df['candle_bearish_engulfing'] = df['candle_bearish_engulfing'].apply(lambda x: -100 if x == -100 else 0)

    return df


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add comprehensive technical indicators"""
    # Clean DataFrame
    df = dropna(df)

    # Trend Indicators
    macd = ta.trend.MACD(close=df['close'], window_slow=26, window_fast=12, window_sign=9)
    df['trend_macd'] = macd.macd()
    df['trend_macd_signal'] = macd.macd_signal()
    df['trend_macd_diff'] = macd.macd_diff()

    # Parabolic SAR
    psar_indicator = ta.trend.PSARIndicator(df['high'], df['low'], df['close'])
    df['psar'] = psar_indicator.psar()
    df['trend_psar_signal'] = np.where(df['close'] > df['psar'], 1, -1)
    df['trend_psar_distance'] = (df['close'] - df['psar']) / df['close']
    df.drop(columns=['psar'], inplace=True)

    # ADX
    adx = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14)
    df['trend_adx'] = adx.adx()
    df['trend_adx_pos'] = adx.adx_pos()
    df['trend_adx_neg'] = adx.adx_neg()

    # Aroon
    aroon = ta.trend.AroonIndicator(df['close'], df['low'], window=25)
    df['trend_aroon_up'] = aroon.aroon_up()
    df['trend_aroon_down'] = aroon.aroon_down()
    df['trend_aroon_ind'] = aroon.aroon_indicator()

    # Moving Average Slopes
    df['ma_20_slope'] = df['close'].rolling(window=20).mean().diff()
    df['ma_50_slope'] = df['close'].rolling(window=50).mean().diff()

    # Momentum Indicators
    df['momentum_rsi'] = ta.momentum.rsi(df['close'], window=14)
    df['momentum_stoch_k'] = ta.momentum.stoch(df['high'], df['low'], df['close'], window=14, smooth_window=3)
    df['momentum_williams_r'] = ta.momentum.williams_r(df['high'], df['low'], df['close'], lbp=14)

    stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'], window=14, smooth_window=3)
    df['momentum_stoch_d'] = stoch.stoch_signal()

    df['momentum_uo'] = ta.momentum.ultimate_oscillator(df['high'], df['low'], df['close'])
    df['momentum_roc'] = ta.momentum.roc(df['close'], window=12)
    df['momentum_cci'] = ta.trend.cci(df['high'], df['low'], df['close'], window=20)
    df['momentum_tsi'] = ta.momentum.tsi(df['close'])
    df['momentum_ao'] = ta.momentum.awesome_oscillator(df['high'], df['low'])

    # Volatility Indicators
    bollinger = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['volatility_bb_width'] = bollinger.bollinger_wband()
    df['volatility_bb_hband_indicator'] = bollinger.bollinger_hband_indicator()
    df['volatility_bb_lband_indicator'] = bollinger.bollinger_lband_indicator()
    df['volatility_atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)

    keltner = ta.volatility.KeltnerChannel(df['high'], df['low'], df['close'], window=20)
    df['volatility_kc_width'] = keltner.keltner_channel_wband()

    donchian = ta.volatility.DonchianChannel(df['high'], df['low'], df['close'], window=20)
    df['volatility_dc_width'] = donchian.donchian_channel_wband()

    # Volume Indicators
    df['volume_obv'] = ta.volume.on_balance_volume(df['close'], df['volume'])
    df['volume_cmf'] = ta.volume.chaikin_money_flow(df['high'], df['low'], df['close'], df['volume'], window=20)
    df['volume_fi'] = ta.volume.force_index(df['close'], df['volume'], window=13)
    df['volume_mfi'] = ta.volume.money_flow_index(df['high'], df['low'], df['close'], df['volume'], window=14)
    df['volume_eom'] = ta.volume.ease_of_movement(df['high'], df['low'], df['volume'], window=14)
    df['volume_vwap'] = ta.volume.volume_weighted_average_price(df['high'], df['low'], df['close'], df['volume'], window=14)

    # Replace infinite values with NaN
    df.replace([np.inf, -np.inf], np.nan, inplace=True)

    # Add candlestick patterns
    df = add_candlestick_patterns(df)

    return df


def create_classification_target(df: pd.DataFrame, threshold: float = 0.001) -> pd.DataFrame:
    """Create classification labels (0=Down, 1=Stay, 2=Up) based on future SMA"""
    sma_window = 5
    df['sma_target'] = df['close'].rolling(window=sma_window).mean()
    future_sma_returns = (df['sma_target'].shift(-1) - df['sma_target']) / df['sma_target']

    df['target'] = 1  # Default to 'Stay'
    df.loc[future_sma_returns > threshold, 'target'] = 2  # Up
    df.loc[future_sma_returns < -threshold, 'target'] = 0  # Down

    df.drop(columns=['sma_target'], inplace=True)

    return df


# ========================================
# ML Predictor Service Class
# ========================================

class MLPredictorService:
    """Service for training and using ML models for stock prediction"""

    def __init__(self, model_dir: str = "models"):
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.models = {}
        self.scalers = {}

    def prepare_data(self, df: pd.DataFrame, feature_sets: List[str] = None) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare data with technical indicators and targets"""
        if feature_sets is None:
            feature_sets = ['trend', 'momentum', 'volatility', 'volume', 'candlestick']

        # Rename columns to lowercase for consistency with talib
        df = df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low',
                                'Close': 'close', 'Volume': 'volume'})

        # Add technical indicators
        df_featured = add_technical_indicators(df.copy())

        # Create target
        df_featured = create_classification_target(df_featured)

        # Select feature columns
        feature_cols = []
        for feature_set in feature_sets:
            feature_cols.extend(INDICATOR_SETS.get(feature_set, []))

        final_feature_cols = [col for col in feature_cols if col in df_featured.columns]

        # Remove NaN rows
        df_featured = df_featured.dropna()

        X = df_featured[final_feature_cols].values
        y = df_featured['target'].values

        return X, y

    def train_model(self, df: pd.DataFrame, model_type: str = "LSTM", seq_length: int = 30,
                   epochs: int = 50, batch_size: int = 32, learning_rate: float = 0.001) -> Dict:
        """Train a machine learning model"""

        # Prepare data
        X, y = self.prepare_data(df)

        # Scale features
        scaler = MinMaxScaler()
        X_scaled = scaler.fit_transform(X)

        # Split data
        split_idx = int(len(X_scaled) * 0.8)
        X_train = X_scaled[:split_idx]
        y_train = y[:split_idx]
        X_val = X_scaled[split_idx:]
        y_val = y[split_idx:]

        # Create datasets
        train_dataset = StockDataset(X_train, y_train, seq_length)
        val_dataset = StockDataset(X_val, y_val, seq_length)

        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

        # Initialize model
        feature_size = X.shape[1]
        if model_type == "LSTM":
            model = LSTMPredictor(feature_size, hidden_size=128, num_layers=3)
        elif model_type == "Transformer":
            model = TimeSeriesTransformer(feature_size, seq_length=seq_length)
        elif model_type == "CNN":
            model = CNNPredictor(feature_size, seq_length=seq_length)
        elif model_type == "CNNLSTM":
            model = CNNLSTMPredictor(feature_size, seq_length=seq_length)
        else:
            raise ValueError(f"Unknown model type: {model_type}")

        model = model.to(self.device)

        # Training setup
        criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

        # Training loop
        best_val_loss = float('inf')
        history = {'train_loss': [], 'val_loss': [], 'val_accuracy': []}

        for epoch in range(epochs):
            # Training
            model.train()
            train_loss = 0.0
            for X_batch, y_batch in train_loader:
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device)

                optimizer.zero_grad()
                outputs = model(X_batch)
                loss = criterion(outputs, y_batch)
                loss.backward()
                optimizer.step()

                train_loss += loss.item()

            # Validation
            model.eval()
            val_loss = 0.0
            correct = 0
            total = 0
            with torch.no_grad():
                for X_batch, y_batch in val_loader:
                    X_batch = X_batch.to(self.device)
                    y_batch = y_batch.to(self.device)

                    outputs = model(X_batch)
                    loss = criterion(outputs, y_batch)
                    val_loss += loss.item()

                    _, predicted = torch.max(outputs.data, 1)
                    total += y_batch.size(0)
                    correct += (predicted == y_batch).sum().item()

            train_loss /= len(train_loader)
            val_loss /= len(val_loader)
            val_accuracy = correct / total

            history['train_loss'].append(train_loss)
            history['val_loss'].append(val_loss)
            history['val_accuracy'].append(val_accuracy)

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                # Save best model
                model_path = os.path.join(self.model_dir, f"{model_type}_best.pth")
                scaler_path = os.path.join(self.model_dir, f"{model_type}_scaler.pkl")
                torch.save(model.state_dict(), model_path)
                joblib.dump(scaler, scaler_path)

        # Store in memory
        self.models[model_type] = model
        self.scalers[model_type] = scaler

        return {
            'model_type': model_type,
            'best_val_loss': best_val_loss,
            'final_val_accuracy': history['val_accuracy'][-1],
            'epochs': epochs,
            'history': history
        }

    def predict(self, df: pd.DataFrame, model_type: str = "LSTM", seq_length: int = 30) -> Dict:
        """Make predictions using a trained model"""

        # Load model if not in memory
        if model_type not in self.models:
            model_path = os.path.join(self.model_dir, f"{model_type}_best.pth")
            scaler_path = os.path.join(self.model_dir, f"{model_type}_scaler.pkl")

            if not os.path.exists(model_path) or not os.path.exists(scaler_path):
                raise FileNotFoundError(f"Model {model_type} not found. Please train the model first.")

            # Load scaler
            scaler = joblib.load(scaler_path)
            self.scalers[model_type] = scaler

            # Prepare data to get feature size
            X, _ = self.prepare_data(df)
            feature_size = X.shape[1]

            # Initialize and load model
            if model_type == "LSTM":
                model = LSTMPredictor(feature_size)
            elif model_type == "Transformer":
                model = TimeSeriesTransformer(feature_size, seq_length=seq_length)
            elif model_type == "CNN":
                model = CNNPredictor(feature_size, seq_length=seq_length)
            elif model_type == "CNNLSTM":
                model = CNNLSTMPredictor(feature_size, seq_length=seq_length)
            else:
                raise ValueError(f"Unknown model type: {model_type}")

            model.load_state_dict(torch.load(model_path, map_location=self.device))
            model = model.to(self.device)
            model.eval()
            self.models[model_type] = model

        # Prepare latest data
        X, _ = self.prepare_data(df)
        X_scaled = self.scalers[model_type].transform(X)

        # Get last sequence
        if len(X_scaled) < seq_length:
            raise ValueError(f"Not enough data. Need {seq_length} samples, have {len(X_scaled)}")

        last_sequence = X_scaled[-seq_length:]
        input_tensor = torch.tensor(last_sequence, dtype=torch.float32).unsqueeze(0).to(self.device)

        # Make prediction
        with torch.no_grad():
            logits = self.models[model_type](input_tensor)
            probabilities = torch.nn.functional.softmax(logits, dim=1)
            prediction_idx = torch.argmax(probabilities, dim=1).item()
            confidence = probabilities[0][prediction_idx].item()

        signal_map = {0: "SELL", 1: "HOLD", 2: "BUY"}

        return {
            'signal': signal_map[prediction_idx],
            'confidence': float(confidence),
            'probabilities': {
                'down': float(probabilities[0][0].item()),
                'hold': float(probabilities[0][1].item()),
                'up': float(probabilities[0][2].item())
            },
            'model_type': model_type
        }
