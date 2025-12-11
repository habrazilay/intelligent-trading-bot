# Multi-Cloud Trading Strategy

**Mission:** Maximize profits using Azure + GCP credits through specialized model deployment and portfolio diversification.

**Status:** Planning phase
**Timeline:** 4 weeks (Dec 10 - Jan 7)
**Budget:** $970 GCP + $300 Azure = $1,270 total

---

## 🎯 Core Philosophy

**Specialization + Ensemble = Better Returns**

Each cloud does what it does BEST:
- **Azure:** Fast, cheap, conservative baseline models
- **GCP:** Advanced ML, deep learning, orderflow intelligence

Then combine results via ensemble voting for final trading decisions.

---

## ⚡ Azure Division: "Speed & Baseline"

### Mission
Fast, cheap, conservative models for high-liquidity markets.

### Stack
```yaml
Models:
  - Logistic Regression (baseline)
  - LightGBM (Kaggle-proven)
  - Random Forest (ensemble complement)

Symbols: BTC, ETH
  Reason: High liquidity, stable patterns, low spreads

Timeframes: 1m, 5m
  Reason: Scalping opportunities, many trades/day

Features:
  - Classic TA (SMA, RSI, ATR)
  - Spread features (bid-ask)
  - Regime detection (vol classification)

Training Frequency: Weekly
  Cost: ~$5-10/week
  Total Budget: ~$80 from $300 credits
```

### Trading Strategy
```yaml
Type: Conservative
Capital Allocation: 60% of total ($600 if $1,000 total)
Risk per Trade: 0.5%
Target Profit: 0.3%
Win Rate Target: ≥55%
Trades/Day: ~10
```

### Azure ML Pipeline
```bash
# Weekly training
az container create \
  --name itb-train-azure \
  --image itbacr.azurecr.io/itb-bot:latest \
  --command-line "sh -c '
    python -m scripts.merge_new -c configs/btcusdt_5m_azure.jsonc &&
    python -m scripts.features_new -c configs/btcusdt_5m_azure.jsonc &&
    python -m scripts.labels_new -c configs/btcusdt_5m_azure.jsonc &&
    python -m scripts.train -c configs/btcusdt_5m_azure.jsonc
  '"
```

---

## 🧠 GCP Division: "Intelligence & Innovation"

### Mission
Advanced ML with orderflow for higher-volatility altcoins.

### Stack
```yaml
Models:
  - Vertex AutoML (automated feature engineering)
  - LSTM (temporal sequence patterns)
  - Transformer (attention mechanism)

Symbols: SOL, BNB, XRP, MATIC
  Reason: Higher volatility = more profit potential

Timeframes: 5m, 15m
  Reason: Orderflow signals clearer at 5-15m

Features:
  - Orderflow L2 (19 features)
  - Bid-ask imbalance (depths: 5, 10, 20)
  - Order book pressure (slope analysis)
  - Wall detection (large orders)

Training:
  - AutoML: $50 (conservative test)
  - LSTM GPU (T4): $30 (if AutoML ≥53%)
  Total Budget: ~$300 from $970 credits
```

### Trading Strategy
```yaml
Type: Aggressive
Capital Allocation: 30% of total ($300 if $1,000 total)
Risk per Trade: 1.0%
Target Profit: 0.5%
Win Rate Target: ≥52%
Trades/Day: ~5
```

### GCP ML Pipeline
```bash
# Upload data to BigQuery
make gcp-upload-bigquery CONFIG=configs/sol_5m_orderflow.jsonc

# Train with AutoML
make gcp-automl CONFIG=configs/sol_5m_orderflow.jsonc BUDGET=1

# If successful (≥53% win rate), train LSTM
make gcp-lstm CONFIG=configs/sol_5m_orderflow.jsonc
```

---

## 🎯 Ensemble Meta-Model Strategy

### Decision Logic

