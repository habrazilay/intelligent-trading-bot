# Organização de Dados - Preservar Tudo, Organizar Melhor

## 🏆 Filosofia: Dados São Ouro

**NUNCA deletar dados!** Tudo deve ser:
- ✅ Preservado
- ✅ Organizado
- ✅ Versionado
- ✅ Documentado

## 📁 Estrutura Atual (Repositório Principal)

```
/Users/danielschmidt/intelligent-trading-bot/
├── DATA_ITB_1m/     (733 MB - BTC + ETH 1 minuto)
├── DATA_ITB_1h/     (BTC 1 hora)
└── DATA_ITB_5m/     (BTC 5 minutos)
```

## 🎯 Estrutura Proposta (Organizada)

```
/Users/danielschmidt/intelligent-trading-bot/
│
├── DATA_EXPERIMENTS/           # Experimentos e testes
│   ├── exp_rsi_sma_20241201/
│   ├── exp_bollinger_20241203/
│   └── exp_custom_features_20241205/
│
├── DATA_STAGING/               # Dados de staging/shadow trading
│   ├── btcusdt_1m/
│   │   ├── raw/               # Dados brutos preservados
│   │   ├── processed/         # Features, labels, etc
│   │   ├── models/            # Modelos treinados
│   │   ├── logs/              # Logs de execução
│   │   └── transactions/      # Histórico de transações (shadow)
│   ├── btcusdt_5m/
│   └── btcusdt_1h/
│
├── DATA_PRODUCTION/            # Dados de produção (quando ativar)
│   └── btcusdt_1m/
│       ├── raw/
│       ├── processed/
│       ├── models/
│       ├── logs/
│       └── transactions/      # Transações REAIS
│
└── DATA_ARCHIVE/               # Dados antigos preservados
    └── 2024/
        ├── 12/
        │   ├── DATA_ITB_1m_20241201/
        │   └── DATA_ITB_1m_20241205/
        └── 11/
```

## 🔄 Script de Reorganização (SEM DELETAR)

```bash
#!/bin/bash
# organize_data.sh - Reorganiza sem deletar nada

REPO="/Users/danielschmidt/intelligent-trading-bot"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Criar estrutura nova
mkdir -p "$REPO/DATA_ARCHIVE/2024/12"
mkdir -p "$REPO/DATA_STAGING/btcusdt_1m"
mkdir -p "$REPO/DATA_STAGING/btcusdt_5m"
mkdir -p "$REPO/DATA_STAGING/btcusdt_1h"

# Mover dados atuais para arquivo (preservar tudo!)
echo "Arquivando dados atuais..."
mv "$REPO/DATA_ITB_1m" "$REPO/DATA_ARCHIVE/2024/12/DATA_ITB_1m_archived_$TIMESTAMP"
mv "$REPO/DATA_ITB_5m" "$REPO/DATA_ARCHIVE/2024/12/DATA_ITB_5m_archived_$TIMESTAMP"
mv "$REPO/DATA_ITB_1h" "$REPO/DATA_ARCHIVE/2024/12/DATA_ITB_1h_archived_$TIMESTAMP"

echo "✓ Dados arquivados em DATA_ARCHIVE/2024/12/"
echo "✓ Estrutura nova criada em DATA_STAGING/"
```

## 📝 Logs São Fundamentais

### Estrutura de Logs

```
DATA_STAGING/btcusdt_1m/logs/
├── server_YYYYMMDD_HHMMSS.log        # Logs do servidor
├── trades_YYYYMMDD.log                # Decisões de trade
├── predictions_YYYYMMDD.log           # Predições do modelo
├── performance_YYYYMMDD.json          # Métricas de performance
└── errors_YYYYMMDD.log                # Erros e warnings
```

### Configurar Logging Robusto

Adicione ao seu `.env`:
```bash
LOG_LEVEL=INFO
LOG_TO_FILE=true
LOG_DIR=./logs
KEEP_LOGS_DAYS=365  # 1 ano
```

### Capturar Tudo

```python
# Em service/server.py ou comum log config
import logging
from datetime import datetime

log_dir = Path(App.config["data_folder"]) / "logs"
log_dir.mkdir(exist_ok=True)

log_file = log_dir / f"server_{datetime.now():%Y%m%d_%H%M%S}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # Console também
    ]
)
```

## 🗂️ Organizar Transações (Seu Ouro!)

### Formato de Transações Melhorado

Em vez de apenas:
```
timestamp,price,profit,status
```

Use:
```
timestamp,symbol,side,price,quantity,notional,profit,profit_pct,status,model_score,signal_type,mode
```

Exemplo:
```
2024-12-09 15:30:00,BTCUSDT,BUY,42000.00,0.00024,10.08,0.00,0.00,EXECUTED,0.025,buy_signal,SHADOW
2024-12-09 16:45:00,BTCUSDT,SELL,42500.00,0.00024,10.20,0.12,1.19,EXECUTED,-0.015,sell_signal,SHADOW
```

### Salvar em Múltiplos Formatos

