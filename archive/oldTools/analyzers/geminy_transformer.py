# %%
# !pip install torch pandas numpy scikit-learn ta yfinance seaborn
import os
import sys

# ==============================================================================
# --- Project Path Correction Block ---
# ==============================================================================
# Get the absolute path of the current script
script_path = os.path.abspath(__file__)
# Get the directory of the script
script_dir = os.path.dirname(script_path)
# Go up two levels to get the project root directory
project_root = os.path.dirname(os.path.dirname(script_dir))
# Add the project root to the Python path
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ==============================================================================

from core.trade_advisor import TradeAdvisor
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import RobustScaler
from sklearn.model_selection import TimeSeriesSplit

from sklearn.metrics import classification_report, confusion_matrix
import ta
import matplotlib.pyplot as plt
import seaborn as sns

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
    ],
    "advanced": [
            'inter_adx_rsi', 'inter_adx_cci', 'inter_psar_atr',
            'target_lag_1', 'target_lag_3', 'target_lag_5',
            'rsi_lag_1', 'rsi_lag_3', 'rsi_lag_5',
            'cci_lag_1', 'cci_lag_3', 'cci_lag_5',
            'return_lag_1'
        ]
}
FEATURE_SETS_TO_USE = [
    'trend',
    'momentum',
    'volatility',
    'volume',
    'market_context',
    'advanced',
    'candlestick' # <-- Example: Uncomment to add all candlestick patterns
]

# ==============================================================================
# 1. DATA PREPARATION AND FEATURE ENGINEERING
# ==============================================================================

def merge_market_context(stock_df, market_df):
    """Merges market data into the primary stock DataFrame."""
    market_features = pd.DataFrame(index=stock_df.index)
    market_features['market_close'] = market_df['Close']
    market_features['market_return'] = market_df['Close'].pct_change()
    merged_df = stock_df.join(market_features, how='left')
    print("Successfully merged market context features.")
    return merged_df

import ta
from ta.utils import dropna
import talib

def add_candlestick_patterns(df):
    """
    Identifies 10 common candlestick patterns and adds them as features.
    The functions return 100 for bullish, -100 for bearish, and 0 for no pattern.
    """
    print("Adding candlestick pattern features...")

    # --- 5 Bullish Patterns ---
    # Hammer
    df['candle_bullish_hammer'] = talib.CDLHAMMER(df['Open'], df['High'], df['Low'], df['Close'])
    # Morning Star (a 3-day pattern)
    df['candle_bullish_morningstar'] = talib.CDLMORNINGSTAR(df['Open'], df['High'], df['Low'], df['Close'], penetration=0)
    # Three White Soldiers (a 3-day pattern)
    df['candle_bullish_3whitesoldiers'] = talib.CDL3WHITESOLDIERS(df['Open'], df['High'], df['Low'], df['Close'])
    # Bullish Engulfing
    df['candle_bullish_engulfing'] = talib.CDLENGULFING(df['Open'], df['High'], df['Low'], df['Close'])
    # Piercing Line
    df['candle_bullish_piercing'] = talib.CDLPIERCING(df['Open'], df['High'], df['Low'], df['Close'])

    # --- 5 Bearish Patterns ---
    # Hanging Man
    df['candle_bearish_hangingman'] = talib.CDLHANGINGMAN(df['Open'], df['High'], df['Low'], df['Close'])
    # Evening Star (a 3-day pattern)
    df['candle_bearish_eveningstar'] = talib.CDLEVENINGSTAR(df['Open'], df['High'], df['Low'], df['Close'], penetration=0)
    # Three Black Crows (a 3-day pattern)
    df['candle_bearish_3blackcrows'] = talib.CDL3BLACKCROWS(df['Open'], df['High'], df['Low'], df['Close'])
    # Bearish Engulfing
    df['candle_bearish_engulfing'] = talib.CDLENGULFING(df['Open'], df['High'], df['Low'], df['Close'])
    # Dark Cloud Cover
    df['candle_bearish_darkcloudcover'] = talib.CDLDARKCLOUDCOVER(df['Open'], df['High'], df['Low'], df['Close'], penetration=0)

    # Note on Engulfing: talib.CDLENGULFING returns +100 for bullish and -100 for bearish in the same column.
    # We will split this into two separate features for clarity and to avoid cancelling effects.
    df['candle_bullish_engulfing'] = df['candle_bullish_engulfing'].apply(lambda x: 100 if x == 100 else 0)
    df['candle_bearish_engulfing'] = df['candle_bearish_engulfing'].apply(lambda x: -100 if x == -100 else 0)

    return df

def add_technical_indicators(df):
    """
    [MASSIVELY ENHANCED] Adds over 30 technical indicators for comprehensive
    feature analysis.
    """
    # Clean DataFrame to remove NaNs from price data
    df = dropna(df)

    # --- Trend Indicators (5 Existing + 7 New = 12 total) ---
    # Moving Average Convergence Divergence (MACD)
    macd = ta.trend.MACD(close=df['Close'], window_slow=26, window_fast=12, window_sign=9)
    df['trend_macd'] = macd.macd()
    df['trend_macd_signal'] = macd.macd_signal()
    df['trend_macd_diff'] = macd.macd_diff() # Existing

    # Parabolic SAR
    # 1. Calculate the raw PSAR indicator first
    psar_indicator = ta.trend.PSARIndicator(df['High'], df['Low'], df['Close'])
    df['psar'] = psar_indicator.psar() # This gives the continuous PSAR dot value
    
    # 2. Engineer the 'trend_psar_signal' feature
    # If close is above psar, it's an uptrend (1), otherwise downtrend (-1)
    df['trend_psar_signal'] = np.where(df['Close'] > df['psar'], 1, -1)
    
    # 3. Engineer the 'trend_psar_distance' feature
    # This shows how strong the trend is (how far price is from the SAR dot)
    df['trend_psar_distance'] = (df['Close'] - df['psar']) / df['Close']
    
    # 4. We can now drop the raw 'psar' column as we've extracted its info
    df.drop(columns=['psar'], inplace=True)

    # Average Directional Movement Index (ADX)
    adx = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close'], window=14)
    df['trend_adx'] = adx.adx() # Existing
    df['trend_adx_pos'] = adx.adx_pos()
    df['trend_adx_neg'] = adx.adx_neg()

    # Aroon Indicator
    aroon = ta.trend.AroonIndicator(df['Close'], df['Low'], window=25)
    df['trend_aroon_up'] = aroon.aroon_up()
    df['trend_aroon_down'] = aroon.aroon_down()
    df['trend_aroon_ind'] = aroon.aroon_indicator()

    # Moving Average Slopes (Existing)
    df['ma_20_slope'] = df['Close'].rolling(window=20).mean().diff()
    df['ma_50_slope'] = df['Close'].rolling(window=50).mean().diff()
    
    # --- Momentum Indicators (3 Existing + 8 New = 11 total) ---
    df['momentum_rsi'] = ta.momentum.rsi(df['Close'], window=14) # Existing (renamed for clarity)
    df['momentum_stoch_k'] = ta.momentum.stoch(df['High'], df['Low'], df['Close'], window=14, smooth_window=3) # Existing
    df['momentum_williams_r'] = ta.momentum.williams_r(df['High'], df['Low'], df['Close'], lbp=14) # Existing

    # Stochastic Oscillator Full (%K and %D)
    stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'], window=14, smooth_window=3)
    df['momentum_stoch_d'] = stoch.stoch_signal()

    # Ultimate Oscillator
    df['momentum_uo'] = ta.momentum.ultimate_oscillator(df['High'], df['Low'], df['Close'])
    
    # Rate of Change (ROC)
    df['momentum_roc'] = ta.momentum.roc(df['Close'], window=12)

    # Commodity Channel Index (CCI)
    df['momentum_cci'] = ta.trend.cci(df['High'], df['Low'], df['Close'], window=20)

    # True Strength Index (TSI)
    df['momentum_tsi'] = ta.momentum.tsi(df['Close'])

    # Awesome Oscillator
    df['momentum_ao'] = ta.momentum.awesome_oscillator(df['High'], df['Low'])

    # --- Volatility Indicators (2 Existing + 4 New = 6 total) ---
    bollinger = ta.volatility.BollingerBands(close=df['Close'], window=20, window_dev=2)
    df['volatility_bb_width'] = bollinger.bollinger_wband() # Existing (renamed)
    df['volatility_bb_hband_indicator'] = bollinger.bollinger_hband_indicator() # Crossing high band
    df['volatility_bb_lband_indicator'] = bollinger.bollinger_lband_indicator() # Crossing low band
    
    df['volatility_atr'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14) # Existing (renamed)

    # Keltner Channel
    keltner = ta.volatility.KeltnerChannel(df['High'], df['Low'], df['Close'], window=20)
    df['volatility_kc_width'] = keltner.keltner_channel_wband()

    # Donchian Channel
    donchian = ta.volatility.DonchianChannel(df['High'], df['Low'], df['Close'], window=20)
    df['volatility_dc_width'] = donchian.donchian_channel_wband()


    # --- Volume Indicators (1 Existing + 5 New = 6 total) ---
    df['volume_obv'] = ta.volume.on_balance_volume(df['Close'], df['Volume']) # Existing (renamed)

    # Chaikin Money Flow (CMF)
    df['volume_cmf'] = ta.volume.chaikin_money_flow(df['High'], df['Low'], df['Close'], df['Volume'], window=20)
    
    # Force Index
    df['volume_fi'] = ta.volume.force_index(df['Close'], df['Volume'], window=13)

    # Money Flow Index (MFI)
    df['volume_mfi'] = ta.volume.money_flow_index(df['High'], df['Low'], df['Close'], df['Volume'], window=14)
    
    # Ease of Movement (EOM)
    df['volume_eom'] = ta.volume.ease_of_movement(df['High'], df['Low'], df['Volume'], window=14)

    # Volume Weighted Average Price (VWAP)
    df['volume_vwap'] = ta.volume.volume_weighted_average_price(df['High'], df['Low'], df['Close'], df['Volume'], window=14)

    # Replace infinite values with NaN so they can be dropped
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    
    # Note: NaNs will be handled globally after all feature creation

    # ADD CANDLESTICK PATERNS
    df = add_candlestick_patterns(df)
    return df

