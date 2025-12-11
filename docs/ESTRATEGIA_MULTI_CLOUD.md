# Estratégia de Trading Multi-Cloud

**Missão:** Maximizar lucros usando créditos Azure + GCP através de deployment especializado de modelos e diversificação de portfólio.

**Status:** Fase de planejamento
**Timeline:** 4 semanas (10 dez - 7 jan)
**Orçamento:** $970 GCP + $300 Azure = $1,270 total

---

## 🎯 Filosofia Central

**Especialização + Ensemble = Melhores Retornos**

Cada cloud faz o que faz de MELHOR:
- **Azure:** Modelos rápidos, baratos, conservadores (baseline)
- **GCP:** ML avançado, deep learning, inteligência orderflow

Depois combinamos resultados via votação ensemble para decisões finais de trading.

---

## ⚡ Divisão Azure: "Velocidade & Baseline"

### Missão
Modelos rápidos, baratos, conservadores para mercados de alta liquidez.

### Stack
```yaml
Modelos:
  - Logistic Regression (baseline)
  - LightGBM (comprovado em competições Kaggle)
  - Random Forest (complemento ensemble)

Símbolos: BTC, ETH
  Razão: Alta liquidez, padrões estáveis, spreads baixos

Timeframes: 1m, 5m
  Razão: Oportunidades de scalping, muitos trades/dia

Features:
  - TA clássico (SMA, RSI, ATR)
  - Spread features (bid-ask)
  - Detecção de regime (classificação vol)

Frequência de Treinamento: Semanal
  Custo: ~$5-10/semana
  Orçamento Total: ~$80 dos $300 créditos
```

### Estratégia de Trading
```yaml
Tipo: Conservador
Alocação de Capital: 60% do total ($600 se $1,000 total)
Risco por Trade: 0.5%
Profit Alvo: 0.3%
Win Rate Alvo: ≥55%
Trades/Dia: ~10
```

### Pipeline ML Azure
```bash
# Treinamento semanal
az container create \
  --name itb-train-azure \
  --image itbacr.azurecr.io/itb-bot:latest \
  --command-line "sh -c '
    python -m scripts.merge -c configs/btcusdt_5m_azure.jsonc &&
    python -m scripts.features -c configs/btcusdt_5m_azure.jsonc &&
    python -m scripts.labels -c configs/btcusdt_5m_azure.jsonc &&
    python -m scripts.train -c configs/btcusdt_5m_azure.jsonc
  '"
```

---

## 🧠 Divisão GCP: "Inteligência & Inovação"

### Missão
ML avançado com orderflow para altcoins de maior volatilidade.

### Stack
```yaml
Modelos:
  - Vertex AutoML (engenharia automática de features)
  - LSTM (padrões de sequência temporal)
  - Transformer (mecanismo de atenção)

Símbolos: SOL, BNB, XRP, MATIC
  Razão: Maior volatilidade = mais potencial de lucro

Timeframes: 5m, 15m
  Razão: Sinais de orderflow mais claros em 5-15m

Features:
  - Orderflow L2 (19 features)
  - Bid-ask imbalance (profundidades: 5, 10, 20)
  - Pressão do order book (análise de slope)
  - Detecção de walls (ordens grandes)

Treinamento:
  - AutoML: $50 (teste conservador)
  - LSTM GPU (T4): $30 (se AutoML ≥53%)
  Orçamento Total: ~$300 dos $970 créditos
```

### Estratégia de Trading
```yaml
Tipo: Agressivo
Alocação de Capital: 30% do total ($300 se $1,000 total)
Risco por Trade: 1.0%
Profit Alvo: 0.5%
Win Rate Alvo: ≥52%
Trades/Dia: ~5
```

