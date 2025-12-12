"""
Unified Trade Schema for Multi-Source Trading

This module provides a standardized schema for trades from multiple sources
(Binance, MT5/MetaApi, etc.) to enable consistent analysis and backtesting.

Key features:
- Idempotent storage (no duplicates via composite key)
- Source-agnostic analysis
- Version tracking for reproducibility
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Literal
from enum import Enum
import hashlib
import json
import subprocess
import pandas as pd
from pathlib import Path


class TradeSource(str, Enum):
    BINANCE_SPOT = "binance_spot"
    BINANCE_FUTURES = "binance_futures"
    BINANCE_TESTNET = "binance_testnet"
    MT5 = "mt5"
    SIMULATION = "simulation"


class TradeSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"
    BOTH = "both"  # For hedge mode


@dataclass
class UnifiedTrade:
    """
    Unified trade record schema.

    Composite key for idempotency: (source, account_id, trade_id)
    """
    # === Identity (composite key) ===
    source: TradeSource
    account_id: str
    trade_id: str

    # === Timing ===
    event_ts_utc: datetime

    # === Trade Details ===
    symbol: str
    side: TradeSide
    position_side: Optional[PositionSide] = None  # For futures
    qty: float = 0.0
    price: float = 0.0

    # === Costs ===
    fee: float = 0.0
    fee_asset: str = ""

    # === References ===
    order_id: Optional[str] = None
    position_id: Optional[str] = None

    # === Strategy Metadata ===
    strategy_id: Optional[str] = None
    signal_version: Optional[str] = None
    model_version: Optional[str] = None
    config_hash: Optional[str] = None
    git_sha: Optional[str] = None

    # === Risk Parameters ===
    leverage: Optional[int] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    # === P&L ===
    realized_pnl: Optional[float] = None
    unrealized_pnl: Optional[float] = None

    # === Extra ===
    raw_data: Optional[dict] = field(default_factory=dict)

    @property
    def composite_key(self) -> str:
        """Unique key for deduplication."""
        return f"{self.source.value}:{self.account_id}:{self.trade_id}"

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        d = asdict(self)
        d['source'] = self.source.value
        d['side'] = self.side.value
        if self.position_side:
            d['position_side'] = self.position_side.value
        d['event_ts_utc'] = self.event_ts_utc.isoformat()
        d['composite_key'] = self.composite_key
        return d


@dataclass
class PositionSnapshot:
    """
    Point-in-time position snapshot for tracking.
    """
    snapshot_ts_utc: datetime
    source: TradeSource
    account_id: str
    symbol: str
    position_side: PositionSide
    qty: float
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    leverage: int = 1
    margin_type: str = "cross"

    # Account context
    account_balance: Optional[float] = None
    account_equity: Optional[float] = None

    # Strategy context
    strategy_id: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d['source'] = self.source.value
        d['position_side'] = self.position_side.value
        d['snapshot_ts_utc'] = self.snapshot_ts_utc.isoformat()
        return d


# =============================================================================
# Converters from source-specific formats
# =============================================================================

def from_binance_futures_trade(trade: dict, account_id: str, testnet: bool = False) -> UnifiedTrade:
    """Convert Binance Futures trade to unified format."""
    return UnifiedTrade(
        source=TradeSource.BINANCE_TESTNET if testnet else TradeSource.BINANCE_FUTURES,
        account_id=account_id,
        trade_id=str(trade.get('id', trade.get('tradeId', ''))),
        event_ts_utc=datetime.utcfromtimestamp(trade['time'] / 1000),
        symbol=trade['symbol'],
        side=TradeSide.BUY if trade['side'].upper() == 'BUY' else TradeSide.SELL,
        position_side=PositionSide(trade.get('positionSide', 'BOTH').lower()),
        qty=float(trade['qty']),
        price=float(trade['price']),
        fee=float(trade.get('commission', 0)),
        fee_asset=trade.get('commissionAsset', ''),
        order_id=str(trade.get('orderId', '')),
        realized_pnl=float(trade.get('realizedPnl', 0)),
        raw_data=trade
    )


def from_binance_futures_position(pos: dict, account_id: str, testnet: bool = False) -> PositionSnapshot:
    """Convert Binance Futures position to snapshot."""
    qty = float(pos['positionAmt'])
    return PositionSnapshot(
        snapshot_ts_utc=datetime.utcnow(),
        source=TradeSource.BINANCE_TESTNET if testnet else TradeSource.BINANCE_FUTURES,
        account_id=account_id,
        symbol=pos['symbol'],
        position_side=PositionSide.LONG if qty > 0 else PositionSide.SHORT,
        qty=abs(qty),
        entry_price=float(pos['entryPrice']),
        mark_price=float(pos.get('markPrice', pos['entryPrice'])),
        unrealized_pnl=float(pos['unrealizedProfit']),
        leverage=int(pos.get('leverage', 1)),
        margin_type=pos.get('marginType', 'cross').lower()
    )


def from_mt5_deal(deal: dict, account_id: str) -> UnifiedTrade:
    """Convert MT5/MetaApi deal to unified format."""
    # MT5 deal types: DEAL_TYPE_BUY, DEAL_TYPE_SELL
    side_map = {
        'DEAL_TYPE_BUY': TradeSide.BUY,
        'DEAL_TYPE_SELL': TradeSide.SELL,
        0: TradeSide.BUY,
        1: TradeSide.SELL
    }

    return UnifiedTrade(
        source=TradeSource.MT5,
        account_id=account_id,
        trade_id=str(deal.get('id', deal.get('ticket', ''))),
        event_ts_utc=datetime.fromisoformat(deal['time'].replace('Z', '+00:00')) if isinstance(deal.get('time'), str) else datetime.utcfromtimestamp(deal['time']),
        symbol=deal['symbol'],
        side=side_map.get(deal.get('type'), TradeSide.BUY),
        qty=float(deal.get('volume', deal.get('lots', 0))),
        price=float(deal.get('price', 0)),
        fee=float(deal.get('commission', 0)) + float(deal.get('swap', 0)),
        fee_asset=deal.get('currency', 'USD'),
        order_id=str(deal.get('orderId', '')),
        position_id=str(deal.get('positionId', '')),
        realized_pnl=float(deal.get('profit', 0)),
        raw_data=deal
    )


# =============================================================================
# Storage utilities
# =============================================================================

def get_git_sha() -> str:
    """Get current git commit SHA."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()[:8] if result.returncode == 0 else "unknown"
    except:
        return "unknown"


