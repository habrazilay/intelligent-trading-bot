# Planejamento Futuro: Arquitetura de Dados & Logging

**Status:** Planejamento/Discussão
**Prioridade:** Média (após teste orderflow)
**Timeline:** Q1 2025

---

## 🗂️ Refatoração da Estrutura de Dados

### Estrutura Atual (Subótima)

```
DATA_ITB_5m/
└── BTCUSDT/
    ├── klines.parquet
    ├── data.csv
    ├── features_aggressive.csv
    ├── matrix_aggressive.csv
    ├── predictions_aggressive.csv
    ├── signals_aggressive.csv
    └── MODELS_AGGRESSIVE_V1/
        ├── high_040_4_lgbm.pkl
        └── low_040_4_lgbm.pkl
```

**Problemas:**
- ❌ `MODELS_AGGRESSIVE_V1` enterrada dentro da pasta do símbolo
- ❌ Difícil comparar modelos entre símbolos
- ❌ Sem separação clara de responsabilidades
- ❌ Nome da variante (`aggressive`) espalhado nos nomes dos arquivos

---

### Estrutura Proposta (Melhor)

```
data/
├── {symbol}/
│   ├── {freq}/
│   │   ├── raw/
│   │   │   └── klines.parquet
│   │   ├── processed/
│   │   │   ├── data.csv
│   │   │   └── features.csv
│   │   └── labeled/
│   │       └── matrix.csv
│   └── orderbook/
│       └── snapshots_*.parquet
│
└── models/
    ├── {symbol}/
    │   ├── {freq}/
    │   │   ├── {variant}/          # aggressive, conservative, orderflow
    │   │   │   ├── {algo}/          # lgbm, logreg, automl
    │   │   │   │   ├── {label}/     # high_040_4, low_040_4
    │   │   │   │   │   ├── model.pkl
    │   │   │   │   │   ├── metadata.json
    │   │   │   │   │   └── metrics.json
```

**Exemplo:**
```
data/
├── BTCUSDT/
│   ├── 5m/
│   │   ├── raw/klines.parquet
│   │   ├── processed/features.csv
│   │   └── labeled/matrix.csv
│   └── orderbook/
│       └── snapshots_20251210.parquet
│
└── models/
    └── BTCUSDT/
        └── 5m/
            ├── aggressive/
            │   └── lgbm/
            │       ├── high_040_4/
            │       │   ├── model.pkl
            │       │   ├── metadata.json  # data de treino, features, hyperparams
            │       │   └── metrics.json   # win rate, sharpe, etc
            │       └── low_040_4/
            │           └── ...
            └── orderflow/
                └── automl/
                    └── high_040_4/
                        └── ...
```

**Benefícios:**
- ✅ Hierarquia clara: symbol → freq → variant → algo → label
- ✅ Fácil encontrar/comparar modelos
- ✅ Separação: data vs models
- ✅ Metadata + métricas com cada modelo
- ✅ Versionamento embutido (pasta = versão)

---

### Estratégia de Migração

**Quando:** Após teste orderflow (17/dez em diante)

**Esforço:** ~1-2 dias
- Atualizar todos os scripts para usar novos caminhos
- Escrever script de migração (copiar antigo → nova estrutura)
- Testar pipeline end-to-end
- Atualizar configs

**Compatibilidade retroativa:**
```python
# Adicionar resolvedor de caminho
def get_model_path(symbol, freq, variant, algo, label):
    # Tentar nova estrutura primeiro
    new_path = f"models/{symbol}/{freq}/{variant}/{algo}/{label}/model.pkl"
    if os.path.exists(new_path):
        return new_path

    # Voltar para estrutura antiga
    old_path = f"DATA_ITB_{freq}/{symbol}/MODELS_{variant.upper()}_V1/{label}_{algo}.pkl"
    return old_path
```

---

## 💾 Migração de Banco de Dados (BigData)

### Problema: Armazenamento Baseado em Arquivos Não Escala

