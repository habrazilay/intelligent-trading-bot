# Shadow Mode Analysis - Production-Ready Validation

## 📋 Visão Geral

Este documento descreve o processo de **análise de shadow mode** do ITB, essencial para validar estratégias antes de capital real.

**Objetivo:** Transformar logs de staging em **decisões baseadas em dados** sobre aprovar ou não uma estratégia para live trading.

---

## 🎯 Por Que Shadow Mode Analysis?

**Sem análise estruturada:**
- ❌ Números soltos sem contexto
- ❌ Não sabemos se a estratégia funciona DE VERDADE
- ❌ Não sabemos quando está pronta para capital real
- ❌ "Voando no escuro"

**Com análise robusta:**
- ✅ Métricas de risco ajustadas (Sharpe, Sortino, Calmar)
- ✅ Drawdown realista com compounding
- ✅ Custos realistas (fees + slippage dinâmico)
- ✅ Simulação de falhas de execução
- ✅ Critérios claros pass/fail
- ✅ **Decisões baseadas em evidências**

---

## 🛠️ Ferramenta: `analyze_staging_logs_v4.py`

### Localização
```
my_tests/analyze_staging_logs_v4.py
```

### Features V4 (Production-Ready)

| Feature | Descrição |
|---------|-----------|
| **Dynamic Slippage** | 5-50 bps baseado em volatilidade recente (não fixo) |
| **Compounding Equity** | Position sizing = % do capital atual (realista) |
| **Hold-time Constraints** | Min 60s holding + detecção same-candle |
| **Log Validation** | Timestamps, signal imbalance, extreme price jumps |
| **Execution Failures** | 2% falhas + 5% partial fills (realista) |
| **Risk Limits** | Daily loss limit + max drawdown stop |
| **Capital Management** | 1% risk per trade, min/max position size |

---

## 🚀 Como Usar

### Análise Básica

```bash
# Server.log na raiz do projeto
python my_tests/analyze_staging_logs_v4.py

# Log customizado
python my_tests/analyze_staging_logs_v4.py --log-file logs/staging/server_1m.log
```

### Análise com Capital Maior

```bash
# Starting capital $5000, risk 1.5% per trade
python my_tests/analyze_staging_logs_v4.py \
  --starting-capital 5000 \
  --risk-per-trade 1.5
```

### Usando Makefile (recomendado)

```bash
# Análise padrão
make analyze-staging

# Capital alto
make analyze-staging-high-capital
```

---

## 📊 Outputs Gerados

### 1. Trade Details CSV
```
logs/analytics/trades_v4_2025-12-09_16-45-00.csv
```

**Colunas:**
- `entry_ts`, `exit_ts`, `hold_minutes`
- `entry_price`, `exit_price`, `position_usdt`
- `gross_pnl`, `fees`, `slippage`, `net_pnl`
- `entry_equity`, `exit_equity`, `return_pct`
- `same_candle_warning` (YES/NO)

### 2. Comprehensive Report
```
logs/analytics/report_v4_2025-12-09_16-45-00.md
```

**Seções:**
- ⚙️ Trading Configuration
- 📡 Log Validation (pass/fail)
- 💰 Performance Summary (compounding)
- 📉 Drawdown Analysis
- 📊 Risk Metrics (Sharpe, Sortino, Calmar, etc.)
- ⚠️ Simulation Warnings
- 🐛 Parse Errors (se houver)

---

## 🎯 Critérios de Aprovação: Shadow → Live

### Critérios Mínimos (Configuráveis)

| Critério | Threshold | Justificativa |
|----------|-----------|---------------|
| **Min Trades** | 100 | Amostra estatisticamente significativa |
| **Min Win Rate** | 52% | Supera fees + slippage |
| **Max Drawdown** | -15% | Risco psicológico aceitável |
| **Min Sharpe Ratio** | 0.5 | Return/volatility razoável |
| **Min Profit Factor** | 1.3 | Wins 30% maiores que losses |
| **Positive Net PnL** | > $0 | Lucratividade básica |
| **Max Consecutive Losses** | ≤ 10 | Evita ruína psicológica |

### Como Interpretar o Report

#### ✅ **PASSED** - Aprovado para Live
```markdown
## ✅ Pass/Fail Assessment

### 🎉 **PASSED** - Strategy approved for live trading

All criteria met:
✅ Min Trades: 150 ≥ 100
✅ Win Rate: 54.2% ≥ 52%
✅ Max DD: -12.5% > -15%
✅ Sharpe: 0.72 ≥ 0.5
✅ Profit Factor: 1.45 ≥ 1.3
✅ Net PnL: $+23.45 > $0
```

**Ação:** 🟢 Avançar para testnet Binance (30 dias)

---

#### ❌ **FAILED** - Não Aprovado
```markdown
## ❌ Pass/Fail Assessment

### ❌ **FAILED** - Strategy NOT approved for live trading

**Failures:**
- ❌ Win rate baixa: 48.5% < 52.0%
- ❌ Drawdown excessivo: -18.2% < -15.0%
- ❌ Sharpe ratio baixo: 0.32 < 0.5
```

**Ação:** 🔴 Ajustar estratégia:
- Tune hyperparameters (LGBM, features)
- Ajustar thresholds de signal score
- Adicionar filtros (volatility, volume, etc.)
- Re-rodar shadow mode por mais 7-14 dias

---

## 📈 Workflow Completo: Shadow → Live

### Fase 0: Shadow Mode (Atual)
```
1. Deploy staging em Azure/local
2. Coletar logs por 7-14 dias (min 100 trades)
3. Rodar analyze_staging_logs_v4.py
4. Avaliar report: PASS ou FAIL?
```

