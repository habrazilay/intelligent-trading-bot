"""
ML-Based Trading Strategy

Usa LightGBM para prever movimentos de preço baseado em features técnicas.
Muito mais sofisticado que a estratégia simples de momentum.

Features:
- Indicadores técnicos (RSI, SMA, ATR, etc)
- Padrões de volatilidade
- Momentum em múltiplos timeframes
- Volume patterns

Usage:
    from backtest.ml_strategy import MLStrategy

    strategy = MLStrategy()
    strategy.train(df_train)
    df_signals = strategy.generate_signals(df_test)
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional, Dict
from dataclasses import dataclass
import warnings

warnings.filterwarnings('ignore')

# Try to import lightgbm
try:
    import lightgbm as lgb
    LGBM_AVAILABLE = True
except ImportError:
    LGBM_AVAILABLE = False
    print("⚠️  LightGBM not available. Install with: pip install lightgbm")


@dataclass
class MLStrategyConfig:
    """Configuração da estratégia ML."""
    # Label generation
    label_horizon: int = 60  # Candles para olhar no futuro
    up_threshold: float = 0.5  # % de alta para considerar "UP"
    down_threshold: float = 0.5  # % de queda para considerar "DOWN"

    # Signal thresholds
    buy_prob_threshold: float = 0.6  # Prob mínima para BUY
    sell_prob_threshold: float = 0.6  # Prob mínima para SELL

    # Model params
    n_estimators: int = 100
    learning_rate: float = 0.1
    max_depth: int = 5
    min_child_samples: int = 100

    # Training
    train_ratio: float = 0.7  # % de dados para treino


def add_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adiciona features técnicas avançadas.

    Muito mais features que a estratégia simples.
    """
    df = df.copy()

    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']

    # ========== Price-based features ==========

    # Returns em múltiplos períodos
    for period in [1, 5, 15, 30, 60]:
        df[f'return_{period}'] = close.pct_change(period)

    # SMAs
    for period in [5, 10, 20, 50, 100]:
        df[f'sma_{period}'] = close.rolling(period).mean()
        df[f'close_to_sma_{period}'] = close / df[f'sma_{period}'] - 1

    # EMAs
    for period in [12, 26]:
        df[f'ema_{period}'] = close.ewm(span=period, adjust=False).mean()

    # MACD
    df['macd'] = df['ema_12'] - df['ema_26']
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']

    # RSI em múltiplos períodos
    for period in [7, 14, 21]:
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        df[f'rsi_{period}'] = 100 - (100 / (1 + rs))

    # ========== Volatility features ==========

    # ATR
    for period in [7, 14, 21]:
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df[f'atr_{period}'] = tr.rolling(period).mean()
        df[f'atr_{period}_pct'] = df[f'atr_{period}'] / close * 100

    # Bollinger Bands
    for period in [20]:
        sma = close.rolling(period).mean()
        std = close.rolling(period).std()
        df[f'bb_upper_{period}'] = sma + 2 * std
        df[f'bb_lower_{period}'] = sma - 2 * std
        df[f'bb_width_{period}'] = (df[f'bb_upper_{period}'] - df[f'bb_lower_{period}']) / sma
        df[f'bb_position_{period}'] = (close - df[f'bb_lower_{period}']) / (df[f'bb_upper_{period}'] - df[f'bb_lower_{period}'])

    # Volatility (std of returns)
    for period in [10, 30, 60]:
        df[f'volatility_{period}'] = df['return_1'].rolling(period).std() * np.sqrt(period)

    # ========== Volume features ==========

    # Volume SMAs
    for period in [5, 20]:
        df[f'volume_sma_{period}'] = volume.rolling(period).mean()
        df[f'volume_ratio_{period}'] = volume / df[f'volume_sma_{period}']

    # VWAP approximation
    typical_price = (high + low + close) / 3
    df['vwap_20'] = (typical_price * volume).rolling(20).sum() / volume.rolling(20).sum()
    df['close_to_vwap'] = close / df['vwap_20'] - 1

    # ========== Momentum features ==========

    # Rate of Change
    for period in [5, 10, 20]:
        df[f'roc_{period}'] = (close / close.shift(period) - 1) * 100

    # Linear regression slope
    for period in [10, 20, 60]:
        def calc_slope(arr):
            if len(arr) < period or np.isnan(arr).any():
                return np.nan
            x = np.arange(len(arr))
            slope, _ = np.polyfit(x, arr, 1)
            return slope
        df[f'slope_{period}'] = close.rolling(period).apply(calc_slope, raw=True)
        df[f'slope_{period}_norm'] = df[f'slope_{period}'] / close * 1000

    # ========== Pattern features ==========

    # Candlestick features
    df['body_size'] = abs(close - df['open']) / close
    df['upper_shadow'] = (high - df[['open', 'close']].max(axis=1)) / close
    df['lower_shadow'] = (df[['open', 'close']].min(axis=1) - low) / close
    df['is_bullish'] = (close > df['open']).astype(int)

    # High/Low position
    df['high_position'] = (close - low) / (high - low + 1e-10)

    # ========== Time features ==========

    if isinstance(df.index, pd.DatetimeIndex):
        df['hour'] = df.index.hour
        df['day_of_week'] = df.index.dayofweek
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)

    return df


