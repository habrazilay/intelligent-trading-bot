"""
Order Flow Feature Generator

Extracts predictive features from order book (L2) data.
These features capture buying/selling pressure before price moves.

Features generated:
1. Bid-ask imbalance at multiple depths
2. Order book pressure (slope of cumulative volume)
3. Large order detection (walls)
4. Effective spread
5. Volume distribution metrics

Integration with ITB:
    Add to config feature_sets:
    {
        "generator": "orderflow",
        "config": {
            "depths": [5, 10, 20],
            "orderbook_file": "DATA_ORDERBOOK/BTCUSDT_orderbook_*.parquet"
        }
    }
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Tuple
import glob


def calculate_imbalance(bid_volumes, ask_volumes):
    """
    Calculate bid-ask imbalance ratio

    Imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)

    Returns:
        float in range [-1, 1]
        +1 = all bids (strong buying pressure)
        -1 = all asks (strong selling pressure)
         0 = balanced
    """
    total_bids = sum(bid_volumes)
    total_asks = sum(ask_volumes)

    if total_bids + total_asks == 0:
        return 0.0

    return (total_bids - total_asks) / (total_bids + total_asks)


def calculate_order_pressure(prices, volumes):
    """
    Calculate order book pressure using linear regression slope

    Pressure measures how volume is distributed across price levels.
    Steep slope = volume concentrated far from mid price (weak pressure)
    Flat slope = volume concentrated near mid price (strong pressure)

    Returns:
        float: regression slope of cumulative volume vs price distance
    """
    if len(prices) < 2 or len(volumes) < 2:
        return 0.0

    # Calculate cumulative volumes
    cum_volumes = np.cumsum(volumes)

    # Price distances from first price
    price_dists = np.array(prices) - prices[0]

    # Linear regression slope
    if len(price_dists) != len(cum_volumes):
        return 0.0

    try:
        slope = np.polyfit(price_dists, cum_volumes, 1)[0]
        return float(slope)
    except:
        return 0.0


def detect_large_orders(volumes, threshold_multiplier=2.0):
    """
    Detect walls (large orders) in order book

    Args:
        volumes: List of order volumes at each level
        threshold_multiplier: Wall = volume > (mean * multiplier)

    Returns:
        tuple: (wall_count, wall_ratio, max_wall_size)
    """
    if not volumes or len(volumes) == 0:
        return 0, 0.0, 0.0

    volumes = np.array(volumes)
    mean_volume = np.mean(volumes)

    if mean_volume == 0:
        return 0, 0.0, 0.0

    # Identify walls
    threshold = mean_volume * threshold_multiplier
    walls = volumes > threshold

    wall_count = int(np.sum(walls))
    wall_ratio = float(np.sum(volumes[walls]) / np.sum(volumes)) if np.sum(volumes) > 0 else 0.0
    max_wall_size = float(np.max(volumes) / mean_volume)

    return wall_count, wall_ratio, max_wall_size


def load_orderbook_data(orderbook_pattern):
    """
    Load order book snapshots from Parquet files

    Args:
        orderbook_pattern: Glob pattern for orderbook files
                          e.g., "DATA_ORDERBOOK/BTCUSDT_orderbook_*.parquet"

    Returns:
        DataFrame with columns: timestamp, bid_price_0..19, bid_qty_0..19,
                               ask_price_0..19, ask_qty_0..19
    """
    files = glob.glob(orderbook_pattern)

    if not files:
        raise FileNotFoundError(f"No orderbook files found matching: {orderbook_pattern}")

    print(f"  Loading {len(files)} orderbook file(s)...")

    dfs = []
    for file in sorted(files):
        df = pd.read_parquet(file)
        dfs.append(df)

    # Concatenate all files
    orderbook_df = pd.concat(dfs, ignore_index=True)

    # Convert timestamp to datetime
    orderbook_df['timestamp'] = pd.to_datetime(orderbook_df['timestamp'])

    # Sort by timestamp
    orderbook_df = orderbook_df.sort_values('timestamp').reset_index(drop=True)

    print(f"  Loaded {len(orderbook_df)} orderbook snapshots")
    print(f"  Time range: {orderbook_df['timestamp'].min()} to {orderbook_df['timestamp'].max()}")

    return orderbook_df


def aggregate_orderbook_to_bars(orderbook_df, ohlcv_df, freq='5T'):
    """
    Aggregate order book snapshots to match OHLCV bar timestamps

    For each OHLCV bar, we calculate order flow features from all
    orderbook snapshots within that bar period.

    Args:
        orderbook_df: DataFrame with orderbook snapshots
        ohlcv_df: DataFrame with OHLCV bars (must have 'timestamp' column)
        freq: Bar frequency (e.g., '5T' for 5 minutes)

    Returns:
        DataFrame with aggregated order flow metrics aligned to OHLCV bars
    """
    print(f"  Aggregating orderbook snapshots to {freq} bars...")

    # Ensure both have datetime timestamps
    if 'timestamp' not in ohlcv_df.columns:
        raise ValueError("ohlcv_df must have 'timestamp' column")

    orderbook_df = orderbook_df.copy()
    ohlcv_df = ohlcv_df.copy()

    orderbook_df['timestamp'] = pd.to_datetime(orderbook_df['timestamp'])
    ohlcv_df['timestamp'] = pd.to_datetime(ohlcv_df['timestamp'])

    # Create time bins based on OHLCV bar timestamps
    ohlcv_df['bar_start'] = ohlcv_df['timestamp']
    ohlcv_df['bar_end'] = ohlcv_df['timestamp'] + pd.Timedelta(freq)

    aggregated_features = []

    for idx, row in ohlcv_df.iterrows():
        bar_start = row['bar_start']
        bar_end = row['bar_end']

        # Get orderbook snapshots within this bar
        mask = (orderbook_df['timestamp'] >= bar_start) & (orderbook_df['timestamp'] < bar_end)
        bar_snapshots = orderbook_df[mask]

        if len(bar_snapshots) == 0:
            # No snapshots in this bar - use NaN (will be forward-filled later)
            features = {'timestamp': row['timestamp']}
        else:
            # Calculate features from snapshots in this bar
            features = calculate_orderflow_features_for_bar(bar_snapshots)
            features['timestamp'] = row['timestamp']

        aggregated_features.append(features)

    result_df = pd.DataFrame(aggregated_features)

    # Forward fill missing values (bars with no orderbook data)
    result_df = result_df.fillna(method='ffill')

    return result_df


def calculate_orderflow_features_for_bar(snapshots_df):
    """
    Calculate order flow features from orderbook snapshots within a single bar

    Args:
        snapshots_df: DataFrame with orderbook snapshots for one bar period

    Returns:
        dict: Order flow features
    """
    features = {}

    if len(snapshots_df) == 0:
        return features

    # Use median snapshot (middle of the bar) to avoid noise
    median_idx = len(snapshots_df) // 2
    snapshot = snapshots_df.iloc[median_idx]

    # Extract bid/ask prices and quantities
    bid_prices = [snapshot[f'bid_price_{i}'] for i in range(20) if f'bid_price_{i}' in snapshot]
    bid_qtys = [snapshot[f'bid_qty_{i}'] for i in range(20) if f'bid_qty_{i}' in snapshot]
    ask_prices = [snapshot[f'ask_price_{i}'] for i in range(20) if f'ask_price_{i}' in snapshot]
    ask_qtys = [snapshot[f'ask_qty_{i}'] for i in range(20) if f'ask_qty_{i}' in snapshot]

    # Feature 1: Bid-ask imbalance at different depths
    for depth in [5, 10, 20]:
        if len(bid_qtys) >= depth and len(ask_qtys) >= depth:
            imbalance = calculate_imbalance(bid_qtys[:depth], ask_qtys[:depth])
            features[f'imbalance_{depth}'] = imbalance

    # Feature 2: Order book pressure
    if len(bid_prices) >= 10 and len(bid_qtys) >= 10:
        bid_pressure = calculate_order_pressure(bid_prices[:10], bid_qtys[:10])
        features['bid_pressure'] = bid_pressure

    if len(ask_prices) >= 10 and len(ask_qtys) >= 10:
        ask_pressure = calculate_order_pressure(ask_prices[:10], ask_qtys[:10])
        features['ask_pressure'] = ask_pressure

    # Feature 3: Large order detection (walls)
    if len(bid_qtys) >= 20:
        bid_wall_count, bid_wall_ratio, bid_max_wall = detect_large_orders(bid_qtys[:20])
        features['bid_wall_count'] = bid_wall_count
        features['bid_wall_ratio'] = bid_wall_ratio
        features['bid_max_wall'] = bid_max_wall

    if len(ask_qtys) >= 20:
        ask_wall_count, ask_wall_ratio, ask_max_wall = detect_large_orders(ask_qtys[:20])
        features['ask_wall_count'] = ask_wall_count
        features['ask_wall_ratio'] = ask_wall_ratio
        features['ask_max_wall'] = ask_max_wall

    # Feature 4: Effective spread
    if 'spread_pct' in snapshot:
        features['effective_spread'] = snapshot['spread_pct']

    # Feature 5: Level 1 imbalance (best bid vs best ask)
    if len(bid_qtys) > 0 and len(ask_qtys) > 0:
        features['level1_imbalance'] = calculate_imbalance([bid_qtys[0]], [ask_qtys[0]])

    # Feature 6: Volume distribution (bid/ask skewness)
    if len(bid_qtys) >= 10:
        features['bid_volume_std'] = np.std(bid_qtys[:10])
        features['bid_volume_skew'] = pd.Series(bid_qtys[:10]).skew()

    if len(ask_qtys) >= 10:
        features['ask_volume_std'] = np.std(ask_qtys[:10])
        features['ask_volume_skew'] = pd.Series(ask_qtys[:10]).skew()

    # Feature 7: Total depth (total bid/ask volume in top 20 levels)
    features['total_bid_depth'] = sum(bid_qtys[:20])
    features['total_ask_depth'] = sum(ask_qtys[:20])
    features['depth_ratio'] = features['total_bid_depth'] / (features['total_ask_depth'] + 1e-8)

    return features


def generate_orderflow_features(df: pd.DataFrame, gen_config: dict, config: dict,
                                model_store) -> Tuple[pd.DataFrame, List[str]]:
    """
    Main function to generate order flow features

    This function follows the ITB generator pattern:
    - Input: OHLCV dataframe
    - Output: (dataframe with new features, list of feature names)

    Config example:
    {
        "generator": "orderflow",
        "config": {
            "orderbook_pattern": "DATA_ORDERBOOK/BTCUSDT_orderbook_*.parquet",
            "depths": [5, 10, 20],
            "freq": "5T"  # Must match OHLCV frequency
        }
    }

    Args:
        df: OHLCV dataframe with 'timestamp' column
        gen_config: Generator configuration
        config: Global config
        model_store: Model store (unused)

    Returns:
        tuple: (dataframe with orderflow features, list of feature names)
    """
    print(f"\n→ Generating order flow features...")

    # Get config
    orderbook_pattern = gen_config.get('orderbook_pattern')
    freq = gen_config.get('freq', '5T')

    if not orderbook_pattern:
        raise ValueError("orderflow generator requires 'orderbook_pattern' in config")

    # Load orderbook data
    orderbook_df = load_orderbook_data(orderbook_pattern)

    # Aggregate to bar frequency
    orderflow_features_df = aggregate_orderbook_to_bars(orderbook_df, df, freq=freq)

    # Merge with original dataframe
    df_merged = df.merge(orderflow_features_df, on='timestamp', how='left')

    # Get list of new feature columns (exclude timestamp)
    feature_cols = [col for col in orderflow_features_df.columns if col != 'timestamp']

    print(f"  ✓ Generated {len(feature_cols)} order flow features")
    print(f"  Features: {', '.join(feature_cols[:5])}{'...' if len(feature_cols) > 5 else ''}")

    return df_merged, feature_cols


# Alias for ITB compatibility
add_orderflow_features = generate_orderflow_features
