#!/usr/bin/env python3
"""
Staging Log Analyzer V3 - Comprehensive Trading Performance Analysis

Features:
- Robust log parsing with error handling
- Drawdown calculation (max, average, recovery time)
- Trade-level CSV export
- Risk-adjusted metrics (Sharpe ratio, Sortino ratio, Calmar ratio)
- Comprehensive Markdown report generation
- Equity curve and drawdown visualization
- Pass/fail criteria for shadow → live transition
- Realistic trading costs (fees, slippage simulation)

Usage:
    python analyze_staging_logs_v3.py --logs-dir logs/raw --notional 5.0
    python analyze_staging_logs_v3.py --logs-dir logs --symbol BTCUSDT --notional 10.0 --fees 0.001
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# ============================================================================
# LOG PARSING
# ============================================================================

# Aceita tanto "Signals" quanto "Sinals", e variação de espaços
SIGNAL_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}).*?"
    r"Analyze finished\.\s+Close:\s+([0-9.,]+)\s+S\w+:\s*trade[_ ]score=([+\-]?[0-9.,]+),\s*"
    r"buy_signal=(True|False),\s*sell_signal=(True|False)"
)


def parse_price(s: str) -> float:
    """Converte string de preço tipo '93,790' ou '93.790' para float."""
    s = s.strip()
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    return float(s)


def parse_score(s: str) -> float:
    """trade_score pode vir como +0.006, -0.003, 0.01 etc."""
    s = s.strip().replace(",", ".")
    return float(s)


@dataclass
class Trade:
    """Representa um trade completo (entry → exit)."""

    entry_price: float
    exit_price: float
    entry_ts: str
    exit_ts: str
    ret_pct: float
    pnl_usdt: float
    trade_score: float  # Score no momento da entrada
    fees_usdt: float = 0.0  # Fees totais (entry + exit)
    slippage_usdt: float = 0.0  # Slippage total estimado
    net_pnl_usdt: float = 0.0  # PnL líquido após fees + slippage

    def __post_init__(self):
        """Calcula PnL líquido automaticamente."""
        self.net_pnl_usdt = self.pnl_usdt - self.fees_usdt - self.slippage_usdt


def parse_log_files(
    files: List[Path],
    notional_usdt: float,
    fee_rate: float = 0.001,
    slippage_bps: float = 5.0,
) -> Tuple[List[Trade], int, int, List[str]]:
    """
    Parseia arquivos de log e extrai trades completos.

    Args:
        files: Lista de arquivos de log
        notional_usdt: Valor notional por trade
        fee_rate: Taxa de fees (0.001 = 0.1% = Binance taker)
        slippage_bps: Slippage estimado em basis points (5 bps = 0.05%)

    Returns:
        (trades, n_signals_buy, n_signals_sell, errors)
    """
    files = sorted(files)
    position_open = False
    entry_price = 0.0
    entry_ts: Optional[str] = None
    entry_score = 0.0

    trades: List[Trade] = []
    n_signals_buy = 0
    n_signals_sell = 0
    errors: List[str] = []

    for f in files:
        try:
            text = f.read_text(errors="ignore")
        except Exception as e:
            errors.append(f"Failed to read {f.name}: {e}")
            continue

        for line_num, line in enumerate(text.splitlines(), 1):
            try:
                m = SIGNAL_RE.search(line)
                if not m:
                    continue

                ts_str, close_str, score_str, buy_str, sell_str = m.group(
                    "ts"
                ), *m.groups()[1:]
                close_price = parse_price(close_str)
                trade_score = parse_score(score_str)
                buy_signal = buy_str == "True"
                sell_signal = sell_str == "True"

                if buy_signal:
                    n_signals_buy += 1
                if sell_signal:
                    n_signals_sell += 1

                # Lógica de trading: BUY abre, SELL fecha
                if buy_signal and not position_open:
                    position_open = True
                    entry_price = close_price
                    entry_ts = ts_str
                    entry_score = trade_score

                elif sell_signal and position_open:
                    exit_price = close_price
                    exit_ts = ts_str
                    ret_pct = (exit_price - entry_price) / entry_price
                    pnl_usdt = notional_usdt * ret_pct

                    # Calcula custos realistas
                    fees_entry = notional_usdt * fee_rate
                    fees_exit = notional_usdt * fee_rate
                    fees_total = fees_entry + fees_exit

                    slippage_total = notional_usdt * (slippage_bps / 10000.0)

                    trade = Trade(
                        entry_price=entry_price,
                        exit_price=exit_price,
                        entry_ts=entry_ts or "unknown",
                        exit_ts=exit_ts,
                        ret_pct=ret_pct,
                        pnl_usdt=pnl_usdt,
                        trade_score=entry_score,
                        fees_usdt=fees_total,
                        slippage_usdt=slippage_total,
                    )
                    trades.append(trade)

                    position_open = False
                    entry_price = 0.0
                    entry_ts = None
                    entry_score = 0.0

            except Exception as e:
                errors.append(f"{f.name}:{line_num} - Parse error: {e}")
                continue

    return trades, n_signals_buy, n_signals_sell, errors


# ============================================================================
# METRICS CALCULATION
# ============================================================================


@dataclass
class DrawdownMetrics:
    """Métricas de drawdown."""

    max_drawdown_pct: float
    max_drawdown_usdt: float
    avg_drawdown_pct: float
    current_drawdown_pct: float
    max_dd_start: Optional[str]
    max_dd_end: Optional[str]
    recovery_time_hours: Optional[float]
    num_drawdown_periods: int


def calculate_drawdown(trades: List[Trade]) -> DrawdownMetrics:
    """
    Calcula métricas de drawdown baseado na equity curve.

    Returns:
        DrawdownMetrics com max drawdown, médio, recovery time, etc.
    """
    if not trades:
        return DrawdownMetrics(
            max_drawdown_pct=0.0,
            max_drawdown_usdt=0.0,
            avg_drawdown_pct=0.0,
            current_drawdown_pct=0.0,
            max_dd_start=None,
            max_dd_end=None,
            recovery_time_hours=None,
            num_drawdown_periods=0,
        )

    # Calcula equity curve (cumulativo)
    equity = [0.0]
    for t in trades:
        equity.append(equity[-1] + t.net_pnl_usdt)

    equity_array = np.array(equity)
    running_max = np.maximum.accumulate(equity_array)
    drawdown = equity_array - running_max
    drawdown_pct = np.where(running_max != 0, (drawdown / running_max) * 100, 0)

    # Max drawdown
    max_dd_idx = np.argmin(drawdown)
    max_dd_pct = drawdown_pct[max_dd_idx]
    max_dd_usdt = drawdown[max_dd_idx]

    # Encontra início e fim do max drawdown
    max_dd_start_idx = np.argmax(running_max[:max_dd_idx + 1])
    max_dd_start_ts = trades[max_dd_start_idx].entry_ts if max_dd_start_idx < len(trades) else None
    max_dd_end_ts = trades[max_dd_idx - 1].exit_ts if max_dd_idx > 0 else None

    # Recovery time (se recuperou)
    recovery_time_hours = None
    if max_dd_idx < len(equity) - 1:
        recovery_idx = None
        peak_equity = running_max[max_dd_start_idx]
        for i in range(max_dd_idx, len(equity)):
            if equity_array[i] >= peak_equity:
                recovery_idx = i
                break

        if recovery_idx is not None and max_dd_start_idx < len(trades):
            try:
                start_dt = datetime.strptime(
                    trades[max_dd_start_idx].entry_ts, "%Y-%m-%d %H:%M:%S,%f"
                )
                end_dt = datetime.strptime(
                    trades[recovery_idx - 1].exit_ts, "%Y-%m-%d %H:%M:%S,%f"
                )
                recovery_time_hours = (end_dt - start_dt).total_seconds() / 3600.0
            except:
                pass

    # Drawdown médio (quando em drawdown)
    drawdowns = drawdown_pct[drawdown_pct < 0]
    avg_dd_pct = np.mean(drawdowns) if len(drawdowns) > 0 else 0.0

    # Current drawdown
    current_dd_pct = drawdown_pct[-1]

    # Número de períodos de drawdown (crossings)
    in_dd = drawdown_pct < -0.01  # Threshold 0.01%
    dd_periods = np.sum(np.diff(in_dd.astype(int)) == 1)

    return DrawdownMetrics(
        max_drawdown_pct=max_dd_pct,
        max_drawdown_usdt=max_dd_usdt,
        avg_drawdown_pct=avg_dd_pct,
        current_drawdown_pct=current_dd_pct,
        max_dd_start=max_dd_start_ts,
        max_dd_end=max_dd_end_ts,
        recovery_time_hours=recovery_time_hours,
        num_drawdown_periods=int(dd_periods),
    )


@dataclass
class RiskMetrics:
    """Métricas de risco ajustadas."""

    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    profit_factor: float
    expectancy_usdt: float
    max_consecutive_wins: int
    max_consecutive_losses: int


def calculate_risk_metrics(
    trades: List[Trade], drawdown: DrawdownMetrics, risk_free_rate: float = 0.0
) -> RiskMetrics:
    """
    Calcula métricas de risco ajustadas.

    Args:
        trades: Lista de trades
        drawdown: Métricas de drawdown
        risk_free_rate: Taxa livre de risco anualizada (ex: 0.04 = 4%)

    Returns:
        RiskMetrics
    """
    if not trades:
        return RiskMetrics(
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            profit_factor=0.0,
            expectancy_usdt=0.0,
            max_consecutive_wins=0,
            max_consecutive_losses=0,
        )

    returns = np.array([t.net_pnl_usdt for t in trades])
    mean_return = np.mean(returns)
    std_return = np.std(returns, ddof=1) if len(returns) > 1 else 0.0

    # Sharpe Ratio (simplificado - não anualizado)
    sharpe = mean_return / std_return if std_return > 0 else 0.0

    # Sortino Ratio (usa apenas downside deviation)
    downside_returns = returns[returns < 0]
    downside_std = np.std(downside_returns, ddof=1) if len(downside_returns) > 1 else 0.0
    sortino = mean_return / downside_std if downside_std > 0 else 0.0

    # Calmar Ratio (return / max drawdown)
    total_return = sum(t.net_pnl_usdt for t in trades)
    calmar = (
        -total_return / drawdown.max_drawdown_usdt
        if drawdown.max_drawdown_usdt < 0
        else 0.0
    )

    # Profit Factor (gross profit / gross loss)
    gross_profit = sum(t.net_pnl_usdt for t in trades if t.net_pnl_usdt > 0)
    gross_loss = abs(sum(t.net_pnl_usdt for t in trades if t.net_pnl_usdt <= 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Expectancy
    expectancy = mean_return

    # Max consecutive wins/losses
    max_consec_wins = 0
    max_consec_losses = 0
    current_wins = 0
    current_losses = 0

    for t in trades:
        if t.net_pnl_usdt > 0:
            current_wins += 1
            current_losses = 0
            max_consec_wins = max(max_consec_wins, current_wins)
        else:
            current_losses += 1
            current_wins = 0
            max_consec_losses = max(max_consec_losses, current_losses)

    return RiskMetrics(
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        profit_factor=profit_factor,
        expectancy_usdt=expectancy,
        max_consecutive_wins=max_consec_wins,
        max_consecutive_losses=max_consec_losses,
    )


# ============================================================================
# PASS/FAIL CRITERIA
# ============================================================================


@dataclass
class ShadowCriteria:
    """Critérios de aprovação shadow → live."""

    min_trades: int = 100
    min_win_rate_pct: float = 52.0
    max_drawdown_pct: float = -15.0
    min_sharpe_ratio: float = 0.5
    min_profit_factor: float = 1.3
    min_positive_pnl_usdt: float = 0.0
    max_consecutive_losses: int = 10


def evaluate_criteria(
    trades: List[Trade],
    win_rate_pct: float,
    total_pnl_usdt: float,
    drawdown: DrawdownMetrics,
    risk_metrics: RiskMetrics,
    criteria: ShadowCriteria,
) -> Tuple[bool, List[str]]:
    """
    Avalia se os resultados do shadow mode atendem os critérios para live.

    Returns:
        (passed, list_of_failures)
    """
    failures = []

    if len(trades) < criteria.min_trades:
        failures.append(
            f"❌ Trades insuficientes: {len(trades)} < {criteria.min_trades}"
        )

    if win_rate_pct < criteria.min_win_rate_pct:
        failures.append(
            f"❌ Win rate baixa: {win_rate_pct:.1f}% < {criteria.min_win_rate_pct}%"
        )

    if drawdown.max_drawdown_pct < criteria.max_drawdown_pct:
        failures.append(
            f"❌ Drawdown excessivo: {drawdown.max_drawdown_pct:.2f}% < {criteria.max_drawdown_pct}%"
        )

    if risk_metrics.sharpe_ratio < criteria.min_sharpe_ratio:
        failures.append(
            f"❌ Sharpe ratio baixo: {risk_metrics.sharpe_ratio:.2f} < {criteria.min_sharpe_ratio}"
        )

    if risk_metrics.profit_factor < criteria.min_profit_factor:
        failures.append(
            f"❌ Profit factor baixo: {risk_metrics.profit_factor:.2f} < {criteria.min_profit_factor}"
        )

    if total_pnl_usdt < criteria.min_positive_pnl_usdt:
        failures.append(
            f"❌ PnL negativo: {total_pnl_usdt:.4f} USDT < {criteria.min_positive_pnl_usdt}"
        )

    if risk_metrics.max_consecutive_losses > criteria.max_consecutive_losses:
        failures.append(
            f"⚠️  Muitas perdas consecutivas: {risk_metrics.max_consecutive_losses} > {criteria.max_consecutive_losses}"
        )

    passed = len(failures) == 0
    return passed, failures


# ============================================================================
# OUTPUT GENERATION
# ============================================================================


def export_trades_csv(trades: List[Trade], csv_path: Path):
    """Exporta trades para CSV com todas as colunas."""
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "entry_ts",
                "exit_ts",
                "entry_price",
                "exit_price",
                "ret_pct",
                "pnl_usdt",
                "fees_usdt",
                "slippage_usdt",
                "net_pnl_usdt",
                "trade_score",
            ],
        )
        writer.writeheader()
        for t in trades:
            writer.writerow(asdict(t))


def generate_equity_curve_data(trades: List[Trade]) -> List[Dict[str, Any]]:
    """Gera dados para plotar equity curve."""
    equity = 0.0
    curve = []
    for i, t in enumerate(trades):
        equity += t.net_pnl_usdt
        curve.append(
            {
                "trade_num": i + 1,
                "exit_ts": t.exit_ts,
                "equity_usdt": equity,
                "net_pnl_usdt": t.net_pnl_usdt,
            }
        )
    return curve


def generate_markdown_report(
    symbol: str,
    timeframe: str,
    trades: List[Trade],
    n_signals_buy: int,
    n_signals_sell: int,
    drawdown: DrawdownMetrics,
    risk_metrics: RiskMetrics,
    criteria: ShadowCriteria,
    passed: bool,
    failures: List[str],
    notional_usdt: float,
    fee_rate: float,
    slippage_bps: float,
    errors: List[str],
) -> str:
    """Gera relatório Markdown completo."""

    wins = [t for t in trades if t.net_pnl_usdt > 0]
    losses = [t for t in trades if t.net_pnl_usdt <= 0]
    win_rate = (len(wins) / len(trades) * 100.0) if trades else 0.0
    total_pnl = sum(t.net_pnl_usdt for t in trades)
    avg_win = np.mean([t.net_pnl_usdt for t in wins]) if wins else 0.0
    avg_loss = np.mean([t.net_pnl_usdt for t in losses]) if losses else 0.0
    best_trade = max(trades, key=lambda t: t.net_pnl_usdt) if trades else None
    worst_trade = min(trades, key=lambda t: t.net_pnl_usdt) if trades else None

    # Header
    report = f"""# 📊 Shadow Mode Analysis Report