```python
def select_model(market_conditions):
    """
    Dynamic model selection based on market volatility.
    """
    volatility = get_current_volatility()

    if volatility < 0.5:
        # Low volatility → stable patterns
        # Use Azure baseline (more reliable)
        return azure_lgbm_btc

    elif volatility < 1.5:
        # Medium volatility → orderflow shines
        # Use GCP orderflow models
        return gcp_automl_sol

    else:
        # High volatility (>1.5) → risky
        # Pause or use most conservative
        return azure_logreg_eth  # or PAUSE
```

### Weighted Voting

```python
# Ensemble prediction from all models
signal_final = (
    0.4 × azure_lgbm_prediction +
    0.3 × gcp_automl_prediction +
    0.2 × azure_logreg_prediction +
    0.1 × gcp_lstm_prediction
)

# Only trade if high confidence
if signal_final > 0.6:
    execute_trade()
```

**Rationale:**
- LGBM gets highest weight (proven baseline)
- AutoML gets 2nd (orderflow innovation)
- LogReg provides conservative anchor
- LSTM experimental (lowest weight)

---

## 💰 Portfolio Allocation

### Capital Distribution

```
Total Capital: $1,000

Azure Division (Conservative):
  - $600 allocated
  - BTC/ETH scalping
  - Models: LGBM + LogReg
  - Target: $15/day
  - Monthly: $450 (75% APY)

GCP Division (Aggressive):
  - $300 allocated
  - SOL/BNB/XRP volatility plays
  - Models: AutoML + LSTM + orderflow
  - Target: $12/day
  - Monthly: $360 (120% APY)

Emergency Reserve:
  - $100 untouched
  - Insurance against drawdowns
```

### Weekly Rebalancing

Based on performance, shift capital:

```python
if azure_win_rate > gcp_win_rate + 5%:
    shift_capital(from_gcp, to_azure, amount=10%)
elif gcp_win_rate > azure_win_rate + 5%:
    shift_capital(from_azure, to_gcp, amount=10%)
```

---

## 🔄 A/B Testing Real-Time

### Shadow Mode Parallel Testing

Run both clouds simultaneously in shadow mode for 1 week:

```yaml
Week 1 Results:
  Azure LGBM (BTC 5m):
    Win Rate: 58%
    Profit: +$45
    Decision: ✅ Increase allocation +10%

  GCP AutoML (SOL 5m):
    Win Rate: 51%
    Profit: +$12
    Decision: ⚠️ Monitor, no change

Week 2 Results:
  Azure LGBM (BTC 5m):
    Win Rate: 52%
    Profit: +$18
    Decision: ⚠️ Slight decrease

  GCP AutoML+orderflow (SOL 5m):
    Win Rate: 61%
    Profit: +$67
    Decision: ✅ Increase allocation +10%
```

### Auto-Adjustment Rules

```yaml
Triggers:
  - Win rate delta > 5% between clouds → shift 10% capital
  - Daily loss > 5% on any cloud → pause that cloud
  - Both clouds <50% win rate for 3 days → HALT everything

Actions:
  - Rebalance capital weekly
  - Retrain models if win rate drops
  - Add/remove symbols based on profitability
```

---

## 📊 Multi-Market Strategy

### Symbol Allocation by Cloud

| Cloud | Symbol | Timeframe | Strategy | Rationale |
|-------|--------|-----------|----------|-----------|
| **Azure** | BTC | 1m | Fast scalping | Highest liquidity, lowest spread |
| **Azure** | ETH | 5m | Momentum following | Correlates with BTC but lags |
| **GCP** | SOL | 5m | Orderflow advantage | High volatility, orderflow works |
| **GCP** | BNB | 15m | Trend following | Exchange token, unique patterns |
| **GCP** | XRP | 5m | Mean reversion | High oscillation, good for scalping |

### Correlation Benefits

**Low correlation** between symbols = **reduced systemic risk**:

```
BTC-ETH correlation: 0.85 (high, expected)
BTC-SOL correlation: 0.65 (medium)
BTC-XRP correlation: 0.45 (low)
SOL-BNB correlation: 0.50 (medium)

Portfolio correlation: ~0.60 (diversified!)
```

If BTC crashes → SOL/XRP might be unaffected or even rise.

---

## 💵 ROI Projections

