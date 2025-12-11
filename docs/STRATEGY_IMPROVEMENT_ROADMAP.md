# Strategy Improvement Roadmap

This document provides actionable recommendations to fix the failed trading strategies documented in `STRATEGY_FAILURE_ANALYSIS.md`.

---

## Quick Navigation

1. [Better Features](#better-features)
2. [More Realistic Labels](#more-realistic-labels)
3. [Alternative ML Algorithms](#alternative-ml-algorithms)
4. [Cloud ML Services](#cloud-ml-services)
5. [Implementation Plan](#implementation-plan)

---

## Better Features

### Current Problem
Our features (SMA, RSI, ATR, LINEARREG_SLOPE) are **lagging indicators** that tell us where price WAS, not where it's GOING.

### Solution Categories

#### 1. Order Flow Features (HIGHEST PRIORITY)

**If we have access to order book data via Binance WebSocket:**

```python
# Example features from L2 order book data
def extract_order_flow_features(order_book):
    """
    Extract predictive features from order book depth
    """
    features = {}

    # Bid-ask imbalance at different depths
    for depth in [5, 10, 20, 50]:
        bid_volume = sum([order['qty'] for order in order_book['bids'][:depth]])
        ask_volume = sum([order['qty'] for order in order_book['asks'][:depth]])
        features[f'imbalance_{depth}'] = (bid_volume - ask_volume) / (bid_volume + ask_volume)

    # Order book pressure (slope of cumulative volume)
    bid_prices = [order['price'] for order in order_book['bids'][:20]]
    bid_volumes = [order['qty'] for order in order_book['bids'][:20]]
    features['bid_pressure'] = calculate_slope(bid_prices, np.cumsum(bid_volumes))

    ask_prices = [order['price'] for order in order_book['asks'][:20]]
    ask_volumes = [order['qty'] for order in order_book['asks'][:20]]
    features['ask_pressure'] = calculate_slope(ask_prices, np.cumsum(ask_volumes))

    # Large order detection (walls)
    features['bid_wall'] = max(bid_volumes) / np.mean(bid_volumes)
    features['ask_wall'] = max(ask_volumes) / np.mean(ask_volumes)

    # Effective spread
    features['effective_spread'] = (order_book['asks'][0]['price'] - order_book['bids'][0]['price']) / mid_price

    # Depth imbalance at best levels
    features['level1_imbalance'] = (order_book['bids'][0]['qty'] - order_book['asks'][0]['qty']) / \
                                    (order_book['bids'][0]['qty'] + order_book['asks'][0]['qty'])

    return features
```

**Why this matters:**
- Order flow shows **buying/selling pressure** BEFORE price moves
- Market makers front-run retail using this data
- Studies show 60-70% win rate possible with order flow features

**Implementation:**
1. Use `python-binance` WebSocket to stream order book
2. Store snapshots every 1 second
3. Aggregate to 1m/5m bars with order flow features
4. Add to feature pipeline

**Reference papers:**
- "High-Frequency Trading and Order Book Dynamics" (Cont, 2011)
- "The Volume Clock: Insights into the High-Frequency Paradigm" (Easley, 2012)

---

#### 2. Microstructure Features

**Trade flow analysis:**

```python
def extract_microstructure_features(trades_df, window='1m'):
    """
    Extract features from tick-level trade data
    """
    features = {}

    # Buy vs Sell volume (using trade side)
    buy_volume = trades_df[trades_df['is_buyer_maker'] == False]['qty'].sum()
    sell_volume = trades_df[trades_df['is_buyer_maker'] == True]['qty'].sum()
    features['buy_sell_ratio'] = buy_volume / (sell_volume + 1e-8)
    features['net_volume'] = buy_volume - sell_volume

    # Large trade detection (>1 BTC or >$100k)
    large_trades = trades_df[trades_df['qty'] > 1.0]
    features['large_trade_count'] = len(large_trades)
    features['large_trade_ratio'] = large_trades['qty'].sum() / trades_df['qty'].sum()

    # Trade size distribution
    features['trade_size_mean'] = trades_df['qty'].mean()
    features['trade_size_std'] = trades_df['qty'].std()
    features['trade_size_skew'] = trades_df['qty'].skew()

    # Price impact (how much price moves per unit volume)
    price_change = trades_df['price'].iloc[-1] - trades_df['price'].iloc[0]
    total_volume = trades_df['qty'].sum()
    features['price_impact'] = price_change / total_volume

    # Roll measure (serial correlation - measures spread)
    returns = trades_df['price'].pct_change()
    features['roll_measure'] = -returns.autocorr(lag=1)

    # Trade frequency
    features['trade_frequency'] = len(trades_df)

    return features
```

**Why this matters:**
- Buyer-initiated vs seller-initiated trades show true demand
- Large trades often predict continuation
- Price impact reveals liquidity and momentum

---

#### 3. Alternative Data Features

**Funding rates (for perpetual futures):**

```python
def extract_funding_features():
    """
    Funding rate as sentiment indicator
    """
    # Get funding rate from Binance Futures
    funding_rate = binance_futures.get_funding_rate('BTCUSDT')

    features = {
        'funding_rate': funding_rate,
        'funding_rate_ma_8h': calculate_ma(funding_rate, periods=3),  # 3 * 8h = 24h
        'funding_rate_change': funding_rate - previous_funding_rate,

        # High positive funding = overleveraged longs = potential drop
        'funding_regime': 'high' if funding_rate > 0.01 else 'low' if funding_rate < -0.01 else 'neutral'
    }

    return features
```

**Open interest and liquidations:**

```python
def extract_derivatives_features():
    """
    Open interest and liquidation data
    """
    oi = binance_futures.get_open_interest('BTCUSDT')
    liquidations = get_liquidation_data()  # From external API

    features = {
        'open_interest': oi,
        'oi_change': oi - previous_oi,
        'oi_change_pct': (oi - previous_oi) / previous_oi,

        # Liquidation cascade risk
        'liquidations_long': liquidations['long_volume'],
        'liquidations_short': liquidations['short_volume'],
        'liquidation_ratio': liquidations['long_volume'] / (liquidations['short_volume'] + 1e-8)
    }

    return features
```

**Why this matters:**
- Funding rate shows market sentiment (greedy longs vs shorts)
- Open interest growth = new positions = potential reversal
- Liquidation cascades create predictable price moves

---

#### 4. Cross-Asset and Macro Features

**Correlation with other assets:**

```python
def extract_cross_asset_features():
    """
    Features from correlated assets
    """
    # Get prices from various sources
    eth_price = get_price('ETHUSDT')
    spx_futures = get_price('ES')  # S&P 500 futures
    dxy = get_price('DXY')  # Dollar index
    gold = get_price('GC')  # Gold futures
    vix = get_price('VIX')  # Volatility index

    features = {
        # BTC vs ETH (BTC dominance indicator)
        'btc_eth_ratio': btc_price / eth_price,
        'btc_eth_ratio_change': (btc_price / eth_price) - previous_ratio,

        # Risk-on/risk-off indicators
        'spx_return_1h': (spx_futures - spx_futures_1h_ago) / spx_futures_1h_ago,
        'vix_change': vix - vix_previous,

        # Dollar strength (inverse correlation with BTC)
        'dxy_return_1h': (dxy - dxy_1h_ago) / dxy_1h_ago,

        # Gold correlation (both are 'digital gold')
        'gold_return_1h': (gold - gold_1h_ago) / gold_1h_ago,

        # Macro regime
        'risk_regime': 'risk_on' if spx_return_1h > 0 and vix_change < 0 else 'risk_off'
    }

    return features
```

**Why this matters:**
- BTC doesn't trade in isolation
- Strong dollar typically = lower BTC
- S&P up + VIX down = risk-on = BTC up
- BTC/ETH ratio shows crypto-specific sentiment

---

#### 5. Time-Based and Calendar Features

**Session and calendar effects:**

```python
def extract_temporal_features(timestamp):
    """
    Time-based patterns
    """
    dt = pd.to_datetime(timestamp)

    features = {
        # Time of day (UTC) - different sessions have different volatility
        'hour': dt.hour,
        'is_asia_session': 1 if 0 <= dt.hour < 8 else 0,
        'is_europe_session': 1 if 8 <= dt.hour < 16 else 0,
        'is_us_session': 1 if 16 <= dt.hour < 24 else 0,

        # Day of week (Monday often different from Friday)
        'day_of_week': dt.dayofweek,
        'is_weekend': 1 if dt.dayofweek >= 5 else 0,

        # Month (tax season, holidays, etc.)
        'month': dt.month,
        'is_end_of_month': 1 if dt.day >= 28 else 0,

        # Volume profile (is current volume higher than usual for this hour?)
        'volume_vs_typical': current_volume / typical_volume_for_hour[dt.hour]
    }

    return features
```

---

### Feature Implementation Priority

| Priority | Feature Type | Implementation Effort | Expected Impact | Data Required |
|----------|--------------|----------------------|-----------------|---------------|
| **P0** | Order flow (L2) | High | Very High | WebSocket |
| **P0** | Trade flow | Medium | High | Trades API |
| **P1** | Funding rate | Low | Medium | Futures API |
| **P1** | Liquidations | Medium | Medium | External API |
| **P2** | Cross-asset | Medium | Medium | Multi-exchange |
| **P2** | Time-based | Low | Low | None |

**Start with P0 features first!**

---

## More Realistic Labels

### Current Problem
Labels are too rare (3-6% positive rate) and too aggressive (0.2%-1.0% targets).

### Solution 1: Multi-Class Labels (Not Just Binary)

**Instead of:**
```python
# Binary: Did price go up 0.2% in 10 min?
label = 1 if future_high > close * 1.002 else 0
```

**Try multi-class:**
```python
def generate_multiclass_labels(df, horizon=10):
    """
    Classify future price movement into multiple categories
    """
    future_return = (df['close'].shift(-horizon) - df['close']) / df['close']

    # 5 classes based on magnitude
    labels = pd.cut(future_return,
                    bins=[-np.inf, -0.002, -0.0005, 0.0005, 0.002, np.inf],
                    labels=['strong_down', 'weak_down', 'neutral', 'weak_up', 'strong_up'])

    return labels
```

**Advantages:**
- No severe class imbalance (each class has ~20% samples)
- Model learns magnitude, not just direction
- Can trade only "strong" signals, filter "weak" ones

---

### Solution 2: Regression Labels (Continuous Target)

**Predict exact return instead of binary outcome:**

```python
def generate_regression_labels(df, horizon=10):
    """
    Predict exact percentage return over next N candles
    """
    # Simple return
    labels = (df['close'].shift(-horizon) - df['close']) / df['close']

    # Or log return (better for ML)
    labels = np.log(df['close'].shift(-horizon) / df['close'])

    # Or risk-adjusted return (Sharpe-like)
    returns = (df['close'].shift(-horizon) - df['close']) / df['close']
    volatility = df['close'].pct_change().rolling(20).std()
    labels = returns / volatility

    return labels
```

**Advantages:**
- Every sample has a label (no imbalance)
- Model learns both direction AND magnitude
- Can set dynamic thresholds: "only trade if predicted return > 0.3%"

**Training with regression:**
```python
# Use LGBM regressor instead of classifier
from lightgbm import LGBMRegressor

model = LGBMRegressor(
    objective='regression',
    metric='rmse',  # Or 'mae', 'huber'
    num_leaves=31,
    learning_rate=0.05,
    n_estimators=300
)
```

---

### Solution 3: Adaptive Labels Based on Volatility

**Problem:** 0.2% target makes sense in high volatility, not in low volatility.

**Solution:** Scale targets by current ATR:

```python
def generate_adaptive_labels(df, base_target=0.002, horizon=10):
    """
    Adjust target based on current volatility regime
    """
    # Calculate ATR as % of price
    atr_pct = df['atr'] / df['close']

    # Adaptive target: base_target * (current_atr / median_atr)
    median_atr = atr_pct.rolling(1000).median()
    adaptive_target = base_target * (atr_pct / median_atr)

    # Generate labels
    future_high = df['high'].rolling(horizon).max().shift(-horizon)
    labels = (future_high > df['close'] * (1 + adaptive_target)).astype(int)

    return labels, adaptive_target
```

**Result:** More balanced labels (10-15% positive rate instead of 3-6%).

---

### Solution 4: Directional + Magnitude Labels

**Combine classification and regression:**

```python
def generate_hybrid_labels(df, horizon=10):
    """
    Two separate targets:
    1. Direction: Will price go up or down?
    2. Magnitude: How much? (only if direction is correct)
    """
    future_return = (df['close'].shift(-horizon) - df['close']) / df['close']

    # Direction (balanced by design)
    direction = (future_return > 0).astype(int)

    # Magnitude (absolute value)
    magnitude = abs(future_return)

    return direction, magnitude
```

**Training:**
1. Train classifier for direction (gets 55-60% accuracy)
2. Train regressor for magnitude (predicts |return|)
3. **Trading rule:** Only trade if (predicted_direction == 1) AND (predicted_magnitude > 0.003)

---

### Solution 5: Multiple Horizons (Ensemble of Timeframes)

**Instead of single horizon (10 min), predict multiple:**

```python
def generate_multi_horizon_labels(df):
    """
    Predict returns at multiple future points
    """
    horizons = [5, 10, 20, 40]  # 5min, 10min, 20min, 40min

    labels = {}
    for h in horizons:
        labels[f'return_{h}min'] = (df['close'].shift(-h) - df['close']) / df['close']

    return labels
```

**Why this helps:**
- If all horizons agree (positive return at 5min, 10min, 20min, 40min) → strong signal
- If only short-term is positive → scalp opportunity
- If only long-term is positive → wait for better entry

---

### Recommended Label Strategy

**For next iteration, try this hybrid approach:**

```python
def generate_improved_labels(df):
    """
    Combination of regression + adaptive thresholds
    """
    # 1. Regression target (always available)
    labels = {}
    labels['return_10m'] = (df['close'].shift(-10) - df['close']) / df['close']
    labels['return_20m'] = (df['close'].shift(-20) - df['close']) / df['close']

    # 2. Adaptive binary labels
    atr_pct = df['atr'] / df['close']
    median_atr = atr_pct.rolling(1000).median()
    adaptive_threshold = 0.001 * (atr_pct / median_atr)  # Base 0.1%, scaled by vol

    labels['up_adaptive'] = (labels['return_10m'] > adaptive_threshold).astype(int)
    labels['down_adaptive'] = (labels['return_10m'] < -adaptive_threshold).astype(int)

    # 3. Multi-class for magnitude
    labels['magnitude_class'] = pd.cut(abs(labels['return_10m']),
                                        bins=[0, 0.001, 0.002, 0.005, np.inf],
                                        labels=['tiny', 'small', 'medium', 'large'])

    return labels
```

**Train 3 models:**
1. Regressor for `return_10m` (primary predictor)
2. Classifier for `up_adaptive` (direction confirmation)
3. Classifier for `magnitude_class` (opportunity sizing)

**Trading rule:**
- Only trade if: `predicted_return > 0.003` AND `predicted_direction == up` AND `predicted_magnitude >= 'medium'`

---

## Alternative ML Algorithms

### Current Status
- ✅ Logistic Classifier (LC): Simple baseline, 50% win rate
- ✅ LightGBM (LGBM): Gradient boosting, 50% win rate
- ❌ Both failed because features are bad (garbage in → garbage out)

### Next Algorithms to Try

#### 1. XGBoost (Similar to LGBM, Worth Quick Test)

**Pros:**
- Often slightly better than LGBM on some datasets
- Better handling of missing values
- More regularization options

**Cons:**
- Slower than LGBM
- More hyperparameters to tune
- Won't fix bad features

**Implementation:**
```python
# Add to common/classifiers.py
import xgboost as xgb

def train_xgboost(df_X, df_y, model_config: dict):
    """Train XGBoost model"""
    train_conf = model_config.get("train", {})

    xgb_params = {
        'objective': 'binary:logistic',
        'eval_metric': 'logloss',
        'max_depth': train_conf.get('max_depth', 6),
        'learning_rate': train_conf.get('learning_rate', 0.05),
        'n_estimators': train_conf.get('n_estimators', 300),
        'subsample': train_conf.get('subsample', 0.8),
        'colsample_bytree': train_conf.get('colsample_bytree', 0.8),
        'reg_alpha': train_conf.get('reg_alpha', 0.1),
        'reg_lambda': train_conf.get('reg_lambda', 1.0)
    }

    model = xgb.XGBClassifier(**xgb_params)
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    return (model, scaler)
```

**Verdict:** Quick win if it performs better, but unlikely to dramatically change results.

---

#### 2. CatBoost (Better Handling of Categorical Features)

**Pros:**
- Best gradient boosting for categorical features
- Handles regime features ('low_vol', 'medium_vol', 'high_vol') natively
- Less prone to overfitting

**Cons:**
- Slower than LGBM/XGBoost
- Requires CatBoost installation

**Implementation:**
```python
from catboost import CatBoostClassifier

def train_catboost(df_X, df_y, model_config: dict):
    """Train CatBoost model"""
    train_conf = model_config.get("train", {})

    # Identify categorical features
    cat_features = [i for i, col in enumerate(df_X.columns) if 'regime' in col or 'session' in col]

    model = CatBoostClassifier(
        iterations=train_conf.get('n_estimators', 300),
        learning_rate=train_conf.get('learning_rate', 0.05),
        depth=train_conf.get('max_depth', 6),
        cat_features=cat_features,
        verbose=False
    )

    model.fit(X_train, y_train, eval_set=(X_test, y_test))

    return (model, scaler)
```

**When to use:** If we add many categorical features (time sessions, regime states, market conditions).

---

#### 3. Neural Networks - LSTM (For Time Series)

**Why LSTM matters:**
- Automatically learns temporal patterns (no need for SMA, LINEARREG_SLOPE)
- Can capture long-range dependencies
- State-of-the-art for time series

**Architecture:**
```python
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout

def build_lstm_model(lookback=60, n_features=5):
    """
    LSTM for price prediction

    Input: Last 60 candles × 5 features (OHLCV)
    Output: Binary prediction or continuous return
    """
    model = Sequential([
        # LSTM layers
        LSTM(128, return_sequences=True, input_shape=(lookback, n_features)),
        Dropout(0.2),
        LSTM(64, return_sequences=True),
        Dropout(0.2),
        LSTM(32),
        Dropout(0.2),

        # Dense layers
        Dense(16, activation='relu'),
        Dense(1, activation='sigmoid')  # For classification
        # OR Dense(1, activation='linear') for regression
    ])

    model.compile(
        optimizer='adam',
        loss='binary_crossentropy',  # Or 'mse' for regression
        metrics=['accuracy']
    )

    return model

# Data preparation
def prepare_lstm_data(df, lookback=60, horizon=10):
    """
    Convert dataframe to LSTM format: (samples, timesteps, features)
    """
    X, y = [], []

    for i in range(lookback, len(df) - horizon):
        # X: Last 60 candles
        X.append(df[['open', 'high', 'low', 'close', 'volume']].iloc[i-lookback:i].values)

        # y: Future return
        future_close = df['close'].iloc[i + horizon]
        current_close = df['close'].iloc[i]
        y.append((future_close > current_close * 1.002).astype(int))

    return np.array(X), np.array(y)

# Training
X_train, y_train = prepare_lstm_data(train_df)
X_test, y_test = prepare_lstm_data(test_df)

model = build_lstm_model()
model.fit(X_train, y_train, epochs=50, batch_size=64, validation_data=(X_test, y_test))
```

**Pros:**
- No manual feature engineering (learns from raw OHLCV)
- Can capture complex temporal patterns
- Works well with high-frequency data

**Cons:**
- Slower to train (10-30 minutes vs 2-3 minutes for LGBM)
- Requires more data (1M+ samples)
- More prone to overfitting
- Harder to interpret

---

#### 4. Transformers with Attention (State-of-the-Art)

**Why Transformers:**
- Attention mechanism learns which timesteps are important
- Outperform LSTM on many time series tasks
- Can handle very long sequences

**Implementation (using Temporal Fusion Transformer):**
```python
# pip install pytorch-forecasting
from pytorch_forecasting import TemporalFusionTransformer, TimeSeriesDataSet
from pytorch_forecasting.data import GroupNormalizer

def train_transformer(df):
    """
    Temporal Fusion Transformer for price prediction
    """
    # Prepare data
    max_encoder_length = 60  # Lookback
    max_prediction_length = 10  # Horizon

    training = TimeSeriesDataSet(
        df,
        time_idx="time_idx",
        target="return_10m",
        group_ids=["symbol"],
        min_encoder_length=30,
        max_encoder_length=max_encoder_length,
        min_prediction_length=1,
        max_prediction_length=max_prediction_length,
        static_categoricals=[],
        time_varying_known_reals=["hour", "day_of_week"],
        time_varying_unknown_reals=["close", "volume", "atr"],
        target_normalizer=GroupNormalizer(groups=["symbol"])
    )

    # Create model
    tft = TemporalFusionTransformer.from_dataset(
        training,
        learning_rate=0.03,
        hidden_size=32,
        attention_head_size=1,
        dropout=0.1,
        hidden_continuous_size=16,
        output_size=7,  # Quantiles for uncertainty estimation
        loss=QuantileLoss()
    )

    # Train
    trainer = pl.Trainer(max_epochs=30, gpus=1)
    trainer.fit(tft, train_dataloader=train_dataloader, val_dataloaders=val_dataloader)

    return tft
```

**Pros:**
- Best performance on time series benchmarks
- Provides uncertainty estimates (confidence intervals)
- Attention weights show which features matter

**Cons:**
- Most complex to implement
- Requires GPU for reasonable speed
- Needs even more data than LSTM

---

#### 5. Reinforcement Learning (Learn Trading Policy Directly)

**Why RL is different:**
- Instead of predicting price, learn optimal actions (buy/sell/hold)
- Maximizes cumulative reward (profit), not prediction accuracy
- Handles sequential decision-making naturally

**Example using Stable-Baselines3:**
```python
# pip install stable-baselines3
import gym
from stable_baselines3 import PPO

class TradingEnv(gym.Env):
    """
    Custom OpenAI Gym environment for trading
    """
    def __init__(self, df):
        super(TradingEnv, self).__init__()

        self.df = df
        self.current_step = 0

        # Actions: 0=hold, 1=buy, 2=sell
        self.action_space = gym.spaces.Discrete(3)

        # Observations: OHLCV + features
        self.observation_space = gym.spaces.Box(
            low=-np.inf, high=np.inf, shape=(20,), dtype=np.float32
        )

    def reset(self):
        self.current_step = 0
        self.position = 0  # 0=flat, 1=long, -1=short
        self.entry_price = 0
        self.balance = 10000
        return self._get_observation()

    def step(self, action):
        # Execute action (buy/sell/hold)
        reward = self._execute_action(action)
        self.current_step += 1
        done = self.current_step >= len(self.df) - 1
        return self._get_observation(), reward, done, {}

    def _execute_action(self, action):
        current_price = self.df['close'].iloc[self.current_step]
        reward = 0

        if action == 1 and self.position == 0:  # Buy
            self.position = 1
            self.entry_price = current_price
        elif action == 2 and self.position == 1:  # Sell
            reward = (current_price - self.entry_price) / self.entry_price - 0.0008  # Minus fees
            self.position = 0

        return reward

# Train RL agent
env = TradingEnv(train_df)
model = PPO("MlpPolicy", env, verbose=1, learning_rate=0.0003, n_steps=2048)
model.learn(total_timesteps=100000)

# Test
test_env = TradingEnv(test_df)
obs = test_env.reset()
for i in range(len(test_df)):
    action, _states = model.predict(obs, deterministic=True)
    obs, reward, done, info = test_env.step(action)
    if done:
        break
```

**Pros:**
- Optimizes for trading performance directly (not prediction accuracy)
- Learns when NOT to trade (implicit risk management)
- Can handle transaction costs, slippage naturally

**Cons:**
- Very hard to train (reward shaping is tricky)
- Requires extensive hyperparameter tuning
- Can overfit to training period

---

### Algorithm Recommendation Matrix

| Algorithm | Complexity | Training Time | Data Needed | When to Use |
|-----------|------------|---------------|-------------|-------------|
| **LGBM** | Low | Fast (2-5 min) | 10k+ samples | Baseline, tabular features |
| **XGBoost** | Low | Medium (5-10 min) | 10k+ samples | If LGBM fails, try this |
| **CatBoost** | Low | Medium (5-10 min) | 10k+ samples | Many categorical features |
| **LSTM** | High | Slow (10-30 min) | 100k+ samples | Time series, raw OHLCV |
| **Transformer** | Very High | Very Slow (30-60 min) | 500k+ samples | Best performance, GPU available |
| **RL (PPO)** | Very High | Slow (20-40 min) | 50k+ samples | Direct policy optimization |

**Recommended progression:**
1. ✅ LGBM (done, failed)
2. Try LSTM with better features (order flow + raw OHLCV)
3. If LSTM works, try Transformer for improvement
4. If Transformer works, try RL for direct optimization

---

## Cloud ML Services

### Azure Machine Learning

**What it offers:**
1. **Automated ML (AutoML):**
   - Tries hundreds of feature engineering + algorithm combinations
   - Automatic hyperparameter tuning
   - Ensemble of best models

2. **Designer (No-code ML):**
   - Drag-and-drop pipeline builder
   - Pre-built components for time series
   - Easy experimentation

3. **Compute:**
   - Scalable GPU/CPU clusters
   - Pay only for usage
   - Faster training (30min LSTM → 5min on GPU cluster)

**Cost estimate:**
- **Compute:** ~$0.50/hour for basic (NC6 with 1x K80 GPU)
- **Compute:** ~$3.60/hour for powerful (NC6s_v3 with 1x V100 GPU)
- **Storage:** ~$0.02/GB/month
- **AutoML:** Included in compute cost

**Example workflow:**
```python
from azureml.core import Workspace, Experiment
from azureml.train.automl import AutoMLConfig

# Connect to workspace
ws = Workspace.from_config()

# Configure AutoML for time series
automl_config = AutoMLConfig(
    task='forecasting',
    primary_metric='normalized_root_mean_squared_error',
    experiment_timeout_hours=2,
    training_data=train_df,
    label_column_name='return_10m',
    n_cross_validations=5,
    enable_early_stopping=True,
    forecasting_parameters={
        'time_column_name': 'timestamp',
        'max_horizon': 10
    }
)

# Run experiment
experiment = Experiment(ws, 'btc-trading')
run = experiment.submit(automl_config, show_output=True)

# Get best model
best_run, fitted_model = run.get_output()
```

**When to use Azure ML:**
- Want to try many algorithms quickly
- Need scalable compute for deep learning
- Want MLOps (model versioning, deployment, monitoring)

**When NOT to use:**
- Features are still bad (AutoML can't fix garbage data)
- Budget is tight (<$100/month for experiments)
- Local compute is sufficient (LGBM trains in 2 minutes)

---

### Google Cloud AI Platform (Vertex AI)

**What it offers:**
1. **Vertex AI AutoML:**
   - Similar to Azure AutoML
   - Good for tabular and time series data
   - Automatic feature engineering

2. **Vertex AI Workbench:**
   - Managed Jupyter notebooks with GPUs
   - Easy collaboration
   - Pre-installed ML libraries

3. **BigQuery ML:**
   - Train ML models directly in SQL
   - Good for large datasets (billions of rows)
   - Integrated with data warehouse

**Cost estimate:**
- **Compute:** ~$0.45/hour for basic (n1-standard-4)
- **Compute:** ~$2.48/hour for GPU (n1-standard-4 + 1x Tesla T4)
- **Storage:** ~$0.02/GB/month
- **BigQuery ML:** Charged by data processed (~$5/TB)

**Example with BigQuery ML:**
```sql
-- Train LGBM directly in SQL
CREATE OR REPLACE MODEL `trading.btc_lgbm`
OPTIONS(
  model_type='BOOSTED_TREE_CLASSIFIER',
  input_label_cols=['label_high_020_10'],
  max_iterations=300,
  learning_rate=0.05,
  num_parallel_tree=1,
  max_tree_depth=6
) AS
SELECT
  close_SMA_3,
  close_RSI_14,
  high_low_close_ATR_14,
  -- ... other features
  label_high_020_10
FROM `trading.btc_features`
WHERE timestamp < '2024-11-01';

-- Make predictions
SELECT
  timestamp,
  predicted_label_high_020_10,
  predicted_label_high_020_10_probs
FROM ML.PREDICT(MODEL `trading.btc_lgbm`,
  (SELECT * FROM `trading.btc_features` WHERE timestamp >= '2024-11-01')
);
```

**When to use GCP:**
- Data is already in BigQuery
- Want SQL-based ML (easy for data analysts)
- Need to process massive datasets (>100GB)

---

### Comparison: Azure ML vs GCP Vertex AI

| Feature | Azure ML | GCP Vertex AI | Winner |
|---------|----------|---------------|--------|
| AutoML Quality | Good | Good | Tie |
| Ease of Use | Excellent | Good | Azure |
| BigQuery Integration | No | Yes | GCP |
| Pricing | Slightly higher | Slightly lower | GCP |
| Documentation | Excellent | Good | Azure |
| Time Series Support | Better | Good | Azure |

---

### Realistic Assessment: Should We Use Cloud ML?

**✅ Use cloud ML if:**
1. We fix features first and still need more compute
2. We want to try deep learning (LSTM, Transformer) and don't have local GPU
3. We want to run hundreds of experiments in parallel (hyperparameter search)
4. We want MLOps (model versioning, A/B testing, deployment)

**❌ Don't use cloud ML if:**
1. Features are still bad (AutoML can't create signal from noise)
2. LGBM trains in 2 minutes locally (no need for cloud)
3. Budget is constrained (<$100/month)
4. We're still in research phase (local Jupyter is faster for iteration)

**My recommendation:**
1. **Phase 1 (Now):** Fix features locally first
   - Add order flow, microstructure, alternative data
   - Try LSTM locally (TensorFlow/PyTorch)
   - If local GPU not available, use Google Colab (free GPU for 12h/day)

2. **Phase 2 (After features are fixed):** Consider cloud if needed
   - If LSTM works but needs more compute → Azure ML with GPU
   - If we want to try hundreds of feature combinations → AutoML
   - If we need to deploy model → Use cloud for serving

---

## Implementation Plan

### Phase 1: Better Features (Week 1-2)

**Goal:** Add predictive features to replace lagging indicators

**Tasks:**
1. **Order book streaming (Priority P0):**
   ```bash
   # Implement WebSocket order book collection
   python -m scripts.collect_orderbook --symbol BTCUSDT --duration 24h

   # Extract order flow features
   python -m scripts.extract_orderflow_features
   ```

2. **Trade flow features (Priority P0):**
   ```bash
   # Collect tick trades
   python -m scripts.collect_trades --symbol BTCUSDT

   # Extract microstructure features
   python -m scripts.extract_microstructure_features
   ```

3. **Alternative data (Priority P1):**
   ```bash
   # Collect funding rates, open interest
   python -m scripts.collect_derivatives_data

   # Extract derivative features
   python -m scripts.extract_derivatives_features
   ```

4. **Test new features:**
   ```bash
   # Create config with new features
   # configs/btcusdt_1m_orderflow.jsonc

   # Train and evaluate
   python -m scripts.train -c configs/btcusdt_1m_orderflow.jsonc
   python -m scripts.simulate -c configs/btcusdt_1m_orderflow.jsonc
   ```

**Success criteria:** Win rate > 53% in backtest

---

### Phase 2: Better Labels (Week 2-3)

**Goal:** Fix class imbalance with regression or adaptive labels

**Tasks:**
1. **Implement regression labels:**
   ```python
   # Modify common/gen_labels_aggressive.py
   def generate_regression_labels(df, gen_config, config, model_store):
       horizon = gen_config.get('horizon', 10)
       labels = (df['close'].shift(-horizon) - df['close']) / df['close']
       return df.assign(return_10m=labels), ['return_10m']
   ```

2. **Update config for regression:**
   ```jsonc
   // configs/btcusdt_1m_regression.jsonc
   {
     "labels": ["return_10m", "return_20m"],
     "algorithms": [{
       "name": "lgbm_reg",
       "algo": "lgbm_regressor",  // New algorithm type
       "train": {
         "objective": "regression",
         "metric": "rmse"
       }
     }]
   }
   ```

3. **Train and evaluate:**
   ```bash
   python -m scripts.train -c configs/btcusdt_1m_regression.jsonc
   python -m scripts.signals_regression -c configs/btcusdt_1m_regression.jsonc
   ```

**Success criteria:** Can predict return magnitude with RMSE < 0.003 (0.3%)

---

### Phase 3: Alternative Algorithms (Week 3-4)

**Goal:** Try LSTM if better features show promise

**Tasks:**
1. **Implement LSTM in classifiers.py:**
   ```python
   # common/classifiers.py
   def train_lstm(df_X, df_y, model_config: dict):
       # Build LSTM model
       # Train on last 60 candles → predict next 10
       # Return trained model
   ```

2. **Create LSTM config:**
   ```jsonc
   // configs/btcusdt_1m_lstm.jsonc
   {
     "algorithms": [{
       "name": "lstm",
       "algo": "lstm",
       "train": {
         "lookback": 60,
         "lstm_units": [128, 64, 32],
         "dropout": 0.2,
         "epochs": 50
       }
     }]
   }
   ```

3. **Train and compare:**
   ```bash
   # Train LSTM (will take 10-30 min)
   python -m scripts.train_lstm -c configs/btcusdt_1m_lstm.jsonc

   # Compare with LGBM
   python -m scripts.compare_models \
     --models LGBM,LSTM \
     --configs configs/btcusdt_1m_orderflow.jsonc,configs/btcusdt_1m_lstm.jsonc
   ```

**Success criteria:** LSTM win rate > LGBM win rate + 2%

---

### Phase 4: Cloud ML (Week 4-5, Optional)

**Goal:** Use cloud only if local experiments show promise

**Tasks:**
1. **If Phase 1-3 achieved >53% win rate:**
   ```bash
   # Set up Azure ML workspace
   az ml workspace create --name itb-trading --resource-group rg-trading

   # Upload data
   az ml data create --name btc-orderflow --path DATA_ITB_1m/

   # Run AutoML experiment
   python -m scripts.azure_automl_train
   ```

2. **Or use Google Colab for free GPU:**
   ```python
   # In Colab notebook
   !git clone https://github.com/user/intelligent-trading-bot
   !pip install lightgbm tensorflow

   # Train LSTM on GPU
   from tensorflow.keras import mixed_precision
   policy = mixed_precision.Policy('mixed_float16')
   mixed_precision.set_global_policy(policy)

   # ... train LSTM (10x faster on GPU)
   ```

**Success criteria:** Cloud training provides >2% win rate improvement OR >10x speedup

---

### Phase 5: Reality Check (Week 5)

**Goal:** Decide if strategy is viable

**Decision criteria:**

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Win Rate (backtest) | >53% | 50.4% | ❌ |
| Win Rate (shadow mode) | >52% | 31.2% | ❌ |
| Sharpe Ratio | >0.5 | -0.5 | ❌ |
| Max Drawdown | <-15% | -10% | ⚠️ |
| Profitable | Yes | No (-7.5%) | ❌ |

**After Phase 1-4, re-evaluate:**

**If win rate >53% in backtest + >52% in shadow mode:**
→ Deploy to live trading (small position)

**If win rate 50-53%:**
→ Continue research (try more features, longer timeframes)

**If win rate still <50%:**
→ Pivot strategy:
  - Try swing trading (daily timeframe)
  - Try different instruments (altcoins, futures)
  - Accept that retail spot scalping may not be viable

---

## Success Metrics

### Minimum Viable Strategy (MVS) Requirements:

| Metric | Minimum | Target | Stretch |
|--------|---------|--------|---------|
| **Backtest Win Rate** | 52% | 55% | 58% |
| **Shadow Mode Win Rate** | 51% | 53% | 56% |
| **Sharpe Ratio** | 0.3 | 0.7 | 1.2 |
| **Max Drawdown** | -20% | -12% | -8% |
| **Avg Profit/Trade** | $0.50 | $2.00 | $5.00 |
| **Trades/Day** | 10 | 20 | 40 |

### Feature Quality Metrics:

| Metric | Minimum | Target |
|--------|---------|--------|
| **Feature Importance** (top feature) | >5% | >10% |
| **Correlation with label** | >0.05 | >0.10 |
| **Mutual Information** | >0.01 | >0.05 |
| **Prediction Confidence** | >60% | >70% |

---

## Resources and References

### Papers:
1. "Machine Learning for Trading" (Gordon Ritter, 2017)
2. "Deep Learning for Finance" (Stefan Zohren, Oxford, 2020)
3. "Financial Machine Learning" (Marcos Lopez de Prado, 2018)

### GitHub Repositories:
- https://github.com/stefan-jansen/machine-learning-for-trading
- https://github.com/tradytics/eiten (RL for portfolio management)
- https://github.com/borisbanushev/stockpredictionai (LSTM for stocks)

### Courses:
- Coursera: "Machine Learning for Trading" (Georgia Tech)
- Udacity: "AI for Trading" nanodegree
- QuantInsti: "Algorithmic Trading with Machine Learning"

---

## Next Actions (Immediate)

1. **Day 1-2: Data Collection**
   - Set up WebSocket for order book streaming
   - Collect 24-48 hours of L2 data
   - Verify data quality

2. **Day 3-4: Feature Engineering**
   - Implement order flow features
   - Implement microstructure features
   - Add to feature pipeline

3. **Day 5-6: Training**
   - Train LGBM with new features
   - Evaluate win rate improvement
   - If >53% → proceed to shadow mode
   - If <53% → add more features

4. **Day 7: Decision Point**
   - If new features work → continue to Phase 2 (labels)
   - If new features fail → pivot to longer timeframe or different strategy

---

**Document created:** December 9, 2024
**Status:** Research phase - implementation pending
**Next milestone:** Order flow features + 53% win rate
