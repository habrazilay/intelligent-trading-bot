#!/usr/bin/env python3
"""
Upload ITB Data to Google BigQuery

Uploads local training data (features + labels) to BigQuery for cloud ML training.

This allows you to:
1. Train models on GCP WHILE waiting for orderbook collection
2. Use AutoML on existing 4 years of data
3. Compare cloud vs local results

Usage:
    # Upload 5m data
    python scripts/upload_to_bigquery.py -c configs/btcusdt_5m_aggressive.jsonc

    # Upload 1m data
    python scripts/upload_to_bigquery.py -c configs/btcusdt_1m_aggressive.jsonc

    # Upload with custom dataset name
    python scripts/upload_to_bigquery.py -c configs/btcusdt_5m_aggressive.jsonc --dataset itb_5m
"""

import argparse
import sys
from pathlib import Path
import pandas as pd

try:
    from google.cloud import bigquery
    HAS_BIGQUERY = True
except ImportError:
    HAS_BIGQUERY = False

# Import ITB utilities
sys.path.insert(0, str(Path(__file__).parent.parent))
from service.App import load_config, App


def upload_to_bigquery(config_file, dataset_name=None, project_id=None):
    """
    Upload ITB data to BigQuery

    Args:
        config_file: Path to ITB config
        dataset_name: BigQuery dataset name (default: itb_trading)
        project_id: GCP project ID (default: from gcloud config)
    """
    print("\n🚀 Uploading ITB Data to BigQuery")
    print("="*60)

    if not HAS_BIGQUERY:
        print("❌ google-cloud-bigquery not installed")
        print("Run: pip install google-cloud-bigquery")
        return False

    # Load config
    load_config(config_file)
    data_folder = Path(App.config.get('data_folder', './DATA_ITB_5m'))
    symbol = App.config.get('symbol', 'BTCUSDT')
    freq = App.config.get('freq', '5m')

    print(f"Config: {config_file}")
    print(f"Data folder: {data_folder}")
    print(f"Symbol: {symbol}")
    print(f"Frequency: {freq}")

    # Find merged data
    merged_file = data_folder / 'merged_data.csv'
    if not merged_file.exists():
        # Try predictions file
        merged_file = data_folder / 'predictions.csv'

    if not merged_file.exists():
        print(f"\n❌ No data found in {data_folder}/")
        print("Run the pipeline first:")
        print(f"  python scripts/features_new.py -c {config_file}")
        print(f"  python scripts/labels_new.py -c {config_file}")
        print(f"  python scripts/merge_new.py -c {config_file}")
        return False

    print(f"\n📊 Loading data from: {merged_file}")
    df = pd.read_csv(merged_file)

    print(f"   Rows: {len(df):,}")
    print(f"   Columns: {len(df.columns)}")

    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        print(f"   Date range: {df['timestamp'].min()} → {df['timestamp'].max()}")

    # Estimate size
    memory_mb = df.memory_usage(deep=True).sum() / 1024 / 1024
    print(f"   Estimated size: {memory_mb:.2f} MB")

    # Get project ID
    if not project_id:
        import subprocess
        result = subprocess.run(
            ['gcloud', 'config', 'get-value', 'project'],
            capture_output=True, text=True
        )
        project_id = result.stdout.strip()

    if not project_id or project_id == '(unset)':
        print("\n❌ No GCP project set")
        print("Run: gcloud config set project PROJECT_ID")
        return False

    print(f"\n☁️  GCP Project: {project_id}")

    # Initialize BigQuery client
    client = bigquery.Client(project=project_id)

    # Create dataset if doesn't exist
    if not dataset_name:
        dataset_name = f"itb_{freq.replace('m', 'min').replace('h', 'hour')}"

    dataset_id = f"{project_id}.{dataset_name}"

    try:
        client.get_dataset(dataset_id)
        print(f"   Dataset '{dataset_name}' already exists")
    except Exception:
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = "US"
        client.create_dataset(dataset)
        print(f"   Created dataset: {dataset_name}")

    # Create table
    table_name = f"{symbol.lower()}_{freq}"
    table_id = f"{dataset_id}.{table_name}"

    print(f"\n📤 Uploading to: {table_id}")
    print(f"   This may take 1-5 minutes...")

    # Upload
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",  # Overwrite existing data
    )

    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()  # Wait for completion

    # Verify
    table = client.get_table(table_id)

    print(f"\n✅ Upload complete!")
    print(f"   Table: {table_id}")
    print(f"   Rows: {table.num_rows:,}")
    print(f"   Size: {table.num_bytes / 1024 / 1024:.2f} MB")

    # Show how to query
    print(f"\n📋 Query Example:")
    print(f"   SELECT * FROM `{table_id}` LIMIT 10")

    # Estimate cost
    print(f"\n💰 Estimated Storage Cost:")
    print(f"   ${table.num_bytes / 1024 / 1024 / 1024 * 0.02:.4f}/month")
    print(f"   (BigQuery: $0.02/GB/month)")

    return True


def main():
    parser = argparse.ArgumentParser(
        description='Upload ITB data to Google BigQuery',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload 5m data
  python scripts/upload_to_bigquery.py -c configs/btcusdt_5m_aggressive.jsonc

  # Upload 1m data
  python scripts/upload_to_bigquery.py -c configs/btcusdt_1m_aggressive.jsonc

  # Custom dataset name
  python scripts/upload_to_bigquery.py -c configs/btcusdt_5m_aggressive.jsonc --dataset my_dataset

After upload, you can:
  1. Run AutoML: python scripts/gcp_automl_train.py -c <config> --budget 1
  2. Query in BigQuery console
  3. Use for other GCP services
        """
    )

    parser.add_argument(
        '--config', '-c',
        required=True,
        help='ITB config file'
    )

    parser.add_argument(
        '--dataset',
        help='BigQuery dataset name (default: itb_5min, itb_1min, etc)'
    )

    parser.add_argument(
        '--project',
        help='GCP project ID (default: from gcloud config)'
    )

    args = parser.parse_args()

    success = upload_to_bigquery(args.config, args.dataset, args.project)

    if success:
        print("\n🎉 Next Steps:")
        print("1. Run AutoML on this data:")
        print(f"   python scripts/gcp_automl_train.py -c {args.config} --budget 1")
        print("")
        print("2. Monitor costs:")
        print("   python scripts/cloud_cost_monitor.py")
        print("")
        print("3. View data in BigQuery console:")
        print("   https://console.cloud.google.com/bigquery")
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