**Abordagem atual:**
```
Arquivos CSV: 51,864 linhas × 35 colunas = ~12 MB
Arquivos Parquet: ~500 KB cada

Problemas:
- Não consegue fazer queries eficientes (precisa pandas.read_csv)
- Sem indexação (buscas lentas)
- Sem acesso concorrente (locks de arquivo)
- Sem agregações (GROUP BY, JOIN)
- Difícil analisar tendências históricas
```

**Quando se torna crítico:**
- Múltiplos símbolos (5+ símbolos × 3 timeframes = 15 datasets)
- Profundidade histórica (2+ anos de dados 1m = milhões de linhas)
- Queries em tempo real (precisam de buscas sub-segundo)
- Acesso multi-usuário (dashboards, análise, trading)

---

### Proposta: TimescaleDB (PostgreSQL para Séries Temporais)

**Por que TimescaleDB:**
- ✅ Compatível com PostgreSQL (SQL familiar)
- ✅ Otimizado para séries temporais (particionamento automático)
- ✅ Compressão (economia de espaço 50-90%)
- ✅ Agregações contínuas (pré-computar métricas)
- ✅ Open source + opção self-hosted

**Design do Schema:**

```sql
-- Dados OHLCV (raw)
CREATE TABLE ohlcv (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    freq TEXT NOT NULL,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume NUMERIC,
    PRIMARY KEY (time, symbol, freq)
);

SELECT create_hypertable('ohlcv', 'time');

-- Features (processadas)
CREATE TABLE features (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    freq TEXT NOT NULL,
    close_sma_3 NUMERIC,
    close_rsi_14 NUMERIC,
    vol_regime INTEGER,
    -- ... todas as features
    PRIMARY KEY (time, symbol, freq)
);

SELECT create_hypertable('features', 'time');

-- Labels
CREATE TABLE labels (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    freq TEXT NOT NULL,
    high_040_4 BOOLEAN,
    low_040_4 BOOLEAN,
    -- ... todas as labels
    PRIMARY KEY (time, symbol, freq)
);

SELECT create_hypertable('labels', 'time');

-- Predictions (outputs dos modelos)
CREATE TABLE predictions (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    freq TEXT NOT NULL,
    model_name TEXT NOT NULL,      -- ex: "lgbm_aggressive"
    label TEXT NOT NULL,            -- ex: "high_040_4"
    probability NUMERIC,
    prediction BOOLEAN,
    PRIMARY KEY (time, symbol, freq, model_name, label)
);

SELECT create_hypertable('predictions', 'time');

-- Trades (executados)
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,            -- 'BUY' ou 'SELL'
    price NUMERIC NOT NULL,
    quantity NUMERIC NOT NULL,
    model_name TEXT,
    signal_strength NUMERIC,
    pnl NUMERIC,                   -- P&L Realizado
    status TEXT                    -- 'OPEN', 'CLOSED', 'CANCELLED'
);

CREATE INDEX ON trades (time DESC);
CREATE INDEX ON trades (symbol, time DESC);

-- Métricas de performance (agregadas)
CREATE MATERIALIZED VIEW daily_performance
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS day,
    symbol,
    model_name,
    COUNT(*) AS total_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)::FLOAT / COUNT(*) AS win_rate,
    SUM(pnl) AS total_pnl,
    AVG(pnl) AS avg_pnl,
    MAX(pnl) AS max_win,
    MIN(pnl) AS max_loss
FROM trades
WHERE status = 'CLOSED'
GROUP BY day, symbol, model_name;
```

**Exemplos de Queries:**

```sql
-- Obter features recentes para predição
SELECT * FROM features
WHERE symbol = 'BTCUSDT'
  AND freq = '5m'
  AND time >= NOW() - INTERVAL '1 hour'
ORDER BY time DESC
LIMIT 12;

-- Performance do modelo últimos 30 dias
SELECT
    symbol,
    model_name,
    win_rate,
    total_pnl,
    total_trades
FROM daily_performance
WHERE day >= NOW() - INTERVAL '30 days'
ORDER BY total_pnl DESC;

-- Comparar modelos Azure vs GCP
SELECT
    CASE
        WHEN model_name LIKE '%azure%' THEN 'Azure'
        WHEN model_name LIKE '%gcp%' THEN 'GCP'
    END AS cloud,
    AVG(win_rate) AS avg_win_rate,
    SUM(total_pnl) AS total_profit
FROM daily_performance
WHERE day >= NOW() - INTERVAL '7 days'
GROUP BY cloud;
```

