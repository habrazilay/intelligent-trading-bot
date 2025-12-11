import math
import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

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

log = logging.getLogger(__name__)

from service.App import App
from common.utils import now_timestamp, to_decimal, round_str, round_down_str
from common.model_store import ModelStore
from common.risk_management import RiskManager
from outputs.notifier_trades import get_signal

import logging
log = logging.getLogger("trader")

# Global risk manager instance (initialized on first use)
_risk_manager: Optional[RiskManager] = None


def get_risk_manager() -> RiskManager:
    """Get or initialize the global RiskManager instance."""
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = RiskManager(App.config)
        log.info("RiskManager initialized")
    return _risk_manager


async def trader_binance(df: pd.DataFrame, model: dict, config: dict, model_store: ModelStore):
    """
    Top-level Binance trader adapter.

    It is scheduled every minute by the server and:
    1. Reads the latest signal from the dataframe.
    2. Synchronizes trade status with Binance (orders + balances).
    3. Checks risk management conditions (stop-loss, take-profit, circuit breaker).
    4. Decides whether to open new BUY/SELL limit orders.
    """
    # Normalize model: sometimes a list of models may be passed; use the first element
    if isinstance(model, list):
        if not model:
            log.error("trader_binance received an empty model list; skipping trade task.")
            return
        log.warning("trader_binance received a list for model; using the first element.")
        model = model[0]

    symbol = config["symbol"]
    freq = config["freq"]
    startTime, endTime = now_timestamp(), now_timestamp()  # interval logging only
    now_ts = now_timestamp()

    buy_signal_column = model.get("buy_signal_column")
    sell_signal_column = model.get("sell_signal_column")

    signal = get_signal(df, buy_signal_column, sell_signal_column)
    signal_side = signal.get("side")
    close_price = signal.get("close_price")
    close_time = signal.get("close_time")

    log.info(f"===> Start trade task. Timestamp {now_ts}. Interval [{startTime},{endTime}].")

    # Get risk manager instance
    risk_manager = get_risk_manager()

    # Check circuit breaker before any trading
    if not risk_manager.is_trading_allowed():
        remaining = risk_manager.circuit_breaker.time_until_reset()
        log.warning("CIRCUIT BREAKER ACTIVE - Trading paused. Remaining: %s", remaining)
        return

    #
    # 1. Sync trade status, check running orders (orders, account etc.)
    #
    status = App.status

    # If status is unknown (e.g. first run), try to infer it from the account
    if status not in ("BUYING", "SELLING", "BOUGHT", "SOLD"):
        await update_trade_status()
        status = App.status

    if status in ("BUYING", "SELLING"):
        # We expect that an order was created before and now we need to check if it still exists or was executed
        order_status = await update_order_status()

        order = App.order
        # If order status executed then change the status
        # Status codes: NEW PARTIALLY_FILLED FILLED CANCELED PENDING_CANCEL REJECTED EXPIRED

        if not order or not order_status:
            # No order exists or some problem
            await update_trade_status()
            log.error(f"Bad order or order status {order}. Full reset/init needed.")
            return
        if order_status == ORDER_STATUS_FILLED:
            log.info(f"Limit order filled. {order}")
            if status == "BUYING":
                log.info("===> BOUGHT: %s", order)
                App.status = "BOUGHT"
                # Register position in risk manager
                entry_price = Decimal(str(order.get("price", close_price)))
                quantity = Decimal(str(order.get("executedQty", "0")))
                risk_manager.open_position(entry_price, "BUY", quantity)
            elif status == "SELLING":
                log.info("<=== SOLD: %s", order)
                App.status = "SOLD"
                # Close position in risk manager
                exit_price = Decimal(str(order.get("price", close_price)))
                # Use risk exit reason if it was set (stop-loss, take-profit, etc.)
                exit_reason = getattr(App, 'risk_exit_reason', None) or "signal"
                risk_manager.close_position(exit_price, exit_reason=exit_reason)
                App.risk_exit_reason = None  # Reset for next trade
            log.info(f"New trade mode: {App.status}")
        elif order_status in (ORDER_STATUS_REJECTED, ORDER_STATUS_EXPIRED, ORDER_STATUS_CANCELED):
            log.error(f"Failed to fill order with order status {order_status}")
            if status == "BUYING":
                App.status = "SOLD"
            elif status == "SELLING":
                App.status = "BOUGHT"
            log.info(f"New trade mode: {App.status}")
        elif order_status == ORDER_STATUS_PENDING_CANCEL:
            return  # Currently do nothing. Check next time.
        elif order_status == ORDER_STATUS_PARTIALLY_FILLED:
            # Currently do nothing. Check next time.
            pass
        elif order_status == ORDER_STATUS_NEW:
            # Wait further for execution
            pass
        else:
            # Order still exists and is active
            pass
    elif status in ("BOUGHT", "SOLD"):
        # Do nothing in this cycle
        pass
    else:
        log.error(f"Wrong status value {status}.")
        return

    #
    # 2. Prepare. Kill or update existing orders (if necessary)
    #
    status = App.status

    # If not sold for 1 minute, then kill and then a new order will be created below if there is signal
    if status in ("BUYING", "SELLING"):  # Still not filled for 1 minute
        order_status = await cancel_order()
        if not order_status:
            # Could not cancel or was already filled; resync state
            await update_trade_status()
            return
        await asyncio.sleep(1)  # Wait for a second till the balance is updated
        if status == "BUYING":
            App.status = "SOLD"
        elif status == "SELLING":
            App.status = "BOUGHT"

    #
    # 3. Check risk management conditions (stop-loss, take-profit)
    #
    status = App.status

    if status == "BOUGHT" and close_price is not None:
        current_price = Decimal(str(close_price))
        exit_reason = risk_manager.check_exit_conditions(current_price)

        if exit_reason:
            # Risk management triggered - force sell
            log.warning("RISK MANAGEMENT: %s triggered at %.2f", exit_reason.upper(), close_price)

            # Override signal to force SELL
            signal_side = "SELL"
            App.risk_exit_reason = exit_reason  # Store for later use

    #
    # 4. Trade by creating orders
    #
    if signal_side == "BUY":
        log.info("===> BUY SIGNAL %s", signal)
    elif signal_side == "SELL":
        log.info("<=== SELL SIGNAL %s", signal)
    else:
        if close_price is not None:
            log.info("PRICE: %.2f", close_price)
        else:
            log.info("PRICE: n/a")

    # Update account balance etc. what is needed for trade
    await update_account_balance()

    # Shadow mode: allows testing order creation regardless of balance-based status
    # When shadow_mode is True, BUY signals will create test orders even if status is "BOUGHT"
    trade_model = config.get("trade_model", {})
    shadow_mode = trade_model.get("shadow_mode", False)
    force_real_trade = trade_model.get("force_real_trade", False)

    # Log the decision-making process
    log.info("Trade decision: status=%s, signal_side=%s, shadow_mode=%s, force_real_trade=%s",
             status, signal_side, shadow_mode, force_real_trade)

    # Determine if we should attempt to create an order
    should_buy = (status == "SOLD" and signal_side == "BUY")
    should_sell = (status == "BOUGHT" and signal_side == "SELL")

    # In shadow mode, allow order creation for testing purposes regardless of status
    if shadow_mode and signal_side == "BUY" and not should_buy:
        log.info("SHADOW MODE: Overriding status check for BUY signal (status was %s)", status)
        should_buy = True
    if shadow_mode and signal_side == "SELL" and not should_sell:
        log.info("SHADOW MODE: Overriding status check for SELL signal (status was %s)", status)
        should_sell = True

    if should_buy:
        order = await new_limit_order(side=SIDE_BUY)

        if not order:
            log.info("No BUY order created; keeping status as %s.", App.status)
        elif model.get("no_trades_only_data_processing"):
            log.info("SKIP TRADING due to 'no_trades_only_data_processing' parameter True")
        elif shadow_mode and not force_real_trade:
            log.info("SHADOW MODE: Test order created but not changing status")
        else:
            # Real trade executed (or shadow_mode with force_real_trade)
            if shadow_mode and force_real_trade:
                log.info("SHADOW MODE + FORCE REAL TRADE: Order executed, changing status to BUYING")
            App.status = "BUYING"
    elif should_sell:
        order = await new_limit_order(side=SIDE_SELL)

        if not order:
            log.info("No SELL order created; keeping status as %s.", App.status)
        elif model.get("no_trades_only_data_processing"):
            log.info("SKIP TRADING due to 'no_trades_only_data_processing' parameter True")
        elif shadow_mode and not force_real_trade:
            log.info("SHADOW MODE: Test order created but not changing status")
        else:
            # Real trade executed (or shadow_mode with force_real_trade)
            if shadow_mode and force_real_trade:
                log.info("SHADOW MODE + FORCE REAL TRADE: Order executed, changing status to SELLING")
            App.status = "SELLING"
    elif signal_side in ("BUY", "SELL"):
        log.info("Signal %s ignored: current status is %s (need %s to act on this signal)",
                 signal_side, status, "SOLD" if signal_side == "BUY" else "BOUGHT")

    log.info("<=== End trade task.")
    return


