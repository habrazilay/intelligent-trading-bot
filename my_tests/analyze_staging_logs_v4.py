#!/usr/bin/env python3
"""
Staging Log Analyzer V4 - Production-Ready Realistic Analysis

IMPROVEMENTS FROM V3:
1. Dynamic slippage based on market volatility (ATR proxy)
2. Compounding equity curve with dynamic position sizing
3. Hold-time constraints and same-candle trade detection
4. Log consistency validation and warnings
5. Execution failure simulation (partial fills, timeouts)
6. Adapts to server.log in root directory
7. Spread-based slippage estimation from price volatility

Usage:
    python analyze_staging_logs_v4.py --log-file server.log
    python analyze_staging_logs_v4.py --log-file logs/server_1m_staging.log --starting-capital 1000
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import warnings
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Suppress numpy warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class TradingConfig:
    """Configuração realista de trading."""

    # Capital management
    starting_capital_usdt: float = 1000.0
    risk_per_trade_pct: float = 1.0  # % do capital por trade
    min_position_usdt: float = 5.0
    max_position_usdt: float = 100.0

    # Fees & costs
    taker_fee_rate: float = 0.001  # 0.1% Binance taker
    maker_fee_rate: float = 0.001  # 0.1% Binance maker (assume taker worst case)

    # Slippage (dynamic)
    base_slippage_bps: float = 5.0  # Base: 5 bps
    slippage_volatility_multiplier: float = 2.0  # 2x base quando volátil
    volatility_window: int = 20  # Window para calcular volatility

    # Execution constraints
    min_hold_time_seconds: int = 60  # Mínimo 1 minuto holding
    execution_failure_rate: float = 0.02  # 2% de falha (timeout, reject)
    partial_fill_rate: float = 0.05  # 5% fills parciais
    partial_fill_pct: float = 0.8  # 80% preenchido em partial

    # Risk limits
    max_drawdown_stop_pct: float = -20.0  # Para de operar se DD > 20%
    daily_loss_limit_pct: float = -5.0  # Para no dia se perder 5%


@dataclass
class MarketState:
    """Estado do mercado para cálculo dinâmico de slippage."""

    recent_prices: deque = field(default_factory=lambda: deque(maxlen=50))
    recent_returns: deque = field(default_factory=lambda: deque(maxlen=50))

    def update(self, price: float):
        """Atualiza estado com novo preço."""
        if len(self.recent_prices) > 0:
            ret = (price - self.recent_prices[-1]) / self.recent_prices[-1]
            self.recent_returns.append(ret)
        self.recent_prices.append(price)

    def get_volatility(self) -> float:
        """Retorna volatilidade recente (std de returns)."""
        if len(self.recent_returns) < 5:
            return 0.001  # Default baixo
        return float(np.std(self.recent_returns))

    def estimate_slippage_bps(self, config: TradingConfig) -> float:
        """
        Estima slippage dinâmico baseado em volatilidade.

        Lógica: volatilidade alta = spread maior = mais slippage
        """
        vol = self.get_volatility()
        vol_normalized = vol / 0.001  # Normaliza contra 0.1% volatility
        multiplier = 1.0 + (vol_normalized * config.slippage_volatility_multiplier)
        slippage_bps = config.base_slippage_bps * multiplier
        return min(slippage_bps, 50.0)  # Cap em 50 bps


# ============================================================================
# LOG PARSING
# ============================================================================

SIGNAL_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}).*?"
    r"Analyze finished\.\s+Close:\s+(?P<price>[0-9.,]+)\s+S\w+:\s*"
    r"trade[_ ]score=(?P<score>[+\-]?[0-9.,]+),\s*"
    r"buy_signal=(?P<buy>True|False),\s*sell_signal=(?P<sell>True|False)"
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


def parse_timestamp(ts_str: str) -> datetime:
    """Parse timestamp do log."""
    return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S,%f")


@dataclass
class Signal:
    """Representa um sinal do log."""

    timestamp: datetime
    price: float
    score: float
    buy: bool
    sell: bool
    line_num: int
    source_file: str


def parse_log_file(
    log_path: Path,
    config: TradingConfig,
) -> Tuple[List[Signal], List[str]]:
    """
    Parseia arquivo de log e retorna lista de sinais.

    Returns:
        (signals, errors)
    """
    signals: List[Signal] = []
    errors: List[str] = []

    if not log_path.exists():
        errors.append(f"Log file not found: {log_path}")
        return signals, errors

    try:
        text = log_path.read_text(errors="ignore")
    except Exception as e:
        errors.append(f"Failed to read {log_path.name}: {e}")
        return signals, errors

    for line_num, line in enumerate(text.splitlines(), 1):
        try:
            m = SIGNAL_RE.search(line)
            if not m:
                continue

            ts_str = m.group("ts")
            price_str = m.group("price")
            score_str = m.group("score")
            buy_str = m.group("buy")
            sell_str = m.group("sell")

            signal = Signal(
                timestamp=parse_timestamp(ts_str),
                price=parse_price(price_str),
                score=parse_score(score_str),
                buy=buy_str == "True",
                sell=sell_str == "True",
                line_num=line_num,
                source_file=log_path.name,
            )
            signals.append(signal)

        except Exception as e:
            errors.append(f"{log_path.name}:{line_num} - Parse error: {e}")
            continue

    return signals, errors


# ============================================================================
# TRADING SIMULATION
# ============================================================================

@dataclass
class Trade:
    """Representa um trade completo (entry → exit)."""

    entry_signal: Signal
    exit_signal: Signal
    position_size_usdt: float
    entry_price: float
    exit_price: float
    hold_time_seconds: float

    # P&L components
    gross_pnl_usdt: float
    fees_usdt: float
    slippage_usdt: float
    net_pnl_usdt: float

    # Metadata
    entry_equity: float
    exit_equity: float
    was_partial_fill: bool = False
    execution_failed: bool = False
    same_candle_warning: bool = False


@dataclass
class PositionState:
    """Estado da posição aberta."""

    entry_signal: Signal
    position_size_usdt: float
    entry_price_with_slippage: float


@dataclass
class PortfolioState:
    """Estado do portfolio com capital compounding."""

    equity_usdt: float
    starting_equity: float
    peak_equity: float
    trades: List[Trade] = field(default_factory=list)
    position: Optional[PositionState] = None
    daily_pnl: Dict[str, float] = field(default_factory=dict)
    stopped_trading: bool = False
    stop_reason: Optional[str] = None


def calculate_position_size(
    equity: float,
    config: TradingConfig,
) -> float:
    """Calcula tamanho da posição baseado em % do capital."""
    size = equity * (config.risk_per_trade_pct / 100.0)
    size = max(size, config.min_position_usdt)
    size = min(size, config.max_position_usdt)
    return size


def simulate_execution_failure(config: TradingConfig) -> bool:
    """Simula falha de execução (timeout, reject, etc)."""
    return np.random.random() < config.execution_failure_rate


def simulate_partial_fill(config: TradingConfig) -> Tuple[bool, float]:
    """
    Simula fill parcial.

    Returns:
        (is_partial, fill_percentage)
    """
    if np.random.random() < config.partial_fill_rate:
        return True, config.partial_fill_pct
    return False, 1.0


def simulate_trading(
    signals: List[Signal],
    config: TradingConfig,
    market_state: MarketState,
) -> Tuple[PortfolioState, List[str]]:
    """
    Simula trading realista com todas as restrições.

    Returns:
        (portfolio_state, warnings)
    """
    portfolio = PortfolioState(
        equity_usdt=config.starting_capital_usdt,
        starting_equity=config.starting_capital_usdt,
        peak_equity=config.starting_capital_usdt,
    )

    warnings_list: List[str] = []

    for signal in signals:
        # Atualiza market state
        market_state.update(signal.price)

        # Check if stopped trading
        if portfolio.stopped_trading:
            continue

        # Check daily loss limit
        day_key = signal.timestamp.strftime("%Y-%m-%d")
        if day_key not in portfolio.daily_pnl:
            portfolio.daily_pnl[day_key] = 0.0

        daily_pnl_pct = (portfolio.daily_pnl[day_key] / portfolio.starting_equity) * 100
        if daily_pnl_pct < config.daily_loss_limit_pct:
            portfolio.stopped_trading = True
            portfolio.stop_reason = f"Daily loss limit hit on {day_key}: {daily_pnl_pct:.2f}%"
            warnings_list.append(portfolio.stop_reason)
            continue

        # Check max drawdown stop
        current_dd_pct = ((portfolio.equity_usdt - portfolio.peak_equity) / portfolio.peak_equity) * 100
        if current_dd_pct < config.max_drawdown_stop_pct:
            portfolio.stopped_trading = True
            portfolio.stop_reason = f"Max drawdown stop hit: {current_dd_pct:.2f}%"
            warnings_list.append(portfolio.stop_reason)
            continue

        # BUY SIGNAL - Open position
        if signal.buy and portfolio.position is None:
            # Simulate execution failure
            if simulate_execution_failure(config):
                warnings_list.append(
                    f"Execution failure on BUY at {signal.timestamp}: {signal.price}"
                )
                continue

            # Calculate position size
            position_size = calculate_position_size(portfolio.equity_usdt, config)

            # Simulate partial fill
            is_partial, fill_pct = simulate_partial_fill(config)
            if is_partial:
                position_size *= fill_pct
                warnings_list.append(
                    f"Partial fill on BUY ({fill_pct*100:.0f}%) at {signal.timestamp}"
                )

            # Calculate slippage
            slippage_bps = market_state.estimate_slippage_bps(config)
            slippage_pct = slippage_bps / 10000.0
            entry_price_with_slippage = signal.price * (1 + slippage_pct)

            # Open position
            portfolio.position = PositionState(
                entry_signal=signal,
                position_size_usdt=position_size,
                entry_price_with_slippage=entry_price_with_slippage,
            )

        # SELL SIGNAL - Close position
        elif signal.sell and portfolio.position is not None:
            pos = portfolio.position

            # Check hold time constraint
            hold_time = (signal.timestamp - pos.entry_signal.timestamp).total_seconds()
            same_candle = hold_time < 60.0  # Less than 1 minute

            if hold_time < config.min_hold_time_seconds:
                warnings_list.append(
                    f"Hold time too short ({hold_time:.0f}s) - skipping exit at {signal.timestamp}"
                )
                continue

            # Simulate execution failure
            if simulate_execution_failure(config):
                warnings_list.append(
                    f"Execution failure on SELL at {signal.timestamp}: {signal.price}"
                )
                continue

            # Calculate exit with slippage
            slippage_bps = market_state.estimate_slippage_bps(config)
            slippage_pct = slippage_bps / 10000.0
            exit_price_with_slippage = signal.price * (1 - slippage_pct)

            # Calculate P&L
            gross_pnl_pct = (exit_price_with_slippage - pos.entry_price_with_slippage) / pos.entry_price_with_slippage
            gross_pnl_usdt = pos.position_size_usdt * gross_pnl_pct

            # Fees
            fees_entry = pos.position_size_usdt * config.taker_fee_rate
            fees_exit = pos.position_size_usdt * config.taker_fee_rate
            fees_total = fees_entry + fees_exit

            # Slippage cost
            slippage_cost_entry = pos.position_size_usdt * (market_state.estimate_slippage_bps(config) / 10000.0)
            slippage_cost_exit = pos.position_size_usdt * (slippage_bps / 10000.0)
            slippage_total = slippage_cost_entry + slippage_cost_exit

            # Net P&L
            net_pnl = gross_pnl_usdt - fees_total - slippage_total

            # Update equity
            new_equity = portfolio.equity_usdt + net_pnl

            # Create trade record
            trade = Trade(
                entry_signal=pos.entry_signal,
                exit_signal=signal,
                position_size_usdt=pos.position_size_usdt,
                entry_price=pos.entry_price_with_slippage,
                exit_price=exit_price_with_slippage,
                hold_time_seconds=hold_time,
                gross_pnl_usdt=gross_pnl_usdt,
                fees_usdt=fees_total,
                slippage_usdt=slippage_total,
                net_pnl_usdt=net_pnl,
                entry_equity=portfolio.equity_usdt,
                exit_equity=new_equity,
                same_candle_warning=same_candle,
            )

            portfolio.trades.append(trade)
            portfolio.equity_usdt = new_equity
            portfolio.peak_equity = max(portfolio.peak_equity, portfolio.equity_usdt)
            portfolio.position = None

            # Update daily P&L
            portfolio.daily_pnl[day_key] += net_pnl

    return portfolio, warnings_list


# ============================================================================
# VALIDATION & CONSISTENCY CHECKS
# ============================================================================

@dataclass
class ValidationReport:
    """Relatório de validação do log."""

    total_signals: int
    buy_signals: int
    sell_signals: int
    signal_imbalance: int  # |buy - sell|
    duplicate_timestamps: int
    out_of_order_timestamps: int
    extreme_price_moves: List[str]  # Price jumps > 10%
    warnings: List[str]

    def is_valid(self) -> bool:
        """Retorna True se log parece válido."""
        critical_issues = (
            self.out_of_order_timestamps > 0 or
            len(self.extreme_price_moves) > 5 or
            abs(self.signal_imbalance) > 50
        )
        return not critical_issues


def validate_signals(signals: List[Signal]) -> ValidationReport:
    """Valida consistência dos sinais parseados."""

    buy_count = sum(1 for s in signals if s.buy)
    sell_count = sum(1 for s in signals if s.sell)

    # Check timestamps
    prev_ts = None
    out_of_order = 0
    duplicates = 0

    for s in signals:
        if prev_ts is not None:
            if s.timestamp < prev_ts:
                out_of_order += 1
            elif s.timestamp == prev_ts:
                duplicates += 1
        prev_ts = s.timestamp

    # Check extreme price moves
    extreme_moves = []
    for i in range(1, len(signals)):
        price_change_pct = abs((signals[i].price - signals[i-1].price) / signals[i-1].price) * 100
        if price_change_pct > 10.0:
            extreme_moves.append(
                f"{signals[i-1].timestamp} → {signals[i].timestamp}: "
                f"{price_change_pct:.1f}% move ({signals[i-1].price} → {signals[i].price})"
            )

    # Generate warnings
    warnings = []
    imbalance = abs(buy_count - sell_count)
    if imbalance > 10:
        warnings.append(f"Signal imbalance: {buy_count} buys vs {sell_count} sells (diff: {imbalance})")

    if out_of_order > 0:
        warnings.append(f"{out_of_order} out-of-order timestamps detected")

    if duplicates > 0:
        warnings.append(f"{duplicates} duplicate timestamps detected")

    if len(extreme_moves) > 0:
        warnings.append(f"{len(extreme_moves)} extreme price moves (>10%) detected")

    return ValidationReport(
        total_signals=len(signals),
        buy_signals=buy_count,
        sell_signals=sell_count,
        signal_imbalance=imbalance,
        duplicate_timestamps=duplicates,
        out_of_order_timestamps=out_of_order,
        extreme_price_moves=extreme_moves,
        warnings=warnings,
    )


# ============================================================================
# METRICS (SAME AS V3)
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
    """Calcula drawdown baseado na equity curve com compounding."""
    if not trades:
        return DrawdownMetrics(
            max_drawdown_pct=0.0, max_drawdown_usdt=0.0,
            avg_drawdown_pct=0.0, current_drawdown_pct=0.0,
            max_dd_start=None, max_dd_end=None,
            recovery_time_hours=None, num_drawdown_periods=0,
        )

    equity = np.array([t.exit_equity for t in trades])
    running_max = np.maximum.accumulate(equity)
    drawdown = equity - running_max
    drawdown_pct = np.where(running_max != 0, (drawdown / running_max) * 100, 0)

    max_dd_idx = np.argmin(drawdown)
    max_dd_pct = drawdown_pct[max_dd_idx]
    max_dd_usdt = drawdown[max_dd_idx]

    max_dd_start_idx = np.argmax(running_max[:max_dd_idx + 1])
    max_dd_start_ts = trades[max_dd_start_idx].entry_signal.timestamp.strftime("%Y-%m-%d %H:%M:%S") if max_dd_start_idx < len(trades) else None
    max_dd_end_ts = trades[max_dd_idx].exit_signal.timestamp.strftime("%Y-%m-%d %H:%M:%S") if max_dd_idx < len(trades) else None

    recovery_time_hours = None
    if max_dd_idx < len(equity) - 1:
        recovery_idx = None
        peak_equity = running_max[max_dd_start_idx]
        for i in range(max_dd_idx, len(equity)):
            if equity[i] >= peak_equity:
                recovery_idx = i
                break

        if recovery_idx is not None:
            delta = trades[recovery_idx].exit_signal.timestamp - trades[max_dd_start_idx].entry_signal.timestamp
            recovery_time_hours = delta.total_seconds() / 3600.0

    drawdowns = drawdown_pct[drawdown_pct < 0]
    avg_dd_pct = np.mean(drawdowns) if len(drawdowns) > 0 else 0.0
    current_dd_pct = drawdown_pct[-1]

    in_dd = drawdown_pct < -0.01
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
    avg_hold_time_minutes: float


def calculate_risk_metrics(trades: List[Trade], drawdown: DrawdownMetrics) -> RiskMetrics:
    """Calcula métricas de risco."""
    if not trades:
        return RiskMetrics(
            sharpe_ratio=0.0, sortino_ratio=0.0, calmar_ratio=0.0,
            profit_factor=0.0, expectancy_usdt=0.0,
            max_consecutive_wins=0, max_consecutive_losses=0,
            avg_hold_time_minutes=0.0,
        )

    returns = np.array([t.net_pnl_usdt for t in trades])
    mean_return = np.mean(returns)
    std_return = np.std(returns, ddof=1) if len(returns) > 1 else 0.0

    sharpe = mean_return / std_return if std_return > 0 else 0.0

    downside_returns = returns[returns < 0]
    downside_std = np.std(downside_returns, ddof=1) if len(downside_returns) > 1 else 0.0
    sortino = mean_return / downside_std if downside_std > 0 else 0.0

    total_return = sum(t.net_pnl_usdt for t in trades)
    calmar = -total_return / drawdown.max_drawdown_usdt if drawdown.max_drawdown_usdt < 0 else 0.0

    gross_profit = sum(t.net_pnl_usdt for t in trades if t.net_pnl_usdt > 0)
    gross_loss = abs(sum(t.net_pnl_usdt for t in trades if t.net_pnl_usdt <= 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

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

    avg_hold_time = np.mean([t.hold_time_seconds for t in trades]) / 60.0

    return RiskMetrics(
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        profit_factor=profit_factor,
        expectancy_usdt=mean_return,
        max_consecutive_wins=max_consec_wins,
        max_consecutive_losses=max_consec_losses,
        avg_hold_time_minutes=avg_hold_time,
    )


# ============================================================================
# OUTPUTS
# ============================================================================

def export_trades_csv(trades: List[Trade], csv_path: Path):
    """Exporta trades para CSV."""
    with csv_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "entry_ts", "exit_ts", "hold_minutes",
            "entry_price", "exit_price", "position_usdt",
            "gross_pnl", "fees", "slippage", "net_pnl",
            "entry_equity", "exit_equity", "return_pct",
            "same_candle_warning"
        ])

        for t in trades:
            writer.writerow([
                t.entry_signal.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                t.exit_signal.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                f"{t.hold_time_seconds / 60:.1f}",
                f"{t.entry_price:.2f}",
                f"{t.exit_price:.2f}",
                f"{t.position_size_usdt:.2f}",
                f"{t.gross_pnl_usdt:.4f}",
                f"{t.fees_usdt:.4f}",
                f"{t.slippage_usdt:.4f}",
                f"{t.net_pnl_usdt:.4f}",
                f"{t.entry_equity:.2f}",
                f"{t.exit_equity:.2f}",
                f"{(t.net_pnl_usdt / t.position_size_usdt) * 100:.2f}",
                "YES" if t.same_candle_warning else "NO",
            ])


def generate_markdown_report(
    config: TradingConfig,
    portfolio: PortfolioState,
    validation: ValidationReport,
    drawdown: DrawdownMetrics,
    risk_metrics: RiskMetrics,
    sim_warnings: List[str],
    parse_errors: List[str],
) -> str:
    """Gera relatório Markdown completo."""

    trades = portfolio.trades
    wins = [t for t in trades if t.net_pnl_usdt > 0]
    losses = [t for t in trades if t.net_pnl_usdt <= 0]
    win_rate = (len(wins) / len(trades) * 100.0) if trades else 0.0

    total_return_pct = ((portfolio.equity_usdt - portfolio.starting_equity) / portfolio.starting_equity) * 100

    report = f"""# 📊 Shadow Mode Analysis Report V4 - Production Reality

