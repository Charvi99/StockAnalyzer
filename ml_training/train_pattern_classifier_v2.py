"""
Chart Pattern Classifier V2 - With "No Pattern" Class
Trains models to recognize specific patterns OR classify as "No Pattern"

This version includes FALSE POSITIVES as a "No Pattern" class!
"""

import json
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime

import tensorflow as tf
from tensorflow.keras import layers, models, callbacks
from tensorflow.keras.layers import Conv1D, SpatialDropout1D, Add, Activation, Lambda, MultiHeadAttention, LayerNormalization

from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, top_k_accuracy_score

# Set random seeds
np.random.seed(42)
tf.random.set_seed(42)

# Configure output directories
OUTPUT_DIR = Path("outputs_multiclass_v2")
OUTPUT_DIR.mkdir(exist_ok=True)
MODELS_DIR = OUTPUT_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)
PLOTS_DIR = OUTPUT_DIR / "plots"
PLOTS_DIR.mkdir(exist_ok=True)


class DataLoader:
    """Load and preprocess training data with No Pattern class"""

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
        print("LOADING TRAINING DATA (MULTI-CLASS + NO PATTERN)")
        print(f"{'='*60}")

        with open(self.json_file, 'r') as f:
            self.data = json.load(f)

        print(f"[OK] Loaded {len(self.data)} samples from {self.json_file}")

        # Separate true positives and false positives
        true_positives = [s for s in self.data if s['label'] == 'true_positive']
        false_positives = [s for s in self.data if s['label'] == 'false_positive']

        print(f"[OK] True positives:  {len(true_positives)}")
        print(f"[OK] False positives: {len(false_positives)}")

        # Analyze pattern distribution
        self._analyze_dataset(true_positives, false_positives)

        return self

    def _analyze_dataset(self, true_positives, false_positives):
        """Analyze and print dataset statistics"""
        pattern_types = {}
        for sample in true_positives:
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

        # Filter true positives to only valid patterns
        true_positives = [s for s in true_positives if s['pattern_name'] in valid_patterns]

        # Balance "No Pattern" class to match average class size
        n_patterns = len(valid_patterns)
        avg_per_class = len(true_positives) / n_patterns
        target_no_pattern = int(avg_per_class * 1.5)  # 1.5x average to help model learn what's NOT a pattern

        if len(false_positives) > target_no_pattern:
            # Randomly sample to balance
            import random
            random.seed(42)
            false_positives = random.sample(false_positives, target_no_pattern)
            print(f"\n[INFO] Balanced 'No Pattern' class to {target_no_pattern} samples")

        # Combine datasets
        self.data = true_positives + false_positives

        # Create label mapping (No Pattern = class 0)
        pattern_names = sorted(valid_patterns.keys())
        self.pattern_to_idx = {"No Pattern": 0}
        for idx, name in enumerate(pattern_names, start=1):
            self.pattern_to_idx[name] = idx

        self.idx_to_pattern = {idx: name for name, idx in self.pattern_to_idx.items()}

        print(f"\nDataset Statistics:")
        print(f"  Total samples:     {len(self.data)}")
        print(f"  Pattern classes:   {len(valid_patterns)} + 1 (No Pattern)")
        print(f"  Total classes:     {len(self.pattern_to_idx)}")

        print(f"\nClass Distribution:")
        class_counts = {"No Pattern": len(false_positives)}
        class_counts.update(valid_patterns)

        for ptype, count in sorted(class_counts.items(), key=lambda x: x[1], reverse=True):
            pct = count / len(self.data) * 100
            bar = '#' * int(pct / 2)
            print(f"  {ptype:30} {count:3} ({pct:5.1f}%) {bar}")

        self.metadata['dataset_info'] = {
            'total_samples': len(self.data),
            'n_classes': len(self.pattern_to_idx),
            'pattern_types': class_counts,
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

            # Normalize
            price_range = sample['price_max'] - sample['price_min']
            if price_range > 0:
                ohlc_array[:, :4] = (ohlc_array[:, :4] - sample['price_min']) / price_range

            if sample['volume_max'] > 0:
                ohlc_array[:, 4] = ohlc_array[:, 4] / sample['volume_max']

            X.append(ohlc_array)

            # Label: 0 for No Pattern, 1+ for specific patterns
            if sample['label'] == 'false_positive':
                pattern_idx = 0  # No Pattern
            else:
                pattern_idx = self.pattern_to_idx[sample['pattern_name']]
            y.append(pattern_idx)

        # Pad sequences
        max_length = max(sequence_lengths)
        X_padded = []
        for seq in X:
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
        print(f"  Classes: {len(self.pattern_to_idx)} (including 'No Pattern')")

        self.metadata['data_shape'] = {
            'samples': self.X.shape[0],
            'timesteps': self.X.shape[1],
            'features': self.X.shape[2],
            'n_classes': len(self.pattern_to_idx)
        }

        return self.X, self.y


class ModelFactory:
    """Factory for creating multi-class models with No Pattern class"""

    @staticmethod
    def create_lstm_classifier(input_shape, n_classes):
        model = models.Sequential([
            layers.Masking(mask_value=0.0, input_shape=input_shape, name='masking'),
            layers.Bidirectional(layers.LSTM(64, return_sequences=False), name='bidirectional_lstm'),
            layers.Dropout(0.5, name='dropout_lstm'),
            layers.Dense(32, activation='relu', name='dense_hidden'),
            layers.Dropout(0.3, name='dropout_dense'),
            layers.Dense(n_classes, activation='softmax', name='output')
        ], name='LSTMClassifierV2')
        return model

    @staticmethod
    def create_gru_classifier(input_shape, n_classes):
        model = models.Sequential([
            layers.Masking(mask_value=0.0, input_shape=input_shape, name='masking'),
            layers.Bidirectional(layers.GRU(48, return_sequences=False), name='bidirectional_gru'),
            layers.Dropout(0.5, name='dropout_gru'),
            layers.Dense(24, activation='relu', name='dense_hidden'),
            layers.Dropout(0.3, name='dropout_dense'),
            layers.Dense(n_classes, activation='softmax', name='output')
        ], name='GRUClassifierV2')
        return model

    @staticmethod
    def create_cnn_lstm_classifier(input_shape, n_classes):
        model = models.Sequential([
            layers.Masking(mask_value=0.0, input_shape=input_shape, name='masking'),
            layers.Conv1D(64, kernel_size=3, activation='relu', padding='same', name='conv1'),
            layers.Conv1D(64, kernel_size=3, activation='relu', padding='same', name='conv2'),
            layers.MaxPooling1D(pool_size=2, name='pool'),
            layers.Bidirectional(layers.LSTM(64), name='bilstm'),
            layers.Dropout(0.5, name='dropout_lstm'),
            layers.Dense(64, activation='relu', name='dense1'),
            layers.Dropout(0.3, name='dropout_dense'),
            layers.Dense(n_classes, activation='softmax', name='output')
        ], name='CNN_LSTM_Classifier')
        return model
    
    

    @staticmethod
    def create_tcn_classifier(input_shape, n_classes):
        from tensorflow.keras import layers
        def residual_block(x, filters, kernel_size, dilation_rate):
            conv1 = layers.Conv1D(filters, kernel_size, padding='causal',dilation_rate=dilation_rate, activation='relu')(x)
            conv1 = layers.SpatialDropout1D(0.2)(conv1)
            conv2 = layers.Conv1D(filters, kernel_size, padding='causal',dilation_rate=dilation_rate)(conv1)

            # 🔧 Match input (residual) channels if necessary
            if x.shape[-1] != filters:
                x = layers.Conv1D(filters, 1, padding='same')(x)

            res = layers.Add()([x, conv2])
            return layers.Activation('relu')(res)
    
        inputs = layers.Input(shape=input_shape)
        x = residual_block(inputs, 64, 3, 1)
        x = residual_block(x, 64, 3, 2)
        x = residual_block(x, 64, 3, 4)
        x = layers.GlobalAveragePooling1D()(x)
        x = layers.Dense(64, activation='relu')(x)
        x = layers.Dropout(0.3)(x)
        outputs = layers.Dense(n_classes, activation='softmax')(x)
        model = models.Model(inputs, outputs, name='TCNClassifier')
        return model
    
    
    # --- Improved TCN classifier ---
    @staticmethod
    def create_improved_tcn(input_shape, n_classes):
        def residual_block(x, filters, kernel_size, dilation_rate, dropout_rate=0.2):
            conv1 = layers.Conv1D(filters, kernel_size, padding='causal',
                                dilation_rate=dilation_rate, activation='relu')(x)
            conv1 = layers.BatchNormalization()(conv1)
            conv1 = layers.SpatialDropout1D(dropout_rate)(conv1)

            conv2 = layers.Conv1D(filters, kernel_size, padding='causal',
                                dilation_rate=dilation_rate)(conv1)
            conv2 = layers.BatchNormalization()(conv2)

            # Project input if number of channels differs
            if x.shape[-1] != filters:
                x = layers.Conv1D(filters, 1, padding='same')(x)

            res = layers.Add()([x, conv2])
            return layers.Activation('relu')(res)

        inputs = layers.Input(shape=input_shape)

        # Optional: price / volume split
        price = layers.Lambda(lambda x: x[..., :4])(inputs)
        vol = layers.Lambda(lambda x: x[..., 4:5])(inputs)

        # Price branch
        x_price = residual_block(price, 32, 3, 1, dropout_rate=0.2)
        x_price = residual_block(x_price, 32, 3, 2, dropout_rate=0.2)

        # Volume branch
        x_vol = residual_block(vol, 16, 3, 1, dropout_rate=0.2)
        x_vol = residual_block(x_vol, 16, 3, 2, dropout_rate=0.2)

        # Merge branches
        x = layers.Concatenate()([x_price, x_vol])

        # One more TCN block
        x = residual_block(x, 64, 3, 4, dropout_rate=0.3)

        # Temporal attention (using MultiHeadAttention for self-attention)
        attn = layers.MultiHeadAttention(num_heads=4, key_dim=16)(x, x)
        x = layers.Add()([x, attn])

        # Global pooling
        x = layers.GlobalAveragePooling1D()(x)

        # Dense layers with dropout
        x = layers.Dense(64, activation='relu')(x)
        x = layers.Dropout(0.4)(x)

        outputs = layers.Dense(n_classes, activation='softmax')(x)

        model = models.Model(inputs, outputs, name='ImprovedTCNClassifier')
        return model
    
    @staticmethod
    def create_transformer_classifier(input_shape, n_classes, num_heads=4, ff_dim=128):
        inputs = layers.Input(shape=input_shape)
        x = layers.LayerNormalization(epsilon=1e-6)(inputs)
        attn_output = layers.MultiHeadAttention(num_heads=num_heads, key_dim=input_shape[-1])(x, x)
        x = layers.Add()([x, attn_output])
        x = layers.LayerNormalization(epsilon=1e-6)(x)
        x = layers.Dense(ff_dim, activation='relu')(x)
        x = layers.Dense(input_shape[-1])(x)
        x = layers.Add()([x, inputs])
        x = layers.GlobalAveragePooling1D()(x)
        x = layers.Dropout(0.4)(x)
        x = layers.Dense(64, activation='relu')(x)
        x = layers.Dropout(0.3)(x)
        outputs = layers.Dense(n_classes, activation='softmax')(x)
        model = models.Model(inputs, outputs, name='TransformerClassifier')
        return model
    
    @staticmethod
    def create_inceptiontime_classifier(input_shape, n_classes):
        input_layer = layers.Input(shape=input_shape)
        
        def inception_module(x, filters=32):
            conv1 = layers.Conv1D(filters, 1, padding='same', activation='relu')(x)
            conv3 = layers.Conv1D(filters, 3, padding='same', activation='relu')(x)
            conv5 = layers.Conv1D(filters, 5, padding='same', activation='relu')(x)
            pool = layers.MaxPooling1D(3, strides=1, padding='same')(x)
            pool_conv = layers.Conv1D(filters, 1, padding='same', activation='relu')(pool)
            return layers.Concatenate(axis=-1)([conv1, conv3, conv5, pool_conv])
        
        x = inception_module(input_layer)
        x = inception_module(x)
        x = layers.GlobalAveragePooling1D()(x)
        x = layers.Dense(64, activation='relu')(x)
        x = layers.Dropout(0.4)(x)
        output_layer = layers.Dense(n_classes, activation='softmax')(x)
        
        model = models.Model(input_layer, output_layer, name='InceptionTimeClassifier')
        return model
    
    @staticmethod
    def compile_model(model):
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy', tf.keras.metrics.SparseTopKCategoricalAccuracy(k=3, name='top3_accuracy')]
        )
        return model