### Pipeline ML GCP
```bash
# Upload dados para BigQuery
make gcp-upload-bigquery CONFIG=configs/sol_5m_orderflow.jsonc

# Treinar com AutoML
make gcp-automl CONFIG=configs/sol_5m_orderflow.jsonc BUDGET=1

# Se sucesso (≥53% win rate), treinar LSTM
make gcp-lstm CONFIG=configs/sol_5m_orderflow.jsonc
```

---

## 🎯 Estratégia Meta-Model Ensemble

### Lógica de Decisão

```python
def selecionar_modelo(condicoes_mercado):
    """
    Seleção dinâmica de modelo baseada em volatilidade do mercado.
    """
    volatilidade = get_volatilidade_atual()

    if volatilidade < 0.5:
        # Baixa volatilidade → padrões estáveis
        # Usar baseline Azure (mais confiável)
        return azure_lgbm_btc

    elif volatilidade < 1.5:
        # Média volatilidade → orderflow brilha
        # Usar modelos orderflow GCP
        return gcp_automl_sol

    else:
        # Alta volatilidade (>1.5) → arriscado
        # Pausar ou usar mais conservador
        return azure_logreg_eth  # ou PAUSAR
```

### Votação Ponderada

```python
# Predição ensemble de todos modelos
sinal_final = (
    0.4 × predicao_azure_lgbm +
    0.3 × predicao_gcp_automl +
    0.2 × predicao_azure_logreg +
    0.1 × predicao_gcp_lstm
)

# Só fazer trade se alta confiança
if sinal_final > 0.6:
    executar_trade()
```

**Justificativa:**
- LGBM recebe maior peso (baseline comprovado)
- AutoML em segundo (inovação orderflow)
- LogReg fornece âncora conservadora
- LSTM experimental (menor peso)

---

## 💰 Alocação de Portfólio

### Distribuição de Capital

```
Capital Total: $1,000

Divisão Azure (Conservador):
  - $600 alocados
  - Scalping BTC/ETH
  - Modelos: LGBM + LogReg
  - Alvo: $15/dia
  - Mensal: $450 (75% APY)

Divisão GCP (Agressivo):
  - $300 alocados
  - Plays de volatilidade SOL/BNB/XRP
  - Modelos: AutoML + LSTM + orderflow
  - Alvo: $12/dia
  - Mensal: $360 (120% APY)

Reserva de Emergência:
  - $100 intocado
  - Seguro contra drawdowns
```

### Rebalanceamento Semanal

Baseado em performance, shift capital:

```python
if azure_win_rate > gcp_win_rate + 5%:
    shift_capital(de_gcp, para_azure, quantidade=10%)
elif gcp_win_rate > azure_win_rate + 5%:
    shift_capital(de_azure, para_gcp, quantidade=10%)
```

---

## 🔄 Teste A/B em Tempo Real

### Teste Paralelo em Shadow Mode

Rodar ambas clouds simultaneamente em shadow mode por 1 semana:

```yaml
Resultados Semana 1:
  Azure LGBM (BTC 5m):
    Win Rate: 58%
    Lucro: +$45
    Decisão: ✅ Aumentar alocação +10%

  GCP AutoML (SOL 5m):
    Win Rate: 51%
    Lucro: +$12
    Decisão: ⚠️ Monitorar, sem mudanças

Resultados Semana 2:
  Azure LGBM (BTC 5m):
    Win Rate: 52%
    Lucro: +$18
    Decisão: ⚠️ Leve queda

  GCP AutoML+orderflow (SOL 5m):
    Win Rate: 61%
    Lucro: +$67
    Decisão: ✅ Aumentar alocação +10%
```

### Regras de Auto-Ajuste

```yaml
Gatilhos:
  - Delta win rate > 5% entre clouds → shift 10% capital
  - Loss diária > 5% em qualquer cloud → pausar essa cloud
  - Ambas clouds <50% win rate por 3 dias → PAUSAR tudo

Ações:
  - Rebalancear capital semanalmente
  - Re-treinar modelos se win rate cair
  - Adicionar/remover símbolos baseado em lucratividade
```

