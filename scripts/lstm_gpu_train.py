#!/usr/bin/env python3
"""
LSTM GPU Training Script

Trains LSTM neural network on GPU (GCP or Azure) for time series prediction.

LSTM advantages over LGBM:
- Learns temporal patterns automatically (no need for SMA, LINEARREG_SLOPE)
- Captures long-range dependencies
- Better for sequential data (price movements)

Expected cost: $10-30 depending on GPU and training time
Expected time: 2-8 hours
Expected improvement: +1-3% win rate vs LGBM

Prerequisites:
    pip install tensorflow pandas numpy scikit-learn

GPU Options:
    - GCP: NVIDIA T4 ($0.35/h), V100 ($2.48/h)
    - Azure: NC6 ($0.90/h), NC6s_v3 ($3.06/h)
    - Local: If you have NVIDIA GPU with CUDA

Usage:
    # Train LSTM on order flow data
    python scripts/lstm_gpu_train.py --config configs/btcusdt_5m_orderflow.jsonc --epochs 100

    # Quick test (10 epochs)
    python scripts/lstm_gpu_train.py --config configs/btcusdt_5m_orderflow.jsonc --epochs 10 --test
"""

import argparse
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    from sklearn.preprocessing import StandardScaler
    HAS_TF = True
except ImportError:
    HAS_TF = False
    print("⚠️  TensorFlow not installed")
    print("Run: pip install tensorflow")

# Import ITB utilities
sys.path.insert(0, str(Path(__file__).parent.parent))
from service.App import load_config, App


def check_gpu():
    """Check if GPU is available"""
    print("\n🔍 Checking GPU availability...")

    gpus = tf.config.list_physical_devices('GPU')

    if not gpus:
        print("⚠️  No GPU detected - training will be SLOW on CPU")
        print("\nTo use GPU:")
        print("  - GCP: Create VM with GPU (e.g., n1-standard-4 + 1x NVIDIA T4)")
        print("  - Azure: Create VM with GPU (e.g., NC6)")
        print("  - Local: Install CUDA + cuDNN")
        return False

    print(f"✅ Found {len(gpus)} GPU(s):")
    for gpu in gpus:
        print(f"   {gpu.name}")

    # Enable memory growth to avoid OOM
    for gpu in gpus:
        tf.config.experimental.set_memory_growth(gpu, True)

    return True


def load_data(config_file):
    """Load and prepare data for LSTM"""
    print(f"\n📊 Loading data from: {config_file}")

    load_config(config_file)

    data_folder = Path(App.config.get('data_folder', './DATA_ITB_5m'))

    # Load merged data
    merged_file = data_folder / 'merged_data.csv'
    if not merged_file.exists():
        raise FileNotFoundError(
            f"No merged data found at {merged_file}\n"
            f"Run: python scripts/merge_new.py -c {config_file}"
        )

    df = pd.read_csv(merged_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    print(f"   Loaded {len(df):,} rows")
    print(f"   Columns: {len(df.columns)}")

    return df


def prepare_lstm_data(df, feature_cols, label_col, lookback=60, train_split=0.8):
    """
    Prepare data for LSTM training

    Args:
        df: DataFrame with features and labels
        feature_cols: List of feature column names
        label_col: Target column name
        lookback: Number of timesteps to look back (e.g., 60 = last 60 bars)
        train_split: Train/test split ratio

    Returns:
        (X_train, y_train, X_test, y_test, scaler)
    """
    print(f"\n🔧 Preparing LSTM data...")
    print(f"   Features: {len(feature_cols)}")
    print(f"   Lookback: {lookback} timesteps")

    # Select features and target
    features = df[feature_cols].values
    target = df[label_col].values

    # Remove NaN rows
    mask = ~(np.isnan(features).any(axis=1) | np.isnan(target))
    features = features[mask]
    target = target[mask]

    print(f"   Valid samples: {len(features):,}")

    # Normalize features
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)

    # Create sequences
    X, y = [], []

    for i in range(lookback, len(features_scaled)):
        X.append(features_scaled[i-lookback:i])  # Last 'lookback' timesteps
        y.append(target[i])  # Predict next timestep

    X = np.array(X)
    y = np.array(y)

    print(f"   Sequences created: {len(X):,}")
    print(f"   Shape: {X.shape} → {y.shape}")

    # Train/test split
    split_idx = int(len(X) * train_split)

    X_train = X[:split_idx]
    y_train = y[:split_idx]
    X_test = X[split_idx:]
    y_test = y[split_idx:]

    print(f"   Train: {len(X_train):,} samples")
    print(f"   Test: {len(X_test):,} samples")

    return X_train, y_train, X_test, y_test, scaler