### Conservative Scenario (53% win rate)

```
Capital: $1,000
Trades/day: 15 (Azure: 10, GCP: 5)
Average profit per win: 0.3%
Win rate: 53%

Calculation:
  Winning trades/day: 15 × 0.53 = 7.95
  Daily profit: 7.95 × 0.3% × $1,000 = $23.85
  Fees (0.08%): -$4.80
  Net daily: $19/day

Monthly: $19 × 30 = $570
Annual: $570 × 12 = $6,840
ROI: 68% per year
```

### Optimistic Scenario (58% win rate with orderflow)

```
Capital: $1,000
Trades/day: 15
Win rate: 58%

Net daily: $32/day
Monthly: $960
Annual: $11,520
ROI: 115% per year
```

### Compounding (Reinvest Profits)

```
Start: $1,000

Month 1: $1,570 (+57%)
Month 2: $2,465 (+146%)
Month 3: $3,870 (+287%)
Month 6: $12,200 (+1,120%)
Year 1: $150,000+ (exponential growth)
```

**Note:** Assumes consistent 58% win rate and full profit reinvestment.

---

## 🛡️ Risk Management Multi-Cloud

### Per-Cloud Circuit Breakers

**Azure Rules:**
```yaml
Daily loss > 2%: Pause trading
3 consecutive losing days: Retrain models
Weekly win rate < 52%: Switch to GCP or HALT
Model divergence (backtest vs live > 5%): Investigate
```

**GCP Rules:**
```yaml
Daily loss > 3%: Pause (higher risk tolerance)
Weekly win rate < 50%: Retrain with more data
GPU training costs > $50/week: Optimize or pause
Orderflow collection failure: Fall back to Azure
```

### Global Portfolio Breakers

```yaml
CRITICAL STOPS:
  - Total portfolio loss > 5% in 1 day → HALT ALL
  - Combined win rate < 50% for 5 days → STOP & ANALYZE
  - Drawdown > 15% from peak → Manual review required
  - Binance API failure → Auto-pause all trading

RECOVERY PROTOCOL:
  1. Stop all trading
  2. Analyze failure mode (model, data, market)
  3. Retrain on recent data
  4. Shadow mode test for 3 days
  5. Resume with 50% capital if win rate recovers
```

---

## 🚀 Implementation Timeline

### Week 1: Dec 10-17 (Preparation)

**Objectives:**
- Complete orderbook collection (7 days)
- Upload data to both clouds
- Split requirements files

**Tasks:**
```bash
# Azure
- Upload BTCUSDT/ETHUSDT data to Azure Blob Storage
- Create configs: btcusdt_5m_azure.jsonc, ethusdt_5m_azure.jsonc
- Test pipeline: download → merge → features → labels → train

# GCP
- Upload SOL/BNB/XRP data to BigQuery
- Create configs: sol_5m_gcp_orderflow.jsonc
- Verify orderflow data quality (7 days collection)

# Code
- Split requirements.txt → requirements-azure.txt + requirements-gcp.txt
- Create Azure training workflow (GitHub Actions)
- Create GCP training workflow (local scripts + manual)
```

**Deliverables:**
- ✅ 7 days of orderbook data
- ✅ Data uploaded to both clouds
- ✅ Configs created for all symbols
- ✅ Requirements split

---

### Week 2: Dec 17-24 (Training & Backtesting)

**Objectives:**
- Train models on both clouds
- Backtest and compare performance
- Select best models per symbol

**Azure Tasks:**
```bash
# Train baseline models
make pipeline CONFIG=configs/btcusdt_5m_azure.jsonc
make pipeline CONFIG=configs/ethusdt_5m_azure.jsonc

# Models trained:
- Logistic Regression (baseline)
- LightGBM (primary)
- Random Forest (ensemble)

# Backtest 90 days
python scripts/backtest.py -c configs/btcusdt_5m_azure.jsonc

# Metrics to collect:
- Win rate
- Sharpe ratio
- Max drawdown
- Profit factor
```

