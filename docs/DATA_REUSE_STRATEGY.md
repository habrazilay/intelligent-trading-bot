# 📊 Data Reuse Strategy - Avoid Unnecessary Downloads

## 🎯 Overview

This guide explains how to **reuse existing data** and avoid re-downloading/reprocessing when running different configurations.

---

## 🗂️ File Hierarchy & Reusability

### **Raw Data (Always Reuse)**

```
DATA_ITB_1m/
├── BTCUSDT/
│   ├── klines_2024-06.csv        ✅ REUSE (raw Binance data)
│   ├── klines_2024-07.csv        ✅ REUSE
│   ├── klines_2024-08.csv        ✅ REUSE
│   └── ...
```

**When to reuse:**
- ✅ **ALWAYS** - Raw klines never change
- Only re-download if you want more recent data or different date range

**How to skip download:**
```bash
# If DATA_ITB_1m/BTCUSDT/ exists with klines, download is skipped
bash scripts/train_aggressive_smart.sh  # Auto-detects and skips
```

---

### **Merged Data (Conditional Reuse)**

```
DATA_ITB_1m/
├── data.csv                      ⚠️ REUSE IF: Same klines + same merge params
```

**When to reuse:**
- ✅ If klines haven't changed
- ✅ If merge parameters are identical (interpolation, date range)

**When to regenerate:**
- ❌ Added new klines (more recent data)
- ❌ Changed `merge_interpolate` settings
- ❌ Changed date range

**How to force regenerate:**
```bash
rm DATA_ITB_1m/data.csv
python -m scripts.merge -c configs/btcusdt_1m_aggressive.jsonc
```

---

### **Features (Conditional Reuse)**

```
DATA_ITB_1m/
├── features.csv                  ⚠️ REUSE IF: Same feature set
```

**When to reuse:**
- ✅ If `feature_sets` in config are **identical**
- ✅ Example: Conservative and Aggressive use same base features (SMA, RSI, ATR)

**When to regenerate:**
- ❌ Added new features (e.g., `vol_regime`, `spread_pct_3`)
- ❌ Changed feature windows (e.g., SMA_5 → SMA_7)
- ❌ Changed feature generators

**Conservative vs Aggressive Features:**

| Feature | Conservative | Aggressive | Compatible? |
|---------|-------------|-----------|-------------|
| SMA | [5,10,20,60] | [3,5,10,20,60] | ❌ Different windows |
| RSI | [14] | [14] | ✅ Same |
| ATR | [14] | [14] | ✅ Same |
| LINEARREG_SLOPE | [10,20,60] | [3,5,10,20] | ❌ Different windows |
| vol_regime | ❌ No | ✅ Yes | ❌ Aggressive has extra |
| spread_pct_* | ❌ No | ✅ Yes | ❌ Aggressive has extra |

**Verdict:** Conservative and Aggressive **CANNOT share** `features.csv` (different features)

**How to check if features match:**
```bash
# Check which features exist
head -1 DATA_ITB_1m/features.csv | tr ',' '\n' | grep -E "SMA|regime|spread"

# If missing vol_regime or spread_pct_3, regenerate:
rm DATA_ITB_1m/features.csv
python -m scripts.features -c configs/btcusdt_1m_aggressive.jsonc
```

---

### **Labels (NEVER Reuse Across Strategies)**

```
DATA_ITB_1m/
├── matrix.csv                    ❌ Conservative labels (high_05_60, low_05_60)
├── matrix_aggressive.csv         ✅ Aggressive labels (high_020_10, low_020_10)
```

**When to reuse:**
- ✅ **NEVER** across different strategies (different targets)
- ✅ Only if running **same strategy** multiple times

**Why different files:**
- Conservative targets: 0.5% in 60 min
- Aggressive targets: 0.2% in 10 min
- Completely different labels → different files

**Config setup:**
```jsonc
// Conservative
{
  "matrix_file_name": "matrix.csv",
  "labels": ["high_05_60", "low_05_60"]
}

// Aggressive
{
  "matrix_file_name": "matrix_aggressive.csv",  // Different file!
  "labels": ["high_020_10", "low_020_10"]
}
```

---

### **Models (NEVER Reuse Across Strategies)**

```
MODELS_LGBM_V1/                   ❌ Conservative models
├── high_05_60_lgbm.pickle
└── low_05_60_lgbm.pickle

MODELS_AGGRESSIVE_V1/             ✅ Aggressive models
├── high_020_10_lgbm_aggressive.pickle
└── low_020_10_lgbm_aggressive.pickle
```

**When to reuse:**
- ✅ **NEVER** across strategies (trained on different labels)
- ✅ Only for the **same strategy**

**Why separate folders:**
- Different labels → different models
- Conservative predicts 0.5%, Aggressive predicts 0.2%
- Mixing models would give wrong predictions

---

### **Predictions & Signals (NEVER Reuse Across Strategies)**

```
DATA_ITB_1m/
├── predictions.csv               ❌ Conservative predictions
├── predictions_aggressive.csv    ✅ Aggressive predictions
├── signals.csv                   ❌ Conservative signals
├── signals_aggressive.csv        ✅ Aggressive signals
```

**When to reuse:**
- ✅ **NEVER** across strategies
- Each strategy has its own predictions/signals

---

## 🔄 Shared vs Separate Data Strategy

### **✅ Recommended Setup: Shared Data Folder**

