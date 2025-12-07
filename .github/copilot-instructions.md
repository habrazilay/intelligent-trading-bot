# Intelligent Trading Bot - Copilot Instructions

## Architecture Overview

This is a machine learning trading system with **offline (batch) and online (streaming) modes** that must guarantee feature consistency across both:

- **Offline Pipeline**: `scripts/download_* → merge → features → labels → train → predict → signals → output`
- **Online Service**: `service/server.py` runs continuous analysis loop with `inputs/*` (data collectors) and `outputs/*` (traders/notifiers)
- **Core Logic**: `common/` contains shared feature generators, label generators, classifiers, and model storage

### Key Design Principle
Features generated offline during training MUST match features generated online during predictions. This is enforced through:
- Centralized feature definitions in `common/gen_features.py` (talib, custom generators)
- Shared feature/label generator functions used by both `scripts/train.py` and `service/server.py`
- Configuration file (`configs/*.jsonc`) defines the exact feature set for a symbol+frequency

## Critical Concepts

### Configuration System
- **Single source of truth**: JSONC config files in `configs/` (e.g., `btcusdt_1m_dev.jsonc`)
- **Structure**: symbol, frequency, data sources, feature_sets, label_sets, algorithms, trade parameters
- **Loaded via**: `App.load_config(config_file)` in `service/App.py` (supports `//` comments)
- **Priority**: Config file > environment variables (`.env` for API keys)
- **Usage**: All scripts (`scripts/train.py`, `scripts/features_new.py`, etc.) take `-c config.json`

### Multi-Venue Support
- `common/types.py` defines `Venue` enum (BINANCE, MT5, YAHOO)
- `inputs/` and `outputs/` have venue-specific implementations (e.g., `collector_binance.py` vs `collector_mt5.py`)
- Use `get_collector_functions(venue)` and `get_trader_functions(venue)` to dynamically load implementations
- Never hardcode venue-specific logic—use the factory pattern

### Feature Generation (Offline & Online)
- **Generator types**: talib, custom Python functions, rolling aggregations
- **Config-driven**: Feature sets defined in `feature_sets` array in JSONC config
- **Example**: `{"generator":"talib", "config":{"columns":["close"], "functions":["SMA"], "windows":[5,10,20]}}`
- **Custom features**: Point to Python module (`"generator":"common.my_feature_example:my_feature_example"`)
- **Rolling aggregation**: Use `gen_features_rolling_agg.py` for time-windowed computations
- **Column naming convention**: `<label>_<input_data>_<algorithm>` (e.g., `high_15_k_nn`)

### Label Generation
- **Generators**: `gen_labels_highlow.py`, `gen_labels_topbot.py` in `common/`
- **Config-driven**: Labels defined in `label_sets` array
- **Labeling horizon**: Minimum look-ahead window (e.g., 120 minutes) to avoid leakage
- **Backtesting challenge**: Labels require periodic re-training due to time-based nature

### Model Training & Prediction
- **Classifiers**: `common/classifiers.py` supports LightGBM (gb), neural networks (nn), logistic regression (lc)
- **Model storage**: `common/model_store.py` handles model persistence and loading
- **Workflow**: Features → Labels → Train/Predict split → Model fitting → Predictions
- **Multi-model**: Generate predictions for each target label × algorithm combination

## Developer Workflows

### Local Development Pipeline
```bash
make setup              # Install deps + validate configs
make download           # Fetch data from Binance (scripts/download_binance.py)
make merge              # Align data from multiple sources
make features           # Generate derived features
make labels             # Generate training labels
make train              # Train all models
make predict            # Generate predictions
make signals            # Create trading signals
make pipeline           # Run all above sequentially
```

### Testing & Validation
- Unit tests in `tests/` directory
- Run: `make test` or `pytest`
- Config validation: Makefile includes `validate-configs` target

### Docker & Deployment
- `Dockerfile` for containerized trading service
- `make docker-build` / `make docker-push` to Azure Container Registry
- Kubernetes manifests in `helm/intelligent-trading-bot/`
- Infrastructure as Code: `infra/` (Terragrunt + Bicep for Azure, Terraform for GCP)

### Online Service Operation
```bash
python -m service.server -c configs/btcusdt_1m_dev.jsonc
```
- Runs continuous loop via `apscheduler` (see `service/server.py`)
- Fetches data from configured `inputs/collector_*`
- Executes trader functions from `outputs/trader_*`
- Sends notifications via `outputs/notifier_*`
- Global state maintained in `service/App` class

## Code Patterns

### Configuration Access
- Always access via `App.config` dictionary (not direct imports)
- Check existence: `App.config.get("key", default_value)`
- After changes: call `load_config()` to reload from file

### Feature/Label Computation
- Generators accept `df` (DataFrame), `config` dict, and optional `last_rows` (for streaming)
- Return modified DataFrame with new columns
- Example: `df = generate_features_talib(df, config_dict, last_rows=288)`

### Venue Abstraction
```python
from common.types import Venue
from inputs import get_collector_functions
from outputs import get_trader_functions

venue = Venue[App.config["venue"].upper()]
collector_fn, health_check_fn = get_collector_functions(venue)
trader_funcs = get_trader_functions(venue)
```

### Error Handling & Status
- `App.error_status`, `App.server_status`, `App.account_status`, `App.trade_state_status`
- Call `data_provider_problems_exist()` before operations
- Log extensively (debugging production issues requires tracing through async loops)

## File Organization

| Path | Purpose |
|------|---------|
| `service/App.py` | Global application state, config loader |
| `service/server.py` | Main async event loop for online trading |
| `service/analyzer.py` | Data analysis & feature computation |
| `common/gen_features.py` | Feature generators (talib, rolling aggs, custom) |
| `common/gen_labels_*.py` | Label generators (high/low, top/bottom) |
| `common/classifiers.py` | ML model training/prediction (LightGBM, NN, sklearn) |
| `common/model_store.py` | Model persistence and loading |
| `scripts/download_*.py` | Data fetchers for Binance, MT5, Yahoo |
| `scripts/train.py` | Offline model training orchestration |
| `scripts/predict.py` | Offline batch predictions |
| `inputs/collector_*.py` | Real-time data collection adapters |
| `outputs/trader_*.py` | Trading execution adapters |
| `outputs/notifier_*.py` | Signal notification (Telegram, APIs) |
| `configs/` | JSONC configuration files (symbol_freq_env) |

## Extending the System

### Adding a New Feature Generator
1. Define function in `common/gen_features.py` or new module
2. Add config entry: `{"generator":"module.path:function_name", "config":{...}}`
3. Generator must accept `(df, config, last_rows=0)` and return DataFrame

### Adding a New Data Source (Venue)
1. Add entry to `Venue` enum in `common/types.py`
2. Implement `inputs/collector_<venue>.py` with `sync_data_collector_task` and `data_provider_health_check`
3. Implement `outputs/trader_<venue>.py` with trader, account, and order functions
4. Update factory functions in `inputs/__init__.py` and `outputs/__init__.py`

### Adding a New ML Algorithm
1. Implement train/predict functions in `common/classifiers.py`
2. Update `scripts/train.py` to call new algorithm
3. Add algorithm identifier (e.g., `xgb`) to config's `algorithms` list

---

**Last Updated**: December 2025 | Review for changes to core data pipeline or service architecture
