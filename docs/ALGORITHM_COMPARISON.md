# 🤖 Algorithm Comparison: LC vs LGBM vs Others

## 📋 Overview

This guide explains when to use each algorithm in the ITB and how to compare their performance.

---

## 🔬 Supported Algorithms

### **1. LC - Logistic Classifier (Logistic Regression)**

**Type:** Linear model
**Library:** scikit-learn `LogisticRegression`

**Pros:**
- ✅ Very fast training (seconds)
- ✅ Low memory footprint
- ✅ High interpretability (feature coefficients)
- ✅ Unlikely to overfit
- ✅ Works well with few samples (<10K)

**Cons:**
- ❌ Linear decision boundary only
- ❌ Needs feature scaling
- ❌ Requires manual feature engineering for interactions
- ❌ Lower accuracy on complex patterns

**Best For:**
- Quick baselines
- Interpretable models
- Small datasets
- Regulatory/compliance needs

**Config Example:**
```jsonc
{
  "name": "lc",
  "algo": "lc",
  "params": {"is_scale": true},  // MUST scale features!
  "train": {
    "penalty": "l2",           // L1 or L2 regularization
    "C": 1.0,                  // Inverse regularization (lower = stronger)
    "solver": "sag",           // sag, saga, lbfgs, liblinear
    "max_iter": 100,
    "class_weight": "balanced" // Handle imbalanced labels
  }
}
```

---

### **2. LGBM - LightGBM (Gradient Boosting)**

**Type:** Ensemble (gradient boosted decision trees)
**Library:** `lightgbm`

**Pros:**
- ✅ State-of-the-art accuracy for tabular data
- ✅ Captures non-linear interactions automatically
- ✅ No feature scaling needed
- ✅ Fast inference (prediction)
- ✅ Handles missing values natively
- ✅ Built-in feature importance

**Cons:**
- ❌ Slower training (minutes vs seconds)
- ❌ More memory intensive
- ❌ Can overfit if not tuned properly
- ❌ Less interpretable than linear models
- ❌ Needs more data (50K+ samples ideal)

**Best For:**
- Production models
- Maximum accuracy
- Complex feature interactions
- Large datasets

**Config Example:**
```jsonc
{
  "name": "lgbm",
  "algo": "lgbm",
  "params": {},  // No scaling needed!
  "train": {
    "num_leaves": 31,           // Tree complexity (default: 31)
    "learning_rate": 0.05,      // Learning rate (lower = more conservative)
    "n_estimators": 300,        // Number of trees
    "max_depth": -1,            // Max tree depth (-1 = no limit)
    "min_child_samples": 20,    // Min samples per leaf (prevents overfitting)
    "subsample": 0.8,           // Row sampling fraction
    "colsample_bytree": 0.8,    // Feature sampling fraction
    "reg_alpha": 0.0,           // L1 regularization
    "reg_lambda": 0.0,          // L2 regularization
    "class_weight": "balanced"
  }
}
```

---

### **3. SVC - Support Vector Classifier**

**Type:** Kernel-based model
**Library:** scikit-learn `SVC`

**Pros:**
- ✅ Effective in high-dimensional spaces
- ✅ Works well with clear margin of separation
- ✅ Memory efficient (uses support vectors only)

**Cons:**
- ❌ Very slow on large datasets (>10K samples)
- ❌ Needs feature scaling
- ❌ Difficult to tune (C, gamma, kernel)
- ❌ Not recommended for time series

**Best For:**
- Small datasets (<5K samples)
- High-dimensional problems (many features, few samples)
- Text classification (not trading)

**Config Example:**
```jsonc
{
  "name": "svc",
  "algo": "svc",
  "params": {"is_scale": true},
  "train": {
    "C": 1.0,
    "kernel": "rbf",
    "gamma": "scale"
  }
}
```

---

## 📊 Performance Comparison (Expected)

