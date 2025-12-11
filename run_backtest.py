#!/usr/bin/env python3
"""
Backtest Runner with Parameter Optimization

Roda backtest com dados históricos e otimiza parâmetros.

Usage:
    python run_backtest.py --days 30 --optimize
    python run_backtest.py --days 365 --symbol BTCUSDT
    python run_backtest.py --start 2024-01-01 --end 2024-12-31
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

import click
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from shadow.simple_features import add_simple_features, generate_signals_simple
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


def filter_data(df: pd.DataFrame, start: str = None, end: str = None, days: int = None) -> pd.DataFrame:
    """Filtra dados por período."""
    if days:
        cutoff = df.index.max() - timedelta(days=days)
        df = df[df.index >= cutoff]
    else:
        if start:
            df = df[df.index >= pd.to_datetime(start)]
        if end:
            df = df[df.index <= pd.to_datetime(end)]

    return df


def generate_signals(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Gera features e sinais com parâmetros específicos."""
    df = add_simple_features(df)
    df = generate_signals_simple(
        df,
        buy_threshold=params.get('buy_threshold', 0.002),
        sell_threshold=params.get('sell_threshold', -0.002),
    )
    return df


def run_single_backtest(
    df: pd.DataFrame,
    buy_threshold: float,
    sell_threshold: float,
    stop_loss_pct: float,
    take_profit_pct: float,
    position_size_pct: float,
    initial_balance: float,
) -> dict:
    """Roda um backtest único e retorna métricas."""
    # Gerar sinais
    df = generate_signals(df, {
        'buy_threshold': buy_threshold,
        'sell_threshold': sell_threshold,
    })

    # Config
    config = BacktestConfig(
        initial_balance=initial_balance,
        position_size_pct=position_size_pct,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        use_stop_loss=stop_loss_pct > 0,
        use_take_profit=take_profit_pct > 0,
    )

    # Rodar
    engine = BacktestEngine(config)
    result = engine.run(df)

    return {
        'engine': engine,
        'result': result,
    }


def run_optimization(
    df: pd.DataFrame,
    initial_balance: float,
    param_grid: dict = None,
) -> tuple:
    """Roda grid search para encontrar melhores parâmetros."""
    if param_grid is None:
        param_grid = {
            'buy_threshold': [0.001, 0.002, 0.003, 0.005],
            'sell_threshold': [-0.001, -0.002, -0.003, -0.005],
            'stop_loss_pct': [1.0, 1.5, 2.0, 3.0],
            'take_profit_pct': [1.5, 2.0, 3.0, 5.0],
        }

    base_config = BacktestConfig(
        initial_balance=initial_balance,
        position_size_pct=2.0,
    )

    optimizer = GridSearchOptimizer(base_config)

    best_params, best_result = optimizer.optimize(
        df,
        param_grid,
        signal_generator=generate_signals,
        metric='sharpe_ratio',
    )

    return best_params, best_result, optimizer


