"""
Config Helper Module

Provides utilities to:
1. Parse CLI arguments (--symbol, --freq)
2. Substitute placeholders in config files ({symbol}, {freq})
3. Calculate dynamic values (train_length, label_horizon) based on freq

Usage:
    from scripts.config_helper import load_config_with_args

    config = load_config_with_args(
        config_path="configs/base_conservative.jsonc",
        symbol="BTCUSDT",
        freq="5m"
    )
"""

import json
import os
import sys
from typing import Dict, Any, Optional


# Mapping: freq → (train_length, label_horizon, pandas_freq)
FREQ_PARAMS = {
    "1m": {
        "train_length": 525600,   # 1 year (365 * 24 * 60)
        "label_horizon": 60,      # 1 hour
        "predict_length": 1440,   # 1 day
        "pandas_freq": "1min",
    },
    "5m": {
        "train_length": 105120,   # 1 year (365 * 24 * 12)
        "label_horizon": 24,      # 2 hours
        "predict_length": 288,    # 1 day
        "pandas_freq": "5min",
    },
    "15m": {
        "train_length": 35040,    # 1 year (365 * 24 * 4)
        "label_horizon": 16,      # 4 hours
        "predict_length": 96,     # 1 day
        "pandas_freq": "15min",
    },
    "1h": {
        "train_length": 8760,     # 1 year (365 * 24)
        "label_horizon": 4,       # 4 hours
        "predict_length": 24,     # 1 day
        "pandas_freq": "1h",
    },
}


def substitute_placeholders(obj: Any, symbol: str, freq: str, pandas_freq: str) -> Any:
    """
    Recursively substitute placeholders in config:
    - {symbol} → BTCUSDT
    - {freq} → 5m
    - {pandas_freq} → 5min
    """
    if isinstance(obj, dict):
        return {k: substitute_placeholders(v, symbol, freq, pandas_freq) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [substitute_placeholders(item, symbol, freq, pandas_freq) for item in obj]
    elif isinstance(obj, str):
        return (obj
                .replace("{symbol}", symbol)
                .replace("{freq}", freq)
                .replace("{pandas_freq}", pandas_freq))
    else:
        return obj


def load_config_with_args(
    config_path: str,
    symbol: Optional[str] = None,
    freq: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Load config and apply CLI arguments.

    Steps:
    1. Load config JSON
    2. If symbol/freq provided, substitute placeholders
    3. Apply freq-based dynamic parameters (train_length, label_horizon)
    4. Validate required fields

    Args:
        config_path: Path to .jsonc config file
        symbol: Override symbol (e.g., "BTCUSDT")
        freq: Override frequency (e.g., "5m")

    Returns:
        Processed config dict

    Raises:
        ValueError: If freq not supported or required fields missing
    """

    # Load config (strip comments for JSONC support)
    with open(config_path, 'r') as f:
        content = f.read()
        # Remove // comments
        lines = []
        for line in content.split('\n'):
            # Remove inline comments
            if '//' in line:
                line = line.split('//')[0]
            lines.append(line)
        clean_content = '\n'.join(lines)
        config = json.loads(clean_content)

    # If no CLI args, use config values as-is
    if symbol is None:
        symbol = config.get("symbol", "BTCUSDT")
    if freq is None:
        freq = config.get("freq", "5m")

    # Validate freq
    if freq not in FREQ_PARAMS:
        raise ValueError(
            f"Unsupported frequency: {freq}. "
            f"Supported: {', '.join(FREQ_PARAMS.keys())}"
        )

    # Get freq-based parameters
    freq_params = FREQ_PARAMS[freq]
    pandas_freq = freq_params["pandas_freq"]

    # Substitute placeholders
    config = substitute_placeholders(config, symbol, freq, pandas_freq)

    # Apply dynamic parameters (only if not already set in config)
    config.setdefault("train_length", freq_params["train_length"])
    config.setdefault("label_horizon", freq_params["label_horizon"])
    config.setdefault("features_horizon", freq_params["label_horizon"])
    config.setdefault("predict_length", freq_params["predict_length"])

    # Validate required fields
    required_fields = ["symbol", "freq", "data_folder"]
    missing = [f for f in required_fields if not config.get(f)]
    if missing:
        raise ValueError(f"Missing required config fields: {', '.join(missing)}")

    return config


def add_config_args(parser):
    """
    Add standard config-related arguments to argparse parser.

    Usage:
        import argparse
        from scripts.config_helper import add_config_args

        parser = argparse.ArgumentParser()
        add_config_args(parser)
        args = parser.parse_args()
    """
    parser.add_argument(
        "-c", "--config",
        type=str,
        required=True,
        help="Path to config file (e.g., configs/base_conservative.jsonc)"
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="Override symbol (e.g., BTCUSDT, ETHUSDT, SOLUSDT)"
    )
    parser.add_argument(
        "--freq",
        type=str,
        default=None,
        choices=list(FREQ_PARAMS.keys()),
        help="Override frequency (e.g., 1m, 5m, 15m, 1h)"
    )


def print_config_summary(config: Dict[str, Any]) -> None:
    """Print a summary of the loaded config."""
    print("\n" + "="*70)
    print("CONFIG SUMMARY")
    print("="*70)
    print(f"Symbol:           {config.get('symbol')}")
    print(f"Frequency:        {config.get('freq')} ({config.get('pandas_freq')})")
    print(f"Data folder:      {config.get('data_folder')}")
    print(f"Description:      {config.get('description', 'N/A')}")
    print(f"Train mode:       {config.get('train', True)}")
    print(f"Train length:     {config.get('train_length'):,} candles")
    print(f"Label horizon:    {config.get('label_horizon')} candles")
    print(f"Predict length:   {config.get('predict_length')} candles")

    # Feature sets
    feature_sets = config.get('feature_sets', [])
    print(f"Feature sets:     {len(feature_sets)}")

    # Train features
    train_features = config.get('train_features', [])
    print(f"Train features:   {len(train_features)}")

    # Algorithms
    algorithms = config.get('algorithms', [])
    algo_names = [a['name'] for a in algorithms]
    print(f"Algorithms:       {', '.join(algo_names)}")

    # Labels
    labels = config.get('labels', [])
    print(f"Labels:           {', '.join(labels)}")

    print("="*70 + "\n")


if __name__ == "__main__":
    """Test config loading"""
    import argparse

    parser = argparse.ArgumentParser(description="Test config helper")
    add_config_args(parser)
    args = parser.parse_args()

    config = load_config_with_args(
        config_path=args.config,
        symbol=args.symbol,
        freq=args.freq
    )

    print_config_summary(config)

    print("\nFull config:")
    print(json.dumps(config, indent=2))
