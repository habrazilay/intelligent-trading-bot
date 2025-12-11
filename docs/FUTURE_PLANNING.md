# Future Planning: Data Architecture & Logging

**Status:** Planning/Discussion
**Priority:** Medium (after orderflow test)
**Timeline:** Q1 2025

---

## 🗂️ Data Structure Refactoring

### Current Structure (Suboptimal)

```
DATA_ITB_5m/
└── BTCUSDT/
    ├── klines.parquet
    ├── data.csv
    ├── features_aggressive.csv
    ├── matrix_aggressive.csv
    ├── predictions_aggressive.csv
    ├── signals_aggressive.csv
    └── MODELS_AGGRESSIVE_V1/
        ├── high_040_4_lgbm.pkl
        └── low_040_4_lgbm.pkl
```

**Problems:**
- ❌ `MODELS_AGGRESSIVE_V1` buried inside symbol folder
- ❌ Hard to compare models across symbols
- ❌ No clear separation of concerns
- ❌ Variant name (`aggressive`) scattered in filenames

---

### Proposed Structure (Better)

```
data/
├── {symbol}/
│   ├── {freq}/
│   │   ├── raw/
│   │   │   └── klines.parquet
│   │   ├── processed/
│   │   │   ├── data.csv
│   │   │   └── features.csv
│   │   └── labeled/
│   │       └── matrix.csv
│   └── orderbook/
│       └── snapshots_*.parquet
│
└── models/
    ├── {symbol}/
    │   ├── {freq}/
    │   │   ├── {variant}/          # aggressive, conservative, orderflow
    │   │   │   ├── {algo}/          # lgbm, logreg, automl
    │   │   │   │   ├── {label}/     # high_040_4, low_040_4
    │   │   │   │   │   ├── model.pkl
    │   │   │   │   │   ├── metadata.json
    │   │   │   │   │   └── metrics.json
```

**Example:**
```
data/
├── BTCUSDT/
│   ├── 5m/
│   │   ├── raw/klines.parquet
│   │   ├── processed/features.csv
│   │   └── labeled/matrix.csv
│   └── orderbook/
│       └── snapshots_20251210.parquet
│
└── models/
    └── BTCUSDT/
        └── 5m/
            ├── aggressive/
            │   └── lgbm/
            │       ├── high_040_4/
            │       │   ├── model.pkl
            │       │   ├── metadata.json  # training date, features, hyperparams
            │       │   └── metrics.json   # win rate, sharpe, etc
            │       └── low_040_4/
            │           └── ...
            └── orderflow/
                └── automl/
                    └── high_040_4/
                        └── ...
```

**Benefits:**
- ✅ Clear hierarchy: symbol → freq → variant → algo → label
- ✅ Easy to find/compare models
- ✅ Separation: data vs models
- ✅ Metadata + metrics with each model
- ✅ Versioning built-in (folder = version)

---

### Migration Strategy

**When:** After orderflow test (17/dez onwards)

**Effort:** ~1-2 days
- Update all scripts to use new paths
- Write migration script (copy old → new structure)
- Test pipeline end-to-end
- Update configs

**Backward compatibility:**
```python
# Add path resolver
def get_model_path(symbol, freq, variant, algo, label):
    # Try new structure first
    new_path = f"models/{symbol}/{freq}/{variant}/{algo}/{label}/model.pkl"
    if os.path.exists(new_path):
        return new_path

    # Fall back to old structure
    old_path = f"DATA_ITB_{freq}/{symbol}/MODELS_{variant.upper()}_V1/{label}_{algo}.pkl"
    return old_path
```

---

## 💾 Database Migration (BigData)

### Problem: File-based Storage Doesn't Scale

**Current approach:**
```
CSV files: 51,864 rows × 35 columns = ~12 MB
Parquet files: ~500 KB each

Issues:
- Can't query efficiently (need pandas.read_csv)
- No indexing (slow lookups)
- No concurrent access (file locks)
- No aggregations (GROUP BY, JOIN)
- Hard to analyze historical trends
```

**When it becomes critical:**
- Multiple symbols (5+ symbols × 3 timeframes = 15 datasets)
- Historical depth (2+ years of 1m data = millions of rows)
- Real-time queries (need sub-second lookups)
- Multi-user access (dashboards, analysis, trading)

---

### Proposed: TimescaleDB (PostgreSQL for Time-Series)

**Why TimescaleDB:**
- ✅ PostgreSQL-compatible (familiar SQL)
- ✅ Optimized for time-series (automatic partitioning)
- ✅ Compression (50-90% space savings)
- ✅ Continuous aggregates (pre-compute metrics)
- ✅ Open source + self-hosted option

**Schema Design:**

