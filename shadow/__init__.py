"""
Shadow Mode Trading System

Allows running multiple parallel shadow trading sessions that:
- Connect to real Binance API
- Receive real market data
- Generate real trading signals
- Simulate order execution (no real orders)
- Log everything for analysis
"""

from shadow.shadow_logger import ShadowLogger, setup_shadow_logging
from shadow.shadow_mode import ShadowTrader, ShadowOrder
from shadow.shadow_analyzer import ShadowAnalyzer

__all__ = [
    'ShadowLogger',
    'setup_shadow_logging',
    'ShadowTrader',
    'ShadowOrder',
    'ShadowAnalyzer',
]
