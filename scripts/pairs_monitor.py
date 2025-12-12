#!/usr/bin/env python3
"""
Pairs Trading Monitor - Real-time Z-Score Monitor

Monitora o Z-Score dos pares de trading e alerta quando há oportunidades.
Também monitora posições abertas e calcula P&L do spread.

Uso:
    python -m scripts.pairs_monitor
    python -m scripts.pairs_monitor --pair MSFT_AMD
    python -m scripts.pairs_monitor --interval 60
"""

import argparse
import time
import sys
from datetime import datetime
from typing import Dict, Optional
import yfinance as yf

# Configuração dos pares
PAIRS_CONFIG = {
    'MSFT_AMD': {
        'symbol_a': 'MSFT',
        'symbol_b': 'AMD',
        'beta': 0.9003,
        'spread_mean': 292.10,
        'spread_std': 9.83,
        'half_life': 11.0,
        'entry_zscore': 2.0,
        'exit_zscore': 0.0,
    },
    'NVDA_AMD': {
        'symbol_a': 'NVDA',
        'symbol_b': 'AMD',
        'beta': 0.82,
        'spread_mean': 0,  # Será calculado
        'spread_std': 1,
        'half_life': 14.3,
        'entry_zscore': 2.0,
        'exit_zscore': 0.0,
    },
    'INTC_AMD': {
        'symbol_a': 'INTC',
        'symbol_b': 'AMD',
        'beta': 0.18,
        'spread_mean': 0,
        'spread_std': 1,
        'half_life': 34.4,
        'entry_zscore': 2.0,
        'exit_zscore': 0.0,
    }
}


def get_price(symbol: str) -> Optional[float]:
    """Busca preço atual via Yahoo Finance"""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        price = info.get('currentPrice') or info.get('regularMarketPrice')
        return price
    except Exception:
        return None


def calculate_zscore(price_a: float, price_b: float, config: Dict) -> tuple:
    """Calcula spread e Z-Score"""
    spread = price_a - config['beta'] * price_b
    zscore = (spread - config['spread_mean']) / config['spread_std']
    return spread, zscore


def get_signal(zscore: float, config: Dict) -> str:
    """Determina sinal baseado no Z-Score"""
    if zscore < -config['entry_zscore']:
        return 'LONG_SPREAD'
    elif zscore > config['entry_zscore']:
        return 'SHORT_SPREAD'
    elif abs(zscore) < config['exit_zscore'] + 0.5:
        return 'EXIT_ZONE'
    else:
        return 'NEUTRAL'