```sql
-- OHLCV data (raw)
CREATE TABLE ohlcv (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    freq TEXT NOT NULL,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume NUMERIC,
    PRIMARY KEY (time, symbol, freq)
);

SELECT create_hypertable('ohlcv', 'time');

-- Features (processed)
CREATE TABLE features (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    freq TEXT NOT NULL,
    close_sma_3 NUMERIC,
    close_rsi_14 NUMERIC,
    vol_regime INTEGER,
    -- ... all features
    PRIMARY KEY (time, symbol, freq)
);

SELECT create_hypertable('features', 'time');

-- Labels
CREATE TABLE labels (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    freq TEXT NOT NULL,
    high_040_4 BOOLEAN,
    low_040_4 BOOLEAN,
    -- ... all labels
    PRIMARY KEY (time, symbol, freq)
);

SELECT create_hypertable('labels', 'time');

-- Predictions (model outputs)
CREATE TABLE predictions (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    freq TEXT NOT NULL,
    model_name TEXT NOT NULL,      -- e.g., "lgbm_aggressive"
    label TEXT NOT NULL,            -- e.g., "high_040_4"
    probability NUMERIC,
    prediction BOOLEAN,
    PRIMARY KEY (time, symbol, freq, model_name, label)
);

SELECT create_hypertable('predictions', 'time');

-- Trades (executed)
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,            -- 'BUY' or 'SELL'
    price NUMERIC NOT NULL,
    quantity NUMERIC NOT NULL,
    model_name TEXT,
    signal_strength NUMERIC,
    pnl NUMERIC,                   -- Realized P&L
    status TEXT                    -- 'OPEN', 'CLOSED', 'CANCELLED'
);

CREATE INDEX ON trades (time DESC);
CREATE INDEX ON trades (symbol, time DESC);

-- Performance metrics (aggregated)
CREATE MATERIALIZED VIEW daily_performance
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS day,
    symbol,
    model_name,
    COUNT(*) AS total_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)::FLOAT / COUNT(*) AS win_rate,
    SUM(pnl) AS total_pnl,
    AVG(pnl) AS avg_pnl,
    MAX(pnl) AS max_win,
    MIN(pnl) AS max_loss
FROM trades
WHERE status = 'CLOSED'
GROUP BY day, symbol, model_name;
```

**Query Examples:**

```sql
-- Get recent features for prediction
SELECT * FROM features
WHERE symbol = 'BTCUSDT'
  AND freq = '5m'
  AND time >= NOW() - INTERVAL '1 hour'
ORDER BY time DESC
LIMIT 12;

-- Model performance last 30 days
SELECT
    symbol,
    model_name,
    win_rate,
    total_pnl,
    total_trades
FROM daily_performance
WHERE day >= NOW() - INTERVAL '30 days'
ORDER BY total_pnl DESC;

-- Compare Azure vs GCP models
SELECT
    CASE
        WHEN model_name LIKE '%azure%' THEN 'Azure'
        WHEN model_name LIKE '%gcp%' THEN 'GCP'
    END AS cloud,
    AVG(win_rate) AS avg_win_rate,
    SUM(total_pnl) AS total_profit
FROM daily_performance
WHERE day >= NOW() - INTERVAL '7 days'
GROUP BY cloud;
```

---

### Migration from CSV → TimescaleDB

**Phase 1: Dual-write (1 week)**
```python
# Write to both CSV and DB
df.to_csv('features.csv')
df.to_sql('features', engine, if_exists='append')
```

**Phase 2: Read from DB (1 week testing)**
```python
# Read from DB instead of CSV
df = pd.read_sql(
    "SELECT * FROM features WHERE symbol = %s AND freq = %s",
    engine,
    params=('BTCUSDT', '5m')
)
```

**Phase 3: Deprecate CSV (after 2 weeks)**
```python
# Remove CSV writes
# Keep CSV as backup for 1 month
```

---

## 📝 Logging Architecture

### Current State: Basic

```python
# Simple print statements or basic logging
logging.info("Training started")
print(f"Win rate: {win_rate}")
```

**Problems:**
- ❌ No structured logs (hard to parse)
- ❌ Logs scattered (files, stdout, stderr)
- ❌ No centralized aggregation
- ❌ Hard to search/filter
- ❌ No retention policy

---

### Proposed: Structured Logging + ELK Stack

**Tech Stack:**
- **Loguru** (Python): Better than stdlib logging
- **Elasticsearch**: Store + search logs
- **Kibana**: Visualize + dashboard
- **Filebeat**: Ship logs to Elasticsearch

**Structured Logging Example:**

