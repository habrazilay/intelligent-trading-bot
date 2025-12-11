"""
Advanced Backtesting Engine

Simula trading com:
- Fees e slippage realistas
- Position sizing (percentage-based)
- Stop-loss / Take-profit
- Métricas avançadas (Sharpe, Sortino, Max Drawdown)
- Suporte a múltiplas estratégias

Usage:
    from backtest.engine import BacktestEngine

    engine = BacktestEngine(config)
    results = engine.run(df, 'buy_signal', 'sell_signal')
    engine.print_summary()
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import json


@dataclass
class Trade:
    """Representa um trade completo (entry + exit)."""
    trade_id: int
    side: str  # 'LONG' or 'SHORT'
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    quantity: float
    notional: float
    pnl: float
    pnl_pct: float
    fee_entry: float
    fee_exit: float
    exit_reason: str  # 'signal', 'stop_loss', 'take_profit'
    hold_bars: int


@dataclass
class BacktestConfig:
    """Configuração do backtest."""
    # Capital
    initial_balance: float = 10000.0

    # Position sizing
    position_size_pct: float = 2.0  # % do balance por trade
    min_notional: float = 10.0

    # Custos
    fee_pct: float = 0.1  # 0.1% = 10 bps (Binance spot)
    slippage_bps: float = 5.0  # 5 bps slippage médio

    # Risk management
    stop_loss_pct: float = 2.0  # -2% stop loss
    take_profit_pct: float = 3.0  # +3% take profit
    use_stop_loss: bool = True
    use_take_profit: bool = True

    # Strategy
    allow_short: bool = False  # Só long por padrão

    @classmethod
    def from_dict(cls, d: dict) -> 'BacktestConfig':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class BacktestResult:
    """Resultado completo do backtest."""
    config: BacktestConfig
    trades: List[Trade]
    equity_curve: pd.Series

    # Summary metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    total_fees: float = 0.0

    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0

    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0

    avg_hold_bars: float = 0.0

    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': round(self.win_rate, 2),
            'total_pnl': round(self.total_pnl, 2),
            'total_pnl_pct': round(self.total_pnl_pct, 2),
            'total_fees': round(self.total_fees, 2),
            'profit_factor': round(self.profit_factor, 2),
            'avg_win': round(self.avg_win, 2),
            'avg_loss': round(self.avg_loss, 2),
            'max_drawdown_pct': round(self.max_drawdown_pct, 2),
            'sharpe_ratio': round(self.sharpe_ratio, 3),
            'sortino_ratio': round(self.sortino_ratio, 3),
            'avg_hold_bars': round(self.avg_hold_bars, 1),
            'start_date': str(self.start_date) if self.start_date else None,
            'end_date': str(self.end_date) if self.end_date else None,
        }


class BacktestEngine:
    """
    Motor de backtesting realista.

    Simula execução de trades com fees, slippage, stop-loss e take-profit.
    """

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()
        self.reset()

    def reset(self):
        """Reset state for new backtest."""
        self.balance = self.config.initial_balance
        self.position = None  # {'side': 'LONG', 'entry_price': X, 'quantity': Y, 'entry_time': T}
        self.trades: List[Trade] = []
        self.equity_history: List[Tuple[datetime, float]] = []
        self.trade_counter = 0

    def run(
        self,
        df: pd.DataFrame,
        buy_signal_col: str = 'buy_signal',
        sell_signal_col: str = 'sell_signal',
        price_col: str = 'close',
        high_col: str = 'high',
        low_col: str = 'low',
    ) -> BacktestResult:
        """
        Executa backtest no DataFrame.

        Args:
            df: DataFrame com OHLCV e sinais
            buy_signal_col: Coluna com sinal de compra (1/0)
            sell_signal_col: Coluna com sinal de venda (1/0)
            price_col: Coluna de preço para execução
            high_col: Coluna de high (para stop-loss/take-profit)
            low_col: Coluna de low (para stop-loss/take-profit)

        Returns:
            BacktestResult com todas as métricas
        """
        self.reset()

        required_cols = [buy_signal_col, sell_signal_col, price_col]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Coluna '{col}' não encontrada no DataFrame")

        # Iterar sobre cada candle
        for idx, row in df.iterrows():
            timestamp = idx if isinstance(idx, (datetime, pd.Timestamp)) else None
            price = row[price_col]
            high = row.get(high_col, price)
            low = row.get(low_col, price)
            buy_signal = row[buy_signal_col]
            sell_signal = row[sell_signal_col]

            if pd.isna(price) or price <= 0:
                continue

            # Check stop-loss / take-profit primeiro
            if self.position:
                exit_reason = self._check_exit_conditions(high, low, timestamp)
                if exit_reason:
                    self._close_position(price, timestamp, exit_reason)

            # Processar sinais
            if self.position is None:
                # Sem posição - pode abrir
                if buy_signal:
                    self._open_position('LONG', price, timestamp)
                elif sell_signal and self.config.allow_short:
                    self._open_position('SHORT', price, timestamp)
            else:
                # Com posição - verificar saída por sinal
                if self.position['side'] == 'LONG' and sell_signal:
                    self._close_position(price, timestamp, 'signal')
                elif self.position['side'] == 'SHORT' and buy_signal:
                    self._close_position(price, timestamp, 'signal')

            # Registrar equity
            current_equity = self._calculate_equity(price)
            self.equity_history.append((timestamp, current_equity))

        # Fechar posição aberta no final
        if self.position:
            last_price = df[price_col].iloc[-1]
            last_time = df.index[-1] if isinstance(df.index[-1], (datetime, pd.Timestamp)) else None
            self._close_position(last_price, last_time, 'end_of_data')

        # Calcular métricas
        return self._calculate_results(df)

    def _apply_slippage(self, price: float, side: str, is_entry: bool) -> float:
        """Aplica slippage ao preço."""
        slippage_mult = self.config.slippage_bps / 10000

        if side == 'LONG':
            if is_entry:  # Comprando - paga mais
                return price * (1 + slippage_mult)
            else:  # Vendendo - recebe menos
                return price * (1 - slippage_mult)
        else:  # SHORT
            if is_entry:  # Vendendo - recebe menos
                return price * (1 - slippage_mult)
            else:  # Comprando - paga mais
                return price * (1 + slippage_mult)

    def _calculate_fee(self, notional: float) -> float:
        """Calcula fee baseado no notional."""
        return notional * (self.config.fee_pct / 100)

    def _open_position(self, side: str, price: float, timestamp: datetime):
        """Abre nova posição."""
        # Calcular tamanho da posição
        position_value = self.balance * (self.config.position_size_pct / 100)
        position_value = max(position_value, self.config.min_notional)
        position_value = min(position_value, self.balance * 0.95)  # Max 95% do balance

        if position_value < self.config.min_notional:
            return  # Balance insuficiente

        # Aplicar slippage
        exec_price = self._apply_slippage(price, side, is_entry=True)

        # Calcular quantidade
        quantity = position_value / exec_price

        # Calcular fee
        fee = self._calculate_fee(position_value)

        # Deduzir capital usado do balance (position_value + fee)
        self.balance -= (position_value + fee)

        # Criar posição
        self.position = {
            'side': side,
            'entry_price': exec_price,
            'quantity': quantity,
            'entry_time': timestamp,
            'entry_fee': fee,
            'notional': position_value,
            'bars_held': 0,
        }

    def _close_position(self, price: float, timestamp: datetime, reason: str):
        """Fecha posição atual."""
        if not self.position:
            return

        side = self.position['side']
        entry_price = self.position['entry_price']
        quantity = self.position['quantity']
        entry_time = self.position['entry_time']
        entry_fee = self.position['entry_fee']
        entry_notional = self.position['notional']

        # Aplicar slippage
        exec_price = self._apply_slippage(price, side, is_entry=False)

        # Calcular notional de saída
        exit_notional = quantity * exec_price
        exit_fee = self._calculate_fee(exit_notional)

        # Calcular PnL bruto
        if side == 'LONG':
            pnl_gross = (exec_price - entry_price) * quantity
        else:  # SHORT
            pnl_gross = (entry_price - exec_price) * quantity

        # PnL líquido (já deduzimos entry_fee na abertura, só exit_fee aqui)
        pnl_net = pnl_gross - exit_fee
        pnl_pct = (pnl_net / entry_notional) * 100

        # Devolver capital + PnL ao balance
        self.balance += exit_notional - exit_fee

        # Calcular bars held
        bars_held = self.position.get('bars_held', 0)

        # Registrar trade
        self.trade_counter += 1
        trade = Trade(
            trade_id=self.trade_counter,
            side=side,
            entry_time=entry_time,
            entry_price=entry_price,
            exit_time=timestamp,
            exit_price=exec_price,
            quantity=quantity,
            notional=entry_notional,
            pnl=pnl_net,
            pnl_pct=pnl_pct,
            fee_entry=entry_fee,
            fee_exit=exit_fee,
            exit_reason=reason,
            hold_bars=bars_held,
        )
        self.trades.append(trade)

        # Limpar posição
        self.position = None

    def _check_exit_conditions(self, high: float, low: float, timestamp: datetime) -> Optional[str]:
        """Verifica stop-loss e take-profit."""
        if not self.position:
            return None

        self.position['bars_held'] = self.position.get('bars_held', 0) + 1

        entry_price = self.position['entry_price']
        side = self.position['side']

        if side == 'LONG':
            # Stop loss: preço caiu X%
            if self.config.use_stop_loss:
                stop_price = entry_price * (1 - self.config.stop_loss_pct / 100)
                if low <= stop_price:
                    return 'stop_loss'

            # Take profit: preço subiu X%
            if self.config.use_take_profit:
                tp_price = entry_price * (1 + self.config.take_profit_pct / 100)
                if high >= tp_price:
                    return 'take_profit'

        else:  # SHORT
            # Stop loss: preço subiu X%
            if self.config.use_stop_loss:
                stop_price = entry_price * (1 + self.config.stop_loss_pct / 100)
                if high >= stop_price:
                    return 'stop_loss'

            # Take profit: preço caiu X%
            if self.config.use_take_profit:
                tp_price = entry_price * (1 - self.config.take_profit_pct / 100)
                if low <= tp_price:
                    return 'take_profit'

        return None

    def _calculate_equity(self, current_price: float) -> float:
        """Calcula equity atual (balance + unrealized PnL)."""
        if not self.position:
            return self.balance

        side = self.position['side']
        entry_price = self.position['entry_price']
        quantity = self.position['quantity']

        if side == 'LONG':
            unrealized = (current_price - entry_price) * quantity
        else:
            unrealized = (entry_price - current_price) * quantity

        return self.balance + unrealized

    def _calculate_results(self, df: pd.DataFrame) -> BacktestResult:
        """Calcula todas as métricas do backtest."""
        result = BacktestResult(
            config=self.config,
            trades=self.trades,
            equity_curve=pd.Series(
                [e[1] for e in self.equity_history],
                index=[e[0] for e in self.equity_history]
            )
        )

        if not self.trades:
            return result

        # Basic stats
        result.total_trades = len(self.trades)
        result.winning_trades = sum(1 for t in self.trades if t.pnl > 0)
        result.losing_trades = sum(1 for t in self.trades if t.pnl <= 0)

        result.total_pnl = sum(t.pnl for t in self.trades)
        result.total_pnl_pct = (self.balance / self.config.initial_balance - 1) * 100
        result.total_fees = sum(t.fee_entry + t.fee_exit for t in self.trades)

        result.win_rate = (result.winning_trades / result.total_trades) * 100

        # Profit factor
        gross_profit = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trades if t.pnl <= 0))
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Average win/loss
        wins = [t.pnl for t in self.trades if t.pnl > 0]
        losses = [t.pnl for t in self.trades if t.pnl <= 0]
        result.avg_win = np.mean(wins) if wins else 0
        result.avg_loss = np.mean(losses) if losses else 0

        # Hold time
        result.avg_hold_bars = np.mean([t.hold_bars for t in self.trades])

        # Drawdown
        result.max_drawdown_pct = self._calculate_max_drawdown()

        # Sharpe & Sortino
        result.sharpe_ratio, result.sortino_ratio = self._calculate_risk_ratios()

        # Dates
        result.start_date = df.index[0] if isinstance(df.index[0], (datetime, pd.Timestamp)) else None
        result.end_date = df.index[-1] if isinstance(df.index[-1], (datetime, pd.Timestamp)) else None

        return result

    def _calculate_max_drawdown(self) -> float:
        """Calcula máximo drawdown em %."""
        if not self.equity_history:
            return 0.0

        equity = np.array([e[1] for e in self.equity_history])
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak * 100
        return float(np.max(drawdown))

    def _calculate_risk_ratios(self) -> Tuple[float, float]:
        """Calcula Sharpe e Sortino ratios."""
        if len(self.equity_history) < 2:
            return 0.0, 0.0

        equity = np.array([e[1] for e in self.equity_history])
        returns = np.diff(equity) / equity[:-1]

        if len(returns) == 0 or np.std(returns) == 0:
            return 0.0, 0.0

        # Sharpe (assumindo 0% risk-free rate para simplificar)
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252 * 24 * 60)  # Anualizado para 1m

        # Sortino (só considera volatilidade negativa)
        negative_returns = returns[returns < 0]
        downside_std = np.std(negative_returns) if len(negative_returns) > 0 else np.std(returns)
        sortino = np.mean(returns) / downside_std * np.sqrt(252 * 24 * 60) if downside_std > 0 else 0

        return float(sharpe), float(sortino)

    def print_summary(self, result: BacktestResult = None):
        """Imprime resumo do backtest."""
        if result is None and self.trades:
            result = self._calculate_results(pd.DataFrame())

        if not result:
            print("Nenhum resultado disponível")
            return

        print("\n" + "=" * 60)
        print("BACKTEST SUMMARY")
        print("=" * 60)
        print(f"Initial Balance:    ${self.config.initial_balance:,.2f}")
        print(f"Final Balance:      ${self.balance:,.2f}")
        print(f"Total PnL:          ${result.total_pnl:,.2f} ({result.total_pnl_pct:+.2f}%)")
        print(f"Total Fees:         ${result.total_fees:,.2f}")
        print("-" * 60)
        print(f"Total Trades:       {result.total_trades}")
        print(f"Win Rate:           {result.win_rate:.1f}%")
        print(f"Profit Factor:      {result.profit_factor:.2f}")
        print(f"Avg Win:            ${result.avg_win:,.2f}")
        print(f"Avg Loss:           ${result.avg_loss:,.2f}")
        print("-" * 60)
        print(f"Max Drawdown:       {result.max_drawdown_pct:.2f}%")
        print(f"Sharpe Ratio:       {result.sharpe_ratio:.3f}")
        print(f"Sortino Ratio:      {result.sortino_ratio:.3f}")
        print(f"Avg Hold Time:      {result.avg_hold_bars:.1f} bars")
        print("=" * 60)

        # Exit reasons
        if self.trades:
            reasons = {}
            for t in self.trades:
                reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1
            print("\nExit Reasons:")
            for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
                print(f"  {reason}: {count} ({100*count/len(self.trades):.1f}%)")


class GridSearchOptimizer:
    """
    Otimizador de parâmetros via grid search.

    Testa múltiplas combinações de parâmetros e encontra a melhor.
    """

    def __init__(self, base_config: BacktestConfig = None):
        self.base_config = base_config or BacktestConfig()
        self.results: List[Dict] = []

    def optimize(
        self,
        df: pd.DataFrame,
        param_grid: Dict[str, List],
        signal_generator,  # Função que recebe df e params, retorna df com sinais
        metric: str = 'sharpe_ratio',
        minimize: bool = False,
    ) -> Tuple[Dict, BacktestResult]:
        """
        Executa grid search sobre os parâmetros.

        Args:
            df: DataFrame com OHLCV
            param_grid: Dict de parâmetros para testar
                Ex: {'buy_threshold': [0.001, 0.002, 0.003], 'stop_loss_pct': [1.0, 2.0, 3.0]}
            signal_generator: Função(df, params) -> df com sinais
            metric: Métrica para otimizar
            minimize: Se True, minimiza a métrica (ex: para drawdown)

        Returns:
            (best_params, best_result)
        """
        from itertools import product

        self.results = []

        # Gerar todas as combinações
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(product(*param_values))

        print(f"Testing {len(combinations)} parameter combinations...")

        best_score = float('inf') if minimize else float('-inf')
        best_params = None
        best_result = None

        for i, combo in enumerate(combinations):
            params = dict(zip(param_names, combo))

            # Atualizar config com parâmetros de backtest
            config = BacktestConfig(
                initial_balance=self.base_config.initial_balance,
                position_size_pct=params.get('position_size_pct', self.base_config.position_size_pct),
                fee_pct=params.get('fee_pct', self.base_config.fee_pct),
                slippage_bps=params.get('slippage_bps', self.base_config.slippage_bps),
                stop_loss_pct=params.get('stop_loss_pct', self.base_config.stop_loss_pct),
                take_profit_pct=params.get('take_profit_pct', self.base_config.take_profit_pct),
                use_stop_loss=params.get('use_stop_loss', self.base_config.use_stop_loss),
                use_take_profit=params.get('use_take_profit', self.base_config.use_take_profit),
            )

            # Gerar sinais com os parâmetros
            df_signals = signal_generator(df.copy(), params)

            # Rodar backtest
            engine = BacktestEngine(config)
            result = engine.run(df_signals)

            # Extrair métrica
            score = getattr(result, metric, 0)

            # Salvar resultado
            self.results.append({
                'params': params,
                'score': score,
                'result': result.to_dict(),
            })

            # Verificar se é o melhor
            is_better = (score < best_score) if minimize else (score > best_score)
            if is_better:
                best_score = score
                best_params = params
                best_result = result

            # Progress
            if (i + 1) % 10 == 0 or i == len(combinations) - 1:
                print(f"  [{i+1}/{len(combinations)}] Best {metric}: {best_score:.4f}")

        print(f"\nBest parameters: {best_params}")
        print(f"Best {metric}: {best_score:.4f}")

        return best_params, best_result

    def get_results_df(self) -> pd.DataFrame:
        """Retorna resultados como DataFrame."""
        if not self.results:
            return pd.DataFrame()

        rows = []
        for r in self.results:
            row = {**r['params'], **r['result'], 'score': r['score']}
            rows.append(row)

        return pd.DataFrame(rows)


if __name__ == '__main__':
    # Teste básico
    import sys
    sys.path.insert(0, '.')

    from shadow.simple_features import add_simple_features, generate_signals_simple

    # Carregar dados
    print("Loading data...")
    df = pd.read_parquet('DATA_ITB_1m/BTCUSDT/klines.parquet')
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.set_index('timestamp')

    # Usar últimos 30 dias
    df = df.tail(30 * 24 * 60)
    print(f"Data shape: {df.shape}")

    # Adicionar features e sinais
    print("Adding features...")
    df = add_simple_features(df)
    df = generate_signals_simple(df, buy_threshold=0.002, sell_threshold=-0.002)

    # Rodar backtest
    print("Running backtest...")
    config = BacktestConfig(
        initial_balance=10000,
        position_size_pct=2.0,
        stop_loss_pct=2.0,
        take_profit_pct=3.0,
    )

    engine = BacktestEngine(config)
    result = engine.run(df)
    engine.print_summary(result)
