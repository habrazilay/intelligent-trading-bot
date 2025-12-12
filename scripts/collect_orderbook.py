#!/usr/bin/env python3
"""
Binance Order Book Collector

Streams real-time order book data via WebSocket and saves to Parquet files.
This data will be used to extract order flow features for improved trading predictions.

This script complements download_binance.py:
- download_binance.py: Downloads historical OHLCV data (REST API, one-time)
- collect_orderbook.py: Collects real-time L2 order book data (WebSocket, continuous)

Usage:
    # From command line
    python scripts/collect_orderbook.py --symbol BTCUSDT --duration 24h

    # From config file (similar to download_binance.py)
    python scripts/collect_orderbook.py --config configs/btcusdt_5m_orderflow.jsonc

    # Custom output directory
    python scripts/collect_orderbook.py --symbol BTCUSDT --output DATA_ORDERBOOK/
"""

import argparse
import json
import time
import signal
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque
import pandas as pd
from binance import ThreadedWebsocketManager

# Reuse existing utilities
try:
    from service.App import load_config, App
    HAS_APP = True
except ImportError:
    HAS_APP = False

# Configure logging - use unique log file per execution to avoid overwriting
log_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_filename = f"logs/collect_orderbook_{log_timestamp}.log"

# Ensure logs directory exists
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_filename, mode="a", encoding="utf-8"),  # append mode!
    ],
)
log = logging.getLogger(__name__)
log.info(f"Log file: {log_filename}")

# Global state
orderbook_snapshots = deque(maxlen=100000)  # Keep last 100k snapshots in memory
running = True
stats = {
    'snapshots_collected': 0,
    'start_time': None,
    'last_save_time': None,
    'files_written': 0
}


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global running
    print('\n\n🛑 Stopping collector...')
    running = False


def parse_duration(duration_str):
    """
    Parse duration string like '24h', '7d', '30m' into seconds

    Examples:
        '30m' -> 1800 seconds
        '24h' -> 86400 seconds
        '7d' -> 604800 seconds
    """
    unit = duration_str[-1]
    value = int(duration_str[:-1])

    if unit == 's':
        return value
    elif unit == 'm':
        return value * 60
    elif unit == 'h':
        return value * 3600
    elif unit == 'd':
        return value * 86400
    else:
        raise ValueError(f"Unknown duration unit: {unit}. Use s, m, h, or d")


def handle_orderbook_update(msg):
    """Process incoming order book updates from WebSocket"""
    global orderbook_snapshots, stats

    try:
        timestamp = datetime.now()

        # Extract bids and asks
        # Binance depth stream sends: {'lastUpdateId': ..., 'bids': [...], 'asks': [...]}
        if 'bids' in msg and 'asks' in msg:
            bids = msg['bids']
            asks = msg['asks']
        elif 'b' in msg and 'a' in msg:
            # Diff depth format
            bids = msg['b']
            asks = msg['a']
        else:
            return

        if not bids or not asks:
            return

        # Parse top 20 levels
        snapshot = {
            'timestamp': timestamp.isoformat(),
            'timestamp_ms': int(timestamp.timestamp() * 1000),
            'update_id': msg.get('lastUpdateId', msg.get('u', 0)),
        }

        # Store top 20 bid levels
        for i, (price, qty) in enumerate(bids[:20]):
            snapshot[f'bid_price_{i}'] = float(price)
            snapshot[f'bid_qty_{i}'] = float(qty)

        # Store top 20 ask levels
        for i, (price, qty) in enumerate(asks[:20]):
            snapshot[f'ask_price_{i}'] = float(price)
            snapshot[f'ask_qty_{i}'] = float(qty)

        # Calculate immediate metrics
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        snapshot['mid_price'] = (best_bid + best_ask) / 2
        snapshot['spread'] = best_ask - best_bid
        snapshot['spread_pct'] = (snapshot['spread'] / snapshot['mid_price']) * 100

        # Add to buffer
        orderbook_snapshots.append(snapshot)
        stats['snapshots_collected'] += 1

        if stats['start_time'] is None:
            stats['start_time'] = timestamp

        # Print progress every 100 snapshots
        if stats['snapshots_collected'] % 100 == 0:
            elapsed = (timestamp - stats['start_time']).total_seconds()
            rate = stats['snapshots_collected'] / elapsed if elapsed > 0 else 0
            print(f"📊 Collected: {stats['snapshots_collected']} snapshots | "
                  f"Rate: {rate:.1f}/s | "
                  f"Buffer: {len(orderbook_snapshots)} | "
                  f"Mid: ${snapshot['mid_price']:,.2f}")

    except Exception as e:
        print(f"⚠️  Error processing update: {e}")


def save_snapshots_to_parquet(output_dir, symbol):
    """
    Save collected snapshots to Parquet file

    Reuses same Parquet format as download_binance.py (snappy compression)
    """
    global orderbook_snapshots, stats

    if not orderbook_snapshots:
        return

    try:
        # Convert to DataFrame
        df = pd.DataFrame(list(orderbook_snapshots))

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{symbol}_orderbook_{timestamp}.parquet"
        filepath = output_dir / filename

        # Ensure directory exists (same pattern as download_binance.py)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Save to Parquet with snappy compression (same as download_binance.py)
        df.to_parquet(filepath, compression='snappy', index=False)

        stats['files_written'] += 1
        stats['last_save_time'] = datetime.now()

        log.info("Saved %d snapshots to %s (%.2f MB)",
                 len(df), filename, filepath.stat().st_size / 1024 / 1024)

        # Clear buffer after saving
        orderbook_snapshots.clear()

    except Exception as e:
        log.error("Error saving to Parquet: %s", e)


