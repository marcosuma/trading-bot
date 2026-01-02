# Alternative Free Real-Time Data Sources for Trading

This document outlines free alternatives to IBKR for real-time market data that also support trading.

See [Broker Integration](brokers.md) for broker setup and [Live Trading System](README.md) for overview.

## Requirements
- **Free real-time data** (or very low cost)
- **Trading capabilities** (paper/live trading)
- **Forex support** (primary use case)
- **API access** for programmatic trading

## Recommended Alternatives

### 1. **OANDA** ⭐ (Recommended)
**Status**: Free real-time data + Trading API

**Pros**:
- ✅ **Free real-time forex data** via REST API
- ✅ **Free paper trading** account
- ✅ **RESTful API** (oandapyV20) - easier than IBKR
- ✅ **No market data fees** for forex
- ✅ **Good documentation** and Python SDK
- ✅ **WebSocket streaming** for real-time prices
- ✅ **Already in requirements.txt** (`oandapyV20`)

**Cons**:
- ❌ Forex only (no stocks/crypto)
- ❌ Smaller selection of instruments than IBKR

**API Documentation**: https://developer.oanda.com/
**Python SDK**: `pip install oandapyV20`

**Implementation Notes**:
- Already planned in architecture (see `LIVE_TRADING_ARCHITECTURE.md`)
- Can be added as alternative broker in `live_trading/brokers/oanda_broker.py`
- WebSocket streaming: `GET /v3/accounts/{accountID}/pricing/stream`

**Code Example**:
```python
from oandapyV20 import API
from oandapyV20.endpoints.pricing import PricingStream

api = API(access_token="your_token", environment="practice")
params = {"instruments": "EUR_USD"}
r = PricingStream(accountID="your_account", params=params)
for response in api.request(r):
    # Real-time price updates
    print(response)
```

---

### 2. **Alpha Vantage** (Data Only)
**Status**: Free tier available (limited)

**Pros**:
- ✅ **Free API** with API key
- ✅ **Forex, stocks, crypto** support
- ✅ **RESTful API** - easy integration
- ✅ **Real-time and historical data**

**Cons**:
- ❌ **No trading capabilities** (data only)
- ❌ **Rate limits** on free tier (5 calls/min, 500 calls/day)
- ❌ **Not suitable for high-frequency trading**

**API**: https://www.alphavantage.co/documentation/
**Free Tier**: 5 API calls per minute, 500 per day

**Use Case**: Good for backtesting, not live trading

---

### 3. **Polygon.io** (Limited Free Tier)
**Status**: Free tier with limitations

**Pros**:
- ✅ **Free tier** available
- ✅ **Real-time data** via WebSocket
- ✅ **Forex, stocks, crypto**
- ✅ **Good documentation**

**Cons**:
- ❌ **No trading capabilities** (data only)
- ❌ **Rate limits** on free tier
- ❌ **Limited historical data** on free tier

**API**: https://polygon.io/
**Free Tier**: Limited to 5 API calls per minute

---

### 4. **Yahoo Finance (yfinance)** (Data Only)
**Status**: Free, unofficial API

**Pros**:
- ✅ **Completely free**
- ✅ **Forex, stocks, crypto**
- ✅ **Python library** (`yfinance`)
- ✅ **Real-time and historical data**

**Cons**:
- ❌ **No trading capabilities** (data only)
- ❌ **Unofficial API** (can break)
- ❌ **Rate limiting** (may get blocked)
- ❌ **Not reliable for production**

**Library**: `pip install yfinance`

**Use Case**: Good for testing/development, not production

---

### 5. **Binance API** (Crypto Only)
**Status**: Free real-time data + Trading

**Pros**:
- ✅ **Free real-time data** via WebSocket
- ✅ **Trading API** available
- ✅ **Crypto pairs** (BTC/USDT, ETH/USDT, etc.)
- ✅ **Good documentation**
- ✅ **No fees for data**

**Cons**:
- ❌ **Crypto only** (no forex/stocks)
- ❌ **Different asset class** than forex

**API**: https://binance-docs.github.io/apidocs/
**WebSocket**: `wss://stream.binance.com:9443/ws/btcusdt@ticker`

---

### 6. **Twelve Data** (Limited Free Tier)
**Status**: Free tier with API key

**Pros**:
- ✅ **Free tier** (800 calls/day)
- ✅ **Forex, stocks, crypto**
- ✅ **Real-time data** via WebSocket
- ✅ **RESTful API**

**Cons**:
- ❌ **No trading capabilities** (data only)
- ❌ **Rate limits** on free tier

**API**: https://twelvedata.com/

---