@click.command()
@click.option('--symbol', '-s', default='BTCUSDT', help='Trading symbol')
@click.option('--days', '-d', default=30, type=int, help='Number of days to backtest')
@click.option('--start', default=None, help='Start date (YYYY-MM-DD)')
@click.option('--end', default=None, help='End date (YYYY-MM-DD)')
@click.option('--balance', '-b', default=10000.0, help='Initial balance')
@click.option('--optimize', '-o', is_flag=True, help='Run parameter optimization')
@click.option('--buy-threshold', default=0.002, help='Buy signal threshold')
@click.option('--sell-threshold', default=-0.002, help='Sell signal threshold')
@click.option('--stop-loss', default=2.0, help='Stop loss percent')
@click.option('--take-profit', default=3.0, help='Take profit percent')
@click.option('--position-size', default=2.0, help='Position size percent')
@click.option('--output', '-out', default=None, help='Output file for results (JSON)')
def main(
    symbol: str,
    days: int,
    start: str,
    end: str,
    balance: float,
    optimize: bool,
    buy_threshold: float,
    sell_threshold: float,
    stop_loss: float,
    take_profit: float,
    position_size: float,
    output: str,
):
    """
    Run backtest on historical data.

    Examples:
        python run_backtest.py --days 30
        python run_backtest.py --days 365 --optimize
        python run_backtest.py --start 2024-01-01 --end 2024-06-30
    """
    print("=" * 60)
    print("BACKTEST RUNNER")
    print("=" * 60)

    # Load data
    print(f"\nLoading {symbol} data...")
    df = load_data(symbol)
    print(f"Total records: {len(df):,}")

    # Filter by period
    df = filter_data(df, start=start, end=end, days=days)
    print(f"Filtered records: {len(df):,}")
    print(f"Period: {df.index.min()} to {df.index.max()}")

    if len(df) < 1000:
        print("⚠️  Warning: Less than 1000 candles. Results may not be statistically significant.")

    results = {}

    if optimize:
        print("\n" + "=" * 60)
        print("PARAMETER OPTIMIZATION")
        print("=" * 60)

        best_params, best_result, optimizer = run_optimization(df.copy(), balance)

        print("\n" + "-" * 60)
        print("BEST PARAMETERS:")
        print("-" * 60)
        for k, v in best_params.items():
            print(f"  {k}: {v}")

        print("\n" + "-" * 60)
        print("BEST RESULT:")
        print("-" * 60)

        # Run final backtest with best params
        bt = run_single_backtest(
            df.copy(),
            buy_threshold=best_params.get('buy_threshold', buy_threshold),
            sell_threshold=best_params.get('sell_threshold', sell_threshold),
            stop_loss_pct=best_params.get('stop_loss_pct', stop_loss),
            take_profit_pct=best_params.get('take_profit_pct', take_profit),
            position_size_pct=position_size,
            initial_balance=balance,
        )
        bt['engine'].print_summary(bt['result'])

        results = {
            'mode': 'optimization',
            'symbol': symbol,
            'period_days': days,
            'best_params': best_params,
            'best_result': bt['result'].to_dict(),
            'all_results': optimizer.results,
        }

    else:
        print("\n" + "=" * 60)
        print("SINGLE BACKTEST")
        print("=" * 60)
        print(f"Parameters:")
        print(f"  buy_threshold: {buy_threshold}")
        print(f"  sell_threshold: {sell_threshold}")
        print(f"  stop_loss: {stop_loss}%")
        print(f"  take_profit: {take_profit}%")
        print(f"  position_size: {position_size}%")

        bt = run_single_backtest(
            df.copy(),
            buy_threshold=buy_threshold,
            sell_threshold=sell_threshold,
            stop_loss_pct=stop_loss,
            take_profit_pct=take_profit,
            position_size_pct=position_size,
            initial_balance=balance,
        )
        bt['engine'].print_summary(bt['result'])

        results = {
            'mode': 'single',
            'symbol': symbol,
            'period_days': days,
            'params': {
                'buy_threshold': buy_threshold,
                'sell_threshold': sell_threshold,
                'stop_loss_pct': stop_loss,
                'take_profit_pct': take_profit,
                'position_size_pct': position_size,
            },
            'result': bt['result'].to_dict(),
        }

        # Trade distribution by exit reason
        if bt['engine'].trades:
            print("\nTrade Analysis:")
            print("-" * 40)

            # PnL distribution
            pnls = [t.pnl for t in bt['engine'].trades]
            print(f"  PnL Stats:")
            print(f"    Min:    ${min(pnls):,.2f}")
            print(f"    Max:    ${max(pnls):,.2f}")
            print(f"    Median: ${np.median(pnls):,.2f}")
            print(f"    Std:    ${np.std(pnls):,.2f}")

            # Hold time distribution
            holds = [t.hold_bars for t in bt['engine'].trades]
            print(f"\n  Hold Time (bars):")
            print(f"    Min:    {min(holds)}")
            print(f"    Max:    {max(holds)}")
            print(f"    Median: {np.median(holds):.0f}")

    # Save results
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        print(f"\nResults saved to: {output_path}")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == '__main__':
    main()