**GCP Tasks:**
```bash
# Upload orderflow data
make gcp-upload-bigquery CONFIG=configs/sol_5m_gcp_orderflow.jsonc

# Train AutoML (conservative $50)
make gcp-automl CONFIG=configs/sol_5m_gcp_orderflow.jsonc BUDGET=1

# If win rate ≥53%, train LSTM
make gcp-lstm CONFIG=configs/sol_5m_gcp_orderflow.jsonc

# Backtest and compare
```

**Decision Point:**
```yaml
If Azure win rate ≥55% AND GCP win rate ≥53%:
  → Proceed to Week 3 (Shadow Mode)

If Azure ≥55% but GCP <53%:
  → Use only Azure, save GCP budget

If both <53%:
  → ABORT multi-cloud strategy
  → Pivot to daily timeframe or re-evaluate
```

**Deliverables:**
- ✅ Trained models on both clouds
- ✅ Backtest results with metrics
- ✅ Go/no-go decision based on win rates

---

### Week 3: Dec 24-31 (Shadow Mode Testing)

**Objectives:**
- Deploy both clouds in shadow mode
- Real-time A/B testing
- Collect live performance metrics

**Azure Shadow Mode:**
```bash
# Deploy server with Azure models
az container create \
  --name itb-shadow-azure \
  --image itbacr.azurecr.io/itb-bot:latest \
  --command-line "python -m service.server -c configs/btcusdt_5m_azure.jsonc" \
  --environment-variables ENABLE_LIVE_TRADING=0

# Monitor logs
az container logs --name itb-shadow-azure --follow
```

**GCP Shadow Mode:**
```bash
# Deploy on Compute Engine or local
python -m service.server -c configs/sol_5m_gcp_orderflow.jsonc

# Set environment
export ENABLE_LIVE_TRADING=0
export MODEL_PATH=/path/to/gcp/models
```

**Metrics to Track (7 days):**
```yaml
Per Cloud:
  - Win rate (%)
  - Profit/loss ($)
  - Number of trades
  - Average hold time
  - Max drawdown
  - Sharpe ratio

Comparison:
  - Which cloud performed better?
  - Any correlation between signals?
  - Ensemble strategy improvement?
```

**Daily Review:**
```bash
# Analyze shadow mode logs
make analyze-staging LOG_FILE=logs/azure_shadow.log
make analyze-staging LOG_FILE=logs/gcp_shadow.log

# Compare results
python scripts/compare_clouds.py \
  --azure logs/azure_shadow.log \
  --gcp logs/gcp_shadow.log
```

**Deliverables:**
- ✅ 7 days of live shadow mode data
- ✅ Performance comparison Azure vs GCP
- ✅ Ensemble voting strategy tested
- ✅ Final model selection

---

### Week 4: Jan 1-7 (Live Trading Launch)

**Objectives:**
- Start live trading with real capital
- Monitor and adjust allocation
- Implement auto-rebalancing

**Phase 1: Conservative Start ($100 test)**

```yaml
Day 1-3: Test with minimal capital
  Azure: $60 (BTC + ETH)
  GCP: $30 (SOL)
  Reserve: $10

Criteria for scale-up:
  - Win rate ≥55% on both clouds
  - No critical errors (API, execution)
  - Drawdown <3%
```

**Phase 2: Scale to Full Capital ($1,000)**

```yaml
Day 4-7: If Phase 1 successful
  Azure: $600 (60% allocation)
  GCP: $300 (30% allocation)
  Reserve: $100 (10% emergency)

Daily monitoring:
  - P&L tracking
  - Win rate vs backtest
  - Cloud performance divergence
  - Risk metrics (Sharpe, max DD)
```

**Auto-Rebalancing Logic:**

```python
# Weekly rebalance
if azure_sharpe > gcp_sharpe + 0.3:
    shift_capital(gcp → azure, 10%)
elif gcp_sharpe > azure_sharpe + 0.3:
    shift_capital(azure → gcp, 10%)

# Emergency stops
if daily_loss > 5%:
    pause_trading()
    send_alert("CRITICAL: Daily loss exceeded")
```

