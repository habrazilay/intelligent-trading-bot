"""
Shadow Mode Logging System

Provides correlated logging between server.log and shadow-specific logs.
Each shadow session has a unique session_id that appears in all log entries.
"""

import logging
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
import threading


class ShadowLogFormatter(logging.Formatter):
    """Custom formatter that includes session_id in all log entries."""

    def __init__(self, session_id: str, fmt: str = None, datefmt: str = None):
        super().__init__(fmt, datefmt)
        self.session_id = session_id

    def format(self, record):
        # Add session_id to the record
        record.session_id = self.session_id
        return super().format(record)


class ShadowLogger:
    """
    Manages logging for a shadow trading session.

    Creates two log files:
    1. Main log in logs/shadow/{session_id}/session.log - detailed execution log
    2. Trades log in logs/shadow/{session_id}/trades.jsonl - structured trade data

    Also logs to server.log with session_id prefix for correlation.
    """

    def __init__(
        self,
        session_id: str,
        config_name: str,
        log_dir: str = "logs/shadow",
        log_level: int = logging.INFO
    ):
        self.session_id = session_id
        self.config_name = config_name
        self.log_dir = Path(log_dir) / session_id
        self.log_level = log_level

        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Setup loggers
        self._setup_loggers()

        # Trade counter for this session
        self._trade_counter = 0
        self._trade_lock = threading.Lock()

        # Session start time
        self.start_time = datetime.now(timezone.utc)

        # Log session start
        self.log_session_start()

    def _setup_loggers(self):
        """Setup all loggers for this shadow session."""

        # Main session logger
        self.logger = logging.getLogger(f"shadow.{self.session_id}")
        self.logger.setLevel(self.log_level)
        self.logger.handlers.clear()

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_fmt = ShadowLogFormatter(
            self.session_id,
            fmt="%(asctime)s [%(levelname)s] [%(session_id)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(console_fmt)
        self.logger.addHandler(console_handler)

        # File handler for session log
        session_log_path = self.log_dir / "session.log"
        file_handler = logging.FileHandler(session_log_path, encoding='utf-8')
        file_handler.setLevel(self.log_level)
        file_fmt = ShadowLogFormatter(
            self.session_id,
            fmt="%(asctime)s [%(levelname)s] [%(session_id)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_fmt)
        self.logger.addHandler(file_handler)

        # Trades logger (JSONL format)
        self.trades_logger = logging.getLogger(f"shadow.{self.session_id}.trades")
        self.trades_logger.setLevel(logging.INFO)
        self.trades_logger.handlers.clear()

        trades_log_path = self.log_dir / "trades.jsonl"
        trades_handler = logging.FileHandler(trades_log_path, encoding='utf-8')
        trades_handler.setLevel(logging.INFO)
        trades_handler.setFormatter(logging.Formatter("%(message)s"))
        self.trades_logger.addHandler(trades_handler)

        # Metrics logger (periodic stats)
        self.metrics_logger = logging.getLogger(f"shadow.{self.session_id}.metrics")
        self.metrics_logger.setLevel(logging.INFO)
        self.metrics_logger.handlers.clear()

        metrics_log_path = self.log_dir / "metrics.jsonl"
        metrics_handler = logging.FileHandler(metrics_log_path, encoding='utf-8')
        metrics_handler.setLevel(logging.INFO)
        metrics_handler.setFormatter(logging.Formatter("%(message)s"))
        self.metrics_logger.addHandler(metrics_handler)

    def log_session_start(self):
        """Log session start with config details."""
        self.logger.info("=" * 60)
        self.logger.info("SHADOW MODE SESSION STARTED")
        self.logger.info("=" * 60)
        self.logger.info(f"Session ID: {self.session_id}")
        self.logger.info(f"Config: {self.config_name}")
        self.logger.info(f"Start time: {self.start_time.isoformat()}")
        self.logger.info(f"Log directory: {self.log_dir}")
        self.logger.info("=" * 60)

    def log_session_end(self, stats: Dict[str, Any] = None):
        """Log session end with summary stats."""
        end_time = datetime.now(timezone.utc)
        duration = end_time - self.start_time

        self.logger.info("=" * 60)
        self.logger.info("SHADOW MODE SESSION ENDED")
        self.logger.info("=" * 60)
        self.logger.info(f"Session ID: {self.session_id}")
        self.logger.info(f"Duration: {duration}")
        self.logger.info(f"Total trades: {self._trade_counter}")

        if stats:
            for key, value in stats.items():
                self.logger.info(f"{key}: {value}")

        self.logger.info("=" * 60)

    def info(self, msg: str, *args, **kwargs):
        """Log info message."""
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        """Log warning message."""
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        """Log error message."""
        self.logger.error(msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs):
        """Log debug message."""
        self.logger.debug(msg, *args, **kwargs)

    def log_signal(
        self,
        signal_type: str,  # BUY, SELL, NONE
        price: float,
        timestamp: int,
        score: float = None,
        extra: Dict[str, Any] = None
    ):
        """Log a trading signal."""
        signal_data = {
            "type": "signal",
            "session_id": self.session_id,
            "timestamp": timestamp,
            "datetime": datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).isoformat(),
            "signal": signal_type,
            "price": price,
            "score": score,
        }
        if extra:
            signal_data.update(extra)

        self.trades_logger.info(json.dumps(signal_data))

        if signal_type in ("BUY", "SELL"):
            self.logger.info(f"{'==>' if signal_type == 'BUY' else '<=='} {signal_type} SIGNAL @ ${price:,.2f}")

    def log_order(
        self,
        order_id: str,
        side: str,  # BUY, SELL
        order_type: str,  # LIMIT, MARKET
        price: float,
        quantity: float,
        status: str,  # SIMULATED, FILLED, CANCELED
        timestamp: int,
        fill_price: float = None,
        pnl: float = None,
        pnl_pct: float = None,
        extra: Dict[str, Any] = None
    ):
        """Log an order (simulated or real)."""
        with self._trade_lock:
            self._trade_counter += 1
            trade_num = self._trade_counter

        order_data = {
            "type": "order",
            "session_id": self.session_id,
            "trade_num": trade_num,
            "order_id": order_id,
            "timestamp": timestamp,
            "datetime": datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).isoformat(),
            "side": side,
            "order_type": order_type,
            "price": price,
            "quantity": quantity,
            "notional_usdt": price * quantity,
            "status": status,
            "fill_price": fill_price,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
        }
        if extra:
            order_data.update(extra)

        self.trades_logger.info(json.dumps(order_data))

        # Also log to main logger
        arrow = "==>" if side == "BUY" else "<=="
        self.logger.info(
            f"{arrow} {status} {side} ORDER #{trade_num} | "
            f"price=${price:,.2f} qty={quantity:.6f} notional=${price * quantity:,.2f}"
        )
        if pnl is not None:
            self.logger.info(f"    PnL: ${pnl:,.4f} ({pnl_pct:+.2f}%)")

    def log_metrics(
        self,
        timestamp: int,
        price: float,
        position: str,  # LONG, SHORT, FLAT
        balance_usdt: float,
        balance_btc: float,
        unrealized_pnl: float = 0,
        total_trades: int = 0,
        win_rate: float = None,
        extra: Dict[str, Any] = None
    ):
        """Log periodic metrics snapshot."""
        metrics_data = {
            "type": "metrics",
            "session_id": self.session_id,
            "timestamp": timestamp,
            "datetime": datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).isoformat(),
            "price": price,
            "position": position,
            "balance_usdt": balance_usdt,
            "balance_btc": balance_btc,
            "total_value_usdt": balance_usdt + (balance_btc * price),
            "unrealized_pnl": unrealized_pnl,
            "total_trades": total_trades,
            "win_rate": win_rate,
        }
        if extra:
            metrics_data.update(extra)

        self.metrics_logger.info(json.dumps(metrics_data))

    def log_config_suggestion(
        self,
        parameter: str,
        current_value: Any,
        suggested_value: Any,
        reason: str,
        confidence: float = None
    ):
        """Log a suggestion to update config based on real-time analysis."""
        suggestion_data = {
            "type": "config_suggestion",
            "session_id": self.session_id,
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "datetime": datetime.now(timezone.utc).isoformat(),
            "parameter": parameter,
            "current_value": current_value,
            "suggested_value": suggested_value,
            "reason": reason,
            "confidence": confidence,
        }

        self.trades_logger.info(json.dumps(suggestion_data))

        self.logger.warning(
            f"CONFIG SUGGESTION: {parameter} = {suggested_value} (was {current_value}) | {reason}"
        )

    def get_log_paths(self) -> Dict[str, Path]:
        """Return paths to all log files."""
        return {
            "session": self.log_dir / "session.log",
            "trades": self.log_dir / "trades.jsonl",
            "metrics": self.log_dir / "metrics.jsonl",
        }


def setup_shadow_logging(
    session_id: str,
    config_name: str,
    log_level: int = logging.INFO
) -> ShadowLogger:
    """
    Setup logging for a shadow trading session.

    Args:
        session_id: Unique identifier for this session
        config_name: Name of the config file being used
        log_level: Logging level (default: INFO)

    Returns:
        ShadowLogger instance
    """
    return ShadowLogger(
        session_id=session_id,
        config_name=config_name,
        log_level=log_level
    )


def generate_session_id(config_name: str, strategy_suffix: str = None) -> str:
    """
    Generate a unique session ID based on config and timestamp.

    Format: {config_name}_{strategy_suffix}_{timestamp}
    Example: btcusdt_1m_aggressive_20251211_143022
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Clean config name
    config_base = Path(config_name).stem.replace("-", "_")

    if strategy_suffix:
        return f"{config_base}_{strategy_suffix}_{timestamp}"
    return f"{config_base}_{timestamp}"
