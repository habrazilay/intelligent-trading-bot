#!/usr/bin/env python3
"""
Unified Pipeline Analyzer - Consolidated Results Report

Analyzes ML pipeline outputs and generates comprehensive reports with:
- Model metrics (AUC, precision, recall)
- Best threshold combinations
- Simulated trade performance (LONG/SHORT)
- Equity curve visualization
- Walk-forward validation
- Warnings and anomaly detection

Usage:
    python tools/analyze_pipeline.py --data-dir DATA_ITB_5m/BTCUSDT --strategy conservative
    python tools/analyze_pipeline.py --data-dir DATA_ITB_5m --symbol BTCUSDT --strategy aggressive
    python tools/analyze_pipeline.py --compare conservative aggressive quick_profit
    python tools/analyze_pipeline.py --walk-forward --folds 5

Output:
    - Console summary
    - Markdown report (reports/analysis_{symbol}_{strategy}_{timestamp}.md)
    - Equity curve PNG (reports/equity_{symbol}_{strategy}_{timestamp}.png)
    - JSON metrics (reports/metrics_{symbol}_{strategy}_{timestamp}.json)
"""

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Optional: matplotlib for charts
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib not installed. Charts will be skipped.")


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ModelMetrics:
    """Metrics from predictions_*.txt"""
    model_name: str
    auc: float
    ap: float  # Average Precision
    f1: float
    precision: float
    recall: float

    def is_good(self) -> bool:
        return self.auc >= 0.7 and self.precision >= 0.5

    def get_warnings(self) -> List[str]:
        warnings = []
        if self.auc < 0.6:
            warnings.append(f"{self.model_name}: AUC muito baixo ({self.auc:.3f} < 0.6) - modelo random")
        elif self.auc < 0.7:
            warnings.append(f"{self.model_name}: AUC fraco ({self.auc:.3f} < 0.7)")
        if self.precision < 0.3:
            warnings.append(f"{self.model_name}: Precision muito baixa ({self.precision:.3f})")
        if self.recall < 0.01:
            warnings.append(f"{self.model_name}: Recall quase zero ({self.recall:.3f}) - modelo muito conservador")
        return warnings


@dataclass
class ThresholdResult:
    """Result from signal_models_*.txt grid search"""
    buy_threshold: float
    sell_threshold: float
    transactions: int
    profit: float
    profit_pct: float
    profitable_count: int
    profitable_pct: float
    profit_per_trade: float
    profit_pct_per_trade: float
    transactions_per_month: float = 0.0
    profit_per_month: float = 0.0
    profit_pct_per_month: float = 0.0


@dataclass
class TradePerformance:
    """Simulated trade performance"""
    strategy_type: str  # 'long', 'short', 'combined'
    total_trades: int
    profitable_trades: int
    win_rate: float
    total_profit: float
    total_profit_pct: float
    avg_profit_per_trade: float
    avg_profit_pct_per_trade: float
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    avg_hold_time_candles: float = 0.0


@dataclass
class DrawdownMetrics:
    """Drawdown analysis"""
    max_drawdown_pct: float
    max_drawdown_value: float
    avg_drawdown_pct: float
    current_drawdown_pct: float
    num_drawdown_periods: int
    longest_drawdown_candles: int


@dataclass
class WalkForwardResult:
    """Walk-forward validation result for one fold"""
    fold: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_win_rate: float
    test_win_rate: float
    train_profit_pct: float
    test_profit_pct: float
    degradation_pct: float  # (train - test) / train


@dataclass
class AnalysisReport:
    """Complete analysis report"""
    symbol: str
    strategy: str
    freq: str
    timestamp: str
    data_period: str
    total_candles: int

    # Model metrics
    model_metrics: List[ModelMetrics] = field(default_factory=list)

    # Threshold results
    threshold_results: List[ThresholdResult] = field(default_factory=list)
    best_threshold: Optional[ThresholdResult] = None

    # Trade performance
    long_performance: Optional[TradePerformance] = None
    short_performance: Optional[TradePerformance] = None
    combined_performance: Optional[TradePerformance] = None

    # Equity curve data
    equity_curve: List[float] = field(default_factory=list)
    equity_timestamps: List[str] = field(default_factory=list)

    # Drawdown
    drawdown: Optional[DrawdownMetrics] = None

    # Walk-forward
    walk_forward_results: List[WalkForwardResult] = field(default_factory=list)
    walk_forward_avg_degradation: float = 0.0

    # Warnings
    warnings: List[str] = field(default_factory=list)

    # Risk metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    profit_factor: float = 0.0


# =============================================================================
# PARSERS
# =============================================================================

