"""
Chart Pattern Classifier - Multi-Class Pattern Recognition
Trains LSTM and GRU models to recognize specific chart pattern types

Usage:
    python train_pattern_classifier.py

This trains models to classify patterns into 16 categories instead of binary valid/invalid.
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
    top_k_accuracy_score
)

# Set random seeds for reproducibility
np.random.seed(42)
tf.random.set_seed(42)

# Configure output directories
OUTPUT_DIR = Path("outputs_multiclass")
OUTPUT_DIR.mkdir(exist_ok=True)
MODELS_DIR = OUTPUT_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)
PLOTS_DIR = OUTPUT_DIR / "plots"
PLOTS_DIR.mkdir(exist_ok=True)


class DataLoader:
    """Load and preprocess training data for multi-class classification"""

    def __init__(self, json_file='training_data.json', min_samples_per_class=5):
        self.json_file = json_file
        self.min_samples_per_class = min_samples_per_class
        self.data = None
        self.X = None
        self.y = None
        self.pattern_to_idx = {}
        self.idx_to_pattern = {}
        self.metadata = {}

    def load_data(self):
        """Load training data from JSON export"""
        print(f"\n{'='*60}")
        print("LOADING TRAINING DATA (MULTI-CLASS)")
        print(f"{'='*60}")

        with open(self.json_file, 'r') as f:
            self.data = json.load(f)

        print(f"[OK] Loaded {len(self.data)} samples from {self.json_file}")

        # Only use TRUE POSITIVES for pattern classification
        # (We're classifying which pattern it is, not if it's valid)
        self.data = [s for s in self.data if s['label'] == 'true_positive']
        print(f"[OK] Filtered to {len(self.data)} true positive samples")

        # Analyze dataset
        self._analyze_dataset()

        return self

    def _analyze_dataset(self):
        """Analyze and print dataset statistics"""
        pattern_types = {}
        for sample in self.data:
            ptype = sample['pattern_name']
            pattern_types[ptype] = pattern_types.get(ptype, 0) + 1

        # Filter out patterns with too few samples
        valid_patterns = {p: c for p, c in pattern_types.items()
                         if c >= self.min_samples_per_class}
        removed_patterns = {p: c for p, c in pattern_types.items()
                          if c < self.min_samples_per_class}

        if removed_patterns:
            print(f"\n[WARNING] Removing {len(removed_patterns)} pattern(s) with < {self.min_samples_per_class} samples:")
            for ptype, count in sorted(removed_patterns.items()):
                print(f"  {ptype:30} {count:3}")

            # Filter data
            self.data = [s for s in self.data if s['pattern_name'] in valid_patterns]

        # Create label mapping
        pattern_names = sorted(valid_patterns.keys())
        self.pattern_to_idx = {name: idx for idx, name in enumerate(pattern_names)}
        self.idx_to_pattern = {idx: name for name, idx in self.pattern_to_idx.items()}

        print(f"\nDataset Statistics:")
        print(f"  Total samples:     {len(self.data)}")
        print(f"  Pattern classes:   {len(valid_patterns)}")
        print(f"  Min per class:     {min(valid_patterns.values())}")
        print(f"  Max per class:     {max(valid_patterns.values())}")
        print(f"  Avg per class:     {len(self.data) / len(valid_patterns):.1f}")

        print(f"\nPattern Distribution:")
        for ptype, count in sorted(valid_patterns.items(), key=lambda x: x[1], reverse=True):
            pct = count / len(self.data) * 100
            bar = '#' * int(pct / 2)
            print(f"  {ptype:30} {count:3} ({pct:5.1f}%) {bar}")

        self.metadata['dataset_info'] = {
            'total_samples': len(self.data),
            'n_classes': len(valid_patterns),
            'pattern_types': valid_patterns,
            'pattern_to_idx': self.pattern_to_idx
        }

    def preprocess(self):
        """Preprocess OHLC data and create training arrays"""
        print(f"\n{'='*60}")
        print("PREPROCESSING DATA")
        print(f"{'='*60}")

        X = []
        y = []
        sequence_lengths = []

        # Extract and normalize sequences
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

            # Multi-class label: pattern name to integer
            pattern_idx = self.pattern_to_idx[sample['pattern_name']]
            y.append(pattern_idx)

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
        print(f"  Classes: {len(self.pattern_to_idx)}")

        self.metadata['data_shape'] = {
            'samples': self.X.shape[0],
            'timesteps': self.X.shape[1],
            'features': self.X.shape[2],
            'n_classes': len(self.pattern_to_idx),
            'min_sequence_length': min_length,
            'max_sequence_length': max_length,
            'avg_sequence_length': float(avg_length)
        }

        return self.X, self.y


class ModelFactory:
    """Factory for creating multi-class LSTM and GRU models"""

    @staticmethod
    def create_lstm_classifier(input_shape, n_classes):
        """
        LSTM Pattern Classifier
        - Bidirectional LSTM for temporal context
        - Softmax output for multi-class classification
        """
        model = models.Sequential([
            # Masking layer to ignore padded zeros
            layers.Masking(mask_value=0.0, input_shape=input_shape, name='masking'),

            layers.Bidirectional(
                layers.LSTM(64, return_sequences=False),
                name='bidirectional_lstm'
            ),
            layers.Dropout(0.5, name='dropout_lstm'),

            layers.Dense(32, activation='relu', name='dense_hidden'),
            layers.Dropout(0.3, name='dropout_dense'),

            layers.Dense(n_classes, activation='softmax', name='output')
        ], name='LSTMClassifier')

        return model

    @staticmethod
    def create_gru_classifier(input_shape, n_classes):
        """
        GRU Pattern Classifier
        - Bidirectional GRU (faster than LSTM)
        - Softmax output for multi-class classification
        """
        model = models.Sequential([
            # Masking layer to ignore padded zeros
            layers.Masking(mask_value=0.0, input_shape=input_shape, name='masking'),

            layers.Bidirectional(
                layers.GRU(48, return_sequences=False),
                name='bidirectional_gru'
            ),
            layers.Dropout(0.5, name='dropout_gru'),

            layers.Dense(24, activation='relu', name='dense_hidden'),
            layers.Dropout(0.3, name='dropout_dense'),

            layers.Dense(n_classes, activation='softmax', name='output')
        ], name='GRUClassifier')

        return model

    @staticmethod
    def compile_model(model, n_classes):
        """Compile model for multi-class classification"""
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
            loss='sparse_categorical_crossentropy',  # For integer labels
            metrics=[
                'accuracy',
                tf.keras.metrics.TopKCategoricalAccuracy(k=3, name='top3_accuracy')
            ]
        )
        return model


class Trainer:
    """Train and evaluate multi-class models"""

    def __init__(self, X, y, pattern_names, test_size=0.2, val_size=0.2):
        self.X = X
        self.y = y
        self.pattern_names = pattern_names
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
            test_size=self.val_size / (1 - self.test_size),
            random_state=42,
            stratify=y_temp
        )

        print(f"[OK] Data split:")
        print(f"  Train: {len(self.X_train):3} samples ({len(self.X_train)/len(self.X)*100:.1f}%)")
        print(f"  Val:   {len(self.X_val):3} samples ({len(self.X_val)/len(self.X)*100:.1f}%)")
        print(f"  Test:  {len(self.X_test):3} samples ({len(self.X_test)/len(self.X)*100:.1f}%)")

    def train_model(self, model_name, model, epochs=150, batch_size=16):
        """Train a single model"""
        print(f"\n{'='*60}")
        print(f"TRAINING {model_name.upper()}")
        print(f"{'='*60}")

        model.summary()

        # Callbacks
        early_stop = callbacks.EarlyStopping(
            monitor='val_loss',
            patience=25,
            restore_best_weights=True,
            verbose=1
        )

        reduce_lr = callbacks.ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=12,
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
        y_pred = np.argmax(y_pred_prob, axis=1)

        # Calculate top-3 accuracy
        top3_acc = top_k_accuracy_score(self.y_test, y_pred_prob, k=3)

        # Calculate per-class metrics
        from sklearn.metrics import precision_recall_fscore_support
        precision, recall, f1, support = precision_recall_fscore_support(
            self.y_test, y_pred, average='weighted'
        )

        test_loss, test_acc, test_top3 = test_metrics

        # Store results
        self.results[model_name] = {
            'loss': test_loss,
            'accuracy': test_acc,
            'top3_accuracy': top3_acc,
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'y_true': self.y_test,
            'y_pred': y_pred,
            'y_pred_prob': y_pred_prob
        }

        # Print results
        print(f"\nTest Set Results:")
        print(f"  Loss:          {test_loss:.4f}")
        print(f"  Accuracy:      {test_acc:.4f}")
        print(f"  Top-3 Acc:     {top3_acc:.4f}")
        print(f"  Precision:     {precision:.4f}")
        print(f"  Recall:        {recall:.4f}")
        print(f"  F1-Score:      {f1:.4f}")

        print(f"\nClassification Report:")
        print(classification_report(
            self.y_test, y_pred,
            target_names=self.pattern_names,
            digits=3
        ))

        return self.results[model_name]

    def save_model(self, model_name):
        """Save trained model"""
        model = self.models[model_name]
        filepath = MODELS_DIR / f"{model_name.lower()}_classifier.keras"
        model.save(filepath)
        print(f"\n[OK] Model saved: {filepath}")


class Visualizer:
    """Create visualizations for multi-class classification"""

    @staticmethod
    def plot_training_history(history_dict):
        """Plot training history for all models"""
        fig, axes = plt.subplots(1, 2, figsize=(15, 5))
        fig.suptitle('Training History - Multi-Class Classification', fontsize=16, fontweight='bold')

        metrics = [
            ('loss', 'Loss'),
            ('accuracy', 'Accuracy')
        ]

        for idx, (metric, title) in enumerate(metrics):
            ax = axes[idx]

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
    def plot_confusion_matrix(results, pattern_names, model_name):
        """Plot confusion matrix with pattern names"""
        cm = confusion_matrix(results['y_true'], results['y_pred'])

        plt.figure(figsize=(14, 12))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                   xticklabels=pattern_names,
                   yticklabels=pattern_names,
                   cbar=True,
                   square=False)

        plt.title(f'{model_name} Confusion Matrix\nAccuracy: {results["accuracy"]:.3f}',
                 fontsize=14, fontweight='bold')
        plt.ylabel('True Pattern')
        plt.xlabel('Predicted Pattern')
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)

        plt.tight_layout()
        filepath = PLOTS_DIR / f'confusion_matrix_{model_name.lower()}.png'
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        print(f"[OK] Saved: {filepath}")
        plt.close()

    @staticmethod
    def plot_model_comparison(results_dict):
        """Bar chart comparing model metrics"""
        metrics = ['accuracy', 'top3_accuracy', 'precision', 'recall', 'f1_score']
        metric_labels = ['Accuracy', 'Top-3 Acc', 'Precision', 'Recall', 'F1-Score']
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
        ax.set_title('Model Performance Comparison - Multi-Class', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(metric_labels)
        ax.legend()
        ax.set_ylim([0, 1.1])
        ax.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()
        filepath = PLOTS_DIR / 'model_comparison.png'
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        print(f"[OK] Saved: {filepath}")
        plt.close()

    @staticmethod
    def plot_per_class_performance(results, pattern_names, model_name):
        """Plot per-class precision, recall, F1"""
        from sklearn.metrics import precision_recall_fscore_support

        precision, recall, f1, support = precision_recall_fscore_support(
            results['y_true'], results['y_pred'], labels=range(len(pattern_names))
        )

        fig, ax = plt.subplots(figsize=(14, 8))

        x = np.arange(len(pattern_names))
        width = 0.25

        bars1 = ax.bar(x - width, precision, width, label='Precision', alpha=0.8)
        bars2 = ax.bar(x, recall, width, label='Recall', alpha=0.8)
        bars3 = ax.bar(x + width, f1, width, label='F1-Score', alpha=0.8)

        ax.set_xlabel('Pattern Type')
        ax.set_ylabel('Score')
        ax.set_title(f'{model_name} - Per-Class Performance', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(pattern_names, rotation=45, ha='right')
        ax.legend()
        ax.set_ylim([0, 1.1])
        ax.grid(True, alpha=0.3, axis='y')

        # Add sample counts
        ax2 = ax.twinx()
        ax2.plot(x, support, 'ro-', label='Samples', linewidth=2, markersize=6)
        ax2.set_ylabel('Number of Samples', color='r')
        ax2.tick_params(axis='y', labelcolor='r')
        ax2.legend(loc='upper right')

        plt.tight_layout()
        filepath = PLOTS_DIR / f'per_class_performance_{model_name.lower()}.png'
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        print(f"[OK] Saved: {filepath}")
        plt.close()


def save_results_summary(results_dict, metadata, pattern_names):
    """Save comprehensive results summary"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = OUTPUT_DIR / f'results_summary_{timestamp}.txt'

    with open(filepath, 'w') as f:
        f.write("="*70 + "\n")
        f.write("MULTI-CLASS CHART PATTERN CLASSIFICATION - RESULTS\n")
        f.write("="*70 + "\n\n")

        f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Dataset info
        f.write("-"*70 + "\n")
        f.write("DATASET INFORMATION\n")
        f.write("-"*70 + "\n")
        if 'dataset_info' in metadata:
            info = metadata['dataset_info']
            f.write(f"Total samples:     {info['total_samples']}\n")
            f.write(f"Number of classes: {info['n_classes']}\n\n")
            f.write(f"Pattern classes:\n")
            for pattern in pattern_names:
                count = info['pattern_types'].get(pattern, 0)
                f.write(f"  {pattern:30} {count:3}\n")

        if 'data_shape' in metadata:
            shape = metadata['data_shape']
            f.write(f"\nData shape:\n")
            f.write(f"  Samples:    {shape['samples']}\n")
            f.write(f"  Timesteps:  {shape['timesteps']}\n")
            f.write(f"  Features:   {shape['features']}\n")
            f.write(f"  Classes:    {shape['n_classes']}\n\n")

        # Model results
        f.write("-"*70 + "\n")
        f.write("MODEL PERFORMANCE\n")
        f.write("-"*70 + "\n\n")

        for model_name, results in results_dict.items():
            f.write(f"{model_name}:\n")
            f.write(f"  Accuracy:      {results['accuracy']:.4f}\n")
            f.write(f"  Top-3 Acc:     {results['top3_accuracy']:.4f}\n")
            f.write(f"  Precision:     {results['precision']:.4f}\n")
            f.write(f"  Recall:        {results['recall']:.4f}\n")
            f.write(f"  F1-Score:      {results['f1_score']:.4f}\n")
            f.write(f"  Loss:          {results['loss']:.4f}\n\n")

        # Best model
        best_model = max(results_dict.items(), key=lambda x: x[1]['accuracy'])
        f.write(f"Best Model: {best_model[0]} (Accuracy: {best_model[1]['accuracy']:.4f})\n\n")

        f.write("="*70 + "\n")

    print(f"\n[OK] Results summary saved: {filepath}")


