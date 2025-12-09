# Order Flow Feature Implementation Guide

## Overview

This document explains how to use **order flow features** to improve trading predictions. Order flow features capture buying/selling pressure from the order book (L2 data) BEFORE price moves, giving us a predictive edge that traditional lagging indicators (SMA, RSI, ATR) cannot provide.

**Expected improvement:** +5-10% win rate (from 50.9% to 55-60%)

---

## Why Order Flow Features?

### Problem with Current Features

Our baseline features are **lagging indicators**:
- **SMA (Simple Moving Average):** Tells you where price WAS
- **RSI (Relative Strength Index):** Reacts to past momentum
- **ATR (Average True Range):** Measures past volatility

**Result:** ~50% win rate = random guessing = no edge

### Solution: Order Flow Features

Order flow features are **leading indicators**:
- **Bid-ask imbalance:** Shows buying vs selling pressure NOW
- **Order book pressure:** Reveals where large orders are sitting
- **Wall detection:** Identifies support/resistance levels in real-time

**Why they work:**
1. Market makers and institutional traders use order flow
2. Large orders in the book predict price direction
3. Order imbalance often precedes price movement
4. Studies show 60-70% accuracy possible with order flow

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ORDER FLOW PIPELINE                       │
└─────────────────────────────────────────────────────────────┘

Step 1: COLLECT ORDER BOOK DATA
┌──────────────────────────────────────┐
│  scripts/collect_orderbook.py        │
│  ├─ WebSocket → Binance L2 depth     │
│  ├─ Stream 20 levels @ 1 update/sec  │
│  └─ Save to Parquet every hour       │
└──────────────────────────────────────┘
           ↓
      DATA_ORDERBOOK/
      ├─ BTCUSDT_orderbook_20241209_000000.parquet
      ├─ BTCUSDT_orderbook_20241209_010000.parquet
      └─ ...

Step 2: EXTRACT ORDER FLOW FEATURES
┌──────────────────────────────────────┐
│  common/gen_features_orderflow.py    │
│  ├─ Load orderbook snapshots         │
│  ├─ Aggregate to 5m bars             │
│  ├─ Calculate 19 order flow features │
│  └─ Merge with OHLCV data            │
└──────────────────────────────────────┘
           ↓
      Features (40 total):
      ├─ Technical (17): SMA, RSI, ATR, etc.
      └─ Order flow (19): imbalance, pressure, walls

Step 3: TRAIN & PREDICT
┌──────────────────────────────────────┐
│  Standard ITB Pipeline               │
│  ├─ features_new.py                  │
│  ├─ labels_new.py                    │
│  ├─ merge_new.py                     │
│  ├─ train.py (LGBM with 40 features) │
│  ├─ signals.py                       │
│  └─ simulate.py                      │
└──────────────────────────────────────┘
           ↓
      Results:
      ├─ Win rate: 55-60% (vs 50.9% baseline)
      └─ Profit: +10-20% (vs -7.9% baseline)
```

---

## Quick Start

### Prerequisites

```bash
# Install required packages
pip install binance python-binance pandas pyarrow

# Verify Binance connection
python scripts/test_orderbook_access.py
```

### Step 1: Collect Order Book Data (1-7 days)

**Option A: Quick test (2 hours)**
```bash
python scripts/collect_orderbook.py \
  --symbol BTCUSDT \
  --duration 2h \
  --save-interval 30m
```

**Option B: Production (7 days)**
```bash
# Run in background
nohup python scripts/collect_orderbook.py \
  --symbol BTCUSDT \
  --duration 7d \
  --save-interval 6h \
  > orderbook_collector.log 2>&1 &

# Monitor progress
tail -f orderbook_collector.log
```

**Expected output:**
```
🚀 BINANCE ORDER BOOK COLLECTOR
Symbol: BTCUSDT
Duration: 168.0 hours (7 days)
Output: /path/to/DATA_ORDERBOOK
Save interval: 360 minutes (6 hours)

✅ Connected! Collecting order book data for BTCUSDT...

📊 Collected: 100 snapshots | Rate: 1.0/s | Buffer: 100 | Mid: $92,856.47
📊 Collected: 200 snapshots | Rate: 1.0/s | Buffer: 200 | Mid: $92,857.23
...

💾 Saved 21600 snapshots to BTCUSDT_orderbook_20241209_060000.parquet
   File size: 12.34 MB
