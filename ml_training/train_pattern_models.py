"""
Chart Pattern Recognition - LSTM vs GRU Proof of Concept
Trains and compares Tiny LSTM and GRU models for binary pattern classification

Usage:
    python train_pattern_models.py
"""

import json
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime
import pandas as pd

import tensorflow as tf
from tensorflow.keras import layers, models, callbacks
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_curve,
    auc,
    precision_recall_curve
)

# Set random seeds for reproducibility
np.random.seed(42)
tf.random.set_seed(42)

# Configure output directories
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)
MODELS_DIR = OUTPUT_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)
PLOTS_DIR = OUTPUT_DIR / "plots"
PLOTS_DIR.mkdir(exist_ok=True)


class DataLoader:
    """Load and preprocess training data from API export"""

    def __init__(self, json_file='training_data.json'):
        self.json_file = json_file
        self.data = None
        self.X = None
        self.y = None
        self.metadata = {}

    def load_data(self):
        """Load training data from JSON export"""
        print(f"\n{'='*60}")
        print("LOADING TRAINING DATA")
        print(f"{'='*60}")

        with open(self.json_file, 'r') as f:
            self.data = json.load(f)

        print(f"[OK] Loaded {len(self.data)} samples from {self.json_file}")

        # Analyze dataset
        self._analyze_dataset()

        return self

    def _analyze_dataset(self):
        """Analyze and print dataset statistics"""
        labels = [s['label'] for s in self.data]
        true_pos = sum(1 for l in labels if l == 'true_positive')
        false_pos = len(labels) - true_pos

        pattern_types = {}
        for sample in self.data:
            ptype = sample['pattern_name']
            pattern_types[ptype] = pattern_types.get(ptype, 0) + 1

        print(f"\nDataset Statistics:")
        print(f"  Total samples:     {len(self.data)}")
        print(f"  True positives:    {true_pos} ({true_pos/len(self.data)*100:.1f}%)")
        print(f"  False positives:   {false_pos} ({false_pos/len(self.data)*100:.1f}%)")
        print(f"  Pattern types:     {len(pattern_types)}")

        print(f"\nTop 5 Pattern Types:")
        for ptype, count in sorted(pattern_types.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {ptype:25} {count:3}")

        self.metadata['dataset_info'] = {
            'total_samples': len(self.data),
            'true_positives': true_pos,
            'false_positives': false_pos,
            'pattern_types': pattern_types
        }

    def preprocess(self):
        """Preprocess OHLC data and create training arrays"""
        print(f"\n{'='*60}")
        print("PREPROCESSING DATA")
        print(f"{'='*60}")

        X = []
        y = []
        sequence_lengths = []

        # First pass: Extract and normalize sequences
        for sample in self.data:
            # Extract OHLC sequence
            ohlc_sequence = []
            for candle in sample['ohlc_data']:
                ohlc_sequence.append([
                    candle['open'],
                    candle['high'],
                    candle['low'],
                    candle['close'],
                    candle['volume']
                ])

            ohlc_array = np.array(ohlc_sequence, dtype=np.float32)
            sequence_lengths.append(len(ohlc_array))

            # Normalize using sample's metadata
            price_range = sample['price_max'] - sample['price_min']
            if price_range > 0:
                # Normalize prices to [0, 1]
                ohlc_array[:, :4] = (ohlc_array[:, :4] - sample['price_min']) / price_range

            # Normalize volume
            if sample['volume_max'] > 0:
                ohlc_array[:, 4] = ohlc_array[:, 4] / sample['volume_max']

            X.append(ohlc_array)

            # Binary label: 1 = true_positive, 0 = false_positive
            y.append(1 if sample['label'] == 'true_positive' else 0)

        # Find max sequence length
        max_length = max(sequence_lengths)
        min_length = min(sequence_lengths)
        avg_length = np.mean(sequence_lengths)

        print(f"\nSequence length statistics:")
        print(f"  Min:     {min_length} candles")
        print(f"  Max:     {max_length} candles")
        print(f"  Average: {avg_length:.1f} candles")

        # Pad sequences to max_length
        print(f"\nPadding sequences to {max_length} candles...")
        X_padded = []
        for seq in X:
            # Pad with zeros if needed
            if len(seq) < max_length:
                padding = np.zeros((max_length - len(seq), 5), dtype=np.float32)
                seq_padded = np.vstack([seq, padding])
            else:
                seq_padded = seq
            X_padded.append(seq_padded)

        self.X = np.array(X_padded, dtype=np.float32)
        self.y = np.array(y, dtype=np.int32)

        print(f"\n[OK] Preprocessed data shape:")
        print(f"  X: {self.X.shape} (samples, timesteps, features)")
        print(f"  y: {self.y.shape} (samples,)")
        print(f"  Sequence length: {self.X.shape[1]} candles (padded)")
        print(f"  Features: {self.X.shape[2]} (OHLCV)")

        self.metadata['data_shape'] = {
            'samples': self.X.shape[0],
            'timesteps': self.X.shape[1],
            'features': self.X.shape[2],
            'min_sequence_length': min_length,
            'max_sequence_length': max_length,
            'avg_sequence_length': float(avg_length)
        }

        return self.X, self.y


class ModelFactory:
    """Factory for creating LSTM and GRU models"""

    @staticmethod
    def create_tiny_lstm(input_shape):
        """
        Tiny LSTM Model
        - Bidirectional LSTM for better context
        - ~15K parameters
        - Best for 200-500 samples
        - Uses masking to ignore padded zeros
        """
        model = models.Sequential([
            # Masking layer to ignore padded zeros
            layers.Masking(mask_value=0.0, input_shape=input_shape, name='masking'),

            layers.Bidirectional(
                layers.LSTM(32, return_sequences=False),
                name='bidirectional_lstm'
            ),
            layers.Dropout(0.4, name='dropout_lstm'),

            layers.Dense(16, activation='relu', name='dense_hidden'),
            layers.Dropout(0.3, name='dropout_dense'),

            layers.Dense(1, activation='sigmoid', name='output')
        ], name='TinyLSTM')

        return model

    @staticmethod
    def create_tiny_gru(input_shape):
        """
        Tiny GRU Model
        - Simpler than LSTM (fewer parameters)
        - ~10K parameters
        - Best for 150-400 samples
        - Uses masking to ignore padded zeros
        """
        model = models.Sequential([
            # Masking layer to ignore padded zeros
            layers.Masking(mask_value=0.0, input_shape=input_shape, name='masking'),

            layers.Bidirectional(
                layers.GRU(24, return_sequences=False),
                name='bidirectional_gru'
            ),
            layers.Dropout(0.4, name='dropout_gru'),

            layers.Dense(12, activation='relu', name='dense_hidden'),
            layers.Dropout(0.3, name='dropout_dense'),

            layers.Dense(1, activation='sigmoid', name='output')
        ], name='TinyGRU')

        return model

    @staticmethod
    def compile_model(model):
        """Compile model with optimizer and metrics"""
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
            loss='binary_crossentropy',
            metrics=[
                'accuracy',
                tf.keras.metrics.Precision(name='precision'),
                tf.keras.metrics.Recall(name='recall'),
                tf.keras.metrics.AUC(name='auc')
            ]
        )
        return model