---

## 📊 Estratégia Multi-Mercado

### Alocação de Símbolos por Cloud

| Cloud | Símbolo | Timeframe | Estratégia | Justificativa |
|-------|---------|-----------|------------|---------------|
| **Azure** | BTC | 1m | Scalping rápido | Maior liquidez, menor spread |
| **Azure** | ETH | 5m | Seguir momentum | Correlaciona com BTC mas com lag |
| **GCP** | SOL | 5m | Vantagem orderflow | Alta volatilidade, orderflow funciona |
| **GCP** | BNB | 15m | Seguir tendência | Token exchange, padrões únicos |
| **GCP** | XRP | 5m | Reversão à média | Alta oscilação, bom para scalping |

### Benefícios de Correlação

**Baixa correlação** entre símbolos = **risco sistêmico reduzido**:

```
Correlação BTC-ETH: 0.85 (alta, esperado)
Correlação BTC-SOL: 0.65 (média)
Correlação BTC-XRP: 0.45 (baixa)
Correlação SOL-BNB: 0.50 (média)

Correlação do portfólio: ~0.60 (diversificado!)
```

Se BTC crashar → SOL/XRP podem não ser afetados ou até subir.

---

## 💵 Projeções de ROI

### Cenário Conservador (53% win rate)

```
Capital: $1,000
Trades/dia: 15 (Azure: 10, GCP: 5)
Lucro médio por win: 0.3%
Win rate: 53%

Cálculo:
  Trades vencedores/dia: 15 × 0.53 = 7.95
  Lucro diário: 7.95 × 0.3% × $1,000 = $23.85
  Fees (0.08%): -$4.80
  Líquido diário: $19/dia

Mensal: $19 × 30 = $570
Anual: $570 × 12 = $6,840
ROI: 68% por ano
```

### Cenário Otimista (58% win rate com orderflow)

```
Capital: $1,000
Trades/dia: 15
Win rate: 58%

Líquido diário: $32/dia
Mensal: $960
Anual: $11,520
ROI: 115% por ano
```

### Compounding (Reinvestir Lucros)

```
Início: $1,000

Mês 1: $1,570 (+57%)
Mês 2: $2,465 (+146%)
Mês 3: $3,870 (+287%)
Mês 6: $12,200 (+1,120%)
Ano 1: $150,000+ (crescimento exponencial)
```

**Nota:** Assume win rate consistente de 58% e reinvestimento total dos lucros.

---

## 🛡️ Gestão de Risco Multi-Cloud

### Circuit Breakers por Cloud

**Regras Azure:**
```yaml
Loss diária > 2%: Pausar trading
3 dias consecutivos perdendo: Re-treinar modelos
Win rate semanal < 52%: Mudar para GCP ou PAUSAR
Divergência modelo (backtest vs live > 5%): Investigar
```

**Regras GCP:**
```yaml
Loss diária > 3%: Pausar (maior tolerância ao risco)
Win rate semanal < 50%: Re-treinar com mais dados
Custos treinamento GPU > $50/semana: Otimizar ou pausar
Falha na coleta orderbook: Voltar para Azure
```

### Breakers Globais do Portfólio

```yaml
PARADAS CRÍTICAS:
  - Loss total portfólio > 5% em 1 dia → PAUSAR TUDO
  - Win rate combinado < 50% por 5 dias → PARAR & ANALISAR
  - Drawdown > 15% do pico → Revisão manual necessária
  - Falha API Binance → Auto-pausar todo trading

PROTOCOLO DE RECUPERAÇÃO:
  1. Parar todo trading
  2. Analisar modo de falha (modelo, dados, mercado)
  3. Re-treinar com dados recentes
  4. Teste em shadow mode por 3 dias
  5. Retomar com 50% capital se win rate recuperar
```

---

## 🚀 Timeline de Implementação

### Semana 1: 10-17 dez (Preparação)