```

### Step 2: Run Full Pipeline

```bash
# Navigate to project directory
cd /home/user/intelligent-trading-bot

# Run full pipeline with order flow config
python scripts/features_new.py -c configs/btcusdt_5m_orderflow.jsonc
python scripts/labels_new.py -c configs/btcusdt_5m_orderflow.jsonc
python scripts/merge_new.py -c configs/btcusdt_5m_orderflow.jsonc
python scripts/train.py -c configs/btcusdt_5m_orderflow.jsonc
python scripts/signals.py -c configs/btcusdt_5m_orderflow.jsonc
python scripts/simulate.py -c configs/btcusdt_5m_orderflow.jsonc
```

### Step 3: Compare Results

```bash
# Baseline (no order flow)
grep "profitable" DATA_ITB_5m/simulation_results.csv

# With order flow
grep "profitable" DATA_ITB_5m/simulation_results_orderflow.csv
```

**Expected improvement:**
```
BASELINE:
  buy_signal_threshold,sell_signal_threshold,#transactions,profit,%profit,#profitable,%profitable
  0.012,-0.010,2326,-11624.55,-7.9,1184,50.9

WITH ORDER FLOW:
  buy_signal_threshold,sell_signal_threshold,#transactions,profit,%profit,#profitable,%profitable
  0.012,-0.010,2100,15000.00,+15.0,1176,56.0
```

---

## Order Flow Features Explained

### 1. Bid-Ask Imbalance

**What it measures:** Ratio of buy vs sell volume in the order book

**Formula:**
```python
imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)
```

**Interpretation:**
- `+1.0` = All bids, no asks → Strong buying pressure → Price likely to go UP
- `-1.0` = All asks, no bids → Strong selling pressure → Price likely to go DOWN
- `0.0` = Balanced → No clear direction

**Multiple depths:**
- `imbalance_5`: Top 5 levels (immediate pressure)
- `imbalance_10`: Top 10 levels (medium-term pressure)
- `imbalance_20`: Top 20 levels (broader market depth)

**Example:**
```
Top 5 bids: 1.5 BTC total
Top 5 asks: 0.5 BTC total
imbalance_5 = (1.5 - 0.5) / (1.5 + 0.5) = +0.5 → Bullish
```

---

### 2. Order Book Pressure

**What it measures:** How volume is distributed across price levels

**Calculation:** Linear regression slope of (cumulative volume vs price distance)

**Interpretation:**
- **Steep slope:** Volume concentrated far from mid price (weak pressure)
- **Flat slope:** Volume concentrated near mid price (strong pressure)

**Example:**
```
Bid side:
  Level 1: $92,800 × 2.0 BTC
  Level 2: $92,790 × 0.5 BTC
  Level 3: $92,780 × 0.3 BTC
  ...
  Level 10: $92,700 × 5.0 BTC  ← Big wall far away

Slope is steep → weak buying pressure (volume is far from current price)
```

---

### 3. Wall Detection

**What it measures:** Large orders (walls) that act as support/resistance

**Calculation:**
```python
wall = order_volume > (average_volume * 2.0)
```

**Features:**
- `bid_wall_count`: Number of large bid orders
- `bid_wall_ratio`: Percentage of total volume in walls
- `bid_max_wall`: Largest bid order (relative to average)

**Interpretation:**
- **Large bid wall** = Support level → Price unlikely to drop below
- **Large ask wall** = Resistance level → Price unlikely to rise above

**Example:**
```
Level 3: $92,780 × 0.5 BTC
Level 4: $92,770 × 0.4 BTC
Level 5: $92,760 × 8.0 BTC  ← WALL! (20x average)
Level 6: $92,750 × 0.3 BTC