**Symbol:** {symbol}
**Timeframe:** {timeframe}
**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
**Notional per trade:** ${notional_usdt:.2f} USDT
**Fee rate:** {fee_rate * 100:.2f}%
**Slippage:** {slippage_bps:.1f} bps

---

## ✅ Pass/Fail Assessment

"""

    if passed:
        report += "### 🎉 **PASSED** - Strategy approved for live trading\n\n"
    else:
        report += "### ❌ **FAILED** - Strategy NOT approved for live trading\n\n"
        report += "**Failures:**\n"
        for failure in failures:
            report += f"- {failure}\n"
        report += "\n"

    # Signals
    report += f"""---

## 📡 Signal Summary

- **Buy signals:** {n_signals_buy}
- **Sell signals:** {n_signals_sell}
- **Trades closed:** {len(trades)}

"""

    if not trades:
        report += "\n**No closed trades to analyze.**\n"
        return report

    # Performance Summary
    report += f"""---

## 💰 Performance Summary

| Metric | Value |
|--------|-------|
| **Total PnL** | **${total_pnl:.4f} USDT** |
| **Win Rate** | **{win_rate:.1f}%** |
| **Total Trades** | {len(trades)} |
| **Wins** | {len(wins)} |
| **Losses** | {len(losses)} |
| **Avg Win** | ${avg_win:.4f} |
| **Avg Loss** | ${avg_loss:.4f} |
| **Best Trade** | ${best_trade.net_pnl_usdt:.4f} ({best_trade.entry_ts} → {best_trade.exit_ts}) |
| **Worst Trade** | ${worst_trade.net_pnl_usdt:.4f} ({worst_trade.entry_ts} → {worst_trade.exit_ts}) |

