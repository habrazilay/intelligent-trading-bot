#!/usr/bin/env python3
"""
ML Strategy Backtest Runner

Treina modelo LightGBM e roda backtest com estratégia ML.
Muito mais sofisticado que a estratégia simples.

Usage:
    python run_ml_backtest.py --train-days 180 --test-days 30
    python run_ml_backtest.py --train-days 365 --test-days 90 --up-threshold 0.5
"""

import sys
from pathlib import Path
from datetime import datetime
import json

import click
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from backtest.ml_strategy import MLStrategy, MLStrategyConfig, run_ml_backtest
from backtest.engine import BacktestEngine, BacktestConfig, GridSearchOptimizer


def load_data(symbol: str, data_folder: str = 'DATA_ITB_1m') -> pd.DataFrame:
    """Carrega dados históricos do Parquet."""
    path = Path(data_folder) / symbol / 'klines.parquet'
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    df = pd.read_parquet(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.set_index('timestamp')
    return df


@click.command()
@click.option('--symbol', '-s', default='BTCUSDT', help='Trading symbol')
@click.option('--train-days', default=180, type=int, help='Days for training')
@click.option('--test-days', default=30, type=int, help='Days for testing')
@click.option('--label-horizon', default=60, type=int, help='Candles to look ahead for labels')
@click.option('--up-threshold', default=0.5, type=float, help='% up for positive label')
@click.option('--down-threshold', default=0.5, type=float, help='% down for negative label')
@click.option('--buy-prob', default=0.60, type=float, help='Min probability for BUY signal')
@click.option('--sell-prob', default=0.60, type=float, help='Min probability for SELL signal')
@click.option('--balance', '-b', default=10000.0, type=float, help='Initial balance')
@click.option('--position-size', default=5.0, type=float, help='Position size %')
@click.option('--stop-loss', default=2.0, type=float, help='Stop loss %')
@click.option('--take-profit', default=3.0, type=float, help='Take profit %')
@click.option('--output', '-out', default=None, help='Output file for results')
def main(
    symbol: str,
    train_days: int,
    test_days: int,
    label_horizon: int,
    up_threshold: float,
    down_threshold: float,
    buy_prob: float,
    sell_prob: float,
    balance: float,
    position_size: float,
    stop_loss: float,
    take_profit: float,
    output: str,
):
    """
    Train ML model and run backtest.

    Examples:
        python run_ml_backtest.py --train-days 180 --test-days 30
        python run_ml_backtest.py --train-days 365 --test-days 90 --position-size 10
    """
    print("=" * 60)
    print("ML STRATEGY BACKTEST")
    print("=" * 60)

    # Load data
    print(f"\nLoading {symbol} data...")
    df = load_data(symbol)
    print(f"Total records: {len(df):,}")

    # ML Strategy config
    ml_config = MLStrategyConfig(
        label_horizon=label_horizon,
        up_threshold=up_threshold,
        down_threshold=down_threshold,
        buy_prob_threshold=buy_prob,
        sell_prob_threshold=sell_prob,
        n_estimators=200,
        learning_rate=0.05,
        max_depth=6,
    )

    print(f"\nML Config:")
    print(f"  label_horizon: {label_horizon} candles")
    print(f"  up_threshold: {up_threshold}%")
    print(f"  down_threshold: {down_threshold}%")
    print(f"  buy_prob_threshold: {buy_prob}")
    print(f"  sell_prob_threshold: {sell_prob}")

    # Run ML backtest
    print("\n" + "-" * 60)
    print("TRAINING MODEL")
    print("-" * 60)

    try:
        df_signals, metrics = run_ml_backtest(
            df,
            train_days=train_days,
            test_days=test_days,
            config=ml_config
        )
    except Exception as e:
        print(f"Error training model: {e}")
        return

    # Print feature importance
    print("\n" + "-" * 60)
    print("TOP FEATURES:")
    print("-" * 60)
    print(metrics['feature_importance'].head(15).to_string())

    # Count signals
    buy_signals = df_signals['buy_signal'].sum()
    sell_signals = df_signals['sell_signal'].sum()
    print(f"\nSignals generated: {buy_signals} BUY, {sell_signals} SELL")

    if buy_signals == 0 and sell_signals == 0:
        print("\n⚠️  No signals generated! Try lowering prob thresholds.")
        return

    # Backtest config
    bt_config = BacktestConfig(
        initial_balance=balance,
        position_size_pct=position_size,
        stop_loss_pct=stop_loss,
        take_profit_pct=take_profit,
        use_stop_loss=stop_loss > 0,
        use_take_profit=take_profit > 0,
    )

    print("\n" + "-" * 60)
    print("BACKTEST CONFIG:")
    print("-" * 60)
    print(f"  Initial balance: ${balance:,.2f}")
    print(f"  Position size: {position_size}%")
    print(f"  Stop loss: {stop_loss}%")
    print(f"  Take profit: {take_profit}%")

    # Run backtest
    print("\n" + "-" * 60)
    print("BACKTEST RESULTS")
    print("-" * 60)

    engine = BacktestEngine(bt_config)
    result = engine.run(df_signals)
    engine.print_summary(result)

    # Additional analysis
    if engine.trades:
        print("\n" + "-" * 60)
        print("TRADE ANALYSIS:")
        print("-" * 60)

        pnls = [t.pnl for t in engine.trades]
        holds = [t.hold_bars for t in engine.trades]

        print(f"  PnL distribution:")
        print(f"    Min:     ${min(pnls):,.2f}")
        print(f"    Max:     ${max(pnls):,.2f}")
        print(f"    Median:  ${np.median(pnls):,.2f}")
        print(f"    Std Dev: ${np.std(pnls):,.2f}")

        print(f"\n  Hold time (bars):")
        print(f"    Min:    {min(holds)}")
        print(f"    Max:    {max(holds)}")
        print(f"    Median: {np.median(holds):.0f}")

        # Exit reason breakdown
        print(f"\n  Exit reasons:")
        reasons = {}
        for t in engine.trades:
            r = t.exit_reason
            if r not in reasons:
                reasons[r] = {'count': 0, 'pnl': 0}
            reasons[r]['count'] += 1
            reasons[r]['pnl'] += t.pnl

        for reason, data in sorted(reasons.items(), key=lambda x: -x[1]['count']):
            count = data['count']
            pnl = data['pnl']
            pct = 100 * count / len(engine.trades)
            print(f"    {reason}: {count} ({pct:.1f}%) | PnL: ${pnl:,.2f}")

    # Save results
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        results = {
            'symbol': symbol,
            'train_days': train_days,
            'test_days': test_days,
            'ml_config': {
                'label_horizon': label_horizon,
                'up_threshold': up_threshold,
                'down_threshold': down_threshold,
                'buy_prob_threshold': buy_prob,
                'sell_prob_threshold': sell_prob,
            },
            'bt_config': {
                'initial_balance': balance,
                'position_size_pct': position_size,
                'stop_loss_pct': stop_loss,
                'take_profit_pct': take_profit,
            },
            'training_metrics': {
                'up_auc_train': metrics['up_auc_train'],
                'up_auc_val': metrics['up_auc_val'],
                'down_auc_train': metrics['down_auc_train'],
                'down_auc_val': metrics['down_auc_val'],
            },
            'backtest_result': result.to_dict(),
        }

        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        print(f"\nResults saved to: {output_path}")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == '__main__':
    main()