**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

---

## ⚙️ Trading Configuration

| Parameter | Value |
|-----------|-------|
| **Starting Capital** | ${config.starting_capital_usdt:.2f} USDT |
| **Risk per Trade** | {config.risk_per_trade_pct}% of equity |
| **Position Size Range** | ${config.min_position_usdt} - ${config.max_position_usdt} |
| **Fee Rate** | {config.taker_fee_rate * 100:.2f}% (taker) |
| **Base Slippage** | {config.base_slippage_bps:.1f} bps (dynamic) |
| **Min Hold Time** | {config.min_hold_time_seconds}s |
| **Execution Failure Rate** | {config.execution_failure_rate * 100:.1f}% |
| **Max Drawdown Stop** | {config.max_drawdown_stop_pct}% |

---

## 📡 Log Validation

| Metric | Value | Status |
|--------|-------|--------|
| **Total Signals** | {validation.total_signals} | {'✅' if validation.total_signals > 0 else '❌'} |
| **Buy Signals** | {validation.buy_signals} | - |
| **Sell Signals** | {validation.sell_signals} | - |
| **Signal Imbalance** | {validation.signal_imbalance} | {'✅' if validation.signal_imbalance < 20 else '⚠️'} |
| **Out of Order TS** | {validation.out_of_order_timestamps} | {'✅' if validation.out_of_order_timestamps == 0 else '❌'} |
| **Duplicate TS** | {validation.duplicate_timestamps} | {'✅' if validation.duplicate_timestamps == 0 else '⚠️'} |
| **Extreme Moves** | {len(validation.extreme_price_moves)} | {'✅' if len(validation.extreme_price_moves) < 5 else '⚠️'} |
| **Overall Valid** | - | {'✅ PASS' if validation.is_valid() else '❌ FAIL'} |

