# Trading Decision Flow

This document explains how the system decides whether to invest/trade or not.

## Overview

The trading decision flow follows this path:

1. **Market Data Reception** → 2. **Bar Completion** → 3. **Signal Generation** → 4. **Signal Handling** → 5. **Order Placement**

## Detailed Flow

### 1. Market Data Reception (`DataManager`)

- **Location**: `live_trading/data/data_manager.py`
- **Process**:
  - Receives real-time ticks from broker
  - Aggregates ticks into bars (1 min, 5 min, etc.)
  - When a bar completes, calls `_process_completed_bar()`
- **Logging**: `[SIGNAL_FLOW] Bar completed for operation...`

### 2. Bar Completion Callback (`OperationRunner`)

- **Location**: `live_trading/engine/operation_runner.py` → `_on_new_bar()`
- **Process**:
  - Receives completed bar data and indicators
  - Checks if operation is running
  - Passes data to `StrategyAdapter`
- **Logging**: `[SIGNAL_FLOW] New bar received for operation...`
- **Potential Issues**:
  - Operation not running → signals ignored
  - No strategy adapter → signals ignored

### 3. Signal Generation (`StrategyAdapter`)

- **Location**: `live_trading/strategies/strategy_adapter.py` → `on_new_bar()`
- **Process**:
  - **CRITICAL FILTER**: Only processes bars matching `primary_bar_size`
    - If bar_size != primary_bar_size → **signals are skipped**
  - Aligns data from multiple timeframes
  - Calls `strategy.generate_signals()` which:
    - Analyzes indicators (RSI, MACD, Bollinger Bands, etc.)
    - Sets `execute_buy` or `execute_sell` columns in DataFrame
  - Checks last row for signals:
    - `execute_buy` → triggers BUY signal
    - `execute_sell` → triggers SELL signal
- **Logging**:
  - `[SIGNAL_FLOW] StrategyAdapter.on_new_bar called...`
  - `[SIGNAL_FLOW] Signal check - execute_buy: X, execute_sell: Y`
  - `[SIGNAL_FLOW] ✅ BUY/SELL SIGNAL DETECTED!` (if signal found)
- **Potential Issues**:
  - Bar size mismatch → signals never generated
  - No aligned data → signals skipped
  - Strategy conditions not met → `execute_buy`/`execute_sell` remain NaN
  - Strategy error → exception logged

### 4. Signal Handling (`StrategyAdapter` → `OperationRunner`)

- **Location**:
  - `live_trading/strategies/strategy_adapter.py` → `_handle_signal()`
  - `live_trading/engine/operation_runner.py` → `_handle_signal()`
- **Process**:
  - StrategyAdapter calls signal callback
  - OperationRunner receives signal
  - Checks operation status (must be "active")
  - Calls `order_manager.place_order()`
- **Logging**:
  - `[SIGNAL_FLOW] StrategyAdapter._handle_signal called...`
  - `[SIGNAL_FLOW] OperationRunner._handle_signal called...`
  - `[SIGNAL_FLOW] ✅ Operation is active, placing order...`
- **Potential Issues**:
  - No callback set → signal lost
  - Operation status != "active" → order not placed

### 5. Order Placement (`OrderManager`)

- **Location**: `live_trading/orders/order_manager.py` → `place_order()`
- **Process**:
  - Validates operation exists
  - Determines order type (LIMIT vs MARKET)
  - Calculates stop loss and take profit
  - Places order with broker
  - Creates Order record in database
- **Logging**:
  - `[SIGNAL_FLOW] OrderManager.place_order called...`
  - `[SIGNAL_FLOW] ✅✅✅ ORDER PLACED SUCCESSFULLY!`
- **Potential Issues**:
  - Broker not connected → order fails
  - Invalid asset format → order fails
  - Calculation errors → order fails

## Common Reasons for No Trades

### 1. **Bar Size Mismatch** (Most Likely)
- **Symptom**: Bars are received but signals never generated
- **Check**: Look for `[SIGNAL_FLOW] Bar size X != primary Y, skipping`
- **Fix**: Ensure bar_size matches primary_bar_size in operation config

### 2. **Strategy Conditions Not Met**
- **Symptom**: Signals generated but `execute_buy`/`execute_sell` are NaN
- **Check**: Look for `[SIGNAL_FLOW] Signal check - execute_buy: nan, execute_sell: nan`
- **Fix**: Review strategy parameters - conditions may be too strict

