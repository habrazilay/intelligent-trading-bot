#!/usr/bin/env python3
"""
Trade Monitor - Logs all trading activity for ML learning

This script monitors open positions and logs:
- Entry/Exit prices and times
- PnL evolution over time
- Market conditions at trade time
- Signal scores that triggered the trade
- Final outcome (TP hit, SL hit, manual close)

Logs are saved in JSON format for easy analysis and model training.
"""

import os
import json
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import pandas as pd
from dotenv import load_dotenv
from binance.client import Client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
LOGS_DIR = BASE_DIR / "logs" / "trades"
TRADES_LOG = LOGS_DIR / "trades_history.jsonl"
POSITIONS_LOG = LOGS_DIR / "positions_snapshots.jsonl"
PERFORMANCE_LOG = LOGS_DIR / "performance_daily.jsonl"


class TradeMonitor:
    """Monitors and logs all trading activity."""

    def __init__(self, testnet: bool = True):
        load_dotenv(BASE_DIR / '.env.dev')

        if testnet:
            api_key = os.getenv('BINANCE_API_KEY_DEMO')
            api_secret = os.getenv('BINANCE_API_SECRET_DEMO')
        else:
            api_key = os.getenv('BINANCE_API_KEY')
            api_secret = os.getenv('BINANCE_API_SECRET')

        self.client = Client(api_key=api_key, api_secret=api_secret, testnet=testnet)
        self.testnet = testnet
        self.known_positions = {}  # Track position changes

        # Ensure log directory exists
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        log.info(f"Trade Monitor initialized ({'TESTNET' if testnet else 'PRODUCTION'})")

    def get_account_info(self) -> dict:
        """Get current account information."""
        account = self.client.futures_account()
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total_balance': float(account['totalWalletBalance']),
            'available_balance': float(account['availableBalance']),
            'unrealized_pnl': float(account['totalUnrealizedProfit']),
            'margin_balance': float(account['totalMarginBalance']),
        }

    def get_open_positions(self) -> list:
        """Get all open positions with details."""
        account = self.client.futures_account()
        positions = []

        for p in account['positions']:
            amt = float(p['positionAmt'])
            if amt == 0:
                continue

            symbol = p['symbol']
            entry_price = float(p['entryPrice'])

            # Get current price
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])

            # Calculate metrics
            direction = 'LONG' if amt > 0 else 'SHORT'
            pnl = float(p['unrealizedProfit'])
            pnl_pct = (pnl / (abs(amt) * entry_price)) * 100 if entry_price > 0 else 0

            # Price change from entry
            if direction == 'LONG':
                price_change_pct = ((current_price - entry_price) / entry_price) * 100
            else:
                price_change_pct = ((entry_price - current_price) / entry_price) * 100

            positions.append({
                'symbol': symbol,
                'direction': direction,
                'quantity': abs(amt),
                'entry_price': entry_price,
                'current_price': current_price,
                'unrealized_pnl': pnl,
                'pnl_percent': round(pnl_pct, 2),
                'price_change_percent': round(price_change_pct, 4),
                'leverage': int(p.get('leverage', 1)),
                'margin_type': p.get('marginType', 'cross'),
                'liquidation_price': float(p['liquidationPrice']) if p.get('liquidationPrice') else None,
            })

        return positions

    def get_open_orders(self, symbol: Optional[str] = None) -> list:
        """Get open orders (SL/TP)."""
        if symbol:
            orders = self.client.futures_get_open_orders(symbol=symbol)
        else:
            orders = self.client.futures_get_open_orders()

        return [{
            'symbol': o['symbol'],
            'order_id': o['orderId'],
            'type': o['type'],
            'side': o['side'],
            'stop_price': float(o['stopPrice']) if o['stopPrice'] else None,
            'quantity': float(o['origQty']),
            'status': o['status'],
            'time': datetime.fromtimestamp(o['time']/1000, tz=timezone.utc).isoformat(),
        } for o in orders]

    def get_recent_trades(self, symbol: str, limit: int = 10) -> list:
        """Get recent trades for a symbol."""
        trades = self.client.futures_account_trades(symbol=symbol, limit=limit)

        return [{
            'symbol': t['symbol'],
            'trade_id': t['id'],
            'order_id': t['orderId'],
            'side': t['side'],
            'price': float(t['price']),
            'quantity': float(t['qty']),
            'realized_pnl': float(t['realizedPnl']),
            'commission': float(t['commission']),
            'time': datetime.fromtimestamp(t['time']/1000, tz=timezone.utc).isoformat(),
        } for t in trades]

    def get_signal_info(self, symbol: str) -> dict:
        """Get the signal that triggered this trade."""
        # Try to load from signals file
        for strategy in ['quick', 'conservative']:
            signal_file = BASE_DIR / f"DATA_ITB_1h/{symbol}/signals_{strategy}.csv"
            if signal_file.exists():
                df = pd.read_csv(signal_file)
                df = df.sort_values('timestamp')
                last = df.iloc[-1]

                return {
                    'strategy': strategy,
                    'timestamp': last['timestamp'],
                    'trade_score': float(last.get('trade_score', 0)),
                    'buy_signal': int(last.get('buy_signal', 0)),
                    'sell_signal': int(last.get('sell_signal', 0)),
                    'close_price': float(last.get('close', 0)),
                }

        return {}

    def log_position_snapshot(self):
        """Log current state of all positions."""
        snapshot = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'account': self.get_account_info(),
            'positions': self.get_open_positions(),
            'open_orders': self.get_open_orders(),
        }

        # Append to JSONL file
        with open(POSITIONS_LOG, 'a') as f:
            f.write(json.dumps(snapshot) + '\n')

        return snapshot

    def log_trade_event(self, event_type: str, symbol: str, data: dict):
        """Log a trade event (open, close, tp_hit, sl_hit)."""
        event = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'event_type': event_type,
            'symbol': symbol,
            'testnet': self.testnet,
            'signal_info': self.get_signal_info(symbol),
            **data
        }

        with open(TRADES_LOG, 'a') as f:
            f.write(json.dumps(event) + '\n')

        log.info(f"Trade event logged: {event_type} {symbol}")
        return event

    def detect_position_changes(self) -> list:
        """Detect if any positions were opened or closed."""
        current_positions = {p['symbol']: p for p in self.get_open_positions()}
        events = []

        # Check for new positions (opened)
        for symbol, pos in current_positions.items():
            if symbol not in self.known_positions:
                events.append({
                    'type': 'POSITION_OPENED',
                    'symbol': symbol,
                    'data': pos
                })
                self.log_trade_event('OPEN', symbol, pos)

        # Check for closed positions
        for symbol, pos in self.known_positions.items():
            if symbol not in current_positions:
                # Get recent trades to find close details
                trades = self.get_recent_trades(symbol, limit=5)
                close_trade = trades[0] if trades else {}

                events.append({
                    'type': 'POSITION_CLOSED',
                    'symbol': symbol,
                    'data': {
                        'entry': pos,
                        'exit': close_trade,
                        'realized_pnl': close_trade.get('realized_pnl', 0)
                    }
                })
                self.log_trade_event('CLOSE', symbol, {
                    'entry_price': pos['entry_price'],
                    'exit_price': close_trade.get('price', 0),
                    'realized_pnl': close_trade.get('realized_pnl', 0),
                    'direction': pos['direction'],
                    'quantity': pos['quantity'],
                    'holding_time': None,  # TODO: calculate from entry time
                })

        # Update known positions
        self.known_positions = current_positions

        return events

    def log_daily_performance(self):
        """Log daily performance summary."""
        account = self.get_account_info()
        positions = self.get_open_positions()

        # Load trade history to calculate daily stats
        daily_trades = []
        if TRADES_LOG.exists():
            today = datetime.now(timezone.utc).date().isoformat()
            with open(TRADES_LOG, 'r') as f:
                for line in f:
                    trade = json.loads(line)
                    if trade['timestamp'].startswith(today):
                        daily_trades.append(trade)

        performance = {
            'date': datetime.now(timezone.utc).date().isoformat(),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'account_balance': account['total_balance'],
            'unrealized_pnl': account['unrealized_pnl'],
            'open_positions_count': len(positions),
            'trades_today': len([t for t in daily_trades if t['event_type'] in ['OPEN', 'CLOSE']]),
            'positions': [{
                'symbol': p['symbol'],
                'direction': p['direction'],
                'pnl': p['unrealized_pnl'],
                'pnl_pct': p['pnl_percent']
            } for p in positions]
        }

        with open(PERFORMANCE_LOG, 'a') as f:
            f.write(json.dumps(performance) + '\n')

        return performance

    def print_status(self):
        """Print current status to console."""
        account = self.get_account_info()
        positions = self.get_open_positions()

        print("\n" + "=" * 70)
        print(f"  TRADE MONITOR - {'TESTNET' if self.testnet else 'PRODUCTION'}")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        print(f"\n  Account Balance: ${account['total_balance']:,.2f}")
        print(f"  Unrealized PnL:  ${account['unrealized_pnl']:,.2f}")
        print(f"  Available:       ${account['available_balance']:,.2f}")

        if positions:
            print(f"\n  Open Positions ({len(positions)}):")
            print("  " + "-" * 66)

            total_pnl = 0
            for p in positions:
                emoji = "🟢" if p['unrealized_pnl'] >= 0 else "🔴"
                direction_emoji = "📈" if p['direction'] == 'LONG' else "📉"

                print(f"  {direction_emoji} {p['symbol']}: {p['direction']} {p['quantity']}")
                print(f"     Entry: ${p['entry_price']:,.4f} → Current: ${p['current_price']:,.4f}")
                print(f"     {emoji} PnL: ${p['unrealized_pnl']:,.2f} ({p['pnl_percent']:+.2f}%)")
                print()

                total_pnl += p['unrealized_pnl']

            print("  " + "-" * 66)
            emoji = "🟢" if total_pnl >= 0 else "🔴"
            print(f"  {emoji} TOTAL PnL: ${total_pnl:,.2f}")
        else:
            print("\n  No open positions")

        print("=" * 70 + "\n")

    def run(self, interval_seconds: int = 60):
        """Run continuous monitoring loop."""
        log.info(f"Starting monitor loop (interval: {interval_seconds}s)")
        log.info(f"Logs directory: {LOGS_DIR}")

        # Initial snapshot
        self.known_positions = {p['symbol']: p for p in self.get_open_positions()}
        self.log_position_snapshot()
        self.print_status()

        try:
            while True:
                time.sleep(interval_seconds)

                # Detect changes
                events = self.detect_position_changes()
                for event in events:
                    log.info(f"Position change: {event['type']} {event['symbol']}")

                # Log snapshot
                self.log_position_snapshot()

                # Print status
                self.print_status()

        except KeyboardInterrupt:
            log.info("Monitor stopped by user")
            self.log_daily_performance()


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Trade Monitor')
    parser.add_argument('--production', action='store_true', help='Use production (not testnet)')
    parser.add_argument('--interval', type=int, default=60, help='Snapshot interval in seconds')
    parser.add_argument('--once', action='store_true', help='Run once and exit')

    args = parser.parse_args()

    monitor = TradeMonitor(testnet=not args.production)

    if args.once:
        monitor.log_position_snapshot()
        monitor.print_status()
    else:
        monitor.run(interval_seconds=args.interval)


if __name__ == '__main__':
    main()
