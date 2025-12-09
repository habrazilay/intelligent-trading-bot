---
name: "Phase 0: Shadow Mode Analysis & Validation"
about: Consolidação de staging e análise de shadow mode antes de live trading
title: "[Phase 0] Shadow Mode Analysis & Validation Framework"
labels: phase-0, priority-high, shadow-mode, devops, phase-0-foundation
assignees: ''
---

## 🎯 Objetivo

Implementar **análise robusta de shadow mode** para validar estratégias antes de capital real, com critérios claros de aprovação para avançar de staging → testnet → live.

---

## 📋 Contexto

**Problema:** Sem análise estruturada de logs de staging, não sabemos se uma estratégia está pronta para capital real. "Números soltos" não geram confiança para decisões.

**Solução:** Framework de análise production-ready (V4) que transforma logs em métricas acionáveis com critérios pass/fail objetivos.

---

## ✅ Acceptance Criteria

### 1. Ferramenta de Análise (V4) - ✅ COMPLETO

- [x] Script `analyze_staging_logs_v4.py` implementado
- [x] Dynamic slippage baseado em volatilidade (5-50 bps)
- [x] Compounding equity curve com position sizing dinâmico
- [x] Hold-time constraints (min 60s) + same-candle detection
- [x] Execution failure simulation (2% failures + 5% partial fills)
- [x] Log validation (timestamps, signal imbalance, price jumps)
- [x] Risk metrics (Sharpe, Sortino, Calmar, Profit Factor)
- [x] Drawdown analysis com recovery time
- [x] CSV export detalhado de trades
- [x] Comprehensive Markdown report

### 2. Documentação - ✅ COMPLETO

- [x] `docs/SHADOW_MODE_ANALYSIS.md` criado
- [x] README.md atualizado com seção Shadow Mode
- [x] Como usar, interpretar reports, troubleshooting
- [x] Workflow completo: Shadow → Testnet → Live

### 3. Makefile Integration - ✅ COMPLETO

- [x] `make analyze-staging` - Análise básica
- [x] `make analyze-staging-high-capital` - Com $10K
- [x] `make analyze-staging-custom` - Customizável

### 4. Critérios de Aprovação - ✅ DEFINIDOS

| Critério | Threshold | Status |
|----------|-----------|--------|
| Min Trades | 100 | ✅ |
| Min Win Rate | 52% | ✅ |
| Max Drawdown | -15% | ✅ |
| Min Sharpe Ratio | 0.5 | ✅ |
| Min Profit Factor | 1.3 | ✅ |
| Positive Net PnL | > $0 | ✅ |

### 5. Próximos Passos - 🔄 TODO

- [ ] Coletar logs reais de staging (7-14 dias, min 100 trades)
- [ ] Rodar V4 e gerar primeiro report real
- [ ] Avaliar: PASS ou FAIL?
- [ ] Se FAIL: ajustar estratégia (tune hyperparameters, features, thresholds)
- [ ] Se PASS: avançar para Fase 1 (Testnet Binance)

---

## 🛠️ Technical Details

### Improvements from V3 → V4

| Feature | V3 | V4 |
|---------|----|----|
| **Slippage** | Fixo (5 bps) | Dinâmico (5-50 bps) baseado em volatilidade |
| **Position sizing** | Fixo ($5) | % do capital (1% default) |
| **Equity curve** | Soma linear | Compounding realista |
| **Hold time** | Nenhum check | Min 60s + same-candle flag |
| **Execution** | 100% sucesso | Failures (2%) + Partial fills (5%) |
| **Validation** | Básica | Completa (timestamps, imbalance, jumps) |
| **Stop loss** | Não | Daily loss + Max DD stops |

### Files Changed

```
✅ my_tests/analyze_staging_logs_v4.py       (NEW - 850 lines)
✅ docs/SHADOW_MODE_ANALYSIS.md              (NEW - comprehensive guide)
✅ README.md                                  (UPDATED - added Shadow Mode section)
✅ Makefile                                   (UPDATED - 3 new targets)
```

---

## 📊 Example Usage

```bash
# Basic analysis
make analyze-staging

# High capital simulation
make analyze-staging-high-capital

# Custom log file
make analyze-staging-custom LOG_FILE=logs/staging_server.log CAPITAL=5000 RISK=1.5
```

### Output Files

```
logs/analytics/
├── trades_v4_2025-12-09_16-45-00.csv    # Detailed trades CSV
└── report_v4_2025-12-09_16-45-00.md     # Comprehensive report
```

---

## 🔗 Related

- **Epic:** Phase 0 - Foundation & Infrastructure
- **Next Phase:** Phase 1 - Basic Strategy V1 (after shadow mode passes)
- **Dependencies:** None (standalone)
- **Blocks:** Phase 1 live trading approval

---

## 🤝 Collaboration

**Trabalho colaborativo Claude Code + ChatGPT:**
- ✅ Claude: Implementação V4, documentação, integration
- ✅ ChatGPT: Roadmap design, critérios de aprovação, review técnico

---

## 📝 Notes

### Why This Matters

Sem shadow mode analysis, estamos "voando no escuro":
- ❌ Não sabemos se a estratégia funciona
- ❌ Não sabemos quando está pronta para capital real
- ❌ Risco de perder $ real com estratégias não validadas

Com V4:
- ✅ Decisões baseadas em dados objetivos
- ✅ Critérios claros de aprovação
- ✅ Simulação realista (fees, slippage, falhas)
- ✅ Confiança para avançar para live

### Realismo do V4

V4 simula condições **realistas** de produção:
- Dynamic slippage (não fixo)
- Execution failures (timeouts, rejects)
- Partial fills (ordens parcialmente preenchidas)
- Position sizing dinâmico (compounding)
- Hold-time constraints (não fecha no mesmo candle)

---

## ✅ Definition of Done

- [x] V4 script implementado e testado
- [x] Documentação completa publicada
- [x] Makefile targets funcionando
- [x] README.md atualizado
- [ ] Primeiro report real gerado (pending logs)
- [ ] Decisão tomada: ajustar estratégia ou avançar para Fase 1

---

**Status:** 🟡 **80% COMPLETO** - Aguardando coleta de logs reais
**Priority:** 🔴 **HIGH** - Bloqueia Fase 1
**Environment:** `dev`, `staging`