**Deliverables:**
- ✅ Live trading operational
- ✅ Real P&L tracking
- ✅ Auto-rebalancing implemented
- ✅ Performance monitoring dashboard

---

## 📈 Month 2+ (Scale & Optimize)

### Continuous Improvement

**Add More Symbols (if profitable):**
```yaml
Azure Expansion:
  - Add MATIC (if BTC/ETH profitable)
  - Add AVAX (high correlation with ETH)

GCP Expansion:
  - Add DOT (orderflow may work)
  - Add ATOM (volatile, good for ML)
```

**Model Improvements:**
```yaml
Ensemble Meta-Model:
  - Train stacking classifier on cloud outputs
  - Improve voting weights dynamically
  - Add market regime detection

Feature Engineering:
  - Add cross-symbol features (BTC → ETH correlation)
  - Time-of-day features (Asia/Europe/US sessions)
  - Order book depth changes (velocity metrics)
```

**Infrastructure:**
```yaml
Monitoring:
  - Unified dashboard (Grafana)
  - Aggregate logs from both clouds
  - Real-time alerts (Telegram/email)

Database:
  - Migrate to TimescaleDB (time-series optimized)
  - Store: trades, signals, model predictions, metrics
  - Enable historical analysis

Cost Optimization:
  - Use spot instances on GCP (60% cheaper)
  - Optimize container sizes
  - Cache frequently-used data
```

---

## 🎨 DevOps Showcase Value

**Multi-Cloud Skills Demonstrated:**

```yaml
Cloud Architecture:
  - Hybrid deployment (Azure + GCP)
  - Cost optimization across providers
  - Vendor lock-in avoidance

Infrastructure as Code:
  - Terraform (Azure infra)
  - GitHub Actions (CI/CD)
  - Container orchestration (ACI + Compute Engine)

MLOps:
  - Model versioning (git tags + container tags)
  - A/B testing framework (shadow mode)
  - Automated retraining pipelines
  - Performance monitoring

Data Engineering:
  - Multi-cloud data sync
  - Real-time data pipelines (orderflow)
  - Time-series databases
  - Log aggregation

Risk Management:
  - Circuit breakers (code-based)
  - Auto-pause on anomalies
  - Capital allocation algorithms
```

**Resume Impact:**
```
"Designed and deployed multi-cloud ML trading system:
- Orchestrated Azure + GCP for model specialization
- Achieved 58% win rate (8% above baseline)
- Managed $1,270 cloud budget with 200% ROI
- Implemented A/B testing and ensemble strategies
- Built real-time monitoring and auto-rebalancing"
```

---

## 🔧 Technical Architecture

### Cloud Resources

**Azure:**
```yaml
Resource Group: rg-itb-prod
Storage:
  - stitbprod (Blob Storage)
  - data-itb-5m (File Share)
Compute:
  - ACI containers (ephemeral training jobs)
Container Registry:
  - itbacr.azurecr.io/itb-bot:azure-latest
```

**GCP:**
```yaml
Project: ninth-goal-464400-e5
Storage:
  - BigQuery: itb_5min dataset
  - Cloud Storage: gs://itb-models/
Compute:
  - Vertex AI (AutoML)
  - Compute Engine with T4 GPU (LSTM)
Container Registry:
  - gcr.io/ninth-goal-464400-e5/itb-bot:gcp-latest
```

### Data Flow