def add_advanced_features(df):
    """
    Creates more sophisticated features by combining existing ones.
    This includes interaction terms and lagged features.
    """
    print("Adding advanced interaction and lagged features...")

    # --- 1. Interaction Features ---
    # We'll create interactions between some of the top features you found.
    # This helps the model learn conditional relationships.
    
    # How does trend strength (ADX) affect momentum (RSI, CCI)?
    if 'trend_adx' in df.columns and 'momentum_rsi' in df.columns:
        df['inter_adx_rsi'] = df['trend_adx'] * df['momentum_rsi']
    if 'trend_adx' in df.columns and 'momentum_cci' in df.columns:
        df['inter_adx_cci'] = df['trend_adx'] * df['momentum_cci']

    # How does PSAR distance relate to volatility?
    if 'trend_psar_distance' in df.columns and 'volatility_atr' in df.columns:
        # Normalize ATR first to keep scales consistent
        normalized_atr = df['volatility_atr'] / df['Close']
        df['inter_psar_atr'] = df['trend_psar_distance'] * normalized_atr

    # --- 2. Lagged Features ---
    # This gives the model a short-term memory of how indicators are changing.
    # We will lag some of the most important and fastest-moving features.
    lags = [1, 3, 5] # e.g., 1 bar ago, 3 bars ago, 5 bars ago

    # Lag the target itself (autoregressive feature)
    if 'target' in df.columns:
        for lag in lags:
            df[f'target_lag_{lag}'] = df['target'].shift(lag)

    # Lag key momentum indicators
    if 'momentum_rsi' in df.columns:
        for lag in lags:
            df[f'rsi_lag_{lag}'] = df['momentum_rsi'].shift(lag)
    if 'momentum_cci' in df.columns:
        for lag in lags:
            df[f'cci_lag_{lag}'] = df['momentum_cci'].shift(lag)
            
    # Lag the change in price (return)
    df['return_lag_1'] = df['Close'].pct_change().shift(1)
    
    return df

def create_classification_target(df, threshold=0.001): # Note: Threshold may need to be smaller for a smooth SMA
    """
    [MODIFIED] Creates the target variable for classification based on the 
    future direction of a 5-day Simple Moving Average (SMA) of the Close price.
    This smooths the target and focuses the model on learning the underlying trend.
    """
    # 1. Calculate the 5-day SMA
    sma_window = 5
    df['sma_target'] = df['Close'].rolling(window=sma_window).mean()

    # 2. Calculate the FUTURE return of the SMA, not the price
    future_sma_returns = np.log(df['sma_target'].shift(-3) / df['sma_target'])

    # 3. Create labels based on the SMA's future direction
    df['target'] = 1 # Default to 'Stay'
    df.loc[future_sma_returns > threshold, 'target'] = 2 # Up
    df.loc[future_sma_returns < -threshold, 'target'] = 0 # Down

    # We can now drop the temporary SMA column
    df.drop(columns=['sma_target'], inplace=True)
    
    return df

def select_and_scale_features(df, feature_sets_to_use):
    """
    [REWRITTEN] Selects and scales features based on a list of category names.
    
    Args:
        df (pd.DataFrame): The DataFrame with all possible features.
        feature_sets_to_use (list): A list of strings, where each string is a key
                                    from the global INDICATOR_SETS dictionary.
    """
    feature_cols = []
    # Build the list of feature columns from the chosen sets
    for feature_set in feature_sets_to_use:
        feature_cols.extend(INDICATOR_SETS.get(feature_set, []))

    cols_to_exclude = ['Open', 'High', 'Low', 'Close', 'Volume', 'market_close', 'target']

    # --- Robustness Check ---
    # Filter out any columns that might not exist in the DataFrame (e.g., market_return if API failed)
    all_generated_features = list(df.columns)
    final_feature_cols = [col for col in all_generated_features if col not in cols_to_exclude]    
    print(f"\n--- Using {len(final_feature_cols)} Features From Sets: {feature_sets_to_use} ---")
    
    data = df[final_feature_cols].values
    scaler = RobustScaler()
    data_scaled = scaler.fit_transform(data)
    
    # Return the final list of columns actually used, for consistency
    return data_scaled, df['target'].values, scaler, final_feature_cols


class StockClassificationDataset(Dataset):
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

# ==============================================================================
# 2. NEURAL NETWORK ARCHITECTURES
# ==============================================================================