def parse_predictions_txt(filepath: Path) -> List[ModelMetrics]:
    """Parse predictions_*.txt to extract model metrics"""
    metrics = []

    if not filepath.exists():
        return metrics

    content = filepath.read_text()

    # Pattern: model_name: {'auc': 0.912, 'ap': 0.592, 'f1': 0.074, 'precision': 0.981, 'recall': 0.038}
    pattern = r"(\w+):\s*\{['\"]auc['\"]: ([0-9.]+),\s*['\"]ap['\"]: ([0-9.]+),\s*['\"]f1['\"]: ([0-9.]+),\s*['\"]precision['\"]: ([0-9.]+),\s*['\"]recall['\"]: ([0-9.]+)\}"

    for match in re.finditer(pattern, content):
        model_name = match.group(1)
        metrics.append(ModelMetrics(
            model_name=model_name,
            auc=float(match.group(2)),
            ap=float(match.group(3)),
            f1=float(match.group(4)),
            precision=float(match.group(5)),
            recall=float(match.group(6)),
        ))

    return metrics


def parse_signal_models_txt(filepath: Path) -> List[ThresholdResult]:
    """Parse signal_models_*.txt to extract threshold grid search results"""
    results = []

    if not filepath.exists():
        return results

    content = filepath.read_text()
    lines = content.strip().split('\n')

    # Skip header line
    for line in lines[1:]:
        if not line.strip():
            continue

        parts = line.split(',')
        if len(parts) >= 9:
            try:
                results.append(ThresholdResult(
                    buy_threshold=float(parts[0]),
                    sell_threshold=float(parts[1]),
                    transactions=int(parts[2]),
                    profit=float(parts[3]),
                    profit_pct=float(parts[4]),
                    profitable_count=int(parts[5]),
                    profitable_pct=float(parts[6]),
                    profit_per_trade=float(parts[7]),
                    profit_pct_per_trade=float(parts[8]),
                    transactions_per_month=float(parts[9]) if len(parts) > 9 else 0.0,
                    profit_per_month=float(parts[10]) if len(parts) > 10 else 0.0,
                    profit_pct_per_month=float(parts[11]) if len(parts) > 11 else 0.0,
                ))
            except (ValueError, IndexError):
                continue

    return results


def parse_features_txt(filepath: Path) -> List[str]:
    """Parse features_*.txt to get feature list"""
    if not filepath.exists():
        return []

    content = filepath.read_text().strip()
    # Remove quotes and split by comma
    features = [f.strip().strip('"').strip("'") for f in content.split(',')]
    return [f for f in features if f]


def parse_labels_txt(filepath: Path) -> List[str]:
    """Parse matrix_*.labels.txt to get label names"""
    if not filepath.exists():
        return []

    content = filepath.read_text().strip()
    labels = [l.strip().strip('"').strip("'") for l in content.split(',')]
    return [l for l in labels if l]


# =============================================================================
# TRADE SIMULATION
# =============================================================================

def simulate_trades(
    df: pd.DataFrame,
    buy_col: str = 'buy_signal',
    sell_col: str = 'sell_signal',
    price_col: str = 'close',
    initial_capital: float = 10000.0,
) -> Tuple[TradePerformance, TradePerformance, TradePerformance, List[dict]]:
    """
    Simulate LONG and SHORT trades from signals.

    Returns: (long_perf, short_perf, combined_perf, trades_list)
    """
    trades = []

    # LONG: Buy on buy_signal, Sell on sell_signal
    long_position = None
    long_trades = []

    # SHORT: Sell on sell_signal, Buy on buy_signal
    short_position = None
    short_trades = []

    for idx, row in df.iterrows():
        price = row[price_col]
        buy_signal = row[buy_col] if buy_col in row else False
        sell_signal = row[sell_col] if sell_col in row else False
        ts = row.get('timestamp', idx)

        if pd.isna(price) or price <= 0:
            continue

        # LONG strategy
        if buy_signal and long_position is None:
            long_position = {'entry_idx': idx, 'entry_price': price, 'entry_ts': ts}
        elif sell_signal and long_position is not None:
            profit = price - long_position['entry_price']
            profit_pct = (profit / long_position['entry_price']) * 100
            hold_candles = idx - long_position['entry_idx'] if isinstance(idx, int) else 0

            long_trades.append({
                'type': 'LONG',
                'entry_ts': long_position['entry_ts'],
                'exit_ts': ts,
                'entry_price': long_position['entry_price'],
                'exit_price': price,
                'profit': profit,
                'profit_pct': profit_pct,
                'hold_candles': hold_candles,
            })
            long_position = None

        # SHORT strategy
        if sell_signal and short_position is None:
            short_position = {'entry_idx': idx, 'entry_price': price, 'entry_ts': ts}
        elif buy_signal and short_position is not None:
            profit = short_position['entry_price'] - price  # Short: profit when price goes down
            profit_pct = (profit / short_position['entry_price']) * 100
            hold_candles = idx - short_position['entry_idx'] if isinstance(idx, int) else 0

            short_trades.append({
                'type': 'SHORT',
                'entry_ts': short_position['entry_ts'],
                'exit_ts': ts,
                'entry_price': short_position['entry_price'],
                'exit_price': price,
                'profit': profit,
                'profit_pct': profit_pct,
                'hold_candles': hold_candles,
            })
            short_position = None

    # Calculate performance metrics
    def calc_performance(trades_list: List[dict], strategy_type: str) -> TradePerformance:
        if not trades_list:
            return TradePerformance(
                strategy_type=strategy_type,
                total_trades=0,
                profitable_trades=0,
                win_rate=0.0,
                total_profit=0.0,
                total_profit_pct=0.0,
                avg_profit_per_trade=0.0,
                avg_profit_pct_per_trade=0.0,
            )

        profits = [t['profit'] for t in trades_list]
        profit_pcts = [t['profit_pct'] for t in trades_list]
        profitable = [t for t in trades_list if t['profit'] > 0]
        hold_candles = [t['hold_candles'] for t in trades_list]

        # Consecutive wins/losses
        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0

        for t in trades_list:
            if t['profit'] > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)

        return TradePerformance(
            strategy_type=strategy_type,
            total_trades=len(trades_list),
            profitable_trades=len(profitable),
            win_rate=(len(profitable) / len(trades_list)) * 100,
            total_profit=sum(profits),
            total_profit_pct=sum(profit_pcts),
            avg_profit_per_trade=np.mean(profits),
            avg_profit_pct_per_trade=np.mean(profit_pcts),
            max_consecutive_wins=max_wins,
            max_consecutive_losses=max_losses,
            avg_hold_time_candles=np.mean(hold_candles) if hold_candles else 0.0,
        )

    long_perf = calc_performance(long_trades, 'LONG')
    short_perf = calc_performance(short_trades, 'SHORT')

    # Combined
    all_trades = long_trades + short_trades
    all_trades.sort(key=lambda x: str(x['entry_ts']))
    combined_perf = calc_performance(all_trades, 'COMBINED')

    return long_perf, short_perf, combined_perf, all_trades