```python
from loguru import logger
import sys

# Configure logger
logger.remove()  # Remove default handler
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)
logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    compression="zip",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
)

# Structured extra fields
logger.bind(
    symbol="BTCUSDT",
    freq="5m",
    model="lgbm_aggressive"
).info(
    "Model training completed",
    win_rate=0.58,
    sharpe=2.1,
    trades=300
)

# Output (JSON for Elasticsearch):
# {
#   "time": "2025-12-10 10:30:00",
#   "level": "INFO",
#   "message": "Model training completed",
#   "symbol": "BTCUSDT",
#   "freq": "5m",
#   "model": "lgbm_aggressive",
#   "extra": {
#     "win_rate": 0.58,
#     "sharpe": 2.1,
#     "trades": 300
#   }
# }
```

**Log Levels:**

```python
# DEBUG: Detailed diagnostic info
logger.debug("Feature calculation", feature_name="close_sma_3", value=99500.5)

# INFO: Normal operations
logger.info("Pipeline step completed", step="merge", duration_sec=5.2)

# WARNING: Potential issues
logger.warning("High API latency", latency_ms=1500, threshold_ms=1000)

# ERROR: Failures that don't stop execution
logger.error("Failed to fetch orderbook", symbol="SOLUSDT", error=str(e))

# CRITICAL: Severe failures
logger.critical("Trading halted", reason="max_drawdown_exceeded", drawdown_pct=15.2)
```

---

### ELK Stack Setup (Docker)

```yaml
# docker-compose.yml
version: '3.8'

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    ports:
      - "9200:9200"
    volumes:
      - es-data:/usr/share/elasticsearch/data

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch

  filebeat:
    image: docker.elastic.co/beats/filebeat:8.11.0
    volumes:
      - ./logs:/logs:ro
      - ./filebeat.yml:/usr/share/filebeat/filebeat.yml:ro
    depends_on:
      - elasticsearch

volumes:
  es-data:
```

**Filebeat config:**
```yaml
# filebeat.yml
filebeat.inputs:
  - type: log
    enabled: true
    paths:
      - /logs/*.log
    json.keys_under_root: true
    json.add_error_key: true

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  index: "itb-logs-%{+yyyy.MM.dd}"

setup.kibana:
  host: "kibana:5601"
```

**Usage:**
```bash
# Start ELK stack
docker-compose up -d

# View logs in Kibana
# http://localhost:5601
# Create index pattern: itb-logs-*
# Query: symbol:"BTCUSDT" AND level:"ERROR"
```

---

### Log Organization

**Folder structure:**
```
logs/
├── app/
│   ├── app_2025-12-10.log         # General application
│   └── app_2025-12-11.log
├── trading/
│   ├── trading_2025-12-10.log     # Trade execution
│   └── trading_2025-12-11.log
├── models/
│   ├── training_2025-12-10.log    # Model training
│   └── predictions_2025-12-10.log # Predictions
├── cloud/
│   ├── azure_2025-12-10.log       # Azure operations
│   └── gcp_2025-12-10.log         # GCP operations
└── errors/
    └── errors_2025-12-10.log      # All errors (aggregated)
```

**Retention:**
- App logs: 30 days
- Trading logs: 1 year (legal compliance)
- Model logs: 90 days
- Error logs: 6 months

---

## 🔍 Monitoring & Observability

### Metrics to Track

**System Metrics:**
```python
# CPU, Memory, Disk
import psutil

logger.info(
    "System metrics",
    cpu_percent=psutil.cpu_percent(),
    memory_percent=psutil.virtual_memory().percent,
    disk_percent=psutil.disk_usage('/').percent
)
```

**Trading Metrics:**
```python
# Win rate, P&L, Sharpe
logger.info(
    "Daily trading summary",
    date=date.today(),
    symbol="BTCUSDT",
    trades=15,
    wins=9,
    losses=6,
    win_rate=0.60,
    total_pnl=45.30,
    sharpe_ratio=2.1
)
```

**Model Performance:**
```python
# Drift detection
logger.warning(
    "Model drift detected",
    model="lgbm_aggressive",
    backtest_win_rate=0.58,
    live_win_rate=0.51,
    drift=0.07  # 7% degradation
)
```

**Cloud Costs:**
```python
# Azure + GCP spending
logger.info(
    "Cloud costs",
    date=date.today(),
    azure_cost_usd=12.50,
    gcp_cost_usd=35.80,
    total_cost_usd=48.30,
    budget_remaining_usd=1221.70
)
```

---

### Alerting

**Slack/Telegram Integration:**

```python
import requests

def send_alert(message, level="INFO"):
    """Send alert to Telegram"""
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    emoji = {
        "INFO": "ℹ️",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "CRITICAL": "🚨"
    }

    text = f"{emoji[level]} {message}"

    requests.post(
        f"https://api.telegram.org/bot{telegram_token}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )

# Usage
if daily_loss > 5:
    send_alert(
        f"CRITICAL: Daily loss {daily_loss}% exceeds threshold!",
        level="CRITICAL"
    )
```