def collect_orderbook(symbol='BTCUSDT', duration_seconds=86400, output_dir='DATA_ORDERBOOK',
                     save_interval=3600):
    """
    Main collection loop

    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        duration_seconds: How long to collect data (seconds)
        output_dir: Directory to save Parquet files
        save_interval: How often to save to disk (seconds)
    """
    global running, stats

    # Setup
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print("="*70)
    print(f"🚀 BINANCE ORDER BOOK COLLECTOR")
    print("="*70)
    print(f"Symbol: {symbol}")
    print(f"Duration: {duration_seconds / 3600:.1f} hours")
    print(f"Output: {output_path.absolute()}")
    print(f"Save interval: {save_interval / 60:.0f} minutes")
    print("="*70)
    print("\nStarting WebSocket connection...")

    # Start WebSocket
    twm = ThreadedWebsocketManager()
    twm.start()

    # Subscribe to order book depth (20 levels @ 100ms)
    stream = twm.start_depth_socket(
        callback=handle_orderbook_update,
        symbol=symbol,
        depth='20'
    )

    print(f"✅ Connected! Collecting order book data for {symbol}...")
    print("   Press Ctrl+C to stop\n")

    start_time = time.time()
    last_save = time.time()

    try:
        while running:
            current_time = time.time()
            elapsed = current_time - start_time

            # Check if duration exceeded
            if elapsed >= duration_seconds:
                print(f"\n✅ Duration reached ({duration_seconds}s)")
                break

            # Periodic save
            if current_time - last_save >= save_interval:
                save_snapshots_to_parquet(output_path, symbol)
                last_save = current_time

            # Sleep briefly
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user")

    finally:
        # Final save
        print("\n📁 Saving remaining data...")
        save_snapshots_to_parquet(output_path, symbol)

        # Stop WebSocket
        twm.stop()

        # Print summary
        print("\n" + "="*70)
        print("COLLECTION SUMMARY")
        print("="*70)
        print(f"Total snapshots: {stats['snapshots_collected']}")
        print(f"Files written: {stats['files_written']}")
        print(f"Duration: {elapsed / 3600:.2f} hours")
        if elapsed > 0:
            print(f"Average rate: {stats['snapshots_collected'] / elapsed:.2f} snapshots/second")
        print(f"Output directory: {output_path.absolute()}")
        print("="*70)
        print("\n✅ Collection complete!")


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(
        description='Collect real-time order book data from Binance',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using command-line arguments:
  python scripts/collect_orderbook.py --symbol BTCUSDT --duration 24h
  python scripts/collect_orderbook.py --symbol BTCUSDT --duration 7d --save-interval 6h

  # Using config file (like download_binance.py):
  python scripts/collect_orderbook.py --config configs/btcusdt_5m_orderflow.jsonc

  # Quick test:
  python scripts/collect_orderbook.py --symbol BTCUSDT --duration 5m --save-interval 1m
        """
    )

    # Config file option (like download_binance.py)
    parser.add_argument(
        '--config',
        '-c',
        type=str,
        help='JSONC configuration file (alternative to CLI args)'
    )

    parser.add_argument(
        '--symbol',
        type=str,
        help='Trading pair symbol (default: from config or BTCUSDT)'
    )

    parser.add_argument(
        '--duration',
        type=str,
        help='Collection duration (e.g., 30m, 24h, 7d) (default: 24h)'
    )

    parser.add_argument(
        '--output',
        type=str,
        help='Output directory (default: DATA_ORDERBOOK or from config)'
    )

    parser.add_argument(
        '--save-interval',
        type=str,
        help='How often to save to disk (e.g., 30m, 1h) (default: 1h)'
    )

    args = parser.parse_args()

    # Determine parameters from config file or CLI args
    if args.config:
        if not HAS_APP:
            log.error("Config file requires service.App module")
            sys.exit(1)

        # Load config (same as download_binance.py)
        load_config(args.config)
        symbol = args.symbol or App.config.get('symbol', 'BTCUSDT')
        output_dir = args.output or f"DATA_ORDERBOOK_{symbol}"

        # Get duration from config if specified
        duration_str = args.duration or App.config.get('orderbook_collection', {}).get('duration', '24h')
        save_interval_str = args.save_interval or App.config.get('orderbook_collection', {}).get('save_interval', '1h')

        log.info("Loaded config from %s", args.config)
        log.info("Symbol: %s, Duration: %s, Save interval: %s", symbol, duration_str, save_interval_str)
    else:
        # Use CLI args with defaults
        symbol = args.symbol or 'BTCUSDT'
        duration_str = args.duration or '24h'
        output_dir = args.output or 'DATA_ORDERBOOK'
        save_interval_str = args.save_interval or '1h'

    # Parse durations
    duration_seconds = parse_duration(duration_str)
    save_interval = parse_duration(save_interval_str)

    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)

    # Run collector
    collect_orderbook(
        symbol=symbol,
        duration_seconds=duration_seconds,
        output_dir=output_dir,
        save_interval=save_interval
    )


if __name__ == '__main__':
    main()
