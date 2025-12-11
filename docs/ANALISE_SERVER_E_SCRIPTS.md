# Análise Completa: Server e Scripts

**Data**: 2025-12-11

---

## 📊 Análise do `service/server.py`

### O que ele faz

O servidor é um **loop de trading em tempo real** que:

1. **Conecta à Binance** via API (REST + WebSocket)
2. **Coleta dados** (klines) a cada intervalo configurado
3. **Gera features** (indicadores técnicos)
4. **Faz predições** com modelos ML treinados
5. **Executa trades** baseado nos sinais

### Fluxo de Execução

```
┌─────────────────────────────────────────────────────────────┐
│                    START SERVER                              │
├─────────────────────────────────────────────────────────────┤
│ 1. load_config()          → Carrega configs/xxx.jsonc       │
│ 2. Client(**args)         → Conecta Binance API             │
│ 3. ModelStore.load_models → Carrega modelos ML (.pkl)       │
│ 4. Analyzer()             → Inicializa DataFrame em memória │
│ 5. health_check()         → Verifica servidor Binance       │
│ 6. main_collector_task()  → Cold start: carrega histórico   │
│ 7. analyzer.analyze()     → Gera features iniciais          │
│ 8. AsyncIOScheduler       → Agenda main_task() por freq     │
│ 9. loop.run_forever()     → Roda até Ctrl+C                 │
└─────────────────────────────────────────────────────────────┘
         │
         │ A cada intervalo (1m, 5m, 1h...)
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    main_task()                               │
├─────────────────────────────────────────────────────────────┤
│ 1. main_collector_task()  → Coleta novos klines             │
│    └── append_klines()    → Adiciona ao DataFrame           │
│                                                              │
│ 2. analyzer.analyze()     → Em thread separada              │
│    ├── generate_features  → SMA, RSI, ATR, etc.            │
│    ├── predict_model      → ML predictions                  │
│    └── generate_signals   → BUY/SELL signals               │
│                                                              │
│ 3. output_feature_set()   → Executa outputs configurados    │
│    ├── trader_binance     → Trading real                    │
│    ├── trader_simulation  → Trading simulado                │
│    ├── score_notification → Telegram notifications          │
│    └── diagram_generator  → Gráficos                        │
└─────────────────────────────────────────────────────────────┘
```

---

## ✅ É Efetivo para Live Trading na Binance?

### **SIM, com ressalvas**

#### ✅ Pontos Positivos

| Aspecto | Status | Descrição |
|---------|--------|-----------|
| **Arquitetura** | ✅ Boa | Async event loop com scheduler |
| **Binance API** | ✅ Completa | REST + WebSocket, orders, balances |
| **Order Types** | ✅ Limit | Limit orders com GTC |
| **State Machine** | ✅ Funciona | SOLD → BUYING → BOUGHT → SELLING |
| **Simulação** | ✅ Tem | `trader_simulation` para shadow mode |
| **Logging** | ✅ Adequado | Logs de sinais, orders, erros |
| **Recovery** | ✅ Básico | `update_trade_status()` resync |

#### ⚠️ Pontos a Melhorar

| Aspecto | Status | Descrição |
|---------|--------|-----------|
| **Risk Management** | ⚠️ Básico | Sem stop-loss automático |
| **Order Timeout** | ⚠️ 1 min fixo | Cancela após 1 minuto sempre |
| **Position Sizing** | ⚠️ Simples | Só percentual ou valor fixo |
| **Multi-symbol** | ❌ Não | Só 1 símbolo por instância |
| **Backoff/Retry** | ⚠️ Básico | Sem exponential backoff |
| **Circuit Breaker** | ❌ Não | Sem proteção contra cascata |
| **Order Book** | ❌ Não usa | Não considera liquidez |
| **Slippage Control** | ⚠️ Básico | Só `limit_price_adjustment` |

---

## 🔧 Modos de Operação

### 1. **Shadow Mode (Simulação)** ✅ Recomendado para testes