"""

    if validation.warnings:
        report += "\n**⚠️ Validation Warnings:**\n"
        for w in validation.warnings[:10]:
            report += f"- {w}\n"
        report += "\n"

    if not trades:
        report += "\n**❌ No trades executed. Cannot generate performance analysis.**\n"
        return report

    report += f"""---

## 💰 Performance Summary (Compounding)

| Metric | Value |
|--------|-------|
| **Starting Equity** | ${portfolio.starting_equity:.2f} |
| **Final Equity** | **${portfolio.equity_usdt:.2f}** |
| **Total Return** | **{total_return_pct:+.2f}%** |
| **Peak Equity** | ${portfolio.peak_equity:.2f} |
| **Total Trades** | {len(trades)} |
| **Wins** | {len(wins)} ({win_rate:.1f}%) |
| **Losses** | {len(losses)} |
| **Avg Hold Time** | {risk_metrics.avg_hold_time_minutes:.1f} min |

"""

    if portfolio.stopped_trading:
        report += f"\n⚠️ **TRADING STOPPED:** {portfolio.stop_reason}\n\n"

    report += f"""---

## 📉 Drawdown Analysis (Compounding)

| Metric | Value |
|--------|-------|
| **Max Drawdown** | **{drawdown.max_drawdown_pct:.2f}%** (${drawdown.max_drawdown_usdt:.2f}) |
| **Avg Drawdown** | {drawdown.avg_drawdown_pct:.2f}% |
| **Current Drawdown** | {drawdown.current_drawdown_pct:.2f}% |
| **Recovery Time** | {f'{drawdown.recovery_time_hours:.1f}h' if drawdown.recovery_time_hours else 'Not recovered'} |

