"""
TCN (Temporal Convolutional Network) Model Implementation

Uses PyTorch with dilated 1D convolutions for time series
"""
import sys
sys.path.insert(0, '/backend')

from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
import logging

from ml_framework.base import BaseModel
from ml_framework.config import TCNConfig

logger = logging.getLogger(__name__)


class TemporalBlock(nn.Module):
    """Temporal block for TCN"""

    def __init__(self, n_inputs, n_outputs, kernel_size, stride, dilation, padding, dropout=0.2):
        super(TemporalBlock, self).__init__()

        self.conv1 = nn.Conv1d(
            n_inputs, n_outputs, kernel_size,
            stride=stride, padding=padding, dilation=dilation
        )
        self.relu1 = nn.LeakyReLU(0.3)
        self.dropout1 = nn.Dropout(dropout)

        self.conv2 = nn.Conv1d(
            n_outputs, n_outputs, kernel_size,
            stride=stride, padding=padding, dilation=dilation
        )
        self.relu2 = nn.LeakyReLU(0.3)
        self.dropout2 = nn.Dropout(dropout)

        self.net = nn.Sequential(self.conv1, self.relu1, self.dropout1, self.conv2, self.relu2, self.dropout2)
        self.downsample = nn.Conv1d(n_inputs, n_outputs, 1) if n_inputs != n_outputs else None
        self.relu = nn.LeakyReLU(0.3)

    def forward(self, x):
        out = self.net(x)
        res = x if self.downsample is None else self.downsample(x)
        return self.relu(out + res)


