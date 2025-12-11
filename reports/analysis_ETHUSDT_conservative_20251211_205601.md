# Pipeline Analysis Report

**Symbol:** `ETHUSDT`
**Strategy:** `conservative`
**Timeframe:** `1m`
**Generated:** 2025-12-11 20:55:58
**Data Period:** 2025-09-29 20:10:00+00:00 to 2025-12-11 18:34:00+00:00
**Total Candles:** 105,025

---

## Model Metrics

| Model | AUC | Precision | Recall | F1 | AP | Status |
|-------|-----|-----------|--------|----|----|--------|
| high_06_24_lc | 0.626 | 0.563 | 0.006 | 0.012 | 0.099 | WARN |
| high_06_24_lgbm | 0.942 | 0.964 | 0.070 | 0.131 | 0.681 | OK |
| low_06_24_lc | 0.643 | 0.446 | 0.005 | 0.010 | 0.105 | WARN |
| low_06_24_lgbm | 0.947 | 0.987 | 0.054 | 0.102 | 0.697 | OK |
| high_06_24_lc | 0.626 | 0.563 | 0.006 | 0.012 | 0.099 | WARN |
| high_06_24_lgbm | 0.942 | 0.970 | 0.070 | 0.130 | 0.675 | OK |
| low_06_24_lc | 0.642 | 0.446 | 0.005 | 0.010 | 0.105 | WARN |
| low_06_24_lgbm | 0.944 | 0.989 | 0.053 | 0.100 | 0.691 | OK |
| high_06_24_lc | 0.626 | 0.563 | 0.006 | 0.012 | 0.099 | WARN |
| high_06_24_lgbm | 0.944 | 0.968 | 0.071 | 0.133 | 0.682 | OK |
| low_06_24_lc | 0.642 | 0.446 | 0.005 | 0.010 | 0.105 | WARN |
| low_06_24_lgbm | 0.946 | 0.989 | 0.055 | 0.104 | 0.695 | OK |

---

## Best Threshold Combination

| Parameter | Value |
|-----------|-------|
| **Buy Threshold** | 0.006 |
| **Sell Threshold** | -0.006 |
| **Total Trades** | 3,281 |
| **Win Rate** | 60.2% |
| **Total Profit** | $19,911.82 |
| **Profit %** | 575.6% |
| **Avg Profit/Trade** | $6.07 (0.20%) |


### Top 5 Threshold Combinations

| Buy | Sell | Trades | Win% | Profit% | Profit/T |
|-----|------|--------|------|---------|----------|
| 0.006 | -0.006 | 3281 | 60.2% | 575.6% | 0.20% |
| 0.005 | -0.006 | 3420 | 59.4% | 573.9% | 0.20% |
| 0.006 | -0.005 | 3416 | 60.0% | 572.5% | 0.20% |
| 0.006 | -0.004 | 3563 | 59.8% | 572.2% | 0.20% |
| 0.005 | -0.004 | 3721 | 58.9% | 570.7% | 0.20% |

---

## Trade Performance

| Strategy | Trades | Wins | Win Rate | Total Profit % | Avg/Trade | Max Wins | Max Losses |
|----------|--------|------|----------|----------------|-----------|----------|------------|
| **LONG** | 3870 | 2320 | 59.9% | 570.3% | 0.15% | 16 | 7 |
| **SHORT** | 3870 | 2224 | 57.5% | 587.0% | 0.15% | 16 | 11 |
| **COMBINED** | 7740 | 4544 | 58.7% | 1157.4% | 0.15% | 18 | 14 |

---

## Risk Metrics

| Metric | Value | Status |
|--------|-------|--------|
| **Sharpe Ratio** | 0.30 | BAD |
| **Sortino Ratio** | 1.08 | WARN |
| **Profit Factor** | 3.52 | OK |

### Drawdown Analysis

| Metric | Value |
|--------|-------|
| **Max Drawdown** | -0.24% ($-63.88) |
| **Avg Drawdown** | -0.05% |
| **Current Drawdown** | 0.00% |
| **Drawdown Periods** | 815 |
| **Longest DD** | 101 candles |


---

## Walk-Forward Validation

| Fold | Train Period | Test Period | Train Win% | Test Win% | Train Profit% | Test Profit% | Degradation |
|------|--------------|-------------|------------|-----------|---------------|--------------|-------------|
| 1 | 2025-09-29..2025-10-10 | 2025-10-10..2025-10-14 | 55.0% | 67.3% | 73.5% | 150.6% | -22.3%  |
| 2 | 2025-10-14..2025-10-24 | 2025-10-24..2025-10-29 | 60.7% | 51.3% | 173.8% | 24.6% | 15.5%  |
| 3 | 2025-10-29..2025-11-08 | 2025-11-08..2025-11-12 | 58.3% | 50.5% | 170.3% | 38.8% | 13.2%  |
| 4 | 2025-11-12..2025-11-22 | 2025-11-22..2025-11-27 | 61.7% | 58.1% | 275.8% | 65.2% | 5.8%  |
| 5 | 2025-11-27..2025-12-07 | 2025-12-07..2025-12-11 | 56.4% | 62.4% | 108.6% | 75.1% | -10.7%  |

**Average Degradation:** 0.3%

---

## Warnings

- high_06_24_lc: AUC fraco (0.626 < 0.7)
- high_06_24_lc: Recall quase zero (0.006) - modelo muito conservador
- low_06_24_lc: AUC fraco (0.643 < 0.7)
- low_06_24_lc: Recall quase zero (0.005) - modelo muito conservador
- high_06_24_lc: AUC fraco (0.626 < 0.7)
- high_06_24_lc: Recall quase zero (0.006) - modelo muito conservador
- low_06_24_lc: AUC fraco (0.642 < 0.7)
- low_06_24_lc: Recall quase zero (0.005) - modelo muito conservador
- high_06_24_lc: AUC fraco (0.626 < 0.7)
- high_06_24_lc: Recall quase zero (0.006) - modelo muito conservador
- low_06_24_lc: AUC fraco (0.642 < 0.7)
- low_06_24_lc: Recall quase zero (0.005) - modelo muito conservador
- Large AUC gap between LGBM (0.942) and LC (0.626) for high_06_24 - possible overfitting
- Large AUC gap between LGBM (0.947) and LC (0.643) for low_06_24 - possible overfitting
- Large AUC gap between LGBM (0.942) and LC (0.626) for high_06_24 - possible overfitting
- Large AUC gap between LGBM (0.944) and LC (0.643) for low_06_24 - possible overfitting
- Large AUC gap between LGBM (0.944) and LC (0.626) for high_06_24 - possible overfitting
- Large AUC gap between LGBM (0.946) and LC (0.643) for low_06_24 - possible overfitting
- High consecutive losses (14) - risk of ruin
- Low Sharpe ratio (0.30) - poor risk-adjusted returns

---

## Summary

**Overall Verdict:** **PROFITABLE**

- Total return: **1157.4%** over 7740 trades
- Win rate: **58.7%**
- Risk-adjusted: Sharpe 0.30, Sortino 1.08
- Max drawdown: **-0.2%** (if applicable)
- Walk-forward stability: 0.3% degradation


---

*Generated by ITB Pipeline Analyzer*