def main():
    """Main training pipeline"""
    print("\n" + "="*70)
    print(" MULTI-CLASS CHART PATTERN CLASSIFICATION V2")
    print(" With 'No Pattern' Class + Confidence Scores")
    print("="*70)

    # 1. Load and preprocess data
    loader = DataLoader('training_data.json', min_samples_per_class=5)
    loader.load_data()
    X, y = loader.preprocess()

    n_classes = len(loader.pattern_to_idx)
    pattern_names = [loader.idx_to_pattern[i] for i in range(n_classes)]

    # 2. Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    X_train, X_val, y_train, y_val = train_test_split(
        X_train, y_train, test_size=0.2, random_state=42, stratify=y_train
    )

    print(f"\n{'='*60}")
    print("DATA SPLIT")
    print(f"{'='*60}")
    print(f"Train: {len(X_train)} samples")
    print(f"Val:   {len(X_val)} samples")
    print(f"Test:  {len(X_test)} samples")

    # 3. Compute class weights for imbalance handling
    from sklearn.utils.class_weight import compute_class_weight

    class_weights = compute_class_weight(
        'balanced',
        classes=np.unique(y_train),
        y=y_train
    )
    class_weight_dict = dict(enumerate(class_weights))

    print(f"\n{'='*60}")
    print("CLASS WEIGHTS (for handling imbalance)")
    print(f"{'='*60}")
    for idx, weight in class_weight_dict.items():
        pattern = pattern_names[idx]
        print(f"  {pattern:30} {weight:.3f}")

    # 4. Create and train model
    input_shape = (X.shape[1], X.shape[2])
    # model = ModelFactory.create_lstm_classifier(input_shape, n_classes)
    # model = ModelFactory.create_gru_classifier(input_shape, n_classes)
    # model = ModelFactory.create_cnn_lstm_classifier(input_shape, n_classes)
    # model = ModelFactory.create_tcn_classifier(input_shape, n_classes)
    # model = ModelFactory.create_transformer_classifier(input_shape, n_classes)
    # model = ModelFactory.create_inceptiontime_classifier(input_shape, n_classes)
    model = ModelFactory.create_improved_tcn(input_shape, n_classes)
    model = ModelFactory.compile_model(model)

    print(f"\n{'='*60}")
    print(f"TRAINING {model.name.upper()}")
    print(f"{'='*60}")
    model.summary()

    early_stop = callbacks.EarlyStopping(monitor='val_loss', patience=25, restore_best_weights=True, verbose=1)
    reduce_lr = callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=12, verbose=1)

    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=150,
        batch_size=16,
        class_weight=class_weight_dict,
        callbacks=[early_stop, reduce_lr],
        verbose=2
    )

    # 4. Evaluate
    print(f"\n{'='*60}")
    print("EVALUATION")
    print(f"{'='*60}")

    y_pred_prob = model.predict(X_test, verbose=0)
    y_pred = np.argmax(y_pred_prob, axis=1)

    test_acc = np.mean(y_pred == y_test)
    print(f"\nTest Accuracy: {test_acc:.1%}")

    # Top-3 accuracy
    top3_correct = sum(y_test[i] in np.argsort(y_pred_prob[i])[-3:] for i in range(len(y_test)))
    top3_acc = top3_correct / len(y_test)
    print(f"Top-3 Accuracy: {top3_acc:.1%}")

    print(f"\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=pattern_names, digits=3))

    # Confusion Matrix Analysis
    print(f"\n{'='*60}")
    print("CONFUSION MATRIX ANALYSIS")
    print(f"{'='*60}")

    cm = confusion_matrix(y_test, y_pred)

    # Detailed "No Pattern" performance
    no_pattern_idx = 0
    no_pattern_tp = cm[no_pattern_idx, no_pattern_idx]
    no_pattern_fn = cm[no_pattern_idx, :].sum() - no_pattern_tp
    no_pattern_fp = cm[:, no_pattern_idx].sum() - no_pattern_tp
    no_pattern_tn = cm.sum() - (no_pattern_tp + no_pattern_fn + no_pattern_fp)

    no_pattern_precision = no_pattern_tp / (no_pattern_tp + no_pattern_fp) if (no_pattern_tp + no_pattern_fp) > 0 else 0
    no_pattern_recall = no_pattern_tp / (no_pattern_tp + no_pattern_fn) if (no_pattern_tp + no_pattern_fn) > 0 else 0
    no_pattern_f1 = 2 * (no_pattern_precision * no_pattern_recall) / (no_pattern_precision + no_pattern_recall) if (no_pattern_precision + no_pattern_recall) > 0 else 0

    print(f"\n'No Pattern' Detailed Performance:")
    print(f"  True Positives:  {no_pattern_tp:3} (correctly identified non-patterns)")
    print(f"  False Negatives: {no_pattern_fn:3} (missed non-patterns, predicted as pattern)")
    print(f"  False Positives: {no_pattern_fp:3} (predicted no pattern, but was a pattern)")
    print(f"  True Negatives:  {no_pattern_tn:3} (correctly identified patterns)")
    print(f"\n  Precision: {no_pattern_precision:.1%} (When predicting 'No Pattern', how often correct?)")
    print(f"  Recall:    {no_pattern_recall:.1%} (Of all non-patterns, how many did we catch?)")
    print(f"  F1-Score:  {no_pattern_f1:.3f}")

    # 5. Save training history and plots
    print(f"\n{'='*60}")
    print("SAVING TRAINING ARTIFACTS")
    print(f"{'='*60}")

    # Save history to JSON
    history_path = OUTPUT_DIR / f"{model.name}_history.json"
    history_dict = {k: [float(v) for v in vals] for k, vals in history.history.items()}
    with open(history_path, 'w') as f:
        json.dump(history_dict, f, indent=2)
    print(f"[OK] Training history saved: {history_path}")

    # Plot training curves
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Accuracy plot
    axes[0].plot(history.history['accuracy'], label='Train', linewidth=2)
    axes[0].plot(history.history['val_accuracy'], label='Val', linewidth=2)
    axes[0].set_title(f'{model.name} - Accuracy', fontsize=14, fontweight='bold')
    axes[0].set_xlabel('Epoch')
    axes[0].set_ylabel('Accuracy')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # Loss plot
    axes[1].plot(history.history['loss'], label='Train', linewidth=2)
    axes[1].plot(history.history['val_loss'], label='Val', linewidth=2)
    axes[1].set_title(f'{model.name} - Loss', fontsize=14, fontweight='bold')
    axes[1].set_xlabel('Epoch')
    axes[1].set_ylabel('Loss')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    # Top-3 Accuracy plot
    if 'top3_accuracy' in history.history:
        axes[2].plot(history.history['top3_accuracy'], label='Train Top-3', linewidth=2)
        axes[2].plot(history.history['val_top3_accuracy'], label='Val Top-3', linewidth=2)
        axes[2].set_title(f'{model.name} - Top-3 Accuracy', fontsize=14, fontweight='bold')
        axes[2].set_xlabel('Epoch')
        axes[2].set_ylabel('Top-3 Accuracy')
        axes[2].legend()
        axes[2].grid(True, alpha=0.3)
    else:
        axes[2].axis('off')

    plt.tight_layout()
    training_plot_path = PLOTS_DIR / f"{model.name}_training.png"
    plt.savefig(training_plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"[OK] Training curves saved: {training_plot_path}")

    # Plot confusion matrix
    fig, ax = plt.subplots(figsize=(16, 14))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', cbar=True,
                xticklabels=pattern_names, yticklabels=pattern_names,
                ax=ax, annot_kws={'size': 8})
    ax.set_title(f'{model.name} - Confusion Matrix\n(Test Accuracy: {test_acc:.1%}, Top-3: {top3_acc:.1%})',
                 fontsize=14, fontweight='bold', pad=20)
    ax.set_ylabel('True Label', fontsize=12)
    ax.set_xlabel('Predicted Label', fontsize=12)
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.tight_layout()
    cm_plot_path = PLOTS_DIR / f"{model.name}_confusion_matrix.png"
    plt.savefig(cm_plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"[OK] Confusion matrix saved: {cm_plot_path}")

    # 6. Save model
    model_path = MODELS_DIR / f"{model.name}.keras"
    model.save(model_path)
    print(f"[OK] Model saved: {model_path}")

    # 7. Demo prediction with confidence
    print(f"\n{'='*60}")
    print("DEMO: Prediction with Confidence Levels")
    print(f"{'='*60}")

    sample_idx = 0
    sample = X_test[sample_idx:sample_idx+1]
    true_label = pattern_names[y_test[sample_idx]]

    predictions = model.predict(sample, verbose=0)[0]
    top3_idx = np.argsort(predictions)[-3:][::-1]

    print(f"\nTrue Pattern: {true_label}")
    print(f"\nTop 3 Predictions:")
    for rank, idx in enumerate(top3_idx, 1):
        pattern = pattern_names[idx]
        confidence = predictions[idx] * 100
        print(f"  {rank}. {pattern:30} {confidence:5.1f}% confidence")

    # Confidence thresholds
    top_conf = predictions[top3_idx[0]] * 100
    if pattern_names[top3_idx[0]] == "No Pattern":
        print(f"\n=> Model says: No clear pattern detected (confidence: {top_conf:.1f}%)")
    elif top_conf > 70:
        print(f"\n=> HIGH CONFIDENCE: {pattern_names[top3_idx[0]]} ({top_conf:.1f}%)")
    elif top_conf > 50:
        print(f"\n=> MODERATE CONFIDENCE: {pattern_names[top3_idx[0]]} ({top_conf:.1f}%)")
    else:
        print(f"\n=> LOW CONFIDENCE: Uncertain, top pick is {pattern_names[top3_idx[0]]} ({top_conf:.1f}%)")

    # 8. Save comprehensive results summary
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    summary_path = OUTPUT_DIR / f"results_summary_{timestamp}.txt"

    with open(summary_path, 'w') as f:
        f.write(f"{'='*70}\n")
        f.write(f"TRAINING RESULTS SUMMARY - {model.name}\n")
        f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*70}\n\n")

        f.write(f"Dataset Information:\n")
        f.write(f"  Total samples: {len(loader.data)}\n")
        f.write(f"  Number of classes: {n_classes} (including 'No Pattern')\n")
        f.write(f"  Train/Val/Test split: {len(X_train)}/{len(X_val)}/{len(X_test)}\n\n")

        f.write(f"Model Architecture: {model.name}\n")
        f.write(f"  Total parameters: {model.count_params():,}\n")
        f.write(f"  Input shape: {input_shape}\n")
        f.write(f"  Epochs trained: {len(history.history['loss'])}\n\n")

        f.write(f"Performance Metrics:\n")
        f.write(f"  Test Accuracy: {test_acc:.1%}\n")
        f.write(f"  Top-3 Accuracy: {top3_acc:.1%}\n\n")

        f.write(f"'No Pattern' Class Performance:\n")
        f.write(f"  Precision: {no_pattern_precision:.1%}\n")
        f.write(f"  Recall: {no_pattern_recall:.1%}\n")
        f.write(f"  F1-Score: {no_pattern_f1:.3f}\n\n")

        f.write(f"Output Files:\n")
        f.write(f"  Model: {model_path}\n")
        f.write(f"  Training history: {history_path}\n")
        f.write(f"  Training plot: {training_plot_path}\n")
        f.write(f"  Confusion matrix: {cm_plot_path}\n")

    print(f"\n[OK] Results summary saved: {summary_path}")

    print("\n" + "="*70)
    print(f"TRAINING COMPLETE! - {model.name}")
    print("="*70)
    print(f"\nModel Capabilities:")
    print(f"  * Recognize {n_classes - 1} specific pattern types")
    print(f"  * Classify 'No Pattern' when appropriate (reduces false positives!)")
    print(f"  * Provide confidence scores for each prediction")
    print(f"\nPerformance:")
    print(f"  * Test Accuracy: {test_acc:.1%}")
    print(f"  * Top-3 Accuracy: {top3_acc:.1%} (model's top 3 guesses)")
    print(f"  * 'No Pattern' Precision: {no_pattern_precision:.1%}")
    print(f"  * 'No Pattern' Recall: {no_pattern_recall:.1%}")
    print(f"\nOutputs saved to: {OUTPUT_DIR}/")
    print("="*70)


if __name__ == '__main__':
    main()
