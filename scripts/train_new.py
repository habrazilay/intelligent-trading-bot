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
    help="Só valida entrada/saída, não treina nem grava modelos",
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

    App.model_store = ModelStore(config)
    App.model_store.load_models()  # vai reclamar se não tiver modelo ainda – normal

    time_column = config.get("time_column", "time")
    if "time_column" not in config:
        log.warning("Config não define 'time_column', usando padrão '%s'.", time_column)

    now = datetime.now()

    symbol = config["symbol"]
    data_path = Path(config["data_folder"]) / symbol

    # === 1. Carregar MATRIX (features + labels) ==============================

    matrix_file_name = config.get("matrix_file_name", "matrix.csv")
    matrix_path = (data_path / matrix_file_name).resolve()

    if not matrix_path.is_file():
        log.error("Arquivo de matriz (features+labels) não encontrado: %s", matrix_path)
        return

    log.info("Carregando matriz (features+labels): %s", matrix_path)
    if matrix_path.suffix == ".parquet":
        df = pd.read_parquet(matrix_path)
    else:
        df = pd.read_csv(matrix_path, parse_dates=[time_column])

    log.info("Matriz carregada com %d linhas e %d colunas.", len(df), len(df.columns))

    # Janela de treino (por segurança, mas normalmente já é o recorte final)
    is_train = config.get("train", True)
    window_size = config.get("train_length") if is_train else config.get("predict_length")
    features_horizon = config.get("features_horizon", 0)
    if window_size:
        window_size += features_horizon
        if window_size < len(df):
            df = df.tail(window_size).reset_index(drop=True)
        log.info("Aplicando janela de treino: %d linhas (tail).", window_size)
    else:
        log.info("Window size não definido, usando todas as linhas.")

    log.info("Range final de treino: %s → %s", df.iloc[0][time_column], df.iloc[-1][time_column])

    # === 2. Verificar features e labels do config ============================

    train_features = config.get("train_features", [])
    labels = config.get("labels", [])

    if not train_features:
        log.error("Config não define 'train_features'. Nada para treinar.")
        return
    if not labels:
        log.error("Config não define 'labels'. Nada para treinar.")
        return

    log.info("Train features (%d): %s", len(train_features), ", ".join(train_features))
    log.info("Labels (%d): %s", len(labels), ", ".join(labels))

    # Checagem simples de existência de colunas
    missing_cols = [c for c in train_features + labels if c not in df.columns]
    if missing_cols:
        log.error("Colunas faltando na matriz para treino: %s", ", ".join(missing_cols))
        return

    # === 3. Train feature sets (infra existente) ============================

    train_feature_sets = config.get("train_feature_sets", [])
    if not train_feature_sets:
        log.warning("Nenhum 'train_feature_sets' definido. Usando apenas train_features/labels/algorithms diretamente.")
        # Ainda assim, podemos seguir usando a infra de ModelStore em outro script antigo se necessário.
        # Aqui, só faremos uma checagem básica e sair.
        if dry_run:
            log.info(
                "DRY-RUN: Treino usaria %d linhas, %d features, %d labels.",
                len(df),
                len(train_features),
                len(labels),
            )
            log.info("Próximo passo depois do treino: python -m scripts.predict -c %s", config_file)
            return
        else:
            log.info("Nada a fazer aqui sem train_feature_sets. Use o train.py legado se quiser esse caminho.")
            return

    if dry_run:
        log.info(
            "DRY-RUN: Treino chamaria %d 'train_feature_sets' sobre %d linhas.",
            len(train_feature_sets),
            len(df),
        )
        for i, tfs in enumerate(train_feature_sets):
            log.info(
                "  - Set %d/%d generator=%s",
                i + 1,
                len(train_feature_sets),
                tfs.get("generator"),
            )
        log.info("Próximo passo depois do treino: python -m scripts.predict -c %s", config_file)
        return

    log.info("Iniciando treino usando %d 'train_feature_sets'...", len(train_feature_sets))

    for i, tfs in enumerate(train_feature_sets):
        gen_name = tfs.get("generator")
        log.info("Iniciando train_feature_set %d/%d (%s)...", i + 1, len(train_feature_sets), gen_name)
        t_now = datetime.now()

        # A função generate_feature_set com generator="train_features"
        # deve cuidar de:
        # - separar X/Y
        # - treinar modelos
        # - salvar para ModelStore/MODELS
        _df_out, trained_items = generate_feature_set(df, tfs, config, App.model_store, last_rows=0)

        t_elapsed = datetime.now() - t_now
        log.info(
            "Finalizado train_feature_set %d/%d (%s). Itens: %s. Tempo: %s",
            i + 1,
            len(train_feature_sets),
            gen_name,
            str(trained_items),
            str(t_elapsed).split(".")[0],
        )

    elapsed = datetime.now() - now
    log.info("✔ TREINO COMPLETO em %s", str(elapsed).split(".")[0])
    log.info("Modelos devem estar salvos em: %s", (data_path / "MODELS").resolve())
    log.info("➡ Próximo passo: python -m scripts.predict -c %s", config_file)


if __name__ == "__main__":
    main()