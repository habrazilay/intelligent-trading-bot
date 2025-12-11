# Strategy Failure Analysis - December 2024

## Executive Summary

After extensive testing of aggressive scalping strategies across three timeframes (1m, 5m, 1h), **all strategies failed to achieve profitable results**. This document analyzes the root causes and provides recommendations for fundamental strategy redesign.

**Key Finding:** ~50% win rate across all timeframes indicates **zero predictive edge** - equivalent to coin flip performance.

---

## Test Results Overview

### 1. BTCUSDT 1m Aggressive (December 4-5, 2024)

**Shadow Mode (12 hours live testing):**
- Win Rate: **31.2%** ❌ (catastrophic failure)
- Profitable trades: 10 out of 32
- Live trading conditions much worse than backtest

**Backtest (6 months historical):**
- Config: `configs/btcusdt_1m_aggressive.jsonc`
- Target: 0.2% profit in 10 minutes
- Labels: `high_020_10`, `low_020_10`
- Algorithm: LightGBM (LGBM)

```
Transactions: 3,404
Total Profit: -7.5%
Win Rate: 50.4%
Avg Profit/Trade: -$2.20
```

**Verdict:** Failed. Win rate barely above 50% = no edge.

---

### 2. BTCUSDT 5m Aggressive (December 9, 2024)

**Backtest (6 months historical):**
- Config: `configs/btcusdt_5m_aggressive.jsonc`
- Target: 0.4% profit in 20 minutes (4 candles)
- Labels: `high_040_4`, `low_040_4`
- Algorithm: LightGBM

```
Transactions: 2,326
Total Profit: -7.9%
Win Rate: 50.9%
Avg Profit/Trade: -$5.00
```

**Verdict:** Failed. Same ~50% win rate as 1m.

---

### 3. BTCUSDT 1h Aggressive (December 9, 2024)

**Backtest (6 months historical):**
- Config: `configs/btcusdt_1h_aggressive.jsonc`
- Target: 1.0% profit in 4 hours (4 candles)
- Labels: `high_100_4`, `low_100_4`
- Algorithm: LightGBM

```
Transactions: 210
Total Profit: -13.7% ❌ WORST!
Win Rate: 51.9%
Avg Profit/Trade: -$83.81
```

**Verdict:** Failed spectacularly. Despite cleaner signals, WORSE performance than 1m/5m.

---

## Root Cause Analysis

### Problem 1: Lagging Indicators Have Zero Predictive Power

**Features Used:**
```
- close_SMA_3, close_SMA_5, close_SMA_10, close_SMA_12, close_SMA_24, close_SMA_48
- close_LINEARREG_SLOPE_3, close_LINEARREG_SLOPE_5, close_LINEARREG_SLOPE_12, close_LINEARREG_SLOPE_24
- close_RSI_14
- high_low_close_ATR_14
- close_STDDEV_12, close_STDDEV_24
- spread_pct_3, spread_pct_5, spread_pct_10, spread_pct_12
- vol_regime (based on ATR percentiles)
```

**Why they fail:**
1. **SMA (Simple Moving Average):** Tells you where price WAS, not where it's GOING
2. **RSI (Relative Strength Index):** Reacts to past momentum, doesn't predict future
3. **ATR (Average True Range):** Measures past volatility, not future moves
4. **LINEARREG_SLOPE:** Linear regression on past prices - inherently backwards-looking
5. **Spread features:** High-low spread is microstructure noise, not predictive signal

**Evidence:** 50% win rate = these features contain NO information about future price direction.

---

### Problem 2: Labels Too Rare (Severe Class Imbalance)

**Label Distribution:**
- 1m: 5.28% (high_020_10), 4.80% (low_020_10)
- 5m: 3.22% (high_040_4), 3.40% (low_040_4)
- 1h: 6.39% (high_100_4), 5.69% (low_100_4)

**Why this matters:**
- When positive labels are <10%, model learns to predict False
- Even if features were perfect, model optimizes for majority class
- Threshold tuning cannot overcome fundamental class imbalance

**Example:** With 3.22% positive rate (5m), a model that always predicts False gets 96.78% accuracy!

---

### Problem 3: Targets Too Aggressive for Available Features

**Reality Check:**

| Timeframe | Target | Horizon | Base Rate | Feasibility |
|-----------|--------|---------|-----------|-------------|
| 1m | 0.2% | 10 min | 5.28% | ❌ Too rare |
| 5m | 0.4% | 20 min | 3.22% | ❌ Too rare |
| 1h | 1.0% | 4 hours | 6.39% | ❌ Too rare |

Even the "safest" 1h strategy only has 6.39% chance of +1% move in 4h.

**With current features (lagging indicators), predicting these rare events is impossible.**

---

### Problem 4: Fees Dominate When Win Rate ≈ 50%

