"""
Aggressive Label Generator for 1-minute Scalping Strategy

Generates realistic short-term labels optimized for high-frequency trading:
- Shorter horizons (10-20 candles = 10-20 minutes for 1m timeframe)
- Smaller thresholds (0.15%-0.30% instead of 0.5%+)
- Tighter tolerances to avoid false positives
- Validation to ensure targets are achievable

Design Philosophy:
- Labels should reflect realistic scalping targets
- Tolerance prevents labeling noise as signal
- Multiple thresholds allow model to learn gradual confidence
"""

import numpy as np
import pandas as pd
from typing import List, Dict

from common.gen_labels_highlow import first_cross_labels


def generate_labels_aggressive(df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, List[str]]:
    """
    Generate aggressive short-term labels for scalping strategies.

    Args:
        df: DataFrame with OHLCV data
        config: Configuration dict with:
            - columns: [close, high, low]
            - function: 'high' or 'low'
            - thresholds: List of % targets (e.g., [0.15, 0.20, 0.25, 0.30])
            - tolerance: Max acceptable opposite move (e.g., 0.05 = 0.05%)
            - horizon: Candles to look forward (e.g., 10-20 for 1m)
            - names: Output column names

    Returns:
        (df, label_names): Modified DataFrame and list of created label columns

    Example config:
        {
            "columns": ["close", "high", "low"],
            "function": "high",
            "thresholds": [0.15, 0.20, 0.25, 0.30],
            "tolerance": 0.05,
            "horizon": 10,
            "names": ["high_015_10", "high_020_10", "high_025_10", "high_030_10"]
        }
    """

    column_names = config.get('columns')
    if not column_names or len(column_names) != 3:
        raise ValueError("Aggressive labels require exactly 3 columns: [close, high, low]")

    close_column = column_names[0]
    high_column = column_names[1]
    low_column = column_names[2]

    function = config.get('function')
    if function not in ['high', 'low']:
        raise ValueError(f"Function must be 'high' or 'low', got: {function}")

    tolerance = config.get('tolerance', 0.05)  # Default 0.05% tolerance

    thresholds = config.get('thresholds')
    if not isinstance(thresholds, list):
        thresholds = [thresholds]

    # Normalize thresholds based on function
    if function == 'high':
        thresholds = [abs(t) for t in thresholds]
        price_columns = [high_column, low_column]
    else:  # function == 'low'
        thresholds = [-abs(t) for t in thresholds]
        price_columns = [low_column, high_column]

    # Calculate tolerances (opposite sign of threshold)
    tolerances = [round(-t * tolerance, 6) for t in thresholds]

    horizon = config.get('horizon')
    if not horizon:
        raise ValueError("Horizon (number of candles) is required")

    names = config.get('names')
    if not names or len(names) != len(thresholds):
        raise ValueError(f"Must provide one name per threshold. Got {len(names)} names for {len(thresholds)} thresholds")

    # Generate labels using the proven first_cross_labels logic
    labels = []
    for i, threshold in enumerate(thresholds):
        label_name = names[i]
        first_cross_labels(df, horizon, [threshold, tolerances[i]], close_column, price_columns, label_name)
        labels.append(label_name)

    print(f"✅ Aggressive labels generated: {labels}")
    print(f"   Horizon: {horizon} candles, Function: {function}, Tolerance: {tolerance}%")

    # Validation: Check label distribution
    _validate_label_distribution(df, labels, thresholds, function)

    return df, labels


def _validate_label_distribution(df: pd.DataFrame, label_names: List[str], thresholds: List[float], function: str):
    """
    Validate that generated labels have reasonable distribution.
    Warns if labels are too rare (impossible targets) or too common (noise).
    """

    print("\n📊 Label Distribution Validation:")
    print(f"{'Label':<20} {'True %':<10} {'Status':<15} {'Recommendation'}")
    print("-" * 80)

    for i, label_name in enumerate(label_names):
        if label_name not in df.columns:
            continue

        # Calculate % of True labels
        true_pct = df[label_name].sum() / len(df) * 100
        threshold = abs(thresholds[i])

        # Classification thresholds
        if true_pct < 5:
            status = "⚠️  TOO RARE"
            recommendation = "Target too ambitious - consider lowering threshold"
        elif true_pct > 40:
            status = "⚠️  TOO COMMON"
            recommendation = "Target too easy - may be noise"
        elif true_pct < 10:
            status = "⚡ CHALLENGING"
            recommendation = "Good for precision, but needs strong model"
        elif true_pct > 25:
            status = "✅ ACHIEVABLE"
            recommendation = "Balanced - good for aggressive scalping"
        else:
            status = "🎯 OPTIMAL"
            recommendation = "Ideal distribution for ML training"

        print(f"{label_name:<20} {true_pct:>6.2f}%    {status:<15} {recommendation}")

    print("-" * 80)


