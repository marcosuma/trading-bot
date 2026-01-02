# Real-Time Data Flow from IBKR

This document explains how real-time market data flows from IBKR to the database.

See [Live Trading System](README.md) for overview and [Broker Integration](brokers.md) for broker setup.

## High-Level Flow

```
1. Operation Created (API)
   ↓
2. OperationRunner.start() subscribes to market data
   ↓
3. IBKRBroker.subscribe_market_data() calls reqMktData
   ↓
4. IBKR sends ticks via callbacks (tickPrice, tickSize)
   ↓
5. Callbacks route to broker_tick_callback
   ↓
6. broker_tick_callback schedules handle_tick (async)
   ↓
7. DataManager.handle_tick() aggregates ticks into bars
   ↓
8. Completed bars stored in MongoDB
```

## Detailed Code Flow

### 1. Operation Creation
**File**: `live_trading/api/main.py`
- **Line**: `77-115` - `create_operation()` endpoint
- Creates a `TradingOperation` via `engine.start_operation()`

### 2. Operation Start
**File**: `live_trading/engine/trading_engine.py`
- **Line**: `91-160` - `start_operation()` method
- Creates `OperationRunner` and calls `runner.start()`

### 3. Market Data Subscription
**File**: `live_trading/engine/operation_runner.py`
- **Line**: `36-127` - `start()` method
- **Key steps**:
  1. **Line 73-81**: Captures the event loop for async scheduling
  2. **Line 87-114**: Creates `broker_tick_callback` function
  3. **Line 116-127**: Calls `broker.subscribe_market_data()` with the callback

**Critical Code** (Line 87-114):
```python
def broker_tick_callback(tick_data: Dict):
    """Callback to route broker ticks to data manager"""
    if tick_data.get("type") == "tick":
        price = tick_data.get("price")
        size = tick_data.get("size", 0.0)
        timestamp = tick_data.get("timestamp", datetime.utcnow())

        if price is not None and self.event_loop is not None:
            # Schedule async work from IBKR thread to main event loop
            coro = self.data_manager.handle_tick(...)
            future = asyncio.run_coroutine_threadsafe(coro, self.event_loop)
```

### 4. IBKR Market Data Request
**File**: `live_trading/brokers/ibkr_broker.py`
- **Line**: `229-270` - `subscribe_market_data()` method
- **Key steps**:
  1. **Line 243-249**: Parses asset (e.g., "USD-CAD" → base="USD", quote="CAD")
  2. **Line 251-255**: Creates IBKR `Contract` object
  3. **Line 257-260**: Generates unique `req_id` and stores callback
  4. **Line 262-265**: Calls `self.client.reqMktData(req_id, contract, "", False, False, [])`

**Critical Code** (Line 251-265):
```python
# Create contract for forex
contract = Contract()
contract.symbol = base          # e.g., "USD"
contract.currency = quote       # e.g., "CAD"
contract.secType = "CASH"
contract.exchange = "IDEALPRO"

req_id = self._get_next_req_id()
self._data_subscriptions[asset] = req_id
self.wrapper.data_callbacks[req_id] = callback

# Request market data (streaming, not snapshot)
self.client.reqMktData(req_id, contract, "", False, False, [])
```

### 5. IBKR Tick Callbacks
**File**: `live_trading/brokers/ibkr_broker.py`
- **Line**: `63-103` - `tickPrice()` and `tickSize()` methods
- **How it works**:
  - IBKR API thread calls `tickPrice()` when price updates arrive
  - **Line 70**: Logs tick type (1=BID, 2=ASK, 4=LAST)
  - **Line 75-82**: Only processes LAST price (tickType=4) for trading
  - **Line 76-82**: Calls the registered callback with tick data

**Critical Code** (Line 63-86):
```python
def tickPrice(self, reqId: TickerId, tickType: int, price: float, attrib):
    """Real-time price update"""
    tick_type_names = {1: "BID", 2: "ASK", 4: "LAST", 6: "HIGH", 7: "LOW", 9: "CLOSE"}
    tick_name = tick_type_names.get(tickType, f"UNKNOWN({tickType})")
    logger.debug(f"tickPrice: reqId={reqId}, tickType={tickType}({tick_name}), price={price}")

    if reqId in self.data_callbacks:
        callback = self.data_callbacks[reqId]
        # Only use LAST price (4) for trading
        if tickType == 4:  # LAST
            callback({
                "type": "tick",
                "tick_type": tickType,
                "tick_name": tick_name,
                "price": price,
                "timestamp": datetime.utcnow()
            })
```

### 6. Tick Aggregation into Bars
**File**: `live_trading/data/data_manager.py`
- **Line**: `146-161` - `handle_tick()` method
- **Line**: `18-104` - `BarAggregator` class
- **How it works**:
  1. Each tick is passed to all `BarAggregator` instances (one per bar_size)
  2. `BarAggregator.add_tick()` updates the current bar (OHLCV)
  3. When a bar time boundary is crossed, returns a completed bar
  4. Completed bar is processed and stored