def build_lstm_model(input_shape, task='classification'):
    """
    Build LSTM model

    Architecture:
        LSTM(128) → Dropout(0.2) →
        LSTM(64) → Dropout(0.2) →
        LSTM(32) → Dropout(0.2) →
        Dense(16) → Output

    Args:
        input_shape: (timesteps, features)
        task: 'classification' or 'regression'
    """
    print(f"\n🏗️  Building LSTM model...")
    print(f"   Input shape: {input_shape}")
    print(f"   Task: {task}")

    model = keras.Sequential([
        # First LSTM layer
        layers.LSTM(128, return_sequences=True, input_shape=input_shape),
        layers.Dropout(0.2),

        # Second LSTM layer
        layers.LSTM(64, return_sequences=True),
        layers.Dropout(0.2),

        # Third LSTM layer
        layers.LSTM(32),
        layers.Dropout(0.2),

        # Dense layers
        layers.Dense(16, activation='relu'),
        layers.Dropout(0.2),

        # Output layer
        layers.Dense(1, activation='sigmoid' if task == 'classification' else 'linear')
    ])

    # Compile
    if task == 'classification':
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='binary_crossentropy',
            metrics=['accuracy', 'AUC']
        )
    else:
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='mse',
            metrics=['mae']
        )

    print(f"\n📋 Model Summary:")
    model.summary()

    total_params = model.count_params()
    print(f"\n   Total parameters: {total_params:,}")

    return model


def train_model(model, X_train, y_train, X_test, y_test, epochs=100, batch_size=64):
    """Train LSTM model with callbacks"""
    print(f"\n🚀 Training model...")
    print(f"   Epochs: {epochs}")
    print(f"   Batch size: {batch_size}")

    # Callbacks
    callbacks = [
        # Early stopping (stop if no improvement for 10 epochs)
        keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=10,
            restore_best_weights=True
        ),

        # Reduce learning rate on plateau
        keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=5,
            min_lr=1e-7
        ),

        # Model checkpoint
        keras.callbacks.ModelCheckpoint(
            'lstm_best_model.h5',
            monitor='val_loss',
            save_best_only=True
        )
    ]

    # Train
    history = model.fit(
        X_train, y_train,
        validation_data=(X_test, y_test),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=callbacks,
        verbose=1
    )

    return history


def evaluate_model(model, X_test, y_test, task='classification'):
    """Evaluate model performance"""
    print(f"\n📊 Evaluating model...")

    # Predictions
    y_pred = model.predict(X_test)

    if task == 'classification':
        y_pred_binary = (y_pred > 0.5).astype(int).flatten()
        y_test_binary = y_test.astype(int)

        # Metrics
        accuracy = np.mean(y_pred_binary == y_test_binary)
        tp = np.sum((y_pred_binary == 1) & (y_test_binary == 1))
        fp = np.sum((y_pred_binary == 1) & (y_test_binary == 0))
        tn = np.sum((y_pred_binary == 0) & (y_test_binary == 0))
        fn = np.sum((y_pred_binary == 0) & (y_test_binary == 1))

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        print(f"\n   Accuracy: {accuracy:.4f} ({accuracy * 100:.2f}%)")
        print(f"   Precision: {precision:.4f}")
        print(f"   Recall: {recall:.4f}")
        print(f"   F1 Score: {f1:.4f}")
        print(f"\n   Confusion Matrix:")
        print(f"      TP: {tp:,}  FP: {fp:,}")
        print(f"      FN: {fn:,}  TN: {tn:,}")

        return accuracy

    else:  # regression
        mse = np.mean((y_pred.flatten() - y_test) ** 2)
        mae = np.mean(np.abs(y_pred.flatten() - y_test))
        rmse = np.sqrt(mse)

        print(f"\n   MSE: {mse:.6f}")
        print(f"   MAE: {mae:.6f}")
        print(f"   RMSE: {rmse:.6f}")

        return rmse


