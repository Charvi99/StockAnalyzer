import os
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import MinMaxScaler
from sklearn.ensemble import RandomForestClassifier
import ta
from ta.utils import dropna
import talib
import joblib # For saving/loading the scaler

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

def merge_market_context(stock_df, market_df):
    """Merges market data into the primary stock DataFrame."""
    market_features = pd.DataFrame(index=stock_df.index)
    market_features['market_close'] = market_df['Close']
    market_features['market_return'] = market_df['Close'].pct_change()
    merged_df = stock_df.join(market_features, how='left')
    print("Successfully merged market context features.")
    return merged_df

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
    future_sma_returns = (df['sma_target'].shift(-1) - df['sma_target']) / df['sma_target']

    # 3. Create labels based on the SMA's future direction
    df['target'] = 1 # Default to 'Stay'
    df.loc[future_sma_returns > threshold, 'target'] = 2 # Up
    df.loc[future_sma_returns < -threshold, 'target'] = 0 # Down

    # We can now drop the temporary SMA column
    df.drop(columns=['sma_target'], inplace=True)
    
    return df

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

class AIPredictorTool:
    """
    An advanced trading tool that uses a pre-trained AI model to predict
    the next trend direction (Up, Down, Stay).
    """
    def __init__(self, model_path, scaler_path, model_architecture='ComplexCNN', seq_length=40):
        """
        Initializes the tool by loading the pre-trained model and data scaler.

        Args:
            model_path (str): Path to the saved .pth model file.
            scaler_path (str): Path to the saved .pkl scaler file.
            model_architecture (str): The name of the model class to instantiate.
            seq_length (int): The sequence length the model was trained on.
        """
        self.name = f"AI Predictor ({model_architecture})"
        self.seq_length = seq_length
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        self.model = None
        self.scaler = None
        self._signal = "WAIT"
        self._reason = "Model has not been run."

        # Define the feature sets required by this model
        self.feature_sets_to_use = [
            'trend', 'momentum', 'volatility', 'volume', 'candlestick'
        ]

        if not os.path.exists(model_path) or not os.path.exists(scaler_path):
            self._reason = f"Error: Model or scaler file not found. Please train the model first."
            print(f"WARNING for {self.name}: {self._reason}")
        else:
            # Load the data scaler
            self.scaler = joblib.load(scaler_path)
            
            # Determine the number of features from the scaler
            num_features = self.scaler.n_features_in_
            
            # Instantiate the correct model architecture
            if model_architecture == 'ComplexCNN':
                self.model = ComplexCNNPredictor(feature_size=num_features, seq_length=self.seq_length)
            elif model_architecture == 'CNNLSTM':
                self.model = CNNLSTMPredictor(feature_size=num_features, seq_length=self.seq_length)
            # Add other architectures here as needed...
            else:
                raise ValueError(f"Unknown model architecture: {model_architecture}")

            # Load the trained model state
            self.model.load_state_dict(torch.load(model_path, map_location=self.device))
            self.model.to(self.device)
            self.model.eval() # Set model to evaluation mode
            print(f"{self.name} initialized and ready.")

    def _prepare_data(self, df):
        """
        Internal method to take a raw DataFrame and prepare it for the model.
        """
        # 1. Add all features
        df_featured = add_technical_indicators(df)
        
        # 2. Select the required feature columns
        feature_cols = []
        for feature_set in self.feature_sets_to_use:
            feature_cols.extend(INDICATOR_SETS.get(feature_set, []))
        
        final_feature_cols = [col for col in feature_cols if col in df_featured.columns]
        
        # Ensure the columns are in the same order as when the model was trained
        df_final_features = df_featured[final_feature_cols]

        # 3. Scale the features using the loaded scaler
        scaled_features = self.scaler.transform(df_final_features)
        
        return scaled_features

    def analyze(self, data):
        """
        Analyzes the most recent data to generate a prediction.
        """
        if self.model is None or self.scaler is None:
            return # Cannot analyze if model/scaler failed to load

        print(f"[{self.name}] Analyzing latest data...")
        
        # Ensure we have enough data for a full sequence
        if len(data) < self.seq_length:
            self._signal = "WAIT"
            self._reason = f"Not enough data. Need {self.seq_length} bars, but only have {len(data)}."
            return

        # Prepare the most recent `seq_length` data points
        latest_data = data.tail(self.seq_length).copy()
        prepared_data = self._prepare_data(latest_data)

        # Convert to a PyTorch tensor
        input_tensor = torch.tensor(prepared_data, dtype=torch.float32).unsqueeze(0) # Add batch dimension
        input_tensor = input_tensor.to(self.device)

        # Make a prediction
        with torch.no_grad():
            logits = self.model(input_tensor)
            prediction_idx = torch.argmax(logits, dim=1).item()

        # Convert prediction index to a meaningful signal
        signal_map = {0: "SELL", 1: "HOLD", 2: "BUY"}
        self._signal = signal_map.get(prediction_idx, "UNKNOWN")
        self._reason = f"Model predicts the next trend direction will be '{self._signal}'. Confidence (logits): {logits.cpu().numpy().round(2)}"
        print(f"[{self.name}] Analysis complete. Signal: {self._signal}")

    def signal(self):
        """
        Returns the last calculated signal and reason.
        """
        return self._signal, self._reason