---

## 📉 Drawdown Analysis

| Metric | Value |
|--------|-------|
| **Max Drawdown** | **{drawdown.max_drawdown_pct:.2f}%** (${drawdown.max_drawdown_usdt:.2f}) |
| **Avg Drawdown** | {drawdown.avg_drawdown_pct:.2f}% |
| **Current Drawdown** | {drawdown.current_drawdown_pct:.2f}% |
| **Drawdown Periods** | {drawdown.num_drawdown_periods} |
| **Max DD Start** | {drawdown.max_dd_start or 'N/A'} |
| **Max DD End** | {drawdown.max_dd_end or 'N/A'} |
| **Recovery Time** | {f'{drawdown.recovery_time_hours:.1f} hours' if drawdown.recovery_time_hours else 'Not recovered'} |

---

## 📊 Risk-Adjusted Metrics

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| **Sharpe Ratio** | {risk_metrics.sharpe_ratio:.2f} | ≥ {criteria.min_sharpe_ratio} | {'✅' if risk_metrics.sharpe_ratio >= criteria.min_sharpe_ratio else '❌'} |
| **Sortino Ratio** | {risk_metrics.sortino_ratio:.2f} | - | - |
| **Calmar Ratio** | {risk_metrics.calmar_ratio:.2f} | - | - |
| **Profit Factor** | {risk_metrics.profit_factor:.2f} | ≥ {criteria.min_profit_factor} | {'✅' if risk_metrics.profit_factor >= criteria.min_profit_factor else '❌'} |
| **Expectancy** | ${risk_metrics.expectancy_usdt:.4f} | > 0 | {'✅' if risk_metrics.expectancy_usdt > 0 else '❌'} |
| **Max Consecutive Wins** | {risk_metrics.max_consecutive_wins} | - | - |
| **Max Consecutive Losses** | {risk_metrics.max_consecutive_losses} | ≤ {criteria.max_consecutive_losses} | {'✅' if risk_metrics.max_consecutive_losses <= criteria.max_consecutive_losses else '⚠️'} |

