"""
Risk Management Module

Implements:
- Stop-Loss: Close position when loss exceeds threshold
- Take-Profit: Close position when profit exceeds threshold
- Circuit Breaker: Pause trading after consecutive losses
- Position Tracking: Track entry prices and P&L
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path
import json

log = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents an open trading position"""
    entry_price: Decimal
    entry_time: datetime
    side: str  # "BUY" or "SELL"
    quantity: Decimal = Decimal("0")
    symbol: str = "BTCUSDT"

    def unrealized_pnl_percent(self, current_price: Decimal) -> float:
        """Calculate unrealized P&L in percentage"""
        if self.entry_price == 0:
            return 0.0

        if self.side == "BUY":
            # Long position: profit when price goes up
            return float((current_price - self.entry_price) / self.entry_price * 100)
        else:
            # Short position: profit when price goes down
            return float((self.entry_price - current_price) / self.entry_price * 100)

    def unrealized_pnl_absolute(self, current_price: Decimal) -> Decimal:
        """Calculate unrealized P&L in absolute terms"""
        if self.side == "BUY":
            return (current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - current_price) * self.quantity


@dataclass
class TradeResult:
    """Result of a completed trade"""
    entry_price: Decimal
    exit_price: Decimal
    entry_time: datetime
    exit_time: datetime
    side: str
    pnl_percent: float
    pnl_absolute: Decimal
    exit_reason: str  # "signal", "stop_loss", "take_profit", "circuit_breaker"


class CircuitBreaker:
    """
    Pauses trading after N consecutive losses.

    Features:
    - Tracks consecutive losses
    - Cooldown period after triggering
    - Auto-reset after cooldown or winning trade
    """

    def __init__(
        self,
        max_consecutive_losses: int = 3,
        cooldown_minutes: int = 60,
        max_daily_losses: int = 5,
        max_daily_loss_percent: float = 10.0
    ):
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_minutes = cooldown_minutes
        self.max_daily_losses = max_daily_losses
        self.max_daily_loss_percent = max_daily_loss_percent

        self.consecutive_losses = 0
        self.daily_losses = 0
        self.daily_loss_percent = 0.0
        self.last_reset_date = datetime.now().date()
        self.cooldown_until: Optional[datetime] = None
        self.is_triggered = False

    def record_trade(self, pnl_percent: float) -> None:
        """Record a trade result and update circuit breaker state"""
        # Reset daily counters if new day
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.daily_losses = 0
            self.daily_loss_percent = 0.0
            self.last_reset_date = today
            log.info("Circuit breaker: Daily counters reset")

        if pnl_percent < 0:
            self.consecutive_losses += 1
            self.daily_losses += 1
            self.daily_loss_percent += abs(pnl_percent)

            log.warning(
                "Circuit breaker: Loss recorded. Consecutive: %d/%d, Daily: %d/%d, Daily %%: %.2f%%/%.2f%%",
                self.consecutive_losses, self.max_consecutive_losses,
                self.daily_losses, self.max_daily_losses,
                self.daily_loss_percent, self.max_daily_loss_percent
            )

            # Check if we should trigger
            if self.consecutive_losses >= self.max_consecutive_losses:
                self._trigger("consecutive losses")
            elif self.daily_losses >= self.max_daily_losses:
                self._trigger("daily loss count")
            elif self.daily_loss_percent >= self.max_daily_loss_percent:
                self._trigger("daily loss percent")
        else:
            # Winning trade resets consecutive losses
            self.consecutive_losses = 0
            log.info("Circuit breaker: Win recorded. Consecutive losses reset.")

    def _trigger(self, reason: str) -> None:
        """Trigger the circuit breaker"""
        self.is_triggered = True
        self.cooldown_until = datetime.now() + timedelta(minutes=self.cooldown_minutes)
        log.warning(
            "🚨 CIRCUIT BREAKER TRIGGERED: %s. Trading paused until %s",
            reason, self.cooldown_until.strftime("%Y-%m-%d %H:%M:%S")
        )

    def is_trading_allowed(self) -> bool:
        """Check if trading is currently allowed"""
        if not self.is_triggered:
            return True

        if self.cooldown_until and datetime.now() >= self.cooldown_until:
            # Cooldown expired, reset
            self.is_triggered = False
            self.consecutive_losses = 0
            self.cooldown_until = None
            log.info("Circuit breaker: Cooldown expired. Trading resumed.")
            return True

        return False

    def time_until_reset(self) -> Optional[timedelta]:
        """Return time remaining until cooldown expires"""
        if self.cooldown_until:
            remaining = self.cooldown_until - datetime.now()
            return remaining if remaining.total_seconds() > 0 else None
        return None

    def get_status(self) -> Dict[str, Any]:
        """Return current circuit breaker status"""
        return {
            "is_triggered": self.is_triggered,
            "consecutive_losses": self.consecutive_losses,
            "daily_losses": self.daily_losses,
            "daily_loss_percent": self.daily_loss_percent,
            "cooldown_until": self.cooldown_until.isoformat() if self.cooldown_until else None,
            "trading_allowed": self.is_trading_allowed()
        }


