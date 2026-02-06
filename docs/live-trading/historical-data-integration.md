# Historical Data Integration

This document explains how historical data fetching was integrated into the live trading system.

## Problem

When a new trading operation was started, the system would immediately begin collecting real-time market data without any historical context. This meant:

1. Strategies had no historical data to analyze
2. Technical indicators couldn't be calculated (they need historical bars)
3. Trading decisions were delayed until enough real-time bars accumulated

## Solution

Historical data is now automatically fetched **before** subscribing to real-time data when an operation starts.

## Implementation

### 1. IBKR Broker Enhancement

Added `fetch_historical_data()` method to `IBKRBroker`:

```python
async def fetch_historical_data(
    self,
    asset: str,
    bar_size: str,
    interval: str,
    callback: Callable[[list, Dict], None],
    context: Optional[Dict] = None
) -> bool
```

**Features:**
- Converts asset format (USD-CAD) to IBKR contract
- Converts bar size format (e.g., "1 week" → "1 W")
- Requests historical data using `reqHistoricalData()`
- Uses callbacks to receive data asynchronously

### 2. IBKRWrapper Callbacks

Added historical data callbacks to `IBKRWrapper`:

- **`historicalData(reqId, bar)`**: Called for each historical bar received
  - Stores bars in `_historical_bars[reqId]`
  - Bar contains: date, open, high, low, close, volume

- **`historicalDataEnd(reqId, start, end)`**: Called when all data is received
  - Triggers user callback with all collected bars
  - Cleans up request tracking

### 3. Operation Runner Integration

Modified `OperationRunner.start()` to:

1. **Fetch historical data first** (before real-time subscription)
2. **Wait for all requests** to complete (with timeout)
3. **Store in database** using `MarketData` model
4. **Calculate indicators** for all historical bars
5. **Populate data buffers** so strategies can use it immediately
6. **Then subscribe** to real-time data

### 4. Data Flow

```
Operation Start
    ↓
Fetch Historical Data (for all bar sizes)
    ↓
Wait for IBKR callbacks (max 60 seconds)
    ↓
Convert bars to DataFrame
    ↓
Calculate indicators (SMA, EMA, RSI, MACD, etc.)
    ↓
Store in MongoDB (MarketData collection)
    ↓
Populate DataManager buffers
    ↓
Subscribe to real-time data
    ↓
Operation ready for trading
```

## Configuration

### Interval Selection

Historical data interval is automatically selected based on bar size:

- **1 min**: 1 month max
- **5 mins**: 1 year max
- **15 mins**: 1 year max
- **1 hour**: 1 year max
- **4 hours**: 1 year max
- **1 day**: 10 years max
- **1 week**: 10 years max

Default: 6 months if not specified

### Timeout

- Maximum wait time: 60 seconds per bar size
- If timeout occurs, operation still starts but with partial historical data

## Benefits

1. **Immediate Strategy Context**: Strategies have historical data from the start
2. **Complete Indicators**: All technical indicators are calculated immediately
3. **Better Decisions**: Trading decisions can be made on first real-time bar
4. **Database Persistence**: Historical data is stored for analysis and recovery

## Technical Details

### Threading Model

Historical data callbacks run in the IBKR API thread (synchronous). To integrate with async code:

```python
# In callback (synchronous, IBKR thread)
def historical_data_callback(bars, context):
    # Schedule async work in main event loop
    asyncio.run_coroutine_threadsafe(
        self._signal_historical_data_complete(bar_size, event),
        self.event_loop
    )
```

### Date Format Handling

IBKR returns dates in different formats:
- String: "20240101 12:00:00"
- Unix timestamp: 1704067200

The code handles both formats automatically.

### Indicator Calculation

Indicators are calculated for **all** historical bars, not just the latest. This ensures:
- Complete indicator history
- Proper indicator initialization
- Accurate strategy signals from the start

## Future Enhancements

1. **Configurable Interval**: Allow users to specify historical data period
2. **Incremental Updates**: Only fetch new data since last operation
3. **Caching**: Cache historical data to avoid redundant requests
4. **OANDA Support**: Add historical data fetching for OANDA broker

