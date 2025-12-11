"""
Binance Futures Trader - Supports LONG and SHORT positions

This module handles bidirectional trading on Binance Futures:
- LONG: Buy low, sell high (profit when price rises)
- SHORT: Sell high, buy low (profit when price falls)

Key differences from Spot trading:
- Uses Futures API endpoints
- Supports leverage (default: 1x = no leverage)
- Can open SHORT positions (not just close LONG)
- Has funding fees (every 8 hours)
- Risk of liquidation if using leverage > 1x

Usage:
    Configure in config.jsonc:
    {
        "venue": "binance_futures",
        "futures": {
            "use_testnet": true,  // ALWAYS test first!
            "leverage": 1,
            "margin_type": "ISOLATED"
        },
        "trade_model": {
            "trader_binance_futures": true,
            "long": { "enabled": true, "position_size_percent": 2.0 },
            "short": { "enabled": true, "position_size_percent": 1.5 }
        }
    }
"""

import math
import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Literal

import pandas as pd

from binance.enums import (
    ORDER_STATUS_NEW,
    ORDER_STATUS_PARTIALLY_FILLED,
    ORDER_STATUS_FILLED,
    ORDER_STATUS_CANCELED,
    ORDER_STATUS_PENDING_CANCEL,
    ORDER_STATUS_REJECTED,
    ORDER_STATUS_EXPIRED,
    ORDER_TYPE_LIMIT,
    ORDER_TYPE_MARKET,
    TIME_IN_FORCE_GTC,
    SIDE_BUY,
    SIDE_SELL,
)

log = logging.getLogger("trader_futures")

from service.App import App
from common.utils import now_timestamp, to_decimal, round_str, round_down_str
from common.model_store import ModelStore
from common.risk_management import RiskManager
from outputs.notifier_trades import get_signal


# Position side for Futures (different from Spot SIDE_BUY/SIDE_SELL)
POSITION_SIDE_LONG = "LONG"
POSITION_SIDE_SHORT = "SHORT"
POSITION_SIDE_BOTH = "BOTH"  # For one-way mode

# Global risk manager instance
_risk_manager: Optional[RiskManager] = None


def get_risk_manager() -> RiskManager:
    """Get or initialize the global RiskManager instance."""
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = RiskManager(App.config)
        log.info("RiskManager initialized for Futures trading")
    return _risk_manager


async def setup_futures_account():
    """
    Initialize Futures account settings (leverage, margin type).
    Should be called once at startup.
    """
    config = App.config
    futures_config = config.get("futures", {})
    symbol = config["symbol"]

    leverage = futures_config.get("leverage", 1)
    margin_type = futures_config.get("margin_type", "ISOLATED")

    try:
        # Set leverage
        log.info(f"Setting leverage to {leverage}x for {symbol}")
        App.futures_client.futures_change_leverage(symbol=symbol, leverage=leverage)

        # Set margin type (ISOLATED or CROSSED)
        log.info(f"Setting margin type to {margin_type} for {symbol}")
        try:
            App.futures_client.futures_change_margin_type(symbol=symbol, marginType=margin_type)
        except Exception as e:
            # May fail if already set to this type
            if "No need to change margin type" not in str(e):
                log.warning(f"Could not set margin type: {e}")

        log.info(f"Futures account setup complete: {leverage}x leverage, {margin_type} margin")
        return True

    except Exception as e:
        log.error(f"Failed to setup Futures account: {e}")
        return False