```jsonc
// No config:
"output_sets": [
    {
        "generator": "trader_simulation",
        "config": {
            "buy_signal_column": "buy_signal",
            "sell_signal_column": "sell_signal"
        }
    }
]
```

**O que faz**:
- Não executa trades reais
- Grava transações simuladas em `transactions.txt`
- Envia notificações Telegram
- Calcula profit/loss hipotético

### 2. **Live Mode (Trading Real)** ⚠️ Cuidado!

```jsonc
"output_sets": [
    {
        "generator": "trader_binance",
        "config": {
            "buy_signal_column": "buy_signal",
            "sell_signal_column": "sell_signal"
        }
    }
],
"trade_model": {
    "trader_binance": true,
    "percentage_used_for_trade": 20.0,
    "min_notional_usdt": 10.0,
    "limit_price_adjustment": 0.001,
    "test_order_before_submit": true,
    "simulate_order_execution": false
}
```

**Flags de segurança**:
- `test_order_before_submit: true` → Testa order antes de enviar
- `simulate_order_execution: true` → Simula execução (não envia de verdade)
- `no_trades_only_data_processing: true` → Só processa dados, não trade

---

## 📁 Análise dos Scripts

### Scripts Principais (Pipeline)

| Script | Função | Status | Notas |
|--------|--------|--------|-------|
| `download_binance.py` | Download dados | ✅ Bom | Suporta incremental |
| `merge.py` | Merge fontes | ✅ Bom | Regular time index |
| `features.py` | Gera features | ✅ Bom | TA-Lib based |
| `labels.py` | Gera labels | ✅ Bom | highlow2 funciona |
| `train.py` | Treina modelos | ✅ Bom | LightGBM + LC |
| `predict.py` | Predições batch | ✅ Bom | Para backtest |
| `signals.py` | Gera sinais | ✅ Bom | Threshold rules |
| `output.py` | Output batch | ✅ Bom | Para análise |
| `simulate.py` | Backtest | ✅ Bom | Calcula trades |

### Scripts Novos

| Script | Função | Status | Notas |
|--------|--------|--------|-------|
| `merge_new.py` | Merge melhorado | ✅ Bom | `--dry-run` |
| `features_new.py` | Features melhorado | ✅ Bom | `--dry-run` |
| `labels_new.py` | Labels melhorado | ✅ Bom | `--dry-run` |
| `collect_orderbook.py` | Coleta orderbook | ✅ Bom | WebSocket |
| `verify_orderbook_data.py` | Verifica orderbook | ✅ Bom | Validação |

### Scripts Auxiliares

| Script | Função | Status | Notas |
|--------|--------|--------|-------|
| `predict_rolling.py` | Walk-forward | ✅ Bom | Re-train periódico |
| `config_helper.py` | Template config | ✅ Bom | Symbol/freq vars |
| `cloud_cost_monitor.py` | Azure costs | ✅ Bom | Monitoramento |
| `gcp_automl_train.py` | GCP training | ⚠️ Experimental | Vertex AI |
| `lstm_gpu_train.py` | LSTM training | ⚠️ Experimental | TensorFlow |
| `upload_to_bigquery.py` | BQ upload | ⚠️ Experimental | GCP |

---

## 🚨 Melhorias Recomendadas

### Alta Prioridade

#### 1. **Stop-Loss Automático**

Atualmente não há stop-loss. Se o preço cair muito, você perde tudo.

```python
# Em trader_binance.py, adicionar:
async def check_stop_loss():
    """Cancel position if loss exceeds threshold"""
    if App.status == "BOUGHT":
        entry_price = App.transaction.get("price", 0)
        current_price = App.analyzer.get_last_kline()["close"]
        loss_pct = (entry_price - current_price) / entry_price * 100

        if loss_pct >= config.get("stop_loss_percent", 5):
            log.warning("STOP LOSS triggered at %.2f%% loss", loss_pct)
            await new_limit_order(side=SIDE_SELL)
```

#### 2. **Take-Profit Automático**