class TimeSeriesTransformerClassifier(nn.Module):
    def __init__(self, feature_size, num_classes=3, d_model=64, nhead=4, num_layers=2, dim_feedforward=256, dropout=0.15, seq_length=30):
        super(TimeSeriesTransformerClassifier, self).__init__()
        self.input_fc = nn.Linear(feature_size, d_model)
        self.pos_embedding = nn.Parameter(torch.zeros(1, seq_length, d_model))
        encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, dim_feedforward=dim_feedforward, dropout=dropout, activation="relu", batch_first=True)
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.fc_out = nn.Linear(d_model, num_classes)

    def forward(self, src):
        src = self.input_fc(src) + self.pos_embedding
        encoded = self.transformer_encoder(src)
        return self.fc_out(encoded[:, -1, :])

class LSTMPredictor(nn.Module):
    def __init__(self, feature_size, hidden_size=100, num_layers=2, num_classes=3, dropout=0.15):
        super(LSTMPredictor, self).__init__()
        self.lstm = nn.LSTM(
            input_size=feature_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout
        )
        self.fc_out = nn.Linear(hidden_size, num_classes)

    def forward(self, src):
        # LSTM output is (output, (hidden_state, cell_state))
        # We only care about the output of the last time step
        lstm_out, _ = self.lstm(src)
        last_time_step_out = lstm_out[:, -1, :]
        return self.fc_out(last_time_step_out)