#
# Order and asset status
#

async def update_trade_status():
    """Read the account state and set the local state parameters."""
    # GET /api/v3/openOrders - get current open orders
    symbol = App.config["symbol"]

    try:
        open_orders = App.client.get_open_orders(symbol=symbol)
    except Exception as e:
        log.error(f"Binance exception in 'get_open_orders' {e}")
        return

    if not open_orders:
        # No open orders, infer status from balances
        await update_account_balance()

        # Analyzer.get_last_kline returns the last kline for the current stream; guard explicitly against None
        last_kline = App.analyzer.get_last_kline()
        if last_kline is None:
            last_close_price = Decimal("0")
        else:
            last_close_price = to_decimal(last_kline['close'])

        base_quantity = App.account_info.base_quantity  # BTC
        btc_assets_in_usd = base_quantity * last_close_price if last_close_price != 0 else Decimal("0")

        usd_assets = App.account_info.quote_quantity  # USDT

        # Log the balance comparison for debugging
        log.info("Status inference: BTC=%s (value=$%.2f), USDT=$%.2f, price=%.2f",
                 base_quantity, float(btc_assets_in_usd), float(usd_assets), float(last_close_price))

        if usd_assets >= btc_assets_in_usd:
            App.status = "SOLD"
            log.info("Status set to SOLD (USDT >= BTC value)")
        else:
            App.status = "BOUGHT"
            log.info("Status set to BOUGHT (BTC value > USDT)")

    elif len(open_orders) == 1:
        order = open_orders[0]
        if order.get("side") == SIDE_SELL:
            App.status = "SELLING"
        elif order.get("side") == SIDE_BUY:
            App.status = "BUYING"
        else:
            log.error(f"Neither SELL nor BUY side of the order {order}.")
            return None

    else:  # Many orders
        log.error("Wrong state. More than one open order. Fix manually.")
        return None