---

### Migração de CSV → TimescaleDB

**Fase 1: Escrita dupla (1 semana)**
```python
# Escrever tanto em CSV quanto em DB
df.to_csv('features.csv')
df.to_sql('features', engine, if_exists='append')
```

**Fase 2: Ler do DB (1 semana de testes)**
```python
# Ler do DB ao invés de CSV
df = pd.read_sql(
    "SELECT * FROM features WHERE symbol = %s AND freq = %s",
    engine,
    params=('BTCUSDT', '5m')
)
```

**Fase 3: Depreciar CSV (após 2 semanas)**
```python
# Remover escritas em CSV
# Manter CSV como backup por 1 mês
```

---

## 📝 Arquitetura de Logging

### Estado Atual: Básico

```python
# Print statements simples ou logging básico
logging.info("Training started")
print(f"Win rate: {win_rate}")
```

**Problemas:**
- ❌ Sem logs estruturados (difícil fazer parse)
- ❌ Logs espalhados (arquivos, stdout, stderr)
- ❌ Sem agregação centralizada
- ❌ Difícil buscar/filtrar
- ❌ Sem política de retenção

---

### Proposta: Logging Estruturado + ELK Stack

**Tech Stack:**
- **Loguru** (Python): Melhor que logging stdlib
- **Elasticsearch**: Armazenar + buscar logs
- **Kibana**: Visualizar + dashboard
- **Filebeat**: Enviar logs para Elasticsearch

**Exemplo de Logging Estruturado:**

```python
from loguru import logger
import sys

# Configurar logger
logger.remove()  # Remover handler padrão
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)
logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    compression="zip",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
)

# Campos estruturados extras
logger.bind(
    symbol="BTCUSDT",
    freq="5m",
    model="lgbm_aggressive"
).info(
    "Model training completed",
    win_rate=0.58,
    sharpe=2.1,
    trades=300
)

# Output (JSON para Elasticsearch):
# {
#   "time": "2025-12-10 10:30:00",
#   "level": "INFO",
#   "message": "Model training completed",
#   "symbol": "BTCUSDT",
#   "freq": "5m",
#   "model": "lgbm_aggressive",
#   "extra": {
#     "win_rate": 0.58,
#     "sharpe": 2.1,
#     "trades": 300
#   }
# }
```

**Níveis de Log:**

```python
# DEBUG: Info de diagnóstico detalhada
logger.debug("Feature calculation", feature_name="close_sma_3", value=99500.5)

# INFO: Operações normais
logger.info("Pipeline step completed", step="merge", duration_sec=5.2)

# WARNING: Problemas potenciais
logger.warning("High API latency", latency_ms=1500, threshold_ms=1000)

# ERROR: Falhas que não param execução
logger.error("Failed to fetch orderbook", symbol="SOLUSDT", error=str(e))

# CRITICAL: Falhas severas
logger.critical("Trading halted", reason="max_drawdown_exceeded", drawdown_pct=15.2)
```

---

### Setup ELK Stack (Docker)

```yaml
# docker-compose.yml
version: '3.8'

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    ports:
      - "9200:9200"
    volumes:
      - es-data:/usr/share/elasticsearch/data

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch

  filebeat:
    image: docker.elastic.co/beats/filebeat:8.11.0
    volumes:
      - ./logs:/logs:ro
      - ./filebeat.yml:/usr/share/filebeat/filebeat.yml:ro
    depends_on:
      - elasticsearch

volumes:
  es-data:
```

**Config do Filebeat:**
```yaml
# filebeat.yml
filebeat.inputs:
  - type: log
    enabled: true
    paths:
      - /logs/*.log
    json.keys_under_root: true
    json.add_error_key: true

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  index: "itb-logs-%{+yyyy.MM.dd}"

setup.kibana:
  host: "kibana:5601"
```

