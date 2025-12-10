# 🚀 Quick Start - GCP Setup & Order Flow Test

**Goal:** Aproveitar seus **~$970 USD** de créditos GCP para melhorar win rate de 55% → 60%+

**Timeline:** 7 dias de teste + uso inteligente da GCP

---

## 📋 **AGORA - Passos Imediatos (Próximos 30 min)**

### **Passo 1: Verificar Dados Coletados de 2h**

```bash
cd ~/intelligent-trading-bot  # ou seu caminho

# Verificar dados
python scripts/verify_orderbook_data.py
```

**Esperado:**
```
✅ Encontrados 4 arquivo(s):
   1. BTCUSDT_orderbook_20241210_013918.parquet (0.46 MB)
   2. BTCUSDT_orderbook_20241210_020918.parquet (0.44 MB)
   3. BTCUSDT_orderbook_20241210_023919.parquet (0.53 MB)
   4. BTCUSDT_orderbook_20241210_030918.parquet (0.xx MB)

Total de snapshots: ~7,200
Taxa média: 1.0 snapshots/segundo ✅
```

---

### **Passo 2: Iniciar Coleta de 7 Dias (AGORA!)**

**SE verificação passou:**

```bash
# Iniciar em background (vai rodar por 7 dias)
nohup python scripts/collect_orderbook.py \
  --symbol BTCUSDT \
  --duration 7d \
  --save-interval 6h \
  > collector_7days.log 2>&1 &

# Ver o processo rodando
ps aux | grep collect_orderbook

# Monitorar log
tail -f collector_7days.log
```

**Output esperado:**
```
🚀 BINANCE ORDER BOOK COLLECTOR
Symbol: BTCUSDT
Duration: 168.0 hours (7 days)
Output: DATA_ORDERBOOK
Save interval: 360 minutes (6 hours)

✅ Connected! Collecting order book data...

📊 Collected: 100 snapshots | Rate: 1.0/s | ...
```

**Deixar rodando!** O processo vai:
- Coletar ~604,800 snapshots ao longo de 7 dias
- Salvar automaticamente a cada 6 horas
- Criar ~28 arquivos Parquet (~560 MB total)

---

## ⏰ **DIAS 1-6: Aguardar Coleta (Nada a Fazer)**

### **Monitoramento Opcional:**

```bash
# Ver se está rodando
ps aux | grep collect_orderbook

# Ver últimas linhas do log
tail -20 collector_7days.log

# Verificar arquivos sendo criados
ls -lh DATA_ORDERBOOK/ | tail -10

# Ver quantos snapshots já coletados
grep "💾 Saved" collector_7days.log | wc -l
```

**Checkpoints esperados:**
- Dia 1: ~4 arquivos (~80 MB)
- Dia 2: ~8 arquivos (~160 MB)
- Dia 3: ~12 arquivos (~240 MB)
- Dia 4: ~16 arquivos (~320 MB)
- Dia 5: ~20 arquivos (~400 MB)
- Dia 6: ~24 arquivos (~480 MB)
- Dia 7: ~28 arquivos (~560 MB) ✅

---

## 📅 **DIA 7 (Terça, 17 Dez): Backtest Order Flow**

### **Pipeline Completa:**

```bash
cd ~/intelligent-trading-bot

# 1. Features (com order flow!)
python scripts/features_new.py -c configs/btcusdt_5m_orderflow.jsonc

# 2. Labels
python scripts/labels_new.py -c configs/btcusdt_5m_orderflow.jsonc

# 3. Merge
python scripts/merge_new.py -c configs/btcusdt_5m_orderflow.jsonc

# 4. Train
python scripts/train.py -c configs/btcusdt_5m_orderflow.jsonc

# 5. Signals
python scripts/signals.py -c configs/btcusdt_5m_orderflow.jsonc

# 6. Simulate
python scripts/simulate.py -c configs/btcusdt_5m_orderflow.jsonc
```

### **Analisar Resultados:**

```bash
# Ver resultados
cat DATA_ITB_5m/simulation_results_orderflow.csv | grep "profitable" | head -5

# Comparar com baseline (sem order flow)
cat DATA_ITB_5m/simulation_results.csv | grep "profitable" | head -1
```

### **DECISÃO CRÍTICA:**