**Objetivos:**
- Completar coleta orderbook (7 dias)
- Upload dados para ambas clouds
- Separar arquivos requirements

**Tarefas:**
```bash
# Azure
- Upload dados BTCUSDT/ETHUSDT para Azure Blob Storage
- Criar configs: btcusdt_5m_azure.jsonc, ethusdt_5m_azure.jsonc
- Testar pipeline: download → merge → features → labels → train

# GCP
- Upload dados SOL/BNB/XRP para BigQuery
- Criar configs: sol_5m_gcp_orderflow.jsonc
- Verificar qualidade dados orderflow (7 dias coleta)

# Código
- Separar requirements.txt → requirements-azure.txt + requirements-gcp.txt
- Criar workflow treinamento Azure (GitHub Actions)
- Criar workflow treinamento GCP (scripts locais + manual)
```

**Entregas:**
- ✅ 7 dias de dados orderbook
- ✅ Dados uploaded para ambas clouds
- ✅ Configs criados para todos símbolos
- ✅ Requirements separados

---

### Semana 2: 17-24 dez (Treinamento & Backtesting)

**Objetivos:**
- Treinar modelos em ambas clouds
- Backtest e comparar performance
- Selecionar melhores modelos por símbolo

**Tarefas Azure:**
```bash
# Treinar modelos baseline
make pipeline CONFIG=configs/btcusdt_5m_azure.jsonc
make pipeline CONFIG=configs/ethusdt_5m_azure.jsonc

# Modelos treinados:
- Logistic Regression (baseline)
- LightGBM (primário)
- Random Forest (ensemble)

# Backtest 90 dias
python scripts/backtest.py -c configs/btcusdt_5m_azure.jsonc

# Métricas para coletar:
- Win rate
- Sharpe ratio
- Max drawdown
- Profit factor
```

**Tarefas GCP:**
```bash
# Upload dados orderflow
make gcp-upload-bigquery CONFIG=configs/sol_5m_gcp_orderflow.jsonc

# Treinar AutoML (conservador $50)
make gcp-automl CONFIG=configs/sol_5m_gcp_orderflow.jsonc BUDGET=1

# Se win rate ≥53%, treinar LSTM
make gcp-lstm CONFIG=configs/sol_5m_gcp_orderflow.jsonc

# Backtest e comparar
```

**Ponto de Decisão:**
```yaml
Se Azure win rate ≥55% E GCP win rate ≥53%:
  → Prosseguir para Semana 3 (Shadow Mode)

Se Azure ≥55% mas GCP <53%:
  → Usar só Azure, economizar orçamento GCP

Se ambos <53%:
  → ABORTAR estratégia multi-cloud
  → Pivotar para timeframe diário ou re-avaliar
```

**Entregas:**
- ✅ Modelos treinados em ambas clouds
- ✅ Resultados backtest com métricas
- ✅ Decisão go/no-go baseada em win rates

---

### Semana 3: 24-31 dez (Teste Shadow Mode)

**Objetivos:**
- Deploy ambas clouds em shadow mode
- Teste A/B em tempo real
- Coletar métricas de performance ao vivo

**Shadow Mode Azure:**
```bash
# Deploy server com modelos Azure
az container create \
  --name itb-shadow-azure \
  --image itbacr.azurecr.io/itb-bot:latest \
  --command-line "python -m service.server -c configs/btcusdt_5m_azure.jsonc" \
  --environment-variables ENABLE_LIVE_TRADING=0

# Monitorar logs
az container logs --name itb-shadow-azure --follow
```

**Shadow Mode GCP:**
```bash
# Deploy em Compute Engine ou local
python -m service.server -c configs/sol_5m_gcp_orderflow.jsonc

# Configurar ambiente
export ENABLE_LIVE_TRADING=0
export MODEL_PATH=/path/to/gcp/models
```

