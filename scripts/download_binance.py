"""
download_binance.py  –  Historical Binance klines downloader (spot or futures).

Example:
    python -m scripts.download_binance -c configs/btcusdt_1m.jsonc
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timedelta, timezone
import time, os, logging
import click
import pandas as pd
try:
    from dotenv import load_dotenv
    load_dotenv()
except ModuleNotFoundError:
    log.warning("python-dotenv is not installed — .env will be ignored.")
from binance.exceptions import BinanceAPIException
from binance import Client, exceptions


from common.utils import binance_freq_from_pandas
from inputs.collector_binance import klines_to_df, column_types
from service.App import *

import requests
from requests.adapters import HTTPAdapter
import urllib3, socket
from urllib3.util import connection

# --------------------------------------------------------------------------- #
#  Logging configuration
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO, 
    # level=logging.DEBUG,  # altere para DEBUG para mais detalhes    
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("download_binance.log", mode="w", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
#  Utility functions
# --------------------------------------------------------------------------- #
def allowed_gai_family(): return socket.AF_INET
connection.allowed_gai_family = allowed_gai_family
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def safe_request(client, symbol, interval, start):
    delay, attempt = 0.2, 0
    while True:
        attempt += 1
        try:
            return client.get_historical_klines(
                symbol=symbol,
                interval=interval,
                start_str=int(start.timestamp() * 1000),
                limit=1_000        
            )
        except exceptions.BinanceAPIException as e:
            log.error("APIException %s (%s) attempt %s", e.code, e.message, attempt)
            if e.code in (-1003,):         # rate‑limit
                time.sleep(delay); delay = min(delay * 2, 8)
            elif e.code in (-2015, -2014): # invalid key or IP
                raise                      # stop and surface the error
            else:
                time.sleep(delay); delay = min(delay * 2, 8)
        except Exception as e:
            log.error("Error %s on attempt %s", e, attempt, exc_info=True)
            time.sleep(delay); delay = min(delay * 2, 8)


def save_parquet(df: pd.DataFrame, target: Path):
    """Save DataFrame to Snappy Parquet and ensure the target directory exists."""
    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(target, index=False, compression="snappy")


def load_existing(target: Path, time_col: str) -> pd.DataFrame | None:
    if not target.is_file():
        return None
    df = pd.read_parquet(target)
    df[time_col] = pd.to_datetime(df[time_col], utc=True)
    df = df.astype(column_types)
    return df

def _render_progress_bar(pct: float, width: int = 30) -> str:
    """Render a simple textual progress bar."""
    # ensure the value is between 0 and 100
    pct = max(0.0, min(100.0, pct))
    filled = int(width * pct / 100.0)
    return "[" + "#" * filled + "." * (width - filled) + f"] {pct:5.1f}%"


# --------------------------------------------------------------------------- #
#  CLI
# --------------------------------------------------------------------------- #
@click.command()
@click.option(
    "--config_file",
    "-c",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="JSONC configuration file",
)
def main(config_file: str):
    load_dotenv()                 # load .env first
    load_config(config_file)

    time_col = App.config["time_column"]
    data_root = Path(App.config.get("data_folder", "./DATA_ITB")).expanduser()
    data_root.mkdir(parents=True, exist_ok=True)
    max_rows = App.config.get("download_max_rows", 0)

    pandas_freq = App.config.get("pandas_freq", App.config["freq"])
    binance_freq = binance_freq_from_pandas(pandas_freq)

    log.info("Freq pandas  = %s | Binance = %s", pandas_freq, binance_freq)

    # Simple mapping from Binance interval to step length in minutes
    STEP_MIN = {
        "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
        "1h": 60, "2h": 120, "4h": 240, "6h": 360,
        "8h": 480, "12h": 720,
        "1d": 1440
    }
    step = timedelta(minutes=STEP_MIN[binance_freq])

    # --- credentials ------------------------------------------------------- #
    client_args = App.config.get("client_args", {})
    client_args["api_key"]    = App.config.get("api_key")    or os.getenv("BINANCE_API_KEY")
    client_args["api_secret"] = App.config.get("api_secret") or os.getenv("BINANCE_API_SECRET")
    App.client = Client(**{k: v for k, v in client_args.items() if v})
    session = requests.Session()
    session.mount("https://", HTTPAdapter(pool_connections=100, pool_maxsize=100))
    # force resolver to use only A records
    session.get_adapter("https://").proxy_manager = {}
    client_args["session"] = session

    futures = False            # ajuste se precisar
    if futures:
        App.client.API_URL = "https://fapi.binance.com/fapi"

    # ----------------------------------------------------------------------- #
    start_all = datetime.now()
    for ds in App.config["data_sources"]:
        symbol = ds.get("folder")
        if not symbol:
            log.error("data_source missing 'folder' (symbol). Skipping.")
            continue

        target_file = data_root / symbol / (("futures" if futures else "klines") + ".parquet")
        existing_df = load_existing(target_file, time_col)
        if existing_df is not None:
            oldest_point = existing_df[time_col].iloc[-5]
            log.info(
                "Found %s (%d rows). Downloading from %s up to now.",
                target_file.name,
                len(existing_df),
                oldest_point,
            )
        else:
            cfg_start = App.config.get("download_start")
            if cfg_start:
                oldest_point = pd.to_datetime(cfg_start, utc=True).to_pydatetime()
            else:
                oldest_point = datetime(2017, 1, 1, tzinfo=timezone.utc)
            log.info("First download of %s since %s …", symbol, oldest_point.date())

        chunks: list[pd.DataFrame] = []
        cur = oldest_point
        start_ts = cur
        latest_ts = datetime.now(timezone.utc)
        log.debug("Loop start for %s | cur=%s latest_ts=%s step=%s", symbol, cur, latest_ts, step)

        while cur < latest_ts - step:
            raw = safe_request(App.client, symbol, binance_freq, cur)
            if not raw:
                log.info("No data returned for %s starting at %s. Stopping loop.", symbol, cur)
                break

            df_chunk = klines_to_df(raw)
            chunks.append(df_chunk)

            last_open = pd.to_datetime(raw[-1][0], unit="ms", utc=True)
            cur = last_open + step

            # approximate progress based on the date range
            if latest_ts > start_ts:
                pct = (last_open - start_ts).total_seconds() / (latest_ts - start_ts).total_seconds() * 100.0
                progress_bar = _render_progress_bar(pct)
                # update the same line in the terminal (no newline)
                print(f"\rProgresso {symbol}: {progress_bar} (até {last_open})", end="", flush=True)

            # log.info(
            #     "Baixado até %s para %s (chunk %d linhas)",
            #     last_open,
            #     symbol,
            #     len(df_chunk),
            # )

            time.sleep(0.2)
        
        # ensure the progress bar ends with a newline
        print()


        if not chunks:
            log.info("Nothing new for %s.", symbol)
            continue

        df_new = pd.concat(chunks)
        if existing_df is not None:
            df_full = (
                pd.concat([existing_df, df_new])
                .drop_duplicates(subset=[time_col], keep="last")
                .iloc[:-1]  # remove kline incompleta
            )
        else:
            df_full = df_new.iloc[:-1]

        if max_rows:
            df_full = df_full.tail(max_rows)

        save_parquet(df_full, target_file)
        log.info("Saved %d rows to %s", len(df_full), target_file)

    log.info("Finished in %s", str(datetime.now() - start_all).split(".")[0])


if __name__ == "__main__":
    main()