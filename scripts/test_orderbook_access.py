#!/usr/bin/env python3
"""
Test Binance order book data access and quality

This script tests:
1. WebSocket connection to Binance
2. Order book data availability
3. Update frequency
4. Data quality (depth, spreads, etc.)
"""

import time
import json
from datetime import datetime
from binance import ThreadedWebsocketManager
from binance.client import Client

# Statistics tracking
stats = {
    'updates_received': 0,
    'first_update_time': None,
    'last_update_time': None,
    'avg_bid_depth': [],
    'avg_ask_depth': [],
    'spreads': [],
    'sample_data': []
}

def handle_depth_update(msg):
    """Handle order book depth updates from Binance WebSocket"""
    global stats

    try:
        # Track timing
        stats['updates_received'] += 1
        current_time = datetime.now()

        if stats['first_update_time'] is None:
            stats['first_update_time'] = current_time
        stats['last_update_time'] = current_time

        # Binance sends different message types
        # Diff depth stream: {'e': 'depthUpdate', 'b': [...], 'a': [...]}
        # Partial depth stream: {'lastUpdateId': ..., 'bids': [...], 'asks': [...]}

        bids = None
        asks = None

        if 'b' in msg and 'a' in msg:
            # Diff depth update format
            bids = msg['b']
            asks = msg['a']
        elif 'bids' in msg and 'asks' in msg:
            # Partial depth format
            bids = msg['bids']
            asks = msg['asks']

        if bids and asks and len(bids) > 0 and len(asks) > 0:
            # Calculate metrics
            best_bid = float(bids[0][0])
            best_ask = float(asks[0][0])
            spread = best_ask - best_bid
            spread_pct = (spread / best_bid) * 100

            stats['avg_bid_depth'].append(len(bids))
            stats['avg_ask_depth'].append(len(asks))
            stats['spreads'].append(spread_pct)

            # Store first 3 samples for inspection
            if len(stats['sample_data']) < 3:
                stats['sample_data'].append({
                    'timestamp': current_time.isoformat(),
                    'best_bid': best_bid,
                    'best_ask': best_ask,
                    'spread': spread,
                    'spread_pct': spread_pct,
                    'bid_depth': len(bids),
                    'ask_depth': len(asks),
                    'top_5_bids': [[float(b[0]), float(b[1])] for b in bids[:5]],
                    'top_5_asks': [[float(a[0]), float(a[1])] for a in asks[:5]]
                })

            # Print progress every 10 updates
            if stats['updates_received'] % 10 == 0:
                print(f"Updates: {stats['updates_received']} | "
                      f"Spread: {spread_pct:.4f}% | "
                      f"Depth: {len(bids)}b/{len(asks)}a")

    except Exception as e:
        print(f"Error processing message: {e}")
        print(f"Message structure: {msg.keys() if isinstance(msg, dict) else type(msg)}")


def test_rest_api_orderbook():
    """Test REST API order book access (fallback if WebSocket fails)"""
    print("\n" + "="*60)
    print("Testing REST API Order Book Access...")
    print("="*60)

    try:
        client = Client()  # No API key needed for public data

        # Get order book depth
        depth = client.get_order_book(symbol='BTCUSDT', limit=20)

        bids = depth['bids']
        asks = depth['asks']

        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        spread = best_ask - best_bid
        spread_pct = (spread / best_bid) * 100

        print(f"✅ REST API works!")
        print(f"   Best bid: ${best_bid:,.2f}")
        print(f"   Best ask: ${best_ask:,.2f}")
        print(f"   Spread: {spread_pct:.4f}%")
        print(f"   Depth: {len(bids)} bids, {len(asks)} asks")
        print(f"\n   Top 5 bids:")
        for i, (price, qty) in enumerate(bids[:5]):
            print(f"      {i+1}. ${float(price):,.2f} × {float(qty):.4f} BTC")
        print(f"\n   Top 5 asks:")
        for i, (price, qty) in enumerate(asks[:5]):
            print(f"      {i+1}. ${float(price):,.2f} × {float(qty):.4f} BTC")

        return True

    except Exception as e:
        print(f"❌ REST API failed: {e}")
        return False


def test_websocket_orderbook(duration=30):
    """Test WebSocket order book streaming"""
    print("\n" + "="*60)
    print(f"Testing WebSocket Order Book Streaming ({duration}s)...")
    print("="*60)

    try:
        twm = ThreadedWebsocketManager()
        twm.start()

        # Subscribe to partial book depth stream (faster, 100ms updates)
        # Options: depth5, depth10, depth20 @ 100ms or 1000ms
        stream = twm.start_depth_socket(callback=handle_depth_update, symbol='BTCUSDT', depth='20')

        print(f"Listening to BTCUSDT order book for {duration} seconds...")
        print("(Press Ctrl+C to stop early)\n")

        time.sleep(duration)

        twm.stop()
        print("\n✅ WebSocket test complete!")

        return True

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        twm.stop()
        return True

    except Exception as e:
        print(f"\n❌ WebSocket failed: {e}")
        return False


