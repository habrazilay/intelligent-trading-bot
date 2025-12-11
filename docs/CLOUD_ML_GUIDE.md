# Cloud ML Guide - Maximize Your $500 Credits

**Your Credits:**
- GCP: ₪982.73 ≈ **$270 USD** (88 days remaining)
- Azure: ~**$200-300 USD** free trial

**Total: ~$500 USD to invest in better models** 🎉

---

## 🎯 Strategy: Use Cloud ONLY for High-ROI Tasks

### ❌ **DON'T Waste On:**
- LGBM training (fast locally: 2-5 min)
- Small datasets (<1M samples)
- Quick experiments
- Feature engineering tests

### ✅ **DO Use For:**
1. **AutoML** - Test 100+ model combinations automatically
2. **GPU Training** - LSTM/Transformer (10x faster than CPU)
3. **Hyperparameter Tuning** - 100+ parallel experiments
4. **Large-scale Ensemble** - Combine dozens of models

---

## 📋 Usage Plan (Prioritized by ROI)

### **Phase 1: Order Flow Test (Days 0-7) - FREE**
```
Cost: $0 (run locally)

Why:
- Only 2,016 samples (7 days × 5m)
- LGBM trains in 2-5 min locally
- Save credits for later

Action: Use local as planned
```

---

### **Phase 2A: If Order Flow Works (Win Rate ≥53%)**

#### **Option 1: AutoML (HIGHEST ROI)** ⭐
```
Cost: $50-100
Time: 2-6 hours
Expected improvement: +2-5% win rate

What it does:
- Tests 100+ feature combinations
- Tests 10+ algorithms (LGBM, XGBoost, Neural Nets)
- Tests 1000+ hyperparameter sets
- Finds best model automatically

How to run:
python scripts/gcp_automl_train.py -c configs/btcusdt_5m_orderflow.jsonc --budget 50

Results:
- Baseline LGBM: 55% win rate
- AutoML: 57-60% win rate (expected)
- +2-5% improvement for $50
```

**When to use:** If order flow test shows promise (win rate ≥53%)

---

#### **Option 2: LSTM with GPU**
```
Cost: $10-30
Time: 2-4 hours
Expected improvement: +1-3% win rate

What it does:
- Learns temporal patterns automatically
- No manual feature engineering needed
- Captures long-range dependencies

How to run:
python scripts/lstm_gpu_train.py -c configs/btcusdt_5m_orderflow.jsonc --epochs 100

GPU options:
- GCP T4: $0.35/hour (recommended)
- GCP V100: $2.48/hour (overkill)
- Azure NC6: $0.90/hour

Training time: 4-8 hours on T4 = $1.40-$2.80
```

**When to use:** If AutoML doesn't improve enough, or you want to try deep learning

---

#### **Option 3: Transformer (State-of-the-Art)**
```
Cost: $30-50
Time: 4-8 hours
Expected improvement: +2-4% win rate

What it does:
- Attention mechanism learns which timesteps matter
- Best performance on time series benchmarks
- Provides uncertainty estimates

Prerequisites:
pip install pytorch-forecasting

How to run:
python scripts/transformer_train.py -c configs/btcusdt_5m_orderflow.jsonc

Training time: 6-10 hours on T4 = $2.10-$3.50
```

**When to use:** If LSTM shows promise but you want maximum performance

---

#### **Option 4: Hyperparameter Tuning (100 trials)**
```
Cost: $20-40
Time: 2-4 hours
Expected improvement: +1-2% win rate

What it does:
- Tests 100 different hyperparameter combinations
- Finds optimal LGBM settings
- Uses Bayesian optimization

How to run:
python scripts/hyperparam_search.py -c configs/btcusdt_5m_orderflow.jsonc --trials 100
```

---

### **Phase 2B: If Order Flow Fails (Win Rate <53%)**

#### **Option 5: Daily Swing Trading + AutoML**
```
Cost: $50-100
Time: 1-2 days
Expected win rate: 55-60%

Why it might work:
- 1,460 samples (4 years daily data)
- Features lagging WORK on daily trends
- AutoML finds patterns in longer timeframes

How to run:
1. Create daily dataset
2. Upload to GCP
3. Run AutoML
4. Compare with baseline
```

---

## 💰 Cost Breakdown by Experiment