**Métricas para Rastrear (7 dias):**
```yaml
Por Cloud:
  - Win rate (%)
  - Profit/loss ($)
  - Número de trades
  - Tempo médio de hold
  - Max drawdown
  - Sharpe ratio

Comparação:
  - Qual cloud performou melhor?
  - Há correlação entre sinais?
  - Estratégia ensemble melhora?
```

**Revisão Diária:**
```bash
# Analisar logs shadow mode
make analyze-staging LOG_FILE=logs/azure_shadow.log
make analyze-staging LOG_FILE=logs/gcp_shadow.log

# Comparar resultados
python scripts/compare_clouds.py \
  --azure logs/azure_shadow.log \
  --gcp logs/gcp_shadow.log
```

**Entregas:**
- ✅ 7 dias de dados shadow mode ao vivo
- ✅ Comparação performance Azure vs GCP
- ✅ Estratégia votação ensemble testada
- ✅ Seleção final de modelos

---

### Semana 4: 1-7 jan (Lançamento Trading Ao Vivo)

**Objetivos:**
- Iniciar trading ao vivo com capital real
- Monitorar e ajustar alocação
- Implementar auto-rebalanceamento

**Fase 1: Início Conservador ($100 teste)**

```yaml
Dias 1-3: Testar com capital mínimo
  Azure: $60 (BTC + ETH)
  GCP: $30 (SOL)
  Reserva: $10

Critérios para escalar:
  - Win rate ≥55% em ambas clouds
  - Sem erros críticos (API, execução)
  - Drawdown <3%
```

**Fase 2: Escalar para Capital Total ($1,000)**

```yaml
Dias 4-7: Se Fase 1 bem-sucedida
  Azure: $600 (60% alocação)
  GCP: $300 (30% alocação)
  Reserva: $100 (10% emergência)

Monitoramento diário:
  - Rastreamento P&L
  - Win rate vs backtest
  - Divergência performance clouds
  - Métricas de risco (Sharpe, max DD)
```

**Lógica Auto-Rebalanceamento:**

```python
# Rebalanceamento semanal
if azure_sharpe > gcp_sharpe + 0.3:
    shift_capital(gcp → azure, 10%)
elif gcp_sharpe > azure_sharpe + 0.3:
    shift_capital(azure → gcp, 10%)

# Paradas de emergência
if daily_loss > 5%:
    pausar_trading()
    enviar_alerta("CRÍTICO: Loss diária excedeu")
```

**Entregas:**
- ✅ Trading ao vivo operacional
- ✅ Rastreamento P&L real
- ✅ Auto-rebalanceamento implementado
- ✅ Dashboard monitoramento performance

---

## 📈 Mês 2+ (Escalar & Otimizar)

### Melhoria Contínua

**Adicionar Mais Símbolos (se lucrativo):**
```yaml
Expansão Azure:
  - Adicionar MATIC (se BTC/ETH lucrativo)
  - Adicionar AVAX (alta correlação com ETH)

Expansão GCP:
  - Adicionar DOT (orderflow pode funcionar)
  - Adicionar ATOM (volátil, bom para ML)
```

**Melhorias de Modelos:**
```yaml
Meta-Model Ensemble:
  - Treinar stacking classifier em outputs clouds
  - Melhorar pesos votação dinamicamente
  - Adicionar detecção regime mercado

Engenharia Features:
  - Adicionar features cross-symbol (correlação BTC → ETH)
  - Features time-of-day (sessões Asia/Europa/US)
  - Mudanças depth order book (métricas velocidade)
```

**Infraestrutura:**
```yaml
Monitoramento:
  - Dashboard unificado (Grafana)
  - Agregar logs de ambas clouds
  - Alertas em tempo real (Telegram/email)

Database:
  - Migrar para TimescaleDB (otimizado time-series)
  - Armazenar: trades, sinais, predições modelos, métricas
  - Habilitar análise histórica

Otimização Custos:
  - Usar spot instances no GCP (60% mais barato)
  - Otimizar tamanhos containers
  - Cachear dados frequentemente usados
```