**Alert Conditions:**

```yaml
CRITICAL (immediate action):
  - Daily loss > 5%
  - Trading halted (any reason)
  - Cloud costs > budget
  - API authentication failure

ERROR (fix within hours):
  - Model training failed
  - Data pipeline error
  - Orderbook collection stopped
  - Win rate < 50% for 3 days

WARNING (monitor):
  - High API latency (>1s)
  - Model drift > 5%
  - Unusual volume/volatility
  - Cloud costs > 80% budget

INFO (daily summary):
  - Daily P&L report
  - Model performance summary
  - Cloud cost summary
```

---

## 📊 Dashboard (Future)

**Grafana Dashboard:**

```yaml
Panels:
  - Real-time P&L (line chart)
  - Win rate by symbol (bar chart)
  - Open positions (table)
  - Cloud costs (stacked area)
  - Model drift (heatmap)
  - API latency (gauge)
  - System resources (CPU/Memory)

Refresh: Every 10 seconds
Time range: Last 24 hours (configurable)
```

**Metrics source:**
- TimescaleDB (trades, predictions)
- Prometheus (system metrics)
- Elasticsearch (log aggregations)

---

## 🛠️ Implementation Priority

### Phase 1 (Immediate - Current)
- ✅ File-based storage (CSV/Parquet)
- ✅ Basic logging (print/logging)
- ✅ Manual monitoring

### Phase 2 (After orderflow test - Jan)
- [ ] Structured logging (Loguru)
- [ ] Log rotation + retention
- [ ] Telegram alerts (critical events)
- [ ] Basic metrics tracking (win rate, P&L)

### Phase 3 (Scale - Feb/Mar)
- [ ] TimescaleDB migration
- [ ] ELK stack setup
- [ ] Grafana dashboard
- [ ] Automated alerting (all levels)

### Phase 4 (Production - Q2)
- [ ] Multi-region replication
- [ ] Advanced monitoring (APM)
- [ ] Cost optimization automation
- [ ] Compliance logging (audit trail)

---

## 💰 Cost Estimates

**ELK Stack (Self-hosted):**
```
AWS/Azure VM: t3.medium (2 vCPU, 4GB RAM)
  Cost: ~$30/month
  Storage: 100GB SSD (~$10/month)
  Total: ~$40/month

Alternative: Elastic Cloud
  Standard tier: ~$95/month
  Managed, no ops overhead
```

**TimescaleDB:**
```
Self-hosted (same VM as ELK):
  Incremental cost: ~$5/month (storage only)

Managed (Timescale Cloud):
  Starter tier: $50/month
  Includes backups, HA
```

**Total Monthly Cost (Full Stack):**
```
Self-hosted: ~$45/month
Managed: ~$145/month

Savings vs managed: $100/month (70%)
Tradeoff: Need to manage infrastructure
```

---

## 📝 Migration Checklist

**Data Structure:**
- [ ] Design new folder structure
- [ ] Write migration script
- [ ] Test with sample data
- [ ] Update all scripts (download → signals)
- [ ] Update configs
- [ ] Backup old structure
- [ ] Run migration
- [ ] Validate data integrity
- [ ] Update documentation

**Database:**
- [ ] Install TimescaleDB (local or cloud)
- [ ] Design schema
- [ ] Write data ingestion scripts
- [ ] Dual-write (CSV + DB) for 1 week
- [ ] Test queries performance
- [ ] Switch reads to DB
- [ ] Deprecate CSV writes
- [ ] Archive old CSVs

**Logging:**
- [ ] Install Loguru
- [ ] Refactor print → logger
- [ ] Add structured fields
- [ ] Configure log rotation
- [ ] Setup Telegram alerts
- [ ] (Optional) Setup ELK stack
- [ ] Create Kibana dashboards

---

## 🎯 Success Criteria

**Data Structure:**
- ✅ Models organized by: symbol/freq/variant/algo/label
- ✅ Clear separation: data vs models
- ✅ Metadata + metrics with each model
- ✅ Easy to compare across symbols/variants

**Database:**
- ✅ Query response < 100ms for recent data
- ✅ Support 1M+ rows per symbol
- ✅ Compression ratio > 50%
- ✅ Zero data loss during migration

**Logging:**
- ✅ Structured logs (JSON)
- ✅ Searchable in <1 second
- ✅ Alerts delivered < 30 seconds
- ✅ 99.9% log delivery (no drops)
- ✅ Clear audit trail (who/what/when)

---

**Document Status:** Planning
**Last Updated:** 2025-12-10
**Next Review:** After orderflow test (2025-12-17)