### 7. **TradingView** ❌ (Not Recommended for API)
**Status**: No public API available

**Pros**:
- ✅ **Excellent charting platform** with real-time data
- ✅ **Free real-time data** for some markets (US stocks via Cboe BZX)
- ✅ **Trading capabilities** through integrated brokers
- ✅ **Forex, stocks, crypto, futures** support

**Cons**:
- ❌ **NO PUBLIC API** - TradingView does not provide an API for accessing market data or indicator values
- ❌ **Broker integration only** - Their REST API is for brokers to integrate INTO TradingView, not for getting data FROM it
- ❌ **No programmatic trading** - Trading must be done through the web interface with connected brokers
- ❌ **Unofficial methods risky** - WebSocket scraping violates Terms of Service and can break at any time
- ❌ **Not suitable for automated trading systems**

**Official Statement**:
> "TradingView does not provide a public API for accessing market data or indicator values. Our REST API is intended for brokers aiming to integrate their services into the TradingView platform."

**Unofficial Workarounds** (Not Recommended):
- WebSocket connections to internal feeds (unofficial, unstable, violates ToS)
- Screen scraping (violates Terms of Service)
- Pine Script alerts (limited, not for real-time streaming)

**Use Case**: Great for manual trading and analysis, but **NOT suitable for API-based automated trading systems**.

**Reference**: https://www.tradingview.com/support/solutions/43000474413/

---

## Recommendation: OANDA

**Best Choice**: **OANDA** for the following reasons:

1. ✅ **Free real-time forex data** - no market data fees
2. ✅ **Trading API** - can execute trades
3. ✅ **Paper trading** - free testing environment
4. ✅ **WebSocket streaming** - real-time price updates
5. ✅ **Already planned** - mentioned in architecture docs
6. ✅ **Python SDK available** - `oandapyV20` already in requirements
7. ✅ **Forex-focused** - matches your use case

## Implementation Plan for OANDA

### Step 1: Create OANDA Broker Adapter
**File**: `live_trading/brokers/oanda_broker.py`

```python
from oandapyV20 import API
from oandapyV20.endpoints.pricing import PricingStream
import asyncio
import websocket
import json

class OANDABroker(BaseBroker):
    def __init__(self):
        self.api = None
        self.account_id = None
        self.connected = False
        self._data_subscriptions = {}  # asset -> websocket

    async def connect(self) -> bool:
        # Initialize OANDA API
        # Connect to practice/live environment
        pass

    async def subscribe_market_data(self, asset, callback):
        # Convert "USD-CAD" to "USD_CAD" format
        # Start WebSocket stream
        # Route ticks to callback
        pass
```

### Step 2: Update Config
**File**: `live_trading/config.py`
- Add `OANDA_API_KEY`
- Add `OANDA_ACCOUNT_ID`
- Add `OANDA_ENVIRONMENT` (practice/live)

### Step 3: Update Trading Engine
- Support both IBKR and OANDA brokers
- Allow switching via config

## Comparison Table

| Service | Free Data | Trading | Forex | API Quality | Recommendation |
|---------|-----------|---------|-------|-------------|-----------------|
| **OANDA** | ✅ Yes | ✅ Yes | ✅ Yes | ⭐⭐⭐⭐⭐ | **Best Choice** |
| Alpha Vantage | ✅ Limited | ❌ No | ✅ Yes | ⭐⭐⭐ | Data only |
| Polygon.io | ✅ Limited | ❌ No | ✅ Yes | ⭐⭐⭐⭐ | Data only |
| Yahoo Finance | ✅ Yes | ❌ No | ✅ Yes | ⭐⭐ | Unofficial, unreliable |
| Binance | ✅ Yes | ✅ Yes | ❌ No | ⭐⭐⭐⭐ | Crypto only |
| Twelve Data | ✅ Limited | ❌ No | ✅ Yes | ⭐⭐⭐ | Data only |
| **TradingView** | ✅ Yes* | ✅ Yes* | ✅ Yes | ❌ **No API** | **Not suitable** |

## Next Steps

1. **Short-term**: Use IBKR with DELAYED data (free, 15-20 min delay)
2. **Medium-term**: Implement OANDA broker adapter for real-time forex data
3. **Long-term**: Support multiple brokers (IBKR for stocks, OANDA for forex)

## OANDA Integration Resources

- **API Documentation**: https://developer.oanda.com/rest-live-v20/introduction/
- **Python SDK**: https://github.com/oanda/v20-python
- **WebSocket Streaming**: https://developer.oanda.com/rest-live-v20/streaming/
- **Paper Trading**: https://www.oanda.com/us-en/trading/forex-demo/

