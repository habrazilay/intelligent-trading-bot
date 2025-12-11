#!/usr/bin/env python3
"""
Threshold Optimizer - Auto-tuning de thresholds baseado em performance real

Este script:
1. Analisa trades fechados e correlaciona score do sinal com PnL
2. Encontra thresholds ótimos que maximizam profit
3. Atualiza configs automaticamente
4. Roda em loop para ajuste contínuo (reinforcement learning style)

A ideia é que quanto mais trades o bot faz, mais ele aprende quais
scores realmente geram lucro e ajusta os thresholds accordingly.
"""

import os
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import pandas as pd
from dataclasses import dataclass
from dotenv import load_dotenv

# Paths
BASE_DIR = Path(__file__).parent.parent
LOGS_DIR = BASE_DIR / "logs" / "trades"
CONFIGS_DIR = BASE_DIR / "configs"
TRADES_LOG = LOGS_DIR / "trades_history.jsonl"
POSITIONS_LOG = LOGS_DIR / "positions_snapshots.jsonl"
OPTIMIZER_LOG = LOGS_DIR / "optimizer_history.jsonl"


@dataclass
class ThresholdRecommendation:
    """Recomendação de threshold otimizado."""
    buy_threshold: float
    sell_threshold: float
    expected_win_rate: float
    expected_profit_factor: float
    confidence: float  # 0-1, baseado em quantidade de dados
    reason: str