def main():
    """Main training pipeline"""
    print("\n" + "="*70)
    print(" MULTI-CLASS CHART PATTERN CLASSIFICATION")
    print(" LSTM vs GRU - Pattern Type Recognition")
    print("="*70)

    # 1. Load and preprocess data
    loader = DataLoader('training_data.json', min_samples_per_class=5)
    loader.load_data()
    X, y = loader.preprocess()

    n_classes = len(loader.pattern_to_idx)
    pattern_names = [loader.idx_to_pattern[i] for i in range(n_classes)]

    # 2. Initialize trainer
    trainer = Trainer(X, y, pattern_names)

    # 3. Get input shape
    input_shape = (X.shape[1], X.shape[2])  # (timesteps, features)

    # 4. Create and train LSTM model
    lstm_model = ModelFactory.create_lstm_classifier(input_shape, n_classes)
    lstm_model = ModelFactory.compile_model(lstm_model, n_classes)
    trainer.train_model('LSTM', lstm_model, epochs=150, batch_size=16)
    trainer.evaluate_model('LSTM')
    trainer.save_model('LSTM')

    # 5. Create and train GRU model
    gru_model = ModelFactory.create_gru_classifier(input_shape, n_classes)
    gru_model = ModelFactory.compile_model(gru_model, n_classes)
    trainer.train_model('GRU', gru_model, epochs=150, batch_size=16)
    trainer.evaluate_model('GRU')
    trainer.save_model('GRU')

    # 6. Create visualizations
    print(f"\n{'='*60}")
    print("CREATING VISUALIZATIONS")
    print(f"{'='*60}")

    Visualizer.plot_training_history(trainer.history)
    Visualizer.plot_confusion_matrix(trainer.results['LSTM'], pattern_names, 'LSTM')
    Visualizer.plot_confusion_matrix(trainer.results['GRU'], pattern_names, 'GRU')
    Visualizer.plot_per_class_performance(trainer.results['LSTM'], pattern_names, 'LSTM')
    Visualizer.plot_per_class_performance(trainer.results['GRU'], pattern_names, 'GRU')
    Visualizer.plot_model_comparison(trainer.results)

    # 7. Save results summary
    save_results_summary(trainer.results, loader.metadata, pattern_names)

    # 8. Final summary
    print(f"\n{'='*60}")
    print("TRAINING COMPLETED")
    print(f"{'='*60}")

    print(f"\nComparison:")
    for model_name in ['LSTM', 'GRU']:
        results = trainer.results[model_name]
        print(f"\n{model_name}:")
        print(f"  Accuracy:  {results['accuracy']:.4f}")
        print(f"  Top-3 Acc: {results['top3_accuracy']:.4f}")
        print(f"  F1-Score:  {results['f1_score']:.4f}")

    # Determine winner
    best_model = max(trainer.results.items(), key=lambda x: x[1]['accuracy'])
    print(f"\n🏆 Best Model: {best_model[0]} (Accuracy: {best_model[1]['accuracy']:.4f})")

    print(f"\nOutputs saved in: {OUTPUT_DIR.absolute()}")
    print(f"  Models:  {MODELS_DIR.absolute()}")
    print(f"  Plots:   {PLOTS_DIR.absolute()}")

    print("\n" + "="*70)


if __name__ == '__main__':
    main()