### 3. **Operation Not Active**
- **Symptom**: Signals detected but orders not placed
- **Check**: Look for `[SIGNAL_FLOW] ⚠️ Operation status is 'paused'...`
- **Fix**: Ensure operation status is "active"

### 4. **No Aligned Data**
- **Symptom**: Signal generation skipped
- **Check**: Look for `[SIGNAL_FLOW] No aligned data available...`
- **Fix**: Ensure sufficient historical data exists for all timeframes

### 5. **Strategy Errors**
- **Symptom**: Exceptions during signal generation
- **Check**: Look for `[SIGNAL_FLOW] Error generating signals...`
- **Fix**: Check strategy implementation and required indicators

## Debugging Checklist

When no trades occur, check logs in this order:

1. ✅ **Are bars being received?**
   - Look for: `[SIGNAL_FLOW] Bar completed for operation...`
   - If missing: Check broker connection and market data subscription

2. ✅ **Is the bar size correct?**
   - Look for: `[SIGNAL_FLOW] Bar size X != primary Y, skipping`
   - If present: Fix bar_size configuration

3. ✅ **Is signal generation running?**
   - Look for: `[SIGNAL_FLOW] StrategyAdapter.on_new_bar called...`
   - If missing: Check operation is running and strategy adapter is set

4. ✅ **Are signals being generated?**
   - Look for: `[SIGNAL_FLOW] Signal check - execute_buy: X, execute_sell: Y`
   - If both are NaN: Strategy conditions not met (review strategy logic)

5. ✅ **Are signals being handled?**
   - Look for: `[SIGNAL_FLOW] ✅ BUY/SELL SIGNAL DETECTED!`
   - If missing: Signals not being generated

6. ✅ **Are orders being placed?**
   - Look for: `[SIGNAL_FLOW] ✅✅✅ ORDER PLACED SUCCESSFULLY!`
   - If missing: Check operation status and order manager

## Log Examples

### Successful Trade Flow
```
[SIGNAL_FLOW] Bar completed for operation 123, bar_size 5 mins, timestamp 2025-01-05, close 1.2345
[SIGNAL_FLOW] New bar received for operation 123, passing to strategy adapter
[SIGNAL_FLOW] StrategyAdapter.on_new_bar called: bar_size=5 mins, primary_bar_size=5 mins
[SIGNAL_FLOW] Primary bar size matched, proceeding with signal generation
[SIGNAL_FLOW] Aligned data available: 100 rows, columns: [...]
[SIGNAL_FLOW] Signal check - execute_buy: 1.2350, execute_sell: nan
[SIGNAL_FLOW] ✅ BUY SIGNAL DETECTED! Price: 1.2350
[SIGNAL_FLOW] StrategyAdapter._handle_signal called: BUY @ 1.2350
[SIGNAL_FLOW] OperationRunner._handle_signal called: BUY @ 1.2350
[SIGNAL_FLOW] ✅ Operation is active, placing order: BUY EUR-USD @ 1.2350
[SIGNAL_FLOW] OrderManager.place_order called: BUY EUR-USD @ 1.2350
[SIGNAL_FLOW] ✅✅✅ ORDER PLACED SUCCESSFULLY! Order ID: 456
```

### No Signal Generated (Normal)
```
[SIGNAL_FLOW] Bar completed for operation 123, bar_size 5 mins
[SIGNAL_FLOW] StrategyAdapter.on_new_bar called: bar_size=5 mins, primary_bar_size=5 mins
[SIGNAL_FLOW] Signal check - execute_buy: nan, execute_sell: nan
[SIGNAL_FLOW] No BUY signal (execute_buy is NaN or None)
[SIGNAL_FLOW] No SELL signal (execute_sell is NaN or None)
```

### Bar Size Mismatch (Issue)
```
[SIGNAL_FLOW] Bar completed for operation 123, bar_size 1 min
[SIGNAL_FLOW] StrategyAdapter.on_new_bar called: bar_size=1 min, primary_bar_size=5 mins
[SIGNAL_FLOW] Bar size 1 min != primary 5 mins, skipping signal generation
```

## Next Steps

With the enhanced logging, you should now see exactly where the flow stops. Check your logs for `[SIGNAL_FLOW]` entries to diagnose why no trades are occurring.