class CNNPredictor(nn.Module):
    """
    A 1D Convolutional Neural Network for time series classification.
    It learns to detect short-term temporal patterns in the feature data.
    """
    def __init__(self, feature_size, num_classes=3, seq_length=30):
        super(CNNPredictor, self).__init__()
        
        # We define two convolutional blocks
        # Block 1
        self.conv1 = nn.Conv1d(
            in_channels=feature_size,  # Input channels = number of features
            out_channels=32,           # Output channels = number of patterns to learn
            kernel_size=3,             # Kernel size = how many time steps to look at once
            padding=1                  # Padding to keep sequence length the same
        )
        self.relu1 = nn.ReLU()
        self.pool1 = nn.MaxPool1d(kernel_size=2) # Reduce sequence length by half

        # Block 2
        self.conv2 = nn.Conv1d(in_channels=32, out_channels=64, kernel_size=3, padding=1)
        self.relu2 = nn.ReLU()
        self.pool2 = nn.MaxPool1d(kernel_size=2) # Reduce again

        # After pooling, the sequence length will be seq_length / 4.
        # We need to calculate the flattened size to feed into the linear layer.
        flattened_size = 64 * (seq_length // 4)

        # Classifier part
        self.fc1 = nn.Linear(flattened_size, 100)
        self.relu3 = nn.ReLU()
        self.fc2 = nn.Linear(100, num_classes)

    def forward(self, src):
        # The input `src` has shape [batch_size, seq_length, feature_size]
        # PyTorch Conv1d expects [batch_size, feature_size, seq_length]
        # So we need to permute the dimensions
        src = src.permute(0, 2, 1)

        # Pass through Block 1
        out = self.conv1(src)
        out = self.relu1(out)
        out = self.pool1(out)

        # Pass through Block 2
        out = self.conv2(out)
        out = self.relu2(out)
        out = self.pool2(out)

        # Flatten the output for the linear layers
        out = out.flatten(start_dim=1)
        
        # Pass through the classifier
        out = self.fc1(out)
        out = self.relu3(out)
        out = self.fc2(out)
        
        return out

class InceptionBlock1D(nn.Module):
    # This class has no issues and remains the same
    def __init__(self, in_channels, out_channels_per_branch):
        super(InceptionBlock1D, self).__init__()
        self.branch1 = nn.Conv1d(in_channels, out_channels_per_branch, kernel_size=3, padding=1)
        self.branch2 = nn.Conv1d(in_channels, out_channels_per_branch, kernel_size=5, padding=2)
        self.branch3 = nn.Conv1d(in_channels, out_channels_per_branch, kernel_size=7, padding=3)
        self.branch4_pool = nn.MaxPool1d(kernel_size=3, stride=1, padding=1)
        self.branch4_conv = nn.Conv1d(in_channels, out_channels_per_branch, kernel_size=1)

    def forward(self, x):
        out1 = self.branch1(x)
        out2 = self.branch2(x)
        out3 = self.branch3(x)
        out4_pooled = self.branch4_pool(x)
        out4 = self.branch4_conv(out4_pooled)
        return torch.cat([out1, out2, out3, out4], dim=1)


class ComplexCNNPredictor(nn.Module):
    """
    [CORRECTED] A more complex CNN using Inception blocks and Residual connections.
    Fixes the inplace operation error.
    """
    def __init__(self, feature_size, num_classes=3, seq_length=30, num_filters=32, dropout=0.2):
        super(ComplexCNNPredictor, self).__init__()
        self.initial_conv = nn.Conv1d(feature_size, num_filters * 4, kernel_size=1)
        self.initial_bn = nn.BatchNorm1d(num_filters * 4)
        self.inception1 = InceptionBlock1D(in_channels=num_filters * 4, out_channels_per_branch=num_filters)
        self.bn1 = nn.BatchNorm1d(num_filters * 4)
        self.inception2 = InceptionBlock1D(in_channels=num_filters * 4, out_channels_per_branch=num_filters)
        self.bn2 = nn.BatchNorm1d(num_filters * 4)
        self.relu = nn.ReLU()
        flattened_size = num_filters * 4 * seq_length
        self.fc1 = nn.Linear(flattened_size, 128)
        self.dropout = nn.Dropout(p=dropout)
        self.fc2 = nn.Linear(128, num_classes)

    def forward(self, src):
        # Permute for Conv1d: [batch, seq, feature] -> [batch, feature, seq]
        src = src.permute(0, 2, 1)

        # Initial convolution
        out = self.relu(self.initial_bn(self.initial_conv(src)))
        
        # --- Inception Block 1 with Residual Connection ---
        residual1 = out
        out = self.inception1(out)
        out = self.bn1(out)
        out = self.relu(out)
        # --- THIS IS THE FIX ---
        # Use non-in-place addition: out = out + residual
        out = out + residual1
        
        # --- Inception Block 2 with Residual Connection ---
        residual2 = out
        out = self.inception2(out)
        out = self.bn2(out)
        out = self.relu(out)
        # --- THIS IS THE FIX ---
        out = out + residual2
        
        # Flatten and classify
        out = out.flatten(start_dim=1)
        out = self.dropout(self.relu(self.fc1(out)))
        out = self.fc2(out)
        
        return out
    
class ComplexLSTMPredictor(nn.Module):
    """
    A more powerful, deeper, and better-regularized LSTM model.
    """
    def __init__(self, feature_size, hidden_size=128, num_layers=3, num_classes=3, dropout=0.3):
        super(ComplexLSTMPredictor, self).__init__()
        
        # A deeper LSTM with more hidden units and higher dropout
        self.lstm = nn.LSTM(
            input_size=feature_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            # Dropout is applied between LSTM layers (but not the last one)
            dropout=dropout if num_layers > 1 else 0,
            # We are not using a BiLSTM to avoid lookahead bias
            bidirectional=False
        )
        
        # We add a Batch Normalization layer for stability
        self.bn = nn.BatchNorm1d(hidden_size)
        self.relu = nn.ReLU()
        # A final dropout layer before the classifier
        self.final_dropout = nn.Dropout(p=dropout)
        
        # Classifier layer
        self.fc_out = nn.Linear(hidden_size, num_classes)

    def forward(self, src):
        # Pass through LSTM
        lstm_out, _ = self.lstm(src)
        
        # We only care about the output of the final time step
        last_time_step_out = lstm_out[:, -1, :]
        
        # Pass through the extra layers for stability and regularization
        out = self.bn(last_time_step_out)
        out = self.relu(out)
        out = self.final_dropout(out)
        
        # Final classification
        out = self.fc_out(out)
        
        return out
    
class FFNNPredictor(nn.Module):
    """
    [CORRECTED] A simple Feed-Forward Neural Network (FFNN).
    Uses .reshape() instead of .view() to handle non-contiguous tensors gracefully.
    """
    def __init__(self, feature_size, seq_length, num_classes=3, hidden_dim1=256, hidden_dim2=128, dropout=0.4):
        super(FFNNPredictor, self).__init__()
        
        input_dim = feature_size * seq_length
        
        self.fc1 = nn.Linear(input_dim, hidden_dim1)
        self.bn1 = nn.BatchNorm1d(hidden_dim1)
        
        self.fc2 = nn.Linear(hidden_dim1, hidden_dim2)
        self.bn2 = nn.BatchNorm1d(hidden_dim2)
        
        self.fc3 = nn.Linear(hidden_dim2, num_classes)
        
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(p=dropout)

    def forward(self, src):
        # src has shape [batch_size, seq_length, feature_size]
        
        # --- THIS IS THE FIX ---
        # Flatten the input sequence into a single vector.
        # .reshape() is a safer alternative to .view() that handles all memory layouts.
        batch_size = src.shape[0]
        src = src.reshape(batch_size, -1)
        # --- END OF FIX ---
        
        # Pass through the network
        out = self.fc1(src)
        out = self.bn1(out)
        out = self.relu(out)
        out = self.dropout(out)
        
        out = self.fc2(out)
        out = self.bn2(out)
        out = self.relu(out)
        out = self.dropout(out)
        
        out = self.fc3(out)
        
        return out

class CNNLSTMPredictor(nn.Module):
    """
    A Hybrid CNN-LSTM model.
    
    This architecture uses a 1D CNN to first extract important local patterns
    from the time series features. The sequence of these extracted patterns is
    then fed into an LSTM, which models the longer-term temporal dependencies
    between them to make a final prediction.
    """
    def __init__(self, feature_size, num_classes=3, seq_length=30, 
                 cnn_out_channels=64, lstm_hidden_size=128, lstm_num_layers=2, dropout=0.3):
        super(CNNLSTMPredictor, self).__init__()
        
        # --- CNN Feature Extractor Stage ---
        # We'll use a simple but effective CNN block
        self.cnn_extractor = nn.Sequential(
            nn.Conv1d(
                in_channels=feature_size,
                out_channels=cnn_out_channels,
                kernel_size=5,
                padding=2
            ),
            nn.BatchNorm1d(cnn_out_channels),
            nn.ReLU(),
            nn.MaxPool1d(kernel_size=2)
        )
        
        # Calculate the new sequence length and feature size after the CNN stage
        # MaxPool1d with kernel_size=2 halves the sequence length
        cnn_output_seq_length = seq_length // 2
        cnn_output_feature_size = cnn_out_channels
        
        # --- LSTM Sequence Processor Stage ---
        self.lstm = nn.LSTM(
            input_size=cnn_output_feature_size,
            hidden_size=lstm_hidden_size,
            num_layers=lstm_num_layers,
            batch_first=True,
            dropout=dropout if lstm_num_layers > 1 else 0
        )
        
        # --- Classifier ---
        self.fc_out = nn.Linear(lstm_hidden_size, num_classes)
        self.dropout = nn.Dropout(p=dropout)

    def forward(self, src):
        # src has shape [batch_size, seq_length, feature_size]
        
        # 1. CNN Stage
        # Permute for Conv1d: [batch, seq, feature] -> [batch, feature, seq]
        cnn_in = src.permute(0, 2, 1)
        cnn_out = self.cnn_extractor(cnn_in)
        # Permute back for LSTM: [batch, feature, seq] -> [batch, seq, feature]
        lstm_in = cnn_out.permute(0, 2, 1)
        
        # 2. LSTM Stage
        lstm_out, _ = self.lstm(lstm_in)
        
        # We only need the output of the last time step from the LSTM
        last_time_step_out = lstm_out[:, -1, :]
        
        # 3. Classifier Stage
        out = self.dropout(last_time_step_out)
        out = self.fc_out(out)
        
        return out        
# ==============================================================================
# 3. MODEL TRAINING AND EVALUATION PIPELINE CLASS
# ==============================================================================
def run_random_strategy_backtest(full_df, split_index, seq_length, transaction_cost=0.0005):
    """
    Runs a backtest using purely random signals to establish a baseline.

    Args:
        full_df (pd.DataFrame): The complete, processed DataFrame.
        split_index (int): The integer index where the test set begins.
        seq_length (int): The sequence length used by the real models.

    Returns:
        pd.Series: The cumulative returns of the random strategy.
    """
    print("\n--- Running Backtest for Random Guess Strategy ---")
    test_df = full_df.iloc[split_index:].copy()
    test_df['daily_return'] = test_df['Close'].pct_change()
    
    # Align the start of the test period, just like the real model
    test_df = test_df.iloc[seq_length:]
    
    # Generate random signals (0=Down, 1=Stay, 2=Up)
    num_predictions = len(test_df)
    random_signals = np.random.randint(0, 3, size=num_predictions)
    test_df['signal'] = random_signals

    # Apply the same trading logic
    test_df['strategy_return'] = 0.0
    test_df.loc[test_df['signal'] == 2, 'strategy_return'] = test_df['daily_return']
    test_df.loc[test_df['signal'] == 0, 'strategy_return'] = -test_df['daily_return']

    # --- [NEW] Transaction Cost Logic (identical to the other function) ---
    trades = test_df['signal'].diff().fillna(0) != 0
    test_df.loc[trades, 'strategy_return'] -= transaction_cost
    # ---

    # Calculate cumulative returns
    strategy_cumulative = (1 + test_df['strategy_return']).cumprod()
    
    total_return_random = strategy_cumulative.iloc[-1] - 1 if not strategy_cumulative.empty else 0
    print(f"Random Strategy Final Return: {total_return_random:.2%}")
    
    return strategy_cumulative

class ModelTrainer:
    """
    Encapsulates the training, evaluation, and backtesting pipeline for a given model.
    """
    def __init__(self, model, train_loader, test_loader, full_df, split_index, device='cpu'):
        self.model = model.to(device)
        self.train_loader = train_loader
        self.test_loader = test_loader
        self.full_df = full_df
        self.split_index = split_index
        self.device = device

    def train(self, lr=1e-4, epochs=30):
        criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        
        print(f"\n--- Training {self.model.__class__.__name__} ---")
        for epoch in range(epochs):
            self.model.train()
            train_losses = []
            for x_batch, y_batch in self.train_loader:
                x_batch, y_batch = x_batch.to(self.device), y_batch.to(self.device)
                optimizer.zero_grad()
                output = self.model(x_batch)
                loss = criterion(output, y_batch)
                if torch.isnan(loss): raise ValueError(f"NaN loss at epoch {epoch+1}.")
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                optimizer.step()
                train_losses.append(loss.item())

            self.model.eval()
            val_losses, correct, total = [], 0, 0
            with torch.no_grad():
                for x_val, y_val in self.test_loader:
                    x_val, y_val = x_val.to(self.device), y_val.to(self.device)
                    output_val = self.model(x_val)
                    val_losses.append(criterion(output_val, y_val).item())
                    _, predicted = torch.max(output_val.data, 1)
                    total += y_val.size(0)
                    correct += (predicted == y_val).sum().item()

            val_accuracy = 100 * correct / total
            print(f"Epoch [{epoch+1}/{epochs}], Train Loss: {np.mean(train_losses):.4f}, Val Loss: {np.mean(val_losses):.4f}, Val Acc: {val_accuracy:.2f}%")
        
        return self.model

    def evaluate(self):
        """
        [MODIFIED] Dynamically handles cases where the test set is missing a class.
        """
        self.model.eval()
        all_preds, all_labels = [], []
        with torch.no_grad():
            for x_batch, y_batch in self.test_loader:
                x_batch, y_batch = x_batch.to(self.device), y_batch.to(self.device)
                outputs = self.model(x_batch)
                _, predicted = torch.max(outputs.data, 1)
                all_preds.extend(predicted.cpu().numpy())
                all_labels.extend(y_batch.cpu().numpy())

        # --- THIS IS THE FIX ---
        # 1. Define the master list of all possible names
        master_target_names = ['Down', 'Stay', 'Up']
        
        # 2. Find which labels are actually present in the results
        unique_labels = np.unique(np.concatenate((all_labels, all_preds)))

        # 3. Create the list of names that correspond to the present labels
        target_names_to_display = [master_target_names[i] for i in unique_labels]

        print(f"\n--- Classification Report for {self.model.__class__.__name__} ---")
        # Note: If a class is missing, a warning about 'precision' and 'f-score'
        # for that class is normal and can be ignored.
        
        # 4. Pass both the 'labels' and the corresponding 'target_names' to the report
        print(classification_report(
            all_labels, 
            all_preds, 
            target_names=target_names_to_display, 
            labels=unique_labels,
            zero_division=0
        ))
        # --- END OF FIX ---

        cm = confusion_matrix(all_labels, all_preds, labels=unique_labels)
        plt.figure(figsize=(8, 6))
        # Use the dynamic target names for the plot as well
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                    xticklabels=target_names_to_display, 
                    yticklabels=target_names_to_display)
        plt.title(f'Confusion Matrix - {self.model.__class__.__name__}'); plt.ylabel('Actual'); plt.xlabel('Predicted'); plt.show()

    def backtest(self, random_results=None, transaction_cost=0.0005):
        """
        [MODIFIED] Now accepts and plots the results from a random strategy for comparison.
        """
        self.model.eval()
        test_df = self.full_df.iloc[self.split_index:].copy()
        test_df['daily_return'] = test_df['Close'].pct_change()
        
        test_dataset = self.test_loader.dataset
        seq_length = test_dataset.dataset.seq_length

        predictions = []
        with torch.no_grad():
            for i in range(len(test_dataset)):
                x, _ = test_dataset[i]
                x = x.unsqueeze(0).to(self.device)
                output = self.model(x)
                _, pred = torch.max(output.data, 1)
                predictions.append(pred.item())
                
        test_df = test_df.iloc[seq_length:]
        if len(predictions) != len(test_df):
            min_len = min(len(predictions), len(test_df))
            predictions, test_df = predictions[:min_len], test_df.iloc[:min_len]

        test_df['signal'] = predictions
        test_df['strategy_return'] = 0.0
        test_df.loc[test_df['signal'] == 2, 'strategy_return'] = test_df['daily_return']
        test_df.loc[test_df['signal'] == 0, 'strategy_return'] = -test_df['daily_return']

        # We fill the first NaN with 0, as there's no trade on the first day.
        trades = test_df['signal'].diff().fillna(0) != 0
    
        # Subtract the transaction cost from the strategy's return ONLY on trade days
        test_df.loc[trades, 'strategy_return'] -= transaction_cost

        test_df['buy_hold_cumulative'] = (1 + test_df['daily_return']).cumprod()
        test_df['strategy_cumulative'] = (1 + test_df['strategy_return']).cumprod()
        
        total_return_strategy = test_df['strategy_cumulative'].iloc[-1] - 1 if not test_df.empty else 0
        total_return_buy_hold = test_df['buy_hold_cumulative'].iloc[-1] - 1 if not test_df.empty else 0
        sharpe_ratio = (test_df['strategy_return'].mean() / test_df['strategy_return'].std()) * np.sqrt(252) if test_df['strategy_return'].std() != 0 else 0
        roll_max = test_df['strategy_cumulative'].cummax(); drawdown = (test_df['strategy_cumulative'] - roll_max) / roll_max; max_drawdown = drawdown.min()

        print(f"\n--- Backtest Results for {self.model.__class__.__name__} ---")
        print(f"Strategy Total Return: {total_return_strategy:.2%}"), print(f"Buy & Hold Total Return: {total_return_buy_hold:.2%}")
        print(f"Sharpe Ratio: {sharpe_ratio:.2f}"), print(f"Maximum Drawdown: {max_drawdown:.2%}")
        
        # --- PLOTTING LOGIC ---
        plt.figure(figsize=(14, 8))
        plt.plot(test_df.index, test_df['buy_hold_cumulative'], label='Buy & Hold Strategy', color='blue')
        plt.plot(test_df.index, test_df['strategy_cumulative'], label=f'{self.model.__class__.__name__} Strategy', color='green', linewidth=2)
        
        # --- [NEW] Add the random strategy plot if its results are provided ---
        if random_results is not None:
            plt.plot(random_results.index, random_results, label='Random Guess Strategy', linestyle='dotted', color='gray')
            
        plt.title(f'Strategy Performance Comparison')
        plt.xlabel('Date'); plt.ylabel('Cumulative Returns'); plt.legend(); plt.grid(True, alpha=0.3); plt.show()