class Trainer:
    """Train and evaluate models"""

    def __init__(self, X, y, test_size=0.3, val_size=0.5):
        self.X = X
        self.y = y
        self.test_size = test_size
        self.val_size = val_size

        # Split data
        self._split_data()

        self.history = {}
        self.models = {}
        self.results = {}

    def _split_data(self):
        """Split data into train/val/test sets"""
        print(f"\n{'='*60}")
        print("SPLITTING DATA")
        print(f"{'='*60}")

        # First split: train + val vs test
        X_temp, self.X_test, y_temp, self.y_test = train_test_split(
            self.X, self.y,
            test_size=self.test_size,
            random_state=42,
            stratify=self.y
        )

        # Second split: train vs val
        self.X_train, self.X_val, self.y_train, self.y_val = train_test_split(
            X_temp, y_temp,
            test_size=self.val_size,
            random_state=42,
            stratify=y_temp
        )

        print(f"[OK] Data split:")
        print(f"  Train: {len(self.X_train):3} samples ({len(self.X_train)/len(self.X)*100:.1f}%)")
        print(f"  Val:   {len(self.X_val):3} samples ({len(self.X_val)/len(self.X)*100:.1f}%)")
        print(f"  Test:  {len(self.X_test):3} samples ({len(self.X_test)/len(self.X)*100:.1f}%)")

        print(f"\n  Train class balance: {np.sum(self.y_train)}/{len(self.y_train) - np.sum(self.y_train)} (pos/neg)")
        print(f"  Val class balance:   {np.sum(self.y_val)}/{len(self.y_val) - np.sum(self.y_val)} (pos/neg)")
        print(f"  Test class balance:  {np.sum(self.y_test)}/{len(self.y_test) - np.sum(self.y_test)} (pos/neg)")

    def train_model(self, model_name, model, epochs=100, batch_size=16):
        """Train a single model"""
        print(f"\n{'='*60}")
        print(f"TRAINING {model_name.upper()}")
        print(f"{'='*60}")

        model.summary()

        # Callbacks
        early_stop = callbacks.EarlyStopping(
            monitor='val_loss',
            patience=20,
            restore_best_weights=True,
            verbose=1
        )

        reduce_lr = callbacks.ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=10,
            min_lr=1e-6,
            verbose=1
        )

        # Train
        print(f"\nStarting training...")
        history = model.fit(
            self.X_train, self.y_train,
            validation_data=(self.X_val, self.y_val),
            epochs=epochs,
            batch_size=batch_size,
            callbacks=[early_stop, reduce_lr],
            verbose=2
        )

        self.models[model_name] = model
        self.history[model_name] = history

        print(f"\n[OK] Training completed for {model_name}")
        print(f"  Best epoch: {early_stop.best_epoch + 1}")
        print(f"  Best val_loss: {early_stop.best:.4f}")

        return model, history

    def evaluate_model(self, model_name):
        """Evaluate model on test set"""
        print(f"\n{'='*60}")
        print(f"EVALUATING {model_name.upper()}")
        print(f"{'='*60}")

        model = self.models[model_name]

        # Evaluate on test set
        test_metrics = model.evaluate(self.X_test, self.y_test, verbose=0)

        # Get predictions
        y_pred_prob = model.predict(self.X_test, verbose=0)
        y_pred = (y_pred_prob > 0.5).astype(int).flatten()

        # Calculate metrics
        test_loss, test_acc, test_prec, test_rec, test_auc = test_metrics
        f1_score = 2 * test_prec * test_rec / (test_prec + test_rec + 1e-7)

        # Store results
        self.results[model_name] = {
            'loss': test_loss,
            'accuracy': test_acc,
            'precision': test_prec,
            'recall': test_rec,
            'f1_score': f1_score,
            'auc': test_auc,
            'y_true': self.y_test,
            'y_pred': y_pred,
            'y_pred_prob': y_pred_prob.flatten()
        }

        # Print results
        print(f"\nTest Set Results:")
        print(f"  Loss:      {test_loss:.4f}")
        print(f"  Accuracy:  {test_acc:.4f}")
        print(f"  Precision: {test_prec:.4f}")
        print(f"  Recall:    {test_rec:.4f}")
        print(f"  F1-Score:  {f1_score:.4f}")
        print(f"  AUC:       {test_auc:.4f}")

        print(f"\nClassification Report:")
        print(classification_report(
            self.y_test, y_pred,
            target_names=['False Pattern', 'True Pattern'],
            digits=4
        ))

        print(f"\nConfusion Matrix:")
        cm = confusion_matrix(self.y_test, y_pred)
        print(cm)
        print(f"  [[TN={cm[0,0]:2} FP={cm[0,1]:2}]")
        print(f"   [FN={cm[1,0]:2} TP={cm[1,1]:2}]]")

        return self.results[model_name]

    def save_model(self, model_name):
        """Save trained model"""
        model = self.models[model_name]
        filepath = MODELS_DIR / f"{model_name.lower()}.keras"
        model.save(filepath)
        print(f"\n[OK] Model saved: {filepath}")