Based on typical trading ML scenarios:

| Algorithm | Training Time | Accuracy | Sharpe Ratio | Overfitting Risk |
|-----------|--------------|----------|--------------|-----------------|
| **LC** | ⚡ 30s | 📊 53-55% | 💰 0.3-0.5 | 🟢 Low |
| **LGBM** | ⏱️ 5-10 min | 📈 57-62% | 💸 0.6-0.9 | 🟡 Medium |
| **SVC** | 🐌 20+ min | 📉 50-53% | 💵 0.2-0.4 | 🔴 High |

*Note: Results vary based on dataset size, features, and tuning.*

---

## 🧪 How to Compare Algorithms

### **Step 1: Train Multiple Algorithms**

Use the ensemble config to train both LC and LGBM:

```bash
# Download and prepare data
python -m scripts.download_binance -c configs/btcusdt_1m_aggressive_ensemble.jsonc
python -m scripts.merge -c configs/btcusdt_1m_aggressive_ensemble.jsonc
python -m scripts.features -c configs/btcusdt_1m_aggressive_ensemble.jsonc
python -m scripts.labels -c configs/btcusdt_1m_aggressive_ensemble.jsonc

# Train BOTH algorithms
python -m scripts.train -c configs/btcusdt_1m_aggressive_ensemble.jsonc

# This will create:
# - MODELS_AGGRESSIVE_ENSEMBLE/high_020_10_lc_baseline.pickle
# - MODELS_AGGRESSIVE_ENSEMBLE/high_020_10_lgbm_production.pickle
# - MODELS_AGGRESSIVE_ENSEMBLE/low_020_10_lc_baseline.pickle
# - MODELS_AGGRESSIVE_ENSEMBLE/low_020_10_lgbm_production.pickle
```

### **Step 2: Compare Training Metrics**

Check the training output file:

```bash
cat MODELS_AGGRESSIVE_ENSEMBLE/prediction-metrics.txt
```

Look for:
- **Accuracy:** Should be >50% (better than random)
- **Precision:** True positives / (true positives + false positives)
- **Recall:** True positives / (true positives + false negatives)
- **F1 Score:** Harmonic mean of precision and recall

**Expected:**
```
LC Baseline:
  Accuracy: 54%
  F1 Score: 0.52

LGBM Production:
  Accuracy: 59%
  F1 Score: 0.57
```

### **Step 3: Backtest Both Models**

```bash
# Generate predictions
python -m scripts.predict -c configs/btcusdt_1m_aggressive_ensemble.jsonc

# Generate signals for both models
python -m scripts.signals -c configs/btcusdt_1m_aggressive_ensemble.jsonc

# Simulate trading
python -m scripts.simulate -c configs/btcusdt_1m_aggressive_ensemble.jsonc
```

This will run TWO simulations (one for LC, one for LGBM).

### **Step 4: Compare Backtest Results**

Check the simulation output:

```
LC Baseline Results:
  Total Trades: 450
  Win Rate: 52%
  Total PnL: +12.5 USDT
  Sharpe Ratio: 0.45
  Max Drawdown: -8.2%

LGBM Production Results:
  Total Trades: 480
  Win Rate: 58%
  Total PnL: +28.7 USDT
  Sharpe Ratio: 0.72
  Max Drawdown: -6.5%
```

### **Step 5: Shadow Mode Test**

Deploy both models to shadow mode and compare after 7 days:

```bash
# LC
python -m service.server -c configs/btcusdt_1m_lc.jsonc

# LGBM (separate process)
python -m service.server -c configs/btcusdt_1m_aggressive.jsonc
```

---

## 🎯 Decision Matrix

