#!/usr/bin/env python3
"""
Simple Shadow Mode Runner

Versão simplificada que NÃO precisa de TA-Lib.
Usa features calculadas com pandas/numpy.

Conecta na Binance real mas simula todas as ordens.

Usage:
    python run_shadow_simple.py --balance 1000 --symbol BTCUSDT
"""

import asyncio
import signal
import sys
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal
import time

import click
import pandas as pd
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from shadow.shadow_logger import ShadowLogger, generate_session_id
from shadow.shadow_mode import ShadowTrader
from shadow.shadow_analyzer import ShadowAnalyzer
from shadow.simple_features import add_simple_features, generate_signals_simple

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("shadow_simple")


class SimpleShadowSession:
    """
    Simple shadow trading session without TA-Lib dependency.

    Uses pandas-based feature calculation and connects directly to Binance.
    """

    def __init__(
        self,
        symbol: str = "BTCUSDT",
        initial_balance: float = 1000.0,
        strategy_suffix: str = None,
        buy_threshold: float = 0.002,
        sell_threshold: float = -0.002,
    ):
        self.symbol = symbol
        self.initial_balance = initial_balance
        self.strategy_suffix = strategy_suffix
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

        # Generate session ID
        self.session_id = generate_session_id(f"{symbol.lower()}_simple", strategy_suffix)

        # Setup logger
        self.logger = ShadowLogger(
            session_id=self.session_id,
            config_name=f"{symbol}_simple_shadow",
        )

        # Config for trader
        self.config = {
            'symbol': symbol,
            'base_asset': symbol.replace('USDT', ''),
            'quote_asset': 'USDT',
            'trade_model': {
                'percentage_used_for_trade': 2.0,
                'min_notional_usdt': 10.0,
                'min_balance_usdt_for_percentage': 500.0,
                'limit_price_adjustment': 0.002,
            },
            'risk_management': {
                'stop_loss_percent': 2.0,
                'take_profit_percent': 3.0,
                'circuit_breaker': {
                    'max_consecutive_losses': 3,
                    'cooldown_minutes': 60,
                    'max_daily_losses': 5,
                    'max_daily_loss_percent': 10.0,
                }
            }
        }

        # Setup trader
        self.trader = ShadowTrader(
            config=self.config,
            logger=self.logger,
            initial_balance=initial_balance,
        )

        # Setup analyzer
        self.analyzer = ShadowAnalyzer(
            config=self.config,
            logger=self.logger,
            analysis_interval=60,
        )

        # Data buffer
        self.klines_buffer = pd.DataFrame()
        self.max_buffer_size = 200  # Keep last 200 candles

        # State
        self.running = False
        self.client = None

    def setup_binance_client(self) -> bool:
        """Initialize Binance client."""
        try:
            from binance import Client

            api_key = os.getenv("BINANCE_API_KEY")
            api_secret = os.getenv("BINANCE_API_SECRET")

            if not api_key or not api_secret:
                self.logger.error("Missing BINANCE_API_KEY or BINANCE_API_SECRET in environment")
                return False

            self.client = Client(api_key=api_key, api_secret=api_secret)
            self.logger.info("Binance client initialized")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize Binance client: {e}")
            return False

    def fetch_klines(self, limit: int = 100) -> pd.DataFrame:
        """Fetch recent klines from Binance."""
        try:
            klines = self.client.get_klines(
                symbol=self.symbol,
                interval='1m',
                limit=limit
            )

            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'
            ])

            # Convert types
            for col in ['open', 'high', 'low', 'close', 'volume', 'quote_av']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.set_index('timestamp')

            return df

        except Exception as e:
            self.logger.error(f"Failed to fetch klines: {e}")
            return pd.DataFrame()

    def update_buffer(self, new_klines: pd.DataFrame):
        """Update klines buffer with new data."""
        if new_klines.empty:
            return

        if self.klines_buffer.empty:
            self.klines_buffer = new_klines.copy()
        else:
            # Append new klines, remove duplicates
            self.klines_buffer = pd.concat([self.klines_buffer, new_klines])
            self.klines_buffer = self.klines_buffer[~self.klines_buffer.index.duplicated(keep='last')]
            self.klines_buffer = self.klines_buffer.sort_index()

            # Keep only last N candles
            if len(self.klines_buffer) > self.max_buffer_size:
                self.klines_buffer = self.klines_buffer.tail(self.max_buffer_size)

    def process_data(self) -> pd.DataFrame:
        """Process buffer data: add features and generate signals."""
        if len(self.klines_buffer) < 60:
            return pd.DataFrame()

        df = self.klines_buffer.copy()

        # Add features
        df = add_simple_features(df)

        # Generate signals
        df = generate_signals_simple(df, self.buy_threshold, self.sell_threshold)

        return df

    async def run(self):
        """Main shadow trading loop."""
        self.running = True

        self.logger.info("=" * 60)
        self.logger.info("SIMPLE SHADOW MODE STARTED")
        self.logger.info("=" * 60)
        self.logger.info(f"Symbol: {self.symbol}")
        self.logger.info(f"Initial balance: ${self.initial_balance:,.2f}")
        self.logger.info(f"Buy threshold: {self.buy_threshold}")
        self.logger.info(f"Sell threshold: {self.sell_threshold}")
        self.logger.info("=" * 60)

        # Initial data fetch
        self.logger.info("Fetching initial data...")
        initial_klines = self.fetch_klines(limit=200)
        self.update_buffer(initial_klines)
        self.logger.info(f"Loaded {len(self.klines_buffer)} initial candles")

        # Main loop
        candle_count = 0
        while self.running:
            try:
                # Fetch latest klines
                new_klines = self.fetch_klines(limit=5)
                self.update_buffer(new_klines)

                # Process and generate signals
                df = self.process_data()

                if df.empty:
                    await asyncio.sleep(10)
                    continue

                # Get current price
                current_row = df.iloc[-1]
                current_price = Decimal(str(current_row['close']))
                timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)

                # Process signal with trader
                await self.trader.process_signal(df, 'buy_signal', 'sell_signal')

                # Record for analyzer
                self.analyzer.record_price(timestamp, float(current_price))

                # Check stop loss / take profit
                if self.trader.check_stop_loss(current_price, timestamp):
                    await self.trader.close_position(current_price, timestamp)
                elif self.trader.check_take_profit(current_price, timestamp):
                    await self.trader.close_position(current_price, timestamp)

                # Periodic analysis
                suggestions = self.analyzer.analyze(float(current_price), timestamp)

                # Log progress
                candle_count += 1
                if candle_count % 60 == 0:  # Every hour
                    stats = self.trader.portfolio.get_stats()
                    self.logger.info(
                        f"Progress: {candle_count} candles | "
                        f"Balance: ${float(self.trader.portfolio.balance_usdt):,.2f} | "
                        f"Trades: {stats['total_trades']} | "
                        f"Win rate: {stats['win_rate']:.1f}%"
                    )

                # Wait for next minute
                await asyncio.sleep(60)

            except asyncio.CancelledError:
                self.logger.info("Session cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(10)

        # Shutdown
        self.shutdown()

    def shutdown(self):
        """Shutdown the session gracefully."""
        self.running = False

        summary = self.trader.get_summary()
        analyzer_summary = self.analyzer.get_summary()

        self.logger.log_session_end({
            **summary,
            **analyzer_summary,
        })

        # Export final analysis
        log_paths = self.logger.get_log_paths()
        suggestions_path = log_paths["session"].parent / "final_suggestions.json"
        self.analyzer.export_suggestions(str(suggestions_path))

        self.logger.info(f"Session ended. Logs at: {log_paths['session'].parent}")

        # Print summary
        print("\n" + "=" * 60)
        print("SHADOW MODE SESSION SUMMARY")
        print("=" * 60)
        print(f"Session ID: {self.session_id}")
        print(f"Initial Balance: ${self.initial_balance:,.2f}")
        print(f"Final Balance: ${float(self.trader.portfolio.balance_usdt):,.2f}")
        print(f"Return: {summary['total_return_pct']:+.2f}%")
        print(f"Total Trades: {summary['total_trades']}")
        print(f"Win Rate: {summary['win_rate']:.1f}%")
        print(f"Profit Factor: {analyzer_summary.get('profit_factor', 0):.2f}")
        print("=" * 60)
        print(f"Logs: {log_paths['session'].parent}")
        print("=" * 60)

    def stop(self):
        """Signal the session to stop."""
        self.running = False


@click.command()
@click.option('--symbol', '-s', default='BTCUSDT', help='Trading symbol (default: BTCUSDT)')
@click.option('--balance', '-b', default=1000.0, help='Initial simulated balance in USDT')
@click.option('--buy-threshold', default=0.002, help='Buy signal threshold')
@click.option('--sell-threshold', default=-0.002, help='Sell signal threshold')
@click.option('--suffix', default=None, help='Session name suffix')
def main(symbol: str, balance: float, buy_threshold: float, sell_threshold: float, suffix: str):
    """
    Run simple shadow trading session.

    No TA-Lib required! Uses pandas-based feature calculation.

    Examples:
        python run_shadow_simple.py --symbol BTCUSDT --balance 1000
        python run_shadow_simple.py -s ETHUSDT -b 5000
    """
    log.info("=" * 60)
    log.info("SIMPLE SHADOW MODE")
    log.info("(No TA-Lib required)")
    log.info("=" * 60)
    log.info(f"Symbol: {symbol}")
    log.info(f"Balance: ${balance:,.2f}")
    log.info(f"Buy threshold: {buy_threshold}")
    log.info(f"Sell threshold: {sell_threshold}")
    log.info("=" * 60)

    # Create session
    session = SimpleShadowSession(
        symbol=symbol,
        initial_balance=balance,
        strategy_suffix=suffix,
        buy_threshold=buy_threshold,
        sell_threshold=sell_threshold,
    )

    # Setup Binance client
    if not session.setup_binance_client():
        log.error("Failed to setup Binance client")
        sys.exit(1)

    # Run
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def signal_handler(sig, frame):
        log.info("Shutdown requested...")
        session.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        loop.run_until_complete(session.run())
    except KeyboardInterrupt:
        session.stop()
    finally:
        loop.close()


if __name__ == "__main__":
    main()