def get_config_hash(config_path: str) -> str:
    """Get hash of config file for versioning."""
    try:
        with open(config_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    except:
        return "unknown"


class TradeStore:
    """
    Persistent storage for unified trades with deduplication.
    """

    def __init__(self, base_path: str = "logs/trades/unified"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._trades_file = self.base_path / "trades.parquet"
        self._positions_file = self.base_path / "positions.parquet"
        self._seen_keys: set = set()
        self._load_existing_keys()

    def _load_existing_keys(self):
        """Load existing composite keys for deduplication."""
        if self._trades_file.exists():
            try:
                df = pd.read_parquet(self._trades_file)
                if 'composite_key' in df.columns:
                    self._seen_keys = set(df['composite_key'].tolist())
            except:
                pass

    def add_trade(self, trade: UnifiedTrade) -> bool:
        """
        Add trade to store. Returns True if added, False if duplicate.
        """
        if trade.composite_key in self._seen_keys:
            return False

        self._seen_keys.add(trade.composite_key)

        # Load existing or create new
        if self._trades_file.exists():
            df = pd.read_parquet(self._trades_file)
            new_row = pd.DataFrame([trade.to_dict()])
            df = pd.concat([df, new_row], ignore_index=True)
        else:
            df = pd.DataFrame([trade.to_dict()])

        df.to_parquet(self._trades_file, index=False)
        return True

    def add_position_snapshot(self, snapshot: PositionSnapshot):
        """Add position snapshot to store."""
        if self._positions_file.exists():
            df = pd.read_parquet(self._positions_file)
            new_row = pd.DataFrame([snapshot.to_dict()])
            df = pd.concat([df, new_row], ignore_index=True)
        else:
            df = pd.DataFrame([snapshot.to_dict()])

        df.to_parquet(self._positions_file, index=False)

    def get_trades(self,
                   source: Optional[TradeSource] = None,
                   symbol: Optional[str] = None,
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None) -> pd.DataFrame:
        """Query trades with optional filters."""
        if not self._trades_file.exists():
            return pd.DataFrame()

        df = pd.read_parquet(self._trades_file)

        if source:
            df = df[df['source'] == source.value]
        if symbol:
            df = df[df['symbol'] == symbol]
        if start_date:
            df = df[pd.to_datetime(df['event_ts_utc']) >= start_date]
        if end_date:
            df = df[pd.to_datetime(df['event_ts_utc']) <= end_date]

        return df

    def get_pnl_summary(self) -> dict:
        """Get P&L summary by source and symbol."""
        df = self.get_trades()
        if df.empty:
            return {}

        summary = df.groupby(['source', 'symbol']).agg({
            'realized_pnl': 'sum',
            'trade_id': 'count',
            'fee': 'sum'
        }).rename(columns={'trade_id': 'num_trades'})

        return summary.to_dict('index')


# =============================================================================
# Migration utility
# =============================================================================

def migrate_jsonl_to_parquet(jsonl_path: str, store: TradeStore, source: TradeSource, account_id: str):
    """
    Migrate existing JSONL trade logs to unified Parquet format.
    """
    from pathlib import Path
    import json

    jsonl_file = Path(jsonl_path)
    if not jsonl_file.exists():
        return 0

    migrated = 0
    with open(jsonl_file, 'r') as f:
        for line in f:
            try:
                data = json.loads(line.strip())

                # Handle different JSONL formats
                if 'trade_id' in data or 'orderId' in data:
                    trade = from_binance_futures_trade(data, account_id, testnet=True)
                    if store.add_trade(trade):
                        migrated += 1
            except:
                continue

    return migrated


if __name__ == '__main__':
    # Example usage
    store = TradeStore()

    # Example: Add a test trade
    test_trade = UnifiedTrade(
        source=TradeSource.BINANCE_TESTNET,
        account_id="test",
        trade_id="12345",
        event_ts_utc=datetime.utcnow(),
        symbol="BTCUSDT",
        side=TradeSide.BUY,
        qty=0.01,
        price=90000.0,
        git_sha=get_git_sha()
    )

    added = store.add_trade(test_trade)
    print(f"Trade added: {added}")
    print(f"Composite key: {test_trade.composite_key}")

    # Show trades
    df = store.get_trades()
    print(f"\nTotal trades in store: {len(df)}")
    if not df.empty:
        print(df[['event_ts_utc', 'source', 'symbol', 'side', 'qty', 'price']].to_string())