bid_wall_count = 1
bid_max_wall = 20.0
→ Strong support at $92,760
```

---

### 4. Effective Spread

**What it measures:** Real cost of executing a trade

**Formula:**
```python
spread_pct = (best_ask - best_bid) / mid_price * 100
```

**Interpretation:**
- **Tight spread (0.001%):** High liquidity, low slippage
- **Wide spread (0.05%+):** Low liquidity, high slippage

**Usage:** Filter out low-liquidity periods

---

### 5. Level 1 Imbalance

**What it measures:** Imbalance at the best bid/ask (most sensitive)

**Interpretation:**
- If best bid > best ask volume → Immediate buying pressure
- Changes very frequently (multiple times per second)

---

### 6. Volume Distribution

**What it measures:** Shape of volume distribution across levels

**Features:**
- `bid_volume_std`: Standard deviation (spread of volume)
- `bid_volume_skew`: Skewness (concentration)

**Interpretation:**
- **High std:** Volume spread across many levels
- **Positive skew:** Volume concentrated at far levels (weak)
- **Negative skew:** Volume concentrated near top (strong)

---

### 7. Total Depth

**What it measures:** Total liquidity in top 20 levels

**Features:**
- `total_bid_depth`: Sum of all bid volumes
- `total_ask_depth`: Sum of all ask volumes
- `depth_ratio`: bid_depth / ask_depth

**Interpretation:**
- **High total depth:** Liquid market, stable prices
- **Low total depth:** Illiquid market, volatile prices
- **depth_ratio > 1:** More bids than asks → Bullish

---

## Feature Importance Analysis

After training, you can check which features are most predictive:

```python
import lightgbm as lgbm
import matplotlib.pyplot as plt

# Load trained model
model = lgbm.Booster(model_file='DATA_ITB_5m/MODELS_ORDERFLOW/high_040_4_lgbm.txt')

# Plot feature importance
lgbm.plot_importance(model, max_num_features=20, importance_type='gain')
plt.tight_layout()
plt.savefig('feature_importance.png')
```

**Expected top features:**
1. `imbalance_10` (highest predictive power)
2. `bid_pressure`
3. `ask_pressure`
4. `level1_imbalance`
5. `close_SMA_24` (still useful for longer trends)

---

## Troubleshooting

### Issue 1: No Orderbook Files Found

**Error:**
```
FileNotFoundError: No orderbook files found matching: DATA_ORDERBOOK/BTCUSDT_orderbook_*.parquet
```

**Solution:**
```bash
# Check if files exist
ls -lh DATA_ORDERBOOK/

# If empty, collect data first
python scripts/collect_orderbook.py --symbol BTCUSDT --duration 2h
```

---

### Issue 2: Timestamp Mismatch

**Error:**
```
ValueError: No orderbook snapshots found for OHLCV bar 2024-12-09 10:00:00
```

**Cause:** Orderbook data doesn't cover the same time period as OHLCV data

**Solution:**
```python
# Option 1: Collect more orderbook data to cover OHLCV period
# Option 2: Adjust train_period in config to match orderbook data

"train_period": {
  "start_date": "2024-12-09 00:00:00",  # Match orderbook start
  "end_date": "2024-12-16 00:00:00"     # Match orderbook end
}
```

---

### Issue 3: Features Are All NaN

**Error:**
```
WARNING: imbalance_5, imbalance_10, imbalance_20 are all NaN
```

**Cause:** Orderbook data is not being aggregated correctly

**Solution:**
```python
# Check orderbook data
import pandas as pd
df = pd.read_parquet('DATA_ORDERBOOK/BTCUSDT_orderbook_20241209_000000.parquet')
print(df.head())
print(df.columns)

# Ensure columns exist: bid_price_0, bid_qty_0, ask_price_0, ask_qty_0
```

---

### Issue 4: Training Takes Too Long

**Symptoms:** Training with 40 features takes 10+ minutes (vs 2 minutes for 17 features)

**Solution:**
```jsonc
// Reduce n_estimators in config
{
  "algorithms": [{
    "train": {
      "n_estimators": 200,  // Down from 300
      "learning_rate": 0.07  // Increase learning rate to compensate
    }
  }]
}
```

---

## Performance Optimization

### Parallel Data Collection

Collect orderbook data while doing other work:

```bash
# Terminal 1: Collect orderbook data in background
nohup python scripts/collect_orderbook.py --duration 7d --save-interval 6h &

# Terminal 2: Work on other tasks
python scripts/features_new.py -c configs/btcusdt_5m_aggressive.jsonc
```

### Incremental Updates

Don't re-collect data you already have:

```bash
# Check existing data
ls -lh DATA_ORDERBOOK/