```
┌─────────────────────────────────────────────────┐
│ Data Sources                                    │
│  - Binance API (OHLCV)                         │
│  - Binance WebSocket (Orderbook L2)            │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ Local Collection                                │
│  - download_binance.py → klines.parquet        │
│  - collect_orderbook.py → orderbook.parquet    │
└─────────────────────────────────────────────────┘
                      ↓
           ┌──────────┴──────────┐
           ↓                     ↓
┌──────────────────┐   ┌─────────────────────┐
│ Azure Pipeline   │   │ GCP Pipeline        │
│                  │   │                     │
│ → Azure Blob     │   │ → BigQuery          │
│ → Merge/Features │   │ → Vertex AutoML     │
│ → Labels         │   │ → LSTM Training     │
│ → LGBM Train     │   │ → Model Export      │
│ → Models Export  │   │                     │
└──────────────────┘   └─────────────────────┘
           ↓                     ↓
┌──────────────────────────────────────────────────┐
│ Shadow Mode Testing (Parallel)                   │
│  - Azure: BTC/ETH predictions                    │
│  - GCP: SOL/BNB/XRP predictions                  │
│  - Compare win rates                             │
└──────────────────────────────────────────────────┘
                      ↓
┌──────────────────────────────────────────────────┐
│ Ensemble Meta-Model                              │
│  - Weighted voting                               │
│  - Market regime detection                       │
│  - Final trade decision                          │
└──────────────────────────────────────────────────┘
                      ↓
┌──────────────────────────────────────────────────┐
│ Live Trading (Binance)                           │
│  - Execute trades                                │
│  - Monitor P&L                                   │
│  - Auto-rebalance capital                        │
└──────────────────────────────────────────────────┘
```

---

## 📝 Configuration Files

### Azure Config Example

```jsonc
// configs/btcusdt_5m_azure.jsonc
{
  "symbol": "BTCUSDT",
  "freq": "5m",
  "data_folder": "./DATA_ITB_5m",

  "labels": ["high_030_4", "low_030_4"],

  "train_features": [
    "close_SMA_3", "close_SMA_6", "close_SMA_12",
    "close_RSI_14",
    "high_low_close_ATR_14",
    "spread_pct_3",
    "vol_regime"
  ],

  "algorithms": [
    {
      "name": "logreg",
      "algo": "sklearn_logreg",
      "train": {
        "C": 1.0,
        "max_iter": 1000
      }
    },
    {
      "name": "lgbm",
      "algo": "lgbm",
      "train": {
        "num_leaves": 31,
        "learning_rate": 0.05,
        "n_estimators": 300
      }
    }
  ],

  "cloud": "azure",
  "deployment": "aci"
}
```

### GCP Config Example

```jsonc
// configs/sol_5m_gcp_orderflow.jsonc
{
  "symbol": "SOLUSDT",
  "freq": "5m",
  "data_folder": "./DATA_ITB_5m",

  "labels": ["high_040_4", "low_040_4"],

  "train_features": [
    // Orderflow features (19)
    "imbalance_5", "imbalance_10", "imbalance_20",
    "bid_pressure", "ask_pressure",
    "bid_wall_count", "ask_wall_count",
    "effective_spread",
    "level1_imbalance",

    // Basic TA (complement)
    "close_SMA_3",
    "close_RSI_14",
    "vol_regime"
  ],

  "feature_sets": [
    {
      "generator": "gen_features_orderflow",
      "config": {
        "orderbook_pattern": "DATA_ORDERBOOK/SOLUSDT_orderbook_*.parquet",
        "depths": [5, 10, 20],
        "freq": "5T"
      }
    }
  ],

  "algorithms": [
    {
      "name": "automl",
      "algo": "vertex_automl",
      "train": {
        "budget_hours": 1,
        "optimization_objective": "maximize-precision-at-recall"
      }
    }
  ],

  "cloud": "gcp",
  "deployment": "vertex"
}
```

---

## 🎯 Success Metrics

### Performance Targets

**Minimum Viable (Go/No-Go):**
```yaml
Win Rate: ≥53%
Sharpe Ratio: ≥1.0
Max Drawdown: <10%
Profit Factor: ≥1.5
```

**Target (Successful):**
```yaml
Win Rate: ≥58%
Sharpe Ratio: ≥2.0
Max Drawdown: <5%
Profit Factor: ≥2.0
Daily Profit: $30+
Monthly ROI: 8%+
```

**Exceptional (Best Case):**
```yaml
Win Rate: ≥65%
Sharpe Ratio: ≥3.0
Max Drawdown: <3%
Profit Factor: ≥3.0
Daily Profit: $50+
Monthly ROI: 15%+
```

### Cloud Comparison Metrics

Track which cloud performs better:

