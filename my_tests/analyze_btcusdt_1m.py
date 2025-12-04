#!/usr/bin/env python
"""
Análise de BTCUSDT 1m para calibrar horizonte (label_horizon), thresholds e volatilidade.

Uso:
  source itb-venv/bin/activate
  python analyze_btcusdt_1m.py \
      --parquet DATA_ITB_1m/BTCUSDT/klines.parquet \
      --days 90

O script:
  - Carrega o klines.parquet (1m)
  - Recorta apenas os últimos N dias
  - Calcula ATR(14) e ATR(30)
  - Calcula retornos futuros em vários horizontes (5, 10, 20, 30, 60, 120 candles)
  - Mostra com que frequência BTC se move ±0.2%, ±0.5%, ±1%, ±2%
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser(description="Análise estatística BTCUSDT 1m")
    parser.add_argument(
        "--parquet",
        type=str,
        default="DATA_ITB_1m/BTCUSDT/klines.parquet",
        help="Caminho para o klines.parquet de 1m",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Número de dias recentes para analisar (default: 90)",
    )
    return parser.parse_args()


def ensure_columns(df: pd.DataFrame):
    required = {"timestamp", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Faltam colunas obrigatórias no parquet: {missing}. "
            f"Colunas disponíveis: {list(df.columns)}"
        )


def compute_atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """
    ATR clássico em preço (não %).
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    prev_close = close.shift(1)
    tr1 = (high - low).abs()
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=window, min_periods=window).mean()
    return atr


def analyze_future_returns(df: pd.DataFrame, horizons: list[int], thresholds: list[float]):
    """
    Para cada horizonte (em candles), calcula distribuição de retornos futuros
    e probabilidade de ultrapassar/abaixar determinados thresholds.
    """
    print("\n" + "=" * 80)
    print("ANÁLISE DE RETORNOS FUTUROS (em %)")
    print("=" * 80)

    for h in horizons:
        future_close = df["close"].shift(-h)
        future_ret = (future_close - df["close"]) / df["close"]  # retorno em fração
        name = f"future_ret_{h}c"

        print(f"\n--- Horizonte: {h} candles ---")
        desc = future_ret.describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9])
        print(desc.to_string())

        for thr in thresholds:
            p_up = (future_ret >= thr).mean()
            p_down = (future_ret <= -thr).mean()
            print(
                f"  P(futuro >= +{thr*100:.2f}%): {p_up*100:5.2f}% | "
                f"P(futuro <= -{thr*100:.2f}%): {p_down*100:5.2f}%"
            )


def main():
    args = parse_args()
    parquet_path = Path(args.parquet)

    if not parquet_path.is_file():
        raise FileNotFoundError(f"Arquivo parquet não encontrado em {parquet_path}")

    print(f"Lendo parquet de 1m: {parquet_path}")
    df = pd.read_parquet(parquet_path)

    ensure_columns(df)

    # Garantir timestamp com timezone e ordenado
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    print("\nDimensão total do dataset 1m:")
    print(f"  Linhas: {len(df)}")
    print(f"  Período: {df['timestamp'].min()}  →  {df['timestamp'].max()}")

    # Recorte para últimos N dias
    cutoff = df["timestamp"].max() - pd.Timedelta(days=args.days)
    df_recent = df[df["timestamp"] >= cutoff].copy().reset_index(drop=True)

    print(f"\nRecorte de {args.days} dias recentes:")
    print(f"  Linhas: {len(df_recent)}")
    print(f"  Período: {df_recent['timestamp'].min()}  →  {df_recent['timestamp'].max()}")

    # ATR 14 e 30
    df_recent["ATR_14"] = compute_atr(df_recent, window=14)
    df_recent["ATR_30"] = compute_atr(df_recent, window=30)

    df_recent["ATR_14_pct"] = df_recent["ATR_14"] / df_recent["close"]
    df_recent["ATR_30_pct"] = df_recent["ATR_30"] / df_recent["close"]

    print("\n" + "=" * 80)
    print("ANÁLISE DE VOLATILIDADE (ATR em % do preço)")
    print("=" * 80)
    print("\nATR_14_pct (ultimos N dias):")
    print(df_recent["ATR_14_pct"].describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]).to_string())

    print("\nATR_30_pct (ultimos N dias):")
    print(df_recent["ATR_30_pct"].describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]).to_string())

    # Análise de retornos futuros para diferentes horizontes
    # Ex: 5, 10, 20, 30, 60, 120 candles (1m)
    horizons = [5, 10, 20, 30, 60, 120]
    # Thresholds em %: 0.2%, 0.5%, 1%, 2%
    thresholds = [0.002, 0.005, 0.01, 0.02]

    analyze_future_returns(df_recent, horizons, thresholds)

    print("\nAnálise concluída. Use esses números para calibrar:")
    print("  - label_horizon (em candles)")
    print("  - thresholds dos labels (ex: 0.5%, 1%)")
    print("  - buy_signal_threshold / sell_signal_threshold")


if __name__ == "__main__":
    main()