class Visualizer:
    """Create visualizations for model comparison"""

    @staticmethod
    def plot_training_history(history_dict):
        """Plot training history for all models"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Training History Comparison', fontsize=16, fontweight='bold')

        metrics = [
            ('loss', 'Loss'),
            ('accuracy', 'Accuracy'),
            ('precision', 'Precision'),
            ('recall', 'Recall')
        ]

        for idx, (metric, title) in enumerate(metrics):
            ax = axes[idx // 2, idx % 2]

            for model_name, history in history_dict.items():
                # Training metric
                ax.plot(history.history[metric],
                       label=f'{model_name} Train',
                       linewidth=2)
                # Validation metric
                ax.plot(history.history[f'val_{metric}'],
                       label=f'{model_name} Val',
                       linestyle='--',
                       linewidth=2)

            ax.set_xlabel('Epoch')
            ax.set_ylabel(title)
            ax.set_title(title)
            ax.legend()
            ax.grid(True, alpha=0.3)

        plt.tight_layout()
        filepath = PLOTS_DIR / 'training_history.png'
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        print(f"[OK] Saved: {filepath}")
        plt.close()

    @staticmethod
    def plot_confusion_matrices(results_dict):
        """Plot confusion matrices for all models"""
        n_models = len(results_dict)
        fig, axes = plt.subplots(1, n_models, figsize=(6*n_models, 5))

        if n_models == 1:
            axes = [axes]

        fig.suptitle('Confusion Matrices', fontsize=16, fontweight='bold')

        for idx, (model_name, results) in enumerate(results_dict.items()):
            cm = confusion_matrix(results['y_true'], results['y_pred'])

            sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                       xticklabels=['False', 'True'],
                       yticklabels=['False', 'True'],
                       ax=axes[idx],
                       cbar=True,
                       square=True)

            axes[idx].set_title(f'{model_name}\nAcc: {results["accuracy"]:.3f}')
            axes[idx].set_ylabel('True Label')
            axes[idx].set_xlabel('Predicted Label')

        plt.tight_layout()
        filepath = PLOTS_DIR / 'confusion_matrices.png'
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        print(f"[OK] Saved: {filepath}")
        plt.close()

    @staticmethod
    def plot_roc_curves(results_dict):
        """Plot ROC curves for all models"""
        plt.figure(figsize=(10, 8))

        for model_name, results in results_dict.items():
            fpr, tpr, _ = roc_curve(results['y_true'], results['y_pred_prob'])
            roc_auc = auc(fpr, tpr)

            plt.plot(fpr, tpr, linewidth=2,
                    label=f'{model_name} (AUC = {roc_auc:.3f})')

        plt.plot([0, 1], [0, 1], 'k--', linewidth=1, label='Random')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate', fontsize=12)
        plt.ylabel('True Positive Rate', fontsize=12)
        plt.title('ROC Curves', fontsize=14, fontweight='bold')
        plt.legend(loc="lower right", fontsize=10)
        plt.grid(True, alpha=0.3)

        filepath = PLOTS_DIR / 'roc_curves.png'
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        print(f"[OK] Saved: {filepath}")
        plt.close()

    @staticmethod
    def plot_precision_recall_curves(results_dict):
        """Plot Precision-Recall curves"""
        plt.figure(figsize=(10, 8))

        for model_name, results in results_dict.items():
            precision, recall, _ = precision_recall_curve(
                results['y_true'],
                results['y_pred_prob']
            )

            plt.plot(recall, precision, linewidth=2,
                    label=f'{model_name} (F1 = {results["f1_score"]:.3f})')

        plt.xlabel('Recall', fontsize=12)
        plt.ylabel('Precision', fontsize=12)
        plt.title('Precision-Recall Curves', fontsize=14, fontweight='bold')
        plt.legend(loc="lower left", fontsize=10)
        plt.grid(True, alpha=0.3)

        filepath = PLOTS_DIR / 'precision_recall_curves.png'
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        print(f"[OK] Saved: {filepath}")
        plt.close()

    @staticmethod
    def plot_model_comparison(results_dict):
        """Bar chart comparing model metrics"""
        metrics = ['accuracy', 'precision', 'recall', 'f1_score', 'auc']
        model_names = list(results_dict.keys())

        data = {metric: [results_dict[m][metric] for m in model_names]
                for metric in metrics}

        x = np.arange(len(metrics))
        width = 0.35

        fig, ax = plt.subplots(figsize=(12, 6))

        for idx, model_name in enumerate(model_names):
            values = [data[metric][idx] for metric in metrics]
            offset = width * (idx - len(model_names)/2 + 0.5)
            bars = ax.bar(x + offset, values, width, label=model_name)

            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.3f}',
                       ha='center', va='bottom', fontsize=9)

        ax.set_xlabel('Metrics', fontsize=12)
        ax.set_ylabel('Score', fontsize=12)
        ax.set_title('Model Performance Comparison', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels([m.upper() for m in metrics])
        ax.legend()
        ax.set_ylim([0, 1.1])
        ax.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()
        filepath = PLOTS_DIR / 'model_comparison.png'
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        print(f"[OK] Saved: {filepath}")
        plt.close()


def save_results_summary(results_dict, metadata):
    """Save comprehensive results summary"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = OUTPUT_DIR / f'results_summary_{timestamp}.txt'

    with open(filepath, 'w') as f:
        f.write("="*70 + "\n")
        f.write("CHART PATTERN RECOGNITION - RESULTS SUMMARY\n")
        f.write("="*70 + "\n\n")

        f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Dataset info
        f.write("-"*70 + "\n")
        f.write("DATASET INFORMATION\n")
        f.write("-"*70 + "\n")
        if 'dataset_info' in metadata:
            info = metadata['dataset_info']
            f.write(f"Total samples:     {info['total_samples']}\n")
            f.write(f"True positives:    {info['true_positives']}\n")
            f.write(f"False positives:   {info['false_positives']}\n")
            f.write(f"Pattern types:     {len(info['pattern_types'])}\n\n")

        if 'data_shape' in metadata:
            shape = metadata['data_shape']
            f.write(f"Data shape:\n")
            f.write(f"  Samples:    {shape['samples']}\n")
            f.write(f"  Timesteps:  {shape['timesteps']}\n")
            f.write(f"  Features:   {shape['features']}\n\n")

        # Model results
        f.write("-"*70 + "\n")
        f.write("MODEL PERFORMANCE\n")
        f.write("-"*70 + "\n\n")

        for model_name, results in results_dict.items():
            f.write(f"{model_name}:\n")
            f.write(f"  Accuracy:  {results['accuracy']:.4f}\n")
            f.write(f"  Precision: {results['precision']:.4f}\n")
            f.write(f"  Recall:    {results['recall']:.4f}\n")
            f.write(f"  F1-Score:  {results['f1_score']:.4f}\n")
            f.write(f"  AUC:       {results['auc']:.4f}\n")
            f.write(f"  Loss:      {results['loss']:.4f}\n\n")

        # Best model
        best_model = max(results_dict.items(), key=lambda x: x[1]['f1_score'])
        f.write(f"Best Model: {best_model[0]} (F1-Score: {best_model[1]['f1_score']:.4f})\n\n")

        f.write("="*70 + "\n")

    print(f"\n[OK] Results summary saved: {filepath}")