async def update_order_status():
    """
    Update information about the current order and return its execution status.

    ASSUMPTIONS and notes:
    - Status codes: NEW PARTIALLY_FILLED FILLED CANCELED PENDING_CANCEL REJECTED EXPIRED
    - only one or no orders can be active currently, but in future there can be many orders
    - if no order id(s) is provided then retrieve all existing orders
    """
    symbol = App.config["symbol"]

    # Get currently active order and id (if any)
    order = App.order
    order_id = order.get("orderId", 0) if order else 0
    if not order_id:
        log.error("Wrong state or use: check order status cannot find the order id.")
        return None

    try:
        new_order = App.client.get_order(symbol=symbol, orderId=order_id)
    except Exception as e:
        log.error(f"Binance exception in 'get_order' {e}")
        return

    if new_order:
        order.update(new_order)
    else:
        return None

    return order.get("status")


async def update_account_balance():
    """Get available assets (as decimal)."""

    base_asset = App.config["base_asset"]
    quote_asset = App.config["quote_asset"]

    # Helper to normalize balance responses from the client
    def _normalize_balance(raw_balance, asset_name):
        """
        raw_balance can be a dict (expected) or a list of dicts.
        Return a single balance dict for the given asset_name, or an empty dict.
        """
        if raw_balance is None:
            return {}
        if isinstance(raw_balance, dict):
            return raw_balance
        if isinstance(raw_balance, list):
            for item in raw_balance:
                if isinstance(item, dict) and item.get("asset") == asset_name:
                    return item
            # If not found, return empty dict
            return {}
        # Fallback for unexpected types
        return {}

    try:
        raw_base = App.client.get_asset_balance(asset=base_asset)
    except Exception as e:
        log.error(f"Binance exception in 'get_asset_balance' for base_asset {base_asset}: {e}")
        return

    base_balance = _normalize_balance(raw_base, base_asset)
    App.account_info.base_quantity = Decimal(base_balance.get("free", "0.00000000"))

    try:
        raw_quote = App.client.get_asset_balance(asset=quote_asset)
    except Exception as e:
        log.error(f"Binance exception in 'get_asset_balance' for quote_asset {quote_asset}: {e}")
        return

    quote_balance = _normalize_balance(raw_quote, quote_asset)
    App.account_info.quote_quantity = Decimal(quote_balance.get("free", "0.00000000"))

    return