**Uso:**
```bash
# Iniciar ELK stack
docker-compose up -d

# Ver logs no Kibana
# http://localhost:5601
# Criar index pattern: itb-logs-*
# Query: symbol:"BTCUSDT" AND level:"ERROR"
```

---

### Organização de Logs

**Estrutura de pastas:**
```
logs/
├── app/
│   ├── app_2025-12-10.log         # Aplicação geral
│   └── app_2025-12-11.log
├── trading/
│   ├── trading_2025-12-10.log     # Execução de trades
│   └── trading_2025-12-11.log
├── models/
│   ├── training_2025-12-10.log    # Treinamento de modelos
│   └── predictions_2025-12-10.log # Predições
├── cloud/
│   ├── azure_2025-12-10.log       # Operações Azure
│   └── gcp_2025-12-10.log         # Operações GCP
└── errors/
    └── errors_2025-12-10.log      # Todos os erros (agregados)
```

**Retenção:**
- Logs da app: 30 dias
- Logs de trading: 1 ano (compliance legal)
- Logs de modelos: 90 dias
- Logs de erro: 6 meses

---

## 🔍 Monitoramento & Observabilidade

### Métricas a Rastrear

**Métricas de Sistema:**
```python
# CPU, Memória, Disco
import psutil

logger.info(
    "System metrics",
    cpu_percent=psutil.cpu_percent(),
    memory_percent=psutil.virtual_memory().percent,
    disk_percent=psutil.disk_usage('/').percent
)
```

**Métricas de Trading:**
```python
# Win rate, P&L, Sharpe
logger.info(
    "Daily trading summary",
    date=date.today(),
    symbol="BTCUSDT",
    trades=15,
    wins=9,
    losses=6,
    win_rate=0.60,
    total_pnl=45.30,
    sharpe_ratio=2.1
)
```

**Performance de Modelos:**
```python
# Detecção de drift
logger.warning(
    "Model drift detected",
    model="lgbm_aggressive",
    backtest_win_rate=0.58,
    live_win_rate=0.51,
    drift=0.07  # 7% de degradação
)
```

**Custos de Cloud:**
```python
# Azure + GCP spending
logger.info(
    "Cloud costs",
    date=date.today(),
    azure_cost_usd=12.50,
    gcp_cost_usd=35.80,
    total_cost_usd=48.30,
    budget_remaining_usd=1221.70
)
```

---

### Alertas

**Integração Slack/Telegram:**

```python
import requests

def send_alert(message, level="INFO"):
    """Enviar alerta para Telegram"""
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    emoji = {
        "INFO": "ℹ️",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "CRITICAL": "🚨"
    }

    text = f"{emoji[level]} {message}"

    requests.post(
        f"https://api.telegram.org/bot{telegram_token}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )

# Uso
if daily_loss > 5:
    send_alert(
        f"CRITICAL: Perda diária {daily_loss}% excede limite!",
        level="CRITICAL"
    )
```

**Condições de Alerta:**

```yaml
CRITICAL (ação imediata):
  - Perda diária > 5%
  - Trading parado (qualquer motivo)
  - Custos cloud > orçamento
  - Falha de autenticação API

ERROR (corrigir em horas):
  - Treinamento de modelo falhou
  - Erro no pipeline de dados
  - Coleta de orderbook parou
  - Win rate < 50% por 3 dias

WARNING (monitorar):
  - Alta latência API (>1s)
  - Drift de modelo > 5%
  - Volume/volatilidade incomum
  - Custos cloud > 80% orçamento

INFO (resumo diário):
  - Relatório P&L diário
  - Resumo de performance dos modelos
  - Resumo de custos cloud
```

---

## 📊 Dashboard (Futuro)

**Dashboard Grafana:**

```yaml
Painéis:
  - P&L em tempo real (gráfico de linha)
  - Win rate por símbolo (gráfico de barras)
  - Posições abertas (tabela)
  - Custos cloud (área empilhada)
  - Drift de modelos (heatmap)
  - Latência API (gauge)
  - Recursos do sistema (CPU/Memória)

Refresh: A cada 10 segundos
Time range: Últimas 24 horas (configurável)
```