```
Win Rate ≥ 55%:  🟢 EXCELENTE - Partir para GCP AutoML
Win Rate 53-55%: 🟡 BOM - GCP AutoML cauteloso
Win Rate 50-53%: 🟠 FRACO - Considerar pivot para daily
Win Rate < 50%:  🔴 FALHA - Pivot para daily ou desistir
```

---

## 🚀 **DIA 7: SE WIN RATE ≥ 53% → Setup GCP**

### **Passo 1: Automated Setup (15 min)**

```bash
# Tornar script executável
chmod +x scripts/setup_gcp.sh

# Rodar setup automatizado
bash scripts/setup_gcp.sh
```

**O script vai:**
1. ✅ Instalar gcloud CLI (se necessário)
2. ✅ Autenticar sua conta (abre browser)
3. ✅ Criar projeto "itb-trading-XXXXX"
4. ✅ Linkar billing account (seus $970)
5. ✅ Ativar APIs (Vertex AI, BigQuery, Compute)
6. ✅ Instalar Python libraries (google-cloud-*)

**Escolher billing account:**
```
Quando pedir, use:
- 01AEAED-1655E14-D36EEB (₪3,519.85 disponível)
```

---

### **Passo 2: Rodar AutoML (Custo: $50-100)**

```bash
# Dry run primeiro (ver custo estimado, sem cobrar)
python scripts/gcp_automl_train.py \
  -c configs/btcusdt_5m_orderflow.jsonc \
  --budget 1 \
  --dry-run

# Se OK, rodar de verdade (budget 1h = ~$3-5)
python scripts/gcp_automl_train.py \
  -c configs/btcusdt_5m_orderflow.jsonc \
  --budget 1
```

**O AutoML vai:**
- Upload dados para BigQuery
- Testar 100+ combinações de features/modelos/hyperparameters
- Treinar por 1-6 horas (depende do budget)
- Retornar melhor modelo encontrado

**Custo estimado:**
- 1h budget = $3-5 (teste rápido)
- 3h budget = $10-15 (bons resultados)
- 6h budget = $20-30 (melhores resultados)

---

### **Passo 3: Comparar Resultados**

```bash
# Ver métricas do AutoML
# (vão aparecer no terminal quando terminar)

# Comparar:
# - Baseline LGBM local: 55% win rate
# - AutoML GCP: ?? % win rate

# SE AutoML > Baseline + 2%:
#   ✅ Sucesso! Usar modelo da GCP
#
# SE AutoML ≈ Baseline:
#   ⚠️ Tentar LSTM ou aumentar budget
```

---

## 💰 **Monitoramento de Custos (IMPORTANTE!)**

### **Antes de Gastar:**

```bash
# Ver custos atuais
python scripts/cloud_cost_monitor.py

# Ver dicas de economia
python scripts/cloud_cost_monitor.py --tips
```

### **Durante Experimentos:**

```bash
# Monitor contínuo (check a cada hora)
python scripts/cloud_cost_monitor.py --monitor --interval 3600

# Ou via web:
# https://console.cloud.google.com/billing
```

### **Deletar Recursos Quando Terminar:**

```bash
# Listar VMs ativas
gcloud compute instances list

# Deletar VM (IMPORTANTE - cobram mesmo parada!)
gcloud compute instances delete INSTANCE_NAME
```

---

## 📊 **Budget Allocation Recomendado**

**Total disponível:** ~$970 USD

### **Conservador ($300 total):**
```
Fase 1 - Local testing: $0
Fase 2 - AutoML (1h): $5
├─ SE melhora +2% → AutoML (3h): $15
├─ SE melhora +2% → LSTM GPU: $30
└─ Reserva: $250
Total usado: $50
Sobra: $920 ✅
```

### **Agressivo ($500 total):**
```
Fase 1 - Local: $0
Fase 2 - AutoML (6h): $30
Fase 3 - LSTM GPU: $50
Fase 4 - Transformer GPU: $100
Fase 5 - Ensemble: $30
Fase 6 - Hyperparameter tuning: $50
Fase 7 - Production deployment: $100
Total usado: $360
Sobra: $610 ✅
```

**Minha recomendação:** Começar conservador, aumentar se funcionar.

---

## 🎯 **Expected Outcomes**

### **Baseline (Local LGBM):**
```
Win Rate: 55%
Trades: ~2,000
Profit: +5-10% (esperado)
```

### **Com AutoML ($50 investidos):**
```
Win Rate: 57-58% (+2-3%)
Trades: ~2,000
Profit: +10-15%
ROI: Paga investimento em 1-2 semanas
```