def estimate_training_cost(epochs, samples, gpu_type='T4'):
    """Estimate training cost"""
    # Estimate time: ~0.1-0.5 seconds per epoch per 1000 samples
    time_per_epoch = (samples / 1000) * 0.3  # seconds
    total_time_hours = (epochs * time_per_epoch) / 3600

    # GPU costs per hour
    gpu_costs = {
        'T4': 0.35,       # GCP
        'V100': 2.48,     # GCP
        'K80': 0.45,      # GCP (cheap but old)
        'NC6': 0.90,      # Azure
        'NC6s_v3': 3.06   # Azure (powerful)
    }

    cost_per_hour = gpu_costs.get(gpu_type, 0.35)
    total_cost = total_time_hours * cost_per_hour

    print(f"\n💰 Estimated Training Cost:")
    print(f"   GPU: {gpu_type} (${cost_per_hour}/hour)")
    print(f"   Training time: {total_time_hours:.2f} hours")
    print(f"   Total cost: ${total_cost:.2f}")

    return total_cost


def main():
    parser = argparse.ArgumentParser(
        description='Train LSTM model on GPU',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--config', '-c', required=True, help='ITB config file')
    parser.add_argument('--epochs', type=int, default=100, help='Training epochs (default: 100)')
    parser.add_argument('--batch-size', type=int, default=64, help='Batch size (default: 64)')
    parser.add_argument('--lookback', type=int, default=60, help='Lookback timesteps (default: 60)')
    parser.add_argument('--target', default='high_040_4', help='Target column')
    parser.add_argument('--task', choices=['classification', 'regression'], default='classification')
    parser.add_argument('--gpu', default='T4', choices=['T4', 'V100', 'K80', 'NC6', 'NC6s_v3'])
    parser.add_argument('--test', action='store_true', help='Quick test (10 epochs)')

    args = parser.parse_args()

    if not HAS_TF:
        sys.exit(1)

    # Check GPU
    has_gpu = check_gpu()
    if not has_gpu:
        print("\n⚠️  Training on CPU will be very slow!")
        response = input("Continue anyway? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            return

    # Load data
    df = load_data(args.config)

    # Get feature columns (all except timestamp and labels)
    exclude_cols = ['timestamp', 'symbol'] + [col for col in df.columns if 'high_' in col or 'low_' in col]
    feature_cols = [col for col in df.columns if col not in exclude_cols]

    print(f"\n   Using {len(feature_cols)} features:")
    for col in feature_cols[:10]:
        print(f"      - {col}")
    if len(feature_cols) > 10:
        print(f"      ... and {len(feature_cols) - 10} more")

    # Prepare data
    X_train, y_train, X_test, y_test, scaler = prepare_lstm_data(
        df, feature_cols, args.target, args.lookback
    )

    # Estimate cost
    epochs = 10 if args.test else args.epochs
    estimate_training_cost(epochs, len(X_train), args.gpu)

    if not args.test:
        response = input("\nContinue with training? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            return

    # Build model
    model = build_lstm_model(
        input_shape=(args.lookback, len(feature_cols)),
        task=args.task
    )

    # Train
    history = train_model(model, X_train, y_train, X_test, y_test, epochs, args.batch_size)

    # Evaluate
    metric = evaluate_model(model, X_test, y_test, args.task)

    # Save model
    model_path = f"lstm_model_{datetime.now().strftime('%Y%m%d_%H%M')}.h5"
    model.save(model_path)
    print(f"\n💾 Model saved: {model_path}")

    print(f"\n✅ Training complete!")
    print(f"\nNext steps:")
    print(f"1. Compare with LGBM baseline")
    print(f"2. If better → Use for predictions")
    print(f"3. If worse → Try different architecture or more epochs")


if __name__ == '__main__':
    main()