#
# Cancel and liquidation orders
#

async def cancel_order():
    """
    Kill existing order. It is a blocking request, that is, it waits for the end of the operation.
    Info: DELETE /api/v3/order - cancel order
    """
    symbol = App.config["symbol"]

    order = App.order
    order_id = order.get("orderId", 0) if order else 0
    if order_id == 0:
        return None

    try:
        log.info(f"Cancelling order id {order_id}")
        new_order = App.client.cancel_order(symbol=symbol, orderId=order_id)
    except Exception as e:
        log.error(f"Binance exception in 'cancel_order' {e}")
        return None

    if new_order:
        order.update(new_order)
    else:
        return None

    return order.get("status")


#
# Order creation
#

async def new_limit_order(side):
    """
    Create a new limit order with the amount we currently have available.
    """
    symbol = App.config["symbol"]
    now_ts = now_timestamp()

    trade_model = App.config.get("trade_model", {})

    #
    # Find limit price (from signal, last kline and adjustment parameters)
    #
    # Analyzer.get_last_kline returns the latest kline; guard explicitly against None
    last_kline = App.analyzer.get_last_kline()
    if last_kline is None:
        log.error("Cannot determine last close price in order to create a limit order (no kline).")
        return None
    last_close_price = to_decimal(last_kline['close'])

    raw_adj = trade_model.get("limit_price_adjustment", 0)
    # Normalize and clamp price adjustment to a sane range [0, 0.05] (0–5%)
    try:
        price_adjustment = Decimal(str(raw_adj))
    except Exception:
        log.error("Invalid limit_price_adjustment value %r; defaulting to 0.", raw_adj)
        price_adjustment = Decimal("0")

    max_adj = Decimal("0.05")
    if price_adjustment < 0:
        log.warning("limit_price_adjustment < 0 (%.4f) in config; using 0.", price_adjustment)
        price_adjustment = Decimal("0")
    elif price_adjustment > max_adj:
        log.warning(
            "limit_price_adjustment %.4f too large; capping to %.4f to satisfy Binance price filters.",
            price_adjustment,
            max_adj,
        )
        price_adjustment = max_adj

    if side == SIDE_BUY:
        price = last_close_price * (Decimal("1") - price_adjustment)
    elif side == SIDE_SELL:
        price = last_close_price * (Decimal("1") + price_adjustment)
    else:
        log.error(f"Unsupported side for new_limit_order: {side}")
        return None

    price_str = round_str(price, 2)
    price = Decimal(price_str)

    #
    # Find quantity
    #
    if side == SIDE_BUY:
        balance_usdt = App.account_info.quote_quantity  # Available USDT as Decimal

        # Read percentage and thresholds from trade_model
        pct = Decimal(str(trade_model.get("percentage_used_for_trade", 0)))  # in %
        min_notional = Decimal(str(trade_model.get("min_notional_usdt", 0)))  # absolute USDT minimum
        min_balance_for_pct = Decimal(str(trade_model.get("min_balance_usdt_for_percentage", 0)))  # apply pct only above this

        notional_usdt = Decimal("0")

        if balance_usdt >= min_balance_for_pct and pct > 0:
            # Use percentage of balance, but never below the configured min_notional
            notional_usdt = (balance_usdt * pct) / Decimal("100")
            if notional_usdt < min_notional:
                notional_usdt = min_notional
        else:
            # If balance is small, try to trade min_notional or whatever balance is left (whichever is smaller)
            if min_notional > 0:
                notional_usdt = min(balance_usdt, min_notional)
            else:
                notional_usdt = balance_usdt

        # If we still don't reach the minimum notional, skip placing an order
        if min_notional > 0 and notional_usdt < min_notional:
            log.info(
                "Notional %.4f below configured min_notional_usdt %.4f; skipping BUY order.",
                notional_usdt,
                min_notional,
            )
            return None

        if notional_usdt <= 0:
            log.info("Notional is non-positive (%.4f); skipping BUY order.", notional_usdt)
            return None

        quantity = notional_usdt / price  # BTC to buy
    elif side == SIDE_SELL:
        # For selling, use all available base asset (BTC)
        quantity = App.account_info.base_quantity  # BTC
    else:
        return None

    # Round quantity to 5 decimal places (Binance LOT_SIZE for BTCUSDT)
    quantity_str = round_down_str(quantity, 5)
    quantity_rounded = Decimal(quantity_str)

    # Check notional AFTER rounding to ensure it meets Binance minimum ($5)
    notional = quantity_rounded * price
    binance_min_notional = Decimal("5.0")  # Binance NOTIONAL filter minimum

    if notional < binance_min_notional:
        log.warning(
            "Notional after rounding (%.4f) is below Binance minimum ($5). "
            "Adjusting quantity upward.",
            float(notional),
        )
        # Calculate minimum quantity needed to meet $5 notional
        min_quantity = binance_min_notional / price
        # Round UP to 5 decimals to ensure we exceed $5
        quantity_str = round_str(min_quantity + Decimal("0.00001"), 5)
        quantity_rounded = Decimal(quantity_str)
        notional = quantity_rounded * price

    # Determine order type from config (default: LIMIT)
    order_type = trade_model.get("order_type", "LIMIT").upper()

    log.info(
        "New order params | type=%s side=%s price=%s quantity=%s notional_usdt=%.4f",
        order_type,
        side,
        price_str,
        quantity_str,
        float(notional),
    )

    if order_type == "MARKET":
        order_spec = dict(
            symbol=symbol,
            side=side,
            type=ORDER_TYPE_MARKET,
            quantity=quantity_str,
        )
    else:  # Default to LIMIT
        order_spec = dict(
            symbol=symbol,
            side=side,
            type=ORDER_TYPE_LIMIT,
            timeInForce=TIME_IN_FORCE_GTC,
            quantity=quantity_str,
            price=price_str,
        )

    if trade_model.get("no_trades_only_data_processing"):
        log.info("NOT executed order spec (no_trades_only_data_processing=True): %s", order_spec)
        return None

    order = execute_order(order_spec)
    if not order:
        log.error("Order was not created (test or real). Skipping state change.")
        return None

    App.order = order
    App.order_time = now_ts

    # If BUY order executed and TP/SL is configured, place OCO sell order
    if side == SIDE_BUY and order.get("status") == ORDER_STATUS_FILLED:
        await _place_oco_tp_sl(order, trade_model)

    return order