from sklearn.ensemble import RandomForestClassifier

def analyze_feature_importance(df, feature_sets_to_use):
    """
    [REWRITTEN] Uses RandomForest to analyze the importance of features from selected sets.
    """
    print("\n--- Running Feature Importance Analysis ---")
    
    feature_cols = []
    for feature_set in feature_sets_to_use:
        feature_cols.extend(INDICATOR_SETS.get(feature_set, []))
        
    final_feature_cols = [col for col in feature_cols if col in df.columns]

    X = df[final_feature_cols]
    y = df['target']

    model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    model.fit(X, y)

    importance_df = pd.DataFrame({
        'Feature': final_feature_cols,
        'Importance': model.feature_importances_
    }).sort_values(by='Importance', ascending=False)

    print("Top 10 Most Important Features:")
    print(importance_df.head(10))

    plt.figure(figsize=(12, 10))
    sns.barplot(x='Importance', y='Feature', data=importance_df.head(20))
    plt.title('Feature Importance Analysis (Top 20)')
    plt.tight_layout()
    plt.show()
    
    return importance_df

# Add this import at the top of your file if it's not already there
from sklearn.model_selection import TimeSeriesSplit

# ==============================================================================
# --- NEW, COMPLETE WalkForwardTrainer CLASS ---
# ==============================================================================
class WalkForwardTrainer:
    """
    [COMPLETE & ENHANCED]
    Orchestrates a full walk-forward validation process to robustly evaluate
    a trading model across multiple time periods. Includes per-fold and final
    aggregated classification metrics and financial backtesting.
    """
    def __init__(self, full_dataset, full_df, model_class, model_params, n_splits=5):
        """
        Args:
            full_dataset (Dataset): The complete, unsplit PyTorch Dataset.
            full_df (pd.DataFrame): The complete, processed DataFrame for backtesting.
            model_class: The class of the model to be trained (e.g., ComplexCNNPredictor).
            model_params (dict): Dictionary of parameters to pass to the model's constructor.
            n_splits (int): The number of forward-walking folds to perform.
        """
        self.full_dataset = full_dataset
        self.full_df = full_df
        self.model_class = model_class
        self.model_params = model_params
        self.n_splits = n_splits
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
    def _evaluate_fold(self, model, test_loader):
        """Helper method to generate predictions and labels for evaluation."""
        model.eval()
        fold_preds, fold_labels = [], []
        with torch.no_grad():
            for x_batch, y_batch in test_loader:
                x_batch = x_batch.to(self.device)
                outputs = model(x_batch)
                _, predicted = torch.max(outputs.data, 1)
                fold_preds.extend(predicted.cpu().numpy())
                fold_labels.extend(y_batch.cpu().numpy())
        return fold_preds, fold_labels

    def run(self, transaction_cost=0.0005, epochs_per_fold=15, quiet=False):
        # TimeSeriesSplit creates indices for each fold
        # We add a gap to prevent any overlap between train and test sets, which is best practice.
        tscv = TimeSeriesSplit(n_splits=self.n_splits, gap=1)

        all_fold_results = []
        all_oos_preds = [] # OOS = Out-of-Sample
        all_oos_labels = []

        print(f"\n--- Starting Walk-Forward Validation with {self.n_splits} Folds ---")

        for fold, (train_indices, test_indices) in enumerate(tscv.split(self.full_dataset)):
            print(f"\n===== FOLD {fold + 1}/{self.n_splits} =====")
            print(f"Training on {len(train_indices)} samples, Testing on {len(test_indices)} samples.")
            
            # --- 1. Create DataLoaders for the current fold ---
            train_subset = torch.utils.data.Subset(self.full_dataset, train_indices)
            test_subset = torch.utils.data.Subset(self.full_dataset, test_indices)

            # Re-calculate sampler for the current training subset to handle imbalance
            train_targets = self.full_dataset.targets[train_indices]
            class_counts = np.bincount(train_targets)
            class_weights = 1. / (class_counts + 1e-6)
            sample_weights = torch.from_numpy(np.array([class_weights[t] for t in train_targets])).double()
            sampler = torch.utils.data.WeightedRandomSampler(sample_weights, len(sample_weights), replacement=True)
            
            train_loader = DataLoader(train_subset, batch_size=64, sampler=sampler)
            test_loader = DataLoader(test_subset, batch_size=64, shuffle=False)

            # --- 2. Initialize and Train a new model for this fold ---
            model = self.model_class(**self.model_params).to(self.device)
            criterion = nn.CrossEntropyLoss()
            optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)

            for epoch in range(epochs_per_fold):
                model.train()
                for x_batch, y_batch in train_loader:
                    x_batch, y_batch = x_batch.to(self.device), y_batch.to(self.device)
                    optimizer.zero_grad()
                    output = model(x_batch)
                    loss = criterion(output, y_batch)
                    loss.backward()
                    optimizer.step()
                print(f"  Fold {fold+1}, Epoch {epoch+1}/{epochs_per_fold} complete.")

            # --- 3. Evaluate this fold's classification performance ---
            print(f"  Evaluating fold...")
            fold_preds, fold_labels = self._evaluate_fold(model, test_loader)
            all_oos_preds.extend(fold_preds)
            all_oos_labels.extend(fold_labels)
            
            print(f"\n--- Classification Report for Fold {fold + 1} ---")
            print(classification_report(fold_labels, fold_preds, target_names=['Down', 'Stay', 'Up'], zero_division=0))

            # --- 4. Backtest ONLY on this fold's test set ---
            start_idx_in_df = test_indices[0] 
            fold_test_df = self.full_df.iloc[start_idx_in_df:].copy()
            fold_test_df['daily_return'] = fold_test_df['Close'].pct_change()
            
            predictions = fold_preds 
            
            seq_length = self.full_dataset.seq_length
            end_slice = len(predictions) + seq_length
            fold_test_df = fold_test_df.iloc[seq_length : end_slice]

            # Ensure alignment before assigning predictions
            if len(predictions) == len(fold_test_df):
                fold_test_df['signal'] = predictions
            else:
                print(f"  Warning: Prediction ({len(predictions)}) and DataFrame ({len(fold_test_df)}) length mismatch in fold {fold+1}. Skipping backtest for this fold.")
                continue

            fold_test_df['strategy_return'] = 0.0
            fold_test_df.loc[fold_test_df['signal'] == 2, 'strategy_return'] = fold_test_df['daily_return']
            fold_test_df.loc[fold_test_df['signal'] == 0, 'strategy_return'] = -fold_test_df['daily_return']
            
            trades = fold_test_df['signal'].diff().fillna(0) != 0
            fold_test_df.loc[trades, 'strategy_return'] -= transaction_cost
            
            all_fold_results.append(fold_test_df[['strategy_return', 'daily_return']])

        # --- 5. Aggregate and Display Final Results ---
        if not all_fold_results:
            print("\nNo backtest results were generated. Cannot display final performance.")
            return

        print("\n--- Walk-Forward Validation Complete. Aggregating All Results... ---")
        final_results_df = pd.concat(all_fold_results)
        final_results_df.fillna(0, inplace=True) # Fill NaNs in returns
        
        # --- Final Equity Curve ---
        final_results_df['strategy_cumulative'] = (1 + final_results_df['strategy_return']).cumprod()
        final_results_df['buy_hold_cumulative'] = (1 + final_results_df['daily_return']).cumprod()
        if not quiet:
            plt.figure(figsize=(14, 8))
            plt.plot(final_results_df.index, final_results_df['buy_hold_cumulative'], label='Buy & Hold Strategy', color='blue')
            plt.plot(final_results_df.index, final_results_df['strategy_cumulative'], label=f'Walk-Forward Strategy ({self.model_class.__name__})', color='green', linewidth=2)
            plt.title('Walk-Forward Validation Performance (Out-of-Sample)')
            plt.xlabel('Date'); plt.ylabel('Cumulative Returns'); plt.legend(); plt.grid(True, alpha=0.3)
            plt.show()

            # --- Final Aggregated Evaluation Metrics ---
            print("\n--- Final Aggregated Classification Report (All Folds Combined) ---")
            master_target_names = ['Down', 'Stay', 'Up']
            unique_labels = np.unique(np.concatenate((all_oos_labels, all_oos_preds)))
            target_names_to_display = [master_target_names[i] for i in unique_labels]

            print(classification_report(all_oos_labels, all_oos_preds, target_names=target_names_to_display, labels=unique_labels, zero_division=0))

            print("\n--- Final Aggregated Confusion Matrix (All Folds Combined) ---")
            cm = confusion_matrix(all_oos_labels, all_oos_preds, labels=unique_labels)
            plt.figure(figsize=(8, 6))
            sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=target_names_to_display, yticklabels=target_names_to_display)
            plt.title('Aggregated Confusion Matrix (All Out-of-Sample Predictions)'); plt.ylabel('Actual'); plt.xlabel('Predicted'); plt.show()

        # --- Final Financial Metrics ---
        total_return_strategy = final_results_df['strategy_cumulative'].iloc[-1] - 1
        total_return_buy_hold = final_results_df['buy_hold_cumulative'].iloc[-1] - 1
        # Annualize Sharpe Ratio based on the data frequency
        bars_per_day = (24*60) / int(self.model_params.get('multiplier', '15')) if self.model_params.get('time_span') == 'minute' else 1
        annualization_factor = np.sqrt(252 * bars_per_day)
        sharpe_ratio = (final_results_df['strategy_return'].mean() / final_results_df['strategy_return'].std()) * annualization_factor if final_results_df['strategy_return'].std() != 0 else 0
        
        if not quiet:
            print("\n--- Final Walk-Forward Performance Metrics ---")
            print(f"Strategy Net Return: {total_return_strategy:.2%}")
            print(f"Buy & Hold Return: {total_return_buy_hold:.2%}")
            print(f"Annualized Sharpe Ratio: {sharpe_ratio:.2f}")
        return sharpe_ratio
