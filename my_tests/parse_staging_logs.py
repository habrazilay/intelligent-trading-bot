from pathlib import Path
from collections import defaultdict
import re
import sys

import json
from datetime import datetime


# Regex para extrair timestamp do início da linha
TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})")

# Regex para detectar o intervalo do kline (1m, 5m, etc.)
INTERVAL_RE = re.compile(
    r'GET /api/v3/klines\?endTime=\d+&interval=(\dm)&limit=\d+&symbol=BTCUSDT'
)

# Regex para capturar o resultado da análise
ANALYZE_RE = re.compile(
    r"Analyze finished\. Close:\s+([0-9.,]+)\s+Signals: trade_score=([+\-0-9.,]+), buy_signal=(True|False), sell_signal=(True|False)"
)


def parse_price(s: str) -> float:
    """Converte string de preço tipo '93,790' ou '93.790' para float."""
    s = s.strip()
    if "," in s and "." in s:
        # Ex: 93,790.12 => 93790.12
        s = s.replace(",", "")
    else:
        s = s.replace(",", "")
    return float(s)


def parse_score(s: str) -> float:
    """Converte trade_score em float (+0.006, -0.003 etc.)."""
    s = s.strip().replace(",", ".")
    return float(s)


def analyze_server_log(log_path: Path, notional_usdt: float = 5.0):
    if not log_path.exists():
        print(f"Arquivo de log não encontrado: {log_path}")
        return

    print(f"Usando log: {log_path}")

    # Estrutura: por timeframe, manter sequências de eventos e trades
    stats = {
        "1m": {
            "signals_buy": 0,
            "signals_sell": 0,
            "trades": [],
            "position_open": False,
            "entry_price": 0.0,
            "entry_ts": None,
        },
        "5m": {
            "signals_buy": 0,
            "signals_sell": 0,
            "trades": [],
            "position_open": False,
            "entry_price": 0.0,
            "entry_ts": None,
        },
    }

    current_tf = None  # "1m" ou "5m"

    text = log_path.read_text(errors="ignore")
    for line in text.splitlines():
        # timestamp da linha
        m_ts = TIMESTAMP_RE.match(line)
        ts_str = m_ts.group(1) if m_ts else None

        # 1) Detectar timeframe pelo GET klines...
        m_int = INTERVAL_RE.search(line)
        if m_int:
            current_tf = m_int.group(1)  # "1m", "5m", ...
            # focamos em 1m e 5m apenas
            if current_tf not in stats:
                current_tf = None
            continue

        # 2) Pegar resultado de análise com signals
        m_an = ANALYZE_RE.search(line)
        if not m_an or current_tf is None:
            continue

        close_str, score_str, buy_str, sell_str = m_an.groups()
        close_price = parse_price(close_str)
        trade_score = parse_score(score_str)
        buy_signal = buy_str == "True"
        sell_signal = sell_str == "True"

        tf_state = stats[current_tf]

        if buy_signal:
            tf_state["signals_buy"] += 1
        if sell_signal:
            tf_state["signals_sell"] += 1

        # Simples: entra quando BUY, sai quando SELL
        if buy_signal and not tf_state["position_open"]:
            tf_state["position_open"] = True
            tf_state["entry_price"] = close_price
            tf_state["entry_ts"] = ts_str
        elif sell_signal and tf_state["position_open"]:
            exit_price = close_price
            exit_ts = ts_str
            ret_pct = (exit_price - tf_state["entry_price"]) / tf_state["entry_price"]
            pnl_usdt = notional_usdt * ret_pct
            tf_state["trades"].append(
                {
                    "entry_ts": tf_state["entry_ts"],
                    "exit_ts": exit_ts,
                    "entry_price": tf_state["entry_price"],
                    "exit_price": exit_price,
                    "ret_pct": ret_pct,
                    "pnl_usdt": pnl_usdt,
                }
            )
            tf_state["position_open"] = False
            tf_state["entry_price"] = 0.0
            tf_state["entry_ts"] = None

    # Impressão de resultados
    for tf_label, tf_state in stats.items():
        print("\n" + "=" * 80)
        print(f"Resumo staging BTCUSDT {tf_label}")
        print("=" * 80)
        print(f"Sinais BUY:  {tf_state['signals_buy']}")
        print(f"Sinais SELL: {tf_state['signals_sell']}")
        print(f"Trades fechados: {len(tf_state['trades'])}")

        if not tf_state["trades"]:
            print("Nenhum trade fechado nesse timeframe.")
            continue

        total_pnl = sum(t["pnl_usdt"] for t in tf_state["trades"])
        avg_pnl = total_pnl / len(tf_state["trades"])
        wins = [t for t in tf_state["trades"] if t["pnl_usdt"] > 0]
        win_rate = len(wins) / len(tf_state["trades"]) * 100

        best = max(tf_state["trades"], key=lambda t: t["pnl_usdt"])
        worst = min(tf_state["trades"], key=lambda t: t["pnl_usdt"])

        print(f"Win rate: {win_rate:.1f}%")
        print(f"Lucro total (notional {notional_usdt:.2f}): {total_pnl:.4f} USDT")
        print(f"Lucro médio por trade: {avg_pnl:.4f} USDT")
        print(
            f"Melhor trade: {best['pnl_usdt']:.4f} USDT "
            f"({best['entry_ts']} -> {best['exit_ts']})"
        )
        print(
            f"Pior trade:   {worst['pnl_usdt']:.4f} USDT "
            f"({worst['entry_ts']} -> {worst['exit_ts']})"
        )


def main():
    # Por padrão, usamos server.log na raiz
    if len(sys.argv) > 1:
        log_path = Path(sys.argv[1])
    else:
        log_path = Path("server.log")

    analyze_server_log(log_path, notional_usdt=5.0)
def save_summary(stats_1m, stats_5m, log_source="server.log"):
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir = Path("logs") / "analytics"
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "run_timestamp": datetime.now().isoformat(),
        "log_source": log_source,
        "btcusdt_1m": stats_1m,
        "btcusdt_5m": stats_5m,
    }

    out_path = out_dir / f"staging_summary_{ts}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\nResumo salvo em: {out_path}\n")


if __name__ == "__main__":
    # aqui você chama suas funções de parse normalmente:
    # stats_1m = parse_timeframe_1m(...)
    # stats_5m = parse_timeframe_5m(...)

    # exemplo de estrutura esperada
    stats_1m = {
        "timeframe": "1m",
        "signals_buy": 328,
        "signals_sell": 120,
        "closed_trades": 16,
        "win_rate": 0.3125,
        "total_pnl_usdt": -0.0264,
        "avg_pnl_usdt": -0.0016,
        "best_trade_usdt": 0.0157,
        "worst_trade_usdt": -0.0136,
    }

    stats_5m = {
        "timeframe": "5m",
        "signals_buy": 45,
        "signals_sell": 19,
        "closed_trades": 8,
        "win_rate": 0.25,
        "total_pnl_usdt": -0.0346,
        "avg_pnl_usdt": -0.0043,
        "best_trade_usdt": 0.0069,
        "worst_trade_usdt": -0.0223,
    }

    # depois de imprimir no terminal, salva:
    save_summary(stats_1m, stats_5m, log_source="server.log")    
    # ou
    save_summary(stats_1m, stats_5m, log_source="staging.log")
main()