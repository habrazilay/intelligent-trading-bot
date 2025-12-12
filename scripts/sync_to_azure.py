#!/usr/bin/env python3
"""
Sync local data to Azure Blob Storage.

Uploads to Azure Blob Container 'itb-data':
- orderbook/: Orderbook parquet files
- trades/: Trade logs
- klines/1h/: 1-hour klines data
- klines/5m/: 5-minute klines data
- klines/1m/: 1-minute klines data

Requires AZURE_STORAGE_KEY in .env.dev

Usage:
    python -m scripts.sync_to_azure --all
    python -m scripts.sync_to_azure --orderbook
    python -m scripts.sync_to_azure --trades
    python -m scripts.sync_to_azure --data
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('.env.dev')

# Azure Storage config
STORAGE_ACCOUNT = os.getenv('AZURE_STORAGE_ACCOUNT', 'stitbdev')
STORAGE_KEY = os.getenv('AZURE_STORAGE_KEY', '')
BLOB_CONTAINER = 'itb-data'

# Local paths to sync to blob container
SYNC_PATHS = {
    'orderbook': {
        'local': 'DATA_ORDERBOOK',
        'remote': 'orderbook',
        'pattern': '*.parquet'
    },
    'trades': {
        'local': 'logs/trades',
        'remote': 'trades',
        'pattern': '*'
    },
    'data_1h': {
        'local': 'DATA_ITB_1h',
        'remote': 'klines/1h',
        'pattern': '**/*.parquet'
    },
    'data_5m': {
        'local': 'DATA_ITB_5m',
        'remote': 'klines/5m',
        'pattern': '**/*.parquet'
    },
    'data_1m': {
        'local': 'DATA_ITB_1m',
        'remote': 'klines/1m',
        'pattern': '**/*.parquet'
    }
}


def run_az_command(cmd: list) -> tuple[bool, str]:
    """Run Azure CLI command and return success status and output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return False, result.stderr
        return True, result.stdout
    except Exception as e:
        return False, str(e)


def ensure_container_exists():
    """Create blob container if it doesn't exist."""
    print(f"Checking blob container '{BLOB_CONTAINER}'...")

    cmd = [
        'az', 'storage', 'container', 'create',
        '--name', BLOB_CONTAINER,
        '--account-name', STORAGE_ACCOUNT,
        '--account-key', STORAGE_KEY,
        '--only-show-errors'
    ]

    success, output = run_az_command(cmd)
    if not success:
        print(f"Warning: Could not create/check container: {output}")
    else:
        print(f"Blob container '{BLOB_CONTAINER}' ready")


def sync_folder(name: str, config: dict, dry_run: bool = False):
    """Sync a local folder to Azure Blob Storage."""
    local_path = Path(config['local'])
    remote_path = config['remote']
    pattern = config['pattern']

    if not local_path.exists():
        print(f"Skipping {name}: {local_path} does not exist")
        return

    # Count files
    files = list(local_path.glob(pattern))
    if not files:
        print(f"Skipping {name}: no files matching {pattern}")
        return

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Syncing {name}:")
    print(f"  Local: {local_path} ({len(files)} files)")
    print(f"  Remote: {BLOB_CONTAINER}/{remote_path}")

    if dry_run:
        for f in files[:5]:
            print(f"    Would upload: {f.name}")
        if len(files) > 5:
            print(f"    ... and {len(files) - 5} more files")
        return

    # Upload to Blob Storage
    cmd = [
        'az', 'storage', 'blob', 'upload-batch',
        '--source', str(local_path),
        '--destination', BLOB_CONTAINER,
        '--destination-path', remote_path,
        '--account-name', STORAGE_ACCOUNT,
        '--account-key', STORAGE_KEY,
        '--pattern', pattern,
        '--overwrite', 'true',
        '--only-show-errors'
    ]

    print(f"  Uploading...")
    success, output = run_az_command(cmd)

    if success:
        print(f"  Done! {len(files)} files synced")
    else:
        print(f"  Error: {output}")


def get_storage_stats():
    """Get stats about what's in Azure Blob Storage."""
    print("\n=== Azure Blob Storage Stats ===")
    cmd = [
        'az', 'storage', 'blob', 'list',
        '--container-name', BLOB_CONTAINER,
        '--account-name', STORAGE_ACCOUNT,
        '--account-key', STORAGE_KEY,
        '--query', '[].{name: name, size: properties.contentLength}',
        '--output', 'table'
    ]
    success, output = run_az_command(cmd)
    if success:
        print(output)
    else:
        print(f"Could not get stats: {output}")


def main():
    parser = argparse.ArgumentParser(description='Sync data to Azure Blob Storage')
    parser.add_argument('--all', action='store_true', help='Sync all data')
    parser.add_argument('--orderbook', action='store_true', help='Sync orderbook data')
    parser.add_argument('--trades', action='store_true', help='Sync trade logs')
    parser.add_argument('--data', action='store_true', help='Sync klines data')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be synced')
    parser.add_argument('--stats', action='store_true', help='Show storage stats')

    args = parser.parse_args()

    # Default to --all if no specific option
    if not any([args.all, args.orderbook, args.trades, args.data, args.stats]):
        args.all = True

    print("=" * 60)
    print(f"  Azure Blob Storage Sync - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Storage Account: {STORAGE_ACCOUNT}")
    print(f"  Container: {BLOB_CONTAINER}")
    print("=" * 60)

    # Check storage key
    if not STORAGE_KEY:
        print("\nError: AZURE_STORAGE_KEY not found in .env.dev")
        print("Add it with: AZURE_STORAGE_KEY=your_key_here")
        sys.exit(1)
    print(f"\nStorage key loaded (ending in ...{STORAGE_KEY[-4:]})")

    # Ensure container exists
    ensure_container_exists()

    if args.stats:
        get_storage_stats()
        return

    # Sync selected paths
    to_sync = []
    if args.all:
        to_sync = list(SYNC_PATHS.keys())
    else:
        if args.orderbook:
            to_sync.append('orderbook')
        if args.trades:
            to_sync.append('trades')
        if args.data:
            to_sync.extend(['data_1h', 'data_5m', 'data_1m'])

    for name in to_sync:
        if name in SYNC_PATHS:
            sync_folder(name, SYNC_PATHS[name], dry_run=args.dry_run)

    print("\n" + "=" * 60)
    print("  Sync complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