async def trader_binance_futures(df: pd.DataFrame, model: dict, config: dict, model_store: ModelStore):
    """
    Binance Futures trader - supports LONG and SHORT positions.

    State machine:
    - FLAT: No position (can open LONG or SHORT)
    - LONG: Holding long position (can close on SELL signal)
    - SHORT: Holding short position (can close on BUY signal)
    - OPENING_LONG/OPENING_SHORT: Order placed, waiting for fill
    - CLOSING_LONG/CLOSING_SHORT: Closing order placed, waiting for fill
    """
    # Normalize model
    if isinstance(model, list):
        if not model:
            log.error("trader_binance_futures received an empty model list")
            return
        model = model[0]

    symbol = config["symbol"]
    now_ts = now_timestamp()

    buy_signal_column = model.get("buy_signal_column")
    sell_signal_column = model.get("sell_signal_column")

    signal = get_signal(df, buy_signal_column, sell_signal_column)
    signal_side = signal.get("side")
    close_price = signal.get("close_price")

    log.info(f"===> Start Futures trade task. Timestamp {now_ts}")

    # Get risk manager
    risk_manager = get_risk_manager()

    # Check circuit breaker
    if not risk_manager.is_trading_allowed():
        remaining = risk_manager.circuit_breaker.time_until_reset()
        log.warning(f"CIRCUIT BREAKER ACTIVE - Trading paused. Remaining: {remaining}")
        return

    # Get trade model settings
    trade_model = config.get("trade_model", {})
    long_config = trade_model.get("long", {})
    short_config = trade_model.get("short", {})

    long_enabled = long_config.get("enabled", True)
    short_enabled = short_config.get("enabled", False)

    # 1. Sync position status
    status = getattr(App, 'futures_status', None)
    if status is None:
        await update_futures_position_status()
        status = App.futures_status

    log.info(f"Current status: {status}, Signal: {signal_side}")

    # 2. Handle pending orders
    if status in ("OPENING_LONG", "OPENING_SHORT", "CLOSING_LONG", "CLOSING_SHORT"):
        order_status = await update_futures_order_status()

        if order_status == ORDER_STATUS_FILLED:
            if status == "OPENING_LONG":
                App.futures_status = "LONG"
                entry_price = Decimal(str(App.futures_order.get("avgPrice", close_price)))
                quantity = Decimal(str(App.futures_order.get("executedQty", "0")))
                risk_manager.open_position(entry_price, "LONG", quantity)
                log.info(f"===> LONG position opened at {entry_price}")

            elif status == "OPENING_SHORT":
                App.futures_status = "SHORT"
                entry_price = Decimal(str(App.futures_order.get("avgPrice", close_price)))
                quantity = Decimal(str(App.futures_order.get("executedQty", "0")))
                risk_manager.open_position(entry_price, "SHORT", quantity)
                log.info(f"<=== SHORT position opened at {entry_price}")

            elif status == "CLOSING_LONG":
                App.futures_status = "FLAT"
                exit_price = Decimal(str(App.futures_order.get("avgPrice", close_price)))
                exit_reason = getattr(App, 'risk_exit_reason', None) or "signal"
                risk_manager.close_position(exit_price, exit_reason=exit_reason)
                App.risk_exit_reason = None
                log.info(f"<=== LONG position closed at {exit_price}")

            elif status == "CLOSING_SHORT":
                App.futures_status = "FLAT"
                exit_price = Decimal(str(App.futures_order.get("avgPrice", close_price)))
                exit_reason = getattr(App, 'risk_exit_reason', None) or "signal"
                risk_manager.close_position(exit_price, exit_reason=exit_reason)
                App.risk_exit_reason = None
                log.info(f"===> SHORT position closed at {exit_price}")

        elif order_status in (ORDER_STATUS_REJECTED, ORDER_STATUS_EXPIRED, ORDER_STATUS_CANCELED):
            log.error(f"Order failed with status {order_status}")
            # Revert to previous state
            if status.startswith("OPENING"):
                App.futures_status = "FLAT"
            elif status == "CLOSING_LONG":
                App.futures_status = "LONG"
            elif status == "CLOSING_SHORT":
                App.futures_status = "SHORT"

        elif order_status in (ORDER_STATUS_NEW, ORDER_STATUS_PARTIALLY_FILLED):
            # Still waiting, cancel after timeout
            await cancel_futures_order()
            return

        status = App.futures_status

    # 3. Check risk management (stop-loss, take-profit)
    if status in ("LONG", "SHORT") and close_price is not None:
        current_price = Decimal(str(close_price))
        exit_reason = risk_manager.check_exit_conditions(current_price)

        if exit_reason:
            log.warning(f"RISK MANAGEMENT: {exit_reason.upper()} triggered at {close_price}")
            # Force close position
            if status == "LONG":
                signal_side = "SELL"
            else:  # SHORT
                signal_side = "BUY"
            App.risk_exit_reason = exit_reason

    # 4. Execute trades based on signals
    if signal_side == "BUY":
        log.info(f"===> BUY SIGNAL {signal}")
    elif signal_side == "SELL":
        log.info(f"<=== SELL SIGNAL {signal}")

    # Update account balance
    await update_futures_account_balance()

    status = App.futures_status

    # Decision logic
    should_open_long = (status == "FLAT" and signal_side == "BUY" and long_enabled)
    should_close_long = (status == "LONG" and signal_side == "SELL")
    should_open_short = (status == "FLAT" and signal_side == "SELL" and short_enabled)
    should_close_short = (status == "SHORT" and signal_side == "BUY")

    if should_open_long:
        order = await new_futures_order(
            side=SIDE_BUY,
            position_side=POSITION_SIDE_LONG,
            position_config=long_config
        )
        if order:
            App.futures_status = "OPENING_LONG"
            log.info("Opening LONG position...")

    elif should_close_long:
        order = await new_futures_order(
            side=SIDE_SELL,
            position_side=POSITION_SIDE_LONG,
            close_position=True
        )
        if order:
            App.futures_status = "CLOSING_LONG"
            log.info("Closing LONG position...")

    elif should_open_short:
        order = await new_futures_order(
            side=SIDE_SELL,
            position_side=POSITION_SIDE_SHORT,
            position_config=short_config
        )
        if order:
            App.futures_status = "OPENING_SHORT"
            log.info("Opening SHORT position...")

    elif should_close_short:
        order = await new_futures_order(
            side=SIDE_BUY,
            position_side=POSITION_SIDE_SHORT,
            close_position=True
        )
        if order:
            App.futures_status = "CLOSING_SHORT"
            log.info("Closing SHORT position...")

    elif signal_side in ("BUY", "SELL"):
        log.info(f"Signal {signal_side} ignored: status={status}, long_enabled={long_enabled}, short_enabled={short_enabled}")

    log.info("<=== End Futures trade task")