---

## 🎨 Valor Showcase DevOps

**Skills Multi-Cloud Demonstradas:**

```yaml
Arquitetura Cloud:
  - Deployment híbrido (Azure + GCP)
  - Otimização custos cross-providers
  - Evitar vendor lock-in

Infraestrutura como Código:
  - Terraform (infra Azure)
  - GitHub Actions (CI/CD)
  - Orquestração containers (ACI + Compute Engine)

MLOps:
  - Versionamento modelos (git tags + container tags)
  - Framework teste A/B (shadow mode)
  - Pipelines re-treinamento automatizados
  - Monitoramento performance

Engenharia Dados:
  - Sync dados multi-cloud
  - Pipelines dados tempo real (orderflow)
  - Databases time-series
  - Agregação logs

Gestão Risco:
  - Circuit breakers (baseado em código)
  - Auto-pausa em anomalias
  - Algoritmos alocação capital
```

**Impacto no Currículo:**
```
"Projetei e deployei sistema trading ML multi-cloud:
- Orquestrei Azure + GCP para especialização modelos
- Atingi 58% win rate (8% acima baseline)
- Gerenciei orçamento $1,270 cloud com ROI 200%
- Implementei teste A/B e estratégias ensemble
- Construí monitoramento tempo real e auto-rebalanceamento"
```

---

## 🔧 Arquitetura Técnica

### Recursos Cloud

**Azure:**
```yaml
Resource Group: rg-itb-prod
Storage:
  - stitbprod (Blob Storage)
  - data-itb-5m (File Share)
Compute:
  - Containers ACI (jobs treinamento efêmeros)
Container Registry:
  - itbacr.azurecr.io/itb-bot:azure-latest
```

**GCP:**
```yaml
Project: ninth-goal-464400-e5
Storage:
  - BigQuery: dataset itb_5min
  - Cloud Storage: gs://itb-models/
Compute:
  - Vertex AI (AutoML)
  - Compute Engine com GPU T4 (LSTM)
Container Registry:
  - gcr.io/ninth-goal-464400-e5/itb-bot:gcp-latest
```

### Fluxo de Dados

```
┌─────────────────────────────────────────────────┐
│ Fontes de Dados                                 │
│  - API Binance (OHLCV)                         │
│  - WebSocket Binance (Orderbook L2)            │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ Coleta Local                                    │
│  - download_binance.py → klines.parquet        │
│  - collect_orderbook.py → orderbook.parquet    │
└─────────────────────────────────────────────────┘
                      ↓
           ┌──────────┴──────────┐
           ↓                     ↓
┌──────────────────┐   ┌─────────────────────┐
│ Pipeline Azure   │   │ Pipeline GCP        │
│                  │   │                     │
│ → Azure Blob     │   │ → BigQuery          │
│ → Merge/Features │   │ → Vertex AutoML     │
│ → Labels         │   │ → Treinamento LSTM  │
│ → Train LGBM     │   │ → Export Modelos    │
│ → Export Modelos │   │                     │
└──────────────────┘   └─────────────────────┘
           ↓                     ↓
┌──────────────────────────────────────────────────┐
│ Teste Shadow Mode (Paralelo)                     │
│  - Azure: predições BTC/ETH                      │
│  - GCP: predições SOL/BNB/XRP                    │
│  - Comparar win rates                            │
└──────────────────────────────────────────────────┘
                      ↓
┌──────────────────────────────────────────────────┐
│ Meta-Model Ensemble                              │
│  - Votação ponderada                             │
│  - Detecção regime mercado                       │
│  - Decisão final trade                           │
└──────────────────────────────────────────────────┘
                      ↓
┌──────────────────────────────────────────────────┐
│ Trading Ao Vivo (Binance)                        │
│  - Executar trades                               │
│  - Monitorar P&L                                 │
│  - Auto-rebalancear capital                      │
└──────────────────────────────────────────────────┘
```

