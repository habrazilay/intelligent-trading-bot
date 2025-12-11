# Sistema de Configuração Genérico

**Status:** Ativo (Dezembro 2025)
**Objetivo:** Simplificar gerenciamento de configs e reduzir duplicação

---

## 🎯 Problema Resolvido

**Antes:** 20+ arquivos de config específicos (btcusdt_1m_dev.jsonc, ethusdt_5m_dev.jsonc, etc.)
**Depois:** 4 configs base reutilizáveis com parâmetros CLI

---

## 📂 Configs Base

### 1. `configs/base_conservative.jsonc`
**Estratégia:** Conservadora para Azure (baseline)
**Modelos:** Logistic Regression + LightGBM
**Thresholds:** 0.6% (altos, menos trades, mais seguros)
**Features:** 20 features (proven indicators)
**Uso:**
```bash
make conservative-btc-5m   # BTCUSDT 5m
make conservative-eth-5m   # ETHUSDT 5m
```

---

### 2. `configs/base_aggressive.jsonc`
**Estratégia:** Agressiva para GCP (advanced ML)
**Modelos:** LightGBM otimizado (LGBM + LogReg opcional)
**Thresholds:** 0.4% (baixos, mais trades)
**Features:** 31 features (inclui CCI, WILLR, MFI, MACD)
**Uso:**
```bash
make aggressive-sol-5m     # SOLUSDT 5m
make aggressive-bnb-5m     # BNBUSDT 5m
```

---

### 3. `configs/base_quick_profit.jsonc`
**Estratégia:** Scalping rápido (lucro rápido 0.2-0.3%)
**Modelos:** LightGBM otimizado para velocidade
**Thresholds:** 0.25% (muito baixos, alta frequência)
**Features:** 29 features (janelas curtas, indicadores rápidos)
**Uso:**
```bash
make quick-btc-1m          # BTCUSDT 1m scalping
make quick-eth-1m          # ETHUSDT 1m scalping
```

---

### 4. `configs/base_staging.jsonc`
**Estratégia:** Produção/staging (só predição, sem treino)
**Modelos:** Usa modelos pré-treinados
**train:** false
**Uso:**
```bash
python -m scripts.predict \
  --config configs/base_staging.jsonc \
  --symbol BTCUSDT \
  --freq 5m
```

---

## 🚀 Como Usar

### Opção 1: Makefile (Recomendado)

```bash
# Pipelines prontos
make conservative-btc-5m
make aggressive-sol-5m
make quick-btc-1m

# Pipeline genérico custom
make pipeline-generic \
  BASE_CONFIG=configs/base_conservative.jsonc \
  SYMBOL=XRPUSDT \
  FREQ=15m
```

### Opção 2: Python Direto

```bash
# Train
python -m scripts.train \
  -c configs/base_conservative.jsonc \
  --symbol BTCUSDT \
  --freq 5m

# Features
python -m scripts.features \
  -c configs/base_aggressive.jsonc \
  --symbol SOLUSDT \
  --freq 5m

# Full pipeline
python -m scripts.merge -c configs/base_conservative.jsonc --symbol ETHUSDT --freq 5m
python -m scripts.features -c configs/base_conservative.jsonc --symbol ETHUSDT --freq 5m
python -m scripts.labels -c configs/base_conservative.jsonc --symbol ETHUSDT --freq 5m
python -m scripts.train -c configs/base_conservative.jsonc --symbol ETHUSDT --freq 5m
```

---

## ⚙️ Parâmetros Dinâmicos

Os seguintes parâmetros são calculados automaticamente com base na `--freq`:

| Freq | train_length | label_horizon | predict_length | pandas_freq |
|------|--------------|---------------|----------------|-------------|
| 1m   | 525,600      | 60 (1h)       | 1,440 (1d)     | 1min        |
| 5m   | 105,120      | 24 (2h)       | 288 (1d)       | 5min        |
| 15m  | 35,040       | 16 (4h)       | 96 (1d)        | 15min       |
| 1h   | 8,760        | 4 (4h)        | 24 (1d)        | 1h          |

**Exemplo:** Se você rodar `--freq 1m`, o config automaticamente usa:
- `train_length: 525600` (1 ano de dados 1m)
- `label_horizon: 60` (1 hora para gerar label)
- `pandas_freq: "1min"`

---

## 📝 Placeholders nos Configs

Os configs base usam placeholders que são substituídos automaticamente:

```jsonc
{
  "symbol": "{symbol}",              // → BTCUSDT
  "freq": "{freq}",                  // → 5m
  "pandas_freq": "{pandas_freq}",    // → 5min
  "data_folder": "./DATA_ITB_{freq}" // → ./DATA_ITB_5m
}
```

