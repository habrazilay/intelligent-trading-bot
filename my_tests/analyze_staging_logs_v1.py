from pathlib import Path
import re
from typing import List

# Aceita tanto "Signals" quanto "Sinals", e variação de espaços
SIGNAL_RE = re.compile(
    r"Analyze finished\.\s+Close:\s+([0-9.,]+)\s+S\w+:\s*trade[_ ]score=([+\-]?[0-9.,]+),\s*buy_signal=(True|False),\s*sell_signal=(True|False)"
)

def parse_price(s: str) -> float:
    """
    Converte string de preço tipo '93,790' ou '93.790' para float.
    """
    s = s.strip()
    # se tiver vírgula e ponto, assume vírgula como separador decimal BR
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
    s = s.strip()
    s = s.replace(",", ".")
    return float(s)

def analyze_files(files: List[Path], label: str, notional_usdt: float = 5.0):
    files = sorted(files)
    print(f"\n=== Analisando {label} ===")
    print(f"Arquivos: {[f.name for f in files]}")

    position_open = False
    entry_price = 0.0

    trades = []
    n_signals_buy = 0
    n_signals_sell = 0

    for f in files:
        text = f.read_text(errors="ignore")
        for line in text.splitlines():
            m = SIGNAL_RE.search(line)
            if not m:
                continue

            close_str, score_str, buy_str, sell_str = m.groups()
            close_price = parse_price(close_str)
            trade_score = parse_score(score_str)
            buy_signal = buy_str == "True"
            sell_signal = sell_str == "True"

            if buy_signal:
                n_signals_buy += 1
            if sell_signal:
                n_signals_sell += 1

            # lógica simples: BUY abre, SELL fecha
            if buy_signal and not position_open:
                position_open = True
                entry_price = close_price
            elif sell_signal and position_open:
                exit_price = close_price
                ret_pct = (exit_price - entry_price) / entry_price
                pnl_usdt = notional_usdt * ret_pct
                trades.append(
                    {
                        "entry": entry_price,
                        "exit": exit_price,
                        "ret_pct": ret_pct,
                        "pnl_usdt": pnl_usdt,
                    }
                )
                position_open = False
                entry_price = 0.0

    print(f"Sinais BUY:  {n_signals_buy}")
    print(f"Sinais SELL: {n_signals_sell}")
    print(f"Trades fechados: {len(trades)}")

    if not trades:
        print("Nenhum trade fechado, nada a reportar ainda.")
        return

    wins = [t for t in trades if t["pnl_usdt"] > 0]
    losses = [t for t in trades if t["pnl_usdt"] <= 0]

    total_pnl = sum(t["pnl_usdt"] for t in trades)
    avg_pnl = total_pnl / len(trades)
    win_rate = len(wins) / len(trades) * 100

    print(f"Win rate: {win_rate:.1f}%")
    print(f"Lucro total: {total_pnl:.4f} USDT (notional {notional_usdt:.2f})")
    print(f"Lucro médio por trade: {avg_pnl:.4f} USDT")
    print(f"Melhor trade: {max(trades, key=lambda t: t['pnl_usdt'])['pnl_usdt']:.4f} USDT")
    print(f"Pior trade:   {min(trades, key=lambda t: t['pnl_usdt'])['pnl_usdt']:.4f} USDT")


def main():
    logs_dir = Path("logs")

    # 1m
    files_1m = list(logs_dir.glob("server_1m_*.log"))
    if files_1m:
        analyze_files(files_1m, "BTCUSDT 1m staging", notional_usdt=5.0)
    else:
        print("Nenhum log 1m encontrado em logs/server_1m_*.log")

    # 5m
    files_5m = list(logs_dir.glob("server_5m_*.log"))
    if files_5m:
        analyze_files(files_5m, "BTCUSDT 5m staging", notional_usdt=5.0)
    else:
        print("Nenhum log 5m encontrado em logs/server_5m_*.log")


if __name__ == "__main__":
    main()