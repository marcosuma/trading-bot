# IBKR TWS API Explained

This document explains how the IBKR TWS (Trader Workstation) API works and how `ibkr_broker.py` integrates with it.

## Architecture Overview

The IBKR API uses a **callback-based architecture** with two main components:

1. **EClient**: Sends requests to TWS/Gateway
2. **EWrapper**: Receives callbacks from TWS/Gateway

Our implementation:
- `IBKRBroker`: Main broker adapter class (uses EClient)
- `IBKRWrapper`: Handles all callbacks (extends EWrapper)

## Connection Flow

### 1. Connection Process

```python
# Step 1: Create EClient with wrapper
self.client = EClient(self.wrapper)
self.client.connect(host, port, clientId)

# Step 2: Start API thread (REQUIRED!)
# Without this, callbacks never fire
def run_loop():
    self.client.run()  # Blocks, processing callbacks

thread = threading.Thread(target=run_loop, daemon=True)
thread.start()

# Step 3: Wait for nextValidId callback
# This confirms connection is established
```

**Why a separate thread?**
- `client.run()` is a blocking call that processes incoming messages
- It must run in a separate thread so the main thread can continue
- Without it, callbacks like `nextValidId`, `tickPrice`, etc. never execute

### 2. Connection Callbacks

#### `nextValidId(orderId: int)`
- **When**: Immediately after successful connection
- **What**: TWS assigns a starting order ID
- **Meaning**: All future orders must use IDs >= this value
- **Our use**: Confirms connection is ready

## Market Data Flow

### Real-Time Market Data Subscription

```python
# Request market data
self.client.reqMktData(reqId, contract, "", False, False, [])
```

**Parameters:**
- `reqId`: Unique request ID (we track this)
- `contract`: Contract specification (symbol, currency, secType, exchange)
- `genericTickList`: "" = all available ticks
- `snapshot`: False = streaming, True = single snapshot
- `regulatorySnapshots`: False = no regulatory data
- `mktDataOptions`: [] = no additional options

### Market Data Callbacks

#### `tickPrice(reqId, tickType, price, attrib)`
- **When**: Every time price updates (real-time or delayed)
- **What**: Price tick for a specific tick type
- **Tick Types**:
  - `1`: BID - Best bid price
  - `2`: ASK - Best ask price
  - `4`: LAST - Last traded price (most important for trading)
  - `6`: HIGH - Current session high
  - `7`: LOW - Current session low
  - `9`: CLOSE - Previous close
  - `14`: OPEN - Current session open
  - `66-76`: DELAYED versions (for delayed data)

- **Our logic**:
  - Priority: LAST (4) > Mid(BID+ASK) > BID (1) > ASK (2)
  - Store latest prices per reqId
  - Calculate mid price when both BID and ASK available
  - Call user callback with best available price

#### `tickSize(reqId, tickType, size)`
- **When**: When order book size updates
- **What**: Size/volume information
- **Tick Types**:
  - `0`: BID_SIZE - Size at best bid
  - `3`: ASK_SIZE - Size at best ask
  - `5`: LAST_SIZE - Size of last trade
  - `8`: VOLUME - Cumulative volume
  - `69-74`: DELAYED versions

- **Our use**: Logged for debugging, not used for trading decisions

#### `tickGeneric(reqId, tickType, value)`
- **When**: Non-price data updates
- **What**: Various market statistics
- **Tick Types**:
  - `48`: RT_VOLUME - Real-time volume
  - `49`: HALTED - Trading halted flag
  - `54`: TRADE_COUNT - Number of trades
  - `55`: TRADE_RATE - Trades per second
  - And many more...

- **Our use**: Logged for debugging

#### `marketDataType(reqId, marketDataType)`
- **When**: When market data type is confirmed
- **What**: Type of data being received
- **Types**:
  - `1`: REALTIME - Real-time data (may incur costs)
  - `2`: FROZEN - Frozen/snapshot data
  - `3`: DELAYED - Delayed data (15-20 min delay, free)
  - `4`: DELAYED_FROZEN - Delayed frozen data

- **Our use**:
  - We request DELAYED (3) to avoid costs
  - Log warning if REALTIME received (may cost money)