**Critical Code** (Line 48-80):
```python
def add_tick(self, price: float, size: float, timestamp: datetime) -> Optional[Dict]:
    """Add a tick and return completed bar if bar is complete."""
    bar_start = self._get_bar_start_time(timestamp)

    # If new bar started, finalize previous bar
    if self.current_bar is not None and bar_start != self.bar_start_time:
        completed_bar = self.current_bar.copy()
        completed_bar["timestamp"] = self.bar_start_time
        completed_bar["close"] = self.current_bar["close"]
        completed_bar["volume"] = self.current_bar["volume"]

        # Start new bar
        self._start_new_bar(bar_start, price, size)
        return completed_bar

    # Update current bar
    self.current_bar["high"] = max(self.current_bar["high"], price)
    self.current_bar["low"] = min(self.current_bar["low"], price)
    self.current_bar["close"] = price
    self.current_bar["volume"] += size

    return None
```

### 7. Bar Processing and Storage
**File**: `live_trading/data/data_manager.py`
- **Line**: `163-220` - `_process_completed_bar()` method
- **Key steps**:
  1. **Line 172**: Adds bar to in-memory buffer
  2. **Line 175-181**: Applies data retention limit
  3. **Line 184-200**: Calculates technical indicators
  4. **Line 203-220**: Stores bar in MongoDB `market_data` collection

**Critical Code** (Line 203-220):
```python
# Store in database
from bson import ObjectId
market_data = MarketData(
    operation_id=ObjectId(operation_id),
    bar_size=bar_size,
    timestamp=bar_data["timestamp"],
    open=bar_data["open"],
    high=bar_data["high"],
    low=bar_data["low"],
    close=bar_data["close"],
    volume=bar_data.get("volume", 0.0),
    indicators=indicators
)
await market_data.insert()
```

## Threading Model

### IBKR API Thread
- **File**: `live_trading/brokers/ibkr_broker.py`
- **Line**: `156-164` - Background thread running `client.run()`
- **Purpose**: Processes IBKR API messages and callbacks
- **Callbacks**: `tickPrice()`, `tickSize()`, `error()` run in this thread

### Main Event Loop (FastAPI)
- **Thread**: Main async event loop (FastAPI/Uvicorn)
- **Purpose**: Handles HTTP requests and async operations
- **Operations**: `handle_tick()`, `_process_completed_bar()`, database operations

### Thread Communication
- **Method**: `asyncio.run_coroutine_threadsafe()`
- **File**: `live_trading/engine/operation_runner.py`
- **Line**: `108` - Schedules async work from IBKR thread to main loop
- **Why**: IBKR callbacks are synchronous, but our data processing is async

## Potential Issues

### 1. No Price Ticks Received
**Symptoms**: Only seeing `tickGeneric` with `tickType: 49` (HALTED)
**Possible Causes**:
- Contract not found (Error 200)
- Market data permissions missing
- Contract specification incorrect
- Market closed or pair unavailable

**Check**:
- Look for Error 200 in logs
- Verify contract: `symbol`, `currency`, `secType="CASH"`, `exchange="IDEALPRO"`
- Check TWS/Gateway market data subscriptions

### 2. Event Loop Issues
**Symptoms**: "No event loop available for tick processing"
**Fix**: Event loop is captured in `start()` method (Line 73-81)

### 3. Callback Not Firing
**Symptoms**: No `tickPrice` callbacks received
**Check**:
- Is `reqMktData` being called? (Check logs)
- Is `req_id` matching in `data_callbacks`?
- Is IBKR API thread running? (Check thread status)

### 4. Bars Not Being Stored
**Symptoms**: Ticks received but no bars in database
**Check**:
- Are ticks being aggregated? (Check `BarAggregator`)
- Are bars completing? (Check bar time boundaries)
- Is database write failing? (Check error logs)

## Debugging Checklist

1. ✅ **IBKR Connected?**
   - Check: "Successfully connected to IBKR" log
   - File: `live_trading/brokers/ibkr_broker.py:205`

2. ✅ **Market Data Requested?**
   - Check: "Requesting market data for {asset}" log
   - File: `live_trading/brokers/ibkr_broker.py:262`

3. ✅ **Ticks Received?**
   - Check: "tickPrice: reqId=X, tickType=4(LAST), price=Y" logs
   - File: `live_trading/brokers/ibkr_broker.py:70`

4. ✅ **Callbacks Firing?**
   - Check: No "Error in tickPrice callback" errors
   - File: `live_trading/brokers/ibkr_broker.py:85`

5. ✅ **Ticks Processed?**
   - Check: "Error scheduling tick processing" logs
   - File: `live_trading/engine/operation_runner.py:111`

6. ✅ **Bars Completed?**
   - Check: "Stored bar for operation" logs
   - File: `live_trading/data/data_manager.py:217`

7. ✅ **Database Writes?**
   - Check MongoDB `market_data` collection
   - Query: `db.market_data.find({operation_id: ObjectId("...")})`

## Key Files Reference

| File | Purpose | Key Methods |
|------|---------|-------------|
| `live_trading/api/main.py` | API endpoints | `create_operation()` |
| `live_trading/engine/trading_engine.py` | Orchestration | `start_operation()` |
| `live_trading/engine/operation_runner.py` | Operation lifecycle | `start()`, `broker_tick_callback()` |
| `live_trading/brokers/ibkr_broker.py` | IBKR integration | `subscribe_market_data()`, `tickPrice()`, `tickSize()` |
| `live_trading/data/data_manager.py` | Data processing | `handle_tick()`, `_process_completed_bar()` |
| `live_trading/data/data_manager.py` | Bar aggregation | `BarAggregator.add_tick()` |

