"""
Risk Manager - Dynamic TP/SL and Position Sizing for Aggressive Trading

Implements adaptive risk management suitable for high-frequency scalping:
- Dynamic Take Profit and Stop Loss based on volatility and regime
- Position sizing with Kelly Criterion
- Trade duration limits
- Drawdown protection
- Circuit breakers for adverse conditions

Philosophy:
- Volatility-adaptive: wider stops in high vol, tighter in low vol
- Time-based exits: don't let scalps become swing trades
- Protect profits: trail stops when in profit
- Cut losses fast: strict SL enforcement
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict
import numpy as np
import pandas as pd


@dataclass
class TradeConfig:
    """Configuration for aggressive scalping strategy."""

    # Position sizing
    risk_per_trade_pct: float = 1.0  # % of capital to risk per trade
    min_position_usdt: float = 10.0
    max_position_usdt: float = 100.0

    # Base TP/SL (will be adjusted by regime)
    base_take_profit_pct: float = 0.25  # 0.25% base TP
    base_stop_loss_pct: float = 0.20    # 0.20% base SL

    # Regime multipliers
    low_vol_multiplier: float = 0.8     # Tighter TP/SL in low vol
    medium_vol_multiplier: float = 1.0  # Base TP/SL in medium vol
    high_vol_multiplier: float = 1.3    # Wider TP/SL in high vol

    # Time-based exits
    max_hold_time_minutes: int = 30     # Force exit after 30 min
    min_hold_time_seconds: int = 60     # Don't exit before 1 min (avoid noise)

    # Trailing stop
    enable_trailing_stop: bool = True
    trailing_trigger_pct: float = 0.15  # Start trailing after 0.15% profit
    trailing_distance_pct: float = 0.10 # Trail 0.10% behind peak

    # Risk limits
    max_daily_loss_pct: float = -3.0    # Stop trading if lose 3% of capital in a day
    max_drawdown_pct: float = -15.0     # Stop trading if DD exceeds 15%
    max_consecutive_losses: int = 5     # Pause after 5 consecutive losses


@dataclass
class TradeState:
    """State of an active trade."""

    entry_time: datetime
    entry_price: float
    position_size_usdt: float
    side: str  # 'BUY' or 'SELL'
    regime: int  # 0 = low vol, 1 = medium, 2 = high vol

    # Dynamic levels
    stop_loss_price: float
    take_profit_price: float
    peak_profit_pct: float = 0.0  # Track peak profit for trailing
    trailing_stop_price: Optional[float] = None


class RiskManager:
    """
    Adaptive risk manager for aggressive scalping strategies.
    """

    def __init__(self, config: TradeConfig):
        self.config = config

        # Track performance for adaptive adjustments
        self.trades_history = []
        self.current_drawdown_pct = 0.0
        self.daily_pnl = {}
        self.consecutive_losses = 0

    def calculate_tp_sl(
        self,
        entry_price: float,
        side: str,
        vol_regime: int,
        atr_pct: Optional[float] = None
    ) -> Tuple[float, float]:
        """
        Calculate dynamic Take Profit and Stop Loss levels.

        Args:
            entry_price: Entry price of the trade
            side: 'BUY' or 'SELL'
            vol_regime: 0 (low), 1 (medium), 2 (high)
            atr_pct: Optional ATR as % of price for dynamic adjustment

        Returns:
            (take_profit_price, stop_loss_price)
        """

        # Select regime multiplier
        if vol_regime == 0:
            multiplier = self.config.low_vol_multiplier
        elif vol_regime == 1:
            multiplier = self.config.medium_vol_multiplier
        else:  # vol_regime == 2
            multiplier = self.config.high_vol_multiplier

        # Base TP/SL percentages
        tp_pct = self.config.base_take_profit_pct * multiplier
        sl_pct = self.config.base_stop_loss_pct * multiplier

        # If ATR provided, use it to further adjust (optional enhancement)
        if atr_pct is not None:
            # ATR-based adjustment: use ATR as minimum stop distance
            sl_pct = max(sl_pct, atr_pct * 1.5)  # SL at least 1.5x ATR
            tp_pct = max(tp_pct, atr_pct * 2.0)  # TP at least 2x ATR

        # Calculate actual price levels
        if side == 'BUY':
            take_profit_price = entry_price * (1 + tp_pct / 100.0)
            stop_loss_price = entry_price * (1 - sl_pct / 100.0)
        else:  # SELL
            take_profit_price = entry_price * (1 - tp_pct / 100.0)
            stop_loss_price = entry_price * (1 + sl_pct / 100.0)

        return take_profit_price, stop_loss_price

    def calculate_position_size(
        self,
        equity: float,
        win_rate: Optional[float] = None,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None
    ) -> float:
        """
        Calculate optimal position size.

        Uses Kelly Criterion if sufficient trade history exists,
        otherwise uses fixed % of capital.

        Args:
            equity: Current account equity
            win_rate: Historical win rate (0-1)
            avg_win: Average winning trade %
            avg_loss: Average losing trade % (positive number)

        Returns:
            position_size_usdt: Position size in USDT
        """

        # Default: fixed % of equity
        position = equity * (self.config.risk_per_trade_pct / 100.0)

        # If we have enough trade history, use Kelly Criterion
        if win_rate and avg_win and avg_loss and len(self.trades_history) >= 30:
            # Kelly formula: f = (p*b - q) / b
            # where p = win rate, q = 1-p, b = avg_win/avg_loss
            b = avg_win / avg_loss
            kelly_fraction = (win_rate * b - (1 - win_rate)) / b

            # Half-Kelly for safety (more conservative)
            kelly_safe = max(0, kelly_fraction * 0.5)

            # Use Kelly if it suggests less than fixed %
            kelly_position = equity * kelly_safe
            if 0 < kelly_position < position:
                position = kelly_position

        # Apply limits
        position = max(position, self.config.min_position_usdt)
        position = min(position, self.config.max_position_usdt)

        return round(position, 2)

    def should_exit_trade(
        self,
        trade: TradeState,
        current_price: float,
        current_time: datetime
    ) -> Tuple[bool, str]:
        """
        Determine if trade should be exited based on TP/SL and time limits.

        Args:
            trade: Current trade state
            current_price: Current market price
            current_time: Current timestamp

        Returns:
            (should_exit, reason)
        """

        # Calculate current P&L
        if trade.side == 'BUY':
            pnl_pct = ((current_price - trade.entry_price) / trade.entry_price) * 100
        else:  # SELL
            pnl_pct = ((trade.entry_price - current_price) / trade.entry_price) * 100

        # Update peak profit for trailing stop
        if pnl_pct > trade.peak_profit_pct:
            trade.peak_profit_pct = pnl_pct

        # 1. Check Take Profit
        if trade.side == 'BUY' and current_price >= trade.take_profit_price:
            return True, f"TP hit at {current_price:.2f} (+{pnl_pct:.3f}%)"
        elif trade.side == 'SELL' and current_price <= trade.take_profit_price:
            return True, f"TP hit at {current_price:.2f} (+{pnl_pct:.3f}%)"

        # 2. Check Stop Loss
        if trade.side == 'BUY' and current_price <= trade.stop_loss_price:
            return True, f"SL hit at {current_price:.2f} ({pnl_pct:.3f}%)"
        elif trade.side == 'SELL' and current_price >= trade.stop_loss_price:
            return True, f"SL hit at {current_price:.2f} ({pnl_pct:.3f}%)"

        # 3. Check Trailing Stop
        if self.config.enable_trailing_stop and pnl_pct >= self.config.trailing_trigger_pct:
            # Activate trailing stop
            if trade.side == 'BUY':
                trail_price = current_price * (1 - self.config.trailing_distance_pct / 100.0)
                if trade.trailing_stop_price is None or trail_price > trade.trailing_stop_price:
                    trade.trailing_stop_price = trail_price

                if current_price <= trade.trailing_stop_price:
                    return True, f"Trailing SL at {current_price:.2f} (+{pnl_pct:.3f}%)"
            else:  # SELL
                trail_price = current_price * (1 + self.config.trailing_distance_pct / 100.0)
                if trade.trailing_stop_price is None or trail_price < trade.trailing_stop_price:
                    trade.trailing_stop_price = trail_price

                if current_price >= trade.trailing_stop_price:
                    return True, f"Trailing SL at {current_price:.2f} (+{pnl_pct:.3f}%)"

        # 4. Check time-based exit
        hold_time = (current_time - trade.entry_time).total_seconds() / 60.0  # minutes

        if hold_time >= self.config.max_hold_time_minutes:
            return True, f"Max hold time ({self.config.max_hold_time_minutes}min) reached. PnL: {pnl_pct:.3f}%"

        # 5. Don't exit too early (avoid noise)
        if hold_time < (self.config.min_hold_time_seconds / 60.0):
            return False, "Within minimum hold time"

        return False, "No exit condition met"

    def can_open_new_trade(
        self,
        current_equity: float,
        starting_equity: float,
        peak_equity: float,
        current_date: str
    ) -> Tuple[bool, str]:
        """
        Check if new trade can be opened based on risk limits.

        Args:
            current_equity: Current account balance
            starting_equity: Initial account balance
            peak_equity: Historical peak equity
            current_date: Current date (YYYY-MM-DD)

        Returns:
            (can_trade, reason)
        """

        # 1. Check daily loss limit
        if current_date in self.daily_pnl:
            daily_pnl_pct = (self.daily_pnl[current_date] / starting_equity) * 100
            if daily_pnl_pct <= self.config.max_daily_loss_pct:
                return False, f"Daily loss limit hit: {daily_pnl_pct:.2f}%"

        # 2. Check max drawdown
        current_dd_pct = ((current_equity - peak_equity) / peak_equity) * 100
        if current_dd_pct <= self.config.max_drawdown_pct:
            return False, f"Max drawdown exceeded: {current_dd_pct:.2f}%"

        # 3. Check consecutive losses circuit breaker
        if self.consecutive_losses >= self.config.max_consecutive_losses:
            return False, f"Circuit breaker: {self.consecutive_losses} consecutive losses"

        return True, "OK to trade"

    def record_trade(
        self,
        pnl_usdt: float,
        pnl_pct: float,
        trade_date: str
    ):
        """
        Record completed trade for performance tracking.

        Args:
            pnl_usdt: P&L in USDT
            pnl_pct: P&L as percentage
            trade_date: Date of trade (YYYY-MM-DD)
        """

        self.trades_history.append({
            'pnl_usdt': pnl_usdt,
            'pnl_pct': pnl_pct,
            'date': trade_date
        })

        # Update daily PnL
        if trade_date not in self.daily_pnl:
            self.daily_pnl[trade_date] = 0.0
        self.daily_pnl[trade_date] += pnl_usdt

        # Track consecutive losses
        if pnl_usdt > 0:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1

    def get_performance_stats(self) -> Dict:
        """
        Get current performance statistics.

        Returns:
            dict with win_rate, avg_win, avg_loss, etc.
        """

        if not self.trades_history:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'consecutive_losses': 0
            }

        pnls = [t['pnl_pct'] for t in self.trades_history]
        wins = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p <= 0]

        return {
            'total_trades': len(self.trades_history),
            'win_rate': len(wins) / len(self.trades_history) if self.trades_history else 0.0,
            'avg_win': np.mean(wins) if wins else 0.0,
            'avg_loss': np.mean(losses) if losses else 0.0,
            'consecutive_losses': self.consecutive_losses
        }


if __name__ == "__main__":
    """Test the risk manager."""

    print("=" * 80)
    print("Risk Manager - Test Mode")
    print("=" * 80)

    # Create config
    config = TradeConfig(
        risk_per_trade_pct=1.0,
        base_take_profit_pct=0.25,
        base_stop_loss_pct=0.20
    )

    rm = RiskManager(config)

    # Test TP/SL calculation
    print("\n🧪 Test 1: TP/SL Calculation")
    print("-" * 80)

    entry_price = 50000.0
    for regime in [0, 1, 2]:
        tp, sl = rm.calculate_tp_sl(entry_price, 'BUY', regime)
        regime_name = ['Low Vol', 'Medium Vol', 'High Vol'][regime]
        print(f"{regime_name:12} | Entry: ${entry_price:,.0f} | TP: ${tp:,.2f} | SL: ${sl:,.2f}")

    # Test position sizing
    print("\n🧪 Test 2: Position Sizing")
    print("-" * 80)

    equity = 1000.0
    position = rm.calculate_position_size(equity)
    print(f"Equity: ${equity:.2f} | Position Size: ${position:.2f}")

    # Test with Kelly
    position_kelly = rm.calculate_position_size(equity, win_rate=0.6, avg_win=0.3, avg_loss=0.2)
    print(f"Equity: ${equity:.2f} | Kelly Position: ${position_kelly:.2f}")

    # Test trade exit logic
    print("\n🧪 Test 3: Trade Exit Logic")
    print("-" * 80)

    trade = TradeState(
        entry_time=datetime.now(),
        entry_price=50000.0,
        position_size_usdt=50.0,
        side='BUY',
        regime=1,
        stop_loss_price=49900.0,
        take_profit_price=50125.0
    )

    test_prices = [50050, 50125, 49900, 50200]
    for price in test_prices:
        should_exit, reason = rm.should_exit_trade(trade, price, datetime.now())
        print(f"Price: ${price:,.0f} | Exit: {should_exit:5} | Reason: {reason}")

    print("\n✅ All tests completed!")