def generate_labels(df: pd.DataFrame, horizon: int = 60, up_threshold: float = 0.5, down_threshold: float = 0.5) -> pd.DataFrame:
    """
    Gera labels para treino do modelo.

    UP: preço subiu mais que up_threshold% nos próximos N candles
    DOWN: preço caiu mais que down_threshold% nos próximos N candles
    """
    df = df.copy()

    close = df['close']

    # Máximo e mínimo nos próximos N candles
    future_max = close.rolling(horizon).max().shift(-horizon)
    future_min = close.rolling(horizon).min().shift(-horizon)

    # Retorno máximo e mínimo
    max_return = (future_max / close - 1) * 100
    min_return = (future_min / close - 1) * 100

    # Labels
    df['label_up'] = (max_return >= up_threshold).astype(int)
    df['label_down'] = (abs(min_return) >= down_threshold).astype(int)

    return df


class MLStrategy:
    """
    Estratégia de trading baseada em Machine Learning.

    Usa LightGBM para prever probabilidade de UP/DOWN.
    """

    def __init__(self, config: MLStrategyConfig = None):
        if not LGBM_AVAILABLE:
            raise ImportError("LightGBM not installed. Run: pip install lightgbm")

        self.config = config or MLStrategyConfig()
        self.model_up = None
        self.model_down = None
        self.feature_cols = None
        self.is_trained = False

    def _get_feature_columns(self, df: pd.DataFrame) -> list:
        """Retorna colunas de features (exclui OHLCV e labels)."""
        exclude = ['open', 'high', 'low', 'close', 'volume', 'close_time',
                   'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore',
                   'label_up', 'label_down', 'buy_signal', 'sell_signal',
                   'trade_score', 'prob_up', 'prob_down']

        return [c for c in df.columns if c not in exclude and not c.startswith('sma_')
                and not c.startswith('ema_') and not c.startswith('bb_upper')
                and not c.startswith('bb_lower') and not c.startswith('atr_')
                and not c.startswith('volume_sma')]

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepara dados com features e labels."""
        df = add_technical_features(df)
        df = generate_labels(
            df,
            horizon=self.config.label_horizon,
            up_threshold=self.config.up_threshold,
            down_threshold=self.config.down_threshold
        )
        return df

    def train(self, df: pd.DataFrame, verbose: bool = True) -> Dict:
        """
        Treina os modelos de UP e DOWN.

        Returns:
            Dict com métricas de treino
        """
        df = self.prepare_data(df)

        # Get feature columns
        self.feature_cols = self._get_feature_columns(df)

        # Remove NaN rows
        df_clean = df.dropna(subset=self.feature_cols + ['label_up', 'label_down'])

        if len(df_clean) < 1000:
            raise ValueError(f"Not enough data for training: {len(df_clean)} rows")

        if verbose:
            print(f"Training data: {len(df_clean)} rows, {len(self.feature_cols)} features")

        # Split train/val
        split_idx = int(len(df_clean) * self.config.train_ratio)
        df_train = df_clean.iloc[:split_idx]
        df_val = df_clean.iloc[split_idx:]

        X_train = df_train[self.feature_cols]
        X_val = df_val[self.feature_cols]

        # LightGBM params
        params = {
            'objective': 'binary',
            'metric': 'auc',
            'boosting_type': 'gbdt',
            'n_estimators': self.config.n_estimators,
            'learning_rate': self.config.learning_rate,
            'max_depth': self.config.max_depth,
            'min_child_samples': self.config.min_child_samples,
            'verbose': -1,
            'random_state': 42,
        }

        # Train UP model
        if verbose:
            print("Training UP model...")
        y_train_up = df_train['label_up']
        y_val_up = df_val['label_up']

        self.model_up = lgb.LGBMClassifier(**params)
        self.model_up.fit(
            X_train, y_train_up,
            eval_set=[(X_val, y_val_up)],
        )

        # Train DOWN model
        if verbose:
            print("Training DOWN model...")
        y_train_down = df_train['label_down']
        y_val_down = df_val['label_down']

        self.model_down = lgb.LGBMClassifier(**params)
        self.model_down.fit(
            X_train, y_train_down,
            eval_set=[(X_val, y_val_down)],
        )

        self.is_trained = True

        # Calculate metrics
        from sklearn.metrics import roc_auc_score, accuracy_score

        pred_up_train = self.model_up.predict_proba(X_train)[:, 1]
        pred_up_val = self.model_up.predict_proba(X_val)[:, 1]
        pred_down_train = self.model_down.predict_proba(X_train)[:, 1]
        pred_down_val = self.model_down.predict_proba(X_val)[:, 1]

        metrics = {
            'up_auc_train': roc_auc_score(y_train_up, pred_up_train),
            'up_auc_val': roc_auc_score(y_val_up, pred_up_val),
            'down_auc_train': roc_auc_score(y_train_down, pred_down_train),
            'down_auc_val': roc_auc_score(y_val_down, pred_down_val),
            'train_size': len(df_train),
            'val_size': len(df_val),
            'up_rate_train': y_train_up.mean(),
            'down_rate_train': y_train_down.mean(),
        }

        if verbose:
            print(f"\nTraining Results:")
            print(f"  UP model AUC:   train={metrics['up_auc_train']:.3f}, val={metrics['up_auc_val']:.3f}")
            print(f"  DOWN model AUC: train={metrics['down_auc_train']:.3f}, val={metrics['down_auc_val']:.3f}")
            print(f"  Label rates:    UP={metrics['up_rate_train']:.1%}, DOWN={metrics['down_rate_train']:.1%}")

        return metrics

    def generate_signals(self, df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
        """
        Gera sinais de trading baseado nas previsões do modelo.

        Args:
            df: DataFrame com OHLCV
            params: Opcional, pode override buy_prob_threshold e sell_prob_threshold

        Returns:
            DataFrame com colunas buy_signal, sell_signal, prob_up, prob_down
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")

        # Prepare features
        df = add_technical_features(df)

        # Get predictions
        df_features = df[self.feature_cols].copy()

        # Handle NaN
        valid_idx = df_features.dropna().index

        df['prob_up'] = np.nan
        df['prob_down'] = np.nan

        if len(valid_idx) > 0:
            X = df_features.loc[valid_idx]
            df.loc[valid_idx, 'prob_up'] = self.model_up.predict_proba(X)[:, 1]
            df.loc[valid_idx, 'prob_down'] = self.model_down.predict_proba(X)[:, 1]

        # Generate signals based on thresholds
        buy_threshold = params.get('buy_prob_threshold', self.config.buy_prob_threshold) if params else self.config.buy_prob_threshold
        sell_threshold = params.get('sell_prob_threshold', self.config.sell_prob_threshold) if params else self.config.sell_prob_threshold

        # Buy when UP prob high and DOWN prob low
        # Sell when DOWN prob high and UP prob low
        df['buy_signal'] = (
            (df['prob_up'] >= buy_threshold) &
            (df['prob_down'] < sell_threshold)
        ).astype(int)

        df['sell_signal'] = (
            (df['prob_down'] >= sell_threshold) &
            (df['prob_up'] < buy_threshold)
        ).astype(int)

        return df

    def get_feature_importance(self, top_n: int = 20) -> pd.DataFrame:
        """Retorna importância das features."""
        if not self.is_trained:
            raise RuntimeError("Model not trained")

        importance_up = pd.DataFrame({
            'feature': self.feature_cols,
            'importance_up': self.model_up.feature_importances_
        })

        importance_down = pd.DataFrame({
            'feature': self.feature_cols,
            'importance_down': self.model_down.feature_importances_
        })

        importance = importance_up.merge(importance_down, on='feature')
        importance['importance_total'] = importance['importance_up'] + importance['importance_down']
        importance = importance.sort_values('importance_total', ascending=False)

        return importance.head(top_n)