| Experiment | GCP Cost | Azure Cost | Time | Win Rate Δ | ROI |
|------------|----------|------------|------|------------|-----|
| **AutoML** | $50-100 | $50-100 | 2-6h | +2-5% | ⭐⭐⭐⭐⭐ |
| **LSTM (T4)** | $10-20 | $8-15 | 2-4h | +1-3% | ⭐⭐⭐⭐ |
| **Transformer** | $30-50 | $25-40 | 4-8h | +2-4% | ⭐⭐⭐⭐ |
| **Hyperparam** | $20-40 | $15-30 | 1-3h | +1-2% | ⭐⭐⭐ |
| **Ensemble** | $15-30 | $12-25 | 1-2h | +0.5-1% | ⭐⭐ |

---

## 🚀 Quick Start

### 1. Setup GCP (15 minutes)

```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Login
gcloud auth login

# Create project
gcloud projects create itb-trading-$(date +%s)
gcloud config set project YOUR_PROJECT_ID

# Enable APIs
gcloud services enable aiplatform.googleapis.com
gcloud services enable bigquery.googleapis.com
gcloud services enable compute.googleapis.com

# Check credits
gcloud billing accounts list
```

### 2. Setup Azure (15 minutes)

```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login
az login

# Create resource group
az group create --name itb-trading --location eastus

# Enable ML
az extension add --name ml
```

### 3. Install Python Libraries

```bash
# GCP
pip install google-cloud-aiplatform google-cloud-bigquery

# Azure
pip install azure-ai-ml azure-identity

# Deep Learning
pip install tensorflow  # For LSTM
# pip install torch pytorch-forecasting  # For Transformer
```

---

## 📊 GCP vs Azure Comparison

| Feature | GCP | Azure | Winner |
|---------|-----|-------|--------|
| **AutoML Quality** | Excellent | Good | 🟢 GCP |
| **Ease of Use** | Very Easy | Complex | 🟢 GCP |
| **GPU Cost** | T4: $0.35/h | NC6: $0.90/h | 🟢 GCP |
| **Documentation** | Excellent | Good | 🟢 GCP |
| **BigQuery ML** | Yes (SQL ML!) | No | 🟢 GCP |
| **Overall** | Better for ITB | Good backup | 🟢 **Use GCP First** |

**Recommendation:** Start with GCP, use Azure as backup if you run out of credits.

---

## 💡 Tips to NOT Waste Credits

### 1. Always Use Preemptible/Spot Instances
```bash
# GCP Preemptible (60-80% cheaper)
gcloud compute instances create lstm-vm \
  --machine-type=n1-standard-4 \
  --accelerator=type=nvidia-tesla-t4,count=1 \
  --preemptible

# Azure Spot Instances
az vm create \
  --resource-group itb-trading \
  --name lstm-vm \
  --size Standard_NC6 \
  --priority Spot \
  --max-price 0.30
```

**Savings:** $1/hour → $0.20/hour

### 2. Delete Resources When Done
```bash
# GCP
gcloud compute instances delete lstm-vm

# Azure
az vm delete --resource-group itb-trading --name lstm-vm
```

**Important:** VMs charge by the hour even when stopped!

### 3. Set Budget Alerts
```bash
# GCP - Alert at $50, $100, $150
gcloud billing budgets create \
  --billing-account=BILLING_ACCOUNT_ID \
  --display-name="ITB Trading Budget" \
  --budget-amount=200 \
  --threshold-rule=percent=25 \
  --threshold-rule=percent=50 \
  --threshold-rule=percent=75
```

### 4. Use Cheapest Region
```
GCP regions (sorted by cost):
1. us-central1 (Iowa) - CHEAPEST
2. us-east1 (South Carolina)
3. us-west1 (Oregon)
4. europe-west1 (Belgium)
5. asia-southeast1 (Singapore) - MOST EXPENSIVE

Always use us-central1 unless you need lower latency
```

### 5. Monitor Costs Daily
```bash
# GCP
gcloud billing accounts list
gcloud alpha billing accounts get-iam-policy BILLING_ACCOUNT_ID

# Azure
az consumption usage list --start-date 2024-12-01

# Or use web console:
# GCP: console.cloud.google.com/billing
# Azure: portal.azure.com → Cost Management
```

---

## 🎁 Free Tier Benefits (Use These!)

