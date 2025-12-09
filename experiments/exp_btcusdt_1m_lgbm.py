"""
Experimento: BTCUSDT 1m - LightGBM em cima da matrix.csv gerada pelo pipeline.

Objetivos:
- Carregar DATA_ITB_1m/BTCUSDT/matrix.csv
- Usar o mesmo conjunto de features do lc (Logistic Regression)
- Treinar um LGBMClassifier para prever high_05_60 e low_05_60
- Fazer split temporal (treino/val por tempo, sem shuffle)
- Calcular métricas (AUC, AP, precision, recall, etc.)
- Salvar métricas em JSON em experiments/results/...
"""
from sklearn.metrics import precision_recall_fscore_support
import argparse
import json
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    precision_recall_fscore_support,
)

try:
    import lightgbm as lgb
    HAS_LGBM = True
except ImportError:
    HAS_LGBM = False
    from sklearn.ensemble import GradientBoostingClassifier


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Experimento LGBM para BTCUSDT 1m usando matrix.csv"
    )
    parser.add_argument(
        "--matrix",
        type=str,
        default="DATA_ITB_1m/BTCUSDT/matrix.csv",
        help="Caminho para o matrix.csv (já com features + labels).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=180,
        help="Número de dias recentes para usar no experimento (default: 180).",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Caminho do JSON de saída com métricas. Default: experiments/results/btcusdt_1m_lgbm_<data>.json",
    )
    return parser.parse_args()


def ensure_results_dir(out_path: Path) -> Path:
    out_dir = out_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_path


def temporal_train_val_split(df: pd.DataFrame, time_col: str, val_frac: float = 0.2):
    """
    Split por tempo: primeiros (1 - val_frac) para treino, últimos val_frac para validação.
    """
    df_sorted = df.sort_values(time_col).reset_index(drop=True)
    n = len(df_sorted)
    split_idx = int(n * (1.0 - val_frac))
    df_train = df_sorted.iloc[:split_idx].copy()
    df_val = df_sorted.iloc[split_idx:].copy()
    return df_train, df_val


def train_one_side(
    df: pd.DataFrame,
    feature_cols: list[str],
    label_col: str,
    time_col: str,
    val_frac: float = 0.2,
) -> dict:
    """
    Treina um modelo (LGBM ou fallback) para uma única label (ex: high_05_60).

    Retorna dict com métricas e alguns metadados.
    """
    # Remove linhas com NaNs em features ou label
    cols_needed = feature_cols + [label_col, time_col]
    df = df[cols_needed].dropna().copy()

    if df[label_col].nunique() < 2:
        return {
            "label": label_col,
            "error": "Menos de 2 classes na label (tudo 0 ou tudo 1).",
        }

    df_train, df_val = temporal_train_val_split(df, time_col, val_frac=val_frac)

    X_train = df_train[feature_cols].values
    y_train = df_train[label_col].values.astype(int)

    X_val = df_val[feature_cols].values
    y_val = df_val[label_col].values.astype(int)

    # Modelo
    if HAS_LGBM:
        model = lgb.LGBMClassifier(
            n_estimators=200,
            learning_rate=0.05,
            num_leaves=31,
            max_depth=-1,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=42,
            n_jobs=-1,
        )
        model_name = "lgbm"
    else:
        # Fallback se lightgbm não estiver instalado
        model = GradientBoostingClassifier(
            n_estimators=150,
            learning_rate=0.05,
            max_depth=3,
            random_state=42,
        )
        model_name = "sklearn_gbc"

    model.fit(X_train, y_train)

    # Probabilidades e métricas
    if hasattr(model, "predict_proba"):
        y_val_proba = model.predict_proba(X_val)[:, 1]
    else:
        # Alguns modelos podem não ter predict_proba, mas quase todos terão
        y_val_proba = model.decision_function(X_val)
        # normaliza para 0-1
        y_val_proba = (y_val_proba - y_val_proba.min()) / (
            y_val_proba.max() - y_val_proba.min() + 1e-9
        )

    y_pred = (y_val_proba >= 0.5).astype(int)

    metrics = {}

    # Métricas principais
    try:
        metrics["auc"] = float(roc_auc_score(y_val, y_val_proba))
    except ValueError:
        metrics["auc"] = None

    try:
        metrics["ap"] = float(average_precision_score(y_val, y_val_proba))
    except ValueError:
        metrics["ap"] = None

    precision, recall, f1, support = precision_recall_fscore_support(
        y_val,
        y_pred,
        average="binary",
        pos_label=1,
        zero_division=0,
    )

    metrics = {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }

    # `support` é None quando usamos average="binary"
    if support is None:
        support_pos = int((y_val == 1).sum())
        support_neg = int((y_val == 0).sum())
        metrics["support_pos"] = support_pos
        metrics["support_neg"] = support_neg
        metrics["support_total"] = support_pos + support_neg
    else:
        metrics["support"] = int(support)


    # Métricas por threshold extra (ex: 0.3, 0.7)
    thresholds = [0.3, 0.5, 0.7]
    thr_metrics = {}
    for thr in thresholds:
        y_thr = (y_val_proba >= thr).astype(int)
        p, r, f, s = precision_recall_fscore_support(
            y_val, y_thr, average="binary", zero_division=0
        )
        thr_metrics[str(thr)] = {
            "precision": float(p),
            "recall": float(r),
            "f1": float(f),
            "support": str(s),
        }

    # Info temporal do split
    metrics["time"] = {
        "train_start": df_train[time_col].iloc[0].isoformat(),
        "train_end": df_train[time_col].iloc[-1].isoformat(),
        "val_start": df_val[time_col].iloc[0].isoformat(),
        "val_end": df_val[time_col].iloc[-1].isoformat(),
    }

    return {
        "label": label_col,
        "model_type": model_name,
        "n_train": int(len(df_train)),
        "n_val": int(len(df_val)),
        "metrics": metrics,
        "threshold_metrics": thr_metrics,
        "feature_cols": feature_cols,
    }