async def update_futures_position_status():
    """Read current Futures position and set status."""
    symbol = App.config["symbol"]

    try:
        positions = App.futures_client.futures_position_information(symbol=symbol)
    except Exception as e:
        log.error(f"Binance Futures exception in futures_position_information: {e}")
        App.futures_status = "FLAT"
        return

    # Find position for this symbol
    position = None
    for pos in positions:
        if pos.get("symbol") == symbol:
            position = pos
            break

    if not position:
        App.futures_status = "FLAT"
        return

    # Check position amount
    position_amt = Decimal(str(position.get("positionAmt", "0")))

    if position_amt > 0:
        App.futures_status = "LONG"
        App.futures_position = position
        log.info(f"Detected LONG position: {position_amt}")
    elif position_amt < 0:
        App.futures_status = "SHORT"
        App.futures_position = position
        log.info(f"Detected SHORT position: {position_amt}")
    else:
        App.futures_status = "FLAT"
        App.futures_position = None
        log.info("No open position (FLAT)")


async def update_futures_order_status():
    """Update status of pending Futures order."""
    symbol = App.config["symbol"]

    order = getattr(App, 'futures_order', None)
    order_id = order.get("orderId") if order else None

    if not order_id:
        log.error("No order ID to check")
        return None

    try:
        new_order = App.futures_client.futures_get_order(symbol=symbol, orderId=order_id)
    except Exception as e:
        log.error(f"Binance Futures exception in futures_get_order: {e}")
        return None

    if new_order:
        App.futures_order = new_order
        return new_order.get("status")

    return None


async def update_futures_account_balance():
    """Get Futures account balance."""
    quote_asset = App.config.get("quote_asset", "USDT")

    try:
        balances = App.futures_client.futures_account_balance()
    except Exception as e:
        log.error(f"Binance Futures exception in futures_account_balance: {e}")
        return

    for balance in balances:
        if balance.get("asset") == quote_asset:
            App.futures_balance = Decimal(str(balance.get("availableBalance", "0")))
            log.info(f"Futures balance: {App.futures_balance} {quote_asset}")
            return

    App.futures_balance = Decimal("0")