---

## 🎯 Shadow → Live Criteria

| Criterion | Required | Actual | Status |
|-----------|----------|--------|--------|
| **Min Trades** | {criteria.min_trades} | {len(trades)} | {'✅' if len(trades) >= criteria.min_trades else '❌'} |
| **Min Win Rate** | {criteria.min_win_rate_pct}% | {win_rate:.1f}% | {'✅' if win_rate >= criteria.min_win_rate_pct else '❌'} |
| **Max Drawdown** | {criteria.max_drawdown_pct}% | {drawdown.max_drawdown_pct:.2f}% | {'✅' if drawdown.max_drawdown_pct > criteria.max_drawdown_pct else '❌'} |
| **Min Sharpe** | {criteria.min_sharpe_ratio} | {risk_metrics.sharpe_ratio:.2f} | {'✅' if risk_metrics.sharpe_ratio >= criteria.min_sharpe_ratio else '❌'} |
| **Min Profit Factor** | {criteria.min_profit_factor} | {risk_metrics.profit_factor:.2f} | {'✅' if risk_metrics.profit_factor >= criteria.min_profit_factor else '❌'} |
| **Positive PnL** | ${criteria.min_positive_pnl_usdt} | ${total_pnl:.4f} | {'✅' if total_pnl >= criteria.min_positive_pnl_usdt else '❌'} |