class RiskManager:
    """
    Main risk management class.

    Handles:
    - Stop-loss monitoring and execution
    - Take-profit monitoring and execution
    - Circuit breaker integration
    - Position tracking
    - Trade logging
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize risk manager with configuration.

        Config parameters:
        - stop_loss_percent: float (default: 2.0)
        - take_profit_percent: float (default: 3.0)
        - trailing_stop_percent: float (optional, default: None)
        - circuit_breaker: dict with CircuitBreaker params
        """
        self.config = config
        risk_config = config.get("risk_management", {})

        # Stop-loss / Take-profit thresholds
        self.stop_loss_percent = risk_config.get("stop_loss_percent", 2.0)
        self.take_profit_percent = risk_config.get("take_profit_percent", 3.0)
        self.trailing_stop_percent = risk_config.get("trailing_stop_percent")
        self.trailing_stop_activation = risk_config.get("trailing_stop_activation", 1.0)

        # Initialize circuit breaker
        cb_config = risk_config.get("circuit_breaker", {})
        self.circuit_breaker = CircuitBreaker(
            max_consecutive_losses=cb_config.get("max_consecutive_losses", 3),
            cooldown_minutes=cb_config.get("cooldown_minutes", 60),
            max_daily_losses=cb_config.get("max_daily_losses", 5),
            max_daily_loss_percent=cb_config.get("max_daily_loss_percent", 10.0)
        )

        # Current position
        self.current_position: Optional[Position] = None
        self.highest_price_since_entry: Decimal = Decimal("0")
        self.lowest_price_since_entry: Decimal = Decimal("999999999")

        # Trade history
        self.trade_history: list[TradeResult] = []

        # State persistence
        self.state_file = Path(config.get("data_folder", ".")) / config.get("symbol", "BTCUSDT") / "risk_state.json"

        # Load previous state if exists
        self._load_state()

        log.info(
            "RiskManager initialized: SL=%.2f%%, TP=%.2f%%, Trailing=%s",
            self.stop_loss_percent,
            self.take_profit_percent,
            f"{self.trailing_stop_percent}%" if self.trailing_stop_percent else "OFF"
        )

    def open_position(self, entry_price: Decimal, side: str, quantity: Decimal = Decimal("0")) -> None:
        """Record opening a new position"""
        self.current_position = Position(
            entry_price=entry_price,
            entry_time=datetime.now(),
            side=side,
            quantity=quantity,
            symbol=self.config.get("symbol", "BTCUSDT")
        )
        self.highest_price_since_entry = entry_price
        self.lowest_price_since_entry = entry_price

        log.info(
            "Position opened: %s at %s, qty=%s",
            side, entry_price, quantity
        )
        self._save_state()

    def close_position(self, exit_price: Decimal, exit_reason: str = "signal") -> Optional[TradeResult]:
        """Record closing a position and return the trade result"""
        if not self.current_position:
            log.warning("Attempted to close position but no position is open")
            return None

        pos = self.current_position
        pnl_percent = pos.unrealized_pnl_percent(exit_price)
        pnl_absolute = pos.unrealized_pnl_absolute(exit_price)

        result = TradeResult(
            entry_price=pos.entry_price,
            exit_price=exit_price,
            entry_time=pos.entry_time,
            exit_time=datetime.now(),
            side=pos.side,
            pnl_percent=pnl_percent,
            pnl_absolute=pnl_absolute,
            exit_reason=exit_reason
        )

        self.trade_history.append(result)
        self.circuit_breaker.record_trade(pnl_percent)

        log.info(
            "Position closed: %s exit at %s, P&L: %.2f%% (%s), reason: %s",
            pos.side, exit_price, pnl_percent, pnl_absolute, exit_reason
        )

        self.current_position = None
        self.highest_price_since_entry = Decimal("0")
        self.lowest_price_since_entry = Decimal("999999999")

        self._save_state()
        return result

    def update_price(self, current_price: Decimal) -> None:
        """Update price tracking for trailing stop"""
        if current_price > self.highest_price_since_entry:
            self.highest_price_since_entry = current_price
        if current_price < self.lowest_price_since_entry:
            self.lowest_price_since_entry = current_price

    def check_exit_conditions(self, current_price: Decimal) -> Optional[str]:
        """
        Check if any exit condition is met.

        Returns:
            - "stop_loss" if stop-loss triggered
            - "take_profit" if take-profit triggered
            - "trailing_stop" if trailing stop triggered
            - None if no exit condition met
        """
        if not self.current_position:
            return None

        self.update_price(current_price)
        pos = self.current_position
        pnl_percent = pos.unrealized_pnl_percent(current_price)

        # Check stop-loss
        if pnl_percent <= -self.stop_loss_percent:
            log.warning(
                "🛑 STOP-LOSS TRIGGERED: P&L %.2f%% <= -%.2f%%",
                pnl_percent, self.stop_loss_percent
            )
            return "stop_loss"

        # Check take-profit
        if pnl_percent >= self.take_profit_percent:
            log.info(
                "🎯 TAKE-PROFIT TRIGGERED: P&L %.2f%% >= %.2f%%",
                pnl_percent, self.take_profit_percent
            )
            return "take_profit"

        # Check trailing stop (only if configured and profit > activation threshold)
        if self.trailing_stop_percent and pnl_percent >= self.trailing_stop_activation:
            if pos.side == "BUY":
                # Long position: trailing stop based on highest price
                trailing_stop_price = self.highest_price_since_entry * (1 - Decimal(str(self.trailing_stop_percent)) / 100)
                if current_price <= trailing_stop_price:
                    log.info(
                        "📉 TRAILING STOP TRIGGERED: Price %s <= trailing stop %s (highest: %s)",
                        current_price, trailing_stop_price, self.highest_price_since_entry
                    )
                    return "trailing_stop"
            else:
                # Short position: trailing stop based on lowest price
                trailing_stop_price = self.lowest_price_since_entry * (1 + Decimal(str(self.trailing_stop_percent)) / 100)
                if current_price >= trailing_stop_price:
                    log.info(
                        "📈 TRAILING STOP TRIGGERED: Price %s >= trailing stop %s (lowest: %s)",
                        current_price, trailing_stop_price, self.lowest_price_since_entry
                    )
                    return "trailing_stop"

        return None

    def is_trading_allowed(self) -> bool:
        """Check if trading is allowed (circuit breaker not triggered)"""
        return self.circuit_breaker.is_trading_allowed()

    def get_position_status(self, current_price: Decimal) -> Dict[str, Any]:
        """Get current position status"""
        if not self.current_position:
            return {"has_position": False}

        pos = self.current_position
        pnl_percent = pos.unrealized_pnl_percent(current_price)

        return {
            "has_position": True,
            "side": pos.side,
            "entry_price": str(pos.entry_price),
            "entry_time": pos.entry_time.isoformat(),
            "current_price": str(current_price),
            "unrealized_pnl_percent": pnl_percent,
            "unrealized_pnl_absolute": str(pos.unrealized_pnl_absolute(current_price)),
            "highest_since_entry": str(self.highest_price_since_entry),
            "lowest_since_entry": str(self.lowest_price_since_entry),
            "stop_loss_at": str(pos.entry_price * (1 - Decimal(str(self.stop_loss_percent)) / 100)),
            "take_profit_at": str(pos.entry_price * (1 + Decimal(str(self.take_profit_percent)) / 100)),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get trading statistics"""
        if not self.trade_history:
            return {"total_trades": 0}

        wins = [t for t in self.trade_history if t.pnl_percent > 0]
        losses = [t for t in self.trade_history if t.pnl_percent <= 0]

        total_pnl = sum(t.pnl_percent for t in self.trade_history)
        avg_win = sum(t.pnl_percent for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.pnl_percent for t in losses) / len(losses) if losses else 0

        return {
            "total_trades": len(self.trade_history),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(self.trade_history) * 100 if self.trade_history else 0,
            "total_pnl_percent": total_pnl,
            "avg_win_percent": avg_win,
            "avg_loss_percent": avg_loss,
            "profit_factor": abs(avg_win / avg_loss) if avg_loss != 0 else float('inf'),
            "circuit_breaker": self.circuit_breaker.get_status(),
            "exit_reasons": {
                "signal": len([t for t in self.trade_history if t.exit_reason == "signal"]),
                "stop_loss": len([t for t in self.trade_history if t.exit_reason == "stop_loss"]),
                "take_profit": len([t for t in self.trade_history if t.exit_reason == "take_profit"]),
                "trailing_stop": len([t for t in self.trade_history if t.exit_reason == "trailing_stop"]),
            }
        }

    def _save_state(self) -> None:
        """Save current state to file"""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            state = {
                "current_position": None,
                "circuit_breaker": {
                    "consecutive_losses": self.circuit_breaker.consecutive_losses,
                    "daily_losses": self.circuit_breaker.daily_losses,
                    "daily_loss_percent": self.circuit_breaker.daily_loss_percent,
                    "is_triggered": self.circuit_breaker.is_triggered,
                    "cooldown_until": self.circuit_breaker.cooldown_until.isoformat() if self.circuit_breaker.cooldown_until else None,
                },
                "highest_price_since_entry": str(self.highest_price_since_entry),
                "lowest_price_since_entry": str(self.lowest_price_since_entry),
            }

            if self.current_position:
                state["current_position"] = {
                    "entry_price": str(self.current_position.entry_price),
                    "entry_time": self.current_position.entry_time.isoformat(),
                    "side": self.current_position.side,
                    "quantity": str(self.current_position.quantity),
                    "symbol": self.current_position.symbol,
                }

            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)

        except Exception as e:
            log.error("Failed to save risk state: %s", e)

    def _load_state(self) -> None:
        """Load previous state from file"""
        try:
            if not self.state_file.exists():
                return

            with open(self.state_file, "r") as f:
                state = json.load(f)

            # Restore circuit breaker state
            cb_state = state.get("circuit_breaker", {})
            self.circuit_breaker.consecutive_losses = cb_state.get("consecutive_losses", 0)
            self.circuit_breaker.daily_losses = cb_state.get("daily_losses", 0)
            self.circuit_breaker.daily_loss_percent = cb_state.get("daily_loss_percent", 0.0)
            self.circuit_breaker.is_triggered = cb_state.get("is_triggered", False)
            if cb_state.get("cooldown_until"):
                self.circuit_breaker.cooldown_until = datetime.fromisoformat(cb_state["cooldown_until"])

            # Restore position
            pos_state = state.get("current_position")
            if pos_state:
                self.current_position = Position(
                    entry_price=Decimal(pos_state["entry_price"]),
                    entry_time=datetime.fromisoformat(pos_state["entry_time"]),
                    side=pos_state["side"],
                    quantity=Decimal(pos_state.get("quantity", "0")),
                    symbol=pos_state.get("symbol", "BTCUSDT"),
                )
                self.highest_price_since_entry = Decimal(state.get("highest_price_since_entry", "0"))
                self.lowest_price_since_entry = Decimal(state.get("lowest_price_since_entry", "999999999"))

            log.info("Risk state loaded from %s", self.state_file)

        except Exception as e:
            log.error("Failed to load risk state: %s", e)