---

## 📊 Risk Metrics

| Metric | Value |
|--------|-------|
| **Sharpe Ratio** | {risk_metrics.sharpe_ratio:.2f} |
| **Sortino Ratio** | {risk_metrics.sortino_ratio:.2f} |
| **Calmar Ratio** | {risk_metrics.calmar_ratio:.2f} |
| **Profit Factor** | {risk_metrics.profit_factor:.2f} |
| **Expectancy** | ${risk_metrics.expectancy_usdt:.4f} |
| **Max Consec Wins** | {risk_metrics.max_consecutive_wins} |
| **Max Consec Losses** | {risk_metrics.max_consecutive_losses} |

---

## ⚠️ Simulation Warnings

**Total warnings:** {len(sim_warnings)}

"""

    if sim_warnings:
        report += "**Sample warnings:**\n"
        for w in sim_warnings[:15]:
            report += f"- {w}\n"
        if len(sim_warnings) > 15:
            report += f"\n... and {len(sim_warnings) - 15} more warnings\n"
    else:
        report += "✅ No warnings during simulation\n"

    report += "\n---\n\n"

    if parse_errors:
        report += f"## 🐛 Parse Errors\n\n{len(parse_errors)} errors:\n\n```\n"
        for e in parse_errors[:10]:
            report += f"{e}\n"
        if len(parse_errors) > 10:
            report += f"... and {len(parse_errors) - 10} more\n"
        report += "```\n\n---\n\n"

    report += """## 📝 V4 Improvements

