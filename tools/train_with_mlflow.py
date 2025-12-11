#!/usr/bin/env python3
"""
Example: Local Training with Azure ML MLflow Tracking

This script demonstrates how to train locally while logging metrics
to Azure ML Workspace. No compute costs - only tracking/storage.

Usage:
    # Set environment variables (or use .env.dev)
    export AZURE_SUBSCRIPTION_ID=xxx
    export AZURE_RESOURCE_GROUP=rg-itb-dev
    export AZURE_ML_WORKSPACE=mlw-itb-dev

    # Run training
    python tools/train_with_mlflow.py --symbol BTCUSDT --freq 5m

Prerequisites:
    pip install azure-ai-ml azure-identity mlflow
    az login  # Authenticate with Azure
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment
load_dotenv('.env.dev')

from common.mlflow_tracking import MLflowTracker, TrainingMetrics


def get_azure_tracker(experiment_name: str) -> MLflowTracker:
    """Create tracker connected to Azure ML Workspace."""
    return MLflowTracker(
        experiment_name=experiment_name,
        azure_ml_workspace=os.getenv('AZURE_ML_WORKSPACE'),
        azure_resource_group=os.getenv('AZURE_RESOURCE_GROUP'),
        azure_subscription_id=os.getenv('AZURE_SUBSCRIPTION_ID'),
    )


def train_model_example(symbol: str, freq: str, strategy: str = "conservative"):
    """
    Example training function that logs to Azure ML.

    Replace this with your actual training logic.
    """
    print(f"\n{'='*60}")
    print(f"Training: {symbol} | {freq} | {strategy}")
    print(f"{'='*60}\n")

    # Create tracker connected to Azure ML
    tracker = get_azure_tracker(experiment_name=f"itb-{strategy}")

    if not tracker.is_available:
        print("ERROR: MLflow not available. Install with: pip install mlflow azure-ai-ml azure-identity")
        return None

    run_name = f"{symbol}_{freq}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    with tracker.start_run(run_name=run_name, tags={"symbol": symbol, "freq": freq, "strategy": strategy}):
        # Log parameters
        params = {
            "symbol": symbol,
            "freq": freq,
            "strategy": strategy,
            "model_type": "lightgbm",
            "n_estimators": 500,
            "learning_rate": 0.05,
            "max_depth": 6,
            "num_leaves": 31,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "label_horizon": 12,
        }
        tracker.log_params(params)
        print(f"Logged params: {list(params.keys())}")

        # Simulate training with epoch logging
        print("\nSimulating training epochs...")
        for epoch in range(1, 11):
            # In real training, these would be actual metrics
            epoch_metrics = {
                "train_loss": 0.5 - (epoch * 0.03) + (0.01 * (epoch % 3)),
                "val_loss": 0.55 - (epoch * 0.025) + (0.02 * (epoch % 4)),
                "train_auc": 0.7 + (epoch * 0.02),
                "val_auc": 0.68 + (epoch * 0.018),
            }
            tracker.log_metrics(epoch_metrics, step=epoch)
            print(f"  Epoch {epoch:2d}: val_auc={epoch_metrics['val_auc']:.4f}, val_loss={epoch_metrics['val_loss']:.4f}")

        # Log final metrics
        final_metrics = TrainingMetrics(
            auc=0.912,
            ap=0.156,
            f1=0.073,
            precision=0.981,
            recall=0.038,
            train_samples=50000,
            val_samples=10000,
            positive_ratio=0.02,
            n_features=150,
            n_estimators=500,
            best_iteration=423,
        )
        tracker.log_metrics(final_metrics)
        print(f"\nFinal metrics logged: auc={final_metrics.auc}, precision={final_metrics.precision}")

        # Log a config dict as artifact
        config_dict = {
            "training_config": params,
            "final_metrics": final_metrics.to_dict(),
            "timestamp": datetime.now().isoformat(),
        }
        tracker.log_dict(config_dict, "training_config.json")

        run_id = tracker.get_run_id()
        print(f"\n✓ Run completed: {run_id}")
        print(f"  View in Azure ML Studio:")
        print(f"  https://ml.azure.com/experiments/{tracker.experiment_name}/runs/{run_id}")

        return run_id


def list_experiments(strategy: str = "conservative"):
    """List recent runs from Azure ML."""
    tracker = get_azure_tracker(experiment_name=f"itb-{strategy}")

    if not tracker.is_available:
        print("MLflow not available")
        return

    print(f"\nRecent runs for itb-{strategy}:")
    print("-" * 80)

    runs = tracker.search_runs(max_results=10)

    if not runs:
        print("No runs found")
        return

    for run in runs:
        run_name = run.get('tags.mlflow.runName', 'unknown')
        auc = run.get('metrics.auc', 'N/A')
        precision = run.get('metrics.precision', 'N/A')
        start_time = run.get('start_time', 'N/A')
        print(f"  {run_name}: auc={auc}, precision={precision} ({start_time})")


def main():
    parser = argparse.ArgumentParser(description="Train with MLflow tracking to Azure ML")
    parser.add_argument("--symbol", default="BTCUSDT", help="Trading symbol")
    parser.add_argument("--freq", default="5m", help="Timeframe")
    parser.add_argument("--strategy", default="conservative", help="Strategy name")
    parser.add_argument("--list", action="store_true", help="List recent runs")

    args = parser.parse_args()

    # Check Azure config
    required_vars = ['AZURE_SUBSCRIPTION_ID', 'AZURE_RESOURCE_GROUP', 'AZURE_ML_WORKSPACE']
    missing = [v for v in required_vars if not os.getenv(v)]

    if missing:
        print(f"ERROR: Missing environment variables: {missing}")
        print("Set them in .env.dev or export them")
        sys.exit(1)

    print(f"Azure ML Workspace: {os.getenv('AZURE_ML_WORKSPACE')}")
    print(f"Resource Group: {os.getenv('AZURE_RESOURCE_GROUP')}")

    if args.list:
        list_experiments(args.strategy)
    else:
        train_model_example(args.symbol, args.freq, args.strategy)


if __name__ == "__main__":
    main()