# ==============================================================================
# 4. PARAMETER OPTIMIZATION FUNCTION
# ==============================================================================
import optuna
class HyperparameterTuner:
    """
    Uses Optuna to find the best hyperparameters for a given model architecture
    by running multiple Walk-Forward Validations.
    """
    def __init__(self, full_df, model_to_tune):
        self.full_df = full_df
        self.model_to_tune = model_to_tune
        # Store the best params found so far
        self.best_sharpe = -np.inf
        self.best_params = None

    def _objective(self, trial):
        """
        This is the main function that Optuna will call for each trial.
        It defines the search space, runs a walk-forward validation, and returns the Sharpe Ratio.
        """
        # --- 1. Define the Hyperparameter Search Space ---
        print(f"\n--- Starting Optuna Trial #{trial.number} ---")
        
        # We can tune data-level parameters
        
        # And model-specific parameters
        if self.model_to_tune == "ComplexCNN":
            model_class = ComplexCNNPredictor
            seq_length = trial.suggest_int("seq_length", 50, 100, step=10)
            target_threshold = trial.suggest_float("target_threshold", 1.5e-4, 4e-4, log=True)
            model_params = {
                'num_filters': trial.suggest_categorical("num_filters", [128, 192, 256]),
                'dropout': trial.suggest_float("dropout", 0.4, 0.6),
                # These params are fixed for this trial based on other suggestions
                'feature_size': None, # Will be set later
                'seq_length': seq_length,
                'num_classes': 3,
            }
        elif self.model_to_tune == "ComplexLSTM":
            model_class = ComplexLSTMPredictor
            seq_length = trial.suggest_int("seq_length", 60, 120, step=10)
            target_threshold = trial.suggest_float("target_threshold", 5e-4, 2e-3, log=True)   
            model_params = {
                'hidden_size': trial.suggest_categorical("hidden_size", [96, 128, 160]),
                'num_layers': trial.suggest_int("num_layers", 2, 3),
                'dropout': trial.suggest_float("dropout", 0.3, 0.5),
                'feature_size': None, # Will be set later
                'num_classes': 3,
            }
        else:
            raise ValueError(f"Model '{self.model_to_tune}' not configured for tuning.")

        # --- 2. Run a full Walk-Forward Validation with these parameters ---
        try:
            # --- Data Preparation (must be done inside the objective) ---
            df_processed = create_classification_target(self.full_df.copy(), threshold=target_threshold)
            df_processed.replace([np.inf, -np.inf], np.nan, inplace=True)
            df_processed.dropna(inplace=True)
            if len(df_processed) < seq_length * 10: # Sanity check
                print("Not enough data after processing with current params. Pruning trial.")
                raise optuna.exceptions.TrialPruned()

            features_scaled, targets_data, scaler, final_feature_cols = select_and_scale_features(df_processed, FEATURE_SETS_TO_USE)
            num_features = features_scaled.shape[1]
            model_params['feature_size'] = num_features # Set the dynamic feature size

            full_dataset = StockClassificationDataset(features_scaled, targets_data, seq_length=seq_length)

            # --- Instantiate and Run the WalkForwardTrainer ---
            # We need a slimmed-down version of the trainer that just returns the final Sharpe Ratio
            wf_trainer = WalkForwardTrainer(
                full_dataset=full_dataset,
                full_df=df_processed,
                model_class=model_class,
                model_params=model_params,
                n_splits=3 # Use fewer splits during HPO for speed
            )
            
            # The run method needs to be modified to return the Sharpe Ratio
            final_sharpe = wf_trainer.run(epochs_per_fold=15, quiet=True) # Add quiet mode
            
            # --- 3. Return the score for Optuna to maximize ---
            print(f"--- Trial #{trial.number} Finished. Sharpe Ratio: {final_sharpe:.4f} ---")

            # Update best score if current trial is better
            if final_sharpe > self.best_sharpe:
                self.best_sharpe = final_sharpe
                self.best_params = trial.params
                print(f"!!! New best trial found: Sharpe={self.best_sharpe:.4f}, Params={self.best_params} !!!")

            return final_sharpe

        except Exception as e:
            print(f"Trial #{trial.number} failed with error: {e}. Pruning trial.")
            # Tell Optuna to discard this trial if it fails for any reason
            raise optuna.exceptions.TrialPruned()

    def tune(self, n_trials=50):
        # Create a study object and specify direction is "maximize"
        study = optuna.create_study(direction="maximize")
        study.optimize(self._objective, n_trials=n_trials)

        print("\n\n--- OPTIMIZATION COMPLETE ---")
        print(f"Number of finished trials: {len(study.trials)}")
        print("Best trial:")
        trial = study.best_trial
        print(f"  Value (Sharpe Ratio): {trial.value:.4f}")
        print("  Params: ")
        for key, value in trial.params.items():
            print(f"    {key}: {value}")
        
        # You can also visualize the results
        optuna.visualization.plot_optimization_history(study).show()
        optuna.visualization.plot_param_importances(study).show()