- ✅ Dynamic slippage based on volatility
- ✅ Compounding equity curve
- ✅ Position sizing as % of capital
- ✅ Hold-time constraints (min 60s)
- ✅ Execution failure simulation (2%)
- ✅ Partial fill simulation (5%)
- ✅ Daily loss limits
- ✅ Max drawdown stop
- ✅ Log validation & consistency checks
- ✅ Same-candle trade detection

---

*Generated by ITB Staging Analyzer V4 - Production Reality*
"""

    return report


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="V4: Production-ready staging log analysis with realistic constraints"
    )
    parser.add_argument(
        "--log-file",
        default="server.log",
        help="Log file to analyze (default: server.log in root)",
    )
    parser.add_argument(
        "--starting-capital",
        type=float,
        default=1000.0,
        help="Starting capital in USDT (default: 1000)",
    )
    parser.add_argument(
        "--risk-per-trade",
        type=float,
        default=1.0,
        help="Risk per trade as %% of capital (default: 1.0)",
    )
    parser.add_argument(
        "--output-dir",
        default="logs/analytics",
        help="Output directory (default: logs/analytics)",
    )

    args = parser.parse_args()

    log_path = Path(args.log_file)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Config
    config = TradingConfig(
        starting_capital_usdt=args.starting_capital,
        risk_per_trade_pct=args.risk_per_trade,
    )

    print("=" * 80)
    print("ITB Staging Analyzer V4 - Production Reality")
    print("=" * 80)
    print(f"\nLog file: {log_path}")
    print(f"Starting capital: ${config.starting_capital_usdt:.2f}")
    print(f"Risk per trade: {config.risk_per_trade_pct}%\n")

    # Parse
    print("Parsing log file...")
    signals, parse_errors = parse_log_file(log_path, config)

    if not signals:
        print("❌ No signals found in log file!")
        sys.exit(1)

    print(f"✅ Parsed {len(signals)} signals")
    if parse_errors:
        print(f"⚠️  {len(parse_errors)} parse errors")

    # Validate
    print("\nValidating signals...")
    validation = validate_signals(signals)

    if not validation.is_valid():
        print("❌ Log validation FAILED - results may be unreliable!")
        for w in validation.warnings:
            print(f"  - {w}")
    else:
        print("✅ Log validation passed")

    # Simulate
    print("\nSimulating trading with realistic constraints...")
    market_state = MarketState()
    portfolio, sim_warnings = simulate_trading(signals, config, market_state)

    print(f"✅ Simulation complete: {len(portfolio.trades)} trades executed")
    if sim_warnings:
        print(f"⚠️  {len(sim_warnings)} simulation warnings")

    if not portfolio.trades:
        print("❌ No trades executed. Check your signals and config.")
        sys.exit(1)

    # Calculate metrics
    print("\nCalculating metrics...")
    drawdown = calculate_drawdown(portfolio.trades)
    risk_metrics = calculate_risk_metrics(portfolio.trades, drawdown)

    # Export
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    csv_path = output_dir / f"trades_v4_{ts}.csv"
    export_trades_csv(portfolio.trades, csv_path)
    print(f"✅ Trades CSV: {csv_path}")

    report_path = output_dir / f"report_v4_{ts}.md"
    report = generate_markdown_report(
        config, portfolio, validation, drawdown, risk_metrics,
        sim_warnings, parse_errors
    )
    report_path.write_text(report)
    print(f"✅ Report: {report_path}")

    # Summary
    total_return_pct = ((portfolio.equity_usdt - portfolio.starting_equity) / portfolio.starting_equity) * 100
    wins = [t for t in portfolio.trades if t.net_pnl_usdt > 0]
    win_rate = (len(wins) / len(portfolio.trades) * 100.0) if portfolio.trades else 0.0

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Starting: ${portfolio.starting_equity:.2f} → Final: ${portfolio.equity_usdt:.2f}")
    print(f"Return: {total_return_pct:+.2f}% | Trades: {len(portfolio.trades)} | Win Rate: {win_rate:.1f}%")
    print(f"Max DD: {drawdown.max_drawdown_pct:.2f}% | Sharpe: {risk_metrics.sharpe_ratio:.2f}")
    print("=" * 80)


if __name__ == "__main__":
    main()
