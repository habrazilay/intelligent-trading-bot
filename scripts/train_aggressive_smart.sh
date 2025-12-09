#!/bin/bash
#
# Smart Training Script - Reuses existing data when possible
#
# This script intelligently runs only the necessary steps:
# - Skips download if klines already exist
# - Skips merge if data.csv exists and is up-to-date
# - Skips features if features.csv exists with same feature set
# - Always generates new: matrix (labels), predictions, signals, models
#
# Usage:
#   bash scripts/train_aggressive_smart.sh
#

set -e  # Exit on error

CONFIG="configs/btcusdt_1m_aggressive.jsonc"
DATA_DIR="DATA_ITB_1m"
MODEL_DIR="MODELS_AGGRESSIVE_V1"

echo "========================================================================"
echo "🧠 SMART AGGRESSIVE MODE TRAINING"
echo "========================================================================"
echo ""
echo "Config: $CONFIG"
echo "Data Directory: $DATA_DIR"
echo "Model Directory: $MODEL_DIR"
echo ""

# Function to check if file exists and is not empty
check_file() {
    local file=$1
    if [ -f "$file" ] && [ -s "$file" ]; then
        return 0  # File exists and is not empty
    else
        return 1  # File missing or empty
    fi
}

# Function to count lines in file
count_lines() {
    local file=$1
    if check_file "$file"; then
        wc -l < "$file"
    else
        echo "0"
    fi
}

# ============================================================================
# STEP 1: Download (only if no data exists)
# ============================================================================

echo "──────────────────────────────────────────────────────────────────────"
echo "📥 STEP 1: Download Historical Data"
echo "──────────────────────────────────────────────────────────────────────"

if [ -d "$DATA_DIR/BTCUSDT" ]; then
    KLINES_COUNT=$(find "$DATA_DIR/BTCUSDT" -name "klines*.csv" -o -name "klines*.parquet" 2>/dev/null | wc -l)
    if [ "$KLINES_COUNT" -gt 0 ]; then
        echo "✅ SKIP: Found $KLINES_COUNT klines files in $DATA_DIR/BTCUSDT"
        echo "   To re-download, delete: $DATA_DIR/BTCUSDT"
    else
        echo "⚠️  $DATA_DIR/BTCUSDT exists but no klines found - downloading..."
        python -m scripts.download_binance -c "$CONFIG"
    fi
else
    echo "📥 Downloading klines from Binance (this may take 10-30 minutes)..."
    python -m scripts.download_binance -c "$CONFIG"
fi

echo ""

# ============================================================================
# STEP 2: Merge (only if data.csv missing or outdated)
# ============================================================================

echo "──────────────────────────────────────────────────────────────────────"
echo "🔗 STEP 2: Merge Data"
echo "──────────────────────────────────────────────────────────────────────"

DATA_CSV="$DATA_DIR/data.csv"

if check_file "$DATA_CSV"; then
    LINES=$(count_lines "$DATA_CSV")
    echo "✅ SKIP: $DATA_CSV exists with $LINES lines"
    echo "   To regenerate, delete: $DATA_CSV"
else
    echo "🔗 Merging klines into single data.csv..."
    python -m scripts.merge -c "$CONFIG"
fi

echo ""

# ============================================================================
# STEP 3: Features (only if features.csv missing)
# ============================================================================

echo "──────────────────────────────────────────────────────────────────────"
echo "⚙️  STEP 3: Generate Features"
echo "──────────────────────────────────────────────────────────────────────"

FEATURES_CSV="$DATA_DIR/features.csv"

if check_file "$FEATURES_CSV"; then
    LINES=$(count_lines "$FEATURES_CSV")
    echo "⚠️  WARNING: $FEATURES_CSV exists with $LINES lines"
    echo "   Checking if it has aggressive mode features (vol_regime, spread_pct_3)..."

    # Check if aggressive features exist
    if head -1 "$FEATURES_CSV" | grep -q "vol_regime"; then
        echo "✅ SKIP: Aggressive features already present"
    else
        echo "❌ REGENERATING: Missing aggressive features (vol_regime, spread_pct_*)"
        echo "   Backing up old features.csv to features_old.csv..."
        cp "$FEATURES_CSV" "$DATA_DIR/features_old.csv"
        python -m scripts.features -c "$CONFIG"
    fi
else
    echo "⚙️  Generating features (SMA, RSI, ATR, regime, spread)..."
    python -m scripts.features -c "$CONFIG"
fi

echo ""

# ============================================================================
# STEP 4: Labels (ALWAYS NEW - different labels)
# ============================================================================

echo "──────────────────────────────────────────────────────────────────────"
echo "🎯 STEP 4: Generate Aggressive Labels"
echo "──────────────────────────────────────────────────────────────────────"

MATRIX_CSV="$DATA_DIR/matrix_aggressive.csv"

echo "🎯 Generating NEW labels: high_020_10, low_020_10 (0.2% in 10 min)..."
python -m scripts.labels -c "$CONFIG"

if check_file "$MATRIX_CSV"; then
    LINES=$(count_lines "$MATRIX_CSV")
    echo "✅ Created: $MATRIX_CSV with $LINES lines"
