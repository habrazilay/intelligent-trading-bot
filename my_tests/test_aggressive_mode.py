#!/usr/bin/env python3
"""
Quick Test Script for Aggressive Mode Implementation

Tests:
1. Label generator imports and runs
2. Risk manager imports and runs
3. Config file is valid JSON
4. All components integrate correctly

Usage:
    python my_tests/test_aggressive_mode.py
"""

import sys
import json
from pathlib import Path
import numpy as np
import pandas as pd


def test_label_generator():
    """Test aggressive label generator."""
    print("\n" + "=" * 80)
    print("TEST 1: Aggressive Label Generator")
    print("=" * 80)

    try:
        from common.gen_labels_aggressive import generate_labels_aggressive, add_regime_features, add_spread_features

        # Generate test data
        np.random.seed(42)
        n = 500

        df = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-01', periods=n, freq='1min'),
            'close': 50000 + np.cumsum(np.random.randn(n) * 10),
        })
        df['high'] = df['close'] * (1 + np.abs(np.random.randn(n)) * 0.001)
        df['low'] = df['close'] * (1 - np.abs(np.random.randn(n)) * 0.001)
        df['high_low_close_ATR_14'] = df['close'] * 0.005  # Mock ATR

        # Test label generation
        config = {
            "columns": ["close", "high", "low"],
            "function": "high",
            "thresholds": [0.20],
            "tolerance": 0.05,
            "horizon": 10,
            "names": ["high_020_10"]
        }

        df, labels = generate_labels_aggressive(df, config)

        assert 'high_020_10' in df.columns, "Label column not created"
        assert len(labels) == 1, "Wrong number of labels"

        # Test regime features
        df = add_regime_features(df, 'high_low_close_ATR_14')
        assert 'vol_regime' in df.columns, "Regime feature not created"

        # Test spread features
        df = add_spread_features(df, windows=[3, 5])
        assert 'spread_pct_3' in df.columns, "Spread feature not created"

        print("✅ Label Generator: PASSED")
        return True

    except Exception as e:
        print(f"❌ Label Generator: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return False


def test_risk_manager():
    """Test risk manager."""
    print("\n" + "=" * 80)
    print("TEST 2: Risk Manager")
    print("=" * 80)

    try:
        from common.risk_manager import RiskManager, TradeConfig, TradeState
        from datetime import datetime

        # Create config
        config = TradeConfig(
            risk_per_trade_pct=1.0,
            base_take_profit_pct=0.25,
            base_stop_loss_pct=0.20
        )

        rm = RiskManager(config)

        # Test TP/SL calculation
        entry_price = 50000.0
        tp, sl = rm.calculate_tp_sl(entry_price, 'BUY', vol_regime=1)

        assert tp > entry_price, "TP should be above entry for BUY"
        assert sl < entry_price, "SL should be below entry for BUY"

        # Test position sizing
        position = rm.calculate_position_size(equity=1000.0)
        assert 0 < position <= 100, "Position size out of range"

        # Test trade exit logic
        trade = TradeState(
            entry_time=datetime.now(),
            entry_price=50000.0,
            position_size_usdt=50.0,
            side='BUY',
            regime=1,
            stop_loss_price=49900.0,
            take_profit_price=50125.0
        )

        # Test TP hit
        should_exit, reason = rm.should_exit_trade(trade, 50125.0, datetime.now())
        assert should_exit, "Should exit on TP hit"

        print("✅ Risk Manager: PASSED")
        return True

    except Exception as e:
        print(f"❌ Risk Manager: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_file():
    """Test aggressive config file."""
    print("\n" + "=" * 80)
    print("TEST 3: Config File Validation")
    print("=" * 80)

    try:
        config_path = Path("configs/btcusdt_1m_aggressive.jsonc")

        if not config_path.exists():
            print(f"❌ Config file not found: {config_path}")
            return False

        # Read JSONC (remove comments)
        content = config_path.read_text()
        lines = []
        for line in content.split('\n'):
            # Remove // comments
            if '//' in line:
                line = line[:line.index('//')]
            lines.append(line)

        clean_json = '\n'.join(lines)
        config = json.loads(clean_json)

        # Validate key fields
        assert config['symbol'] == 'BTCUSDT', "Wrong symbol"
        assert config['freq'] == '1m', "Wrong frequency"
        assert 'high_020_10' in config['labels'], "Missing aggressive label"

        signal_sets = config.get('signal_sets', [])
        threshold_config = None
        for s in signal_sets:
            if s.get('generator') == 'threshold_rule':
                threshold_config = s.get('config', {}).get('parameters', {})
                break

        if threshold_config:
            buy_threshold = threshold_config.get('buy_signal_threshold')
            assert buy_threshold == 0.01, f"Wrong buy threshold: {buy_threshold}"

        print("✅ Config File: PASSED")
        print(f"   Symbol: {config['symbol']}")
        print(f"   Frequency: {config['freq']}")
        print(f"   Labels: {config['labels']}")
        print(f"   Buy Threshold: {buy_threshold}")

        return True

    except Exception as e:
        print(f"❌ Config File: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """Test that all components work together."""
    print("\n" + "=" * 80)
    print("TEST 4: Integration Test")
    print("=" * 80)

    try:
        from common.gen_labels_aggressive import generate_labels_aggressive
        from common.risk_manager import RiskManager, TradeConfig
        from datetime import datetime

        # Generate sample data with aggressive labels
        np.random.seed(42)
        n = 200

        df = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-01', periods=n, freq='1min'),
            'close': 50000 + np.cumsum(np.random.randn(n) * 10),
        })
        df['high'] = df['close'] * (1 + np.abs(np.random.randn(n)) * 0.001)
        df['low'] = df['close'] * (1 - np.abs(np.random.randn(n)) * 0.001)

        # Generate labels
        config = {
            "columns": ["close", "high", "low"],
            "function": "high",
            "thresholds": [0.20],
            "tolerance": 0.05,
            "horizon": 10,
            "names": ["high_020_10"]
        }

        df, labels = generate_labels_aggressive(df, config)

        # Simulate risk manager usage
        rm = RiskManager(TradeConfig())

        # Simulate a trade
        entry_price = df['close'].iloc[-1]
        tp, sl = rm.calculate_tp_sl(entry_price, 'BUY', vol_regime=1)
        position = rm.calculate_position_size(equity=1000.0)

        print(f"✅ Integration: PASSED")
        print(f"   Labels generated: {labels}")
        print(f"   Entry: ${entry_price:.2f}")
        print(f"   TP: ${tp:.2f} (+{((tp/entry_price-1)*100):.3f}%)")
        print(f"   SL: ${sl:.2f} ({((sl/entry_price-1)*100):.3f}%)")
        print(f"   Position: ${position:.2f}")

        return True

    except Exception as e:
        print(f"❌ Integration: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 80)
    print("🧪 AGGRESSIVE MODE - TEST SUITE")
    print("=" * 80)

    results = {
        'Label Generator': test_label_generator(),
        'Risk Manager': test_risk_manager(),
        'Config File': test_config_file(),
        'Integration': test_integration()
    }

    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)

    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:20} {status}")
        if not passed:
            all_passed = False

    print("=" * 80)

    if all_passed:
        print("\n🎉 ALL TESTS PASSED! Aggressive mode is ready to use.")
        print("\nNext steps:")
        print("  1. Review docs/AGGRESSIVE_MODE.md")
        print("  2. Run: python -m scripts.labels -c configs/btcusdt_1m_aggressive.jsonc")
        print("  3. Train model and backtest")
        print("  4. Deploy to shadow mode for 7 days")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED. Please fix issues before proceeding.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