async def _place_oco_tp_sl(buy_order: dict, trade_model: dict) -> None:
    """
    Place an OCO (One-Cancels-Other) order with Take Profit and Stop Loss
    after a BUY order is filled.

    OCO order includes:
    - Limit sell at take_profit price (TP)
    - Stop-limit sell at stop_loss price (SL)
    """
    risk_config = App.config.get("risk_management", {})
    tp_percent = risk_config.get("take_profit_percent")
    sl_percent = risk_config.get("stop_loss_percent")

    # Check if native TP/SL is enabled
    if not trade_model.get("use_native_tp_sl", False):
        return

    if not tp_percent or not sl_percent:
        log.warning("Native TP/SL enabled but take_profit_percent or stop_loss_percent not configured")
        return

    try:
        # Get entry price and quantity from the filled order
        entry_price = Decimal(str(buy_order.get("price", "0")))
        # For market orders, use avgPrice or cummulativeQuoteQty/executedQty
        if entry_price == 0:
            executed_qty = Decimal(str(buy_order.get("executedQty", "0")))
            cumm_quote = Decimal(str(buy_order.get("cummulativeQuoteQty", "0")))
            if executed_qty > 0 and cumm_quote > 0:
                entry_price = cumm_quote / executed_qty

        if entry_price == 0:
            log.error("Cannot determine entry price for OCO order")
            return

        quantity = buy_order.get("executedQty", buy_order.get("origQty"))
        symbol = buy_order.get("symbol", App.config["symbol"])

        # Calculate TP and SL prices
        tp_price = entry_price * (Decimal("1") + Decimal(str(tp_percent)) / Decimal("100"))
        sl_price = entry_price * (Decimal("1") - Decimal(str(sl_percent)) / Decimal("100"))
        # Stop limit price slightly below stop price to ensure execution
        sl_limit_price = sl_price * Decimal("0.995")

        # Round prices to 2 decimals
        tp_price_str = round_str(tp_price, 2)
        sl_price_str = round_str(sl_price, 2)
        sl_limit_price_str = round_str(sl_limit_price, 2)

        log.info(
            "Placing OCO TP/SL order | entry=%.2f TP=%.2f (+%.1f%%) SL=%.2f (-%.1f%%)",
            float(entry_price),
            float(tp_price),
            float(tp_percent),
            float(sl_price),
            float(sl_percent),
        )

        # Place OCO order
        oco_response = App.client.create_oco_order(
            symbol=symbol,
            side=SIDE_SELL,
            quantity=quantity,
            price=tp_price_str,           # Take profit limit price
            stopPrice=sl_price_str,        # Stop trigger price
            stopLimitPrice=sl_limit_price_str,  # Stop limit price
            stopLimitTimeInForce=TIME_IN_FORCE_GTC,
        )

        log.info("OCO order placed successfully: %s", oco_response.get("orderListId"))
        App.oco_order = oco_response

    except Exception as e:
        log.error("Failed to place OCO TP/SL order: %s", e)


def execute_order(order: dict):
    """Validate and submit order"""

    trade_model = App.config.get("trade_model", {})

    # Optionally test order before real submit
    if trade_model.get("test_order_before_submit"):
        try:
            log.info(f"Submitting test order: {order}")
            test_response = App.client.create_test_order(**order)
            log.info(f"Test order response: {test_response}")
        except Exception as e:
            log.error(f"Binance exception in 'create_test_order' {e}")
            return None

    if trade_model.get("simulate_order_execution"):
        log.info("Simulated order execution: %s", order)
        return order

    try:
        log.info(f"Submitting order: {order}")
        order = App.client.create_order(**order)
    except Exception as e:
        log.error(f"Binance exception in 'create_order' {e}")
        return None

    if not order or not order.get("status"):
        return None

    return order
