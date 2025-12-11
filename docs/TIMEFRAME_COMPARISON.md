# Timeframe Comparison Guide

## 🎯 Quick Decision: Which Timeframe to Use?

| If you want... | Use | Win Rate Target | Trades/Day |
|---|---|---|---|
| **High frequency** (but 1m failed) | **5m** | 45-55% | 15-25 |
| **Stable profits** (less noise) | **1h** | 55-65% | 2-5 |
| **Ultra scalping** (risky!) | 1m | 35-45% | 30-50 |

---

## 📊 Configurations Available

### **1. BTCUSDT 1m Aggressive** ⚡
**Status:** ❌ Shadow mode failed (31% win rate)
```bash
# Config: configs/btcusdt_1m_aggressive.jsonc
Target:   0.2% in 10 minutes
Labels:   high_020_10, low_020_10
Features: 17 (SMA, RSI, ATR, spread, regime)
```

**Problems:**
- Too much noise (tick-level fluctuations)
- Fees/spread eat profits (0.08% round-trip)
- Model can't predict 10min moves reliably

---

### **2. BTCUSDT 5m Aggressive** ✅ **RECOMMENDED**
```bash
# Config: configs/btcusdt_5m_aggressive.jsonc
Target:   0.4% in 20 minutes
Labels:   high_040_4, low_040_4
Features: 17 (scaled 5x: SMA_3→15min, SMA_6→30min)
```

**Advantages:**
- Filters out tick noise
- Better risk/reward (0.4% vs 0.2%)
- Fees less impactful (fewer trades)
- Based on real stats: P(+0.5% in 20min) = 2.78%

**When to use:**
- You want active trading (15-25 signals/day)
- BTC volatility is moderate (ATR > 0.5%)
- You have good execution (low latency)

---

### **3. BTCUSDT 1h Aggressive** 🎯 **SAFEST**
```bash
# Config: configs/btcusdt_1h_aggressive.jsonc
Target:   1.0% in 4 hours
Labels:   high_100_4, low_100_4
Features: 17 (scaled 60x: SMA_3→3h, SMA_6→6h)
```

**Advantages:**
- Captures real trends (not noise)
- Much better win rate potential (55-65%)
- Fewer trades = less fees = better Sharpe
- Based on real stats: P(+1% in 4h) = 4.3%

**When to use:**
- You want consistent profits
- You can hold positions for hours
- You prefer quality over quantity

---

## 🚀 How to Run Each Timeframe

### **Step 1: Download Data**

```bash
# 5m (if you don't have it yet)
python -m scripts.download_binance -c configs/btcusdt_5m_aggressive.jsonc

# 1h (if you don't have it yet)
python -m scripts.download_binance -c configs/btcusdt_1h_aggressive.jsonc
```

### **Step 2: Train & Backtest**

**For 5m:**
```bash
# Full pipeline
python -m scripts.merge -c configs/btcusdt_5m_aggressive.jsonc
python -m scripts.features_new -c configs/btcusdt_5m_aggressive.jsonc
python -m scripts.labels_new -c configs/btcusdt_5m_aggressive.jsonc
python -m scripts.train -c configs/btcusdt_5m_aggressive.jsonc
python -m scripts.predict -c configs/btcusdt_5m_aggressive.jsonc
python -m scripts.signals -c configs/btcusdt_5m_aggressive.jsonc
python -m scripts.simulate -c configs/btcusdt_5m_aggressive.jsonc
```

**For 1h:**
```bash
# Same pipeline, different config
python -m scripts.merge -c configs/btcusdt_1h_aggressive.jsonc
python -m scripts.features_new -c configs/btcusdt_1h_aggressive.jsonc
python -m scripts.labels_new -c configs/btcusdt_1h_aggressive.jsonc
python -m scripts.train -c configs/btcusdt_1h_aggressive.jsonc
python -m scripts.predict -c configs/btcusdt_1h_aggressive.jsonc
python -m scripts.signals -c configs/btcusdt_1h_aggressive.jsonc
python -m scripts.simulate -c configs/btcusdt_1h_aggressive.jsonc
```

### **Step 3: Compare Results**

```bash
# View backtest results
cat DATA_ITB_5m/BTCUSDT/signal_models_aggressive.txt
cat DATA_ITB_1h/BTCUSDT/signal_models_aggressive.txt

# Compare with 1m
cat DATA_ITB_1m/BTCUSDT/signal_models_aggressive.txt
```

**Decision criteria:**
- ✅ Win rate > 52%
- ✅ Sharpe > 0.5
- ✅ Max drawdown < -15%
- ✅ Profit/trade > 0

---

## 📈 Expected Performance (Estimates)

Based on volatility analysis and shadow mode results:

| Metric | 1m | 5m | 1h |
|--------|----|----|-----|
| **Win Rate** | 31% ❌ | 45-50% ⚠️ | 55-65% ✅ |
| **Sharpe Ratio** | -0.5 | 0.3-0.7 | 0.8-1.2 |
| **Trades/Day** | 30-50 | 15-25 | 2-5 |
| **Avg Profit/Trade** | -$0.002 | $0.01-0.02 | $0.05-0.10 |
| **Max Drawdown** | -10% | -8% | -5% |
| **Fees Impact** | 💀 High | ⚠️ Medium | ✅ Low |

---

## 🔍 Which One First?

**My recommendation:**

1. **Start with 1h** (safest, best win rate)
2. **If 1h works** → add 5m for diversification
3. **Never use 1m** (proven to fail in shadow mode)

**Quick test (1 hour each):**
```bash
# Test 1h first (takes ~10 min to train)
time bash -c "python -m scripts.merge -c configs/btcusdt_1h_aggressive.jsonc && \
              python -m scripts.features_new -c configs/btcusdt_1h_aggressive.jsonc && \
              python -m scripts.labels_new -c configs/btcusdt_1h_aggressive.jsonc && \
              python -m scripts.train -c configs/btcusdt_1h_aggressive.jsonc && \
              python -m scripts.predict -c configs/btcusdt_1h_aggressive.jsonc && \
              python -m scripts.signals -c configs/btcusdt_1h_aggressive.jsonc && \
              python -m scripts.simulate -c configs/btcusdt_1h_aggressive.jsonc"

# Check results
cat DATA_ITB_1h/BTCUSDT/signal_models_aggressive.txt
```

If **win rate > 52%** → deploy to shadow mode!
If **win rate < 50%** → try 5m or improve features.

---

## 💡 Pro Tips

1. **Start conservative:** Use 1h until you prove it works
2. **Monitor separately:** Don't mix 5m and 1h signals
3. **Adjust thresholds:** `buy_signal_threshold` might need tuning per timeframe
4. **Check correlation:** If BTC trends strong, 1h wins. If choppy, avoid 5m.

---

## 🆘 Troubleshooting

**Q: 5m also gives bad win rate (<45%)?**
→ Your features are too weak. Add momentum features (see `docs/AGGRESSIVE_MODE.md`)

**Q: 1h gives only 2 trades/day, too few?**
→ That's normal! Lower threshold to 0.005 for more signals (but test in backtest first)

**Q: Can I run both 5m and 1h simultaneously?**
→ Yes! Use separate configs and separate shadow mode instances.

---

**Next Steps:**
1. Run `scripts/simulate` for both 5m and 1h
2. Compare win rates and Sharpe ratios
3. Deploy the best one to shadow mode
4. Monitor for 7 days before going live
