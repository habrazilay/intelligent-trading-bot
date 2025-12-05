from pathlib import Path
from typing import Union
import json
from datetime import datetime, date, timedelta
import re
import os

import pandas as pd

from common.model_store import *
from common.types import AccountBalances, MT5AccountInfo

PACKAGE_ROOT = Path(__file__).parent.parent
#PACKAGE_PARENT = '..'
#SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
#sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))
#PACKAGE_ROOT = os.path.dirname(os.path.abspath(__file__))


class App:
    """Globally visible variables."""

    # System
    loop = None  # asyncio main loop
    sched = None  # Scheduler

    analyzer = None  # Store and analyze data

    # Connector client
    client = None

    # WebSocket for push notifications
    bm = None
    conn_key = None  # Socket

    #
    # State of the server (updated after each interval)
    #
    # State 0 or None or empty means ok. String and other non empty objects mean error
    error_status = 0  # Networks, connections, exceptions etc. what does not allow us to work at all
    server_status = 0  # If server allow us to trade (maintenance, down etc.)
    account_status = 0  # If account allows us to trade (funds, suspended etc.)
    trade_state_status = 0  # Something wrong with our trading logic (wrong use, inconsistent state etc. what we cannot recover)

    df = None  # Data from the latest analysis

    # Trade simulator
    transaction = None
    # Trade binance
    status = None  # BOUGHT, SOLD, BUYING, SELLING
    order = None  # Latest or current order
    order_time = None  # Order submission time

    # Account Info
    # Available assets for trade
    # Can be set by the sync/recover function or updated by the trading algorithm
    # base_quantity = "0.04108219"  # BTC owned (on account, already bought, available for trade)
    # quote_quantity = "1000.0"  # USDT owned (on account, available for trade)
    account_info: Union[AccountBalances, MT5AccountInfo] = AccountBalances()

    #
    # Trader. Status data retrieved from the server. Below are examples only.
    #
    system_status = {"status": 0, "msg": "normal"}  # 0: normal，1：system maintenance
    symbol_info = {}
    # account_info = {}

    model_store: ModelStore = None

    #
    # Constant configuration parameters
    # At runtime, this will be fully replaced by the JSONC config file via load_config().
    #
    config = {}


def data_provider_problems_exist():
    if App.error_status != 0:
        return True
    if App.server_status != 0:
        return True
    return False


def problems_exist():
    if App.error_status != 0:
        return True
    if App.server_status != 0:
        return True
    if App.account_status != 0:
        return True
    if App.trade_state_status != 0:
        return True
    return False


def load_config(config_file: str) -> None:
    """Load a JSON/JSONC config file into App.config and overlay env secrets.

    - Reads the given JSON/JSONC file (supports // comments)
    - Replaces App.config entirely with the file content
    - If BINANCE_API_KEY / BINANCE_API_SECRET are set in the environment and
      the config does not define them, they are injected.
    """
    if not config_file:
        # No file provided: leave as-is (caller may fill App.config manually)
        return

    # Resolve path relative to project root
    config_file_path = PACKAGE_ROOT / config_file
    if not config_file_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_file_path}")

    with open(config_file_path, encoding="utf-8") as f:
        raw = f.read()

    # Strip // comments to support JSONC-style configs
    conf_str = re.sub(r"//.*$", "", raw, flags=re.M)

    try:
        conf_json = json.loads(conf_str)
    except Exception as e:
        raise RuntimeError(f"Erro ao parsear JSON de '{config_file_path}': {e}")

    # Replace the in-memory config entirely with the JSON config
    App.config = conf_json

    # If API key/secret are not set in config, fall back to environment variables
    api_key_env = os.getenv("BINANCE_API_KEY")
    api_secret_env = os.getenv("BINANCE_API_SECRET")
    if api_key_env and not App.config.get("api_key"):
        App.config["api_key"] = api_key_env
    if api_secret_env and not App.config.get("api_secret"):
        App.config["api_secret"] = api_secret_env

    # Ensure we have a default time_column if missing
    if not App.config.get("time_column"):
        App.config["time_column"] = "timestamp"


if __name__ == "__main__":
    pass
