"""
Shadow Mode Real-Time Analyzer

Analyzes shadow trading performance in real-time and suggests
config adjustments based on observed patterns.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import statistics

from shadow.shadow_logger import ShadowLogger


@dataclass
class PerformanceWindow:
    """Rolling window of performance metrics."""
    window_size: int = 100  # Number of trades to track
    trades: List[Dict[str, Any]] = field(default_factory=list)
    signals: List[Dict[str, Any]] = field(default_factory=list)

    def add_trade(self, trade: Dict[str, Any]):
        """Add a trade to the window."""
        self.trades.append(trade)
        if len(self.trades) > self.window_size:
            self.trades.pop(0)

    def add_signal(self, signal: Dict[str, Any]):
        """Add a signal to the window."""
        self.signals.append(signal)
        if len(self.signals) > self.window_size * 10:  # Keep more signals
            self.signals.pop(0)

    def get_win_rate(self) -> float:
        """Calculate win rate from trades."""
        if not self.trades:
            return 0.0
        wins = sum(1 for t in self.trades if t.get("pnl", 0) > 0)
        return wins / len(self.trades) * 100

    def get_avg_pnl(self) -> float:
        """Calculate average PnL."""
        if not self.trades:
            return 0.0
        pnls = [t.get("pnl", 0) for t in self.trades]
        return statistics.mean(pnls)

    def get_profit_factor(self) -> float:
        """Calculate profit factor (gross profit / gross loss)."""
        if not self.trades:
            return 0.0
        gross_profit = sum(t.get("pnl", 0) for t in self.trades if t.get("pnl", 0) > 0)
        gross_loss = abs(sum(t.get("pnl", 0) for t in self.trades if t.get("pnl", 0) < 0))
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    def get_avg_hold_time(self) -> float:
        """Calculate average hold time in seconds."""
        hold_times = [t.get("hold_time_seconds", 0) for t in self.trades if t.get("hold_time_seconds")]
        if not hold_times:
            return 0.0
        return statistics.mean(hold_times)

    def get_signal_accuracy(self) -> Dict[str, float]:
        """Calculate signal accuracy (how often signals lead to profitable trades)."""
        buy_signals = [s for s in self.signals if s.get("signal") == "BUY"]
        sell_signals = [s for s in self.signals if s.get("signal") == "SELL"]

        # Match signals to trades by timestamp proximity
        buy_accuracy = self._match_signals_to_trades(buy_signals, "BUY")
        sell_accuracy = self._match_signals_to_trades(sell_signals, "SELL")

        return {
            "buy_accuracy": buy_accuracy,
            "sell_accuracy": sell_accuracy,
        }

    def _match_signals_to_trades(self, signals: List[Dict], side: str) -> float:
        """Match signals to trades and calculate accuracy."""
        if not signals or not self.trades:
            return 0.0

        matched = 0
        profitable = 0

        for signal in signals:
            signal_ts = signal.get("timestamp", 0)
            # Find trade within 5 minutes of signal
            for trade in self.trades:
                trade_ts = trade.get("timestamp", 0)
                if abs(trade_ts - signal_ts) < 300000:  # 5 min
                    matched += 1
                    if trade.get("pnl", 0) > 0:
                        profitable += 1
                    break

        if matched == 0:
            return 0.0
        return profitable / matched * 100


@dataclass
class ConfigSuggestion:
    """A suggestion to modify config based on analysis."""
    parameter: str
    current_value: Any
    suggested_value: Any
    reason: str
    confidence: float  # 0-1
    priority: int  # 1=high, 2=medium, 3=low

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parameter": self.parameter,
            "current_value": self.current_value,
            "suggested_value": self.suggested_value,
            "reason": self.reason,
            "confidence": self.confidence,
            "priority": self.priority,
        }


class ShadowAnalyzer:
    """
    Real-time analyzer for shadow trading sessions.

    Monitors performance metrics and suggests config adjustments
    based on observed patterns.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        logger: ShadowLogger,
        analysis_interval: int = 60,  # Minutes between analyses
    ):
        self.config = config
        self.logger = logger
        self.analysis_interval = analysis_interval

        # Performance tracking
        self.performance = PerformanceWindow(window_size=100)

        # Price tracking for volatility
        self.price_history: List[Tuple[int, float]] = []
        self.max_price_history = 1440  # 24 hours of 1m candles

        # Analysis state
        self.last_analysis_time: Optional[int] = None
        self.suggestions: List[ConfigSuggestion] = []

        # Thresholds for generating suggestions
        self.thresholds = {
            "min_trades_for_analysis": 20,
            "low_win_rate": 45.0,
            "high_win_rate": 70.0,
            "low_profit_factor": 1.0,
            "high_profit_factor": 2.0,
            "short_hold_time": 60,  # seconds
            "long_hold_time": 7200,  # 2 hours
        }

    def record_price(self, timestamp: int, price: float):
        """Record a price point for volatility tracking."""
        self.price_history.append((timestamp, price))
        if len(self.price_history) > self.max_price_history:
            self.price_history.pop(0)

    def record_signal(self, signal: Dict[str, Any]):
        """Record a trading signal."""
        self.performance.add_signal(signal)

    def record_trade(self, trade: Dict[str, Any]):
        """Record a completed trade."""
        self.performance.add_trade(trade)

    def calculate_volatility(self, periods: int = 60) -> float:
        """Calculate recent volatility (standard deviation of returns)."""
        if len(self.price_history) < periods + 1:
            return 0.0

        recent = self.price_history[-periods:]
        returns = []
        for i in range(1, len(recent)):
            ret = (recent[i][1] / recent[i-1][1] - 1) * 100
            returns.append(ret)

        if not returns:
            return 0.0

        return statistics.stdev(returns)

    def analyze(self, current_price: float, timestamp: int) -> List[ConfigSuggestion]:
        """
        Perform analysis and generate suggestions if needed.

        Returns list of suggestions for config adjustments.
        """
        # Check if enough time has passed since last analysis
        if self.last_analysis_time:
            elapsed_minutes = (timestamp - self.last_analysis_time) / 60000
            if elapsed_minutes < self.analysis_interval:
                return []

        self.last_analysis_time = timestamp
        self.suggestions.clear()

        # Need minimum trades for meaningful analysis
        if len(self.performance.trades) < self.thresholds["min_trades_for_analysis"]:
            return []

        self.logger.info(f"Running shadow analysis with {len(self.performance.trades)} trades")

        # Analyze various aspects
        self._analyze_win_rate()
        self._analyze_profit_factor()
        self._analyze_hold_time()
        self._analyze_signal_thresholds()
        self._analyze_position_sizing()
        self._analyze_stop_loss()
        self._analyze_take_profit()
        self._analyze_volatility(current_price)

        # Log suggestions
        for suggestion in self.suggestions:
            self.logger.log_config_suggestion(
                parameter=suggestion.parameter,
                current_value=suggestion.current_value,
                suggested_value=suggestion.suggested_value,
                reason=suggestion.reason,
                confidence=suggestion.confidence,
            )

        return self.suggestions

    def _analyze_win_rate(self):
        """Analyze win rate and suggest adjustments."""
        win_rate = self.performance.get_win_rate()

        if win_rate < self.thresholds["low_win_rate"]:
            # Win rate too low - suggest tightening entry conditions
            current_buy_threshold = self.config.get("signal_sets", [{}])[-1].get(
                "config", {}
            ).get("parameters", {}).get("buy_signal_threshold", 0.002)

            # Suggest higher threshold (more selective)
            suggested = current_buy_threshold * 1.5

            self.suggestions.append(ConfigSuggestion(
                parameter="buy_signal_threshold",
                current_value=current_buy_threshold,
                suggested_value=round(suggested, 4),
                reason=f"Win rate {win_rate:.1f}% is below {self.thresholds['low_win_rate']}%. "
                       f"Consider more selective entry.",
                confidence=0.7,
                priority=1,
            ))

        elif win_rate > self.thresholds["high_win_rate"]:
            # Win rate very high - could be too conservative
            current_buy_threshold = self.config.get("signal_sets", [{}])[-1].get(
                "config", {}
            ).get("parameters", {}).get("buy_signal_threshold", 0.002)

            # Suggest lower threshold (more opportunities)
            suggested = current_buy_threshold * 0.7

            self.suggestions.append(ConfigSuggestion(
                parameter="buy_signal_threshold",
                current_value=current_buy_threshold,
                suggested_value=round(suggested, 4),
                reason=f"Win rate {win_rate:.1f}% is very high. "
                       f"Could capture more opportunities with looser threshold.",
                confidence=0.5,
                priority=3,
            ))

    def _analyze_profit_factor(self):
        """Analyze profit factor."""
        pf = self.performance.get_profit_factor()

        if pf < self.thresholds["low_profit_factor"]:
            # Not profitable - suggest reviewing strategy
            self.suggestions.append(ConfigSuggestion(
                parameter="strategy_review",
                current_value="current",
                suggested_value="review_needed",
                reason=f"Profit factor {pf:.2f} is below 1.0 (losing money). "
                       f"Strategy review recommended.",
                confidence=0.9,
                priority=1,
            ))

    def _analyze_hold_time(self):
        """Analyze average hold time."""
        avg_hold = self.performance.get_avg_hold_time()

        if avg_hold < self.thresholds["short_hold_time"]:
            # Holding too short - might be getting stopped out too quickly
            current_sl = self.config.get("risk_management", {}).get("stop_loss_percent", 2.0)

            self.suggestions.append(ConfigSuggestion(
                parameter="stop_loss_percent",
                current_value=current_sl,
                suggested_value=current_sl * 1.2,
                reason=f"Average hold time {avg_hold:.0f}s is very short. "
                       f"Trades may be getting stopped out too quickly.",
                confidence=0.6,
                priority=2,
            ))

        elif avg_hold > self.thresholds["long_hold_time"]:
            # Holding too long - might need tighter take profit
            current_tp = self.config.get("risk_management", {}).get("take_profit_percent", 3.0)

            self.suggestions.append(ConfigSuggestion(
                parameter="take_profit_percent",
                current_value=current_tp,
                suggested_value=current_tp * 0.8,
                reason=f"Average hold time {avg_hold/60:.0f}min is long. "
                       f"Consider tighter take profit.",
                confidence=0.5,
                priority=3,
            ))

    def _analyze_signal_thresholds(self):
        """Analyze signal accuracy and suggest threshold adjustments."""
        accuracy = self.performance.get_signal_accuracy()

        buy_acc = accuracy.get("buy_accuracy", 0)
        sell_acc = accuracy.get("sell_accuracy", 0)

        if buy_acc < 40:
            current_threshold = 0.002  # Default
            self.suggestions.append(ConfigSuggestion(
                parameter="buy_signal_threshold",
                current_value=current_threshold,
                suggested_value=current_threshold * 1.3,
                reason=f"Buy signal accuracy {buy_acc:.1f}% is low. "
                       f"Raise threshold to filter weak signals.",
                confidence=0.65,
                priority=2,
            ))

        if sell_acc < 40:
            current_threshold = -0.002  # Default
            self.suggestions.append(ConfigSuggestion(
                parameter="sell_signal_threshold",
                current_value=current_threshold,
                suggested_value=current_threshold * 1.3,
                reason=f"Sell signal accuracy {sell_acc:.1f}% is low. "
                       f"Adjust threshold to filter weak signals.",
                confidence=0.65,
                priority=2,
            ))

    def _analyze_position_sizing(self):
        """Analyze position sizing based on performance."""
        stats = {
            "win_rate": self.performance.get_win_rate(),
            "profit_factor": self.performance.get_profit_factor(),
            "avg_pnl": self.performance.get_avg_pnl(),
        }

        current_pct = self.config.get("trade_model", {}).get("percentage_used_for_trade", 2.0)

        # If performing well, could increase size
        if stats["win_rate"] > 55 and stats["profit_factor"] > 1.5:
            suggested = min(current_pct * 1.2, 5.0)  # Cap at 5%
            self.suggestions.append(ConfigSuggestion(
                parameter="percentage_used_for_trade",
                current_value=current_pct,
                suggested_value=round(suggested, 1),
                reason=f"Strong performance (WR={stats['win_rate']:.1f}%, PF={stats['profit_factor']:.2f}). "
                       f"Could increase position size.",
                confidence=0.6,
                priority=3,
            ))

        # If performing poorly, reduce size
        elif stats["win_rate"] < 45 or stats["profit_factor"] < 0.8:
            suggested = max(current_pct * 0.7, 1.0)  # Floor at 1%
            self.suggestions.append(ConfigSuggestion(
                parameter="percentage_used_for_trade",
                current_value=current_pct,
                suggested_value=round(suggested, 1),
                reason=f"Poor performance (WR={stats['win_rate']:.1f}%, PF={stats['profit_factor']:.2f}). "
                       f"Reduce position size to limit losses.",
                confidence=0.75,
                priority=1,
            ))

    def _analyze_stop_loss(self):
        """Analyze stop loss effectiveness."""
        if len(self.performance.trades) < 10:
            return

        # Look at losing trades
        losses = [t for t in self.performance.trades if t.get("pnl", 0) < 0]
        if not losses:
            return

        loss_pcts = [abs(t.get("pnl_pct", 0)) for t in losses]
        avg_loss = statistics.mean(loss_pcts)
        max_loss = max(loss_pcts)

        current_sl = self.config.get("risk_management", {}).get("stop_loss_percent", 2.0)

        # If average loss is much smaller than stop loss, could tighten
        if avg_loss < current_sl * 0.5:
            suggested = max(avg_loss * 1.3, 1.0)
            self.suggestions.append(ConfigSuggestion(
                parameter="stop_loss_percent",
                current_value=current_sl,
                suggested_value=round(suggested, 1),
                reason=f"Average loss {avg_loss:.1f}% is well below stop loss {current_sl}%. "
                       f"Could tighten stop loss.",
                confidence=0.55,
                priority=3,
            ))

        # If max loss exceeds stop loss, stop loss isn't working
        if max_loss > current_sl * 1.2:
            self.suggestions.append(ConfigSuggestion(
                parameter="stop_loss_implementation",
                current_value="current",
                suggested_value="check_execution",
                reason=f"Max loss {max_loss:.1f}% exceeds stop loss {current_sl}%. "
                       f"Check stop loss execution.",
                confidence=0.8,
                priority=1,
            ))

    def _analyze_take_profit(self):
        """Analyze take profit effectiveness."""
        if len(self.performance.trades) < 10:
            return

        # Look at winning trades
        wins = [t for t in self.performance.trades if t.get("pnl", 0) > 0]
        if not wins:
            return

        win_pcts = [t.get("pnl_pct", 0) for t in wins]
        avg_win = statistics.mean(win_pcts)
        max_win = max(win_pcts)

        current_tp = self.config.get("risk_management", {}).get("take_profit_percent", 3.0)

        # If average win is close to take profit, it's working well
        if avg_win > current_tp * 0.8:
            return  # Working as expected

        # If average win is much smaller, might be taking profit too early manually
        if avg_win < current_tp * 0.3:
            suggested = avg_win * 1.2
            self.suggestions.append(ConfigSuggestion(
                parameter="take_profit_percent",
                current_value=current_tp,
                suggested_value=round(suggested, 1),
                reason=f"Average win {avg_win:.1f}% is well below take profit {current_tp}%. "
                       f"Consider lowering take profit target.",
                confidence=0.5,
                priority=3,
            ))

    def _analyze_volatility(self, current_price: float):
        """Analyze current volatility and suggest adjustments."""
        vol_1h = self.calculate_volatility(60)
        vol_4h = self.calculate_volatility(240)

        if vol_1h == 0 or vol_4h == 0:
            return

        # High volatility - widen stops
        if vol_1h > 0.5:  # High volatility
            current_sl = self.config.get("risk_management", {}).get("stop_loss_percent", 2.0)
            suggested = min(current_sl * 1.3, 5.0)

            self.suggestions.append(ConfigSuggestion(
                parameter="stop_loss_percent",
                current_value=current_sl,
                suggested_value=round(suggested, 1),
                reason=f"High volatility ({vol_1h:.2f}% 1h stdev). "
                       f"Widen stop loss to avoid noise.",
                confidence=0.6,
                priority=2,
            ))

        # Low volatility - tighten stops
        elif vol_1h < 0.1:  # Low volatility
            current_sl = self.config.get("risk_management", {}).get("stop_loss_percent", 2.0)
            suggested = max(current_sl * 0.7, 1.0)

            self.suggestions.append(ConfigSuggestion(
                parameter="stop_loss_percent",
                current_value=current_sl,
                suggested_value=round(suggested, 1),
                reason=f"Low volatility ({vol_1h:.2f}% 1h stdev). "
                       f"Could tighten stop loss.",
                confidence=0.5,
                priority=3,
            ))

    def get_summary(self) -> Dict[str, Any]:
        """Get analyzer summary."""
        return {
            "total_trades_analyzed": len(self.performance.trades),
            "total_signals_tracked": len(self.performance.signals),
            "win_rate": self.performance.get_win_rate(),
            "profit_factor": self.performance.get_profit_factor(),
            "avg_pnl": self.performance.get_avg_pnl(),
            "avg_hold_time_seconds": self.performance.get_avg_hold_time(),
            "signal_accuracy": self.performance.get_signal_accuracy(),
            "suggestions_generated": len(self.suggestions),
            "current_volatility_1h": self.calculate_volatility(60),
        }

    def export_suggestions(self, filepath: str):
        """Export suggestions to JSON file."""
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.logger.session_id,
            "summary": self.get_summary(),
            "suggestions": [s.to_dict() for s in self.suggestions],
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