### GCP Free Tier (Always Free)
- BigQuery: 1 TB queries/month
- Cloud Storage: 5 GB/month
- Compute Engine: 1 f1-micro instance/month

### Azure Free Tier
- 750 hours B1S VM/month
- 5 GB storage
- 1 million requests

**Use these for:**
- Data storage (free!)
- Small experiments
- Monitoring dashboards

---

## 📈 Expected Results by Investment

### Conservative Budget ($100-150):
```
Phase 1: Local testing - $0
Phase 2: AutoML GCP - $50
Phase 3: LSTM GPU - $30
Phase 4: Hyperparameter tuning - $20
Total: $100

Expected outcome:
- Baseline: 55% win rate (order flow)
- After cloud ML: 57-60% win rate
- Improvement: +2-5%
- ROI: If profitable, pays for itself in weeks
```

### Aggressive Budget ($300-400):
```
Phase 1: Local - $0
Phase 2: AutoML GCP - $100
Phase 3: AutoML Azure - $100
Phase 4: LSTM + Transformer - $50
Phase 5: Ensemble - $30
Phase 6: Hyperparameter tuning - $20
Total: $300

Expected outcome:
- Baseline: 55% win rate
- After cloud ML: 58-62% win rate
- Improvement: +3-7%
- ROI: Higher win rate = more profit
```

---

## 🎯 Decision Framework

### After Order Flow Test (Day 7):

```
IF win_rate >= 55%:
    → Invest $100 in AutoML (high confidence)
    → If AutoML improves +2% → Invest another $50 in LSTM
    → If LSTM improves +1% → Go live with $100

ELIF win_rate 53-55%:
    → Invest $50 in AutoML (medium confidence)
    → If AutoML improves to 55%+ → Invest more
    → Else → Pivot to daily

ELIF win_rate < 53%:
    → DON'T waste money on cloud
    → Pivot to daily swing trading
    → Then try AutoML on daily data
```

---

## ⚠️ Common Mistakes to Avoid

1. **Running expensive VMs 24/7**
   - ❌ Leaving V100 GPU running overnight: $60 wasted
   - ✅ Use preemptible, delete when done

2. **Not setting budget alerts**
   - ❌ Accidentally spending $500 in 2 days
   - ✅ Set alerts at $50, $100, $150

3. **Using wrong region**
   - ❌ Using asia-southeast1: 2x cost
   - ✅ Using us-central1: cheapest

4. **Training on cloud when local is fine**
   - ❌ Running LGBM on cloud: unnecessary
   - ✅ Only use cloud for GPU/AutoML

5. **Not comparing with baseline**
   - ❌ Spending $100 without knowing if it's better
   - ✅ Always compare with local LGBM results

---

## 📝 Tracking Your Spending

Create a simple spreadsheet:

| Date | Service | Experiment | Cost | Win Rate Before | Win Rate After | Worth It? |
|------|---------|------------|------|-----------------|----------------|-----------|
| Dec 17 | GCP AutoML | Order flow | $50 | 55% | 57% | ✅ YES (+2%) |
| Dec 18 | GCP LSTM | GPU training | $15 | 57% | 58% | ✅ YES (+1%) |
| Dec 19 | GCP Hyperparam | 100 trials | $25 | 58% | 58.5% | ⚠️ MAYBE (+0.5%) |

**Total spent:** $90
**Total improvement:** +3.5% win rate
**ROI:** EXCELLENT

---

## 🏁 Summary

**Best Use of Your $500:**

1. **First $50:** AutoML on order flow data (if test succeeds)
2. **Next $30:** LSTM with GPU (if AutoML works)
3. **Next $20:** Hyperparameter tuning
4. **Reserve $100:** For daily strategy if scalping fails
5. **Save $300:** For production deployment, monitoring, etc.

**Expected Timeline:**
- Day 0-7: Local testing (free)
- Day 7: AutoML if promising ($50)
- Day 8: LSTM if AutoML works ($30)
- Day 9-10: Shadow mode with best model
- Day 11+: Live trading or pivot

**Expected Outcome:**
- Baseline: 55% win rate (order flow local)
- After $80-100 cloud: 57-60% win rate
- If successful: System pays for cloud costs in 1-2 weeks

---

**Created:** December 10, 2024
**Your Credits:** $270 GCP + $200-300 Azure = $500 total
**Strategy:** Invest smart, track ROI, don't waste on low-value tasks