**SE PASSOU:**

### Fase 1: Testnet Binance (30 dias)
```
5. Deploy em Binance Testnet
6. Capital simulado: $1000-5000
7. Rodar V4 diariamente
8. Avaliar após 30 dias
```

**SE PASSOU:**

### Fase 2: Live (Capital Real Limitado)
```
9. Deploy em Binance Live
10. Capital real: $50-100 (limitado!)
11. Rodar V4 diariamente
12. Monitorar 30 dias
13. Se continuar passando → escalar gradualmente
```

---

## 🔧 Configuração Avançada

### TradingConfig (V4)

```python
@dataclass
class TradingConfig:
    # Capital management
    starting_capital_usdt: float = 1000.0
    risk_per_trade_pct: float = 1.0      # % do capital por trade
    min_position_usdt: float = 5.0
    max_position_usdt: float = 100.0

    # Fees & costs
    taker_fee_rate: float = 0.001        # 0.1% Binance taker

    # Slippage (dynamic)
    base_slippage_bps: float = 5.0       # Base: 5 bps
    slippage_volatility_multiplier: float = 2.0

    # Execution constraints
    min_hold_time_seconds: int = 60      # Mínimo 1 min holding
    execution_failure_rate: float = 0.02 # 2% falhas
    partial_fill_rate: float = 0.05      # 5% fills parciais

    # Risk limits
    max_drawdown_stop_pct: float = -20.0 # Stop se DD > 20%
    daily_loss_limit_pct: float = -5.0   # Stop no dia se -5%
```

### Como Customizar

**Via CLI:**
```bash
python my_tests/analyze_staging_logs_v4.py \
  --starting-capital 5000 \
  --risk-per-trade 2.0
```

**Editando o código:**
```python
# Em analyze_staging_logs_v4.py, linha ~600
config = TradingConfig(
    starting_capital_usdt=args.starting_capital,
    risk_per_trade_pct=args.risk_per_trade,
    base_slippage_bps=10.0,  # Slippage mais conservador
    execution_failure_rate=0.05,  # 5% falhas (mais conservador)
)
```

---

## 🐛 Troubleshooting

### Problema: "No signals found in log file"

**Causa:** Log não contém linhas no formato esperado.

**Solução:**
```bash
# Verificar formato do log
grep "Analyze finished" server.log | head -5

# Formato esperado:
# 2025-12-04 06:02:01,322 INFO Analyze finished. Close: 93,521 Signals: trade score=+0.003, buy_signal=True, sell_signal=False
```

### Problema: "Log validation FAILED"

**Causas possíveis:**
- Timestamps fora de ordem
- Signal imbalance (muitos buys, poucos sells)
- Extreme price jumps (>10%)

**Ação:**
1. Revisar warnings no report
2. Verificar se staging rodou corretamente
3. Considerar recoletar logs

### Problema: "No trades executed"

**Causas possíveis:**
- Buy signals mas nenhum sell (posição nunca fecha)
- Hold time muito curto (< 60s)
- Execution failures excessivos

**Ação:**
1. Verificar signal imbalance no validation report
2. Ajustar `min_hold_time_seconds` se necessário
3. Revisar lógica de sinais

---

## 📚 Comparação: V3 vs V4

| Feature | V3 (Básico) | V4 (Production) |
|---------|-------------|-----------------|
| **Slippage** | Fixo (5 bps) | Dinâmico (5-50 bps) |
| **Position sizing** | Fixo ($5) | % capital (1%) |
| **Equity curve** | Linear | Compounding |
| **Hold time** | Nenhum check | Min 60s + same-candle |
| **Execution** | 100% sucesso | Failures + Partials |
| **Validation** | Básica | Completa |
| **Risk limits** | Não | Daily/DD stops |
| **Drawdown** | Linear | Compounding |

**Recomendação:** Sempre use **V4** para decisões de live trading.

---

## 🔗 Referências

- **Roadmap:** `/docs/ROADMAP.md` (Fase 0 → Fase 5)
- **Server docs:** `/docs/server.md`
- **Trader docs:** `/docs/trader.md`
- **CHANGELOG:** `/CHANGELOG.md`

---

## 📝 Notas Importantes

### O Que V4 NÃO Testa

1. **Código de execução real** - Não testa reconexões, delays, rate limits
2. **Liquidez real** - Slippage é estimado, não medido
3. **Eventos de mercado** - Flash crashes, halts, exchange downtime
4. **Custos indiretos** - Funding rates (futuros), withdrawal fees

### Limitações do Shadow Mode

- **Survivorship bias** - Assume que todas as ordens foram executadas
- **Logs podem mentir** - Se staging tem bugs, análise reflete bugs
- **Data quality** - Garbage in, garbage out

### Mitigações

1. ✅ Validação de logs robusta (V4)
2. ✅ Simulação de falhas de execução
3. ✅ Testnet antes de live
4. ✅ Capital limitado em live inicial
5. ✅ Monitoramento diário

---

## 🎯 Próximos Passos

1. **Coletar logs de shadow mode** (7-14 dias, min 100 trades)
2. **Rodar V4:** `python my_tests/analyze_staging_logs_v4.py`
3. **Avaliar report:** Pass ou fail?
4. **Se passou:** Testnet (30 dias)
5. **Se falhou:** Ajustar estratégia, re-rodar shadow

---

**Última atualização:** 2025-12-09
**Versão:** V4 Production-Ready
**Autores:** Claude Code + ChatGPT (colaborativo)
