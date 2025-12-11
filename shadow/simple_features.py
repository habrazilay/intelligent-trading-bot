"""
Simple Feature Generation without TA-Lib

Calculates basic technical indicators using only pandas/numpy.
This allows shadow mode to run without the TA-Lib native library.
"""

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=window).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=window, adjust=False).mean()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()

    rs = gain / loss
    return 100 - (100 / (1 + rs))


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """Average True Range."""
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.rolling(window=window).mean()


def stddev(series: pd.Series, window: int) -> pd.Series:
    """Standard Deviation."""
    return series.rolling(window=window).std()


def linear_reg_slope(series: pd.Series, window: int) -> pd.Series:
    """Linear Regression Slope."""
    def calc_slope(arr):
        if len(arr) < window or np.isnan(arr).any():
            return np.nan
        x = np.arange(len(arr))
        slope, _ = np.polyfit(x, arr, 1)
        return slope

    return series.rolling(window=window).apply(calc_slope, raw=True)


def add_simple_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add technical indicator features to a DataFrame with OHLCV data.

    Expected columns: open, high, low, close, volume

    Returns DataFrame with added feature columns.
    """
    df = df.copy()

    # SMAs
    for w in [5, 10, 20, 60]:
        df[f'close_SMA_{w}'] = sma(df['close'], w)

    # RSI
    df['close_RSI_14'] = rsi(df['close'], 14)

    # Linear Regression Slopes
    for w in [10, 20, 60]:
        df[f'close_LINEARREG_SLOPE_{w}'] = linear_reg_slope(df['close'], w)

    # ATR
    df['high_low_close_ATR_14'] = atr(df['high'], df['low'], df['close'], 14)

    # Standard Deviation
    for w in [20, 60]:
        df[f'close_STDDEV_{w}'] = stddev(df['close'], w)

    return df


def generate_labels(df: pd.DataFrame, horizon: int = 60, threshold: float = 0.5) -> pd.DataFrame:
    """
    Generate high/low labels for ML.

    high_05_60: 1 if price goes up >0.5% in next 60 candles
    low_05_60: 1 if price goes down >0.5% in next 60 candles
    """
    df = df.copy()

    # Future max high
    future_high = df['high'].rolling(window=horizon).max().shift(-horizon)
    # Future min low
    future_low = df['low'].rolling(window=horizon).min().shift(-horizon)

    # High label: did price go up by threshold%?
    df['high_05_60'] = ((future_high / df['close'] - 1) * 100 >= threshold).astype(float)

    # Low label: did price go down by threshold%?
    df['low_05_60'] = ((1 - future_low / df['close']) * 100 >= threshold).astype(float)

    return df


def generate_signals_simple(df: pd.DataFrame, buy_threshold: float = 0.002, sell_threshold: float = -0.002) -> pd.DataFrame:
    """
    Generate simple trading signals based on momentum.

    Uses a combination of RSI, SMA crossover, and slope.
    """
    df = df.copy()

    # Momentum score based on multiple indicators
    score = 0.0

    # RSI component: oversold (< 30) is bullish, overbought (> 70) is bearish
    rsi_score = (50 - df['close_RSI_14'].fillna(50)) / 100  # -0.2 to +0.2

    # SMA crossover: price above SMA20 is bullish
    sma_score = (df['close'] / df['close_SMA_20'].fillna(df['close']) - 1)  # Normalized distance

    # Slope: positive slope is bullish
    slope_score = df['close_LINEARREG_SLOPE_20'].fillna(0) / df['close'].fillna(1) * 1000

    # Combined score
    df['trade_score'] = (rsi_score * 0.3 + sma_score * 0.4 + slope_score * 0.3).clip(-0.1, 0.1)

    # Generate buy/sell signals
    df['buy_signal'] = (df['trade_score'] >= buy_threshold).astype(int)
    df['sell_signal'] = (df['trade_score'] <= sell_threshold).astype(int)

    return df


if __name__ == '__main__':
    # Test with sample data
    import sys
    sys.path.insert(0, '.')

    # Load klines
    df = pd.read_parquet('DATA_ITB_1m/BTCUSDT/klines.parquet')
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.set_index('timestamp')

    # Take last 1000 rows for test
    df = df.tail(1000).copy()

    print("Original shape:", df.shape)
    print("Original columns:", list(df.columns))

    # Add features
    df = add_simple_features(df)
    print("\nWith features shape:", df.shape)
    print("Feature columns:", [c for c in df.columns if 'SMA' in c or 'RSI' in c or 'ATR' in c or 'SLOPE' in c or 'STDDEV' in c])

    # Add signals
    df = generate_signals_simple(df)
    print("\nWith signals shape:", df.shape)
    print("Signal columns:", [c for c in df.columns if 'signal' in c or 'score' in c])

    # Show recent signals
    recent = df.tail(100)
    buy_count = recent['buy_signal'].sum()
    sell_count = recent['sell_signal'].sum()
    print(f"\nLast 100 candles: {buy_count} buy signals, {sell_count} sell signals")
