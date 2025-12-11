import numpy as np
import pandas as pd

"""
Backtesting and trade performance using trade simulation
"""

def simulated_trade_performance(df, buy_signal_column, sell_signal_column, price_column):
    """
    Simulates trading by executing buy/sell signals and calculating profit from complete trade pairs.

    LONG strategy: BUY at signal → SELL at signal → profit = sell_price - buy_price
    SHORT strategy: SELL at signal → BUY at signal → profit = sell_price - buy_price

    Returns performance metrics for long and short strategies.
    """
    # LONG strategy state
    long_position = None  # (index, buy_price)
    long_trades = []  # List of completed trades: (buy_idx, buy_price, sell_idx, sell_price, profit, profit_pct)
    long_profit = 0
    long_profit_percent = 0
    long_profitable = 0

    # SHORT strategy state
    short_position = None  # (index, sell_price)
    short_trades = []  # List of completed trades
    short_profit = 0
    short_profit_percent = 0
    short_profitable = 0

    # Process all signals
    df = df[[sell_signal_column, buy_signal_column, price_column]]
    for (index, sell_signal, buy_signal, price) in df.itertuples(name=None):
        if not price or pd.isnull(price):
            continue

        # === LONG STRATEGY: Buy first, then Sell ===
        if buy_signal and long_position is None:
            # Open LONG position
            long_position = (index, price)

        elif sell_signal and long_position is not None:
            # Close LONG position
            buy_idx, buy_price = long_position
            sell_price = price
            profit = sell_price - buy_price
            profit_pct = 100.0 * profit / buy_price

            long_trades.append((buy_idx, buy_price, index, sell_price, profit, profit_pct))
            long_profit += profit
            long_profit_percent += profit_pct
            if profit > 0:
                long_profitable += 1

            long_position = None  # Close position

        # === SHORT STRATEGY: Sell first, then Buy ===
        if sell_signal and short_position is None:
            # Open SHORT position (sell borrowed asset)
            short_position = (index, price)

        elif buy_signal and short_position is not None:
            # Close SHORT position (buy back asset)
            sell_idx, sell_price = short_position
            buy_price = price
            profit = sell_price - buy_price  # Profit from selling high, buying low
            profit_pct = 100.0 * profit / sell_price

            short_trades.append((sell_idx, sell_price, index, buy_price, profit, profit_pct))
            short_profit += profit
            short_profit_percent += profit_pct
            if profit > 0:
                short_profitable += 1

            short_position = None  # Close position

    # Build performance metrics
    long_transactions = len(long_trades)
    long_performance = {
        "#transactions": long_transactions,
        "profit": round(long_profit, 2),
        "%profit": round(long_profit_percent, 1),

        "#profitable": long_profitable,
        "%profitable": round(100.0 * long_profitable / long_transactions, 1) if long_transactions else 0.0,

        "profit/T": round(long_profit / long_transactions, 2) if long_transactions else 0.0,
        "%profit/T": round(long_profit_percent / long_transactions, 1) if long_transactions else 0.0,
    }

    short_transactions = len(short_trades)
    short_performance = {
        "#transactions": short_transactions,
        "profit": round(short_profit, 2),
        "%profit": round(short_profit_percent, 1),

        "#profitable": short_profitable,
        "%profitable": round(100.0 * short_profitable / short_transactions, 1) if short_transactions else 0.0,

        "profit/T": round(short_profit / short_transactions, 2) if short_transactions else 0.0,
        "%profit/T": round(short_profit_percent / short_transactions, 1) if short_transactions else 0.0,
    }

    # Combined performance
    total_profit = long_profit + short_profit
    total_profit_percent = long_profit_percent + short_profit_percent
    total_transactions = long_transactions + short_transactions
    total_profitable = long_profitable + short_profitable

    performance = {
        "#transactions": total_transactions,
        "profit": round(total_profit, 2),
        "%profit": round(total_profit_percent, 1),

        "#profitable": total_profitable,
        "%profitable": round(100.0 * total_profitable / total_transactions, 1) if total_transactions else 0.0,

        "profit/T": round(total_profit / total_transactions, 2) if total_transactions else 0.0,
        "%profit/T": round(total_profit_percent / total_transactions, 1) if total_transactions else 0.0,
    }

    return performance, long_performance, short_performance
