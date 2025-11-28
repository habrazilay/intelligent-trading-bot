from pathlib import Path
from datetime import datetime
import logging

import numpy as np
import pandas as pd
import click

from service.App import *
from common.model_store import *
from common.generators import generate_feature_set

log = logging.getLogger(__name__)

@click.command()
@click.option("-c", "--config_file", type=click.Path(exists=True), required=True, help="Configuration file path")
@click.option("--dry-run", is_flag=True, help="Só valida entrada/saída, não grava o arquivo de features")
@click.option("--log-level", default="INFO", show_default=True, help="Logging level (DEBUG, INFO, WARNING, ERROR)")
def main(config_file, dry_run, log_level):
    # Configure logging
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")

    load_config(config_file)
    config = App.config

    App.model_store = ModelStore(config)
    App.model_store.load_models()

    time_column = config.get("time_column", "time")
    if "time_column" not in config:
        log.warning("Config não define 'time_column', usando padrão '%s'.", time_column)

    now = datetime.now()

    symbol = config["symbol"]
    data_path = Path(config["data_folder"]) / symbol

    # Determine window size
    is_train = config.get("train", True)
    window_size = config.get("train_length") if is_train else config.get("predict_length")
    features_horizon = config.get("features_horizon", 0)
    if window_size:
        window_size += features_horizon
        log.info("Window size (dados usados): %d linhas", window_size)
    else:
        log.info("Window size não definido, usando todos os registros.")

    # Load MERGED data
    file_path = data_path / config.get("merge_file_name")
    if not file_path.is_file():
        log.error("Arquivo de merge não encontrado: %s", file_path)
        return

    log.info("Carregando merge: %s", file_path)
    if file_path.suffix == ".parquet":
        df = pd.read_parquet(file_path)
    else:
        df = pd.read_csv(file_path, parse_dates=[time_column])

    log.info("Merge carregado com %d linhas e %d colunas.", len(df), len(df.columns))

    if window_size:
        df = df.tail(window_size).reset_index(drop=True)

    log.info("Range: %s → %s", df.iloc[0][time_column], df.iloc[-1][time_column])

    # Generate features
    feature_sets = config.get("feature_sets", [])
    if not feature_sets:
        log.error("Nenhum feature_set definido no config.")
        return

    log.info("Gerando features (%d sets)...", len(feature_sets))

    all_features = []
    for i, fs in enumerate(feature_sets):
        log.info("Iniciando feature set %d/%d (%s)...", i+1, len(feature_sets), fs.get("generator"))
        fs_now = datetime.now()

        df, new_features = generate_feature_set(df, fs, config, App.model_store, last_rows=0)

        all_features.extend(new_features)
        fs_elapsed = datetime.now() - fs_now
        log.info(
            "Finalizado set %d/%d → %d novas features (%s). Tempo: %s",
            i+1, len(feature_sets), len(new_features), fs.get("generator"),
            str(fs_elapsed).split(".")[0]
        )

    log.info("Total de features novas: %d", len(all_features))

    # NULL handling
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    na_rows = df[df[all_features].isna().any(axis=1)]
    if len(na_rows) > 0:
        log.warning("Existem %d linhas com valores NULL em features.", len(na_rows))
    log.info("Resumo de NULL por feature:\n%s", df[all_features].isnull().sum().sort_values(ascending=False))

    # Prepare output
    out_file_name = config.get("feature_file_name")
    out_path = (data_path / out_file_name).resolve()

    if dry_run:
        log.info("DRY-RUN: resultaria em arquivo %s com %d linhas e %d colunas.",
                 out_path, len(df), len(df.columns))
        log.info("Próximo passo depois do features: python -m scripts.labels -c %s", config_file)
        return

    # Store output
    log.info("Salvando arquivo de features em %s ...", out_path)
    if out_path.suffix == ".parquet":
        df.to_parquet(out_path, index=False)
    else:
        df.to_csv(out_path, index=False, float_format="%.6f")

    log.info("Arquivo salvo: %s (%d linhas)", out_path, len(df))

    # Save feature list
    with open(out_path.with_suffix('.txt'), "a+") as f:
        f.write(", ".join([f'"{f}"' for f in all_features]) + "\n\n")

    log.info("Lista de %d features salva em %s", len(all_features), out_path.with_suffix('.txt'))

    elapsed = datetime.now() - now
    log.info("✔ FEATURES COMPLETAS em %s", str(elapsed).split(".")[0])
    log.info("➡ Próximo passo: python -m scripts.labels -c %s", config_file)


if __name__ == '__main__':
    main()
