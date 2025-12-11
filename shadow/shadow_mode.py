"""
Shadow Mode Trading System

Connects to real Binance API, receives real data, generates real signals,
but simulates order execution instead of placing real orders.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any, List
from enum import Enum

import pandas as pd

from binance.enums import (
    ORDER_TYPE_LIMIT,
    TIME_IN_FORCE_GTC,
    SIDE_BUY,
    SIDE_SELL,
)

from shadow.shadow_logger import ShadowLogger, generate_session_id
from common.utils import now_timestamp, to_decimal, round_str


class Position(Enum):
    FLAT = "FLAT"
    LONG = "LONG"
    SHORT = "SHORT"  # Not used in spot, but kept for futures


@dataclass
class ShadowOrder:
    """Represents a simulated order in shadow mode."""
    order_id: str
    session_id: str
    side: str  # BUY, SELL
    order_type: str  # LIMIT, MARKET
    symbol: str
    price: Decimal
    quantity: Decimal
    timestamp: int
    status: str = "SIMULATED"  # SIMULATED, FILLED, CANCELED
    fill_price: Optional[Decimal] = None
    fill_time: Optional[int] = None
    slippage_bps: float = 0.0

    @property
    def notional(self) -> Decimal:
        """Order value in quote currency (USDT)."""
        return self.price * self.quantity

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            "order_id": self.order_id,
            "session_id": self.session_id,
            "side": self.side,
            "order_type": self.order_type,
            "symbol": self.symbol,
            "price": float(self.price),
            "quantity": float(self.quantity),
            "notional": float(self.notional),
            "timestamp": self.timestamp,
            "status": self.status,
            "fill_price": float(self.fill_price) if self.fill_price else None,
            "fill_time": self.fill_time,
            "slippage_bps": self.slippage_bps,
        }


@dataclass
class ShadowTrade:
    """Represents a completed trade (entry + exit)."""
    trade_id: str
    session_id: str
    symbol: str
    side: str  # LONG, SHORT
    entry_order: ShadowOrder
    exit_order: Optional[ShadowOrder] = None
    pnl: Optional[Decimal] = None
    pnl_pct: Optional[float] = None
    hold_time_seconds: Optional[int] = None

    @property
    def is_closed(self) -> bool:
        return self.exit_order is not None

    def close(self, exit_order: ShadowOrder):
        """Close the trade with an exit order."""
        self.exit_order = exit_order

        entry_price = self.entry_order.fill_price or self.entry_order.price
        exit_price = exit_order.fill_price or exit_order.price

        if self.side == "LONG":
            self.pnl = (exit_price - entry_price) * self.entry_order.quantity
            self.pnl_pct = float((exit_price / entry_price - 1) * 100)
        else:  # SHORT (for futures)
            self.pnl = (entry_price - exit_price) * self.entry_order.quantity
            self.pnl_pct = float((entry_price / exit_price - 1) * 100)

        if exit_order.fill_time and self.entry_order.fill_time:
            self.hold_time_seconds = (exit_order.fill_time - self.entry_order.fill_time) // 1000


@dataclass
class ShadowPortfolio:
    """Tracks simulated portfolio state."""
    session_id: str
    initial_balance_usdt: Decimal = Decimal("1000.0")
    balance_usdt: Decimal = Decimal("1000.0")
    balance_base: Decimal = Decimal("0.0")  # BTC, ETH, etc.
    position: Position = Position.FLAT
    current_trade: Optional[ShadowTrade] = None
    trade_history: List[ShadowTrade] = field(default_factory=list)

    # Fee configuration
    maker_fee: Decimal = Decimal("0.001")  # 0.1%
    taker_fee: Decimal = Decimal("0.001")  # 0.1%

    # Slippage simulation
    base_slippage_bps: float = 5.0  # 5 basis points

    def get_total_value(self, current_price: Decimal) -> Decimal:
        """Calculate total portfolio value in USDT."""
        return self.balance_usdt + (self.balance_base * current_price)

    def get_unrealized_pnl(self, current_price: Decimal) -> Decimal:
        """Calculate unrealized PnL for open position."""
        if not self.current_trade or self.current_trade.is_closed:
            return Decimal("0")

        entry_price = self.current_trade.entry_order.fill_price or self.current_trade.entry_order.price
        return (current_price - entry_price) * self.balance_base

    def get_stats(self) -> Dict[str, Any]:
        """Get portfolio statistics."""
        if not self.trade_history:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_pnl": 0.0,
                "max_win": 0.0,
                "max_loss": 0.0,
            }

        closed_trades = [t for t in self.trade_history if t.is_closed]
        if not closed_trades:
            return {
                "total_trades": len(self.trade_history),
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_pnl": 0.0,
                "max_win": 0.0,
                "max_loss": 0.0,
            }

        pnls = [float(t.pnl) for t in closed_trades if t.pnl is not None]
        winning = [p for p in pnls if p > 0]
        losing = [p for p in pnls if p < 0]

        return {
            "total_trades": len(closed_trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": len(winning) / len(closed_trades) * 100 if closed_trades else 0.0,
            "total_pnl": sum(pnls),
            "avg_pnl": sum(pnls) / len(pnls) if pnls else 0.0,
            "max_win": max(winning) if winning else 0.0,
            "max_loss": min(losing) if losing else 0.0,
        }


class ShadowTrader:
    """
    Shadow mode trader that connects to real Binance but simulates orders.

    Features:
    - Connects to real Binance API for market data
    - Generates real trading signals
    - Simulates order execution with realistic slippage/fees
    - Logs everything for later analysis
    """

    def __init__(
        self,
        config: Dict[str, Any],
        logger: ShadowLogger,
        initial_balance: float = 1000.0,
    ):
        self.config = config
        self.logger = logger
        self.session_id = logger.session_id

        # Symbol info
        self.symbol = config.get("symbol", "BTCUSDT")
        self.base_asset = config.get("base_asset", "BTC")
        self.quote_asset = config.get("quote_asset", "USDT")

        # Trade model config
        self.trade_model = config.get("trade_model", {})
        self.risk_management = config.get("risk_management", {})

        # Portfolio
        self.portfolio = ShadowPortfolio(
            session_id=self.session_id,
            initial_balance_usdt=Decimal(str(initial_balance)),
            balance_usdt=Decimal(str(initial_balance)),
        )

        # Order tracking
        self.pending_order: Optional[ShadowOrder] = None
        self.last_order_time: Optional[int] = None

        # Risk management state
        self.consecutive_losses = 0
        self.daily_losses = 0
        self.daily_loss_amount = Decimal("0")
        self.circuit_breaker_until: Optional[int] = None

        # Metrics
        self.signals_received = 0
        self.orders_placed = 0
        self.orders_filled = 0

        self.logger.info(f"ShadowTrader initialized for {self.symbol}")
        self.logger.info(f"Initial balance: ${initial_balance:,.2f} USDT")

    def check_circuit_breaker(self, current_ts: int) -> bool:
        """Check if trading is paused due to circuit breaker."""
        if self.circuit_breaker_until and current_ts < self.circuit_breaker_until:
            return True

        cb_config = self.risk_management.get("circuit_breaker", {})

        # Check consecutive losses
        max_consecutive = cb_config.get("max_consecutive_losses", 3)
        if self.consecutive_losses >= max_consecutive:
            cooldown_ms = cb_config.get("cooldown_minutes", 60) * 60 * 1000
            self.circuit_breaker_until = current_ts + cooldown_ms
            self.logger.warning(
                f"CIRCUIT BREAKER: {self.consecutive_losses} consecutive losses. "
                f"Pausing for {cooldown_ms // 60000} minutes."
            )
            return True

        # Check daily losses
        max_daily = cb_config.get("max_daily_losses", 5)
        if self.daily_losses >= max_daily:
            self.logger.warning(f"CIRCUIT BREAKER: {self.daily_losses} daily losses. Pausing until reset.")
            return True

        # Check daily loss percentage
        max_daily_pct = Decimal(str(cb_config.get("max_daily_loss_percent", 10.0)))
        daily_loss_pct = (self.daily_loss_amount / self.portfolio.initial_balance_usdt) * 100
        if daily_loss_pct >= max_daily_pct:
            self.logger.warning(f"CIRCUIT BREAKER: Daily loss {daily_loss_pct:.1f}% exceeds limit.")
            return True

        return False

    def calculate_position_size(self, price: Decimal) -> Decimal:
        """Calculate position size based on config."""
        pct = Decimal(str(self.trade_model.get("percentage_used_for_trade", 2.0)))
        min_notional = Decimal(str(self.trade_model.get("min_notional_usdt", 5.0)))
        min_balance_for_pct = Decimal(str(self.trade_model.get("min_balance_usdt_for_percentage", 500.0)))

        if self.portfolio.balance_usdt >= min_balance_for_pct:
            notional = (self.portfolio.balance_usdt * pct) / Decimal("100")
            notional = max(notional, min_notional)
        else:
            notional = min(self.portfolio.balance_usdt, min_notional)

        if notional < min_notional:
            return Decimal("0")

        quantity = notional / price
        return quantity

    def calculate_limit_price(self, side: str, market_price: Decimal) -> Decimal:
        """Calculate limit price with adjustment."""
        adj = Decimal(str(self.trade_model.get("limit_price_adjustment", 0.002)))
        adj = max(Decimal("0"), min(adj, Decimal("0.05")))  # Clamp 0-5%

        if side == SIDE_BUY:
            price = market_price * (Decimal("1") - adj)
        else:
            price = market_price * (Decimal("1") + adj)

        return price.quantize(Decimal("0.01"))

    def simulate_slippage(self, price: Decimal, side: str, volatility: float = 0.0) -> Decimal:
        """Simulate realistic slippage based on volatility."""
        import random

        # Base slippage + volatility component
        base_bps = self.portfolio.base_slippage_bps
        vol_bps = volatility * 10  # Higher volatility = more slippage

        total_bps = base_bps + vol_bps
        slippage_pct = Decimal(str(random.uniform(0, total_bps) / 10000))

        if side == SIDE_BUY:
            return price * (Decimal("1") + slippage_pct)
        else:
            return price * (Decimal("1") - slippage_pct)

    def simulate_fill(self, order: ShadowOrder, market_price: Decimal) -> ShadowOrder:
        """Simulate order fill with slippage."""
        fill_price = self.simulate_slippage(order.price, order.side)
        order.fill_price = fill_price.quantize(Decimal("0.01"))
        order.fill_time = now_timestamp()
        order.status = "FILLED"
        order.slippage_bps = float((fill_price / order.price - 1) * 10000)

        return order

    async def process_signal(
        self,
        df: pd.DataFrame,
        buy_signal_column: str,
        sell_signal_column: str,
    ) -> Optional[ShadowOrder]:
        """
        Process trading signal and return simulated order if applicable.

        This is the main entry point called by the server on each candle.
        """
        self.signals_received += 1
        now_ts = now_timestamp()

        # Get latest row
        if df.empty:
            return None

        row = df.iloc[-1]
        close_price = Decimal(str(row.get("close", 0)))

        if close_price == 0:
            return None

        # Get signals
        buy_signal = bool(row.get(buy_signal_column, False))
        sell_signal = bool(row.get(sell_signal_column, False))

        # Determine signal side
        if buy_signal and sell_signal:
            signal_side = "BOTH"
        elif buy_signal:
            signal_side = "BUY"
        elif sell_signal:
            signal_side = "SELL"
        else:
            signal_side = "NONE"

        # Get score if available
        score = row.get("trade_score", None)
        if score is not None:
            score = float(score)

        # Log signal
        self.logger.log_signal(
            signal_type=signal_side,
            price=float(close_price),
            timestamp=now_ts,
            score=score,
            extra={
                "position": self.portfolio.position.value,
                "balance_usdt": float(self.portfolio.balance_usdt),
            }
        )

        # Check circuit breaker
        if self.check_circuit_breaker(now_ts):
            return None

        # Process based on current position and signal
        order = None

        if self.portfolio.position == Position.FLAT and signal_side == "BUY":
            order = await self.open_position(SIDE_BUY, close_price, now_ts)

        elif self.portfolio.position == Position.LONG and signal_side == "SELL":
            order = await self.close_position(close_price, now_ts)

        # Log periodic metrics
        if self.signals_received % 60 == 0:  # Every 60 signals (~1 hour for 1m)
            self._log_metrics(close_price, now_ts)

        return order

    async def open_position(
        self,
        side: str,
        market_price: Decimal,
        timestamp: int
    ) -> Optional[ShadowOrder]:
        """Open a new position."""
        quantity = self.calculate_position_size(market_price)

        if quantity <= 0:
            self.logger.warning("Cannot open position: insufficient balance or below minimum")
            return None

        limit_price = self.calculate_limit_price(side, market_price)

        # Create simulated order
        order = ShadowOrder(
            order_id=f"SIM_{uuid.uuid4().hex[:12]}",
            session_id=self.session_id,
            side=side,
            order_type="LIMIT",
            symbol=self.symbol,
            price=limit_price,
            quantity=quantity,
            timestamp=timestamp,
        )

        # Simulate fill immediately (shadow mode assumes instant fill)
        order = self.simulate_fill(order, market_price)

        # Apply fees
        fee = order.quantity * order.fill_price * self.portfolio.taker_fee

        # Update portfolio
        cost = order.quantity * order.fill_price + fee
        self.portfolio.balance_usdt -= cost
        self.portfolio.balance_base += order.quantity
        self.portfolio.position = Position.LONG

        # Create trade record
        trade = ShadowTrade(
            trade_id=f"TRADE_{uuid.uuid4().hex[:8]}",
            session_id=self.session_id,
            symbol=self.symbol,
            side="LONG",
            entry_order=order,
        )
        self.portfolio.current_trade = trade

        self.orders_placed += 1
        self.orders_filled += 1

        # Log order
        self.logger.log_order(
            order_id=order.order_id,
            side=order.side,
            order_type=order.order_type,
            price=float(order.price),
            quantity=float(order.quantity),
            status=order.status,
            timestamp=timestamp,
            fill_price=float(order.fill_price),
            extra={
                "fee": float(fee),
                "slippage_bps": order.slippage_bps,
                "balance_usdt_after": float(self.portfolio.balance_usdt),
            }
        )

        return order

    async def close_position(
        self,
        market_price: Decimal,
        timestamp: int
    ) -> Optional[ShadowOrder]:
        """Close current position."""
        if self.portfolio.position == Position.FLAT:
            return None

        if not self.portfolio.current_trade:
            return None

        quantity = self.portfolio.balance_base
        limit_price = self.calculate_limit_price(SIDE_SELL, market_price)

        # Create simulated order
        order = ShadowOrder(
            order_id=f"SIM_{uuid.uuid4().hex[:12]}",
            session_id=self.session_id,
            side=SIDE_SELL,
            order_type="LIMIT",
            symbol=self.symbol,
            price=limit_price,
            quantity=quantity,
            timestamp=timestamp,
        )

        # Simulate fill
        order = self.simulate_fill(order, market_price)

        # Apply fees
        fee = order.quantity * order.fill_price * self.portfolio.taker_fee

        # Calculate proceeds
        proceeds = order.quantity * order.fill_price - fee

        # Close trade
        self.portfolio.current_trade.close(order)
        pnl = self.portfolio.current_trade.pnl
        pnl_pct = self.portfolio.current_trade.pnl_pct

        # Update portfolio
        self.portfolio.balance_usdt += proceeds
        self.portfolio.balance_base = Decimal("0")
        self.portfolio.position = Position.FLAT

        # Update risk management
        if pnl and pnl < 0:
            self.consecutive_losses += 1
            self.daily_losses += 1
            self.daily_loss_amount += abs(pnl)
        elif pnl and pnl > 0:
            self.consecutive_losses = 0

        # Move trade to history
        self.portfolio.trade_history.append(self.portfolio.current_trade)
        self.portfolio.current_trade = None

        self.orders_placed += 1
        self.orders_filled += 1

        # Log order
        self.logger.log_order(
            order_id=order.order_id,
            side=order.side,
            order_type=order.order_type,
            price=float(order.price),
            quantity=float(order.quantity),
            status=order.status,
            timestamp=timestamp,
            fill_price=float(order.fill_price),
            pnl=float(pnl) if pnl else None,
            pnl_pct=pnl_pct,
            extra={
                "fee": float(fee),
                "slippage_bps": order.slippage_bps,
                "balance_usdt_after": float(self.portfolio.balance_usdt),
                "hold_time_seconds": self.portfolio.trade_history[-1].hold_time_seconds,
            }
        )

        return order

    def check_stop_loss(self, current_price: Decimal, timestamp: int) -> bool:
        """Check if stop-loss should be triggered."""
        if self.portfolio.position == Position.FLAT:
            return False

        if not self.portfolio.current_trade:
            return False

        entry_price = self.portfolio.current_trade.entry_order.fill_price
        if not entry_price:
            return False

        stop_loss_pct = Decimal(str(self.risk_management.get("stop_loss_percent", 2.0)))
        loss_pct = (entry_price - current_price) / entry_price * 100

        if loss_pct >= stop_loss_pct:
            self.logger.warning(f"STOP LOSS triggered: {loss_pct:.2f}% loss")
            return True

        return False

    def check_take_profit(self, current_price: Decimal, timestamp: int) -> bool:
        """Check if take-profit should be triggered."""
        if self.portfolio.position == Position.FLAT:
            return False

        if not self.portfolio.current_trade:
            return False

        entry_price = self.portfolio.current_trade.entry_order.fill_price
        if not entry_price:
            return False

        take_profit_pct = Decimal(str(self.risk_management.get("take_profit_percent", 3.0)))
        profit_pct = (current_price - entry_price) / entry_price * 100

        if profit_pct >= take_profit_pct:
            self.logger.info(f"TAKE PROFIT triggered: {profit_pct:.2f}% profit")
            return True

        return False

    def _log_metrics(self, current_price: Decimal, timestamp: int):
        """Log periodic metrics."""
        stats = self.portfolio.get_stats()

        self.logger.log_metrics(
            timestamp=timestamp,
            price=float(current_price),
            position=self.portfolio.position.value,
            balance_usdt=float(self.portfolio.balance_usdt),
            balance_btc=float(self.portfolio.balance_base),
            unrealized_pnl=float(self.portfolio.get_unrealized_pnl(current_price)),
            total_trades=stats["total_trades"],
            win_rate=stats["win_rate"],
            extra={
                "total_pnl": stats["total_pnl"],
                "consecutive_losses": self.consecutive_losses,
                "signals_received": self.signals_received,
            }
        )

    def get_summary(self) -> Dict[str, Any]:
        """Get session summary."""
        stats = self.portfolio.get_stats()

        return {
            "session_id": self.session_id,
            "symbol": self.symbol,
            "initial_balance": float(self.portfolio.initial_balance_usdt),
            "final_balance": float(self.portfolio.balance_usdt),
            "total_return_pct": float(
                (self.portfolio.balance_usdt / self.portfolio.initial_balance_usdt - 1) * 100
            ),
            "signals_received": self.signals_received,
            "orders_placed": self.orders_placed,
            "orders_filled": self.orders_filled,
            **stats,
        }