def calculate_equity_curve(
    trades: List[dict],
    initial_capital: float = 10000.0,
    position_size_pct: float = 10.0,
) -> Tuple[List[float], List[str], DrawdownMetrics]:
    """
    Calculate equity curve from trades with position sizing.

    Returns: (equity_values, timestamps, drawdown_metrics)
    """
    if not trades:
        return [initial_capital], ['start'], DrawdownMetrics(
            max_drawdown_pct=0.0,
            max_drawdown_value=0.0,
            avg_drawdown_pct=0.0,
            current_drawdown_pct=0.0,
            num_drawdown_periods=0,
            longest_drawdown_candles=0,
        )

    equity = [initial_capital]
    timestamps = ['start']

    for trade in trades:
        current_equity = equity[-1]
        position_size = current_equity * (position_size_pct / 100.0)

        # Calculate PnL based on position size
        pnl_pct = trade['profit_pct'] / 100.0
        pnl = position_size * pnl_pct

        new_equity = current_equity + pnl
        equity.append(new_equity)
        timestamps.append(str(trade['exit_ts']))

    # Calculate drawdown
    equity_arr = np.array(equity)
    running_max = np.maximum.accumulate(equity_arr)
    drawdown = equity_arr - running_max
    drawdown_pct = np.where(running_max != 0, (drawdown / running_max) * 100, 0)

    # Find drawdown periods
    in_drawdown = drawdown_pct < -0.01
    dd_starts = np.where(np.diff(in_drawdown.astype(int)) == 1)[0]
    dd_ends = np.where(np.diff(in_drawdown.astype(int)) == -1)[0]

    longest_dd = 0
    if len(dd_starts) > 0 and len(dd_ends) > 0:
        for start, end in zip(dd_starts, dd_ends[:len(dd_starts)]):
            longest_dd = max(longest_dd, end - start)

    dd_metrics = DrawdownMetrics(
        max_drawdown_pct=float(np.min(drawdown_pct)),
        max_drawdown_value=float(np.min(drawdown)),
        avg_drawdown_pct=float(np.mean(drawdown_pct[drawdown_pct < 0])) if np.any(drawdown_pct < 0) else 0.0,
        current_drawdown_pct=float(drawdown_pct[-1]),
        num_drawdown_periods=len(dd_starts),
        longest_drawdown_candles=longest_dd,
    )

    return equity, timestamps, dd_metrics


def calculate_risk_metrics(trades: List[dict]) -> Tuple[float, float, float]:
    """
    Calculate Sharpe, Sortino, and Profit Factor.

    Returns: (sharpe, sortino, profit_factor)
    """
    if not trades:
        return 0.0, 0.0, 0.0

    returns = np.array([t['profit_pct'] for t in trades])

    # Sharpe (simplified - per trade, not annualized)
    mean_return = np.mean(returns)
    std_return = np.std(returns, ddof=1) if len(returns) > 1 else 1.0
    sharpe = mean_return / std_return if std_return > 0 else 0.0

    # Sortino (downside deviation)
    negative_returns = returns[returns < 0]
    downside_std = np.std(negative_returns, ddof=1) if len(negative_returns) > 1 else 1.0
    sortino = mean_return / downside_std if downside_std > 0 else 0.0

    # Profit Factor
    gross_profit = np.sum(returns[returns > 0])
    gross_loss = abs(np.sum(returns[returns <= 0]))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    return float(sharpe), float(sortino), float(profit_factor)