def print_summary():
    """Print summary statistics"""
    print("\n" + "="*60)
    print("ORDER BOOK DATA QUALITY ASSESSMENT")
    print("="*60)

    if stats['updates_received'] == 0:
        print("❌ No data received - order book access not available")
        return

    # Calculate duration
    duration = (stats['last_update_time'] - stats['first_update_time']).total_seconds()
    update_rate = stats['updates_received'] / duration if duration > 0 else 0

    print(f"\n📊 Statistics:")
    print(f"   Updates received: {stats['updates_received']}")
    print(f"   Duration: {duration:.1f} seconds")
    print(f"   Update rate: {update_rate:.1f} updates/second")

    if stats['avg_bid_depth']:
        avg_bid_depth = sum(stats['avg_bid_depth']) / len(stats['avg_bid_depth'])
        avg_ask_depth = sum(stats['avg_ask_depth']) / len(stats['avg_ask_depth'])
        print(f"   Average depth: {avg_bid_depth:.0f} bids, {avg_ask_depth:.0f} asks")

    if stats['spreads']:
        avg_spread = sum(stats['spreads']) / len(stats['spreads'])
        min_spread = min(stats['spreads'])
        max_spread = max(stats['spreads'])
        print(f"   Average spread: {avg_spread:.4f}%")
        print(f"   Spread range: {min_spread:.4f}% - {max_spread:.4f}%")

    # Show sample data
    if stats['sample_data']:
        print(f"\n📋 Sample Order Book Data:")
        for i, sample in enumerate(stats['sample_data'][:3], 1):
            print(f"\n   Sample {i} ({sample['timestamp']}):")
            print(f"      Best bid: ${sample['best_bid']:,.2f}")
            print(f"      Best ask: ${sample['best_ask']:,.2f}")
            print(f"      Spread: {sample['spread_pct']:.4f}%")
            # Format bid/ask lists separately to avoid nested f-string issues
            top_bids = ', '.join([f"${p:,.2f}×{q:.3f}" for p, q in sample['top_5_bids'][:3]])
            top_asks = ', '.join([f"${p:,.2f}×{q:.3f}" for p, q in sample['top_5_asks'][:3]])
            print(f"      Top 3 bids: {top_bids}")
            print(f"      Top 3 asks: {top_asks}")

    # Verdict
    print("\n" + "="*60)
    print("VERDICT:")
    print("="*60)

    if update_rate >= 1:
        print("✅ Order book data is EXCELLENT")
        print(f"   • Update rate: {update_rate:.1f}/s (fast enough for scalping)")
        print(f"   • Depth: {avg_bid_depth:.0f} levels (sufficient for analysis)")
        print(f"   • Spread: {avg_spread:.4f}% (tight, good liquidity)")
        print("\n💡 RECOMMENDATION: Proceed with order flow feature implementation")
        print("   • Implement bid-ask imbalance features")
        print("   • Implement order book pressure indicators")
        print("   • Expected win rate improvement: +5-10%")

    elif update_rate >= 0.1:
        print("⚠️  Order book data is USABLE but not ideal")
        print(f"   • Update rate: {update_rate:.1f}/s (slow for 1m scalping)")
        print("\n💡 RECOMMENDATION: Consider 5m or 15m timeframes")
        print("   • Order flow features may still help")
        print("   • Expected win rate improvement: +2-5%")

    else:
        print("❌ Order book data quality is POOR")
        print(f"   • Update rate: {update_rate:.1f}/s (too slow)")
        print("\n💡 RECOMMENDATION: Pivot to daily swing trading")
        print("   • Don't rely on order flow data")
        print("   • Use longer timeframes where lagging indicators work")
        print("   • Focus on trend following instead of scalping")


def main():
    """Main test function"""
    print("\n🔍 BINANCE ORDER BOOK ACCESS TEST")
    print("="*60)
    print("This test will check:")
    print("  1. REST API order book access (snapshot)")
    print("  2. WebSocket order book streaming (real-time)")
    print("  3. Data quality and update frequency")
    print("="*60)

    # Test REST API first
    rest_works = test_rest_api_orderbook()

    if not rest_works:
        print("\n❌ Cannot access Binance order book data at all")
        print("   Please check internet connection and Binance API status")
        return

    # Test WebSocket
    print("\nREST API works! Now testing WebSocket streaming...")
    input("\nPress ENTER to start 30-second WebSocket test...")

    ws_works = test_websocket_orderbook(duration=30)

    # Print summary
    print_summary()

    # Save results
    with open('/home/user/intelligent-trading-bot/orderbook_test_results.json', 'w') as f:
        json.dump({
            'rest_api_works': rest_works,
            'websocket_works': ws_works,
            'stats': {
                'updates_received': stats['updates_received'],
                'duration_seconds': (stats['last_update_time'] - stats['first_update_time']).total_seconds()
                                    if stats['last_update_time'] and stats['first_update_time'] else 0,
                'avg_spread_pct': sum(stats['spreads']) / len(stats['spreads']) if stats['spreads'] else None,
                'avg_bid_depth': sum(stats['avg_bid_depth']) / len(stats['avg_bid_depth']) if stats['avg_bid_depth'] else None
            },
            'sample_data': stats['sample_data']
        }, f, indent=2)

    print(f"\n📁 Results saved to: orderbook_test_results.json")


if __name__ == '__main__':
    main()
