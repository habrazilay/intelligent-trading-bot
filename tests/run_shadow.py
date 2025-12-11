#!/usr/bin/env python3
"""
Shadow Mode Runner

Run multiple shadow trading sessions in parallel, each with different configs.
Connects to real Binance API but simulates all orders.

Usage:
    # Single config:
    python run_shadow.py -c configs/btcusdt_1m_staging.jsonc

    # Multiple configs in parallel:
    python run_shadow.py -c configs/btcusdt_1m_aggressive.jsonc configs/btcusdt_1m_conservative.jsonc

    # With custom initial balance:
    python run_shadow.py -c configs/btcusdt_1m_staging.jsonc --balance 5000

    # With strategy suffix for session naming:
    python run_shadow.py -c configs/btcusdt_1m_staging.jsonc --suffix test_v2
"""

import asyncio
import signal
import sys
import os
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp

import click
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from service.App import App, load_config, PACKAGE_ROOT
from service.analyzer import Analyzer
from common.model_store import ModelStore
from common.utils import now_timestamp, pandas_get_interval, freq_to_CronTrigger, pandas_interval_length_ms
from common.types import Venue
from inputs import get_collector_functions
from shadow.shadow_logger import ShadowLogger, generate_session_id
from shadow.shadow_mode import ShadowTrader
from shadow.shadow_analyzer import ShadowAnalyzer

# Load environment
load_dotenv()

# Setup base logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("shadow_runner")