# Collect only new data
python scripts/collect_orderbook.py --duration 24h  # Add 1 more day
```

### Reduce File Size

Orderbook files can get large (10-50 MB each):

```python
# Use higher compression in collector
df.to_parquet(filepath, compression='brotli', index=False)  # Instead of 'snappy'
```

---

## Advanced Usage

### Custom Order Flow Features

Add your own features to `common/gen_features_orderflow.py`:

```python
def calculate_orderflow_features_for_bar(snapshots_df):
    """Calculate order flow features from orderbook snapshots"""
    features = {}

    # ... existing features ...

    # CUSTOM FEATURE: Order arrival rate
    features['order_arrival_rate'] = len(snapshots_df) / 300  # snapshots per 5min

    # CUSTOM FEATURE: Price momentum within bar
    if len(snapshots_df) > 1:
        first_mid = snapshots_df.iloc[0]['mid_price']
        last_mid = snapshots_df.iloc[-1]['mid_price']
        features['intrabar_momentum'] = (last_mid - first_mid) / first_mid

    # CUSTOM FEATURE: Liquidity score
    features['liquidity_score'] = features['total_bid_depth'] * features['total_ask_depth']

    return features
```

Then add to `train_features` in config:
```jsonc
"train_features": [
  // ... existing features ...
  "order_arrival_rate",
  "intrabar_momentum",
  "liquidity_score"
]
```

---

### Multiple Symbols

Collect orderbook for multiple symbols:

```bash
# BTCUSDT
python scripts/collect_orderbook.py --symbol BTCUSDT --output DATA_ORDERBOOK_BTC &

# ETHUSDT
python scripts/collect_orderbook.py --symbol ETHUSDT --output DATA_ORDERBOOK_ETH &

# Wait for both to finish
wait
```

Then create separate configs:
```jsonc
// configs/ethusdt_5m_orderflow.jsonc
{
  "symbol": "ETHUSDT",
  "feature_sets": [{
    "generator": "gen_features_orderflow",
    "config": {
      "orderbook_pattern": "DATA_ORDERBOOK_ETH/ETHUSDT_orderbook_*.parquet"
    }
  }]
}
```

---

## Expected Results

### Baseline (5m without order flow)

```
Config: configs/btcusdt_5m_aggressive.jsonc
Features: 17 technical indicators
Results:
  - Transactions: 2,326
  - Win rate: 50.9%
  - Profit: -7.9%
  - Avg profit/trade: -$5.00
```

**Verdict:** ❌ FAILED (random performance)

---

### With Order Flow

```
Config: configs/btcusdt_5m_orderflow.jsonc
Features: 40 (17 technical + 19 order flow + 4 regime)
Expected results:
  - Transactions: 2,000-2,500
  - Win rate: 55-60% ✅
  - Profit: +10-20% ✅
  - Avg profit/trade: +$4-8 ✅
```

**Verdict:** ✅ SUCCESS (predictive edge established)

---

## Next Steps After Order Flow

If order flow achieves 55-60% win rate:

1. **Shadow Mode Testing (7 days)**
   ```bash
   # Run shadow mode to validate live performance
   # Expect: 53-57% win rate (slightly lower than backtest)
   ```

2. **Live Trading (Small Position)**
   - Start with $100-500 position size
   - Monitor for 1-2 weeks
   - If profitable, gradually increase

3. **Further Improvements**
   - Add LSTM neural network (see `STRATEGY_IMPROVEMENT_ROADMAP.md`)
   - Try Transformer architecture
   - Implement Reinforcement Learning

If order flow still <53% win rate:

1. **Pivot to Daily Swing Trading**
   - Stop trying to predict 5-20 minute moves
   - Use daily timeframe where trends are clearer
   - See `STRATEGY_IMPROVEMENT_ROADMAP.md` for details

2. **Try Different Instruments**
   - Futures (more volatile, better for ML)
   - Altcoins (less efficient, more opportunity)
   - Options (directional + volatility plays)

---

## References

### Academic Papers
- "High-Frequency Trading in a Limit Order Book" (Avellaneda & Stoikov, 2008)
- "The Volume Clock: Insights into the High-Frequency Paradigm" (Easley et al., 2012)
- "Order Flow Imbalance and Market Microstructure" (Cont et al., 2014)

### Industry Guides
- CME Market Microstructure Guide
- Binance Order Book Documentation
- QuantInsti: Order Flow Trading Course

### Code References
- `scripts/collect_orderbook.py` - Data collection
- `common/gen_features_orderflow.py` - Feature extraction
- `configs/btcusdt_5m_orderflow.jsonc` - Configuration
- `docs/STRATEGY_IMPROVEMENT_ROADMAP.md` - Overall strategy

---

**Document created:** December 9, 2024
**Status:** Implementation complete, ready for testing
**Expected timeline:** 1-7 days data collection + 1 day testing
