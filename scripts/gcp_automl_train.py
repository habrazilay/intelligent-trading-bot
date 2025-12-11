#!/usr/bin/env python3
"""
GCP AutoML Training Script

Uploads ITB data to Google Cloud and runs Vertex AI AutoML to automatically
find the best model, features, and hyperparameters.

Expected cost: $30-100 depending on budget setting
Expected time: 2-6 hours
Expected improvement: +2-5% win rate vs manual LGBM

Prerequisites:
    pip install google-cloud-aiplatform google-cloud-bigquery pandas

Setup:
    gcloud auth login
    gcloud config set project YOUR_PROJECT_ID

Usage:
    # After order flow test succeeds (win rate ≥53%)
    python scripts/gcp_automl_train.py --config configs/btcusdt_5m_orderflow.jsonc --budget 50

    # For daily swing trading
    python scripts/gcp_automl_train.py --config configs/btcusdt_daily.jsonc --budget 100
"""

import argparse
import sys
import os
from pathlib import Path
import pandas as pd
from datetime import datetime

try:
    from google.cloud import aiplatform
    from google.cloud import bigquery
    HAS_GCP = True
except ImportError:
    HAS_GCP = False
    print("⚠️  Google Cloud libraries not installed")
    print("Run: pip install google-cloud-aiplatform google-cloud-bigquery")

# Import ITB utilities
sys.path.insert(0, str(Path(__file__).parent.parent))
from service.App import load_config, App


def check_gcp_setup():
    """Verify GCP is configured correctly"""
    print("\n🔍 Checking GCP setup...")

    # Check gcloud is installed
    if os.system("which gcloud > /dev/null 2>&1") != 0:
        print("❌ gcloud CLI not installed")
        print("Install: https://cloud.google.com/sdk/docs/install")
        return False

    # Check authentication
    result = os.popen("gcloud auth list --filter=status:ACTIVE --format='value(account)'").read().strip()
    if not result:
        print("❌ Not authenticated")
        print("Run: gcloud auth login")
        return False

    print(f"✅ Authenticated as: {result}")

    # Check project is set
    project = os.popen("gcloud config get-value project").read().strip()
    if not project or project == "(unset)":
        print("❌ No project set")
        print("Run: gcloud config set project YOUR_PROJECT_ID")
        return False

    print(f"✅ Project: {project}")

    # Check billing
    print("\n💰 Checking billing and credits...")
    print("   Go to: https://console.cloud.google.com/billing")
    print("   Verify you have credits remaining")

    return True


def load_itb_data(config_file):
    """Load merged ITB data (features + labels)"""
    print(f"\n📊 Loading ITB data from config: {config_file}")

    load_config(config_file)

    data_folder = Path(App.config.get('data_folder', './DATA_ITB_5m'))

    # Look for merged predictions file (has features + labels)
    predictions_file = data_folder / 'predictions.csv'
    if not predictions_file.exists():
        predictions_file = data_folder / 'predictions_orderflow.csv'

    if not predictions_file.exists():
        raise FileNotFoundError(
            f"No predictions file found in {data_folder}\n"
            f"Run the ITB pipeline first:\n"
            f"  python scripts/features_new.py -c {config_file}\n"
            f"  python scripts/labels_new.py -c {config_file}\n"
            f"  python scripts/merge_new.py -c {config_file}\n"
            f"  python scripts/train.py -c {config_file}"
        )

    print(f"   Loading: {predictions_file}")
    df = pd.read_csv(predictions_file)

    print(f"   Rows: {len(df):,}")
    print(f"   Columns: {len(df.columns)}")
    print(f"   Date range: {df['timestamp'].min()} → {df['timestamp'].max()}")

    return df


def upload_to_bigquery(df, project_id, dataset_name='itb_trading', table_name='training_data'):
    """Upload DataFrame to BigQuery"""
    print(f"\n☁️  Uploading to BigQuery...")

    client = bigquery.Client(project=project_id)

    # Create dataset if doesn't exist
    dataset_id = f"{project_id}.{dataset_name}"
    try:
        client.get_dataset(dataset_id)
        print(f"   Dataset {dataset_name} already exists")
    except Exception:
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = "US"
        client.create_dataset(dataset)
        print(f"   Created dataset: {dataset_name}")

    # Upload table
    table_id = f"{dataset_id}.{table_name}"

    print(f"   Uploading {len(df)} rows to {table_id}...")
    job = client.load_table_from_dataframe(df, table_id)
    job.result()  # Wait for completion

    table = client.get_table(table_id)
    print(f"   ✅ Uploaded {table.num_rows:,} rows")

    return table_id


