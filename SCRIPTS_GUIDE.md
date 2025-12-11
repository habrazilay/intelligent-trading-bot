# Guia Completo de Scripts - Intelligent Trading Bot

## 📋 Índice
- [Pipeline Principal](#pipeline-principal)
- [Scripts Antigos vs Novos](#scripts-antigos-vs-novos)
- [Novos Scripts Detalhados](#novos-scripts-detalhados)
- [Como Testar Localmente](#como-testar-localmente)
- [Perguntas Frequentes](#perguntas-frequentes)

---

## Pipeline Principal

### Pipeline Completo (8 etapas)

```bash
# 1. Download de dados históricos da Binance
python -m scripts.download_binance -c config.json

# 2. Merge de múltiplas fontes de dados
python -m scripts.merge -c config.json

# 3. Geração de features (indicadores técnicos)
python -m scripts.features -c config.json

# 4. Geração de labels (alvos de predição)
python -m scripts.labels -c config.json

# 5. Treinamento de modelos ML
python -m scripts.train -c config.json

# 6. Predições com modelos treinados
python -m scripts.predict -c config.json

# 7. Geração de sinais de trading
python -m scripts.signals -c config.json

# 8. Execução/notificação de trades
python -m scripts.output -c config.json
```

---

## Scripts Antigos vs Novos

### Matriz de Compatibilidade

| Etapa | Script Antigo | Script Novo | Status | Notas |
|-------|--------------|-------------|--------|-------|
| **1. Download** | `download_binance.py` | ✓ (mesmo) | ✅ Funcionando | Downloads OHLCV |
| **1b. Orderbook** | ❌ Não existia | `collect_orderbook.py` | 🆕 **NOVO** | Coleta orderbook em tempo real |
| **1c. Verificação** | ❌ Não existia | `verify_orderbook_data.py` | 🆕 **NOVO** | Valida dados de orderbook |
| **2. Merge** | `merge.py` | `merge_new.py` | ⚠️ **Ambos** | Novo tem melhor logging |
| **3. Features** | `features.py` | `features_new.py` | ⚠️ **Ambos** | Novo suporta dry-run |
| **4. Labels** | `labels.py` | `labels_new.py` | ⚠️ **Ambos** | Novo suporta dry-run |
| **5. Train** | `train.py` | ✓ (mesmo) | ✅ Funcionando | Usa dados de qualquer pipeline |
| **6. Predict** | `predict.py` | ✓ (mesmo) | ✅ Funcionando | - |
| **7. Signals** | `signals.py` | ✓ (mesmo) | ✅ Funcionando | - |
| **8. Output** | `output.py` | ✓ (mesmo) | ✅ Funcionando | - |

### Quando Usar Cada Versão?

#### **Use os scripts ANTIGOS** quando:
- ✅ Você já tem um pipeline funcionando
- ✅ Não precisa de validação dry-run
- ✅ Não usa dados de orderbook

#### **Use os scripts NOVOS** quando:
- 🆕 Quer validar antes de processar (`--dry-run`)
- 🆕 Precisa de melhor logging e diagnóstico
- 🆕 Vai usar features de orderbook (order flow)
- 🆕 Quer preparar para CI/CD automatizado

---

## Novos Scripts Detalhados

### 1. `collect_orderbook.py` 🆕

**Propósito**: Coleta dados de orderbook (livro de ofertas) em tempo real via WebSocket.

**Por que foi criado?**
- O `download_binance.py` baixa apenas dados OHLCV (candles)
- Para estratégias avançadas, precisamos de **order flow** (fluxo de ordens)
- Orderbook mostra bid/ask spreads, profundidade de mercado, etc.

**Uso**:

```bash
# Coletar por 24 horas
python scripts/collect_orderbook.py --symbol BTCUSDT --duration 24h

# Teste rápido (5 minutos)
python scripts/collect_orderbook.py --symbol BTCUSDT --duration 5m --save-interval 1m

# Via config file (como download_binance)
python scripts/collect_orderbook.py -c configs/btcusdt_5m_orderflow.jsonc
```

**Saída**:
- Arquivos Parquet em `DATA_ORDERBOOK/`
- Formato: `BTCUSDT_orderbook_20251211_143022.parquet`
- Colunas: `bid_price_0...19`, `ask_price_0...19`, `mid_price`, `spread`, etc.

**Relação com download_binance.py**:
- **NÃO substituí** o `download_binance.py`
- São **complementares**:
  - `download_binance.py` → dados históricos de preço (OHLCV)
  - `collect_orderbook.py` → dados de mercado em tempo real (order book)

---

### 2. `verify_orderbook_data.py` 🆕

**Propósito**: Valida que os dados de orderbook foram coletados corretamente.

**Uso**:

```bash
python scripts/verify_orderbook_data.py
```

**O que verifica**:
- ✅ Arquivos existem em `DATA_ORDERBOOK/`
- ✅ Número de snapshots coletados
- ✅ Período de tempo coberto
- ✅ Colunas presentes
- ✅ Dados faltantes (NaN)

**Exemplo de saída**:
```
✅ Encontrados 2 arquivo(s):

   1. BTCUSDT_orderbook_20251211_143022.parquet
      Tamanho: 45.23 MB
      Linhas: 86,400
      Período: 2025-12-11 14:30 → 2025-12-11 23:30

📊 RESUMO
Total de snapshots: 86,400
Taxa média: 12.00 snapshots/segundo
```

---

### 3. `merge_new.py` 🆕

**Diferenças do `merge.py` antigo**:

| Feature | merge.py (antigo) | merge_new.py (novo) |
|---------|------------------|-------------------|
| Funcionalidade básica | ✅ | ✅ |
| Dry-run mode | ❌ | ✅ `--dry-run` |
| Logging detalhado | ⚠️ Básico | ✅ Completo |
| Interpolação configurável | ❌ | ✅ |
| Validação de entrada | ⚠️ Básica | ✅ Robusta |
| Mensagens de próximo passo | ❌ | ✅ |

**Uso**:

```bash
# Validar sem gravar arquivo
python -m scripts.merge_new -c configs/btcusdt_1m_dev.jsonc --dry-run

# Executar de verdade
python -m scripts.merge_new -c configs/btcusdt_1m_dev.jsonc

# Debug detalhado
python -m scripts.merge_new -c configs/btcusdt_1m_dev.jsonc --log-level DEBUG
```

**Saída**:
```
✔ MERGE COMPLETE — data looks good.
✔ Rows: 525,600 | Range: 2024-01-01 00:00:00 → 2025-01-01 00:00:00
✔ File saved at: DATA_ITB_1m/BTCUSDT/data.csv
➡ Next step: python -m scripts.features_new -c configs/btcusdt_1m_dev.jsonc
```

---

### 4. `features_new.py` 🆕

**Diferenças do `features.py` antigo**:

| Feature | features.py | features_new.py |
|---------|------------|----------------|
| Geração de features | ✅ | ✅ |
| Dry-run mode | ❌ | ✅ `--dry-run` |
| Validação NULL detalhada | ⚠️ | ✅ |
| Log de tempo por feature set | ❌ | ✅ |
| Lista de features geradas | ❌ | ✅ Salva em .txt |

**Uso**:

```bash
# Dry-run para validar
python -m scripts.features_new -c configs/btcusdt_1m_dev.jsonc --dry-run

# Executar
python -m scripts.features_new -c configs/btcusdt_1m_dev.jsonc
```

**Saída**:
```
Iniciando feature set 1/5 (talib)...
Finalizado set 1/5 → 8 novas features (talib). Tempo: 0:02:15

Total de features novas: 42

Resumo de NULL por feature:
close_SMA_5      0
close_SMA_10     0
close_RSI_14    13
...

✔ FEATURES COMPLETAS em 0:12:34
➡ Próximo passo: python -m scripts.labels_new -c configs/btcusdt_1m_dev.jsonc
```

---

### 5. `labels_new.py` 🆕

**Diferenças do `labels.py` antigo**:

| Feature | labels.py | labels_new.py |
|---------|-----------|--------------|
| Geração de labels | ✅ | ✅ |
| Dry-run mode | ❌ | ✅ `--dry-run` |
| Arquivo de saída | features.csv | **matrix.csv** (features+labels) |
| Lista de labels | ❌ | ✅ Salva em .labels.txt |

**Uso**:

```bash
# Dry-run
python -m scripts.labels_new -c configs/btcusdt_1m_dev.jsonc --dry-run

# Executar
python -m scripts.labels_new -c configs/btcusdt_1m_dev.jsonc
```

**Importante**: O novo script gera um arquivo `matrix.csv` que contém **features + labels** juntos.

---

## Como Testar Localmente

### Teste Rápido (5 minutos) - Recomendado

```bash
./test_pipeline_local.sh --quick
```

**O que testa**:
- ✅ Scripts novos (`merge_new`, `features_new`, `labels_new`)
- ✅ Collect orderbook (30s de teste)
- ✅ Verify orderbook data
- ✅ Train com dados novos

### Teste Completo (30 minutos)

```bash
./test_pipeline_local.sh --full
```

**O que testa**:
- ✅ Pipeline antigo completo (8 etapas)
- ✅ Scripts novos
- ✅ Integração entre ambos

### Teste Apenas Scripts Novos

```bash
./test_pipeline_local.sh --new-only
```

---

## Perguntas Frequentes

### 1. **Devo usar os scripts novos ou antigos?**

**Resposta**: Depende da sua situação.

- **Para produção existente**: Continue com scripts antigos até validar os novos
- **Para novos experimentos**: Use scripts novos (melhor logging e validação)
- **Para CI/CD**: Use scripts novos (suportam dry-run, essencial para testes automatizados)

### 2. **O `collect_orderbook.py` é usado pelo `download_binance.py`?**

**Não!** São scripts **independentes e complementares**:

- `download_binance.py`:
  - Baixa dados **históricos** via REST API
  - Dados de preço (OHLCV - candles)
  - Executado **uma vez** para pegar histórico

- `collect_orderbook.py`:
  - Coleta dados **em tempo real** via WebSocket
  - Dados de mercado (order book)
  - Executado **continuamente** enquanto você quer coletar

**Fluxo recomendado**:
```bash
# 1. Baixar histórico de preços (uma vez)
python -m scripts.download_binance -c config.json

# 2. Iniciar coleta de orderbook (deixar rodando)
python scripts/collect_orderbook.py --symbol BTCUSDT --duration 7d &

# 3. Depois de 7 dias, verificar dados
python scripts/verify_orderbook_data.py

# 4. Adicionar features de orderbook ao config
# 5. Executar pipeline normal
```

### 3. **Posso misturar scripts novos e antigos?**

**Sim!** Os scripts são compatíveis. Exemplo:

```bash
# Usar antigos para download e merge
python -m scripts.download_binance -c config.json
python -m scripts.merge -c config.json

# Usar novos para features e labels
python -m scripts.features_new -c config.json
python -m scripts.labels_new -c config.json

# Usar antigo para train
python -m scripts.train -c config.json
```

### 4. **O que significa `--dry-run`?**

**Dry-run** = "teste seco" = simular sem executar de verdade.

Com `--dry-run`:
- ✅ Carrega e valida arquivos de entrada
- ✅ Processa dados em memória
- ✅ Mostra estatísticas e validações
- ❌ **NÃO grava** arquivo de saída

**Uso típico**:
```bash
# 1. Dry-run para validar
python -m scripts.features_new -c config.json --dry-run

# 2. Se OK, executar de verdade
python -m scripts.features_new -c config.json
```

### 5. **Qual a diferença entre `features.csv` e `matrix.csv`?**

- **`merge.csv` / `data.csv`**: Dados brutos merged
- **`features.csv`**: Dados brutos + features calculadas
- **`matrix.csv`**: Dados brutos + features + **labels**

**Pipeline**:
```
download → merge.csv
              ↓
         features.py → features.csv
              ↓
          labels.py → matrix.csv (usado no train)
```

### 6. **Como integrar orderbook features no pipeline?**

**Passo a passo**:

1. **Coletar dados de orderbook** (deixar rodando por alguns dias):
```bash
python scripts/collect_orderbook.py --symbol BTCUSDT --duration 7d
```

2. **Verificar coleta**:
```bash
python scripts/verify_orderbook_data.py
```

3. **Adicionar ao config** ([configs/btcusdt_5m_orderflow.jsonc](configs/btcusdt_5m_orderflow.jsonc)):
```jsonc
{
  "data_sources": [
    { "folder": "BTCUSDT", "file": "klines", "column_prefix": "" },
    { "folder": "BTCUSDT", "file": "orderbook", "column_prefix": "ob" }  // NOVO
  ],

  "feature_sets": [
    // Features normais
    { "generator": "talib", ... },

    // Features de orderbook
    {
      "generator": "orderbook_features",
      "config": {
        "columns": ["ob_bid_price_0", "ob_ask_price_0", "ob_spread"],
        "functions": ["bid_ask_imbalance", "spread_volatility"],
        "windows": [5, 10, 20]
      }
    }
  ]
}
```

4. **Executar pipeline normal**:
```bash
python -m scripts.merge_new -c configs/btcusdt_5m_orderflow.jsonc
python -m scripts.features_new -c configs/btcusdt_5m_orderflow.jsonc
# ... resto do pipeline
```

---

## Próximos Passos

Depois de testar localmente:

1. ✅ **Validar logs**: `cat test_pipeline_*.log`
2. ✅ **Verificar arquivos de saída**: Conferir se foram criados
3. ✅ **Atualizar CI/CD**: Configurar GitHub Actions para Azure
4. ✅ **Deploy**: Executar pipeline automatizado na nuvem

---

## Comandos Úteis

### Verificar estrutura de dados

```bash
# Ver colunas de um arquivo Parquet
python -c "import pandas as pd; print(pd.read_parquet('DATA_ITB_1m/BTCUSDT/klines.parquet').columns)"

# Ver primeiras linhas
python -c "import pandas as pd; print(pd.read_parquet('DATA_ITB_1m/BTCUSDT/klines.parquet').head())"

# Contar linhas
python -c "import pandas as pd; print(len(pd.read_parquet('DATA_ITB_1m/BTCUSDT/klines.parquet')))"
```

### Limpar dados de teste

```bash
# Remover todos os dados de teste
rm -rf DATA_ITB_TEST DATA_ORDERBOOK_TEST

# Remover logs
rm -f test_pipeline_*.log
```

---

## Estrutura de Pastas

```
intelligent-trading-bot/
│
├── scripts/
│   ├── download_binance.py        # Download OHLCV (antigo)
│   ├── collect_orderbook.py       # Coleta orderbook (NOVO)
│   ├── verify_orderbook_data.py   # Valida orderbook (NOVO)
│   │
│   ├── merge.py                   # Merge (antigo)
│   ├── merge_new.py               # Merge (NOVO - com dry-run)
│   │
│   ├── features.py                # Features (antigo)
│   ├── features_new.py            # Features (NOVO - com dry-run)
│   │
│   ├── labels.py                  # Labels (antigo)
│   ├── labels_new.py              # Labels (NOVO - com dry-run)
│   │
│   ├── train.py                   # Train (mesmo para ambos)
│   ├── predict.py                 # Predict
│   ├── signals.py                 # Signals
│   └── output.py                  # Output
│
├── configs/
│   ├── btcusdt_1m_dev.jsonc       # Config básico
│   ├── btcusdt_5m_orderflow.jsonc # Config com orderbook
│   └── ...
│
├── DATA_ITB_1m/                   # Dados 1 minuto
├── DATA_ITB_5m/                   # Dados 5 minutos
├── DATA_ORDERBOOK/                # Dados de orderbook
│
├── test_pipeline_local.sh         # Script de teste (NOVO)
└── SCRIPTS_GUIDE.md               # Este arquivo
```

---

**Última atualização**: 2025-12-11
**Versão**: 1.0