```jsonc
// Conservative Config
{
  "data_folder": "./DATA_ITB_1m",
  "matrix_file_name": "matrix.csv",
  "predict_file_name": "predictions.csv",
  "signal_file_name": "signals.csv",
  "model_folder": "MODELS_LGBM_V1"
}

// Aggressive Config
{
  "data_folder": "./DATA_ITB_1m",              // SAME folder
  "matrix_file_name": "matrix_aggressive.csv", // DIFFERENT file
  "predict_file_name": "predictions_aggressive.csv",
  "signal_file_name": "signals_aggressive.csv",
  "model_folder": "MODELS_AGGRESSIVE_V1"       // DIFFERENT folder
}
```

**Benefits:**
- ✅ Shares klines (no re-download)
- ✅ Shares data.csv (no re-merge)
- ✅ Can share features.csv if compatible
- ✅ Keeps models/predictions separate (no confusion)

**Folder structure:**
```
DATA_ITB_1m/
├── BTCUSDT/
│   ├── klines_*.csv              # Shared
├── data.csv                      # Shared
├── features.csv                  # Shared (if compatible)
├── matrix.csv                    # Conservative only
├── matrix_aggressive.csv         # Aggressive only
├── predictions.csv               # Conservative only
├── predictions_aggressive.csv    # Aggressive only
├── signals.csv                   # Conservative only
└── signals_aggressive.csv        # Aggressive only

MODELS_LGBM_V1/                   # Conservative models
MODELS_AGGRESSIVE_V1/             # Aggressive models
```

---

## 🚀 Smart Training Script

Use the smart script that auto-detects what can be reused:

```bash
# Automatically skips steps if files exist
bash scripts/train_aggressive_smart.sh
```

**What it does:**
1. ✅ **SKIP** download if klines exist
2. ✅ **SKIP** merge if data.csv exists
3. ⚠️ **CHECK** features.csv for aggressive features (vol_regime, spread)
   - If missing → regenerate
   - If present → reuse
4. ❌ **ALWAYS NEW:** matrix, models, predictions, signals

---

## 🔧 Manual Control

### **Force Re-download:**
```bash
rm -rf DATA_ITB_1m/BTCUSDT/
python -m scripts.download_binance -c configs/btcusdt_1m_aggressive.jsonc
```

### **Force Re-merge:**
```bash
rm DATA_ITB_1m/data.csv
python -m scripts.merge -c configs/btcusdt_1m_aggressive.jsonc
```

### **Force Re-feature:**
```bash
rm DATA_ITB_1m/features.csv
python -m scripts.features -c configs/btcusdt_1m_aggressive.jsonc
```

### **Clean Everything (Fresh Start):**
```bash
rm -rf DATA_ITB_1m/ MODELS_AGGRESSIVE_V1/
bash scripts/train_aggressive_smart.sh
```

---

## 📊 Typical Workflow

### **First Time (Conservative Mode):**
```bash
# Downloads everything fresh
python -m scripts.download_binance -c configs/btcusdt_1m_dev_lgbm.jsonc
python -m scripts.merge -c configs/btcusdt_1m_dev_lgbm.jsonc
python -m scripts.features -c configs/btcusdt_1m_dev_lgbm.jsonc
python -m scripts.labels -c configs/btcusdt_1m_dev_lgbm.jsonc
python -m scripts.train -c configs/btcusdt_1m_dev_lgbm.jsonc
# ... etc
```

**Result:**
- `DATA_ITB_1m/` created with klines, data.csv, features.csv
- `MODELS_LGBM_V1/` created with conservative models

### **Second Time (Aggressive Mode):**
```bash
# Reuses DATA_ITB_1m/ folder
bash scripts/train_aggressive_smart.sh
```

**What happens:**
1. ✅ SKIP download (klines exist)
2. ✅ SKIP merge (data.csv exists)
3. ⚠️ CHECK features:
   - If features.csv has `vol_regime` → reuse
   - If missing → regenerate
4. ❌ NEW: matrix_aggressive.csv (different labels)
5. ❌ NEW: MODELS_AGGRESSIVE_V1/ (different models)
6. ❌ NEW: predictions_aggressive.csv, signals_aggressive.csv

**Time saved:** ~20-30 minutes (no download/merge)

---

## ⚡ Performance Comparison

| Task | Fresh Download | Smart Reuse | Time Saved |
|------|---------------|-------------|------------|
| Download | 20-30 min | 0 sec ⚡ | 100% |
| Merge | 2-3 min | 0 sec ⚡ | 100% |
| Features | 5-10 min | 0-10 min | 0-100% |
| Labels | 3-5 min | 3-5 min | 0% |
| Train | 5-10 min | 5-10 min | 0% |
| **TOTAL** | **40-60 min** | **10-30 min** | **50-75%** |

---

## ✅ Best Practices

1. **Use shared data folder** for all 1m strategies
2. **Separate model folders** per strategy
3. **Unique filenames** for labels/predictions/signals
4. **Use smart script** to auto-detect reusable files
5. **Only regenerate** features if feature set changed

---

## 🐛 Troubleshooting

### **Error: "Features missing column 'vol_regime'"**

**Cause:** Trying to use old features.csv from conservative mode

**Fix:**
```bash
rm DATA_ITB_1m/features.csv
python -m scripts.features -c configs/btcusdt_1m_aggressive.jsonc
```

### **Error: "No such file: matrix_aggressive.csv"**

**Cause:** Config has wrong matrix filename

**Fix:** Check config has:
```jsonc
"matrix_file_name": "matrix_aggressive.csv"
```

### **Signals look wrong (too few/many trades)**

**Cause:** Using wrong predictions file (conservative vs aggressive)

**Fix:** Verify config has unique filenames:
```jsonc
"predict_file_name": "predictions_aggressive.csv",
"signal_file_name": "signals_aggressive.csv"
```

---

**Last Updated:** 2025-12-09
**Related Docs:**
- `docs/AGGRESSIVE_MODE.md`
- `scripts/train_aggressive_smart.sh`