---

## 📝 Arquivos de Configuração

### Exemplo Config Azure

```jsonc
// configs/btcusdt_5m_azure.jsonc
{
  "symbol": "BTCUSDT",
  "freq": "5m",
  "data_folder": "./DATA_ITB_5m",

  "labels": ["high_030_4", "low_030_4"],

  "train_features": [
    "close_SMA_3", "close_SMA_6", "close_SMA_12",
    "close_RSI_14",
    "high_low_close_ATR_14",
    "spread_pct_3",
    "vol_regime"
  ],

  "algorithms": [
    {
      "name": "logreg",
      "algo": "sklearn_logreg",
      "train": {
        "C": 1.0,
        "max_iter": 1000
      }
    },
    {
      "name": "lgbm",
      "algo": "lgbm",
      "train": {
        "num_leaves": 31,
        "learning_rate": 0.05,
        "n_estimators": 300
      }
    }
  ],

  "cloud": "azure",
  "deployment": "aci"
}
```

### Exemplo Config GCP

```jsonc
// configs/sol_5m_gcp_orderflow.jsonc
{
  "symbol": "SOLUSDT",
  "freq": "5m",
  "data_folder": "./DATA_ITB_5m",

  "labels": ["high_040_4", "low_040_4"],

  "train_features": [
    // Features orderflow (19)
    "imbalance_5", "imbalance_10", "imbalance_20",
    "bid_pressure", "ask_pressure",
    "bid_wall_count", "ask_wall_count",
    "effective_spread",
    "level1_imbalance",

    // TA básico (complemento)
    "close_SMA_3",
    "close_RSI_14",
    "vol_regime"
  ],

  "feature_sets": [
    {
      "generator": "gen_features_orderflow",
      "config": {
        "orderbook_pattern": "DATA_ORDERBOOK/SOLUSDT_orderbook_*.parquet",
        "depths": [5, 10, 20],
        "freq": "5T"
      }
    }
  ],

  "algorithms": [
    {
      "name": "automl",
      "algo": "vertex_automl",
      "train": {
        "budget_hours": 1,
        "optimization_objective": "maximize-precision-at-recall"
      }
    }
  ],

  "cloud": "gcp",
  "deployment": "vertex"
}
```

---

## 🎯 Métricas de Sucesso

### Alvos de Performance

**Mínimo Viável (Go/No-Go):**
```yaml
Win Rate: ≥53%
Sharpe Ratio: ≥1.0
Max Drawdown: <10%
Profit Factor: ≥1.5
```

**Alvo (Sucesso):**
```yaml
Win Rate: ≥58%
Sharpe Ratio: ≥2.0
Max Drawdown: <5%
Profit Factor: ≥2.0
Lucro Diário: $30+
ROI Mensal: 8%+
```

**Excepcional (Melhor Caso):**
```yaml
Win Rate: ≥65%
Sharpe Ratio: ≥3.0
Max Drawdown: <3%
Profit Factor: ≥3.0
Lucro Diário: $50+
ROI Mensal: 15%+
```

### Métricas Comparação Clouds

Rastrear qual cloud performa melhor:

```python
metricas = {
    "azure": {
        "win_rate": 0.58,
        "sharpe": 2.1,
        "profit": 1250,  # Lucro total em $
        "trades": 300,
        "cost": 80,      # Gasto cloud
        "roi": 1250/80 = 15.6x
    },
    "gcp": {
        "win_rate": 0.61,
        "sharpe": 2.4,
        "profit": 1680,
        "trades": 150,
        "cost": 300,
        "roi": 1680/300 = 5.6x
    }
}

# Vencedor: GCP (maior win rate, Sharpe)
# Mas Azure tem melhor ROI (custo-eficiência)
# Solução: Usar ambos! Diversificação vence.
```

---

## 📚 Dependências

