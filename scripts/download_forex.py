#!/usr/bin/env python3
"""
Download Forex historical data via MetaApi.

Usage:
    python -m scripts.download_forex --symbol EURUSD --timeframe 1h --days 365
    python -m scripts.download_forex --symbol GBPUSD --timeframe 4h --days 180
"""

import os
import sys
import argparse
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from service.adapters.metaapi_adapter import MetaApiAdapter


def download_forex_data(
    symbol: str,
    timeframe: str = '1h',
    days: int = 365,
    output_dir: str = None
) -> pd.DataFrame:
    """
    Download historical Forex data from MetaApi.

    Args:
        symbol: Forex pair (e.g., 'EURUSD', 'GBPUSD')
        timeframe: Candle timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d)
        days: Number of days of history to download
        output_dir: Directory to save CSV files

    Returns:
        DataFrame with OHLCV data
    """
    print(f"\n{'='*60}")
    print(f"  Downloading {symbol} {timeframe} - {days} days")
    print(f"{'='*60}")

    # Initialize adapter
    adapter = MetaApiAdapter()

    # Calculate start time
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)

    print(f"\n  Period: {start_time.date()} to {end_time.date()}")

    # Download in chunks (MetaApi limits)
    all_candles = []
    chunk_days = 30  # Download 30 days at a time
    current_start = start_time

    while current_start < end_time:
        chunk_end = min(current_start + timedelta(days=chunk_days), end_time)

        print(f"  Downloading: {current_start.date()} to {chunk_end.date()}...", end=" ")

        try:
            df = adapter.get_candles(
                symbol=symbol,
                timeframe=timeframe,
                start_time=current_start,
                limit=10000
            )

            if not df.empty:
                all_candles.append(df)
                print(f"{len(df)} candles")
            else:
                print("no data")

        except Exception as e:
            print(f"error: {e}")

        current_start = chunk_end

    if not all_candles:
        print("\n  No data downloaded!")
        return pd.DataFrame()

    # Combine all chunks
    df = pd.concat(all_candles, ignore_index=True)

    # Remove duplicates and sort
    df = df.drop_duplicates(subset=['timestamp'])
    df = df.sort_values('timestamp')
    df = df.reset_index(drop=True)

    print(f"\n  Total candles: {len(df)}")
    print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

    # Save to CSV
    if output_dir is None:
        output_dir = f"DATA_FOREX_{timeframe}"

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    filename = f"{symbol.lower()}_klines.csv"
    filepath = os.path.join(output_dir, filename)

    df.to_csv(filepath, index=False)
    print(f"\n  Saved to: {filepath}")

    return df


def main():
    parser = argparse.ArgumentParser(description='Download Forex historical data')
    parser.add_argument('--symbol', '-s', default='EURUSD',
                        help='Forex pair (e.g., EURUSD, GBPUSD)')
    parser.add_argument('--timeframe', '-t', default='1h',
                        help='Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d)')
    parser.add_argument('--days', '-d', type=int, default=365,
                        help='Days of history to download')
    parser.add_argument('--output', '-o', default=None,
                        help='Output directory')
    parser.add_argument('--all-pairs', action='store_true',
                        help='Download all major pairs')

    args = parser.parse_args()

    if args.all_pairs:
        # Download all major Forex pairs
        pairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'NZDUSD']
        for pair in pairs:
            try:
                download_forex_data(
                    symbol=pair,
                    timeframe=args.timeframe,
                    days=args.days,
                    output_dir=args.output
                )
            except Exception as e:
                print(f"Error downloading {pair}: {e}")
    else:
        download_forex_data(
            symbol=args.symbol,
            timeframe=args.timeframe,
            days=args.days,
            output_dir=args.output
        )


if __name__ == '__main__':
    main()
