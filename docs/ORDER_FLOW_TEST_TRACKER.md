# Order Flow Test - 1 Week Tracker

**Start Date:** December 10, 2024
**Deadline:** December 17, 2024 (7 days)
**Objective:** Test if order flow features achieve win rate ≥53%

---

## Decision Criteria

### Backtest (Day 7):
- **≥55%** win rate → 🟢 Proceed to shadow mode
- **53-55%** win rate → 🟡 Cautious shadow mode
- **50-53%** win rate → 🟠 Consider pivot to daily
- **<50%** win rate → 🔴 ABORT, pivot to daily

### Shadow Mode (Days 8-10):
- **≥52%** win rate → 🟢 Go LIVE with $100
- **50-52%** win rate → 🟡 Consider adjustments
- **<50%** win rate → 🔴 ABORT scalping strategy

### Abort Criteria (Stop immediately):
- ❌ Features don't extract (technical failure)
- ❌ Collector crashes repeatedly
- ❌ Backtest win rate <50%
- ❌ Shadow mode win rate <45%

---

## Day 0 - Tuesday, December 10, 2024

### ✅ Completed:
- [x] Created order flow pipeline (collector, features, config)
- [x] Tested WebSocket access (1 update/sec - EXCELLENT)
- [x] Started 2h data collection (13:08)

### ⏳ In Progress:
- [ ] 2h data collection (finishes ~15:08)

### 📋 Next Steps (After 2h collection):
- [ ] Verify Parquet files created
- [ ] Inspect data quality
- [ ] Create test config for 2h data
- [ ] Test feature extraction
- [ ] **GO/NO-GO DECISION:** Technical validation

### 🎯 Expected Results:
```
Files expected:
- DATA_ORDERBOOK/BTCUSDT_orderbook_20241210_133000.parquet (~3MB)
- DATA_ORDERBOOK/BTCUSDT_orderbook_20241210_140000.parquet (~3MB)
- DATA_ORDERBOOK/BTCUSDT_orderbook_20241210_143000.parquet (~3MB)
- DATA_ORDERBOOK/BTCUSDT_orderbook_20241210_150000.parquet (~3MB)

Total: ~7,200 snapshots, ~12MB
Covers: ~24 bars of 5m (2 hours)
```

---

## Day 0 Evening - Start 7-Day Collection (If GO)

### ⏳ Pending:
- [ ] If technical validation passes → Start 7-day collection
- [ ] Command: `nohup python scripts/collect_orderbook.py --symbol BTCUSDT --duration 7d --save-interval 6h > collector.log 2>&1 &`
- [ ] Verify first save after 6h

### 🎯 Expected Results:
```
7 days × 24 hours × 3600 snapshots/hour = ~604,800 snapshots
7 days × 24 hours / 6h = 28 files (~20MB each)
Total: ~560MB compressed

Covers: ~2,016 bars of 5m (7 days × 288 bars/day)
Training samples: Sufficient for LGBM
```

---

## Days 1-6 - Data Collection (Dec 11-16)

### ⏳ Monitoring:
- [ ] Check collector running: `ps aux | grep collect_orderbook`
- [ ] Check logs: `tail -f collector.log`
- [ ] Verify saves every 6h: `ls -lh DATA_ORDERBOOK/`

### Expected Progress:
- Day 1: ~4 files (~80MB)
- Day 2: ~8 files (~160MB)
- Day 3: ~12 files (~240MB)
- Day 4: ~16 files (~320MB)
- Day 5: ~20 files (~400MB)
- Day 6: ~24 files (~480MB)
- Day 7: ~28 files (~560MB)

---

## Day 7 - Tuesday, December 17, 2024

### 📋 Full Pipeline:
```bash
# 1. Features
python scripts/features_new.py -c configs/btcusdt_5m_orderflow.jsonc

# 2. Labels
python scripts/labels_new.py -c configs/btcusdt_5m_orderflow.jsonc

# 3. Merge
python scripts/merge_new.py -c configs/btcusdt_5m_orderflow.jsonc

# 4. Train
python scripts/train.py -c configs/btcusdt_5m_orderflow.jsonc

# 5. Signals
python scripts/signals.py -c configs/btcusdt_5m_orderflow.jsonc

# 6. Simulate
python scripts/simulate.py -c configs/btcusdt_5m_orderflow.jsonc
```

### 🎯 Critical Metrics:
- [ ] Win rate: _____% (need ≥53%)
- [ ] Total profit: _____% (need >0%)
- [ ] Sharpe ratio: _____ (need >0.3)
- [ ] Trades: _____ (need >100 for statistical significance)

### 🚦 DECISION:
- [ ] 🟢 Win rate ≥55% → Shadow mode
- [ ] 🟡 Win rate 53-55% → Shadow mode (cautious)
- [ ] 🟠 Win rate 50-53% → Consider pivot to daily
- [ ] 🔴 Win rate <50% → ABORT, pivot to daily

---

## Days 8-10 - Shadow Mode (If win rate ≥53%)

### ⏳ Pending:
- [ ] Configure shadow mode
- [ ] Run 3 days (72 hours)
- [ ] Monitor win rate hourly

### 🎯 Critical Metrics:
- [ ] Shadow win rate: _____% (need ≥52%)
- [ ] Shadow profit: _____% (need >0%)
- [ ] Profitable trades: _____
- [ ] Total trades: _____

### 🚦 FINAL DECISION:
- [ ] 🟢 Win rate ≥52% → GO LIVE with $100
- [ ] 🟡 Win rate 50-52% → Adjust or abort
- [ ] 🔴 Win rate <50% → ABORT scalping completely

---

## Alternative: Pivot to Daily Swing Trading

**Trigger:** If order flow fails (win rate <53% backtest OR <52% shadow)

### Plan:
```
1. Create configs/btcusdt_daily_swing.jsonc
2. Target: 2% profit in 5 days
3. Features: SMA/RSI work on daily trends
4. Backtest 4 years (1,460 samples)
5. Expected win rate: 55-60%
```

### Timeline:
- Day 1: Create config + features
- Day 2: Train + backtest
- Day 3: Shadow mode
- Day 4-10: Live testing

---

## Success Metrics Summary

| Metric | Baseline (Failed) | Order Flow Target |
|--------|-------------------|-------------------|
| Backtest Win Rate | 50.9% | **≥55%** |
| Shadow Win Rate | 31.2% | **≥52%** |
| Profit | -7.9% | **>0%** |
| Sharpe Ratio | -0.5 | **>0.3** |

---

## Notes & Observations

### Day 0 (Dec 10):
- Order book access confirmed: 1 update/sec (EXCELLENT)
- WebSocket stable, no disconnections
- Data quality: spread 0.0000% (tight liquidity)
- Started 2h test collection at 13:08

### Day X:
_Add notes as we progress..._

---

**Last Updated:** December 10, 2024 13:30
**Status:** ⏳ Collecting 2h test data (97 min remaining)
**Next Milestone:** Technical validation (~15:08)
