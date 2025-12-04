#!/usr/bin/env python
"""
Análise de BTCUSDT 1h para calibrar horizonte (label_horizon), thresholds e volatilidade.

Uso:
  source itb-venv/bin/activate
  python analyze_btcusdt_1h.py \
      --parquet DATA_ITB_1h/BTCUSDT/klines.parquet \
      --days 365

O script:
  - Carrega o klines.parquet (1h)
  - Recorta apenas os últimos N dias
  - Calcula ATR(14) e ATR(30)
  - Calcula retornos futuros em vários horizontes (6, 12, 24, 48 candles de 1h)
  - Mostra com que frequência BTC se move ±0.5%, ±1%, ±2%, ±4%
"""

import argparse
from pathlib import Path

import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser(description="Análise estatística BTCUSDT 1h")
    parser.add_argument(
        "--parquet",
        type=str,
        default="DATA_ITB_1h/BTCUSDT/klines.parquet",
        help="Caminho para o klines.parquet de 1h",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Número de dias recentes para analisar (default: 365)",
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
    Para cada horizonte (em candles de 1h), calcula distribuição de retornos futuros
    e probabilidade de ultrapassar/abaixar determinados thresholds.
    """
    print("\n" + "=" * 80)
    print("ANÁLISE DE RETORNOS FUTUROS (em %)")
    print("=" * 80)

    for h in horizons:
        future_close = df["close"].shift(-h)
        future_ret = (future_close - df["close"]) / df["close"]

        print(f"\n--- Horizonte: {h} candles (1h) ---")
        print(f"  (~ {h} horas)")
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

    print(f"Lendo parquet de 1h: {parquet_path}")
    df = pd.read_parquet(parquet_path)

    ensure_columns(df)

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    print("\nDimensão total do dataset 1h:")
    print(f"  Linhas: {len(df)}")
    print(f"  Período: {df['timestamp'].min()}  →  {df['timestamp'].max()}")

    cutoff = df["timestamp"].max() - pd.Timedelta(days=args.days)
    df_recent = df[df["timestamp"] >= cutoff].copy().reset_index(drop=True)

    print(f"\nRecorte de {args.days} dias recentes:")
    print(f"  Linhas: {len(df_recent)}")
    print(f"  Período: {df_recent['timestamp'].min()}  →  {df_recent['timestamp'].max()}")

    # ATR
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

    # Horizons em 1h: 6h, 12h, 24h, 48h
    horizons = [6, 12, 24, 48]
    # Thresholds em %: 0.5%, 1%, 2%, 4%
    thresholds = [0.005, 0.01, 0.02, 0.04]

    analyze_future_returns(df_recent, horizons, thresholds)

    print("\nAnálise concluída. Use esses números para calibrar:")
    print("  - label_horizon (em candles de 1h: ex 12, 24, 48)")
    print("  - thresholds dos labels (ex: 1%, 2%)")
    print("  - buy_signal_threshold / sell_signal_threshold e grade do simulate_model")


if __name__ == "__main__":
    main()