**File names genéricos (SEM hardcode de symbol/freq):**
```jsonc
{
  "merge_file_name":   "data.csv",
  "feature_file_name": "features.csv",
  "matrix_file_name":  "matrix.csv",
  "predict_file_name": "predictions.csv",
  "signal_file_name":  "signals.csv"
}
```

---

## 🔧 Implementação Técnica

### 1. **Config Helper** (`scripts/config_helper.py`)

Módulo que:
- Carrega config base
- Substitui placeholders ({symbol}, {freq}, {pandas_freq})
- Calcula parâmetros dinâmicos (train_length, label_horizon)
- Valida campos obrigatórios

```python
from scripts.config_helper import load_config_with_args

config = load_config_with_args(
    config_path="configs/base_conservative.jsonc",
    symbol="BTCUSDT",
    freq="5m"
)
```

### 2. **Service App** (`service/App.py`)

Função `load_config()` modificada para aceitar symbol/freq:

```python
def load_config(config_file: str, symbol: str = None, freq: str = None):
    # Se symbol/freq fornecidos, usa config_helper
    if symbol or freq:
        from scripts.config_helper import load_config_with_args
        conf_json = load_config_with_args(config_path, symbol, freq)
    # ...
```

### 3. **Scripts CLI** (merge, features, labels, train, etc.)

Adicionado --symbol e --freq em todos:

```python
@click.command()
@click.option('--config_file', '-c', required=True)
@click.option('--symbol', default=None, help='Symbol override')
@click.option('--freq', default=None, help='Frequency override')
def main(config_file, symbol, freq):
    load_config(config_file, symbol=symbol, freq=freq)
```

---

## 📊 Comparação: Configs Antigos vs Novos

### Sistema Antigo (20+ configs)
```
configs/
├── btcusdt_1m_dev.jsonc
├── btcusdt_5m_dev.jsonc
├── btcusdt_1h_dev.jsonc
├── ethusdt_1m_dev.jsonc
├── ethusdt_5m_dev.jsonc
├── solusdt_1m_dev.jsonc
├── btcusdt_1m_dev_optimazed.jsonc
├── btcusdt_5m_dev_optimazed.jsonc
├── ethusdt_5m_dev_optimazed.jsonc
├── btcusdt_1m_aggressive.jsonc
├── btcusdt_5m_aggressive.jsonc
├── btcusdt_1m_staging_v2.jsonc
├── btcusdt_5m_staging_v2.jsonc
└── ... (total 20 arquivos)
```

**Problemas:**
- ❌ Muita duplicação
- ❌ Difícil manter sincronizado
- ❌ Hardcoded symbol/freq nos file names
- ❌ Adicionar novo símbolo = criar 5+ configs

---

### Sistema Novo (4 configs base)
```
configs/
├── base_conservative.jsonc    # Azure baseline
├── base_aggressive.jsonc      # GCP advanced
├── base_quick_profit.jsonc    # Scalping
└── base_staging.jsonc         # Production
```

**Benefícios:**
- ✅ Apenas 4 configs para manter
- ✅ Adicionar novo símbolo: apenas `--symbol XRPUSDT`
- ✅ File names genéricos (sem hardcode)
- ✅ Parâmetros calculados automaticamente
- ✅ Fácil testar múltiplos symbols/freqs

---

## 🎯 Features por Estratégia

### Conservative (20 features)
```python
# Trend
close_SMA_5, close_SMA_10, close_SMA_20, close_SMA_60, close_SMA_120
close_EMA_12, close_EMA_26

# Momentum
close_RSI_14, close_LINEARREG_SLOPE_10/20/60, close_MOM_10

# Volatility
ATR_14, STDDEV_20/60, BBANDS_20

# Volume (NOVO!)
OBV, volume_SMA_20
```

### Aggressive (31 features)
```python
# Conservative features +
close_RSI_7, CCI_14, WILLR_14
ATR_7, STDDEV_10, volume_SMA_10
MFI_14, MACD (macd, signal, hist)
```

### Quick Profit (29 features)
```python
# Janelas curtas (scalping)
SMA_3/5/10/20, EMA_3/5/12
RSI_7/14, LINEARREG_SLOPE_3/5/10
MOM_3/5, CCI_10, ATR_7/14
BBANDS_10 (rápido), volume_SMA_5/10
MFI_10, MACD
```

**Ver detalhes:** `docs/TRAIN_FEATURES_GUIDE.md`

---

