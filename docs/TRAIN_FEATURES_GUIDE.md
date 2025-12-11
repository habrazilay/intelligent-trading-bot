# Train Features Guide

**Objetivo:** Otimizar features para melhorar win rate de 50% → 55-60%

---

## 📊 Features por Estratégia

### Conservative (Azure - BTCUSDT/ETHUSDT)
```python
"train_features": [
    # Trend (Médias Móveis)
    "close_SMA_5","close_SMA_10","close_SMA_20","close_SMA_60","close_SMA_120",
    "close_EMA_12","close_EMA_26",

    # Momentum
    "close_RSI_14",
    "close_LINEARREG_SLOPE_10","close_LINEARREG_SLOPE_20","close_LINEARREG_SLOPE_60",
    "close_MOM_10",

    # Volatility
    "high_low_close_ATR_14","close_STDDEV_20","close_STDDEV_60",
    "close_BBANDS_20_upper","close_BBANDS_20_middle","close_BBANDS_20_lower",

    # Volume (NOVO - CRÍTICO!)
    "close_volume_OBV_1","volume_SMA_20"
]
```

**Total:** 20 features
**Foco:** Proven indicators, avoid overfitting

---

### Aggressive (GCP - SOLUSDT/BNBUSDT/XRPUSDT)
```python
"train_features": [
    # Trend
    "close_SMA_5","close_SMA_10","close_SMA_20","close_SMA_60",
    "close_EMA_5","close_EMA_12","close_EMA_26",

    # Momentum
    "close_RSI_7","close_RSI_14",  # 2 RSI windows para mais sensibilidade
    "close_LINEARREG_SLOPE_5","close_LINEARREG_SLOPE_10","close_LINEARREG_SLOPE_20",
    "close_MOM_5","close_MOM_10",
    "high_low_close_CCI_14",       # Commodity Channel Index
    "close_WILLR_14",              # Williams %R

    # Volatility
    "high_low_close_ATR_7","high_low_close_ATR_14",
    "close_STDDEV_10","close_STDDEV_20",
    "close_BBANDS_20_upper","close_BBANDS_20_middle","close_BBANDS_20_lower",

    # Volume
    "close_volume_OBV_1","volume_SMA_10","volume_SMA_20",
    "high_low_close_volume_MFI_14",  # Money Flow Index

    # MACD (trend + momentum combined)
    "close_MACD_1_macd","close_MACD_1_macdsignal","close_MACD_1_macdhist"
]
```

**Total:** 31 features
**Foco:** More features, more complexity, better for LGBM

---

### Quick Profit (Scalping)
```python
"train_features": [
    # Fast Trend (janelas curtas)
    "close_SMA_3","close_SMA_5","close_SMA_10","close_SMA_20",
    "close_EMA_3","close_EMA_5","close_EMA_12",

    # Fast Momentum
    "close_RSI_7","close_RSI_14",
    "close_LINEARREG_SLOPE_3","close_LINEARREG_SLOPE_5","close_LINEARREG_SLOPE_10",
    "close_MOM_3","close_MOM_5",
    "high_low_close_CCI_10",

    # Fast Volatility
    "high_low_close_ATR_7","high_low_close_ATR_14",
    "close_STDDEV_10","close_STDDEV_20",
    "close_BBANDS_10_upper","close_BBANDS_10_middle","close_BBANDS_10_lower",  # Bollinger mais rápido

    # Volume (crítico para scalping)
    "close_volume_OBV_1","volume_SMA_5","volume_SMA_10",
    "high_low_close_volume_MFI_10",

    # Fast MACD
    "close_MACD_1_macd","close_MACD_1_macdsignal","close_MACD_1_macdhist"
]
```

**Total:** 29 features
**Foco:** Short windows, fast reactions

---

## ✅ Features ADICIONADAS (Novas)

### 1. **Volume Features** (CRÍTICO - estava faltando!)
```python
# On-Balance Volume (acumulação/distribuição)
"close_volume_OBV_1"

# Volume médio (detectar picos de volume)
"volume_SMA_10","volume_SMA_20"

# Money Flow Index (RSI + volume)
"high_low_close_volume_MFI_14"
```

**Por que crítico:**
- Volume é **leading indicator** (lidera o preço)
- Breakouts com alto volume são mais confiáveis
- Pode melhorar win rate em 3-5%

---

### 2. **MACD** (Trend + Momentum)
```python
"close_MACD_1_macd","close_MACD_1_macdsignal","close_MACD_1_macdhist"
```

**Por que útil:**
- Combina trend + momentum em um indicador
- `macdhist` (diferença) é bom para detectar reversões
- Usado por muitos traders → pode capturar padrões de mercado

---

### 3. **CCI e Williams %R** (Aggressive only)
```python
"high_low_close_CCI_14"   # Commodity Channel Index
"close_WILLR_14"          # Williams %R
```

**Por que útil:**
- Detectar sobrecompra/sobrevenda
- Complementar RSI com perspectiva diferente
- Útil em mercados de alta volatilidade

---

### 4. **EMA** (além do SMA)
```python
"close_EMA_5","close_EMA_12","close_EMA_26"
```

**Por que útil:**
- EMA reage mais rápido que SMA (dá mais peso a preços recentes)
- EMA 12/26 são padrão do MACD
- Pode capturar trends mais cedo

---

### 5. **MOM (Momentum)**
```python
"close_MOM_5","close_MOM_10"
```

**Por que útil:**
- Velocidade da mudança de preço
- Simples mas efetivo
- Complementa LINEARREG_SLOPE

---

## ❌ Features REMOVIDAS (Não estavam sendo usadas)