**Fonte de métricas:**
- TimescaleDB (trades, predições)
- Prometheus (métricas de sistema)
- Elasticsearch (agregações de logs)

---

## 🛠️ Prioridade de Implementação

### Fase 1 (Imediato - Atual)
- ✅ Armazenamento baseado em arquivos (CSV/Parquet)
- ✅ Logging básico (print/logging)
- ✅ Monitoramento manual

### Fase 2 (Após teste orderflow - Jan)
- [ ] Logging estruturado (Loguru)
- [ ] Rotação de logs + retenção
- [ ] Alertas Telegram (eventos críticos)
- [ ] Rastreamento básico de métricas (win rate, P&L)

### Fase 3 (Escala - Fev/Mar)
- [ ] Migração TimescaleDB
- [ ] Setup ELK stack
- [ ] Dashboard Grafana
- [ ] Alertas automatizados (todos os níveis)

### Fase 4 (Produção - Q2)
- [ ] Replicação multi-região
- [ ] Monitoramento avançado (APM)
- [ ] Automação de otimização de custos
- [ ] Logging de compliance (audit trail)

---

## 💰 Estimativas de Custo

**ELK Stack (Self-hosted):**
```
VM AWS/Azure: t3.medium (2 vCPU, 4GB RAM)
  Custo: ~$30/mês
  Storage: 100GB SSD (~$10/mês)
  Total: ~$40/mês

Alternativa: Elastic Cloud
  Tier padrão: ~$95/mês
  Gerenciado, sem overhead de ops
```

**TimescaleDB:**
```
Self-hosted (mesma VM do ELK):
  Custo incremental: ~$5/mês (só storage)

Gerenciado (Timescale Cloud):
  Tier starter: $50/mês
  Inclui backups, HA
```

**Custo Mensal Total (Stack Completo):**
```
Self-hosted: ~$45/mês
Gerenciado: ~$145/mês

Economia vs gerenciado: $100/mês (70%)
Tradeoff: Precisa gerenciar infraestrutura
```

---

## 📝 Checklist de Migração

**Estrutura de Dados:**
- [ ] Design da nova estrutura de pastas
- [ ] Escrever script de migração
- [ ] Testar com dados de amostra
- [ ] Atualizar todos os scripts (download → signals)
- [ ] Atualizar configs
- [ ] Backup da estrutura antiga
- [ ] Executar migração
- [ ] Validar integridade dos dados
- [ ] Atualizar documentação

**Banco de Dados:**
- [ ] Instalar TimescaleDB (local ou cloud)
- [ ] Design do schema
- [ ] Escrever scripts de ingestão de dados
- [ ] Escrita dupla (CSV + DB) por 1 semana
- [ ] Testar performance de queries
- [ ] Mudar leituras para DB
- [ ] Depreciar escritas CSV
- [ ] Arquivar CSVs antigos

**Logging:**
- [ ] Instalar Loguru
- [ ] Refatorar print → logger
- [ ] Adicionar campos estruturados
- [ ] Configurar rotação de logs
- [ ] Setup de alertas Telegram
- [ ] (Opcional) Setup ELK stack
- [ ] Criar dashboards Kibana

---

## 🎯 Critérios de Sucesso

**Estrutura de Dados:**
- ✅ Modelos organizados por: symbol/freq/variant/algo/label
- ✅ Separação clara: data vs models
- ✅ Metadata + métricas com cada modelo
- ✅ Fácil comparar entre símbolos/variantes

**Banco de Dados:**
- ✅ Resposta de query < 100ms para dados recentes
- ✅ Suportar 1M+ linhas por símbolo
- ✅ Taxa de compressão > 50%
- ✅ Zero perda de dados durante migração

**Logging:**
- ✅ Logs estruturados (JSON)
- ✅ Buscável em <1 segundo
- ✅ Alertas entregues < 30 segundos
- ✅ 99.9% entrega de logs (sem drops)
- ✅ Audit trail claro (quem/o quê/quando)

---

**Status do Documento:** Planejamento
**Última Atualização:** 2025-12-10
**Próxima Revisão:** Após teste orderflow (2025-12-17)