# =============================================================================
# WALK-FORWARD VALIDATION
# =============================================================================

def walk_forward_validation(
    df: pd.DataFrame,
    n_folds: int = 5,
    train_ratio: float = 0.7,
) -> List[WalkForwardResult]:
    """
    Perform walk-forward validation to detect overfitting.

    Splits data into n_folds and tests each fold on out-of-sample data.
    """
    results = []

    total_rows = len(df)
    fold_size = total_rows // n_folds

    if fold_size < 100:
        print(f"Warning: Fold size too small ({fold_size}). Need more data for walk-forward.")
        return results

    for fold in range(n_folds):
        # Define train and test ranges
        fold_start = fold * fold_size
        fold_end = (fold + 1) * fold_size if fold < n_folds - 1 else total_rows

        train_size = int((fold_end - fold_start) * train_ratio)

        train_start = fold_start
        train_end = fold_start + train_size
        test_start = train_end
        test_end = fold_end

        if test_end - test_start < 50:
            continue

        train_df = df.iloc[train_start:train_end].reset_index(drop=True)
        test_df = df.iloc[test_start:test_end].reset_index(drop=True)

        # Simulate on both
        _, _, train_perf, _ = simulate_trades(train_df)
        _, _, test_perf, _ = simulate_trades(test_df)

        # Calculate degradation
        if train_perf.win_rate > 0:
            degradation = ((train_perf.win_rate - test_perf.win_rate) / train_perf.win_rate) * 100
        else:
            degradation = 0.0

        # Get timestamps
        train_start_ts = str(train_df['timestamp'].iloc[0]) if 'timestamp' in train_df else str(train_start)
        train_end_ts = str(train_df['timestamp'].iloc[-1]) if 'timestamp' in train_df else str(train_end)
        test_start_ts = str(test_df['timestamp'].iloc[0]) if 'timestamp' in test_df else str(test_start)
        test_end_ts = str(test_df['timestamp'].iloc[-1]) if 'timestamp' in test_df else str(test_end)

        results.append(WalkForwardResult(
            fold=fold + 1,
            train_start=train_start_ts[:19] if len(train_start_ts) > 19 else train_start_ts,
            train_end=train_end_ts[:19] if len(train_end_ts) > 19 else train_end_ts,
            test_start=test_start_ts[:19] if len(test_start_ts) > 19 else test_start_ts,
            test_end=test_end_ts[:19] if len(test_end_ts) > 19 else test_end_ts,
            train_win_rate=train_perf.win_rate,
            test_win_rate=test_perf.win_rate,
            train_profit_pct=train_perf.total_profit_pct,
            test_profit_pct=test_perf.total_profit_pct,
            degradation_pct=degradation,
        ))

    return results


# =============================================================================
# WARNINGS & ANOMALY DETECTION
# =============================================================================

def detect_warnings(report: AnalysisReport) -> List[str]:
    """Detect potential issues and generate warnings"""
    warnings = []

    # Model warnings
    for model in report.model_metrics:
        warnings.extend(model.get_warnings())

    # Check for train/val AUC gap (overfitting)
    lgbm_models = [m for m in report.model_metrics if 'lgbm' in m.model_name.lower()]
    lc_models = [m for m in report.model_metrics if 'lc' in m.model_name.lower()]

    for lgbm in lgbm_models:
        # Find corresponding lc model
        label = lgbm.model_name.replace('_lgbm', '')
        lc = next((m for m in lc_models if m.model_name.replace('_lc', '') == label), None)
        if lc and (lgbm.auc - lc.auc) > 0.3:
            warnings.append(f"Large AUC gap between LGBM ({lgbm.auc:.3f}) and LC ({lc.auc:.3f}) for {label} - possible overfitting")

    # Trade performance warnings
    if report.combined_performance:
        perf = report.combined_performance
        if perf.total_trades < 100:
            warnings.append(f"Low trade count ({perf.total_trades}) - results may not be statistically significant")
        if perf.win_rate > 80:
            warnings.append(f"Suspiciously high win rate ({perf.win_rate:.1f}%) - check for look-ahead bias")
        if perf.win_rate < 40:
            warnings.append(f"Low win rate ({perf.win_rate:.1f}%) - strategy may not be profitable after fees")
        if perf.max_consecutive_losses > 10:
            warnings.append(f"High consecutive losses ({perf.max_consecutive_losses}) - risk of ruin")

    # Drawdown warnings
    if report.drawdown:
        dd = report.drawdown
        if dd.max_drawdown_pct < -30:
            warnings.append(f"Severe max drawdown ({dd.max_drawdown_pct:.1f}%) - unacceptable risk")
        elif dd.max_drawdown_pct < -20:
            warnings.append(f"High max drawdown ({dd.max_drawdown_pct:.1f}%) - consider reducing position size")

    # Walk-forward warnings
    if report.walk_forward_results:
        avg_degradation = np.mean([r.degradation_pct for r in report.walk_forward_results])
        if avg_degradation > 30:
            warnings.append(f"High walk-forward degradation ({avg_degradation:.1f}%) - likely overfitting!")
        elif avg_degradation > 15:
            warnings.append(f"Moderate walk-forward degradation ({avg_degradation:.1f}%) - caution advised")

        # Check for negative test performance
        negative_folds = [r for r in report.walk_forward_results if r.test_profit_pct < 0]
        if len(negative_folds) > len(report.walk_forward_results) / 2:
            warnings.append(f"Majority of walk-forward folds ({len(negative_folds)}/{len(report.walk_forward_results)}) show losses")

    # Risk metrics warnings
    if report.sharpe_ratio < 0.5:
        warnings.append(f"Low Sharpe ratio ({report.sharpe_ratio:.2f}) - poor risk-adjusted returns")
    if report.profit_factor < 1.5:
        warnings.append(f"Low profit factor ({report.profit_factor:.2f}) - thin margin over losses")

    return warnings