class ShadowSession:
    """
    Represents a single shadow trading session.

    Manages the lifecycle of a shadow trader including:
    - Binance connection
    - Data collection
    - Signal generation
    - Simulated order execution
    - Logging and analysis
    """

    def __init__(
        self,
        config_file: str,
        initial_balance: float = 1000.0,
        strategy_suffix: str = None,
    ):
        self.config_file = config_file
        self.initial_balance = initial_balance
        self.strategy_suffix = strategy_suffix

        # Will be initialized in setup()
        self.config: Dict[str, Any] = {}
        self.session_id: str = ""
        self.logger: Optional[ShadowLogger] = None
        self.trader: Optional[ShadowTrader] = None
        self.analyzer: Optional[ShadowAnalyzer] = None

        self.running = False
        self.start_time: Optional[datetime] = None

    def setup(self) -> bool:
        """Initialize the session."""
        try:
            # Load config
            config_path = PACKAGE_ROOT / self.config_file
            if not config_path.exists():
                log.error(f"Config file not found: {config_path}")
                return False

            load_config(self.config_file)
            self.config = App.config.copy()

            # Force shadow mode settings
            self.config["trade_model"] = self.config.get("trade_model", {})
            self.config["trade_model"]["simulate_order_execution"] = True
            self.config["trade_model"]["test_order_before_submit"] = False
            self.config["trade_model"]["no_trades_only_data_processing"] = False

            # Generate session ID
            config_name = Path(self.config_file).stem
            self.session_id = generate_session_id(config_name, self.strategy_suffix)

            # Setup logger
            self.logger = ShadowLogger(
                session_id=self.session_id,
                config_name=self.config_file,
            )

            # Setup trader
            self.trader = ShadowTrader(
                config=self.config,
                logger=self.logger,
                initial_balance=self.initial_balance,
            )

            # Setup analyzer
            self.analyzer = ShadowAnalyzer(
                config=self.config,
                logger=self.logger,
                analysis_interval=60,  # Analyze every hour
            )

            self.logger.info("Shadow session setup complete")
            return True

        except Exception as e:
            log.error(f"Failed to setup session: {e}")
            traceback.print_exc()
            return False

    async def run(self):
        """Run the shadow trading session."""
        if not self.trader or not self.logger:
            log.error("Session not setup properly")
            return

        self.running = True
        self.start_time = datetime.now(timezone.utc)

        symbol = self.config.get("symbol", "BTCUSDT")
        freq = self.config.get("freq", "1m")
        venue = Venue(self.config.get("venue", "binance"))

        self.logger.info(f"Starting shadow session for {symbol} @ {freq}")

        # Get collector functions
        sync_data_collector_task, data_provider_health_check = get_collector_functions(venue)

        # Initialize Binance client
        from binance import Client
        api_key = self.config.get("api_key") or os.getenv("BINANCE_API_KEY")
        api_secret = self.config.get("api_secret") or os.getenv("BINANCE_API_SECRET")

        if not api_key or not api_secret:
            self.logger.error("Missing Binance API credentials")
            return

        try:
            App.client = Client(api_key=api_key, api_secret=api_secret)
        except Exception as e:
            self.logger.error(f"Failed to connect to Binance: {e}")
            return

        # Initialize model store and analyzer
        App.model_store = ModelStore(self.config)
        App.model_store.load_models()
        App.analyzer = Analyzer(self.config, App.model_store)
        App.config = self.config

        # Health check
        try:
            await data_provider_health_check()
            self.logger.info("Binance health check passed")
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return

        # Initial data collection
        try:
            await sync_data_collector_task(self.config)
            await sync_data_collector_task(self.config)  # Second call for newest data
            App.analyzer.analyze()
            self.logger.info("Initial data collection complete")
        except Exception as e:
            self.logger.error(f"Initial data collection failed: {e}")
            return

        # Main loop
        interval_ms = pandas_interval_length_ms(freq)

        while self.running:
            try:
                # Collect new data
                results = await sync_data_collector_task(self.config)
                if results is None:
                    self.logger.warning("No data received, retrying...")
                    await asyncio.sleep(5)
                    continue

                App.analyzer.append_klines(results)
                App.analyzer.analyze()

                df = App.analyzer.df
                if df is None or df.empty:
                    await asyncio.sleep(1)
                    continue

                # Get signal columns from config
                output_sets = self.config.get("output_sets", [])
                buy_col = "buy_signal"
                sell_col = "sell_signal"

                for os_config in output_sets:
                    if os_config.get("generator") == "trader_binance":
                        buy_col = os_config.get("config", {}).get("buy_signal_column", buy_col)
                        sell_col = os_config.get("config", {}).get("sell_signal_column", sell_col)
                        break

                # Process signal with shadow trader
                order = await self.trader.process_signal(df, buy_col, sell_col)

                # Record for analyzer
                if df is not None and not df.empty:
                    row = df.iloc[-1]
                    current_price = float(row.get("close", 0))
                    timestamp = now_timestamp()

                    self.analyzer.record_price(timestamp, current_price)

                    # Run periodic analysis
                    suggestions = self.analyzer.analyze(current_price, timestamp)

                    # Check stop loss / take profit
                    from decimal import Decimal
                    if self.trader.check_stop_loss(Decimal(str(current_price)), timestamp):
                        await self.trader.close_position(Decimal(str(current_price)), timestamp)
                    elif self.trader.check_take_profit(Decimal(str(current_price)), timestamp):
                        await self.trader.close_position(Decimal(str(current_price)), timestamp)

                # Wait for next candle
                _, next_interval_start = pandas_get_interval(freq)
                now = now_timestamp()
                wait_ms = max(0, next_interval_start - now + 1000)  # +1s buffer
                await asyncio.sleep(wait_ms / 1000)

            except asyncio.CancelledError:
                self.logger.info("Session cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                traceback.print_exc()
                await asyncio.sleep(5)

        # Shutdown
        self.shutdown()

    def shutdown(self):
        """Shutdown the session gracefully."""
        self.running = False

        if self.trader and self.logger:
            summary = self.trader.get_summary()
            analyzer_summary = self.analyzer.get_summary() if self.analyzer else {}

            self.logger.log_session_end({
                **summary,
                **analyzer_summary,
            })

            # Export final analysis
            log_paths = self.logger.get_log_paths()
            suggestions_path = log_paths["session"].parent / "final_suggestions.json"
            if self.analyzer:
                self.analyzer.export_suggestions(str(suggestions_path))

            self.logger.info(f"Session ended. Logs at: {log_paths['session'].parent}")

    def stop(self):
        """Signal the session to stop."""
        self.running = False


def run_single_session(args):
    """Run a single shadow session (for multiprocessing)."""
    config_file, initial_balance, strategy_suffix = args

    session = ShadowSession(
        config_file=config_file,
        initial_balance=initial_balance,
        strategy_suffix=strategy_suffix,
    )

    if not session.setup():
        return {"error": "Setup failed", "config": config_file}

    # Run async loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Handle signals
    def signal_handler(sig, frame):
        session.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        loop.run_until_complete(session.run())
    except KeyboardInterrupt:
        session.stop()
    finally:
        loop.close()

    return session.trader.get_summary() if session.trader else {"error": "No trader"}


@click.command()
@click.option(
    '--config', '-c',
    multiple=True,
    required=True,
    help='Config file(s) to run. Can specify multiple for parallel execution.'
)
@click.option(
    '--balance', '-b',
    default=1000.0,
    help='Initial simulated balance in USDT (default: 1000)'
)
@click.option(
    '--suffix', '-s',
    default=None,
    help='Strategy suffix for session naming'
)
@click.option(
    '--parallel/--sequential',
    default=True,
    help='Run configs in parallel or sequentially'
)
def main(config: tuple, balance: float, suffix: str, parallel: bool):
    """
    Run shadow trading sessions.

    Examples:
        python run_shadow.py -c configs/btcusdt_1m_staging.jsonc
        python run_shadow.py -c config1.jsonc -c config2.jsonc --parallel
    """
    log.info("=" * 60)
    log.info("SHADOW MODE RUNNER")
    log.info("=" * 60)
    log.info(f"Configs: {list(config)}")
    log.info(f"Initial balance: ${balance:,.2f}")
    log.info(f"Parallel: {parallel}")
    log.info("=" * 60)

    if len(config) == 1:
        # Single config - run directly
        session = ShadowSession(
            config_file=config[0],
            initial_balance=balance,
            strategy_suffix=suffix,
        )

        if not session.setup():
            log.error("Setup failed")
            sys.exit(1)

        # Run in main process
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

    elif parallel:
        # Multiple configs - run in parallel using multiprocessing
        log.info(f"Starting {len(config)} parallel shadow sessions...")

        # Prepare args for each session
        args_list = [
            (cfg, balance, f"{suffix}_{i}" if suffix else f"p{i}")
            for i, cfg in enumerate(config)
        ]

        # Use process pool
        with ProcessPoolExecutor(max_workers=len(config)) as executor:
            results = list(executor.map(run_single_session, args_list))

        # Print results
        log.info("=" * 60)
        log.info("SHADOW MODE RESULTS")
        log.info("=" * 60)
        for cfg, result in zip(config, results):
            log.info(f"\n{cfg}:")
            for key, value in result.items():
                log.info(f"  {key}: {value}")

    else:
        # Sequential execution
        log.info(f"Running {len(config)} sessions sequentially...")

        for i, cfg in enumerate(config):
            log.info(f"\n--- Session {i+1}/{len(config)}: {cfg} ---\n")

            session = ShadowSession(
                config_file=cfg,
                initial_balance=balance,
                strategy_suffix=f"{suffix}_{i}" if suffix else f"s{i}",
            )

            if not session.setup():
                log.error(f"Setup failed for {cfg}")
                continue

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                loop.run_until_complete(session.run())
            except KeyboardInterrupt:
                session.stop()
                break
            finally:
                loop.close()


if __name__ == "__main__":
    main()
