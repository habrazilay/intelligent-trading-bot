#!/usr/bin/env python3
"""
Download Forex historical data from Yahoo Finance (free).

Yahoo Finance provides free Forex data with symbols like:
- EURUSD=X (EUR/USD)
- GBPUSD=X (GBP/USD)
- USDJPY=X (USD/JPY)

Usage:
    python -m scripts.download_forex_yfinance --symbol EURUSD --timeframe 1h --days 365
    python -m scripts.download_forex_yfinance --all-pairs
"""

import os
import argparse
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    print("Installing yfinance...")
    os.system("pip install yfinance")
    import yfinance as yf


# Forex pairs mapping to Yahoo Finance symbols
FOREX_SYMBOLS = {
    # Major pairs (USD)
    'EURUSD': 'EURUSD=X',
    'GBPUSD': 'GBPUSD=X',
    'USDJPY': 'USDJPY=X',
    'USDCHF': 'USDCHF=X',
    'AUDUSD': 'AUDUSD=X',
    'USDCAD': 'USDCAD=X',
    'NZDUSD': 'NZDUSD=X',

    # Cross pairs
    'EURGBP': 'EURGBP=X',
    'EURJPY': 'EURJPY=X',
    'GBPJPY': 'GBPJPY=X',
    'EURCHF': 'EURCHF=X',
    'EURAUD': 'EURAUD=X',
    'GBPCHF': 'GBPCHF=X',
    'AUDJPY': 'AUDJPY=X',
    'CADJPY': 'CADJPY=X',

    # Exotic pairs
    'USDILS': 'USDILS=X',   # Israeli Shekel
    'USDBRL': 'USDBRL=X',   # Brazilian Real
    'USDMXN': 'USDMXN=X',   # Mexican Peso
    'USDZAR': 'USDZAR=X',   # South African Rand
    'USDTRY': 'USDTRY=X',   # Turkish Lira
    'USDPLN': 'USDPLN=X',   # Polish Zloty
    'USDSEK': 'USDSEK=X',   # Swedish Krona
    'USDNOK': 'USDNOK=X',   # Norwegian Krone
    'USDDKK': 'USDDKK=X',   # Danish Krone
    'USDSGD': 'USDSGD=X',   # Singapore Dollar
    'USDHKD': 'USDHKD=X',   # Hong Kong Dollar
    'USDCNH': 'USDCNH=X',   # Chinese Yuan (offshore)
    'USDINR': 'USDINR=X',   # Indian Rupee
}

# Yahoo Finance timeframe mapping
TIMEFRAME_MAP = {
    '1m': '1m',
    '5m': '5m',
    '15m': '15m',
    '30m': '30m',
    '1h': '1h',
    '4h': '4h',   # Not available, will use 1h
    '1d': '1d',
    '1w': '1wk',
}


def download_forex_data(
    symbol: str,
    timeframe: str = '1h',
    days: int = 365,
    output_dir: str = None
) -> pd.DataFrame:
    """
    Download historical Forex data from Yahoo Finance.

    Args:
        symbol: Forex pair (e.g., 'EURUSD', 'GBPUSD')
        timeframe: Candle timeframe (1m, 5m, 15m, 30m, 1h, 1d)
        days: Number of days of history to download
        output_dir: Directory to save files

    Returns:
        DataFrame with OHLCV data
    """
    print(f"\n{'='*60}")
    print(f"  Downloading {symbol} {timeframe} - {days} days (Yahoo Finance)")
    print(f"{'='*60}")

    # Get Yahoo Finance symbol
    yf_symbol = FOREX_SYMBOLS.get(symbol.upper(), f"{symbol}=X")
    yf_interval = TIMEFRAME_MAP.get(timeframe, '1h')

    # Yahoo Finance limitations:
    # - 1m: max 7 days
    # - 5m, 15m, 30m: max 60 days
    # - 1h: max 730 days
    # - 1d+: no limit

    if timeframe == '1m' and days > 7:
        print(f"  Note: 1m data limited to 7 days on Yahoo Finance")
        days = 7
    elif timeframe in ['5m', '15m', '30m'] and days > 60:
        print(f"  Note: {timeframe} data limited to 60 days on Yahoo Finance")
        days = 60
    elif timeframe == '1h' and days > 730:
        print(f"  Note: 1h data limited to 730 days on Yahoo Finance")
        days = 730

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    print(f"\n  Symbol: {yf_symbol}")
    print(f"  Period: {start_date.date()} to {end_date.date()}")
    print(f"  Interval: {yf_interval}")

    # Download data
    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(
            start=start_date,
            end=end_date,
            interval=yf_interval
        )

        if df.empty:
            print(f"\n  No data returned!")
            return pd.DataFrame()

        # Rename columns to match our format
        df = df.reset_index()
        df = df.rename(columns={
            'Date': 'timestamp',
            'Datetime': 'timestamp',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        })

        # Select only needed columns
        columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        df = df[[c for c in columns if c in df.columns]]

        # Ensure timestamp is datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Remove timezone info if present
        if df['timestamp'].dt.tz is not None:
            df['timestamp'] = df['timestamp'].dt.tz_localize(None)

        print(f"\n  Total candles: {len(df)}")
        print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

        # Save to files
        if output_dir is None:
            output_dir = f"DATA_FOREX_{timeframe}"

        symbol_dir = os.path.join(output_dir, symbol.upper())
        Path(symbol_dir).mkdir(parents=True, exist_ok=True)

        # Save as both CSV and Parquet
        csv_path = os.path.join(symbol_dir, "klines.csv")
        parquet_path = os.path.join(symbol_dir, "klines.parquet")

        df.to_csv(csv_path, index=False)
        df.to_parquet(parquet_path, index=False)

        print(f"\n  Saved to:")
        print(f"    - {csv_path}")
        print(f"    - {parquet_path}")

        return df

    except Exception as e:
        print(f"\n  Error: {e}")
        return pd.DataFrame()


def main():
    parser = argparse.ArgumentParser(description='Download Forex data from Yahoo Finance')
    parser.add_argument('--symbol', '-s', default='EURUSD',
                        help='Forex pair (e.g., EURUSD, GBPUSD)')
    parser.add_argument('--timeframe', '-t', default='1h',
                        help='Timeframe (1m, 5m, 15m, 30m, 1h, 1d)')
    parser.add_argument('--days', '-d', type=int, default=365,
                        help='Days of history to download')
    parser.add_argument('--output', '-o', default=None,
                        help='Output directory')
    parser.add_argument('--all-pairs', action='store_true',
                        help='Download all major pairs')

    args = parser.parse_args()

    if args.all_pairs:
        pairs = list(FOREX_SYMBOLS.keys())
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

    print("\n" + "="*60)
    print("  Download complete!")
    print("="*60)


if __name__ == '__main__':
    main()
