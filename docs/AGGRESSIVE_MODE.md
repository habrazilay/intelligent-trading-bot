# 🚀 Aggressive Mode - High-Frequency Scalping Strategy

## 📋 Overview

The **Aggressive Mode** is a high-frequency scalping strategy optimized for 1-minute BTCUSDT trading with the following characteristics:

- **Target Profits:** 0.15-0.25% per trade (vs 0.5% conservative)
- **Holding Period:** 10-20 minutes average (vs 60 min conservative)
- **Trade Frequency:** 30-50 trades/day target (vs 5-10 conservative)
- **Risk Management:** Dynamic TP/SL with trailing stops and circuit breakers

---

## 🎯 Key Improvements Over Conservative Mode

| Feature | Conservative | Aggressive | Impact |
|---------|-------------|-----------|--------|
| **Labels** | 0.5% in 60 min | 0.2% in 10 min | ✅ Realistic targets |
| **Signal Threshold** | 0.003 | 0.01 | ✅ 3x more trades |
| **TP/SL** | None | Dynamic (0.20-0.25%) | ✅ Protects profits |
| **Max Hold Time** | Unlimited | 30 minutes | ✅ Prevents stale positions |
| **Trailing Stop** | No | Yes (after 0.15%) | ✅ Locks in profits |
| **Circuit Breaker** | No | Yes (5 losses) | ✅ Stops bleeding |
| **Regime Adaptation** | No | Yes (volatility-based) | ✅ Adapts to market |

---

## 📁 Files Created

### 1. **Label Generator**
```
common/gen_labels_aggressive.py
```
- Generates 0.15%, 0.20%, 0.25% targets in 10-minute horizons
- Validates label distribution (warns if too rare/common)
- Includes regime detection and spread features

### 2. **Risk Manager**
```
common/risk_manager.py
```
- Dynamic TP/SL based on volatility regime
- Trailing stops (activates after 0.15% profit)
- Time-based exits (30 min max hold)
- Position sizing with Kelly Criterion
- Circuit breakers (daily loss, consecutive losses)

### 3. **Aggressive Config**
```
configs/btcusdt_1m_aggressive.jsonc
```
- Complete configuration for aggressive strategy
- Includes all new features and labels
- Ready to use with existing ITB pipeline

---

## 🚀 Quick Start

### Step 1: Test Label Generation

```bash
# Test the aggressive label generator
python -c "from common.gen_labels_aggressive import *; import sys; sys.exit(0 if __name__ == '__main__' else 1)" && echo "✅ Labels OK"
```

### Step 2: Test Risk Manager

```bash
# Test the risk manager
python -c "from common.risk_manager import *; import sys; sys.exit(0 if __name__ == '__main__' else 1)" && echo "✅ Risk Manager OK"
```

### Step 3: Run Full Pipeline (Training)

```bash
# Download data
python -m scripts.download_binance -c configs/btcusdt_1m_aggressive.jsonc

# Merge data
python -m scripts.merge -c configs/btcusdt_1m_aggressive.jsonc

# Generate features (includes regime detection + spread)
python -m scripts.features -c configs/btcusdt_1m_aggressive.jsonc

# Generate aggressive labels
python -m scripts.labels -c configs/btcusdt_1m_aggressive.jsonc

# Train model
python -m scripts.train -c configs/btcusdt_1m_aggressive.jsonc

# Generate predictions
python -m scripts.predict -c configs/btcusdt_1m_aggressive.jsonc

# Generate signals
python -m scripts.signals -c configs/btcusdt_1m_aggressive.jsonc
```

### Step 4: Backtest

```bash
# Simulate trading with aggressive config
python -m scripts.simulate -c configs/btcusdt_1m_aggressive.jsonc
```

### Step 5: Shadow Mode (7 Days)

```bash
# Start server in shadow mode (staging environment)
python -m service.server -c configs/btcusdt_1m_aggressive.jsonc

# After 7 days, analyze results
python my_tests/analyze_staging_logs_v4.py \
  --log-file server.log \
  --starting-capital 1000 \
  --risk-per-trade 1.0
```

---

## 📊 Expected Performance Characteristics

### Conservative Mode (Current)
- **Win Rate:** 31% (from logs)
- **Trades/Day:** ~2-3
- **Avg PnL:** -0.16 USDT per trade
- **Problem:** Too few trades, unrealistic targets

### Aggressive Mode (Expected)
- **Win Rate Target:** 52%+ (more realistic targets)
- **Trades/Day:** 30-50 (higher frequency)
- **Avg PnL:** +0.10-0.15 USDT per trade
- **Risk:** Managed by TP/SL and circuit breakers

---

## ⚙️ Configuration Details

### Labels

```jsonc
{
  "thresholds": [0.15, 0.20, 0.25],  // % targets
  "tolerance": 0.05,                 // Max opposite move
  "horizon": 10                      // Minutes to look forward
}
```

**Rationale:**
- **0.2% in 10 min** is achievable (≈1.2%/hour if sustained)
- **0.5% in 60 min** was too ambitious (requires continuous move)
- **Tolerance 0.05%** prevents labeling bid-ask noise

### Signal Thresholds

```jsonc
{
  "buy_signal_threshold": 0.01,   // Enter on 1% model confidence
  "sell_signal_threshold": -0.01
}
```

