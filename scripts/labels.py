from pathlib import Path
from datetime import datetime
import logging

import numpy as np
import pandas as pd
import click

from service.App import App, load_config
from common.model_store import ModelStore
from common.generators import generate_feature_set

log = logging.getLogger(__name__)


@click.command()
@click.option(
    "-c",
    "--config_file",
    type=click.Path(exists=True),
    required=True,
    help="Configuration file path",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Só valida entrada/saída, não grava o arquivo de matriz (features+labels)",
)
@click.option(
    "--log-level",
    default="INFO",
    show_default=True,
    help="Logging level (DEBUG, INFO, WARNING, ERROR)",
)
def main(config_file, dry_run, log_level):
    # Logging básico
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    load_config(config_file)
    config = App.config

    # ModelStore (não é estritamente necessário para labels, mas mantemos padrão)
    App.model_store = ModelStore(config)
    App.model_store.load_models()

    time_column = config.get("time_column", "time")
    if "time_column" not in config:
        log.warning("Config não define 'time_column', usando padrão '%s'.", time_column)

    now = datetime.now()

    symbol = config["symbol"]
    data_path = Path(config["data_folder"]) / symbol

    # Determine window size (mesma lógica dos outros scripts)
    is_train = config.get("train", True)
    window_size = config.get("train_length") if is_train else config.get("predict_length")
    features_horizon = config.get("features_horizon", 0)
    if window_size:
        window_size += features_horizon
        log.info("Window size (dados usados): %d linhas", window_size)
    else:
        log.info("Window size não definido, usando todos os registros.")

    # === 1. Carregar FEATURES =================================================
    feature_file_name = config.get("feature_file_name", "features.csv")
    feat_path = (data_path / feature_file_name).resolve()

    if not feat_path.is_file():
        log.error("Arquivo de features não encontrado: %s", feat_path)
        return

    log.info("Carregando features: %s", feat_path)
    if feat_path.suffix == ".parquet":
        df = pd.read_parquet(feat_path)
    else:
        df = pd.read_csv(feat_path, parse_dates=[time_column])

    log.info("Features carregadas com %d linhas e %d colunas.", len(df), len(df.columns))

    if window_size:
        df = df.tail(window_size).reset_index(drop=True)

    log.info("Range: %s → %s", df.iloc[0][time_column], df.iloc[-1][time_column])

    # === 2. Gerar LABELS ======================================================
    label_sets = config.get("label_sets", [])
    if not label_sets:
        log.error("Nenhum label_set definido no config. Nada a fazer.")
        return

    log.info("Gerando labels (%d sets)...", len(label_sets))

    all_labels = []
    for i, ls in enumerate(label_sets):
        gen_name = ls.get("generator")
        log.info("Iniciando label set %d/%d (%s)...", i + 1, len(label_sets), gen_name)
        ls_now = datetime.now()

        df, new_labels = generate_feature_set(df, ls, config, App.model_store, last_rows=0)
        all_labels.extend(new_labels)

        ls_elapsed = datetime.now() - ls_now
        log.info(
            "Finalizado label set %d/%d → %d labels novas (%s). Tempo: %s",
            i + 1,
            len(label_sets),
            len(new_labels),
            gen_name,
            str(ls_elapsed).split(".")[0],
        )

    log.info("Total de labels novas: %d (%s)", len(all_labels), ", ".join(all_labels))

    # === 3. Tratar NULLs em labels ============================================
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    na_rows = df[df[all_labels].isna().any(axis=1)]
    if len(na_rows) > 0:
        log.warning("Existem %d linhas com valores NULL em labels.", len(na_rows))
    log.info(
        "Resumo de NULL por label:\n%s",
        df[all_labels].isnull().sum().sort_values(ascending=False),
    )

    # === 4. Preparar saída (MATRIX) ===========================================
    matrix_file_name = config.get("matrix_file_name", "matrix.csv")
    out_path = (data_path / matrix_file_name).resolve()

    if dry_run:
        log.info(
            "DRY-RUN: matriz (features+labels) seria salva em %s com %d linhas e %d colunas.",
            out_path,
            len(df),
            len(df.columns),
        )
        log.info("Próximo passo depois dos labels: python -m scripts.train -c %s", config_file)
        return

    # Gravar matriz
    log.info("Salvando matriz (features+labels) em %s ...", out_path)
    if out_path.suffix == ".parquet":
        df.to_parquet(out_path, index=False)
    else:
        df.to_csv(out_path, index=False, float_format="%.6f")

    log.info("Matriz salva: %s (%d linhas, %d colunas)", out_path, len(df), len(df.columns))

    # Guardar lista de labels (opcional)
    labels_txt_path = out_path.with_suffix(".labels.txt")
    with open(labels_txt_path, "a+") as f:
        f.write(", ".join([f'"{lbl}"' for lbl in all_labels]) + "\n\n")

    log.info("Lista de %d labels salva em %s", len(all_labels), labels_txt_path)

    elapsed = datetime.now() - now
    log.info("✔ LABELS COMPLETAS em %s", str(elapsed).split(".")[0])
    log.info("➡ Próximo passo: python -m scripts.train -c %s", config_file)


if __name__ == "__main__":
    main()