## 📈 Thresholds por Estratégia

### Conservative
```python
# Labels
high_06_24: 0.6% gain em 24 candles (2h para 5m)
low_06_24: 0.6% drop

# Signals
buy_signal_threshold: 0.004   # Alto = menos trades, mais seguros
sell_signal_threshold: -0.004

# Grid (otimização)
buy: [0.003, 0.004, 0.005, 0.006]
sell: [-0.003, -0.004, -0.005, -0.006]
```

### Aggressive
```python
# Labels
high_04_18: 0.4% gain em 18 candles
low_04_18: 0.4% drop

# Signals
buy_signal_threshold: 0.002   # Baixo = mais trades
sell_signal_threshold: -0.002

# Grid
buy: [0.001, 0.0015, 0.002, 0.0025, 0.003]
sell: [-0.001, -0.0015, -0.002, -0.0025, -0.003]
```

### Quick Profit
```python
# Labels
high_025_12: 0.25% gain em 12 candles (scalping)
low_025_12: 0.25% drop

# Signals
buy_signal_threshold: 0.0008  # Muito baixo = alta frequência
sell_signal_threshold: -0.0008

# Grid
buy: [0.0005, 0.0008, 0.001, 0.0012, 0.0015, 0.002]
sell: [-0.0005, -0.0008, -0.001, -0.0012, -0.0015, -0.002]
```

---

## 🌐 Multi-Cloud Usage

### Azure (Conservative)
```bash
# BTCUSDT + ETHUSDT com baseline models
make conservative-btc-5m
make conservative-eth-5m

# Ou custom
python -m scripts.train \
  -c configs/base_conservative.jsonc \
  --symbol BTCUSDT \
  --freq 5m
```

### GCP (Aggressive)
```bash
# SOLUSDT + BNBUSDT + XRPUSDT com advanced ML
make aggressive-sol-5m
make aggressive-bnb-5m

# Ou custom
python -m scripts.train \
  -c configs/base_aggressive.jsonc \
  --symbol XRPUSDT \
  --freq 5m
```

**Ver estratégia completa:** `docs/ESTRATEGIA_MULTI_CLOUD.md`

---

## 🔄 Migração de Configs Antigos

### Passo 1: Identificar estratégia
```
btcusdt_1m_dev.jsonc → base_conservative.jsonc
btcusdt_5m_aggressive.jsonc → base_aggressive.jsonc
```

### Passo 2: Substituir chamada
**Antes:**
```bash
make train CONFIG=configs/btcusdt_1m_dev.jsonc
```

**Depois:**
```bash
make pipeline-generic \
  BASE_CONFIG=configs/base_conservative.jsonc \
  SYMBOL=BTCUSDT \
  FREQ=1m
```

### Passo 3: Validar
```bash
# Test config loading
python scripts/config_helper.py \
  -c configs/base_conservative.jsonc \
  --symbol BTCUSDT \
  --freq 5m
```

---

## ✅ Validação

### Teste rápido
```bash
# Testar config_helper
python scripts/config_helper.py \
  -c configs/base_conservative.jsonc \
  --symbol ETHUSDT \
  --freq 5m

# Output esperado:
# ══════════════════════════════════════════════════════════════════
# CONFIG SUMMARY
# ══════════════════════════════════════════════════════════════════
# Symbol:           ETHUSDT
# Frequency:        5m (5min)
# Data folder:      ./DATA_ITB_5m
# Description:      Conservative strategy - Azure baseline
# Train mode:       True
# Train length:     105,120 candles
# Label horizon:    24 candles
# ...
```

### Validar todos configs
```bash
make validate-configs
```

---

## 🚨 Troubleshooting

### Erro: "Unsupported frequency: 30m"
```
Solução: Adicionar 30m em FREQ_PARAMS do config_helper.py
```

### Erro: "Missing required config fields: symbol"
```
Solução: Passar --symbol na CLI ou definir no config
```

### Placeholder não substituído ({symbol} aparece literal)
```
Solução: Usar load_config(config, symbol="BTCUSDT", freq="5m")
         Não usar load_config(config) sem parâmetros
```

---

## 📚 Documentação Relacionada

- `docs/TRAIN_FEATURES_GUIDE.md` - Guia de features
- `docs/ESTRATEGIA_MULTI_CLOUD.md` - Estratégia multi-cloud
- `docs/PLANEJAMENTO_FUTURO.md` - Refatorações futuras

---

**Status do Documento:** Ativo
**Última Atualização:** 2025-12-11
**Próxima Revisão:** Após teste orderflow (2025-12-17)