class TemporalConvNet(nn.Module):
    """Temporal Convolutional Network"""

    def __init__(self, num_inputs, num_channels, kernel_size=3, dropout=0.2):
        super(TemporalConvNet, self).__init__()

        layers = []
        num_levels = len(num_channels)

        for i in range(num_levels):
            dilation_size = 2 ** i
            in_channels = num_inputs if i == 0 else num_channels[i-1]
            out_channels = num_channels[i]

            padding = (kernel_size - 1) * dilation_size
            self.add_module(f'temporal_block_{i}',
                          TemporalBlock(in_channels, out_channels, kernel_size, stride=1,
                                       dilation=dilation_size, padding=padding, dropout=dropout))

        self.network = nn.Sequential(*layers)
        self.fc = nn.Linear(num_channels[-1], 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        # x shape: (batch_size, seq_len, features)
        # Transpose to (batch_size, features, seq_len) for Conv1d
        x = x.transpose(1, 2)

        out = self.network(x)

        # Global max pooling
        out = F.max_pool1d(out, out.size(2))
        out = out.squeeze(2)

        out = self.fc(out)
        return self.sigmoid(out)


class TCNModel(BaseModel):
    """TCN model wrapper"""

    def __init__(self, config: TCNConfig, trial_params: Optional[Dict] = None):
        """
        Initialize TCN model

        Args:
            config: TCN configuration
            trial_params: Hyperparameters from Optuna trial (overrides config)
        """
        super().__init__(config, "tcn")
        self.trial_params = trial_params or {}
        self.device = torch.device(config.device)

    def build_model(self, input_shape: Tuple[int, int] = None, **kwargs):
        """
        Build TCN model

        Args:
            input_shape: (sequence_length, n_features)
        """
        # Determine number of input features
        if input_shape is not None:
            n_features = input_shape[1]
        else:
            n_features = 45  # Default

        # Merge config with trial params
        num_channels = self.config.num_channels
        if 'num_layers' in self.trial_params:
            num_layers = int(self.trial_params['num_layers'])
            num_channels = [64, 128, 64][:num_layers]

        kernel_size = self.trial_params.get('kernel_size', self.config.kernel_size)
        dropout = self.trial_params.get('dropout', self.config.dropout)

        self.model = TemporalConvNet(
            num_inputs=n_features,
            num_channels=num_channels,
            kernel_size=kernel_size,
            dropout=dropout
        )

        self.model.to(self.device)

        # Loss function
        self.criterion = nn.BCELoss()

        # Optimizer
        learning_rate = self.trial_params.get('learning_rate', 0.001)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)

        # Learning rate scheduler
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode='min', factor=0.5, patience=5, verbose=False
        )

        logger.info(f"✅ TCN model built on device: {self.device}")

        return self.model

    def prepare_data(self, X: pd.DataFrame, y: np.ndarray, sequence_length: int = 60):
        """
        Prepare data for TCN (create sequences)

        Args:
            X: Features DataFrame
            y: Labels
            sequence_length: Length of input sequences

        Returns:
            DataLoader
        """
        # Create sequences
        X_seq, y_seq = [], []

        for i in range(sequence_length, len(X)):
            X_seq.append(X.iloc[i-sequence_length:i].values)
            y_seq.append(y.iloc[i])  # Fixed: use .iloc[] for positional indexing

        X_seq = np.array(X_seq, dtype=np.float32)
        y_seq = np.array(y_seq, dtype=np.float32)

        # Convert to tensors
        X_tensor = torch.FloatTensor(X_seq)
        y_tensor = torch.FloatTensor(y_seq).unsqueeze(1)

        # Create dataset and dataloader
        dataset = TensorDataset(X_tensor, y_tensor)
        dataloader = DataLoader(
            dataset,
            batch_size=self.config.batch_size,
            shuffle=True
        )

        return dataloader

    def train(self, X_train, y_train, X_val, y_val, **kwargs):
        """Train TCN model"""
        if self.model is None:
            # Infer input shape from data
            sequence_length = 60
            input_shape = (sequence_length, X_train.shape[1])
            self.build_model(input_shape=input_shape)

        # Store feature columns
        self.feature_cols = X_train.columns.tolist()

        # Prepare data
        train_loader = self.prepare_data(X_train, y_train)
        val_loader = self.prepare_data(X_val, y_val)

        # Training loop
        best_val_loss = float('inf')
        patience_counter = 0

        for epoch in range(self.config.epochs):
            # Training phase
            self.model.train()
            train_loss = 0.0

            for X_batch, y_batch in train_loader:
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device)

                self.optimizer.zero_grad()
                outputs = self.model(X_batch)
                loss = self.criterion(outputs, y_batch)
                loss.backward()
                self.optimizer.step()

                train_loss += loss.item()

            train_loss /= len(train_loader)

            # Validation phase
            self.model.eval()
            val_loss = 0.0

            with torch.no_grad():
                for X_batch, y_batch in val_loader:
                    X_batch = X_batch.to(self.device)
                    y_batch = y_batch.to(self.device)

                    outputs = self.model(X_batch)
                    loss = self.criterion(outputs, y_batch)
                    val_loss += loss.item()

            val_loss /= len(val_loader)

            # Learning rate scheduling
            self.scheduler.step(val_loss)

            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0

                # Save best model
                torch.save(self.model.state_dict(), 'best_model.pth')
            else:
                patience_counter += 1
                if patience_counter >= self.config.early_stopping_patience:
                    logger.info(f"Early stopping at epoch {epoch+1}")
                    break

            # Log every 10 epochs
            if (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch+1}: train_loss={train_loss:.4f}, val_loss={val_loss:.4f}")

        # Load best model
        self.model.load_state_dict(torch.load('best_model.pth'))
        self.is_fitted = True

        logger.info(f"✅ TCN trained. Best val_loss: {best_val_loss:.4f}")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make binary predictions"""
        proba = self.predict_proba(X)
        return (proba[:, 1] > 0.5).astype(int)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict probabilities"""
        if not self.is_fitted:
            raise ValueError("Model not fitted.")

        self.model.eval()

        sequence_length = 60
        if len(X) < sequence_length:
            raise ValueError(f"Need at least {sequence_length} samples, got {len(X)}")

        # Create last sequence
        X_seq = X.iloc[-sequence_length:].values[np.newaxis, :, :]
        X_tensor = torch.FloatTensor(X_seq.astype(np.float32)).to(self.device)

        with torch.no_grad():
            proba = self.model(X_tensor).cpu().numpy()

        # Convert to binary probabilities (2 columns)
        proba_full = np.column_stack([1 - proba.flatten(), proba.flatten()])

        return proba_full

    def evaluate(self, X_test, y_test) -> Dict[str, float]:
        """Evaluate model on test set"""
        # Skip first sequence_length samples
        y_test_seq = y_test[60:]

        # Prepare predictions
        proba_list = []
        for i in range(60, len(X_test)):
            X_seq = X_test.iloc[i-60:i].values[np.newaxis, :, :]
            X_tensor = torch.FloatTensor(X_seq.astype(np.float32)).to(self.device)

            self.model.eval()
            with torch.no_grad():
                proba = self.model(X_tensor).cpu().numpy()[0, 0]

            proba_list.append(proba)

        y_prob = np.array(proba_list)
        y_pred = (y_prob > 0.5).astype(int)

        metrics = {
            'accuracy': accuracy_score(y_test_seq, y_pred),
            'precision': precision_score(y_test_seq, y_pred, zero_division=0),
            'recall': recall_score(y_test_seq, y_pred, zero_division=0),
            'auc': roc_auc_score(y_test_seq, y_prob) if len(np.unique(y_test_seq)) > 1 else 0.5
        }

        return metrics

    def _save_model(self, path: Path):
        """Save TCN model"""
        torch.save(self.model.state_dict(), str(path / 'model.pth'))

        # Save config
        config_dict = {
            'num_channels': self.config.num_channels,
            'kernel_size': self.config.kernel_size,
            'dropout': self.config.dropout,
            'feature_cols': self.feature_cols
        }

        import json
        with open(path / 'config.json', 'w') as f:
            json.dump(config_dict, f, indent=2)

    def _load_model(self, path: Path):
        """Load TCN model"""
        # Load config
        import json
        with open(path / 'config.json', 'r') as f:
            config_dict = json.load(f)

        self.feature_cols = config_dict['feature_cols']
        n_features = len(self.feature_cols)

        # Rebuild model
        self.model = TemporalConvNet(
            num_inputs=n_features,
            num_channels=config_dict['num_channels'],
            kernel_size=config_dict['kernel_size'],
            dropout=config_dict['dropout']
        )

        self.model.load_state_dict(torch.load(str(path / 'model.pth')))
        self.model.to(self.device)
        self.model.eval()
        self.is_fitted = True