```python
metrics = {
    "azure": {
        "win_rate": 0.58,
        "sharpe": 2.1,
        "profit": 1250,  # Total profit in $
        "trades": 300,
        "cost": 80,      # Cloud spend
        "roi": 1250/80 = 15.6x
    },
    "gcp": {
        "win_rate": 0.61,
        "sharpe": 2.4,
        "profit": 1680,
        "trades": 150,
        "cost": 300,
        "roi": 1680/300 = 5.6x
    }
}

# Winner: GCP (higher win rate, Sharpe)
# But Azure has better ROI (cost-efficiency)
# Solution: Use both! Diversification wins.
```

---

## 📚 Dependencies

### Requirements Split

**requirements-azure.txt:**
```txt
# Base dependencies (same as requirements.txt)
numpy==2.1.*
pandas==2.*
python-binance>=1.0.32
ta-lib
scikit-learn==1.6.*
lightgbm==4.*
python-dotenv>=1.0.0

# No GCP libraries needed
```

**requirements-gcp.txt:**
```txt
# Include base
-r requirements-azure.txt

# GCP-specific
google-cloud-bigquery>=3.0.0
google-cloud-aiplatform>=1.38.0
google-cloud-storage>=2.10.0

# Deep learning (optional, for LSTM)
tensorflow==2.19.*
```

**Installation:**
```bash
# Azure containers
pip install -r requirements-azure.txt

# Local with GCP
pip install -r requirements-gcp.txt
```

---

## 🚨 Risks & Mitigation

### Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Model overfitting | High | Medium | Cross-validation, walk-forward testing |
| API rate limits | High | Low | Implement exponential backoff |
| Cloud outage | Medium | Low | Multi-cloud redundancy |
| Data pipeline failure | High | Medium | Monitoring + alerts + fallbacks |
| Execution delays | Medium | Medium | Use limit orders, acceptable slippage |

### Financial Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Flash crash | High | Low | Circuit breakers, max loss limits |
| Sustained drawdown | High | Medium | Auto-pause at -5% daily, -15% total |
| Model decay | Medium | High | Weekly retraining, monitor drift |
| Binance delisting | Low | Low | Diversify symbols |
| Fee changes | Low | Low | Monitor profitability threshold |

### Operational Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Config error | High | Low | Validation scripts, dry-run tests |
| Insufficient credits | Medium | Low | Monitor spend, alerts at 80% usage |
| Lost credentials | High | Low | Secrets in GitHub, Azure Key Vault |
| Data corruption | Medium | Low | Daily backups, versioning |

---

## 📖 References

- [Azure Container Instances Pricing](https://azure.microsoft.com/en-us/pricing/details/container-instances/)
- [GCP Vertex AI Pricing](https://cloud.google.com/vertex-ai/pricing)
- [LightGBM Documentation](https://lightgbm.readthedocs.io/)
- [Binance API Documentation](https://binance-docs.github.io/apidocs/spot/en/)
- [Multi-Cloud Architecture Best Practices](https://cloud.google.com/architecture/hybrid-and-multi-cloud-patterns-and-practices)

---

## ✅ Next Actions

**Immediate (Dec 10-17):**
- [ ] Split requirements.txt → requirements-azure.txt + requirements-gcp.txt
- [ ] Create Azure configs for BTC/ETH
- [ ] Create GCP configs for SOL/BNB/XRP
- [ ] Upload data to Azure Blob + GCP BigQuery
- [ ] Complete 7-day orderbook collection

**Week 2 (Dec 17-24):**
- [ ] Train Azure models (LGBM baseline)
- [ ] Train GCP AutoML (orderflow)
- [ ] Backtest both, compare win rates
- [ ] Go/no-go decision

**Week 3 (Dec 24-31):**
- [ ] Deploy shadow mode on both clouds
- [ ] A/B test for 7 days
- [ ] Implement ensemble voting

**Week 4 (Jan 1-7):**
- [ ] Launch live trading ($100 test)
- [ ] Scale to $1,000 if successful
- [ ] Monitor and optimize

---

**Document Status:** Planning
**Last Updated:** 2025-12-10
**Next Review:** 2025-12-17 (after orderbook collection)
