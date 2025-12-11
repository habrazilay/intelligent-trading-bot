"""
MetaApi Adapter for MT5 Forex Trading

This adapter uses MetaApi REST API to connect to MT5 accounts.
It provides a unified interface similar to the Binance adapter.
"""

import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
import logging

log = logging.getLogger('metaapi_adapter')


class MetaApiAdapter:
    """Adapter for MetaApi REST API - connects to MT5 accounts."""

    # MetaApi REST API base URLs
    PROVISIONING_API = "https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai"
    CLIENT_API = "https://mt-client-api-v1.london.agiliumtrade.ai"

    def __init__(self, token: str = None, account_id: str = None):
        """
        Initialize MetaApi adapter.

        Args:
            token: MetaApi access token (or from env METAAPI_TOKEN)
            account_id: MetaApi account ID (or from env METAAPI_ACCOUNT_ID)
        """
        load_dotenv('.env.dev')

        self.token = token or os.getenv('METAAPI_TOKEN')
        self.account_id = account_id or os.getenv('METAAPI_ACCOUNT_ID')

        if not self.token or not self.account_id:
            raise ValueError("METAAPI_TOKEN and METAAPI_ACCOUNT_ID are required")

        self.headers = {
            'auth-token': self.token,
            'Content-Type': 'application/json'
        }

        self._account_info = None

    def _request(self, method: str, url: str, **kwargs) -> Dict:
        """Make HTTP request to MetaApi."""
        try:
            response = requests.request(
                method,
                url,
                headers=self.headers,
                timeout=30,
                **kwargs
            )
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.RequestException as e:
            log.error(f"MetaApi request error: {e}")
            raise

    @property
    def base_url(self) -> str:
        """Get base URL for account-specific endpoints."""
        return f"{self.CLIENT_API}/users/current/accounts/{self.account_id}"

    # ==================== Account Information ====================

    def get_account_info(self) -> Dict:
        """Get account information (balance, equity, margin, etc.)."""
        url = f"{self.base_url}/account-information"
        self._account_info = self._request('GET', url)
        return self._account_info

    def get_balance(self) -> Decimal:
        """Get account balance."""
        info = self.get_account_info()
        return Decimal(str(info.get('balance', 0)))

    def get_equity(self) -> Decimal:
        """Get account equity."""
        info = self.get_account_info()
        return Decimal(str(info.get('equity', 0)))

    def get_free_margin(self) -> Decimal:
        """Get free margin available for trading."""
        info = self.get_account_info()
        return Decimal(str(info.get('freeMargin', 0)))

    # ==================== Market Data ====================

    def get_symbols(self) -> List[str]:
        """Get list of available symbols."""
        url = f"{self.base_url}/symbols"
        return self._request('GET', url)

    def get_symbol_specification(self, symbol: str) -> Dict:
        """Get symbol specification (min lot, digits, etc.)."""
        url = f"{self.base_url}/symbols/{symbol}/specification"
        return self._request('GET', url)

    def get_symbol_price(self, symbol: str) -> Dict:
        """Get current bid/ask price for a symbol."""
        url = f"{self.base_url}/symbols/{symbol}/current-price"
        return self._request('GET', url)

    def get_ticker_price(self, symbol: str) -> float:
        """Get current price (mid price between bid and ask)."""
        price = self.get_symbol_price(symbol)
        bid = price.get('bid', 0)
        ask = price.get('ask', 0)
        return (bid + ask) / 2

    def get_candles(
        self,
        symbol: str,
        timeframe: str = '1h',
        start_time: datetime = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Get historical candles (klines).

        Args:
            symbol: Trading pair (e.g., 'EURUSD')
            timeframe: Candle timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w)
            start_time: Start time for historical data
            limit: Maximum number of candles

        Returns:
            DataFrame with OHLCV data
        """
        # Map timeframe to MetaApi format
        tf_map = {
            '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
            '1h': '1h', '4h': '4h', '1d': '1d', '1w': '1w', '1M': '1mn'
        }
        mt_timeframe = tf_map.get(timeframe, '1h')

        if start_time is None:
            start_time = datetime.utcnow() - timedelta(days=30)

        url = f"{self.base_url}/historical-market-data/symbols/{symbol}/timeframes/{mt_timeframe}/candles"
        params = {
            'startTime': start_time.isoformat() + 'Z',
            'limit': limit
        }

        candles = self._request('GET', url, params=params)

        if not candles:
            return pd.DataFrame()

        df = pd.DataFrame(candles)
        df['time'] = pd.to_datetime(df['time'])
        df = df.rename(columns={
            'time': 'timestamp',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'tickVolume': 'volume'
        })

        return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]

    # Alias for compatibility
    def get_klines(self, symbol: str, interval: str, limit: int = 1000) -> pd.DataFrame:
        """Alias for get_candles (Binance compatibility)."""
        return self.get_candles(symbol, interval, limit=limit)

    # ==================== Trading ====================

    def get_positions(self) -> List[Dict]:
        """Get all open positions."""
        url = f"{self.base_url}/positions"
        return self._request('GET', url)

    def get_orders(self) -> List[Dict]:
        """Get all pending orders."""
        url = f"{self.base_url}/orders"
        return self._request('GET', url)

    def create_market_order(
        self,
        symbol: str,
        side: str,  # 'buy' or 'sell'
        volume: float,
        stop_loss: float = None,
        take_profit: float = None,
        comment: str = None
    ) -> Dict:
        """
        Create a market order.

        Args:
            symbol: Trading pair (e.g., 'EURUSD')
            side: 'buy' or 'sell'
            volume: Lot size (e.g., 0.01)
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            comment: Order comment (optional)

        Returns:
            Order result
        """
        url = f"{self.base_url}/trade"

        action_type = 'ORDER_TYPE_BUY' if side.lower() == 'buy' else 'ORDER_TYPE_SELL'

        order = {
            'actionType': action_type,
            'symbol': symbol,
            'volume': volume
        }

        if stop_loss:
            order['stopLoss'] = stop_loss
        if take_profit:
            order['takeProfit'] = take_profit
        if comment:
            order['comment'] = comment

        return self._request('POST', url, json=order)

    def create_limit_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        price: float,
        stop_loss: float = None,
        take_profit: float = None,
        comment: str = None
    ) -> Dict:
        """
        Create a limit order.

        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            volume: Lot size
            price: Limit price
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            comment: Order comment (optional)
        """
        url = f"{self.base_url}/trade"

        action_type = 'ORDER_TYPE_BUY_LIMIT' if side.lower() == 'buy' else 'ORDER_TYPE_SELL_LIMIT'

        order = {
            'actionType': action_type,
            'symbol': symbol,
            'volume': volume,
            'openPrice': price
        }

        if stop_loss:
            order['stopLoss'] = stop_loss
        if take_profit:
            order['takeProfit'] = take_profit
        if comment:
            order['comment'] = comment

        return self._request('POST', url, json=order)

    def close_position(self, position_id: str) -> Dict:
        """Close a position by ID."""
        url = f"{self.base_url}/trade"

        order = {
            'actionType': 'POSITION_CLOSE_ID',
            'positionId': position_id
        }

        return self._request('POST', url, json=order)

    def close_position_by_symbol(self, symbol: str) -> Dict:
        """Close all positions for a symbol."""
        url = f"{self.base_url}/trade"

        order = {
            'actionType': 'POSITION_CLOSE_SYMBOL',
            'symbol': symbol
        }

        return self._request('POST', url, json=order)

    def cancel_order(self, order_id: str) -> Dict:
        """Cancel a pending order."""
        url = f"{self.base_url}/trade"

        order = {
            'actionType': 'ORDER_CANCEL',
            'orderId': order_id
        }

        return self._request('POST', url, json=order)

    def modify_position(
        self,
        position_id: str,
        stop_loss: float = None,
        take_profit: float = None
    ) -> Dict:
        """Modify stop loss and take profit of a position."""
        url = f"{self.base_url}/trade"

        order = {
            'actionType': 'POSITION_MODIFY',
            'positionId': position_id
        }

        if stop_loss:
            order['stopLoss'] = stop_loss
        if take_profit:
            order['takeProfit'] = take_profit

        return self._request('POST', url, json=order)

    # ==================== History ====================

    def get_history_orders(
        self,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 1000
    ) -> List[Dict]:
        """Get historical orders."""
        url = f"{self.base_url}/history-orders/time"

        if start_time is None:
            start_time = datetime.utcnow() - timedelta(days=30)
        if end_time is None:
            end_time = datetime.utcnow()

        params = {
            'startTime': start_time.isoformat() + 'Z',
            'endTime': end_time.isoformat() + 'Z',
            'limit': limit
        }

        return self._request('GET', url, params=params)

    def get_history_deals(
        self,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 1000
    ) -> List[Dict]:
        """Get historical deals (executed trades)."""
        url = f"{self.base_url}/history-deals/time"

        if start_time is None:
            start_time = datetime.utcnow() - timedelta(days=30)
        if end_time is None:
            end_time = datetime.utcnow()

        params = {
            'startTime': start_time.isoformat() + 'Z',
            'endTime': end_time.isoformat() + 'Z',
            'limit': limit
        }

        return self._request('GET', url, params=params)


# ==================== Test Connection ====================

def test_connection():
    """Test MetaApi connection."""
    print("Testing MetaApi connection...")

    try:
        adapter = MetaApiAdapter()

        # Get account info
        info = adapter.get_account_info()
        print(f"\n✅ Connected to MT5!")
        print(f"   Broker: {info.get('broker')}")
        print(f"   Balance: ${info.get('balance'):,.2f}")
        print(f"   Equity: ${info.get('equity'):,.2f}")
        print(f"   Leverage: 1:{info.get('leverage')}")

        # Get symbols
        symbols = adapter.get_symbols()
        forex_pairs = [s for s in symbols if 'USD' in s][:5]
        print(f"\n   Forex pairs: {', '.join(forex_pairs)}")

        # Get positions
        positions = adapter.get_positions()
        print(f"   Open positions: {len(positions)}")

        print("\n✅ MetaApi adapter working!")
        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


if __name__ == '__main__':
    test_connection()