```python
async def check_take_profit():
    """Close position if profit exceeds threshold"""
    if App.status == "BOUGHT":
        entry_price = App.transaction.get("price", 0)
        current_price = App.analyzer.get_last_kline()["close"]
        profit_pct = (current_price - entry_price) / entry_price * 100

        if profit_pct >= config.get("take_profit_percent", 3):
            log.info("TAKE PROFIT triggered at %.2f%% profit", profit_pct)
            await new_limit_order(side=SIDE_SELL)
```

#### 3. **Melhor Logging para Análise**

Adicionar logs estruturados para análise posterior:

```python
# JSON structured logging
import json

def log_trade_event(event_type, data):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        **data
    }
    log.info("TRADE_EVENT: %s", json.dumps(log_entry))
```

#### 4. **Circuit Breaker**

Parar de tradear após N perdas consecutivas:

```python
class CircuitBreaker:
    def __init__(self, max_consecutive_losses=3, cooldown_minutes=60):
        self.consecutive_losses = 0
        self.max_losses = max_consecutive_losses
        self.cooldown_until = None

    def record_trade(self, profit):
        if profit < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.max_losses:
                self.cooldown_until = datetime.now() + timedelta(minutes=60)
                log.warning("CIRCUIT BREAKER: %d consecutive losses. Pausing.",
                           self.consecutive_losses)
        else:
            self.consecutive_losses = 0

    def is_trading_allowed(self):
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return False
        return True
```

### Média Prioridade

#### 5. **Multi-Symbol Support**

Permitir múltiplos símbolos numa única instância.

#### 6. **Dynamic Position Sizing**

Ajustar tamanho da posição baseado em volatilidade.

#### 7. **Order Book Integration**

Usar dados de orderbook para melhor timing.

### Baixa Prioridade

#### 8. **WebSocket para Trades**

Usar WebSocket para updates de ordem em real-time.

#### 9. **Database Backend**

Migrar de arquivos para SQLite/PostgreSQL.

#### 10. **Dashboard Web**

Interface web para monitoramento.

---

## 📋 Checklist para Live Trading

Antes de ativar live trading, verifique:

### Setup
- [ ] `.env` configurado com API keys
- [ ] Modelos treinados em `MODELS/`
- [ ] Config validado com `--dry-run`
- [ ] Shadow mode rodou por 1+ semana
- [ ] Métricas de shadow mode são positivas

### Segurança
- [ ] `test_order_before_submit: true`
- [ ] `percentage_used_for_trade` < 30%
- [ ] `min_notional_usdt` configurado
- [ ] Telegram notificações ativadas
- [ ] Monitoring/alerting configurado

### Operacional
- [ ] Servidor em máquina confiável (não laptop)
- [ ] Logs salvos e rotacionados
- [ ] Backup de configs
- [ ] Plano de rollback

---

## 🔍 Resumo Executivo

### O `service/server.py` é bom para:

✅ Shadow mode / paper trading
✅ Testes de estratégia em tempo real
✅ Pequenos valores de trading
✅ Aprendizado e experimentação

### NÃO é recomendado para:

❌ Grandes somas de dinheiro (sem stop-loss)
❌ Trading de alta frequência
❌ Múltiplos pares simultaneamente
❌ Produção sem supervisão

### Veredicto Final

**O servidor é funcional e efetivo para testes de live trading**, mas precisa de melhorias em gerenciamento de risco antes de ser usado com valores significativos. Recomendo:

1. **Rodar em shadow mode por 2-4 semanas**
2. **Analisar métricas** com `analyze_staging_logs_v4.py`
3. **Se positivo**, começar com valores pequenos (< $100)
4. **Implementar stop-loss** antes de aumentar valores

---

## 📚 Referências

- [service/server.py](../service/server.py) - Servidor principal
- [service/analyzer.py](../service/analyzer.py) - Engine de análise
- [outputs/trader_binance.py](../outputs/trader_binance.py) - Trading real
- [outputs/notifier_trades.py](../outputs/notifier_trades.py) - Simulação
- [configs/btcusdt_1m_staging_v2.jsonc](../configs/btcusdt_1m_staging_v2.jsonc) - Config exemplo
