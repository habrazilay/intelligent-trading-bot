from datetime import datetime
from pathlib import Path
import logging

import pandas as pd
import numpy as np
import click

from service.App import App, load_config

"""
Create one output file from multiple input data files.
Compatible with btcusdt_1m_dev.jsonc and klines.parquet.
"""

log = logging.getLogger(__name__)


def merge_data_sources(
    data_sources: list,
    time_column: str,
    freq: str,
    config: dict,
) -> pd.DataFrame | None:
    """
    Carrega os dfs já existentes em data_sources[*]["df"],
    ajusta índice de tempo, aplica prefixos e constrói um
    único DataFrame com índice regular.
    """

    for ds in data_sources:
        df = ds.get("df")
        if df is None:
            log.error("Data source %s não tem 'df' carregado.", ds)
            return None

        # Garante que o índice seja a coluna de tempo
        if time_column in df.columns:
            df = df.set_index(time_column)
        elif df.index.name == time_column:
            pass
        else:
            log.error("Timestamp column '%s' is absent.", time_column)
            return None

        # Add prefix if not already there
        prefix = ds.get("column_prefix") or ""
        if prefix:
            df.columns = [
                f"{prefix}_{col}" if not col.startswith(f"{prefix}_") else col
                for col in df.columns
            ]

        ds["start"] = df.index[0]
        ds["end"] = df.index[-1]
        ds["df"] = df

    #
    # Create common (main) index and empty data frame
    #
    range_start = min(ds["start"] for ds in data_sources)
    range_end = min(ds["end"] for ds in data_sources)

    log.info("Common time range: %s → %s", range_start, range_end)

    # Generate a discrete time raster according to pandas frequency parameter
    index = pd.date_range(range_start, range_end, freq=freq)

    df_out = pd.DataFrame(index=index)
    df_out.index.name = time_column
    df_out.insert(0, time_column, df_out.index)  # Repeat index as a new column

    for ds in data_sources:
        # Note: timestamps must have the same semantics (start of kline, etc.)
        df_out = df_out.join(ds["df"], how="left")

    # Interpolate numeric columns (opcional & controlado)
    merge_interpolate = config.get("merge_interpolate", False)
    if merge_interpolate:
        cols_cfg = config.get("merge_interpolate_columns")
        max_gap = config.get("merge_interpolate_max_gap")  # em nº de passos

        if cols_cfg:
            num_columns = [c for c in cols_cfg if c in df_out.columns]
        else:
            # fallback: todos numéricos
            num_columns = df_out.select_dtypes(include=[np.number]).columns.tolist()

        # garante que não vamos mexer na coluna de tempo
        if time_column in num_columns:
            num_columns.remove(time_column)

        log.info("Interpolando colunas numéricas: %s", num_columns)
        for col in num_columns:
            before_nans = df_out[col].isna().sum()
            if max_gap:
                df_out[col] = df_out[col].interpolate(limit=max_gap)
            else:
                df_out[col] = df_out[col].interpolate()
            after_nans = df_out[col].isna().sum()
            log.info("  - %s: NaNs antes=%d, depois=%d", col, before_nans, after_nans)

    return df_out


