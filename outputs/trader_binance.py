import math
import asyncio
from datetime import datetime
from decimal import Decimal

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
    TIME_IN_FORCE_GTC,
    SIDE_BUY,
    SIDE_SELL,
)

from service.App import App
from common.utils import now_timestamp, to_decimal, round_str, round_down_str
from common.model_store import ModelStore
from outputs.notifier_trades import get_signal

import logging
log = logging.getLogger("trader")


async def trader_binance(df: pd.DataFrame, model: dict, config: dict, model_store: ModelStore):
    """
    Top-level Binance trader adapter.

    It is scheduled every minute by the server and:
    1. Reads the latest signal from the dataframe.
    2. Synchronizes trade status with Binance (orders + balances).
    3. Decides whether to open new BUY/SELL limit orders.
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
                print(f"===> BOUGHT: {order}")
                App.status = "BOUGHT"
            elif status == "SELLING":
                print(f"<=== SOLD: {order}")
                App.status = "SOLD"
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
    # 3. Trade by creating orders
    #
    status = App.status

    if signal_side == "BUY":
        print(f"===> BUY SIGNAL {signal}: ")
    elif signal_side == "SELL":
        print(f"<=== SELL SIGNAL: {signal}")
    else:
        if close_price is not None:
            print(f"PRICE: {close_price:.2f}")
        else:
            print("PRICE: n/a")

    # Update account balance etc. what is needed for trade
    await update_account_balance()

    if status == "SOLD" and signal_side == "BUY":
        order = await new_limit_order(side=SIDE_BUY)

        if not order:
            log.info("No BUY order created; keeping status as %s.", App.status)
        elif model.get("no_trades_only_data_processing"):
            print("SKIP TRADING due to 'no_trades_only_data_processing' parameter True")
            # Never change status if orders not executed
        else:
            App.status = "BUYING"
    elif status == "BOUGHT" and signal_side == "SELL":
        order = await new_limit_order(side=SIDE_SELL)

        if not order:
            log.info("No SELL order created; keeping status as %s.", App.status)
        elif model.get("no_trades_only_data_processing"):
            print("SKIP TRADING due to 'no_trades_only_data_processing' parameter True")
            # Never change status if orders not executed
        else:
            App.status = "SELLING"

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
            last_close_price = to_decimal(last_kline.iloc[4])

        base_quantity = App.account_info.base_quantity  # BTC
        btc_assets_in_usd = base_quantity * last_close_price if last_close_price != 0 else Decimal("0")

        usd_assets = App.account_info.quote_quantity  # USDT

        if usd_assets >= btc_assets_in_usd:
            App.status = "SOLD"
        else:
            App.status = "BOUGHT"

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
    last_close_price = to_decimal(last_kline.iloc[4])

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

    notional = quantity * price
    log.info(
        "New limit order params | side=%s price=%s quantity=%s notional_usdt=%.4f",
        side,
        price_str,
        round_str(quantity, 8),
        float(notional),
    )

    quantity_str = round_down_str(quantity, 5)

    order_spec = dict(
        symbol=symbol,
        side=side,
        type=ORDER_TYPE_LIMIT,
        timeInForce=TIME_IN_FORCE_GTC,
        quantity=quantity_str,
        price=price_str,
    )

    if trade_model.get("no_trades_only_data_processing"):
        print(f"NOT executed order spec: {order_spec}")
        return None

    order = execute_order(order_spec)
    if not order:
        log.error("Order was not created (test or real). Skipping state change.")
        return None

    App.order = order
    App.order_time = now_ts

    return order


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
        print(order)
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