### **Com AutoML + LSTM ($100 investidos):**
```
Win Rate: 58-60% (+3-5%)
Trades: ~2,000
Profit: +15-20%
ROI: Paga investimento em 1 semana
```

---

## ⚠️ **ABORT Criteria (Quando Desistir)**

**Parar imediatamente se:**
1. ❌ Order flow backtest <50% win rate (pior que random)
2. ❌ AutoML não melhora nada vs baseline
3. ❌ Custos >$200 sem resultados
4. ❌ Shadow mode <45% win rate

**Nestes casos:** Pivot para daily swing trading ou aceitar que scalping não funciona.

---

## 📁 **Arquivos Importantes**

```
intelligent-trading-bot/
├── scripts/
│   ├── verify_orderbook_data.py       # Verificar coleta de 2h
│   ├── collect_orderbook.py           # Coletor (rodando 7 dias)
│   ├── setup_gcp.sh                   # Setup automatizado GCP
│   ├── gcp_automl_train.py            # AutoML training
│   ├── lstm_gpu_train.py              # LSTM com GPU
│   └── cloud_cost_monitor.py          # Monitor custos
├── configs/
│   └── btcusdt_5m_orderflow.jsonc     # Config com order flow
├── docs/
│   ├── CLOUD_ML_GUIDE.md              # Guia completo cloud
│   └── ORDER_FLOW_IMPLEMENTATION.md   # Guia order flow
├── ORDER_FLOW_TEST_TRACKER.md         # Timeline 1 semana
├── QUICKSTART_GCP.md                  # Este arquivo
└── gcp_project_info.txt               # Info do projeto (criado após setup)
```

---

## 🆘 **Troubleshooting**

### **Coletor parou de funcionar:**
```bash
# Ver se processo está rodando
ps aux | grep collect_orderbook

# Se parou, reiniciar
nohup python scripts/collect_orderbook.py --symbol BTCUSDT --duration 7d --save-interval 6h > collector_7days.log 2>&1 &
```

### **GCP setup falhou:**
```bash
# Verificar instalação gcloud
gcloud version

# Re-autenticar
gcloud auth login

# Ver projeto ativo
gcloud config get-value project
```

### **AutoML dando erro:**
```bash
# Verificar billing ativo
gcloud billing projects describe PROJECT_ID

# Verificar APIs ativadas
gcloud services list --enabled | grep aiplatform
```

---

## ✅ **Checklist Completo**

### **Hoje (Dia 0):**
- [ ] Verificar dados de 2h coletados
- [ ] Iniciar coleta de 7 dias em background
- [ ] Confirmar processo está rodando

### **Dias 1-6:**
- [ ] Monitorar coleta ocasionalmente
- [ ] Verificar arquivos sendo criados

### **Dia 7:**
- [ ] Parar coletor (se ainda rodando)
- [ ] Rodar pipeline completa
- [ ] Analisar win rate
- [ ] **DECISÃO:** GCP ou não?

### **Dia 7 (SE ≥53%):**
- [ ] Setup GCP automatizado
- [ ] Rodar AutoML (budget conservador)
- [ ] Comparar resultados
- [ ] Decidir próximos passos

### **Dia 8-10 (SE AutoML funciona):**
- [ ] Shadow mode 3 dias
- [ ] SE shadow mode ≥52% → Live $100

---

## 💬 **Comandos Rápidos**

```bash
# Verificar dados de 2h
python scripts/verify_orderbook_data.py

# Iniciar 7 dias
nohup python scripts/collect_orderbook.py --symbol BTCUSDT --duration 7d --save-interval 6h > collector_7days.log 2>&1 &

# Monitorar
tail -f collector_7days.log

# Pipeline completa (Dia 7)
for script in features_new labels_new merge_new train signals simulate; do
    python scripts/${script}.py -c configs/btcusdt_5m_orderflow.jsonc
done

# Setup GCP
bash scripts/setup_gcp.sh

# AutoML
python scripts/gcp_automl_train.py -c configs/btcusdt_5m_orderflow.jsonc --budget 1

# Monitor custos
python scripts/cloud_cost_monitor.py
```

---

**Criado:** 10 Dezembro 2024
**Status:** Coleta de 2h completa, iniciando 7 dias
**Próximo milestone:** Dia 7 (17 Dezembro) - Backtest order flow
**Budget GCP:** ~$970 USD disponível