# =============================================================================
# REPORT GENERATION
# =============================================================================

def generate_markdown_report(report: AnalysisReport) -> str:
    """Generate comprehensive Markdown report"""

    md = f"""# Pipeline Analysis Report

**Symbol:** `{report.symbol}`
**Strategy:** `{report.strategy}`
**Timeframe:** `{report.freq}`
**Generated:** {report.timestamp}
**Data Period:** {report.data_period}
**Total Candles:** {report.total_candles:,}

---

## Model Metrics

| Model | AUC | Precision | Recall | F1 | AP | Status |
|-------|-----|-----------|--------|----|----|--------|
"""

    for m in report.model_metrics:
        status = "OK" if m.is_good() else "WARN"
        md += f"| {m.model_name} | {m.auc:.3f} | {m.precision:.3f} | {m.recall:.3f} | {m.f1:.3f} | {m.ap:.3f} | {status} |\n"

    md += "\n---\n\n## Best Threshold Combination\n\n"

    if report.best_threshold:
        bt = report.best_threshold
        md += f"""| Parameter | Value |
|-----------|-------|
| **Buy Threshold** | {bt.buy_threshold} |
| **Sell Threshold** | {bt.sell_threshold} |
| **Total Trades** | {bt.transactions:,} |
| **Win Rate** | {bt.profitable_pct:.1f}% |
| **Total Profit** | ${bt.profit:,.2f} |
| **Profit %** | {bt.profit_pct:.1f}% |
| **Avg Profit/Trade** | ${bt.profit_per_trade:.2f} ({bt.profit_pct_per_trade:.2f}%) |

"""

    md += "\n### Top 5 Threshold Combinations\n\n"
    md += "| Buy | Sell | Trades | Win% | Profit% | Profit/T |\n"
    md += "|-----|------|--------|------|---------|----------|\n"

    for tr in report.threshold_results[:5]:
        md += f"| {tr.buy_threshold} | {tr.sell_threshold} | {tr.transactions} | {tr.profitable_pct:.1f}% | {tr.profit_pct:.1f}% | {tr.profit_pct_per_trade:.2f}% |\n"

    md += "\n---\n\n## Trade Performance\n\n"

    md += "| Strategy | Trades | Wins | Win Rate | Total Profit % | Avg/Trade | Max Wins | Max Losses |\n"
    md += "|----------|--------|------|----------|----------------|-----------|----------|------------|\n"

    for perf in [report.long_performance, report.short_performance, report.combined_performance]:
        if perf:
            md += f"| **{perf.strategy_type}** | {perf.total_trades} | {perf.profitable_trades} | {perf.win_rate:.1f}% | {perf.total_profit_pct:.1f}% | {perf.avg_profit_pct_per_trade:.2f}% | {perf.max_consecutive_wins} | {perf.max_consecutive_losses} |\n"

    md += "\n---\n\n## Risk Metrics\n\n"

    md += f"""| Metric | Value | Status |
|--------|-------|--------|
| **Sharpe Ratio** | {report.sharpe_ratio:.2f} | {'OK' if report.sharpe_ratio > 1 else 'WARN' if report.sharpe_ratio > 0.5 else 'BAD'} |
| **Sortino Ratio** | {report.sortino_ratio:.2f} | {'OK' if report.sortino_ratio > 1.5 else 'WARN'} |
| **Profit Factor** | {report.profit_factor:.2f} | {'OK' if report.profit_factor > 2 else 'WARN' if report.profit_factor > 1.5 else 'BAD'} |

"""

    if report.drawdown:
        dd = report.drawdown
        md += f"""### Drawdown Analysis

| Metric | Value |
|--------|-------|
| **Max Drawdown** | {dd.max_drawdown_pct:.2f}% (${dd.max_drawdown_value:,.2f}) |
| **Avg Drawdown** | {dd.avg_drawdown_pct:.2f}% |
| **Current Drawdown** | {dd.current_drawdown_pct:.2f}% |
| **Drawdown Periods** | {dd.num_drawdown_periods} |
| **Longest DD** | {dd.longest_drawdown_candles} candles |

"""

    if report.walk_forward_results:
        md += "\n---\n\n## Walk-Forward Validation\n\n"
        md += "| Fold | Train Period | Test Period | Train Win% | Test Win% | Train Profit% | Test Profit% | Degradation |\n"
        md += "|------|--------------|-------------|------------|-----------|---------------|--------------|-------------|\n"

        for wf in report.walk_forward_results:
            deg_status = "" if wf.degradation_pct < 15 else "" if wf.degradation_pct < 30 else ""
            md += f"| {wf.fold} | {wf.train_start[:10]}..{wf.train_end[:10]} | {wf.test_start[:10]}..{wf.test_end[:10]} | {wf.train_win_rate:.1f}% | {wf.test_win_rate:.1f}% | {wf.train_profit_pct:.1f}% | {wf.test_profit_pct:.1f}% | {wf.degradation_pct:.1f}% {deg_status} |\n"

        md += f"\n**Average Degradation:** {report.walk_forward_avg_degradation:.1f}%\n"

    if report.warnings:
        md += "\n---\n\n## Warnings\n\n"
        for w in report.warnings:
            md += f"- {w}\n"
    else:
        md += "\n---\n\n## Warnings\n\nNo warnings detected.\n"

    md += f"""
---

## Summary

"""

    if report.combined_performance:
        perf = report.combined_performance
        verdict = "PROFITABLE" if perf.total_profit_pct > 0 and perf.win_rate > 50 else "MARGINAL" if perf.total_profit_pct > 0 else "UNPROFITABLE"

        md += f"""**Overall Verdict:** **{verdict}**

- Total return: **{perf.total_profit_pct:.1f}%** over {perf.total_trades} trades
- Win rate: **{perf.win_rate:.1f}%**
- Risk-adjusted: Sharpe {report.sharpe_ratio:.2f}, Sortino {report.sortino_ratio:.2f}
- Max drawdown: **{report.drawdown.max_drawdown_pct:.1f}%** (if applicable)
- Walk-forward stability: {report.walk_forward_avg_degradation:.1f}% degradation

"""

    md += """
---

*Generated by ITB Pipeline Analyzer*
"""

    return md