def print_header():
    """Imprime cabeçalho"""
    print('\033[2J\033[H')  # Clear screen
    print('=' * 70)
    print('   📊 PAIRS TRADING MONITOR - Real-time Z-Score')
    print('=' * 70)
    print(f'   Última atualização: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 70)


def print_pair_status(name: str, config: Dict, price_a: float, price_b: float):
    """Imprime status de um par"""
    spread, zscore = calculate_zscore(price_a, price_b, config)
    signal = get_signal(zscore, config)

    # Cores para o terminal
    if signal == 'LONG_SPREAD':
        color = '\033[92m'  # Verde
        emoji = '📈'
    elif signal == 'SHORT_SPREAD':
        color = '\033[91m'  # Vermelho
        emoji = '📉'
    elif signal == 'EXIT_ZONE':
        color = '\033[93m'  # Amarelo
        emoji = '🔔'
    else:
        color = '\033[0m'  # Normal
        emoji = '⏸️'

    reset = '\033[0m'

    print(f'\n   {emoji} {name}')
    print(f'   {"-" * 40}')
    print(f'   {config["symbol_a"]}: ${price_a:.2f}')
    print(f'   {config["symbol_b"]}: ${price_b:.2f}')
    print(f'   Beta: {config["beta"]:.4f}')
    print(f'   Spread: {spread:.2f} (média: {config["spread_mean"]:.2f})')
    print(f'   {color}Z-Score: {zscore:+.2f}{reset}')
    print(f'   {color}Sinal: {signal}{reset}')

    if signal == 'LONG_SPREAD':
        print(f'   → AÇÃO: BUY {config["symbol_a"]} + SELL {config["symbol_b"]}')
    elif signal == 'SHORT_SPREAD':
        print(f'   → AÇÃO: SELL {config["symbol_a"]} + BUY {config["symbol_b"]}')
    elif signal == 'EXIT_ZONE':
        print(f'   → AÇÃO: Considerar fechar posições')

    # Barra visual do Z-Score
    bar_width = 30
    z_normalized = max(-3, min(3, zscore))  # Limitar entre -3 e +3
    z_position = int((z_normalized + 3) / 6 * bar_width)

    bar = ['─'] * bar_width
    bar[bar_width // 2] = '│'  # Centro (Z=0)

    # Marcar zonas
    entry_low = int((-config['entry_zscore'] + 3) / 6 * bar_width)
    entry_high = int((config['entry_zscore'] + 3) / 6 * bar_width)

    if 0 <= z_position < bar_width:
        bar[z_position] = '●'

    bar_str = ''.join(bar)
    print(f'   Z: [{bar_str}]')
    print(f'       -3      -2       0      +2      +3')


def monitor_positions():
    """Monitora posições abertas no MT5"""
    try:
        from service.adapters.metaapi_adapter import MetaApiAdapter
        adapter = MetaApiAdapter()

        positions = adapter.get_positions()
        if not positions:
            return

        print(f'\n   📋 POSIÇÕES MT5:')
        print(f'   {"-" * 40}')

        pairs_symbols = ['MSFT', 'AMD', 'NVDA', 'INTC']
        pairs_pnl = 0

        for p in positions:
            symbol = p.get('symbol', '')
            if symbol in pairs_symbols:
                ptype = p.get('type', '').replace('POSITION_TYPE_', '')
                vol = p.get('volume', 0)
                entry = p.get('openPrice', 0)
                pnl = p.get('profit', 0)
                pairs_pnl += pnl

                pnl_color = '\033[92m' if pnl >= 0 else '\033[91m'
                reset = '\033[0m'

                print(f'   {symbol:<6} {ptype:<5} {vol} @ ${entry:.2f} | {pnl_color}P/L: ${pnl:+.2f}{reset}')

        if pairs_pnl != 0:
            pnl_color = '\033[92m' if pairs_pnl >= 0 else '\033[91m'
            reset = '\033[0m'
            print(f'   {"-" * 40}')
            print(f'   {pnl_color}Total Pairs P/L: ${pairs_pnl:+.2f}{reset}')

    except Exception as e:
        pass  # Silently fail if MT5 not available


def main():
    parser = argparse.ArgumentParser(description='Pairs Trading Monitor')
    parser.add_argument('--pair', type=str, default='all',
                        help='Par específico (MSFT_AMD, NVDA_AMD, INTC_AMD) ou "all"')
    parser.add_argument('--interval', type=int, default=30,
                        help='Intervalo de atualização em segundos (default: 30)')
    parser.add_argument('--once', action='store_true',
                        help='Executar apenas uma vez')

    args = parser.parse_args()

    pairs_to_monitor = PAIRS_CONFIG.keys() if args.pair == 'all' else [args.pair]

    print('Iniciando monitor de Pairs Trading...')
    print(f'Pares: {", ".join(pairs_to_monitor)}')
    print(f'Intervalo: {args.interval}s')
    print('Pressione Ctrl+C para sair.\n')

    try:
        while True:
            print_header()

            for pair_name in pairs_to_monitor:
                if pair_name not in PAIRS_CONFIG:
                    print(f'\n   ⚠️ Par desconhecido: {pair_name}')
                    continue

                config = PAIRS_CONFIG[pair_name]

                price_a = get_price(config['symbol_a'])
                price_b = get_price(config['symbol_b'])

                if price_a and price_b:
                    print_pair_status(pair_name, config, price_a, price_b)
                else:
                    print(f'\n   ⚠️ {pair_name}: Erro ao buscar preços')

            # Monitorar posições MT5
            monitor_positions()

            print('\n' + '=' * 70)
            print(f'   Próxima atualização em {args.interval}s... (Ctrl+C para sair)')
            print('=' * 70)

            if args.once:
                break

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print('\n\nMonitor encerrado.')


if __name__ == '__main__':
    main()
