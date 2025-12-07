from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple, Any

# Aceita tanto "Signals" quanto "Sinals", e variação de espaços
# Exemplo de linha:
# 2025-12-04 06:02:01,322 INFO Analyze finished. Close: 93,521 Signals: trade score=+0.003, buy_signal=True, sell_signal=False
SIGNAL_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}).*?"
    r"Analyze finished\.\s+Close:\s+([0-9.,]+)\s+S\w+:\s*trade[_ ]score=([+\-]?[0-9.,]+),\s*"
    r"buy_signal=(True|False),\s*sell_signal=(True|False)"
)


def parse_price(s: str) -> float:
    """
    Converte string de preço tipo '93,790' ou '93.790' para float.
    """
    s = s.strip()
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    return float(s)


def parse_score(s: str) -> float:
    """
    trade_score pode vir como +0.006, -0.003, 0.01 etc.
    Também aceita vírgula como decimal.
    """
    s = s.strip().replace(",", ".")
    return float(s)


def parse_log_files(files: List[Path], notional_usdt: float) -> Dict[str, Any]:
    files = sorted(files)
    position_open = False
    entry_price = 0.0
    entry_ts: str | None = None

    trades: List[Dict[str, Any]] = []
    n_signals_buy = 0
    n_signals_sell = 0

    for f in files:
        text = f.read_text(errors="ignore")
        for line in text.splitlines():
            m = SIGNAL_RE.search(line)
            if not m:
                continue

            ts_str, close_str, score_str, buy_str, sell_str = m.group(
                "ts"
            ), *m.groups()[1:]
            close_price = parse_price(close_str)
            # trade_score = parse_score(score_str)  # Mantemos pra futuro filtro, se quiser
            buy_signal = buy_str == "True"
            sell_signal = sell_str == "True"

            if buy_signal:
                n_signals_buy += 1
            if sell_signal:
                n_signals_sell += 1

            if buy_signal and not position_open:
                position_open = True
                entry_price = close_price
                entry_ts = ts_str
            elif sell_signal and position_open:
                exit_price = close_price
                exit_ts = ts_str
                ret_pct = (exit_price - entry_price) / entry_price
                pnl_usdt = notional_usdt * ret_pct
                trades.append(
                    {
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "ret_pct": ret_pct,
                        "pnl_usdt": pnl_usdt,
                        "entry_ts": entry_ts,
                        "exit_ts": exit_ts,
                    }
                )
                position_open = False
                entry_price = 0.0
                entry_ts = None

    wins = [t for t in trades if t["pnl_usdt"] > 0]
    losses = [t for t in trades if t["pnl_usdt"] <= 0]

    total_pnl = sum(t["pnl_usdt"] for t in trades)
    avg_pnl = total_pnl / len(trades) if trades else 0.0
    win_rate = (len(wins) / len(trades) * 100.0) if trades else 0.0

    best_trade = max(trades, key=lambda t: t["pnl_usdt"]) if trades else None
    worst_trade = min(trades, key=lambda t: t["pnl_usdt"]) if trades else None

    return {
        "signals": {
            "buy": n_signals_buy,
            "sell": n_signals_sell,
        },
        "trades": {
            "closed": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": win_rate,
            "pnl_total_usdt": total_pnl,
            "pnl_avg_usdt": avg_pnl,
            "best_trade": best_trade,
            "worst_trade": worst_trade,
        },
    }


def print_human_summary(label: str, summary: Dict[str, Any], notional_usdt: float):
    sig = summary["signals"]
    tr = summary["trades"]

    print("\n" + "=" * 80)
    print(f"Resumo staging {label}")
    print("=" * 80)
    print(f"Sinais BUY:  {sig['buy']}")
    print(f"Sinais SELL: {sig['sell']}")
    print(f"Trades fechados: {tr['closed']}")
    if tr["closed"] == 0:
        print("Nenhum trade fechado, nada a reportar ainda.")
        return

    print(f"Win rate: {tr['win_rate_pct']:.1f}%")
    print(
        f"Lucro total (notional {notional_usdt:.2f}): "
        f"{tr['pnl_total_usdt']:.4f} USDT"
    )
    print(f"Lucro médio por trade: {tr['pnl_avg_usdt']:.4f} USDT")

    best = tr["best_trade"]
    worst = tr["worst_trade"]
    if best:
        print(
            f"Melhor trade: {best['pnl_usdt']:.4f} USDT "
            f"({best['entry_ts']} -> {best['exit_ts']})"
        )
    if worst:
        print(
            f"Pior trade:   {worst['pnl_usdt']:.4f} USDT "
            f"({worst['entry_ts']} -> {worst['exit_ts']})"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Analisa logs de staging (BTCUSDT 1m/5m) e gera resumo + JSON."
    )
    parser.add_argument(
        "--logs-dir",
        default="logs",
        help="Diretório onde estão os logs (default: logs). Ex: logs ou logs/raw",
    )
    parser.add_argument(
        "--symbol",
        default="BTCUSDT",
        help="Símbolo (apenas para metadados do JSON, default: BTCUSDT)",
    )
    parser.add_argument(
        "--notional",
        type=float,
        default=5.0,
        help="Notional em USDT por trade na simulação (default: 5.0)",
    )
    args = parser.parse_args()

    logs_dir = Path(args.logs_dir)
    analytics_dir = logs_dir / "analytics"
    analytics_dir.mkdir(parents=True, exist_ok=True)

    # Descobrir arquivos
    files_1m = sorted(logs_dir.glob("server_1m_*.log"))
    files_5m = sorted(logs_dir.glob("server_5m_*.log"))

    summaries: Dict[str, Any] = {
        "symbol": args.symbol,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "notional_usdt": args.notional,
        "logs_dir": str(logs_dir),
        "timeframes": {},
    }

    if files_1m:
        summary_1m = parse_log_files(files_1m, args.notional)
        summaries["timeframes"]["1m"] = {
            "files": [f.name for f in files_1m],
            **summary_1m,
        }
        print_human_summary(f"{args.symbol} 1m staging", summary_1m, args.notional)
    else:
        print("Nenhum log 1m encontrado (server_1m_*.log).")

    if files_5m:
        summary_5m = parse_log_files(files_5m, args.notional)
        summaries["timeframes"]["5m"] = {
            "files": [f.name for f in files_5m],
            **summary_5m,
        }
        print_human_summary(f"{args.symbol} 5m staging", summary_5m, args.notional)
    else:
        print("Nenhum log 5m encontrado (server_5m_*.log).")

    # Salvar JSON
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    json_path = analytics_dir / f"staging_summary_{args.symbol}_{ts}.json"
    json_path.write_text(json.dumps(summaries, indent=2, ensure_ascii=False))
    print(f"\nSnapshot JSON salvo em: {json_path}")


if __name__ == "__main__":
    main()