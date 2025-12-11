#!/usr/bin/env python3
"""
Sync local data to Azure Storage Account.

Uploads:
- Orderbook data (DATA_ORDERBOOK/)
- Trade logs (logs/trades/)
- Position snapshots
- Training data (DATA_ITB_*)

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
CONTAINER_NAME = 'itb-data'
RESOURCE_GROUP = os.getenv('AZURE_RESOURCE_GROUP', 'rg-itb-dev')

# Local paths to sync
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
    """Create container if it doesn't exist."""
    print(f"Checking container '{CONTAINER_NAME}'...")

    cmd = [
        'az', 'storage', 'container', 'create',
        '--name', CONTAINER_NAME,
        '--account-name', STORAGE_ACCOUNT,
        '--auth-mode', 'login',
        '--only-show-errors'
    ]

    success, output = run_az_command(cmd)
    if not success:
        print(f"Warning: Could not create/check container: {output}")
    else:
        print(f"Container '{CONTAINER_NAME}' ready")


def sync_folder(name: str, config: dict, dry_run: bool = False):
    """Sync a local folder to Azure Storage."""
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
    print(f"  Remote: {CONTAINER_NAME}/{remote_path}")

    if dry_run:
        for f in files[:5]:
            print(f"    Would upload: {f.name}")
        if len(files) > 5:
            print(f"    ... and {len(files) - 5} more files")
        return

    # Use azcopy for efficient sync (or az storage blob upload-batch)
    cmd = [
        'az', 'storage', 'blob', 'upload-batch',
        '--source', str(local_path),
        '--destination', CONTAINER_NAME,
        '--destination-path', remote_path,
        '--account-name', STORAGE_ACCOUNT,
        '--auth-mode', 'login',
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
    """Get stats about what's in Azure Storage."""
    print("\n=== Azure Storage Stats ===")

    cmd = [
        'az', 'storage', 'blob', 'list',
        '--container-name', CONTAINER_NAME,
        '--account-name', STORAGE_ACCOUNT,
        '--auth-mode', 'login',
        '--query', '[].{name: name, size: properties.contentLength}',
        '--output', 'table'
    ]

    success, output = run_az_command(cmd)
    if success:
        print(output)
    else:
        print(f"Could not get stats: {output}")


def main():
    parser = argparse.ArgumentParser(description='Sync data to Azure Storage')
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
    print(f"  Azure Storage Sync - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Storage Account: {STORAGE_ACCOUNT}")
    print(f"  Container: {CONTAINER_NAME}")
    print("=" * 60)

    # Check Azure CLI login
    print("\nChecking Azure CLI login...")
    success, _ = run_az_command(['az', 'account', 'show', '--query', 'name', '-o', 'tsv'])
    if not success:
        print("Error: Not logged in to Azure CLI. Run 'az login' first.")
        sys.exit(1)
    print("Azure CLI authenticated")

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