### Error Callbacks

#### `error(reqId, errorCode, errorString, advancedOrderRejectJson)`
- **When**: Any error occurs
- **Error Code Categories**:
  - `200-299`: System/Connection errors (critical)
  - `300-399`: Order errors
  - `400-499`: Market data errors
  - `500+`: Informational messages

**Common Errors:**
- `200`: "No security definition has been found" - Contract not found/invalid
- `2104, 2106`: Market data farm connection warnings (non-critical)
- `2108`: "Market data farm connection is inactive" - Warning, not critical for forex
- `2158`: "Sec-def data farm connection is OK" - Informational (not an error!)

## Order Management

### Placing Orders

```python
order = IBOrder()
order.action = "BUY" or "SELL"
order.totalQuantity = quantity
order.orderType = "MARKET", "LIMIT", "STOP", etc.
order.lmtPrice = price  # For limit orders

self.client.placeOrder(orderId, contract, order)
```

### Order Status Callbacks

#### `orderStatus(orderId, status, filled, remaining, avgFillPrice, ...)`
- **When**: Order status changes
- **Status Values**:
  - `"Submitted"`: Order sent to exchange
  - `"PreSubmitted"`: Order queued
  - `"Filled"`: Order completely filled
  - `"PartiallyFilled"`: Order partially filled
  - `"Cancelled"`: Order cancelled
  - `"ApiCancelled"`: Cancelled via API
  - `"PendingCancel"`: Cancellation pending
  - `"PendingSubmit"`: Submission pending
  - `"Inactive"`: Order inactive

- **Parameters**:
  - `filled`: Quantity filled
  - `remaining`: Quantity remaining
  - `avgFillPrice`: Average fill price
  - `lastFillPrice`: Last fill price

## Data Flow Example

### Real-Time Tick Processing

```
1. User calls: broker.subscribe_market_data("USD-CAD", callback)
   ↓
2. IBKRBroker creates Contract, generates reqId
   ↓
3. Calls: client.reqMktData(reqId, contract, ...)
   ↓
4. TWS starts sending ticks
   ↓
5. IBKRWrapper.tickPrice() called for each price update
   ↓
6. Stores price in _latest_prices[reqId][tickType]
   ↓
7. Calculates best price (LAST > MID > BID > ASK)
   ↓
8. Calls user callback with: {
       "type": "tick",
       "price": calculated_price,
       "timestamp": datetime.utcnow()
   }
   ↓
9. User callback (in OperationRunner) routes to DataManager
   ↓
10. DataManager aggregates ticks into bars
```

## Threading Model

**Critical Understanding:**

1. **Main Thread**: Runs async event loop (FastAPI/async code)
2. **IBKR API Thread**: Runs `client.run()` (synchronous, blocking)
3. **Callback Thread**: IBKR callbacks run in API thread (synchronous)

**Problem**: Callbacks are synchronous but need to call async code

**Solution**: Use `asyncio.run_coroutine_threadsafe()`

```python
# In IBKR callback (synchronous, runs in API thread)
def tickPrice(...):
    # Schedule async work in main event loop
    coro = data_manager.handle_tick(...)
    future = asyncio.run_coroutine_threadsafe(coro, event_loop)
    # Fire and forget - don't wait
```

## Request ID Management

- Each request needs a unique `reqId`
- We track: `_data_subscriptions[asset] = reqId`
- Callbacks use `reqId` to route to correct callback
- Must increment `reqId` for each new request

## Market Data Type

**Important**: We request DELAYED data to avoid costs:

```python
self.client.reqMarketDataType(MarketDataTypeEnum.DELAYED)  # 3
```

However, TWS may override this if:
- User has real-time subscriptions enabled
- Account has real-time data access

Always check `marketDataType` callback to confirm what you're receiving!

## Summary

**Key Points:**
1. IBKR API is callback-based (not request/response)
2. Must run `client.run()` in separate thread
3. Callbacks are synchronous, use `run_coroutine_threadsafe` for async
4. Track `reqId` for each subscription/request
5. Price priority: LAST > MID > BID > ASK
6. Request DELAYED data to avoid costs
7. Error codes 200-299 are critical, 500+ are informational