class ThresholdOptimizer:
    """
    Otimizador de thresholds usando dados reais de trading.

    Estratégias de otimização:
    1. Score Binning: Agrupa trades por faixa de score e analisa win rate
    2. Gradient Search: Busca thresholds que maximizam profit factor
    3. Bayesian Update: Atualiza probabilidades com cada novo trade
    4. Adaptive: Ajusta mais agressivamente quando confiança é alta
    """

    def __init__(self, min_trades: int = 10, learning_rate: float = 0.1):
        """
        Args:
            min_trades: Mínimo de trades para começar a otimizar
            learning_rate: Taxa de ajuste (0.1 = 10% por iteração)
        """
        self.min_trades = min_trades
        self.learning_rate = learning_rate

        # Histórico de otimizações
        self.optimization_history = []

        # Carregar histórico anterior se existir
        if OPTIMIZER_LOG.exists():
            with open(OPTIMIZER_LOG, 'r') as f:
                for line in f:
                    self.optimization_history.append(json.loads(line))

    def load_trade_data(self) -> pd.DataFrame:
        """Carrega dados de trades com scores."""
        if not TRADES_LOG.exists():
            return pd.DataFrame()

        trades = []
        with open(TRADES_LOG, 'r') as f:
            for line in f:
                trade = json.loads(line)
                # Só pegar trades fechados
                if trade.get('event_type') == 'CLOSE':
                    signal_info = trade.get('signal_info', {})
                    trades.append({
                        'timestamp': trade['timestamp'],
                        'symbol': trade['symbol'],
                        'direction': trade.get('direction', 'UNKNOWN'),
                        'entry_price': trade.get('entry_price', 0),
                        'exit_price': trade.get('exit_price', 0),
                        'realized_pnl': trade.get('realized_pnl', 0),
                        'trade_score': signal_info.get('trade_score', 0),
                        'strategy': signal_info.get('strategy', 'unknown'),
                    })

        if not trades:
            return pd.DataFrame()

        df = pd.DataFrame(trades)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['is_winner'] = df['realized_pnl'] > 0

        return df

    def load_snapshot_scores(self) -> pd.DataFrame:
        """
        Carrega scores de posições abertas dos snapshots.
        Útil quando ainda não há trades fechados.
        """
        if not POSITIONS_LOG.exists():
            return pd.DataFrame()

        # Pegar último snapshot de cada posição
        snapshots = {}
        with open(POSITIONS_LOG, 'r') as f:
            for line in f:
                snap = json.loads(line)
                for pos in snap.get('positions', []):
                    symbol = pos['symbol']
                    snapshots[symbol] = {
                        'timestamp': snap['timestamp'],
                        'symbol': symbol,
                        'direction': pos['direction'],
                        'unrealized_pnl': pos['unrealized_pnl'],
                        'pnl_percent': pos['pnl_percent'],
                        'entry_price': pos['entry_price'],
                        'current_price': pos['current_price'],
                    }

        if not snapshots:
            return pd.DataFrame()

        # Adicionar scores dos sinais
        records = []
        for symbol, data in snapshots.items():
            # Tentar carregar score do sinal
            for strategy in ['quick', 'conservative']:
                signal_file = BASE_DIR / f"DATA_ITB_1h/{symbol}/signals_{strategy}.csv"
                if signal_file.exists():
                    df = pd.read_csv(signal_file)
                    df = df.sort_values('timestamp')
                    last = df.iloc[-1]
                    data['trade_score'] = float(last.get('trade_score', 0))
                    data['strategy'] = strategy
                    break

            records.append(data)

        return pd.DataFrame(records)

    def analyze_score_performance(self, df: pd.DataFrame) -> dict:
        """
        Analisa performance por faixa de score.

        Returns:
            Dict com estatísticas por faixa de score
        """
        if df.empty:
            return {}

        # Definir bins de score
        bins = [-1.0, -0.1, -0.05, -0.02, -0.01, 0, 0.01, 0.02, 0.05, 0.1, 1.0]
        labels = ['-0.1+', '-0.05/-0.1', '-0.02/-0.05', '-0.01/-0.02',
                  '-0.01/0', '0/0.01', '0.01/0.02', '0.02/0.05', '0.05/0.1', '0.1+']

        df['score_bin'] = pd.cut(df['trade_score'], bins=bins, labels=labels)

        results = {}
        for bin_label in labels:
            bin_data = df[df['score_bin'] == bin_label]
            if len(bin_data) > 0:
                results[bin_label] = {
                    'count': len(bin_data),
                    'win_rate': bin_data['is_winner'].mean() if 'is_winner' in bin_data else None,
                    'avg_pnl': bin_data['realized_pnl'].mean() if 'realized_pnl' in bin_data else bin_data['unrealized_pnl'].mean(),
                    'total_pnl': bin_data['realized_pnl'].sum() if 'realized_pnl' in bin_data else bin_data['unrealized_pnl'].sum(),
                }

        return results

    def find_optimal_thresholds(self, df: pd.DataFrame) -> ThresholdRecommendation:
        """
        Encontra thresholds ótimos usando grid search + análise estatística.

        Estratégia:
        1. Para LONG: encontrar score mínimo onde win_rate > 50% e avg_pnl > 0
        2. Para SHORT: encontrar score máximo (negativo) com mesmos critérios
        3. Adicionar margem de segurança baseada na variância
        """
        if df.empty or len(df) < self.min_trades:
            return ThresholdRecommendation(
                buy_threshold=0.02,
                sell_threshold=-0.02,
                expected_win_rate=50.0,
                expected_profit_factor=1.0,
                confidence=0.0,
                reason=f"Dados insuficientes ({len(df)}/{self.min_trades} trades)"
            )

        # Separar por direção
        longs = df[df['direction'] == 'LONG'] if 'direction' in df else df[df['trade_score'] > 0]
        shorts = df[df['direction'] == 'SHORT'] if 'direction' in df else df[df['trade_score'] < 0]

        # Grid search para buy threshold
        best_buy = 0.02
        best_buy_score = -float('inf')

        for threshold in np.arange(0.005, 0.15, 0.005):
            subset = longs[longs['trade_score'] >= threshold] if not longs.empty else pd.DataFrame()
            if len(subset) >= 3:
                pnl_col = 'realized_pnl' if 'realized_pnl' in subset else 'unrealized_pnl'
                win_rate = subset['is_winner'].mean() if 'is_winner' in subset else (subset[pnl_col] > 0).mean()
                avg_pnl = subset[pnl_col].mean()

                # Score = win_rate * avg_pnl * sqrt(count) (recompensa mais dados)
                score = win_rate * avg_pnl * np.sqrt(len(subset))

                if score > best_buy_score:
                    best_buy_score = score
                    best_buy = threshold

        # Grid search para sell threshold
        best_sell = -0.02
        best_sell_score = -float('inf')

        for threshold in np.arange(-0.15, -0.005, 0.005):
            subset = shorts[shorts['trade_score'] <= threshold] if not shorts.empty else pd.DataFrame()
            if len(subset) >= 3:
                pnl_col = 'realized_pnl' if 'realized_pnl' in subset else 'unrealized_pnl'
                win_rate = subset['is_winner'].mean() if 'is_winner' in subset else (subset[pnl_col] > 0).mean()
                avg_pnl = subset[pnl_col].mean()

                score = win_rate * avg_pnl * np.sqrt(len(subset))

                if score > best_sell_score:
                    best_sell_score = score
                    best_sell = threshold

        # Calcular métricas esperadas
        all_qualifying = pd.concat([
            longs[longs['trade_score'] >= best_buy] if not longs.empty else pd.DataFrame(),
            shorts[shorts['trade_score'] <= best_sell] if not shorts.empty else pd.DataFrame()
        ])

        if len(all_qualifying) > 0:
            pnl_col = 'realized_pnl' if 'realized_pnl' in all_qualifying else 'unrealized_pnl'
            win_rate = all_qualifying['is_winner'].mean() * 100 if 'is_winner' in all_qualifying else (all_qualifying[pnl_col] > 0).mean() * 100

            wins = all_qualifying[all_qualifying[pnl_col] > 0][pnl_col]
            losses = all_qualifying[all_qualifying[pnl_col] < 0][pnl_col]

            gross_profit = wins.sum() if len(wins) > 0 else 0
            gross_loss = abs(losses.sum()) if len(losses) > 0 else 1
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 1.0
        else:
            win_rate = 50.0
            profit_factor = 1.0

        # Calcular confiança (0-1) baseado em quantidade de dados
        confidence = min(1.0, len(df) / 100)  # 100 trades = 100% confiança

        return ThresholdRecommendation(
            buy_threshold=round(best_buy, 4),
            sell_threshold=round(best_sell, 4),
            expected_win_rate=round(win_rate, 2),
            expected_profit_factor=round(profit_factor, 2),
            confidence=round(confidence, 2),
            reason=f"Baseado em {len(df)} trades, {len(all_qualifying)} qualifying"
        )

    def get_current_thresholds(self, config_file: str) -> Tuple[float, float]:
        """Lê thresholds atuais de um config file."""
        config_path = CONFIGS_DIR / config_file
        if not config_path.exists():
            return 0.02, -0.02

        with open(config_path, 'r') as f:
            content = f.read()

        # Extrair valores usando regex (funciona com JSONC)
        buy_match = re.search(r'"buy_signal_threshold"\s*:\s*([-\d.]+)', content)
        sell_match = re.search(r'"sell_signal_threshold"\s*:\s*([-\d.]+)', content)

        buy = float(buy_match.group(1)) if buy_match else 0.02
        sell = float(sell_match.group(1)) if sell_match else -0.02

        return buy, sell

    def update_config_thresholds(self, config_file: str,
                                  new_buy: float, new_sell: float,
                                  gradual: bool = True) -> bool:
        """
        Atualiza thresholds em um config file.

        Args:
            config_file: Nome do arquivo (ex: 'base_conservative.jsonc')
            new_buy: Novo threshold de compra
            new_sell: Novo threshold de venda
            gradual: Se True, aplica learning_rate para mudança gradual
        """
        config_path = CONFIGS_DIR / config_file
        if not config_path.exists():
            print(f"Config não encontrado: {config_path}")
            return False

        # Ler thresholds atuais
        current_buy, current_sell = self.get_current_thresholds(config_file)

        # Aplicar learning rate para mudança gradual
        if gradual:
            new_buy = current_buy + self.learning_rate * (new_buy - current_buy)
            new_sell = current_sell + self.learning_rate * (new_sell - current_sell)

        # Arredondar para 4 casas decimais
        new_buy = round(new_buy, 4)
        new_sell = round(new_sell, 4)

        # Ler arquivo
        with open(config_path, 'r') as f:
            content = f.read()

        # Substituir valores
        content = re.sub(
            r'("buy_signal_threshold"\s*:\s*)([-\d.]+)',
            f'\\g<1>{new_buy}',
            content
        )
        content = re.sub(
            r'("sell_signal_threshold"\s*:\s*)([-\d.]+)',
            f'\\g<1>{new_sell}',
            content
        )

        # Salvar
        with open(config_path, 'w') as f:
            f.write(content)

        print(f"Config atualizado: {config_file}")
        print(f"  buy_threshold: {current_buy} -> {new_buy}")
        print(f"  sell_threshold: {current_sell} -> {new_sell}")

        return True

    def log_optimization(self, recommendation: ThresholdRecommendation,
                         config_file: str, applied: bool):
        """Salva histórico de otimização."""
        record = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'config_file': config_file,
            'buy_threshold': recommendation.buy_threshold,
            'sell_threshold': recommendation.sell_threshold,
            'expected_win_rate': recommendation.expected_win_rate,
            'expected_profit_factor': recommendation.expected_profit_factor,
            'confidence': recommendation.confidence,
            'reason': recommendation.reason,
            'applied': applied,
        }

        with open(OPTIMIZER_LOG, 'a') as f:
            f.write(json.dumps(record) + '\n')

        self.optimization_history.append(record)

    def optimize(self, config_file: str = 'base_conservative.jsonc',
                 auto_apply: bool = False,
                 min_confidence: float = 0.3) -> ThresholdRecommendation:
        """
        Executa otimização completa.

        Args:
            config_file: Arquivo de config a otimizar
            auto_apply: Se True, aplica automaticamente se confiança >= min_confidence
            min_confidence: Confiança mínima para auto-aplicar
        """
        print("\n" + "=" * 60)
        print("  THRESHOLD OPTIMIZER")
        print("=" * 60)

        # Carregar dados
        trades_df = self.load_trade_data()
        snapshots_df = self.load_snapshot_scores()

        print(f"\nDados carregados:")
        print(f"  Trades fechados: {len(trades_df)}")
        print(f"  Posições em snapshots: {len(snapshots_df)}")

        # Combinar dados (trades fechados + snapshots para análise mais rica)
        if not trades_df.empty and len(trades_df) >= self.min_trades:
            df = trades_df
            data_source = "trades fechados"
        elif not snapshots_df.empty:
            # Usar snapshots quando não há trades fechados suficientes
            df = snapshots_df.copy()
            df['is_winner'] = df['unrealized_pnl'] > 0
            df['realized_pnl'] = df['unrealized_pnl']  # Usar unrealized como proxy
            data_source = f"snapshots de posições (poucos trades fechados: {len(trades_df)})"
        elif not trades_df.empty:
            df = trades_df
            data_source = f"trades fechados ({len(trades_df)} - abaixo do mínimo)"
        else:
            print("\nSem dados suficientes para otimização.")
            return ThresholdRecommendation(
                buy_threshold=0.02,
                sell_threshold=-0.02,
                expected_win_rate=50.0,
                expected_profit_factor=1.0,
                confidence=0.0,
                reason="Sem dados"
            )

        print(f"  Usando: {data_source}")

        # Analisar performance por score
        print("\nPerformance por faixa de score:")
        score_analysis = self.analyze_score_performance(df)
        for bin_label, stats in score_analysis.items():
            if stats['count'] > 0:
                pnl = stats['avg_pnl']
                emoji = "🟢" if pnl > 0 else "🔴"
                print(f"  {bin_label}: {stats['count']} trades, avg PnL: {emoji} ${pnl:.2f}")

        # Encontrar thresholds ótimos
        recommendation = self.find_optimal_thresholds(df)

        print(f"\n{'=' * 60}")
        print("  RECOMENDAÇÃO")
        print(f"{'=' * 60}")
        print(f"  Buy Threshold:  {recommendation.buy_threshold}")
        print(f"  Sell Threshold: {recommendation.sell_threshold}")
        print(f"  Win Rate Esperado: {recommendation.expected_win_rate}%")
        print(f"  Profit Factor: {recommendation.expected_profit_factor}")
        print(f"  Confiança: {recommendation.confidence * 100:.0f}%")
        print(f"  Razão: {recommendation.reason}")

        # Comparar com atual
        current_buy, current_sell = self.get_current_thresholds(config_file)
        print(f"\n  Atual em {config_file}:")
        print(f"    buy_threshold: {current_buy}")
        print(f"    sell_threshold: {current_sell}")

        # Aplicar se auto_apply e confiança suficiente
        applied = False
        if auto_apply and recommendation.confidence >= min_confidence:
            print(f"\n  Auto-aplicando (confiança {recommendation.confidence:.0%} >= {min_confidence:.0%})...")
            applied = self.update_config_thresholds(
                config_file,
                recommendation.buy_threshold,
                recommendation.sell_threshold,
                gradual=True
            )
        elif auto_apply:
            print(f"\n  Não aplicado: confiança muito baixa ({recommendation.confidence:.0%} < {min_confidence:.0%})")

        # Logar
        self.log_optimization(recommendation, config_file, applied)

        print("=" * 60 + "\n")

        return recommendation

    def run_continuous(self, config_file: str = 'base_conservative.jsonc',
                       interval_minutes: int = 30,
                       auto_apply: bool = True):
        """
        Roda otimização contínua.

        O optimizer vai:
        1. Analisar trades a cada N minutos
        2. Ajustar thresholds gradualmente quando confiança é alta
        3. Logar todas as mudanças
        """
        import time

        print(f"Iniciando otimização contínua...")
        print(f"  Config: {config_file}")
        print(f"  Intervalo: {interval_minutes} minutos")
        print(f"  Auto-apply: {auto_apply}")
        print(f"\nPressione Ctrl+C para parar.\n")

        try:
            while True:
                self.optimize(config_file, auto_apply=auto_apply)
                print(f"Próxima otimização em {interval_minutes} minutos...")
                time.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            print("\nOtimização parada pelo usuário.")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Threshold Optimizer')
    parser.add_argument('--config', default='base_conservative.jsonc',
                        help='Config file to optimize')
    parser.add_argument('--apply', action='store_true',
                        help='Auto-apply recommendations')
    parser.add_argument('--continuous', action='store_true',
                        help='Run continuously')
    parser.add_argument('--interval', type=int, default=30,
                        help='Interval in minutes for continuous mode')
    parser.add_argument('--min-confidence', type=float, default=0.3,
                        help='Minimum confidence to auto-apply')
    parser.add_argument('--learning-rate', type=float, default=0.1,
                        help='Learning rate for gradual updates')

    args = parser.parse_args()

    optimizer = ThresholdOptimizer(learning_rate=args.learning_rate)

    if args.continuous:
        optimizer.run_continuous(
            config_file=args.config,
            interval_minutes=args.interval,
            auto_apply=args.apply
        )
    else:
        optimizer.optimize(
            config_file=args.config,
            auto_apply=args.apply,
            min_confidence=args.min_confidence
        )


if __name__ == '__main__':
    main()