```python
# CSV para análise rápida
transactions.csv

# JSON para metadados completos
transactions.jsonl  # Uma linha por transação

# Parquet para análise pesada
transactions.parquet
```

## 📊 Versionamento de Modelos

Nunca sobrescrever modelos! Versionar:

```
DATA_STAGING/btcusdt_1m/models/
├── v1_20241201/
│   ├── high_05_60_lc.pickle
│   ├── low_05_60_lc.pickle
│   └── metadata.json          # Hyper-params, performance, etc
├── v2_20241205/
│   ├── high_05_60_lgbm.pickle
│   ├── low_05_60_lgbm.pickle
│   └── metadata.json
└── current -> v2_20241205/    # Symlink para versão ativa
```

`metadata.json`:
```json
{
  "version": "v2_20241205",
  "created_at": "2024-12-05T14:30:00Z",
  "algorithm": "lgbm",
  "hyperparameters": {
    "num_leaves": 31,
    "learning_rate": 0.05,
    "n_estimators": 500
  },
  "training_metrics": {
    "accuracy": 0.68,
    "f1_score": 0.65,
    "samples": 500000
  },
  "data_period": {
    "start": "2023-01-01",
    "end": "2024-11-30"
  }
}
```

## 📈 Tracking de Performance

Salve métricas periodicamente:

```
DATA_STAGING/btcusdt_1m/performance/
├── daily_summary_20241201.json
├── daily_summary_20241202.json
└── monthly_summary_202412.json
```

`daily_summary.json`:
```json
{
  "date": "2024-12-09",
  "mode": "SHADOW",
  "trades_total": 24,
  "trades_profitable": 15,
  "win_rate": 0.625,
  "profit_total_usdt": 15.43,
  "profit_total_pct": 2.1,
  "avg_trade_duration_min": 45,
  "signals_generated": 48,
  "signals_executed": 24,
  "model_version": "v2_20241205",
  "uptime_pct": 99.8
}
```

## 🎯 Configs Organizadas

```
configs/
├── experiments/
│   ├── exp_rsi_sma.jsonc
│   └── exp_bollinger.jsonc
├── staging/
│   ├── btcusdt_1m_staging.jsonc
│   └── btcusdt_5m_staging.jsonc
└── production/
    └── btcusdt_1m_prod.jsonc   # Quando estiver pronto
```

Cada config aponta para sua pasta:
```jsonc
// experiments/exp_rsi_sma.jsonc
{
  "data_folder": "./DATA_EXPERIMENTS/exp_rsi_sma_20241209"
}

// staging/btcusdt_1m_staging.jsonc
{
  "data_folder": "./DATA_STAGING/btcusdt_1m"
}

// production/btcusdt_1m_prod.jsonc
{
  "data_folder": "./DATA_PRODUCTION/btcusdt_1m"
}
```

## 🔍 Análise Histórica

Com tudo preservado, você pode:

1. **Comparar modelos ao longo do tempo**
   ```bash
   python -m scripts.analyze_models --compare v1 v2 v3
   ```

2. **Replay de dados históricos**
   ```bash
   python -m scripts.replay --date 2024-12-01 --model v2
   ```

3. **A/B testing de estratégias**
   ```bash
   python -m scripts.backtest --strategy A --strategy B --period 30d
   ```

## 💾 Backup Strategy

```bash
# Backup diário automático (cron job)
#!/bin/bash
# backup_daily.sh

REPO="/Users/danielschmidt/intelligent-trading-bot"
BACKUP_DIR="/Users/danielschmidt/Backups/trading-bot"
DATE=$(date +%Y%m%d)

# Backup apenas arquivos pequenos importantes
rsync -av --exclude="*.csv" --exclude="*.parquet" \
  "$REPO/DATA_STAGING/" \
  "$BACKUP_DIR/$DATE/DATA_STAGING/"

# Backup de modelos
rsync -av "$REPO/DATA_STAGING/*/models/" \
  "$BACKUP_DIR/$DATE/models/"

# Backup de transações (CRÍTICO!)
rsync -av "$REPO/DATA_STAGING/*/transactions/" \
  "$BACKUP_DIR/$DATE/transactions/"

# Backup de logs
rsync -av "$REPO/DATA_STAGING/*/logs/" \
  "$BACKUP_DIR/$DATE/logs/"

# Backup de configs
cp -r "$REPO/configs/" "$BACKUP_DIR/$DATE/configs/"
```

## 📋 Checklist de Organização

- [ ] Criar estrutura DATA_STAGING/
- [ ] Configurar logging robusto
- [ ] Implementar versionamento de modelos
- [ ] Adicionar metadados em todas as transações
- [ ] Salvar métricas diárias
- [ ] Configurar backup automático
- [ ] Documentar cada experimento
- [ ] Nunca deletar dados históricos

## 🚀 Próximos Passos

1. Mover dados atuais para DATA_ARCHIVE (preservar!)
2. Criar estrutura DATA_STAGING
3. Configurar logging detalhado
4. Rodar shadow trading com logs completos
5. Analisar resultados após 7 dias
6. Iterar e melhorar

---

**Lembre-se: Dados são seu maior ativo. Preserve, organize, analise!**