async def cancel_futures_order():
    """Cancel pending Futures order."""
    symbol = App.config["symbol"]

    order = getattr(App, 'futures_order', None)
    order_id = order.get("orderId") if order else None

    if not order_id:
        return None

    try:
        log.info(f"Cancelling Futures order {order_id}")
        result = App.futures_client.futures_cancel_order(symbol=symbol, orderId=order_id)
        return result.get("status")
    except Exception as e:
        log.error(f"Binance Futures exception in futures_cancel_order: {e}")
        return None


async def new_futures_order(
    side: str,
    position_side: str,
    position_config: dict = None,
    close_position: bool = False
):
    """
    Create a new Futures order.

    Args:
        side: SIDE_BUY or SIDE_SELL
        position_side: POSITION_SIDE_LONG or POSITION_SIDE_SHORT
        position_config: Config dict with position_size_percent, etc.
        close_position: If True, close existing position instead of opening new
    """
    symbol = App.config["symbol"]
    trade_model = App.config.get("trade_model", {})
    futures_config = App.config.get("futures", {})

    # Get current price
    try:
        ticker = App.futures_client.futures_symbol_ticker(symbol=symbol)
        current_price = Decimal(str(ticker.get("price", "0")))
    except Exception as e:
        log.error(f"Could not get current price: {e}")
        return None

    if current_price == 0:
        log.error("Current price is 0, cannot create order")
        return None

    # Calculate quantity
    if close_position:
        # Close entire position
        position = getattr(App, 'futures_position', None)
        if not position:
            log.error("No position to close")
            return None
        quantity = abs(Decimal(str(position.get("positionAmt", "0"))))
    else:
        # Open new position
        if not position_config:
            position_config = {}

        balance = getattr(App, 'futures_balance', Decimal("0"))
        pct = Decimal(str(position_config.get("position_size_percent", 2.0)))
        leverage = Decimal(str(futures_config.get("leverage", 1)))

        # Notional = balance * percentage * leverage
        notional = (balance * pct / Decimal("100")) * leverage

        min_notional = Decimal(str(trade_model.get("min_notional_usdt", 6.0)))
        if notional < min_notional:
            log.warning(f"Notional {notional} below minimum {min_notional}")
            return None

        quantity = notional / current_price

    # Round quantity
    quantity_str = round_down_str(quantity, 3)  # Futures typically uses 3 decimals
    quantity_rounded = Decimal(quantity_str)

    if quantity_rounded <= 0:
        log.error(f"Quantity is 0 after rounding")
        return None

    # Determine position side for hedge mode
    position_mode = futures_config.get("position_mode", "ONE_WAY")

    order_params = dict(
        symbol=symbol,
        side=side,
        type=ORDER_TYPE_MARKET,
        quantity=quantity_str,
    )

    # Add positionSide for hedge mode
    if position_mode == "HEDGE":
        order_params["positionSide"] = position_side

    log.info(f"New Futures order: {order_params}")

    # Check for simulation mode
    if trade_model.get("no_trades_only_data_processing"):
        log.info(f"NOT executed (no_trades_only_data_processing=True): {order_params}")
        return None

    if trade_model.get("simulate_order_execution"):
        log.info(f"Simulated order: {order_params}")
        return {"orderId": "SIMULATED", "status": ORDER_STATUS_FILLED}

    # Execute order
    try:
        if trade_model.get("test_order_before_submit"):
            log.info(f"Testing order first...")
            # Note: Futures testnet doesn't have test endpoint, just execute

        order = App.futures_client.futures_create_order(**order_params)
        log.info(f"Futures order created: {order}")

        App.futures_order = order
        App.futures_order_time = now_timestamp()

        return order

    except Exception as e:
        log.error(f"Binance Futures exception in futures_create_order: {e}")
        return None
