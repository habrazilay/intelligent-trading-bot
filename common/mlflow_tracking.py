"""
MLflow Tracking Module for ITB

Provides experiment tracking, model versioning, and metrics logging.
Can work with:
- Local MLflow (file-based tracking)
- Azure ML Workspace (cloud-based tracking)
- MLflow Tracking Server (remote)

Usage:
    from common.mlflow_tracking import MLflowTracker

    tracker = MLflowTracker(experiment_name="itb-training")
    with tracker.start_run(run_name="BTCUSDT_conservative_5m"):
        tracker.log_params({"symbol": "BTCUSDT", "strategy": "conservative"})
        tracker.log_metrics({"auc": 0.912, "precision": 0.981})
        tracker.log_model(model, "lgbm_high_06_24")
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict

# MLflow is optional - gracefully degrade if not installed
try:
    import mlflow
    from mlflow.tracking import MlflowClient
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    mlflow = None
    MlflowClient = None

# Azure ML is optional
try:
    from azure.ai.ml import MLClient
    from azure.identity import DefaultAzureCredential
    AZUREML_AVAILABLE = True
except ImportError:
    AZUREML_AVAILABLE = False
    MLClient = None


@dataclass
class TrainingMetrics:
    """Standard metrics for a training run."""
    # Model quality
    auc: float = 0.0
    ap: float = 0.0  # Average Precision
    f1: float = 0.0
    precision: float = 0.0
    recall: float = 0.0

    # Training metadata
    train_samples: int = 0
    val_samples: int = 0
    positive_ratio: float = 0.0

    # Model info
    n_features: int = 0
    n_estimators: int = 0
    best_iteration: int = 0

    def to_dict(self) -> Dict[str, float]:
        return {k: v for k, v in asdict(self).items() if v != 0}


@dataclass
class ExperimentConfig:
    """Configuration for an experiment."""
    symbol: str
    strategy: str
    freq: str
    label_horizon: int
    train_features: List[str]
    labels: List[str]
    train_length: int = 0
    config_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Convert lists to strings for MLflow params
        d['train_features'] = ','.join(self.train_features[:10])  # First 10
        d['labels'] = ','.join(self.labels)
        d['n_features'] = len(self.train_features)
        return d


class MLflowTracker:
    """
    MLflow tracking wrapper with Azure ML support.

    Supports three modes:
    1. Local tracking (default) - stores in ./mlruns
    2. Azure ML tracking - stores in Azure ML Workspace
    3. Remote server - stores in MLflow Tracking Server
    """

    def __init__(
        self,
        experiment_name: str = "itb-training",
        tracking_uri: Optional[str] = None,
        azure_ml_workspace: Optional[str] = None,
        azure_resource_group: Optional[str] = None,
        azure_subscription_id: Optional[str] = None,
    ):
        """
        Initialize MLflow tracker.

        Args:
            experiment_name: Name of the experiment
            tracking_uri: MLflow tracking URI (file:// or http://)
            azure_ml_workspace: Azure ML workspace name (enables Azure ML tracking)
            azure_resource_group: Azure resource group
            azure_subscription_id: Azure subscription ID
        """
        self.experiment_name = experiment_name
        self.tracking_uri = tracking_uri
        self.azure_config = {
            'workspace': azure_ml_workspace,
            'resource_group': azure_resource_group,
            'subscription_id': azure_subscription_id,
        }
        self._run = None
        self._client = None
        self._initialized = False

        if not MLFLOW_AVAILABLE:
            print("Warning: MLflow not installed. Tracking disabled.")
            print("Install with: pip install mlflow")
            return

        self._initialize()

    def _initialize(self):
        """Initialize MLflow tracking."""
        if not MLFLOW_AVAILABLE:
            return

        # Check for Azure ML configuration
        if self.azure_config['workspace'] and AZUREML_AVAILABLE:
            self._init_azure_ml()
        elif self.tracking_uri:
            mlflow.set_tracking_uri(self.tracking_uri)
        else:
            # Default: local file tracking
            mlruns_path = Path("mlruns").absolute()
            mlflow.set_tracking_uri(f"file://{mlruns_path}")

        # Set or create experiment
        mlflow.set_experiment(self.experiment_name)
        self._client = MlflowClient()
        self._initialized = True

        print(f"MLflow initialized: {mlflow.get_tracking_uri()}")
        print(f"Experiment: {self.experiment_name}")

    def _init_azure_ml(self):
        """Initialize Azure ML workspace as MLflow backend."""
        if not AZUREML_AVAILABLE:
            print("Warning: azure-ai-ml not installed. Using local tracking.")
            return

        try:
            credential = DefaultAzureCredential()
            ml_client = MLClient(
                credential=credential,
                subscription_id=self.azure_config['subscription_id'],
                resource_group_name=self.azure_config['resource_group'],
                workspace_name=self.azure_config['workspace'],
            )

            # Get MLflow tracking URI from Azure ML
            tracking_uri = ml_client.workspaces.get(
                self.azure_config['workspace']
            ).mlflow_tracking_uri

            mlflow.set_tracking_uri(tracking_uri)
            print(f"Connected to Azure ML workspace: {self.azure_config['workspace']}")

        except Exception as e:
            print(f"Warning: Could not connect to Azure ML: {e}")
            print("Falling back to local tracking.")

    @property
    def is_available(self) -> bool:
        """Check if MLflow tracking is available."""
        return MLFLOW_AVAILABLE and self._initialized

    def start_run(
        self,
        run_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        nested: bool = False,
    ):
        """
        Start a new MLflow run.

        Args:
            run_name: Name for the run (e.g., "BTCUSDT_conservative_5m")
            tags: Additional tags for the run
            nested: Whether this is a nested run

        Returns:
            Self for context manager usage
        """
        if not self.is_available:
            return self

        if run_name is None:
            run_name = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        default_tags = {
            "framework": "lightgbm",
            "project": "intelligent-trading-bot",
        }
        if tags:
            default_tags.update(tags)

        self._run = mlflow.start_run(run_name=run_name, tags=default_tags, nested=nested)
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_run()
        return False

    def end_run(self):
        """End the current run."""
        if self.is_available and self._run:
            mlflow.end_run()
            self._run = None

    def log_params(self, params: Dict[str, Any]):
        """Log parameters."""
        if not self.is_available:
            return

        # MLflow params must be strings
        clean_params = {}
        for k, v in params.items():
            if isinstance(v, (list, dict)):
                clean_params[k] = json.dumps(v)[:250]  # MLflow has 250 char limit
            else:
                clean_params[k] = str(v)[:250]

        mlflow.log_params(clean_params)

    def log_param(self, key: str, value: Any):
        """Log a single parameter."""
        self.log_params({key: value})

    def log_metrics(self, metrics: Union[Dict[str, float], TrainingMetrics], step: Optional[int] = None):
        """Log metrics."""
        if not self.is_available:
            return

        if isinstance(metrics, TrainingMetrics):
            metrics = metrics.to_dict()

        mlflow.log_metrics(metrics, step=step)

    def log_metric(self, key: str, value: float, step: Optional[int] = None):
        """Log a single metric."""
        if not self.is_available:
            return
        mlflow.log_metric(key, value, step=step)

    def log_config(self, config: ExperimentConfig):
        """Log experiment configuration."""
        if not self.is_available:
            return
        self.log_params(config.to_dict())

    def log_model(
        self,
        model: Any,
        artifact_path: str,
        model_type: str = "lightgbm",
        registered_model_name: Optional[str] = None,
    ):
        """
        Log a trained model.

        Args:
            model: The trained model object
            artifact_path: Path within the run to store the model
            model_type: Type of model (lightgbm, sklearn, keras)
            registered_model_name: If provided, register the model
        """
        if not self.is_available:
            return

        try:
            if model_type == "lightgbm":
                mlflow.lightgbm.log_model(
                    model,
                    artifact_path,
                    registered_model_name=registered_model_name,
                )
            elif model_type == "sklearn":
                mlflow.sklearn.log_model(
                    model,
                    artifact_path,
                    registered_model_name=registered_model_name,
                )
            elif model_type == "keras":
                mlflow.keras.log_model(
                    model,
                    artifact_path,
                    registered_model_name=registered_model_name,
                )
            else:
                # Generic pickling
                mlflow.pyfunc.log_model(
                    artifact_path,
                    python_model=model,
                    registered_model_name=registered_model_name,
                )
        except Exception as e:
            print(f"Warning: Could not log model: {e}")

    def log_artifact(self, local_path: str, artifact_path: Optional[str] = None):
        """Log an artifact file."""
        if not self.is_available:
            return

        mlflow.log_artifact(local_path, artifact_path)

    def log_artifacts(self, local_dir: str, artifact_path: Optional[str] = None):
        """Log a directory of artifacts."""
        if not self.is_available:
            return

        mlflow.log_artifacts(local_dir, artifact_path)

    def log_figure(self, figure, artifact_file: str):
        """Log a matplotlib figure."""
        if not self.is_available:
            return

        mlflow.log_figure(figure, artifact_file)

    def log_dict(self, dictionary: Dict, artifact_file: str):
        """Log a dictionary as JSON artifact."""
        if not self.is_available:
            return

        mlflow.log_dict(dictionary, artifact_file)

    def set_tag(self, key: str, value: str):
        """Set a tag on the current run."""
        if not self.is_available:
            return

        mlflow.set_tag(key, value)

    def set_tags(self, tags: Dict[str, str]):
        """Set multiple tags."""
        if not self.is_available:
            return

        mlflow.set_tags(tags)

    def get_run_id(self) -> Optional[str]:
        """Get current run ID."""
        if self._run:
            return self._run.info.run_id
        return None

    def get_experiment_id(self) -> Optional[str]:
        """Get current experiment ID."""
        if self.is_available:
            exp = mlflow.get_experiment_by_name(self.experiment_name)
            if exp:
                return exp.experiment_id
        return None

    def search_runs(
        self,
        filter_string: str = "",
        max_results: int = 100,
        order_by: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Search for runs in the experiment.

        Args:
            filter_string: MLflow filter string (e.g., "metrics.auc > 0.8")
            max_results: Maximum number of results
            order_by: List of columns to order by (e.g., ["metrics.auc DESC"])

        Returns:
            List of run dictionaries
        """
        if not self.is_available:
            return []

        experiment = mlflow.get_experiment_by_name(self.experiment_name)
        if not experiment:
            return []

        runs = mlflow.search_runs(
            experiment_ids=[experiment.experiment_id],
            filter_string=filter_string,
            max_results=max_results,
            order_by=order_by or ["start_time DESC"],
        )

        return runs.to_dict('records')

    def get_best_run(self, metric: str = "auc", maximize: bool = True) -> Optional[Dict]:
        """Get the best run based on a metric."""
        order = "DESC" if maximize else "ASC"
        runs = self.search_runs(
            max_results=1,
            order_by=[f"metrics.{metric} {order}"],
        )
        return runs[0] if runs else None

    def compare_runs(
        self,
        run_ids: List[str],
        metrics: List[str] = None,
    ) -> Dict[str, Dict]:
        """
        Compare multiple runs.

        Args:
            run_ids: List of run IDs to compare
            metrics: List of metrics to compare

        Returns:
            Dictionary mapping run_id to metrics
        """
        if not self.is_available:
            return {}

        if metrics is None:
            metrics = ["auc", "precision", "recall", "f1"]

        results = {}
        for run_id in run_ids:
            run = mlflow.get_run(run_id)
            results[run_id] = {
                "name": run.info.run_name,
                "metrics": {m: run.data.metrics.get(m) for m in metrics},
                "params": run.data.params,
            }

        return results


# Global tracker instance (lazy initialization)
_global_tracker: Optional[MLflowTracker] = None


def get_tracker(
    experiment_name: str = "itb-training",
    **kwargs,
) -> MLflowTracker:
    """Get or create global tracker instance."""
    global _global_tracker

    if _global_tracker is None or _global_tracker.experiment_name != experiment_name:
        _global_tracker = MLflowTracker(experiment_name=experiment_name, **kwargs)

    return _global_tracker


def log_training_run(
    symbol: str,
    strategy: str,
    freq: str,
    model_name: str,
    metrics: Dict[str, float],
    params: Dict[str, Any],
    model: Any = None,
    artifacts_dir: Optional[str] = None,
) -> Optional[str]:
    """
    Convenience function to log a complete training run.

    Args:
        symbol: Trading symbol (e.g., BTCUSDT)
        strategy: Strategy name (e.g., conservative)
        freq: Timeframe (e.g., 5m)
        model_name: Model identifier (e.g., lgbm_high_06_24)
        metrics: Dictionary of metrics
        params: Dictionary of parameters
        model: Trained model object (optional)
        artifacts_dir: Directory with artifacts to log (optional)

    Returns:
        Run ID if successful, None otherwise
    """
    tracker = get_tracker(experiment_name=f"itb-{strategy}")

    run_name = f"{symbol}_{freq}_{model_name}"

    with tracker.start_run(run_name=run_name, tags={"symbol": symbol, "freq": freq}):
        # Log params
        tracker.log_params({
            "symbol": symbol,
            "strategy": strategy,
            "freq": freq,
            "model_name": model_name,
            **params,
        })

        # Log metrics
        tracker.log_metrics(metrics)

        # Log model if provided
        if model is not None:
            tracker.log_model(model, artifact_path=model_name)

        # Log artifacts if provided
        if artifacts_dir and Path(artifacts_dir).exists():
            tracker.log_artifacts(artifacts_dir)

        return tracker.get_run_id()


if __name__ == "__main__":
    # Test MLflow tracking
    print("Testing MLflow tracking...")

    tracker = MLflowTracker(experiment_name="itb-test")

    if tracker.is_available:
        with tracker.start_run(run_name="test_run"):
            tracker.log_params({
                "symbol": "BTCUSDT",
                "strategy": "conservative",
                "freq": "5m",
            })
            tracker.log_metrics({
                "auc": 0.912,
                "precision": 0.981,
                "recall": 0.038,
            })
            print(f"Run ID: {tracker.get_run_id()}")

        print("Test completed successfully!")
    else:
        print("MLflow not available - install with: pip install mlflow")