| Your Situation | Recommended Algorithm |
|----------------|----------------------|
| "I need results NOW" | LC (fast baseline) |
| "I want the best model possible" | LGBM |
| "I have <10K training samples" | LC (less overfitting) |
| "I have >100K training samples" | LGBM (learns better) |
| "I need to explain every decision" | LC (interpretable coefficients) |
| "I just need it to work" | LGBM (less feature engineering) |
| "Budget: Limited CPU/RAM" | LC (lightweight) |
| "Budget: Cloud GPUs available" | LGBM (can parallelize) |
| "Data has complex patterns" | LGBM (non-linear) |
| "Data is clean and linear" | LC (simpler is better) |

---

## 💡 Pro Tips

### **1. Always Start with LC as Baseline**

Train LC first to:
- ✅ Verify problem is solvable (LC should be >50% accuracy)
- ✅ Identify which features are important (check coefficients)
- ✅ Set a performance baseline to beat

**If LC fails (<50% accuracy):**
- 🔴 Problem: Your features don't have signal
- 🛠️ Fix: Add better features or check labels

### **2. Feature Importance Comparison**

**LC Coefficients:**
```python
# After training LC model
import pickle
model = pickle.load(open('MODELS/.../high_020_10_lc_baseline.pickle', 'rb'))
coefs = model.coef_[0]

# Positive = bullish, Negative = bearish
# close_SMA_5: +0.42  → Strong bullish indicator
# close_RSI_14: -0.15 → Weak bearish when high
```

**LGBM Feature Importance:**
```python
# After training LGBM model
import pickle
model = pickle.load(open('MODELS/.../high_020_10_lgbm_production.pickle', 'rb'))
importance = model.feature_importances_

# Shows which features are used most
# close_SMA_5: 850  → Most important
# vol_regime: 620   → Second most important
```

### **3. Ensemble Both Models (Advanced)**

Combine LC + LGBM for best results:

```jsonc
// In signal_sets
{
  "generator": "combine",
  "config": {
    "columns": ["trade_score_lc", "trade_score_lgbm"],
    "names": "trade_score_ensemble",
    "combine": "average"  // or "weighted_average"
  }
}
```

**Why this works:**
- LC catches linear patterns
- LGBM catches non-linear patterns
- Averaging reduces variance (more stable)

### **4. Hyperparameter Tuning**

**LC Tuning:**
- `C` (regularization): Try [0.1, 1.0, 10.0]
  - Lower C = simpler model (less overfit)
  - Higher C = complex model (may overfit)

**LGBM Tuning:**
- `num_leaves`: Try [15, 31, 63]
  - Lower = simpler trees
  - Higher = more complex (may overfit)
- `learning_rate`: Try [0.01, 0.05, 0.1]
  - Lower = more conservative (needs more `n_estimators`)
  - Higher = faster convergence (may overfit)

---

## 📚 Further Reading

- **LightGBM Docs:** https://lightgbm.readthedocs.io/
- **Scikit-learn Logistic Regression:** https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html
- **Kaggle: Gradient Boosting for Trading:** https://www.kaggle.com/code (search "trading lgbm")

---

## ✅ Summary

| Question | Answer |
|----------|--------|
| **What should I use for production?** | LGBM (best accuracy) |
| **What should I use for quick tests?** | LC (fast baseline) |
| **Can I use both?** | Yes! Train both and compare |
| **Which is easier to tune?** | LC (fewer hyperparameters) |
| **Which needs more data?** | LGBM (50K+ samples ideal) |

---

**Default Recommendation:**
1. Start with LC to validate features
2. Switch to LGBM for production
3. Optionally ensemble both for maximum robustness

**Current ITB Setup:**
- Most configs use LGBM by default
- LC is commented out in samples
- Aggressive mode uses LGBM only

**To Compare:**
- Use `configs/btcusdt_1m_aggressive_ensemble.jsonc`
- Trains both simultaneously
- Compare results before choosing

---

**Last Updated:** 2025-12-09
**Related Docs:**
- `docs/AGGRESSIVE_MODE.md`
- `docs/SHADOW_MODE_ANALYSIS.md`
