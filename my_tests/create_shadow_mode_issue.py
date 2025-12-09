#!/usr/bin/env python3
"""
Create GitHub Issue for Phase 0 Shadow Mode Analysis

Usage:
    python my_tests/create_shadow_mode_issue.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def check_gh_cli():
    """Check if gh CLI is installed."""
    try:
        result = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        print(f"✅ GitHub CLI installed: {result.stdout.strip().split()[2]}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ GitHub CLI (gh) not installed or not in PATH")
        print("   Install: https://cli.github.com/")
        return False


def check_gh_auth():
    """Check if gh CLI is authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            check=True,
        )
        print("✅ GitHub CLI authenticated")
        return True
    except subprocess.CalledProcessError:
        print("❌ GitHub CLI not authenticated")
        print("   Run: gh auth login")
        return False


def create_issue():
    """Create GitHub issue for Phase 0 Shadow Mode."""

    title = "[Phase 0] Shadow Mode Analysis & Validation Framework"

    body = """## 🎯 Objetivo

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

**Status:** 🟡 **80% COMPLETO** - Aguardando coleta de logs reais
**Priority:** 🔴 **HIGH** - Bloqueia Fase 1
**Environment:** `dev`, `staging`
"""

    labels = [
        "phase-0",
        "priority-high",
        "shadow-mode",
        "devops",
        "phase-0-foundation",
    ]

    # Create issue using gh CLI
    cmd = [
        "gh", "issue", "create",
        "--title", title,
        "--body", body,
        "--label", ",".join(labels),
    ]

    print("\n" + "=" * 80)
    print("Creating GitHub Issue...")
    print("=" * 80)
    print(f"\nTitle: {title}")
    print(f"Labels: {', '.join(labels)}")
    print("\nExecuting: gh issue create...\n")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )

        print("✅ Issue created successfully!")
        print(result.stdout)

        # Extract issue URL from output
        for line in result.stdout.split("\n"):
            if "https://github.com" in line:
                issue_url = line.strip()
                print(f"\n🔗 Issue URL: {issue_url}")

        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create issue: {e}")
        print(f"stderr: {e.stderr}")
        return False


def main():
    print("=" * 80)
    print("Phase 0 Shadow Mode - GitHub Issue Creator")
    print("=" * 80)

    # Check prerequisites
    if not check_gh_cli():
        sys.exit(1)

    if not check_gh_auth():
        sys.exit(1)

    # Create issue
    success = create_issue()

    if success:
        print("\n" + "=" * 80)
        print("✅ SUCCESS - Issue created!")
        print("=" * 80)
        print("\nNext steps:")
        print("1. View issue on GitHub")
        print("2. Add to GitHub Project if needed")
        print("3. Assign to yourself: gh issue edit <number> --add-assignee @me")
        print("4. Collect staging logs (7-14 days)")
        print("5. Run: make analyze-staging")
        print("=" * 80)
        sys.exit(0)
    else:
        print("\n❌ FAILED - Could not create issue")
        sys.exit(1)


if __name__ == "__main__":
    main()