def main():
    args = parse_args()

    matrix_path = Path(args.matrix)
    if not matrix_path.is_file():
        raise FileNotFoundError(f"matrix.csv não encontrado em: {matrix_path}")

    print(f"Lendo matrix de: {matrix_path}")
    df = pd.read_csv(matrix_path)

    # Coluna de tempo – deve bater com App.config["time_column"]
    time_col = "timestamp"
    if time_col not in df.columns:
        raise ValueError(f"Coluna de tempo '{time_col}' não encontrada em matrix.csv")

    df[time_col] = pd.to_datetime(df[time_col], utc=True)

    # Recorte de N dias recentes (default: 180)
    if args.days is not None and args.days > 0:
        max_ts = df[time_col].max()
        min_allowed = max_ts - timedelta(days=args.days)
        df = df[df[time_col] >= min_allowed].copy()
        print(
            f"Usando últimos {args.days} dias: "
            f"{df[time_col].min()} → {df[time_col].max()} (n={len(df)})"
        )

    # Mesmas features do modelo lc (config otimizado 1m)
    feature_cols = [
        "close_SMA_5",
        "close_SMA_10",
        "close_SMA_20",
        "close_SMA_60",
        "close_RSI_14",
        "close_LINEARREG_SLOPE_10",
        "close_LINEARREG_SLOPE_20",
        "close_LINEARREG_SLOPE_60",
        "high_low_close_ATR_14",
        "close_STDDEV_20",
        "close_STDDEV_60",
    ]

    for col in feature_cols:
        if col not in df.columns:
            raise ValueError(f"Feature '{col}' não encontrada em matrix.csv")

    # Labels atuais do 1m otimizado
    label_cols = ["high_05_60", "low_05_60"]
    for col in label_cols:
        if col not in df.columns:
            raise ValueError(f"Label '{col}' não encontrada em matrix.csv")

    results = {
        "dataset": "BTCUSDT_1m",
        "matrix_path": str(matrix_path),
        "time_range": {
            "start": df[time_col].min().isoformat(),
            "end": df[time_col].max().isoformat(),
        },
        "n_rows": int(len(df)),
        "days": args.days,
        "has_lightgbm": HAS_LGBM,
        "labels": {},
    }

    for label_col in label_cols:
        print(f"\nTreinando modelo para label: {label_col}")
        res = train_one_side(
            df=df,
            feature_cols=feature_cols,
            label_col=label_col,
            time_col=time_col,
            val_frac=0.2,
        )
        results["labels"][label_col] = res

    # Caminho de saída
    if args.out:
        out_path = Path(args.out)
    else:
        now_str = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        out_path = Path("experiments/results") / f"btc_1m_lgbm_{now_str}.json"

    out_path = ensure_results_dir(out_path)

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nMétricas salvas em: {out_path}")


if __name__ == "__main__":
    main()