"""

    # Errors section
    if errors:
        report += f"""---

## ⚠️ Parsing Errors

{len(errors)} errors encountered during log parsing:

```
"""
        for err in errors[:20]:  # Limit to first 20 errors
            report += f"{err}\n"
        if len(errors) > 20:
            report += f"... and {len(errors) - 20} more errors\n"
        report += "```\n\n"

    # Footer
    report += f"""---

## 📝 Notes

- **Fee model:** {fee_rate * 100:.2f}% per trade (entry + exit)
- **Slippage model:** {slippage_bps:.1f} bps average
- **Net PnL:** Gross PnL - Fees - Slippage
- **Sharpe/Sortino:** Not annualized (per-trade basis)
- **Recovery time:** Time from max DD start to full recovery

---

*Generated by ITB Staging Analyzer V3*
"""

    return report


# ============================================================================
# MAIN
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Analisa logs de staging com métricas robustas de risco e drawdown."
    )
    parser.add_argument(
        "--logs-dir",
        default="logs",
        help="Diretório onde estão os logs (default: logs)",
    )
    parser.add_argument(
        "--symbol",
        default="BTCUSDT",
        help="Símbolo (default: BTCUSDT)",
    )
    parser.add_argument(
        "--notional",
        type=float,
        default=5.0,
        help="Notional em USDT por trade (default: 5.0)",
    )
    parser.add_argument(
        "--fees",
        type=float,
        default=0.001,
        help="Taxa de fees por trade (default: 0.001 = 0.1%%)",
    )
    parser.add_argument(
        "--slippage-bps",
        type=float,
        default=5.0,
        help="Slippage estimado em basis points (default: 5.0 bps)",
    )
    parser.add_argument(
        "--min-trades",
        type=int,
        default=100,
        help="Mínimo de trades para aprovar (default: 100)",
    )
    parser.add_argument(
        "--min-win-rate",
        type=float,
        default=52.0,
        help="Win rate mínimo em %% (default: 52.0)",
    )
    parser.add_argument(
        "--max-drawdown",
        type=float,
        default=-15.0,
        help="Max drawdown permitido em %% (default: -15.0)",
    )

    args = parser.parse_args()

    logs_dir = Path(args.logs_dir)
    if not logs_dir.exists():
        print(f"❌ Logs directory not found: {logs_dir}")
        sys.exit(1)

    analytics_dir = logs_dir / "analytics"
    analytics_dir.mkdir(parents=True, exist_ok=True)

    # Critérios de aprovação
    criteria = ShadowCriteria(
        min_trades=args.min_trades,
        min_win_rate_pct=args.min_win_rate,
        max_drawdown_pct=args.max_drawdown,
    )

    # Descobrir arquivos
    timeframes = {
        "1m": sorted(logs_dir.glob("server_1m_*.log")),
        "5m": sorted(logs_dir.glob("server_5m_*.log")),
    }

    results: Dict[str, Any] = {
        "symbol": args.symbol,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "notional_usdt": args.notional,
        "fee_rate": args.fees,
        "slippage_bps": args.slippage_bps,
        "logs_dir": str(logs_dir),
        "criteria": asdict(criteria),
        "timeframes": {},
    }

    for tf, files in timeframes.items():
        if not files:
            print(f"\n⚠️  No logs found for {tf} timeframe (server_{tf}_*.log)")
            continue

        print(f"\n{'=' * 80}")
        print(f"Analyzing {args.symbol} {tf} staging logs...")
        print(f"{'=' * 80}\n")

        # Parse logs
        trades, n_signals_buy, n_signals_sell, errors = parse_log_files(
            files, args.notional, args.fees, args.slippage_bps
        )

        if errors:
            print(f"⚠️  {len(errors)} parsing errors encountered (see report for details)")

        if not trades:
            print("❌ No closed trades found. Cannot generate analysis.")
            continue

        # Calcula métricas
        drawdown = calculate_drawdown(trades)
        risk_metrics = calculate_risk_metrics(trades, drawdown)

        wins = [t for t in trades if t.net_pnl_usdt > 0]
        losses = [t for t in trades if t.net_pnl_usdt <= 0]
        win_rate = (len(wins) / len(trades) * 100.0) if trades else 0.0
        total_pnl = sum(t.net_pnl_usdt for t in trades)

        # Avalia critérios
        passed, failures = evaluate_criteria(
            trades, win_rate, total_pnl, drawdown, risk_metrics, criteria
        )

        # Exporta CSV
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        csv_path = analytics_dir / f"trades_{args.symbol}_{tf}_{ts}.csv"
        export_trades_csv(trades, csv_path)
        print(f"✅ Trade details exported: {csv_path}")

        # Gera equity curve data
        equity_curve = generate_equity_curve_data(trades)
        equity_path = analytics_dir / f"equity_{args.symbol}_{tf}_{ts}.json"
        equity_path.write_text(json.dumps(equity_curve, indent=2))
        print(f"✅ Equity curve data exported: {equity_path}")

        # Gera relatório Markdown
        report = generate_markdown_report(
            args.symbol,
            tf,
            trades,
            n_signals_buy,
            n_signals_sell,
            drawdown,
            risk_metrics,
            criteria,
            passed,
            failures,
            args.notional,
            args.fees,
            args.slippage_bps,
            errors,
        )

        report_path = analytics_dir / f"report_{args.symbol}_{tf}_{ts}.md"
        report_path.write_text(report)
        print(f"✅ Markdown report generated: {report_path}")

        # Salva JSON estruturado
        results["timeframes"][tf] = {
            "files": [f.name for f in files],
            "signals": {
                "buy": n_signals_buy,
                "sell": n_signals_sell,
            },
            "trades": {
                "closed": len(trades),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate_pct": win_rate,
                "total_pnl_usdt": total_pnl,
            },
            "drawdown": asdict(drawdown),
            "risk_metrics": asdict(risk_metrics),
            "passed": passed,
            "failures": failures,
            "csv_path": str(csv_path),
            "report_path": str(report_path),
        }

        # Print summary
        print(f"\n{'=' * 80}")
        print(f"SUMMARY: {args.symbol} {tf}")
        print(f"{'=' * 80}")
        print(f"Trades: {len(trades)} | Win Rate: {win_rate:.1f}% | PnL: ${total_pnl:.4f}")
        print(f"Max DD: {drawdown.max_drawdown_pct:.2f}% | Sharpe: {risk_metrics.sharpe_ratio:.2f}")
        print(f"Status: {'✅ PASSED' if passed else '❌ FAILED'}")
        print(f"{'=' * 80}\n")

    # Salva JSON consolidado
    json_path = analytics_dir / f"staging_summary_{args.symbol}_{ts}.json"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\n✅ Consolidated JSON saved: {json_path}")

    print("\n" + "=" * 80)
    print("Analysis complete! Check the analytics/ directory for full reports.")
    print("=" * 80)


if __name__ == "__main__":
    main()