def add_regime_features(df: pd.DataFrame, gen_config: dict, config: dict, model_store) -> tuple[pd.DataFrame, list[str]]:
    """
    Add market regime features to help model adapt strategy.

    ITB Generator compatible function.

    Regimes:
        - vol_regime: 0 (low vol), 1 (medium vol), 2 (high vol)
        - Based on ATR percentile ranking

    Args:
        df: DataFrame with OHLCV data
        gen_config: Generator config dict (expects 'atr_column' key)
        config: Global config dict
        model_store: Model store instance

    Returns:
        (df, feature_names): Modified DataFrame and list of created features

    Config example:
        {
            "generator": "common.gen_labels_aggressive:add_regime_features",
            "config": {
                "atr_column": "high_low_close_ATR_14"
            }
        }
    """

    # Get ATR column from config, default to standard name
    atr_column = gen_config.get('atr_column', 'high_low_close_ATR_14')

    if atr_column not in df.columns:
        print(f"⚠️  Warning: ATR column '{atr_column}' not found. Skipping regime detection.")
        return df, []

    # Calculate ATR as % of price
    if 'close' in df.columns:
        atr_pct = (df[atr_column] / df['close']) * 100
    else:
        atr_pct = df[atr_column]  # Assume already in percentage

    # Define regime boundaries using percentiles
    p35 = atr_pct.quantile(0.35)
    p70 = atr_pct.quantile(0.70)

    def classify_regime(atr_val):
        if pd.isna(atr_val):
            return 1  # Default to medium
        elif atr_val < p35:
            return 0  # Low volatility
        elif atr_val < p70:
            return 1  # Medium volatility
        else:
            return 2  # High volatility

    df['vol_regime'] = atr_pct.apply(classify_regime)

    # Statistics
    regime_counts = df['vol_regime'].value_counts().sort_index()
    total = len(df)

    print("\n🔍 Volatility Regime Distribution:")
    print(f"   Low Vol (0):    {regime_counts.get(0, 0):>6} samples ({regime_counts.get(0, 0)/total*100:>5.1f}%)")
    print(f"   Medium Vol (1): {regime_counts.get(1, 0):>6} samples ({regime_counts.get(1, 0)/total*100:>5.1f}%)")
    print(f"   High Vol (2):   {regime_counts.get(2, 0):>6} samples ({regime_counts.get(2, 0)/total*100:>5.1f}%)")

    return df, ['vol_regime']


def add_spread_features(df: pd.DataFrame, gen_config: dict, config: dict, model_store) -> tuple[pd.DataFrame, list[str]]:
    """
    Add high-low spread features for microstructure analysis.
    Useful for detecting volatility and liquidity conditions.

    ITB Generator compatible function.

    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        gen_config: Generator config dict (expects 'windows' key)
        config: Global config dict
        model_store: Model store instance

    Returns:
        (df, feature_names): Modified DataFrame and list of created features

    Config example:
        {
            "generator": "common.gen_labels_aggressive:add_spread_features",
            "config": {
                "windows": [3, 5, 10]
            }
        }
    """

    # Get windows from config, default to [3, 5, 10]
    windows = gen_config.get('windows', [3, 5, 10])

    if 'high' not in df.columns or 'low' not in df.columns or 'close' not in df.columns:
        print("⚠️  Warning: Missing required columns for spread features")
        return df, []

    # Candle spread as % of close
    spread_pct = ((df['high'] - df['low']) / df['close']) * 100

    features_added = []
    for window in windows:
        feature_name = f"spread_pct_{window}"
        df[feature_name] = spread_pct.rolling(window=window, min_periods=1).mean()
        features_added.append(feature_name)

    print(f"✅ Spread features added: {features_added}")

    return df, features_added


if __name__ == "__main__":
    # Example usage and testing
    print("=" * 80)
    print("Aggressive Label Generator - Test Mode")
    print("=" * 80)

    # Generate sample data
    np.random.seed(42)
    n_samples = 1000

    sample_df = pd.DataFrame({
        'timestamp': pd.date_range('2025-01-01', periods=n_samples, freq='1min'),
        'close': 50000 + np.cumsum(np.random.randn(n_samples) * 10),
    })

    # Add high/low with realistic spread
    sample_df['high'] = sample_df['close'] * (1 + np.abs(np.random.randn(n_samples)) * 0.001)
    sample_df['low'] = sample_df['close'] * (1 - np.abs(np.random.randn(n_samples)) * 0.001)

    # Test configuration
    test_config = {
        "columns": ["close", "high", "low"],
        "function": "high",
        "thresholds": [0.15, 0.20, 0.25, 0.30],
        "tolerance": 0.05,
        "horizon": 10,
        "names": ["high_015_10", "high_020_10", "high_025_10", "high_030_10"]
    }

    print("\n🧪 Testing with configuration:")
    print(f"   Function: {test_config['function']}")
    print(f"   Thresholds: {test_config['thresholds']}")
    print(f"   Horizon: {test_config['horizon']} candles")
    print(f"   Tolerance: {test_config['tolerance']}%")

    # Generate labels
    sample_df, labels = generate_labels_aggressive(sample_df, test_config)

    print("\n✅ Test completed successfully!")
    print(f"   Labels created: {labels}")
    print(f"   DataFrame shape: {sample_df.shape}")