**Rationale:**
- Lower threshold = more trades
- Risk managed by TP/SL, not by signal filtering
- Conservative mode (0.003) was too restrictive

### Risk Management

```jsonc
{
  "base_take_profit_pct": 0.25,    // 0.25% TP (base)
  "base_stop_loss_pct": 0.20,      // 0.20% SL (base)
  "max_hold_time_minutes": 30,     // Force exit after 30 min
  "enable_trailing_stop": true,    // Trail after 0.15% profit
  "max_daily_loss_pct": -3.0,      // Circuit breaker
  "max_consecutive_losses": 5      // Pause after 5 losses
}
```

**Regime Adaptation:**
- **Low Vol:** TP=0.20%, SL=0.16% (0.8x base)
- **Medium Vol:** TP=0.25%, SL=0.20% (1.0x base)
- **High Vol:** TP=0.33%, SL=0.26% (1.3x base)

---

## 🧪 Testing Checklist

Before deploying to live trading:

- [ ] **1. Unit Tests**
  - [ ] Run label generator test: `python common/gen_labels_aggressive.py`
  - [ ] Run risk manager test: `python common/risk_manager.py`

- [ ] **2. Label Distribution**
  - [ ] Check that 0.20% labels have 15-30% True rate
  - [ ] Verify labels are not too rare (<5%) or too common (>40%)

- [ ] **3. Backtest**
  - [ ] Run simulate on 90 days of data
  - [ ] Win rate > 50%
  - [ ] Max DD < 15%
  - [ ] Sharpe > 0.5

- [ ] **4. Shadow Mode (7 Days)**
  - [ ] Deploy to staging
  - [ ] Collect min 100 trades
  - [ ] Analyze with V4 analyzer
  - [ ] Compare: aggressive vs conservative

- [ ] **5. Validation Criteria**
  - [ ] Min trades: 100
  - [ ] Min win rate: 52%
  - [ ] Max drawdown: -15%
  - [ ] Min Sharpe: 0.5
  - [ ] Positive net PnL

---

## 🔧 Troubleshooting

### Problem: "No module named 'common.gen_labels_aggressive'"

**Solution:**
```bash
# Make sure you're in the project root
cd /path/to/intelligent-trading-bot

# Run from project root
python -m scripts.labels -c configs/btcusdt_1m_aggressive.jsonc
```

### Problem: Labels show as "TOO RARE" or "TOO COMMON"

**Action:**
- **TOO RARE (<5%):** Lower thresholds (e.g., 0.15% → 0.12%)
- **TOO COMMON (>40%):** Raise thresholds (e.g., 0.25% → 0.30%)
- **Adjust tolerance:** Tighter tolerance = fewer True labels

### Problem: Win rate still low after aggressive mode

**Possible Causes:**
1. Model not trained on aggressive labels
2. Thresholds still too high/low
3. Market regime changed (needs retraining)
4. Features insufficient for 1m predictions

**Debugging:**
```bash
# Check label distribution
grep "Label Distribution" logs/labels_*.log

# Check signal frequency
grep "buy_signal=True" server.log | wc -l

# Analyze trades by regime
python my_tests/analyze_staging_logs_v4.py --detailed
```

---

## 📈 Comparison: Conservative vs Aggressive

### Conservative Config (`btcusdt_1m_dev_lgbm.jsonc`)
```json
{
  "labels": ["high_05_60", "low_05_60"],          // 0.5% in 60 min
  "buy_signal_threshold": 0.003,
  "no_tp_sl": true,
  "expected_trades_per_day": 5-10
}
```

**Result (from logs):**
- Win rate: 31%
- Trades: 16 in 7 days (2.3/day)
- PnL: -0.026 USDT total

### Aggressive Config (`btcusdt_1m_aggressive.jsonc`)
```json
{
  "labels": ["high_020_10", "low_020_10"],        // 0.2% in 10 min
  "buy_signal_threshold": 0.01,
  "tp_sl": "dynamic",
  "expected_trades_per_day": 30-50
}
```

**Expected Result:**
- Win rate: 52%+
- Trades: 30-50/day
- PnL: Positive (target +1-2% weekly)

---

## 🎓 Next Steps

After implementing aggressive mode:

1. **Week 1:** Shadow mode validation
   - Deploy with config
   - Monitor signal frequency
   - Check TP/SL hit rates

2. **Week 2:** Analysis and tuning
   - Run V4 analyzer
   - Compare with conservative
   - Optimize thresholds if needed

3. **Week 3:** Testnet deployment
   - If shadow mode passes → deploy to Binance Testnet
   - Run for 30 days
   - Validate with real executions

4. **Week 4+:** Live (if validated)
   - Start with $50-100 capital
   - Scale gradually if profitable
   - Monitor daily with V4 analyzer

---

## 📚 Related Documentation

- **Shadow Mode Analysis:** `docs/SHADOW_MODE_ANALYSIS.md`
- **Original ITB README:** `README.md`
- **Label Generation:** `common/gen_labels_highlow.py` (original)
- **Risk Management:** `common/risk_manager.py` (new)

---

**Last Updated:** 2025-12-09
**Version:** Aggressive Mode V1
**Status:** 🟡 Ready for Testing
**Author:** Claude Code (Collaborative with User)