def run_ml_backtest(
    df: pd.DataFrame,
    train_days: int = 180,
    test_days: int = 30,
    config: MLStrategyConfig = None,
) -> Tuple[pd.DataFrame, Dict]:
    """
    Roda backtest com estratégia ML.

    Divide dados em treino/teste, treina modelo, e retorna sinais.

    Args:
        df: DataFrame com OHLCV
        train_days: Dias para treino
        test_days: Dias para teste
        config: Configuração da estratégia

    Returns:
        (df_test_with_signals, metrics)
    """
    config = config or MLStrategyConfig()

    # Calculate split points
    total_rows = len(df)
    rows_per_day = 24 * 60  # 1-minute candles

    train_rows = train_days * rows_per_day
    test_rows = test_days * rows_per_day

    if train_rows + test_rows > total_rows:
        raise ValueError(f"Not enough data: need {train_rows + test_rows}, have {total_rows}")

    # Split data
    df_train = df.iloc[-(train_rows + test_rows):-test_rows].copy()
    df_test = df.iloc[-test_rows:].copy()

    print(f"Train period: {df_train.index[0]} to {df_train.index[-1]} ({len(df_train)} rows)")
    print(f"Test period:  {df_test.index[0]} to {df_test.index[-1]} ({len(df_test)} rows)")

    # Train strategy
    strategy = MLStrategy(config)
    metrics = strategy.train(df_train)

    # Generate signals for test data
    df_test_signals = strategy.generate_signals(df_test)

    # Add feature importance to metrics
    metrics['feature_importance'] = strategy.get_feature_importance()

    return df_test_signals, metrics


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '.')

    # Load data
    print("Loading data...")
    df = pd.read_parquet('DATA_ITB_1m/BTCUSDT/klines.parquet')
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.set_index('timestamp')

    print(f"Total data: {len(df)} rows")

    # Run ML backtest
    print("\n" + "="*60)
    print("ML STRATEGY BACKTEST")
    print("="*60)

    config = MLStrategyConfig(
        label_horizon=60,
        up_threshold=0.5,
        down_threshold=0.5,
        buy_prob_threshold=0.65,  # Mais seletivo
        sell_prob_threshold=0.65,
    )

    df_signals, metrics = run_ml_backtest(
        df,
        train_days=180,
        test_days=30,
        config=config
    )

    print("\n" + "-"*60)
    print("Feature Importance (Top 10):")
    print(metrics['feature_importance'].head(10).to_string())

    # Count signals
    buy_signals = df_signals['buy_signal'].sum()
    sell_signals = df_signals['sell_signal'].sum()
    print(f"\nSignals generated: {buy_signals} BUY, {sell_signals} SELL")

    # Run backtest
    print("\n" + "-"*60)
    print("Running backtest...")

    from backtest.engine import BacktestEngine, BacktestConfig

    bt_config = BacktestConfig(
        initial_balance=10000,
        position_size_pct=2.0,
        stop_loss_pct=2.0,
        take_profit_pct=3.0,
    )

    engine = BacktestEngine(bt_config)
    result = engine.run(df_signals)
    engine.print_summary(result)
