#!/usr/bin/env python3
"""
Sync local data to Azure Blob Storage using Python SDK.

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


def get_blob_service_client():
    """Create BlobServiceClient using account key."""
    from azure.storage.blob import BlobServiceClient

    connection_string = (
        f"DefaultEndpointsProtocol=https;"
        f"AccountName={STORAGE_ACCOUNT};"
        f"AccountKey={STORAGE_KEY};"
        f"EndpointSuffix=core.windows.net"
    )
    return BlobServiceClient.from_connection_string(connection_string)


def ensure_container_exists(blob_service_client):
    """Create blob container if it doesn't exist."""
    print(f"Checking blob container '{BLOB_CONTAINER}'...")

    try:
        container_client = blob_service_client.get_container_client(BLOB_CONTAINER)
        if not container_client.exists():
            container_client.create_container()
            print(f"Created blob container '{BLOB_CONTAINER}'")
        else:
            print(f"Blob container '{BLOB_CONTAINER}' ready")
    except Exception as e:
        print(f"Warning: Could not create/check container: {e}")


def get_existing_blobs(container_client, prefix: str) -> set:
    """Get set of existing blob names with given prefix."""
    existing = set()
    try:
        blobs = container_client.list_blobs(name_starts_with=prefix)
        for blob in blobs:
            existing.add(blob.name)
    except Exception:
        pass
    return existing


def sync_folder(blob_service_client, name: str, config: dict, dry_run: bool = False):
    """Sync a local folder to Azure Blob Storage."""
    local_path = Path(config['local'])
    remote_path = config['remote']
    pattern = config['pattern']

    if not local_path.exists():
        print(f"Skipping {name}: {local_path} does not exist")
        return

    # Get all local files
    files = list(local_path.glob(pattern))
    if not files:
        print(f"Skipping {name}: no files matching {pattern}")
        return

    container_client = blob_service_client.get_container_client(BLOB_CONTAINER)

    # Get existing blobs to avoid re-uploading
    existing_blobs = get_existing_blobs(container_client, remote_path)

    # Filter to only new files
    files_to_upload = []
    for f in files:
        # Construct blob name preserving subfolder structure
        relative_path = f.relative_to(local_path)
        blob_name = f"{remote_path}/{relative_path}"
        if blob_name not in existing_blobs:
            files_to_upload.append((f, blob_name))

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Syncing {name}:")
    print(f"  Local: {local_path} ({len(files)} total files)")
    print(f"  Remote: {BLOB_CONTAINER}/{remote_path}")
    print(f"  Existing: {len(existing_blobs)} blobs")
    print(f"  To upload: {len(files_to_upload)} new files")

    if dry_run:
        for f, blob_name in files_to_upload[:5]:
            print(f"    Would upload: {f.name} -> {blob_name}")
        if len(files_to_upload) > 5:
            print(f"    ... and {len(files_to_upload) - 5} more files")
        return

    if not files_to_upload:
        print(f"  All files already synced!")
        return

    # Upload new files
    uploaded = 0
    errors = 0
    for f, blob_name in files_to_upload:
        try:
            blob_client = container_client.get_blob_client(blob_name)
            with open(f, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)
            uploaded += 1
            if uploaded % 10 == 0:
                print(f"  Uploaded {uploaded}/{len(files_to_upload)}...")
        except Exception as e:
            errors += 1
            print(f"  Error uploading {f.name}: {e}")

    print(f"  Done! {uploaded} files uploaded, {errors} errors")


def get_storage_stats(blob_service_client):
    """Get stats about what's in Azure Blob Storage."""
    print("\n=== Azure Blob Storage Stats ===")

    try:
        container_client = blob_service_client.get_container_client(BLOB_CONTAINER)

        # Count blobs by prefix
        stats = {}
        total_size = 0

        for blob in container_client.list_blobs():
            prefix = blob.name.split('/')[0] if '/' in blob.name else 'root'
            if prefix not in stats:
                stats[prefix] = {'count': 0, 'size': 0}
            stats[prefix]['count'] += 1
            stats[prefix]['size'] += blob.size or 0
            total_size += blob.size or 0

        print(f"\nContainer: {BLOB_CONTAINER}")
        print(f"{'Prefix':<20} {'Count':>10} {'Size':>15}")
        print("-" * 50)
        for prefix, data in sorted(stats.items()):
            size_mb = data['size'] / 1024 / 1024
            print(f"{prefix:<20} {data['count']:>10} {size_mb:>12.2f} MB")
        print("-" * 50)
        print(f"{'Total':<20} {sum(d['count'] for d in stats.values()):>10} {total_size/1024/1024:>12.2f} MB")

    except Exception as e:
        print(f"Could not get stats: {e}")


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

    # Create blob service client
    try:
        blob_service_client = get_blob_service_client()
    except Exception as e:
        print(f"\nError connecting to Azure Storage: {e}")
        sys.exit(1)

    # Ensure container exists
    ensure_container_exists(blob_service_client)

    if args.stats:
        get_storage_stats(blob_service_client)
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
            sync_folder(blob_service_client, name, SYNC_PATHS[name], dry_run=args.dry_run)

    print("\n" + "=" * 60)
    print("  Sync complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