def plot_equity_curve(
    equity: List[float],
    timestamps: List[str],
    output_path: Path,
    title: str = "Equity Curve",
):
    """Generate equity curve chart"""
    if not HAS_MATPLOTLIB:
        print("Skipping chart generation (matplotlib not installed)")
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]})

    # Equity curve
    ax1.plot(equity, 'b-', linewidth=1.5, label='Equity')
    ax1.fill_between(range(len(equity)), equity[0], equity, alpha=0.3)
    ax1.axhline(y=equity[0], color='gray', linestyle='--', alpha=0.5, label='Initial Capital')
    ax1.set_title(title, fontsize=14, fontweight='bold')
    ax1.set_ylabel('Equity ($)')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)

    # Drawdown
    equity_arr = np.array(equity)
    running_max = np.maximum.accumulate(equity_arr)
    drawdown_pct = np.where(running_max != 0, ((equity_arr - running_max) / running_max) * 100, 0)

    ax2.fill_between(range(len(drawdown_pct)), 0, drawdown_pct, color='red', alpha=0.5)
    ax2.set_ylabel('Drawdown (%)')
    ax2.set_xlabel('Trade #')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"Equity curve saved: {output_path}")


# =============================================================================
# MAIN ANALYZER
# =============================================================================

def analyze_pipeline(
    data_dir: Path,
    strategy: str,
    run_walk_forward: bool = True,
    walk_forward_folds: int = 5,
) -> AnalysisReport:
    """
    Main analysis function.

    Args:
        data_dir: Path to DATA_ITB_{freq}/{symbol}/ directory
        strategy: Strategy name (conservative, aggressive, quick_profit)
        run_walk_forward: Whether to run walk-forward validation
        walk_forward_folds: Number of folds for walk-forward

    Returns:
        AnalysisReport with all metrics
    """

    # Detect symbol and freq from path
    symbol = data_dir.name if data_dir.name.isupper() else "UNKNOWN"
    freq = data_dir.parent.name.split('_')[-1] if 'ITB' in data_dir.parent.name else "5m"

    # If data_dir is DATA_ITB_5m, look for symbol subdirectory
    if 'ITB' in data_dir.name:
        # User passed DATA_ITB_5m, need to find symbol
        symbols = [d for d in data_dir.iterdir() if d.is_dir() and d.name.isupper()]
        if symbols:
            data_dir = symbols[0]
            symbol = data_dir.name
        freq = data_dir.parent.name.split('_')[-1]

    print(f"\nAnalyzing: {symbol} / {strategy} / {freq}")
    print(f"Data directory: {data_dir}")

    # File paths
    predictions_file = data_dir / f"predictions_{strategy}.txt"
    signal_models_file = data_dir / f"signal_models_{strategy}.txt"
    features_file = data_dir / f"features_{strategy}.txt"
    labels_file = data_dir / f"matrix_{strategy}.labels.txt"
    signals_file = data_dir / f"signals_{strategy}.csv"

    # Initialize report
    report = AnalysisReport(
        symbol=symbol,
        strategy=strategy,
        freq=freq,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        data_period="",
        total_candles=0,
    )

    # Parse model metrics
    print("  Parsing model metrics...")
    report.model_metrics = parse_predictions_txt(predictions_file)

    # Parse threshold results
    print("  Parsing threshold grid search...")
    report.threshold_results = parse_signal_models_txt(signal_models_file)
    if report.threshold_results:
        # Best is first (sorted by profit)
        report.best_threshold = report.threshold_results[0]

    # Load signals CSV
    if signals_file.exists():
        print("  Loading signals CSV...")
        df = pd.read_csv(signals_file)
        report.total_candles = len(df)

        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            report.data_period = f"{df['timestamp'].min()} to {df['timestamp'].max()}"

        # Simulate trades
        print("  Simulating trades...")
        long_perf, short_perf, combined_perf, trades = simulate_trades(df)
        report.long_performance = long_perf
        report.short_performance = short_perf
        report.combined_performance = combined_perf

        # Equity curve
        print("  Calculating equity curve...")
        equity, timestamps, drawdown = calculate_equity_curve(trades)
        report.equity_curve = equity
        report.equity_timestamps = timestamps
        report.drawdown = drawdown

        # Risk metrics
        print("  Calculating risk metrics...")
        sharpe, sortino, pf = calculate_risk_metrics(trades)
        report.sharpe_ratio = sharpe
        report.sortino_ratio = sortino
        report.profit_factor = pf

        # Walk-forward validation
        if run_walk_forward and len(df) > 1000:
            print(f"  Running walk-forward validation ({walk_forward_folds} folds)...")
            report.walk_forward_results = walk_forward_validation(df, n_folds=walk_forward_folds)
            if report.walk_forward_results:
                report.walk_forward_avg_degradation = np.mean([r.degradation_pct for r in report.walk_forward_results])
    else:
        print(f"  Warning: signals file not found: {signals_file}")

    # Detect warnings
    print("  Detecting warnings...")
    report.warnings = detect_warnings(report)

    return report