Nenhuma feature foi removida. **Todas as features antigas foram mantidas** (SMA, RSI, LINEARREG_SLOPE, ATR, STDDEV, BBANDS) porque são **proven indicators**.

---

## 🔧 Features MODIFICADAS

### 1. **RSI com múltiplas janelas** (Aggressive/Quick)
```python
# Antes (Conservative):
"close_RSI_14"

# Depois (Aggressive/Quick):
"close_RSI_7","close_RSI_14"
```

**Razão:** RSI_7 é mais sensível, RSI_14 é mais estável. Ter ambos dá ao modelo mais opções.

---

### 2. **ATR com múltiplas janelas** (Aggressive)
```python
# Antes (Conservative):
"high_low_close_ATR_14"

# Depois (Aggressive):
"high_low_close_ATR_7","high_low_close_ATR_14"
```

**Razão:** ATR_7 captura volatilidade recente, ATR_14 é média mais longa.

---

### 3. **Bollinger Bands janela mais curta** (Quick Profit)
```python
# Antes (Conservative):
"close_BBANDS_20_*"

# Depois (Quick Profit):
"close_BBANDS_10_*"  # Bollinger de 10 períodos (mais rápido)
```

**Razão:** Scalping precisa de sinais rápidos.

---

### 4. **Volume SMA múltiplas janelas**
```python
# Conservative: volume_SMA_20
# Aggressive: volume_SMA_10, volume_SMA_20
# Quick: volume_SMA_5, volume_SMA_10
```

**Razão:** Diferentes estratégias precisam diferentes janelas de tempo.

---

## 🎯 Próximas Features a Testar (Após Orderflow)

### Orderflow Features (19 features esperadas)
```python
# L2 Orderbook depth
"bid_depth_5","ask_depth_5"
"bid_depth_10","ask_depth_10"

# Imbalance
"imbalance_ratio"
"imbalance_score"

# Pressure
"buy_pressure"
"sell_pressure"

# Walls
"bid_wall_size"
"ask_wall_size"

# Spread
"spread_bps"
"spread_pct"

# etc... (total 19 features)
```

**Impacto esperado:** +5-10% win rate (orderflow são leading indicators)

---

## 📈 Feature Importance (Como Verificar)

Após treinar LGBM, verificar feature importance:

```python
import lightgbm as lgb

# Após treino
model = lgb.LGBMClassifier(...)
model.fit(X_train, y_train)

# Feature importance
importance = pd.DataFrame({
    'feature': X_train.columns,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

print(importance.head(20))
```

**Features esperadas no top 10:**
1. Volume features (OBV, volume_SMA, MFI)
2. MACD histogram
3. RSI
4. LINEARREG_SLOPE
5. ATR
6. Bollinger Bands (upper/lower)
7. SMA crossovers (implícito)

---

## ⚠️ Evitar Overfitting

**Sinais de overfitting:**
- Train accuracy 95%, test accuracy 52%
- Win rate backtesting 65%, shadow mode 48%
- Muitas features (>50) com pouca importância

**Como evitar:**
1. ✅ Usar cross-validation
2. ✅ Regularização LGBM (`min_child_samples`, `subsample`)
3. ✅ Feature selection (remover features com importance < 0.01)
4. ✅ Walk-forward testing (rolling_predict)
5. ✅ Shadow mode antes de live

---

## 📊 Feature Count por Config

| Config | Features | Comentário |
|--------|----------|------------|
| Conservative | 20 | Balanceado, evita overfit |
| Aggressive | 31 | Mais features para LGBM explorar |
| Quick Profit | 29 | Foco em velocidade (janelas curtas) |

---

## 🔑 Principais Mudanças vs Configs Antigos

### Antes (ethusdt_5m_dev_optimazed.jsonc)
```python
"train_features": [
    "close_SMA_5","close_SMA_10","close_SMA_20","close_SMA_60",
    "close_RSI_14",
    "close_LINEARREG_SLOPE_10","close_LINEARREG_SLOPE_20","close_LINEARREG_SLOPE_60",
    "high_low_close_ATR_14","close_STDDEV_20","close_STDDEV_60"
]
```
**Total:** 11 features
**Problemas:** ❌ Sem volume, ❌ Sem MACD, ❌ Sem EMA, ❌ Sem Bollinger

---

### Depois (base_conservative.jsonc)
```python
"train_features": [
    # Todas as 11 anteriores +
    "close_SMA_120","close_EMA_12","close_EMA_26",
    "close_MOM_10",
    "close_BBANDS_20_upper","close_BBANDS_20_middle","close_BBANDS_20_lower",
    "close_volume_OBV_1","volume_SMA_20"  # CRÍTICO!
]
```
**Total:** 20 features (+9 novas)
**Melhorias:** ✅ Volume, ✅ Bollinger, ✅ EMA, ✅ Momentum

---

## 💡 Recomendações Finais

### Para Testar Primeiro (dev)
1. **Treinar com conservative** → Ver se volume features melhoram win rate
2. **Comparar LGBM vs LogReg** → LGBM deve ser melhor (mais features)
3. **Feature importance** → Remover features com importance < 0.01

### Para Orderflow Test (17/dez)
1. Adicionar 19 orderflow features
2. Retreinar com **conservative + orderflow**
3. Comparar win rate: baseline (sem orderflow) vs com orderflow

### Para Multi-Cloud (após orderflow)
1. **Azure:** Conservative (20 features + orderflow selecionadas)
2. **GCP:** Aggressive (31 features + orderflow todas)
3. Ensemble voting dos dois

---

**Status:** Pronto para testar
**Próximo passo:** Rodar pipeline com novos configs e verificar win rate