# ==============================================================================
# 5. MAIN EXECUTION
# ==============================================================================
if __name__ == '__main__':
    # --- Configuration ---
    API_KEY = "slkk84FyTZ20BA1tBZFFCEnnCB6wcv_W" # <--- SET YOUR API KEY
    STOCK_SYMBOL = "NVDA"
    MARKET_SYMBOL = "SPY"
    DATA_PERIOD = "5y"
    SEQ_LENGTH = 50
    # [MODIFIED] Using a smaller threshold suitable for a smoother SMA target
    TARGET_THRESHOLD = 0.0002
    DATA_SPAN = "minute"
    DATA_SPAN_MULTIPLYER = "15"
    MODEL_TO_TRAIN = "ComplexCNN" # Options: "ComplexCNN", "CNNLSTM", "ComplexLSTM", "FFNN"
    N_SPLITS_WALK_FORWARD = 5
    TRANSACTION_COST = 0.0001
    NUM_OPTUNA_TRIALS = 15
    BEST_LSTM_PARAMS = {'seq_length': 70, 'target_threshold': 0.0009883508270479432, 'hidden_size': 128, 'num_layers': 2, 'dropout': 0.39857981482178745} # value 0.10452482726255327 
    
    if MODEL_TO_TRAIN == "ComplexCNN":
        model_class = ComplexCNNPredictor
        best_params = {
            'seq_length': 80,
            'target_threshold': 0.0003,
            'num_filters': 128,
            'dropout': 0.43
        }
    elif MODEL_TO_TRAIN == "ComplexLSTM":
        # Add the best params for other models here if you want to test them
        model_class = ComplexLSTMPredictor
        best_params = {
            'seq_length': 70,
            'target_threshold': 0.00098,
            'hidden_size': 128,
            'num_layers': 2,
            'dropout': 0.4
        }
    else:
        raise ValueError(f"Model '{MODEL_TO_TRAIN}' is not configured for validation.")
    print(f"--- Starting Validation for: {MODEL_TO_TRAIN} ---")
    print(f"Using parameters: {best_params}")

    # Define the features and validation settings
    FEATURE_SETS_TO_USE = [
        'trend', 'momentum', 'volatility', 'volume', 
        'candlestick', 'market_context', 'advanced'
    ]
    N_SPLITS_WALK_FORWARD = 5
    TRANSACTION_COST = 0.0005
    EPOCHS_PER_FOLD = 20

    # 1. Load Data
    stock_advisor = TradeAdvisor(symbol=STOCK_SYMBOL, api_key=API_KEY, period=DATA_PERIOD, time_span=DATA_SPAN, multiplyer=DATA_SPAN_MULTIPLYER)
    market_advisor = TradeAdvisor(symbol=MARKET_SYMBOL, api_key=API_KEY, period=DATA_PERIOD, time_span=DATA_SPAN, multiplyer=DATA_SPAN_MULTIPLYER)
    stock_advisor.load_data()
    # print(f"Stock data loaded for {STOCK_SYMBOL}. sector: {stock_advisor.sector}, industry: {stock_advisor.industry}")
    market_advisor.load_data()

    if stock_advisor.data is None or market_advisor.data is None:
        raise ValueError("Data loading failed. Cannot proceed.")
    
    df = stock_advisor.data.copy()
    if market_advisor.data is not None and STOCK_SYMBOL != MARKET_SYMBOL:
        df = merge_market_context(df, market_advisor.data)

    df = add_technical_indicators(df)
    df_with_target = create_classification_target(df, threshold=best_params['target_threshold'])
    df_advanced = add_advanced_features(df_with_target)
    
    df_advanced.replace([np.inf, -np.inf], np.nan, inplace=True)
    df_processed = df_advanced.dropna()
    print(f"Data ready for validation: {len(df_processed)} rows.")
    if df_processed.empty: 
        raise ValueError("DataFrame empty after cleaning.")

    # --- Step 4: Scale Features and Create the PyTorch Dataset ---
    features_scaled, targets_data, scaler, final_feature_cols = select_and_scale_features(df_processed, FEATURE_SETS_TO_USE)
    num_features = features_scaled.shape[1]
    
    full_dataset = StockClassificationDataset(
        features_scaled, 
        targets_data, 
        seq_length=best_params['seq_length']
    )
    print(f"Created full dataset with {len(full_dataset)} sequences.")

    # --- Step 5: Run the Walk-Forward Validation ---
    # Prepare the model parameter dictionary, adding the dynamic feature size
    model_init_params = best_params.copy()
    model_init_params['feature_size'] = num_features
    model_init_params['num_classes'] = 3
    
    # Remove the target_threshold as it's not a model parameter
    model_init_params.pop('target_threshold', None)

    wf_trainer = WalkForwardTrainer(
        full_dataset=full_dataset,
        full_df=df_processed,
        model_class=model_class,
        model_params=model_init_params,
        n_splits=N_SPLITS_WALK_FORWARD
    )

    wf_trainer.run(
        transaction_cost=TRANSACTION_COST,
        epochs_per_fold=EPOCHS_PER_FOLD
    )
    
    # ========= OPTUNA HYPERPARAMETER TUNING =========
    # === Uncomment to run hyperparameter tuning ===
    # tuner = HyperparameterTuner(
    #     full_df=df, # Pass the unprocessed DataFrame
    #     model_to_tune=MODEL_TO_TRAIN
    # )
    # tuner.tune(n_trials=NUM_OPTUNA_TRIALS)
    # =================================================

    # ========= RANDOM STRATEGY BACKTESTING =========
    # Uncomment to run the random strategy backtest
    # random_cumulative_returns = run_random_strategy_backtest( 


    # train_size = int(len(full_dataset) * 0.8)
    
    # # --- [CORRECTED] IMPLEMENT WEIGHTED SAMPLING ---

    # # 1. Get the targets for the training set by slicing the full 'targets' array
    # train_targets = targets[:train_size]

    # # 2. Calculate class weights from the training targets
    # class_counts = np.bincount(train_targets)
    # class_weights = 1. / (class_counts + 1e-6)
    
    # # 3. Assign a weight to every sample in the training set
    # sample_weights = np.array([class_weights[t] for t in train_targets])
    # sample_weights = torch.from_numpy(sample_weights).double()

    # # 4. Create the sampler using the calculated weights
    # sampler = torch.utils.data.WeightedRandomSampler(
    #     weights=sample_weights, 
    #     num_samples=len(sample_weights), 
    #     replacement=True
    # )
    
    # # 5. Create the actual dataset subsets
    # train_dataset = torch.utils.data.Subset(dataset, range(train_size))
    # test_dataset = torch.utils.data.Subset(dataset, range(train_size, len(dataset)))

    # # 6. Use the sampler in the Training DataLoader (shuffle must be False)
    # train_loader = DataLoader(train_dataset, batch_size=32, sampler=sampler)
    # test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)

    # print(f"Data prepared. Features: {feature_cols}. Train size: {len(train_dataset)}, Test size: {len(test_dataset)}")
    # print("Using WeightedRandomSampler to address class imbalance.")


    # # 7. Initialize Model and Trainer
    # device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    # # --- CHOOSE YOUR MODEL ARCHITECTURE HERE ---
    # # model = TimeSeriesTransformerClassifier(feature_size=feature_cols, seq_length=SEQ_LENGTH, nhead=4)
    # # model = LSTMPredictor(feature_size=len(feature_cols), hidden_size=100)
    # # model = CNNPredictor(feature_size=len(feature_cols), seq_length=SEQ_LENGTH) # <--- NEW MODEL
    # model = ComplexCNNPredictor(feature_size=feature_cols, seq_length=SEQ_LENGTH)
    # # model = ComplexLSTMPredictor(feature_size=feature_cols) # <--- NEW, MORE POWERFUL LSTM
    # # model = FFNNPredictor(feature_size=feature_cols, seq_length=SEQ_LENGTH) # <--- NEW FFNN BASELINE MODEL
    # # model = CNNLSTMPredictor(feature_size=feature_cols, seq_length=SEQ_LENGTH) # <--- NEW HYBRID MODEL




    
    # backtest_split_index = df_processed.index.get_loc(df_processed.index[train_size])
    
    # trainer = ModelTrainer(
    #     model=model,
    #     train_loader=train_loader,
    #     test_loader=test_loader,
    #     full_df=df_processed,
    #     split_index=backtest_split_index,
    #     device=device
    # )
    # TRANSACTION_COST = 0.0005 # 0.05% per trade
    # random_cumulative_returns = run_random_strategy_backtest(
    #     full_df=df_processed,
    #     split_index=backtest_split_index,
    #     seq_length=SEQ_LENGTH,
    #     transaction_cost=TRANSACTION_COST
    # )
    # # 8. Run the Pipeline
    # trainer.train(epochs=40)
    # trainer.evaluate()
    # trainer.backtest(random_results=random_cumulative_returns, transaction_cost=TRANSACTION_COST)
    print("\n--- SCRIPT COMPLETE ---")



    print('hello')