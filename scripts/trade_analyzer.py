#!/usr/bin/env python3
"""
Trade Analyzer - Analyzes trade logs to improve strategy

This script analyzes the trade history to:
1. Calculate performance metrics (win rate, avg PnL, Sharpe ratio)
2. Identify patterns in winning vs losing trades
3. Analyze signal quality (which scores lead to profits)
4. Generate insights for model improvement
5. Create reports for strategy optimization
"""

import os
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
import pandas as pd
import numpy as np

# Paths
BASE_DIR = Path(__file__).parent.parent
LOGS_DIR = BASE_DIR / "logs" / "trades"
TRADES_LOG = LOGS_DIR / "trades_history.jsonl"
POSITIONS_LOG = LOGS_DIR / "positions_snapshots.jsonl"
PERFORMANCE_LOG = LOGS_DIR / "performance_daily.jsonl"
REPORTS_DIR = BASE_DIR / "reports"


class TradeAnalyzer:
    """Analyzes trade history for learning and optimization."""

    def __init__(self):
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def load_trades(self) -> pd.DataFrame:
        """Load trade history from JSONL file."""
        if not TRADES_LOG.exists():
            return pd.DataFrame()

        trades = []
        with open(TRADES_LOG, 'r') as f:
            for line in f:
                trades.append(json.loads(line))

        if not trades:
            return pd.DataFrame()

        df = pd.DataFrame(trades)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df

    def load_snapshots(self) -> pd.DataFrame:
        """Load position snapshots."""
        if not POSITIONS_LOG.exists():
            return pd.DataFrame()

        snapshots = []
        with open(POSITIONS_LOG, 'r') as f:
            for line in f:
                snapshots.append(json.loads(line))

        return pd.DataFrame(snapshots)

    def calculate_trade_metrics(self, trades_df: pd.DataFrame) -> dict:
        """Calculate overall trading metrics."""
        if trades_df.empty:
            return {}

        # Filter closed trades only
        closed = trades_df[trades_df['event_type'] == 'CLOSE'].copy()

        if closed.empty:
            return {'status': 'no_closed_trades'}

        # Basic metrics
        total_trades = len(closed)
        winning_trades = len(closed[closed['realized_pnl'] > 0])
        losing_trades = len(closed[closed['realized_pnl'] < 0])

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        total_pnl = closed['realized_pnl'].sum()
        avg_pnl = closed['realized_pnl'].mean()

        # Winning vs Losing analysis
        wins = closed[closed['realized_pnl'] > 0]['realized_pnl']
        losses = closed[closed['realized_pnl'] < 0]['realized_pnl']

        avg_win = wins.mean() if len(wins) > 0 else 0
        avg_loss = abs(losses.mean()) if len(losses) > 0 else 0

        # Profit factor
        gross_profit = wins.sum() if len(wins) > 0 else 0
        gross_loss = abs(losses.sum()) if len(losses) > 0 else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Risk/Reward ratio
        risk_reward = avg_win / avg_loss if avg_loss > 0 else float('inf')

        # Expectancy (average expected profit per trade)
        expectancy = (win_rate/100 * avg_win) - ((1 - win_rate/100) * avg_loss)

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 2),
            'total_pnl': round(total_pnl, 2),
            'avg_pnl_per_trade': round(avg_pnl, 2),
            'avg_winning_trade': round(avg_win, 2),
            'avg_losing_trade': round(avg_loss, 2),
            'profit_factor': round(profit_factor, 2),
            'risk_reward_ratio': round(risk_reward, 2),
            'expectancy': round(expectancy, 2),
            'largest_win': round(wins.max(), 2) if len(wins) > 0 else 0,
            'largest_loss': round(losses.min(), 2) if len(losses) > 0 else 0,
        }

    def analyze_by_symbol(self, trades_df: pd.DataFrame) -> dict:
        """Analyze performance by symbol."""
        if trades_df.empty:
            return {}

        closed = trades_df[trades_df['event_type'] == 'CLOSE']
        if closed.empty:
            return {}

        results = {}
        for symbol in closed['symbol'].unique():
            symbol_trades = closed[closed['symbol'] == symbol]
            results[symbol] = {
                'trades': len(symbol_trades),
                'total_pnl': round(symbol_trades['realized_pnl'].sum(), 2),
                'win_rate': round(
                    len(symbol_trades[symbol_trades['realized_pnl'] > 0]) / len(symbol_trades) * 100, 2
                ),
                'avg_pnl': round(symbol_trades['realized_pnl'].mean(), 2),
            }

        return results

    def analyze_by_direction(self, trades_df: pd.DataFrame) -> dict:
        """Analyze performance by trade direction (LONG vs SHORT)."""
        if trades_df.empty:
            return {}

        closed = trades_df[trades_df['event_type'] == 'CLOSE']
        if closed.empty or 'direction' not in closed.columns:
            return {}

        results = {}
        for direction in ['LONG', 'SHORT']:
            dir_trades = closed[closed['direction'] == direction]
            if len(dir_trades) == 0:
                continue

            results[direction] = {
                'trades': len(dir_trades),
                'total_pnl': round(dir_trades['realized_pnl'].sum(), 2),
                'win_rate': round(
                    len(dir_trades[dir_trades['realized_pnl'] > 0]) / len(dir_trades) * 100, 2
                ),
                'avg_pnl': round(dir_trades['realized_pnl'].mean(), 2),
            }

        return results

    def analyze_signal_quality(self, trades_df: pd.DataFrame) -> dict:
        """Analyze which signal scores lead to profitable trades."""
        if trades_df.empty:
            return {}

        closed = trades_df[trades_df['event_type'] == 'CLOSE'].copy()
        if closed.empty:
            return {}

        # Extract signal scores
        signal_data = []
        for _, row in closed.iterrows():
            signal_info = row.get('signal_info', {})
            if signal_info and 'trade_score' in signal_info:
                signal_data.append({
                    'trade_score': signal_info['trade_score'],
                    'realized_pnl': row['realized_pnl'],
                    'is_winner': row['realized_pnl'] > 0,
                    'direction': row.get('direction', 'UNKNOWN'),
                })

        if not signal_data:
            return {'status': 'no_signal_data'}

        df = pd.DataFrame(signal_data)

        # Analyze by score ranges
        score_ranges = [
            (-1.0, -0.05, 'strong_short'),
            (-0.05, -0.02, 'weak_short'),
            (-0.02, 0.02, 'neutral'),
            (0.02, 0.05, 'weak_long'),
            (0.05, 1.0, 'strong_long'),
        ]

        results = {}
        for low, high, name in score_ranges:
            range_trades = df[(df['trade_score'] >= low) & (df['trade_score'] < high)]
            if len(range_trades) > 0:
                results[name] = {
                    'score_range': f'[{low}, {high})',
                    'trades': len(range_trades),
                    'win_rate': round(range_trades['is_winner'].mean() * 100, 2),
                    'avg_pnl': round(range_trades['realized_pnl'].mean(), 2),
                    'total_pnl': round(range_trades['realized_pnl'].sum(), 2),
                }

        # Optimal threshold analysis
        if len(df) >= 10:
            # Find score threshold that maximizes win rate
            thresholds = np.arange(-0.1, 0.1, 0.01)
            best_threshold = 0
            best_win_rate = 0

            for t in thresholds:
                above = df[df['trade_score'].abs() >= abs(t)]
                if len(above) > 5:
                    wr = above['is_winner'].mean()
                    if wr > best_win_rate:
                        best_win_rate = wr
                        best_threshold = t

            results['optimal_threshold'] = {
                'threshold': round(abs(best_threshold), 4),
                'expected_win_rate': round(best_win_rate * 100, 2),
            }

        return results

    def analyze_pnl_evolution(self) -> pd.DataFrame:
        """Analyze PnL evolution over time from snapshots."""
        snapshots = self.load_snapshots()
        if snapshots.empty:
            return pd.DataFrame()

        evolution = []
        for _, row in snapshots.iterrows():
            account = row.get('account', {})
            evolution.append({
                'timestamp': row['timestamp'],
                'balance': account.get('total_balance', 0),
                'unrealized_pnl': account.get('unrealized_pnl', 0),
                'positions_count': len(row.get('positions', [])),
            })

        df = pd.DataFrame(evolution)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')

        return df

    def generate_insights(self, trades_df: pd.DataFrame) -> list:
        """Generate actionable insights from trade analysis."""
        insights = []

        metrics = self.calculate_trade_metrics(trades_df)
        if not metrics or metrics.get('status') == 'no_closed_trades':
            insights.append({
                'type': 'info',
                'message': 'No fechado trades ainda. Continue coletando dados.',
            })
            return insights

        # Win rate insights
        if metrics['win_rate'] < 40:
            insights.append({
                'type': 'warning',
                'message': f"Win rate baixo ({metrics['win_rate']}%). Considere aumentar thresholds de sinal.",
                'action': 'Aumentar buy_signal_threshold e sell_signal_threshold',
            })
        elif metrics['win_rate'] > 60:
            insights.append({
                'type': 'success',
                'message': f"Win rate bom ({metrics['win_rate']}%). Estratégia está funcionando.",
            })

        # Risk/Reward insights
        if metrics['risk_reward_ratio'] < 1:
            insights.append({
                'type': 'warning',
                'message': f"Risk/Reward baixo ({metrics['risk_reward_ratio']}). Perdas médias maiores que ganhos.",
                'action': 'Ajustar stop loss mais apertado ou take profit mais largo',
            })

        # Profit factor insights
        if metrics['profit_factor'] < 1:
            insights.append({
                'type': 'critical',
                'message': f"Profit factor < 1 ({metrics['profit_factor']}). Estratégia perdendo dinheiro.",
                'action': 'Revisar estratégia ou pausar trading',
            })
        elif metrics['profit_factor'] > 2:
            insights.append({
                'type': 'success',
                'message': f"Profit factor excelente ({metrics['profit_factor']}). Estratégia lucrativa.",
            })

        # Expectancy insights
        if metrics['expectancy'] < 0:
            insights.append({
                'type': 'critical',
                'message': f"Expectancy negativa ({metrics['expectancy']}). Cada trade perde dinheiro em média.",
            })
        else:
            insights.append({
                'type': 'info',
                'message': f"Expectancy positiva ({metrics['expectancy']}). Ganho esperado por trade.",
            })

        # Direction analysis
        by_direction = self.analyze_by_direction(trades_df)
        if by_direction:
            for direction, stats in by_direction.items():
                if stats['win_rate'] < 40:
                    insights.append({
                        'type': 'warning',
                        'message': f"{direction} trades com baixa performance ({stats['win_rate']}% win rate).",
                        'action': f'Considere desabilitar {direction} temporariamente',
                    })

        # Signal quality analysis
        signal_analysis = self.analyze_signal_quality(trades_df)
        if 'optimal_threshold' in signal_analysis:
            opt = signal_analysis['optimal_threshold']
            insights.append({
                'type': 'recommendation',
                'message': f"Threshold ótimo sugerido: {opt['threshold']} (win rate esperado: {opt['expected_win_rate']}%)",
                'action': 'Atualizar thresholds na configuração',
            })

        return insights

    def generate_report(self, output_format: str = 'markdown') -> str:
        """Generate a comprehensive analysis report."""
        trades_df = self.load_trades()

        report_lines = []
        report_lines.append(f"# Trade Analysis Report")
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")

        # Overall metrics
        report_lines.append("## Overall Performance")
        metrics = self.calculate_trade_metrics(trades_df)
        if metrics and 'total_trades' in metrics:
            report_lines.append(f"- **Total Trades:** {metrics['total_trades']}")
            report_lines.append(f"- **Win Rate:** {metrics['win_rate']}%")
            report_lines.append(f"- **Total PnL:** ${metrics['total_pnl']}")
            report_lines.append(f"- **Avg PnL/Trade:** ${metrics['avg_pnl_per_trade']}")
            report_lines.append(f"- **Profit Factor:** {metrics['profit_factor']}")
            report_lines.append(f"- **Risk/Reward:** {metrics['risk_reward_ratio']}")
            report_lines.append(f"- **Expectancy:** ${metrics['expectancy']}")
        else:
            report_lines.append("No closed trades yet.")
        report_lines.append("")

        # By Symbol
        report_lines.append("## Performance by Symbol")
        by_symbol = self.analyze_by_symbol(trades_df)
        if by_symbol:
            for symbol, stats in by_symbol.items():
                report_lines.append(f"### {symbol}")
                report_lines.append(f"- Trades: {stats['trades']}")
                report_lines.append(f"- Total PnL: ${stats['total_pnl']}")
                report_lines.append(f"- Win Rate: {stats['win_rate']}%")
                report_lines.append("")
        else:
            report_lines.append("No data by symbol yet.")
        report_lines.append("")

        # By Direction
        report_lines.append("## Performance by Direction")
        by_direction = self.analyze_by_direction(trades_df)
        if by_direction:
            for direction, stats in by_direction.items():
                report_lines.append(f"### {direction}")
                report_lines.append(f"- Trades: {stats['trades']}")
                report_lines.append(f"- Total PnL: ${stats['total_pnl']}")
                report_lines.append(f"- Win Rate: {stats['win_rate']}%")
                report_lines.append("")
        else:
            report_lines.append("No data by direction yet.")
        report_lines.append("")

        # Signal Quality
        report_lines.append("## Signal Quality Analysis")
        signal_analysis = self.analyze_signal_quality(trades_df)
        if signal_analysis and 'status' not in signal_analysis:
            for range_name, stats in signal_analysis.items():
                if range_name != 'optimal_threshold':
                    report_lines.append(f"### {range_name} ({stats['score_range']})")
                    report_lines.append(f"- Trades: {stats['trades']}")
                    report_lines.append(f"- Win Rate: {stats['win_rate']}%")
                    report_lines.append(f"- Avg PnL: ${stats['avg_pnl']}")
                    report_lines.append("")

            if 'optimal_threshold' in signal_analysis:
                opt = signal_analysis['optimal_threshold']
                report_lines.append(f"**Optimal Threshold:** {opt['threshold']} (expected {opt['expected_win_rate']}% win rate)")
        else:
            report_lines.append("No signal data yet.")
        report_lines.append("")

        # Insights
        report_lines.append("## Insights & Recommendations")
        insights = self.generate_insights(trades_df)
        for insight in insights:
            icon = {'success': '✅', 'warning': '⚠️', 'critical': '🔴', 'info': 'ℹ️', 'recommendation': '💡'}.get(insight['type'], '•')
            report_lines.append(f"{icon} {insight['message']}")
            if 'action' in insight:
                report_lines.append(f"   → Action: {insight['action']}")
        report_lines.append("")

        report = '\n'.join(report_lines)

        # Save report
        report_file = REPORTS_DIR / f"trade_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_file, 'w') as f:
            f.write(report)

        print(f"Report saved to: {report_file}")

        return report


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Trade Analyzer')
    parser.add_argument('--report', action='store_true', help='Generate full report')
    parser.add_argument('--metrics', action='store_true', help='Show metrics only')
    parser.add_argument('--insights', action='store_true', help='Show insights only')

    args = parser.parse_args()

    analyzer = TradeAnalyzer()

    if args.metrics:
        trades = analyzer.load_trades()
        metrics = analyzer.calculate_trade_metrics(trades)
        print(json.dumps(metrics, indent=2))
    elif args.insights:
        trades = analyzer.load_trades()
        insights = analyzer.generate_insights(trades)
        for i in insights:
            print(f"[{i['type'].upper()}] {i['message']}")
            if 'action' in i:
                print(f"  → {i['action']}")
    else:
        # Default: generate report
        report = analyzer.generate_report()
        print(report)


if __name__ == '__main__':
    main()