def compare_strategies(
    data_dir: Path,
    strategies: List[str],
) -> str:
    """Compare multiple strategies and generate comparison report"""

    reports = []
    for strategy in strategies:
        try:
            report = analyze_pipeline(data_dir, strategy, run_walk_forward=False)
            reports.append(report)
        except Exception as e:
            print(f"Error analyzing {strategy}: {e}")

    if not reports:
        return "No strategies could be analyzed."

    md = f"""# Strategy Comparison Report

**Symbol:** `{reports[0].symbol}`
**Timeframe:** `{reports[0].freq}`
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## Performance Comparison

| Strategy | Trades | Win Rate | Profit % | Sharpe | Max DD | Profit Factor |
|----------|--------|----------|----------|--------|--------|---------------|
"""

    for r in reports:
        if r.combined_performance:
            p = r.combined_performance
            dd = r.drawdown.max_drawdown_pct if r.drawdown else 0
            md += f"| **{r.strategy}** | {p.total_trades} | {p.win_rate:.1f}% | {p.total_profit_pct:.1f}% | {r.sharpe_ratio:.2f} | {dd:.1f}% | {r.profit_factor:.2f} |\n"

    md += "\n---\n\n## Model Quality Comparison\n\n"
    md += "| Strategy | Best Model | AUC | Precision |\n"
    md += "|----------|------------|-----|----------|\n"

    for r in reports:
        if r.model_metrics:
            best = max(r.model_metrics, key=lambda m: m.auc)
            md += f"| **{r.strategy}** | {best.model_name} | {best.auc:.3f} | {best.precision:.3f} |\n"

    md += "\n---\n\n## Best Thresholds\n\n"
    md += "| Strategy | Buy Threshold | Sell Threshold | Profit/Trade |\n"
    md += "|----------|---------------|----------------|-------------|\n"

    for r in reports:
        if r.best_threshold:
            bt = r.best_threshold
            md += f"| **{r.strategy}** | {bt.buy_threshold} | {bt.sell_threshold} | {bt.profit_pct_per_trade:.2f}% |\n"

    # Recommendation
    best_report = max(reports, key=lambda r: r.sharpe_ratio if r.sharpe_ratio else 0)

    md += f"""
---

## Recommendation

Based on risk-adjusted returns (Sharpe ratio), **{best_report.strategy}** appears to be the best strategy.

| Winner | Sharpe | Win Rate | Max DD |
|--------|--------|----------|--------|
| **{best_report.strategy}** | {best_report.sharpe_ratio:.2f} | {best_report.combined_performance.win_rate:.1f}% | {best_report.drawdown.max_drawdown_pct:.1f}% |

---

*Generated by ITB Pipeline Analyzer*
"""

    return md


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Unified Pipeline Analyzer - Generate comprehensive analysis reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Analyze single strategy
    python tools/analyze_pipeline.py --data-dir DATA_ITB_5m/BTCUSDT --strategy conservative

    # Compare multiple strategies
    python tools/analyze_pipeline.py --data-dir DATA_ITB_5m/BTCUSDT --compare conservative aggressive quick_profit

    # Skip walk-forward validation
    python tools/analyze_pipeline.py --data-dir DATA_ITB_5m/BTCUSDT --strategy conservative --no-walk-forward
        """
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        default="DATA_ITB_5m/BTCUSDT",
        help="Path to data directory (e.g., DATA_ITB_5m/BTCUSDT)",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default="conservative",
        help="Strategy name (conservative, aggressive, quick_profit)",
    )
    parser.add_argument(
        "--compare",
        nargs="+",
        help="Compare multiple strategies (e.g., --compare conservative aggressive)",
    )
    parser.add_argument(
        "--no-walk-forward",
        action="store_true",
        help="Skip walk-forward validation",
    )
    parser.add_argument(
        "--walk-forward-folds",
        type=int,
        default=5,
        help="Number of folds for walk-forward validation (default: 5)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="reports",
        help="Output directory for reports (default: reports)",
    )

    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not data_dir.exists():
        print(f"Error: Data directory not found: {data_dir}")
        sys.exit(1)

    print("=" * 70)
    print("ITB PIPELINE ANALYZER")
    print("=" * 70)

    if args.compare:
        # Compare multiple strategies
        print(f"\nComparing strategies: {', '.join(args.compare)}")

        comparison_md = compare_strategies(data_dir, args.compare)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        symbol = data_dir.name if data_dir.name.isupper() else "multi"

        # Save comparison report
        report_path = output_dir / f"comparison_{symbol}_{ts}.md"
        report_path.write_text(comparison_md)
        print(f"\nComparison report: {report_path}")

        # Print to console
        print("\n" + comparison_md)

    else:
        # Single strategy analysis
        report = analyze_pipeline(
            data_dir,
            args.strategy,
            run_walk_forward=not args.no_walk_forward,
            walk_forward_folds=args.walk_forward_folds,
        )

        # Generate outputs
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{report.symbol}_{report.strategy}_{ts}"

        # Markdown report
        md_report = generate_markdown_report(report)
        report_path = output_dir / f"analysis_{base_name}.md"
        report_path.write_text(md_report)
        print(f"\nMarkdown report: {report_path}")

        # JSON metrics
        json_path = output_dir / f"metrics_{base_name}.json"
        with open(json_path, 'w') as f:
            json.dump(asdict(report), f, indent=2, default=str)
        print(f"JSON metrics: {json_path}")

        # Equity curve chart
        if report.equity_curve and len(report.equity_curve) > 1:
            chart_path = output_dir / f"equity_{base_name}.png"
            plot_equity_curve(
                report.equity_curve,
                report.equity_timestamps,
                chart_path,
                title=f"Equity Curve - {report.symbol} / {report.strategy}",
            )

        # Print summary to console
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)

        if report.combined_performance:
            p = report.combined_performance
            print(f"Symbol:     {report.symbol}")
            print(f"Strategy:   {report.strategy}")
            print(f"Timeframe:  {report.freq}")
            print(f"Candles:    {report.total_candles:,}")
            print(f"")
            print(f"Total Trades:     {p.total_trades}")
            print(f"Win Rate:         {p.win_rate:.1f}%")
            print(f"Total Profit:     {p.total_profit_pct:.1f}%")
            print(f"Sharpe Ratio:     {report.sharpe_ratio:.2f}")
            print(f"Profit Factor:    {report.profit_factor:.2f}")

            if report.drawdown:
                print(f"Max Drawdown:     {report.drawdown.max_drawdown_pct:.1f}%")

            if report.walk_forward_results:
                print(f"WF Degradation:   {report.walk_forward_avg_degradation:.1f}%")

        if report.warnings:
            print(f"\nWarnings ({len(report.warnings)}):")
            for w in report.warnings[:5]:
                print(f"  - {w}")
            if len(report.warnings) > 5:
                print(f"  ... and {len(report.warnings) - 5} more")

        print("=" * 70)


if __name__ == "__main__":
    main()