**Binance BTCUSDT Fees:**
- Maker: 0.02% - 0.04%
- Taker: 0.04% - 0.075%
- Round-trip: ~0.08% - 0.12%

**Impact Analysis:**

| Strategy | Win Rate | Avg P/L | Fees Impact | Net Result |
|----------|----------|---------|-------------|------------|
| 1m | 50.4% | -$2.20 | 0.08% × 3,404 | -7.5% total |
| 5m | 50.9% | -$5.00 | 0.08% × 2,326 | -7.9% total |
| 1h | 51.9% | -$83.81 | 0.08% × 210 | -13.7% total |

**Even 1h with 51.9% win rate loses money because:**
- 51.9% win is only +1.9% edge
- But round-trip fees are 0.08-0.12%
- With larger position sizes, fees eat the edge

---

## Why 1h Was WORSE Than Expected

We hypothesized 1h would have:
- ✅ Less noise (hourly filters tick-level fluctuations)
- ✅ Better win rate (captures trends)
- ✅ Lower fees impact (fewer trades)

**What actually happened:** -13.7% loss (worst of all timeframes!)

**Why:**
1. **Fewer samples = worse training:** Only 4,320 training samples vs 250k for 1m
2. **Labels still too rare:** 6.39% positive rate is still severe imbalance
3. **Larger stop losses:** 1h needs wider stops → bigger losses when wrong
4. **Features still lagging:** SMA_72 (3 days) is even more delayed
5. **BTC regime changed:** 6-month backtest may not capture current market

**Conclusion:** Timeframe is NOT the problem. The fundamental approach is broken.

---

## What We Learned

### ✅ What Worked:
1. ITB pipeline is solid (download, merge, features, labels, train, predict, signals, simulate)
2. LightGBM implementation works correctly
3. Config system is flexible and extensible
4. Data reuse strategy saves time
5. Shadow mode validation caught failure early

### ❌ What Failed:
1. Lagging indicators cannot predict future price moves
2. Rare labels (<10% positive rate) prevent effective training
3. 50% win rate = random guessing = no edge
4. Timeframe diversification (1m/5m/1h) didn't help
5. Algorithm choice (LC vs LGBM) is irrelevant when features are worthless

---

## Fundamental Strategy Rethink Required

### Current Approach (FAILED):
```
Lagging Indicators → ML Model → Binary Prediction → Trade Signal
   (SMA, RSI, ATR)     (LGBM)     (Buy/Sell/Hold)     (Enter/Exit)
```

**Problem:** Garbage in → Garbage out. No amount of ML sophistication can extract signal from lagging indicators.

---

### Option A: Better Features (Leading Indicators)

**What we need:**
- **Order flow features** (if L2 data available):
  - Bid-ask imbalance at different depth levels
  - Trade flow (buyer vs seller initiated)
  - Order book pressure
  - Large order detection

- **Microstructure features:**
  - Price impact of trades
  - Effective spread
  - Roll measure (serial correlation)
  - Volume-weighted bid-ask spread

- **Alternative data:**
  - Funding rates (perpetual futures)
  - Open interest changes
  - Liquidation events
  - Social sentiment (Twitter, Reddit)
  - On-chain metrics (for crypto)

- **Cross-asset features:**
  - ETH/BTC correlation
  - DXY (dollar index)
  - S&P 500 futures
  - Gold prices
  - Volatility indices (VIX)

**Challenge:** Most of this data is not free. May require:
- Binance WebSocket for real-time order book
- CryptoQuant/Glassnode subscription for on-chain data
- Alternative data providers

---

### Option B: Different Target (Regression Instead of Classification)

**Current approach:** Binary classification (will price go up 0.2% in 10 min? Yes/No)

**Alternative:** Regression (predict exact price change in next N minutes)

**Advantages:**
1. No label imbalance (every sample has a continuous target)
2. Model learns magnitude, not just direction
3. Can set dynamic thresholds based on prediction confidence
4. Better for risk management (position sizing based on predicted move)

**Example:**
```python
# Instead of:
label = 1 if future_high > close * 1.002 else 0

# Use:
label = (future_close - current_close) / current_close  # Percentage return
```

---

### Option C: Ensemble of Strategies (Not Ensemble of Models)

**Instead of:** One model trying to predict everything

**Try:** Multiple specialized strategies:
1. **Trend following** (1h/4h): Ride established trends
2. **Mean reversion** (5m/15m): Fade extremes in ranging markets
3. **Breakout detection** (1m/5m): Catch explosive moves
4. **Regime switching:** Detect market state and switch strategies

**Each strategy:**
- Has its own features
- Has its own labels
- Trades only when conditions are favorable
- Has different risk parameters

---

### Option D: Deep Learning Approaches

**Instead of:** Hand-crafted features → LGBM

**Try:** Raw price/volume → Neural Network

**Architectures to explore:**
1. **LSTM (Long Short-Term Memory):**
   - Learns temporal patterns automatically
   - No need for manual feature engineering
   - Can handle variable-length sequences