@click.command()
@click.option(
    "-c",
    "--config_file",
    type=click.Path(exists=True),
    required=True,
    help="Configuration file path (ex.: configs/btcusdt_1m_dev.jsonc)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Só valida entrada/saída, não grava arquivo de saída",
)
@click.option(
    "--log-level",
    default="INFO",
    show_default=True,
    help="Logging level (DEBUG, INFO, WARNING, ERROR)",
)
def main(config_file: str, dry_run: bool, log_level: str) -> None:
    # Logging básico
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    load_config(config_file)
    config = App.config

    time_column = config.get("time_column", "time")
    if "time_column" not in config:
        log.warning("Config não define 'time_column'. Usando padrão: '%s'.", time_column)

    now = datetime.now()

    symbol = config["symbol"]
    data_path = Path(config["data_folder"])
    freq = config.get("pandas_freq", "1min")

    # Determine desired data length depending on train/predict mode
    is_train = config.get("train", True)
    if is_train:
        window_size = config.get("train_length")
    else:
        window_size = config.get("predict_length")

    features_horizon = config.get("features_horizon", 0)
    if window_size:
        window_size = int(window_size) + int(features_horizon)
        log.info("Window size (dados usados): %d linhas", window_size)
    else:
        log.info("Window size não definido; usaremos todos os registros disponíveis.")
        window_size = None

    #
    # Load data from multiple sources and merge
    #
    data_sources = config.get("data_sources", [])
    if not data_sources:
        log.error("Data sources are not defined. Nothing to merge.")
        return

    # Read data from input files
    for ds in data_sources:
        quote = ds.get("folder")
        if not quote:
            log.error("ERROR. 'folder' is not specified in data_source: %s", ds)
            continue

        file = ds.get("file", quote) or quote

        base_path = data_path / quote / file

        # Tenta detectar extensão: parquet → csv
        if base_path.suffix:
            file_path = base_path
        else:
            parquet_path = base_path.with_suffix(".parquet")
            csv_path = base_path.with_suffix(".csv")
            if parquet_path.exists():
                file_path = parquet_path
            elif csv_path.exists():
                file_path = csv_path
            else:
                log.error(
                    "Nenhum arquivo encontrado para base '%s' (.parquet/.csv).",
                    base_path,
                )
                continue

        log.info("Reading data file: %s", file_path)

        if file_path.suffix == ".parquet":
            df = pd.read_parquet(file_path)
        elif file_path.suffix == ".csv":
            df = pd.read_csv(file_path, parse_dates=[time_column])
        else:
            log.error(
                "Unknown extension of the input file '%s'. Only 'csv' and 'parquet' are supported",
                file_path.suffix,
            )
            return

        log.info("Loaded file with %d records.", len(df))

        # Select only the data necessary for analysis
        if window_size:
            df = df.tail(window_size).reset_index(drop=True)

        ds["df"] = df

    # Merge in one df with prefixes and common regular time index
    df_out = merge_data_sources(data_sources, time_column, freq, config)
    if df_out is None:
        log.error("Merge failed. Abort.")
        return

    #
    # Store file with features
    #
    merge_file_name = config.get("merge_file_name", "merged.parquet")
    out_path = data_path / symbol / merge_file_name

    df_out = df_out.reset_index(drop=(df_out.index.name in df_out.columns))

    # range real baseado na coluna de tempo
    range_start = df_out[time_column].iloc[0]
    range_end = df_out[time_column].iloc[-1]

    if dry_run:
        log.info(
            "DRY-RUN: merge resultaria em arquivo %s com %d registros. Range: (%s, %s)",
            out_path,
            len(df_out),
            range_start,
            range_end,
        )
        elapsed = datetime.now() - now
        log.info("Finished merging data (dry-run) in %s", str(elapsed).split(".")[0])
        return

    log.info("Storing output file %s ...", out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.suffix == ".parquet":
        df_out.to_parquet(out_path, index=False)
    elif out_path.suffix == ".csv":
        df_out.to_csv(out_path, index=False)
    else:
        log.error(
            "Unknown extension of the output file '%s'. Only 'csv' and 'parquet' are supported",
            out_path.suffix,
        )
        return

    log.info(
    "Stored output file %s with %d records. Range: (%s, %s)",
    out_path, len(df_out), range_start, range_end
    )

    elapsed = datetime.now() - now
    log.info("Finished merging data in %s", str(elapsed).split(".")[0])
    if not dry_run:
        log.info("✔ MERGE COMPLETE — data looks good.")
        log.info("✔ Rows: %d | Range: %s → %s", len(df_out), range_start, range_end)
        log.info("✔ File saved at: %s", out_path)
        log.info("➡ Next step: python -m scripts.features_new -c %s", config_file)


if __name__ == "__main__":
    main()