def run_automl_forecast(project_id, region, dataset_table_id, target_column, budget_hours=1):
    """
    Run Vertex AI AutoML Forecasting

    AutoML will automatically:
    - Engineer features
    - Select best model (LGBM, XGBoost, Neural Networks)
    - Tune hyperparameters
    - Evaluate performance

    Args:
        project_id: GCP project ID
        region: GCP region (e.g., 'us-central1')
        dataset_table_id: BigQuery table ID
        target_column: Column to predict (e.g., 'high_040_4')
        budget_hours: Training budget (1-72 hours)
                     More hours = better model but higher cost
                     1h ≈ $3-5, 3h ≈ $10-15, 6h ≈ $20-30
    """
    print(f"\n🤖 Running Vertex AI AutoML...")
    print(f"   Budget: {budget_hours} hours ≈ ${budget_hours * 3}-${budget_hours * 5}")
    print(f"   Target: {target_column}")

    aiplatform.init(project=project_id, location=region)

    # Create dataset
    print("\n   Creating Vertex AI dataset...")
    dataset = aiplatform.TabularDataset.create(
        display_name=f"itb_trading_{datetime.now().strftime('%Y%m%d_%H%M')}",
        bq_source=f"bq://{dataset_table_id}",
    )

    print(f"   Dataset created: {dataset.display_name}")

    # Start training job
    print(f"\n   Starting AutoML training (this will take {budget_hours}+ hours)...")
    print("   You can close this script - training runs in the cloud")
    print("   Monitor at: https://console.cloud.google.com/vertex-ai/training")

    job = aiplatform.AutoMLForecastingTrainingJob(
        display_name=f"itb_automl_{datetime.now().strftime('%Y%m%d_%H%M')}",
        optimization_objective="minimize-rmse",  # For regression
        # For classification, use: "maximize-au-roc"
    )

    model = job.run(
        dataset=dataset,
        target_column=target_column,
        time_column="timestamp",
        time_series_identifier_column="symbol",  # If you have multiple symbols
        unavailable_at_forecast_columns=[target_column],  # Don't use future data
        budget_milli_node_hours=budget_hours * 1000,  # Convert to milli-node-hours
        model_display_name=f"itb_model_{datetime.now().strftime('%Y%m%d_%H%M')}",
    )

    print(f"\n✅ Training complete!")
    print(f"   Model: {model.display_name}")
    print(f"   Resource name: {model.resource_name}")

    # Get evaluation metrics
    print(f"\n📊 Evaluation Metrics:")
    evaluations = model.list_model_evaluations()
    for evaluation in evaluations:
        print(f"   {evaluation.metrics}")

    return model


def estimate_cost(budget_hours, strategy='orderflow'):
    """Estimate total cost for AutoML training"""
    # AutoML pricing (approximate):
    # - Training: $3-5 per node hour
    # - Prediction: $0.05 per 1000 predictions
    # - Storage: $0.02/GB/month

    training_cost_low = budget_hours * 3
    training_cost_high = budget_hours * 5
    storage_cost = 0.50  # ~25GB data

    total_low = training_cost_low + storage_cost
    total_high = training_cost_high + storage_cost

    print(f"\n💰 Estimated Cost:")
    print(f"   Training: ${training_cost_low}-${training_cost_high} ({budget_hours}h × $3-5/h)")
    print(f"   Storage: ${storage_cost}")
    print(f"   Total: ${total_low}-${total_high}")
    print(f"\n   Your GCP credits: ~$270")
    print(f"   Remaining after: ~${270 - total_high} - ${270 - total_low}")


def main():
    parser = argparse.ArgumentParser(
        description='Train trading model using GCP Vertex AI AutoML',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run AutoML on order flow data (1h budget)
  python scripts/gcp_automl_train.py -c configs/btcusdt_5m_orderflow.jsonc --budget 1

  # Run AutoML on daily data (3h budget for better results)
  python scripts/gcp_automl_train.py -c configs/btcusdt_daily.jsonc --budget 3

  # High budget for maximum accuracy (6h)
  python scripts/gcp_automl_train.py -c configs/btcusdt_5m_orderflow.jsonc --budget 6

Cost guide:
  1h = $3-5 (quick test)
  3h = $10-15 (good results)
  6h = $20-30 (best results)
        """
    )

    parser.add_argument(
        '--config', '-c',
        required=True,
        help='ITB config file (must have already run train.py)'
    )

    parser.add_argument(
        '--budget',
        type=int,
        default=1,
        help='Training budget in hours (1-72, default: 1)'
    )

    parser.add_argument(
        '--project',
        help='GCP project ID (default: from gcloud config)'
    )

    parser.add_argument(
        '--region',
        default='us-central1',
        help='GCP region (default: us-central1)'
    )

    parser.add_argument(
        '--target',
        default='high_040_4',
        help='Target column to predict (default: high_040_4)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show cost estimate and exit (don\'t actually train)'
    )

    args = parser.parse_args()

    # Check prerequisites
    if not HAS_GCP:
        sys.exit(1)

    if not check_gcp_setup():
        sys.exit(1)

    # Get project ID
    project_id = args.project or os.popen("gcloud config get-value project").read().strip()

    # Show cost estimate
    estimate_cost(args.budget)

    if args.dry_run:
        print("\n✅ Dry run complete (no charges)")
        return

    # Confirm with user
    print(f"\n⚠️  This will cost approximately ${args.budget * 3}-${args.budget * 5}")
    response = input("Continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Cancelled")
        return

    # Load ITB data
    df = load_itb_data(args.config)

    # Upload to BigQuery
    table_id = upload_to_bigquery(df, project_id)

    # Run AutoML
    model = run_automl_forecast(
        project_id=project_id,
        region=args.region,
        dataset_table_id=table_id,
        target_column=args.target,
        budget_hours=args.budget
    )

    print(f"\n✅ AutoML training complete!")
    print(f"\nNext steps:")
    print(f"1. Review metrics in GCP console")
    print(f"2. Compare with local LGBM baseline")
    print(f"3. If better, use for predictions")
    print(f"4. If worse, try different budget or features")

    print(f"\nModel resource name (save this!):")
    print(f"{model.resource_name}")


if __name__ == '__main__':
    main()