2. **Transformer with Attention:**
   - State-of-the-art for time series
   - Attention mechanism learns which timesteps matter
   - Can capture long-range dependencies

3. **Convolutional Neural Networks:**
   - Treat price charts as images
   - Learn visual patterns (support/resistance, channels)
   - Combined with LSTM for temporal modeling

4. **Reinforcement Learning:**
   - Learn optimal trading policy directly
   - Maximizes cumulative reward (profit)
   - Handles sequential decision-making naturally

**Example:**
```python
# Instead of 17 hand-crafted features:
X = [SMA_3, SMA_5, RSI_14, ATR_14, ...]

# Feed raw OHLCV directly:
X = last_100_candles[['open', 'high', 'low', 'close', 'volume']]
# Shape: (100, 5) → LSTM → Dense → Prediction
```

---

### Option E: Cloud ML Services (Azure ML / GCP AI)

**Why consider cloud ML:**
1. **AutoML:** Automatically tries hundreds of feature/model combinations
2. **More compute:** Train larger models faster
3. **MLOps:** Better model versioning, deployment, monitoring
4. **Managed infrastructure:** No DevOps overhead

**Azure Machine Learning:**
- AutoML for time series forecasting
- Designer for no-code ML pipelines
- Scalable compute clusters
- Cost: ~$0.50/hour for basic compute

**Google Cloud AI Platform:**
- Vertex AI for AutoML
- BigQuery ML for SQL-based training
- Pre-trained models for time series
- Cost: Similar to Azure

**Realistic assessment:**
- Cloud ML won't magically fix bad features
- AutoML can't create signal where none exists
- Main benefit: Faster experimentation, not better results
- **Recommendation:** Fix features first, then consider cloud ML for scale

---

## Recommended Next Steps

### Phase 1: Feature Research (Week 1)
1. Analyze what data we actually have access to
2. Research crypto trading feature engineering papers
3. Implement order flow features (if L2 data available)
4. Test regression approach vs classification
5. Measure feature importance and predictive power

### Phase 2: Strategy Redesign (Week 2)
1. Create separate trend-following and mean-reversion configs
2. Implement regime detection (trending vs ranging)
3. Test on different market conditions (bull/bear/sideways)
4. Focus on win rate >55% before considering deployment

### Phase 3: Advanced ML (Week 3-4)
1. Implement LSTM baseline
2. Try Transformer architecture
3. Compare with LGBM results
4. If no improvement, question viability of BTC spot scalping

### Phase 4: Reality Check (Week 4)
**Ask fundamental questions:**
- Is spot scalping viable without HFT infrastructure?
- Do retail traders have edge against market makers?
- Should we focus on swing trading (days/weeks) instead?
- Are there better instruments (futures, options, altcoins)?

---

## Critical Questions to Answer

1. **Do we have access to order book data?**
   - If NO → Scalping is very hard
   - If YES → Implement L2 features first

2. **What is our latency?**
   - If >100ms → Cannot compete on 1m timeframe
   - If <50ms → 5m/15m may be viable

3. **What is our bankroll?**
   - If <$10k → Fees will eat profits on small positions
   - If >$100k → Can afford lower win rate strategies

4. **What is our risk tolerance?**
   - If conservative → Focus on 1h+ swing trading
   - If aggressive → Need much better features or give up

---

## Conclusion

**The hard truth:** After testing 3 timeframes and 2 algorithms, we have **zero profitable strategies**.

**The problem is NOT:**
- ❌ Timeframe (tested 1m, 5m, 1h - all failed)
- ❌ Algorithm (LC and LGBM both failed)
- ❌ Hyperparameters (no amount of tuning fixes 50% win rate)
- ❌ Threshold optimization (can't optimize away lack of edge)

**The problem IS:**
- ✅ **Features have no predictive power** (lagging indicators)
- ✅ **Labels are too rare** (severe class imbalance)
- ✅ **Fundamental approach is flawed** (need complete redesign)

**Next decision point:**
1. Invest time in better features (order flow, microstructure, alternative data)
2. Try deep learning approaches (LSTM, Transformer)
3. Pivot to longer timeframes (daily swing trading)
4. Pivot to different instruments (futures, options, altcoins)
5. Accept that retail spot scalping may not be viable in 2024-2025

---

## References

- Shadow mode results: December 4-5, 2024
- Backtest period: June 2024 - December 2024
- Configs tested: `btcusdt_1m_aggressive.jsonc`, `btcusdt_5m_aggressive.jsonc`, `btcusdt_1h_aggressive.jsonc`
- Algorithm: LightGBM with 300 estimators, 0.05 learning rate
- Data: 4 years of Binance BTCUSDT (2022-2025)

---

**Document created:** December 9, 2024
**Status:** Strategy failed - redesign required
**Next action:** Feature research and strategy rethink