else
    echo "❌ ERROR: Failed to create $MATRIX_CSV"
    exit 1
fi

echo ""

# ============================================================================
# STEP 5: Train (ALWAYS NEW - new model)
# ============================================================================

echo "──────────────────────────────────────────────────────────────────────"
echo "🧠 STEP 5: Train LightGBM Model"
echo "──────────────────────────────────────────────────────────────────────"

echo "🧠 Training LGBM on aggressive labels (5-10 minutes)..."
python -m scripts.train -c "$CONFIG"

# Check if models were created
MODEL_HIGH="$MODEL_DIR/high_020_10_lgbm_aggressive.pickle"
MODEL_LOW="$MODEL_DIR/low_020_10_lgbm_aggressive.pickle"

if check_file "$MODEL_HIGH" && check_file "$MODEL_LOW"; then
    echo "✅ Models created successfully:"
    ls -lh "$MODEL_HIGH" "$MODEL_LOW"

    # Show training metrics
    if check_file "$MODEL_DIR/prediction-metrics.txt"; then
        echo ""
        echo "📊 Training Metrics:"
        cat "$MODEL_DIR/prediction-metrics.txt"
    fi
else
    echo "❌ ERROR: Failed to create models"
    exit 1
fi

echo ""

# ============================================================================
# STEP 6: Predict (ALWAYS NEW - uses new model)
# ============================================================================

echo "──────────────────────────────────────────────────────────────────────"
echo "🔮 STEP 6: Generate Predictions"
echo "──────────────────────────────────────────────────────────────────────"

echo "🔮 Applying LGBM models to generate predictions..."
python -m scripts.predict -c "$CONFIG"

PRED_CSV="$DATA_DIR/predictions_aggressive.csv"
if check_file "$PRED_CSV"; then
    echo "✅ Created: $PRED_CSV"
else
    echo "❌ ERROR: Failed to create predictions"
    exit 1
fi

echo ""

# ============================================================================
# STEP 7: Signals (ALWAYS NEW - uses new predictions)
# ============================================================================

echo "──────────────────────────────────────────────────────────────────────"
echo "📊 STEP 7: Generate Trading Signals"
echo "──────────────────────────────────────────────────────────────────────"

echo "📊 Converting predictions to buy/sell signals (threshold: 0.01)..."
python -m scripts.signals -c "$CONFIG"

SIGNAL_CSV="$DATA_DIR/signals_aggressive.csv"
if check_file "$SIGNAL_CSV"; then
    echo "✅ Created: $SIGNAL_CSV"

    # Count signals
    BUY_COUNT=$(grep -c "buy_signal_aggressive.*True" "$SIGNAL_CSV" || echo "0")
    SELL_COUNT=$(grep -c "sell_signal_aggressive.*True" "$SIGNAL_CSV" || echo "0")

    echo ""
    echo "📊 Signal Summary:"
    echo "   Buy signals:  $BUY_COUNT"
    echo "   Sell signals: $SELL_COUNT"

    if [ "$BUY_COUNT" -gt 0 ] && [ "$SELL_COUNT" -gt 0 ]; then
        IMBALANCE=$((BUY_COUNT - SELL_COUNT))
        IMBALANCE_ABS=${IMBALANCE#-}  # Absolute value
        IMBALANCE_PCT=$((IMBALANCE_ABS * 100 / BUY_COUNT))

        echo "   Imbalance:    $IMBALANCE ($IMBALANCE_PCT%)"

        if [ "$IMBALANCE_PCT" -gt 30 ]; then
            echo "   ⚠️  WARNING: High signal imbalance (>30%)"
        else
            echo "   ✅ Signal balance OK"
        fi
    fi
else
    echo "❌ ERROR: Failed to create signals"
    exit 1
fi

echo ""

# ============================================================================
# STEP 8: Backtest (ALWAYS RUN - shows performance)
# ============================================================================

echo "──────────────────────────────────────────────────────────────────────"
echo "🎮 STEP 8: Backtest Strategy"
echo "──────────────────────────────────────────────────────────────────────"

echo "🎮 Running backtest simulation..."
python -m scripts.simulate -c "$CONFIG"

echo ""

# ============================================================================
# SUMMARY
# ============================================================================

echo "========================================================================"
echo "✅ TRAINING COMPLETE!"
echo "========================================================================"
echo ""
echo "📁 Generated Files:"
echo "   Data:        $DATA_DIR/"
echo "   Models:      $MODEL_DIR/"
echo "   Predictions: $PRED_CSV"
echo "   Signals:     $SIGNAL_CSV"
echo ""
echo "📊 Next Steps:"
echo ""
echo "1. Review backtest results above"
echo "   ✅ Target: Win Rate > 52%, Sharpe > 0.5, Max DD < -15%"
echo ""
echo "2. If backtest PASSED → Deploy to shadow mode:"
echo "   python -m service.server -c $CONFIG"
echo ""
echo "3. If backtest FAILED → Optimize thresholds:"
echo "   python -m scripts.simulate -c $CONFIG --optimize"
echo ""
echo "4. Compare with conservative mode:"
echo "   python -m scripts.simulate -c configs/btcusdt_1m_dev_lgbm.jsonc"
echo ""
echo "========================================================================"
