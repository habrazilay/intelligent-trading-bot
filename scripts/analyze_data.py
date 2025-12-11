#!/usr/bin/env python
"""
Generic data analysis script for calibrating trading parameters.

Usage:
  python -m scripts.analyze_data --symbol BTCUSDT --freq 5m --days 90

The script:
  - Loads klines.parquet for the specified symbol/freq
  - Analyzes recent N days of data
  - Calculates ATR (volatility indicators)
  - Analyzes future returns at multiple horizons
  - Shows probabilities of price movements
  - Provides recommendations for label thresholds and signal parameters
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


# Frequency mapping for horizon calculation
FREQ_CONFIG = {
    "1m": {
        "horizons": [5, 10, 20, 30, 60, 120],  # 5min, 10min, 20min, 30min, 1h, 2h
        "horizon_desc": lambda h: f"{h} candles (={h}min)",
        "label_horizon_rec": 60,  # Recommend 60 candles (1h)
    },
    "5m": {
        "horizons": [6, 12, 24, 36, 72],  # 30min, 1h, 2h, 3h, 6h
        "horizon_desc": lambda h: f"{h} candles (={h*5}min)",
        "label_horizon_rec": 24,  # Recommend 24 candles (2h)
    },
    "15m": {
        "horizons": [4, 8, 16, 24, 48],  # 1h, 2h, 4h, 6h, 12h
        "horizon_desc": lambda h: f"{h} candles (={h*15}min)",
        "label_horizon_rec": 16,  # Recommend 16 candles (4h)
    },
    "1h": {
        "horizons": [1, 2, 4, 6, 12, 24],  # 1h, 2h, 4h, 6h, 12h, 24h
        "horizon_desc": lambda h: f"{h} candles (={h}h)",
        "label_horizon_rec": 4,  # Recommend 4 candles (4h)
    },
}


def parse_args():
    parser = argparse.ArgumentParser(description="Generic data analysis for trading")
    parser.add_argument(
        "--symbol",
        type=str,
        required=True,
        help="Trading symbol (e.g., BTCUSDT, ETHUSDT)",
    )
    parser.add_argument(
        "--freq",
        type=str,
        required=True,
        choices=["1m", "5m", "15m", "1h"],
        help="Timeframe (1m, 5m, 15m, 1h)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Number of recent days to analyze (default: 90)",
    )
    parser.add_argument(
        "--parquet",
        type=str,
        default=None,
        help="Path to parquet file (default: DATA_ITB_{freq}/{symbol}/klines.parquet)",
    )
    return parser.parse_args()


def ensure_columns(df: pd.DataFrame):
    required = {"timestamp", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required columns in parquet: {missing}. "
            f"Available columns: {list(df.columns)}"
        )


def compute_atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """
    Calculate Average True Range (ATR) in absolute price terms.
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    prev_close = close.shift(1)
    tr1 = (high - low).abs()
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=window, min_periods=window).mean()
    return atr


def analyze_future_returns(
    df: pd.DataFrame,
    horizons: list[int],
    thresholds: list[float],
    horizon_desc_fn,
):
    """
    Analyze future return distributions and probabilities for different horizons.
    """
    print("\n" + "=" * 80)
    print("FUTURE RETURNS ANALYSIS (in %)")
    print("=" * 80)

    for h in horizons:
        future_close = df["close"].shift(-h)
        future_ret = (future_close - df["close"]) / df["close"]

        print(f"\n--- Horizon: {horizon_desc_fn(h)} ---")
        desc = future_ret.describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9])
        print(desc.to_string())

        for thr in thresholds:
            p_up = (future_ret >= thr).mean()
            p_down = (future_ret <= -thr).mean()
            print(
                f"  P(future >= +{thr*100:.2f}%): {p_up*100:5.2f}% | "
                f"P(future <= -{thr*100:.2f}%): {p_down*100:5.2f}%"
            )


def main():
    args = parse_args()

    # Determine parquet path
    if args.parquet:
        parquet_path = Path(args.parquet)
    else:
        parquet_path = Path(f"DATA_ITB_{args.freq}/{args.symbol}/klines.parquet")

    if not parquet_path.is_file():
        raise FileNotFoundError(f"Parquet file not found: {parquet_path}")

    print(f"Reading {args.freq} parquet: {parquet_path}")
    df = pd.read_parquet(parquet_path)

    ensure_columns(df)

    # Ensure timestamp with timezone and sorted
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    print(f"\nTotal dataset size ({args.freq}):")
    print(f"  Rows: {len(df):,}")
    print(f"  Period: {df['timestamp'].min()}  →  {df['timestamp'].max()}")

    # Filter to recent N days
    cutoff = df["timestamp"].max() - pd.Timedelta(days=args.days)
    df_recent = df[df["timestamp"] >= cutoff].copy().reset_index(drop=True)

    print(f"\nRecent {args.days} days subset:")
    print(f"  Rows: {len(df_recent):,}")
    print(f"  Period: {df_recent['timestamp'].min()}  →  {df_recent['timestamp'].max()}")

    # Calculate ATR
    df_recent["ATR_14"] = compute_atr(df_recent, window=14)
    df_recent["ATR_30"] = compute_atr(df_recent, window=30)

    df_recent["ATR_14_pct"] = df_recent["ATR_14"] / df_recent["close"]
    df_recent["ATR_30_pct"] = df_recent["ATR_30"] / df_recent["close"]

    print("\n" + "=" * 80)
    print("VOLATILITY ANALYSIS (ATR as % of price)")
    print("=" * 80)
    print("\nATR_14_pct (last N days):")
    print(
        df_recent["ATR_14_pct"]
        .describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9])
        .to_string()
    )

    print("\nATR_30_pct (last N days):")
    print(
        df_recent["ATR_30_pct"]
        .describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9])
        .to_string()
    )

    # Get frequency-specific configuration
    freq_conf = FREQ_CONFIG.get(args.freq)
    if not freq_conf:
        raise ValueError(f"Unsupported frequency: {args.freq}")

    horizons = freq_conf["horizons"]
    horizon_desc_fn = freq_conf["horizon_desc"]

    # Analyze future returns
    thresholds = [0.002, 0.005, 0.01, 0.02]  # 0.2%, 0.5%, 1%, 2%
    analyze_future_returns(df_recent, horizons, thresholds, horizon_desc_fn)

    # Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print(f"\nFor {args.symbol} {args.freq} trading:")
    print(f"  - label_horizon: {freq_conf['label_horizon_rec']} candles "
          f"(~{horizon_desc_fn(freq_conf['label_horizon_rec'])})")

    # ATR-based threshold recommendation
    median_atr_pct = df_recent["ATR_14_pct"].median()
    print(f"  - Median ATR: {median_atr_pct*100:.3f}%")
    print(f"  - Suggested label threshold: {median_atr_pct*100:.2f}% - {median_atr_pct*100*1.5:.2f}%")
    print(f"  - Suggested signal threshold: {median_atr_pct*100*0.5:.3f}% - {median_atr_pct*100:.3f}%")

    print("\nUse these statistics to calibrate:")
    print("  - label_horizon (in candles)")
    print("  - thresholds for labels (e.g., 0.5%, 1%)")
    print("  - buy_signal_threshold / sell_signal_threshold")


if __name__ == "__main__":
    main()