### Separação Requirements

**requirements-azure.txt:**
```txt
# Dependências base (mesmo que requirements.txt)
numpy==2.1.*
pandas==2.*
python-binance>=1.0.32
ta-lib
scikit-learn==1.6.*
lightgbm==4.*
python-dotenv>=1.0.0

# Sem bibliotecas GCP necessárias
```

**requirements-gcp.txt:**
```txt
# Incluir base
-r requirements-azure.txt

# Específico GCP
google-cloud-bigquery>=3.0.0
google-cloud-aiplatform>=1.38.0
google-cloud-storage>=2.10.0

# Deep learning (opcional, para LSTM)
tensorflow==2.19.*
```

**Instalação:**
```bash
# Containers Azure
pip install -r requirements-azure.txt

# Local com GCP
pip install -r requirements-gcp.txt
```

---

## 🚨 Riscos & Mitigação

### Riscos Técnicos

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Overfitting modelos | Alto | Médio | Cross-validation, walk-forward testing |
| Rate limits API | Alto | Baixo | Implementar exponential backoff |
| Outage cloud | Médio | Baixo | Redundância multi-cloud |
| Falha pipeline dados | Alto | Médio | Monitoramento + alertas + fallbacks |
| Delays execução | Médio | Médio | Usar limit orders, slippage aceitável |

### Riscos Financeiros

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Flash crash | Alto | Baixo | Circuit breakers, limites max loss |
| Drawdown sustentado | Alto | Médio | Auto-pausa em -5% diário, -15% total |
| Decay modelo | Médio | Alto | Re-treinamento semanal, monitorar drift |
| Delisting Binance | Baixo | Baixo | Diversificar símbolos |
| Mudança fees | Baixo | Baixo | Monitorar threshold lucratividade |

### Riscos Operacionais

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Erro config | Alto | Baixo | Scripts validação, testes dry-run |
| Créditos insuficientes | Médio | Baixo | Monitorar gasto, alertas em 80% uso |
| Credenciais perdidas | Alto | Baixo | Secrets no GitHub, Azure Key Vault |
| Corrupção dados | Médio | Baixo | Backups diários, versionamento |

---

## 📖 Referências

- [Pricing Azure Container Instances](https://azure.microsoft.com/pt-br/pricing/details/container-instances/)
- [Pricing GCP Vertex AI](https://cloud.google.com/vertex-ai/pricing)
- [Documentação LightGBM](https://lightgbm.readthedocs.io/)
- [Documentação API Binance](https://binance-docs.github.io/apidocs/spot/en/)
- [Multi-Cloud Architecture Best Practices](https://cloud.google.com/architecture/hybrid-and-multi-cloud-patterns-and-practices)

---

## ✅ Próximas Ações

**Imediato (10-17 dez):**
- [ ] Separar requirements.txt → requirements-azure.txt + requirements-gcp.txt
- [ ] Criar configs Azure para BTC/ETH
- [ ] Criar configs GCP para SOL/BNB/XRP
- [ ] Upload dados para Azure Blob + GCP BigQuery
- [ ] Completar coleta orderbook 7 dias

**Semana 2 (17-24 dez):**
- [ ] Treinar modelos Azure (baseline LGBM)
- [ ] Treinar GCP AutoML (orderflow)
- [ ] Backtest ambos, comparar win rates
- [ ] Decisão go/no-go

**Semana 3 (24-31 dez):**
- [ ] Deploy shadow mode em ambas clouds
- [ ] Teste A/B por 7 dias
- [ ] Implementar votação ensemble

**Semana 4 (1-7 jan):**
- [ ] Lançar trading ao vivo (teste $100)
- [ ] Escalar para $1,000 se sucesso
- [ ] Monitorar e otimizar

---

**Status Documento:** Planejamento
**Última Atualização:** 2025-12-10
**Próxima Revisão:** 2025-12-17 (após coleta orderbook)