def main():
    """Main training pipeline"""
    print("\n" + "="*70)
    print(" CHART PATTERN RECOGNITION - LSTM vs GRU")
    print(" Proof of Concept Training Pipeline")
    print("="*70)

    # 1. Load and preprocess data
    loader = DataLoader('training_data.json')
    loader.load_data()
    X, y = loader.preprocess()

    # 2. Initialize trainer
    trainer = Trainer(X, y)

    # 3. Get input shape
    input_shape = (X.shape[1], X.shape[2])  # (timesteps, features)

    # 4. Create and train LSTM model
    lstm_model = ModelFactory.create_tiny_lstm(input_shape)
    lstm_model = ModelFactory.compile_model(lstm_model)
    trainer.train_model('LSTM', lstm_model, epochs=100, batch_size=16)
    trainer.evaluate_model('LSTM')
    trainer.save_model('LSTM')

    # 5. Create and train GRU model
    gru_model = ModelFactory.create_tiny_gru(input_shape)
    gru_model = ModelFactory.compile_model(gru_model)
    trainer.train_model('GRU', gru_model, epochs=100, batch_size=16)
    trainer.evaluate_model('GRU')
    trainer.save_model('GRU')

    # 6. Create visualizations
    print(f"\n{'='*60}")
    print("CREATING VISUALIZATIONS")
    print(f"{'='*60}")

    Visualizer.plot_training_history(trainer.history)
    Visualizer.plot_confusion_matrices(trainer.results)
    Visualizer.plot_roc_curves(trainer.results)
    Visualizer.plot_precision_recall_curves(trainer.results)
    Visualizer.plot_model_comparison(trainer.results)

    # 7. Save results summary
    save_results_summary(trainer.results, loader.metadata)

    # 8. Final summary
    print(f"\n{'='*60}")
    print("TRAINING COMPLETED")
    print(f"{'='*60}")

    print(f"\nComparison:")
    for model_name in ['LSTM', 'GRU']:
        results = trainer.results[model_name]
        print(f"\n{model_name}:")
        print(f"  F1-Score: {results['f1_score']:.4f}")
        print(f"  Accuracy: {results['accuracy']:.4f}")
        print(f"  AUC:      {results['auc']:.4f}")

    # Determine winner
    best_model = max(trainer.results.items(), key=lambda x: x[1]['f1_score'])
    print(f"\n[WINNER] Best Model: {best_model[0]} (F1-Score: {best_model[1]['f1_score']:.4f})")

    print(f"\nOutputs saved in: {OUTPUT_DIR.absolute()}")
    print(f"  Models:  {MODELS_DIR.absolute()}")
    print(f"  Plots:   {PLOTS_DIR.absolute()}")

    print("\n" + "="*70)


if __name__ == '__main__':
    main()
