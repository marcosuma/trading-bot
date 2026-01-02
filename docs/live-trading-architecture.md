# Live Trading System - Architecture Plan

## Overview
This document outlines the architecture and implementation plan for a live trading system that runs continuously, manages multiple trading operations, and provides a user interface for monitoring and control.

See [Live Trading System](live-trading/README.md) for setup and usage instructions.

## Requirements Summary

1. **Continuous Operation**: Run infinitely, cloud-preferred
2. **Multi-Operation Tracking**: Track multiple trades on different assets simultaneously
3. **Journal/Recovery**: Persistent journal of all actions for recovery
4. **User Interface**: View active/past trades, P/L per operation and overall
5. **Dynamic Trading**: Add new trading operations (asset, bar size, strategy)
6. **Manual Control**: Close any active trading at any time
7. **Broker Flexibility**: IBKR (paper) → OANDA (future), configurable for real accounts

---

## Architecture Overview

### High-Level Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Web UI (React/Vue)                       │
│              Real-time Dashboard & Controls                 │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP/WebSocket
┌───────────────────────┴─────────────────────────────────────┐
│              API Server (FastAPI/Flask)                     │
│  - REST API for CRUD operations                             │
│  - WebSocket for real-time updates                          │
│  - Authentication & Authorization                           │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────┴────────────────────────────────────┐
│            Trading Engine (Core Service)                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Strategy Manager                                   │   │
│  │  - Strategy execution with incremental data         │   │
│  │  - Signal generation                                │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Order Manager                                      │   │
│  │  - Order placement & tracking                       │   │
│  │  - Position management                              │   │
│  │  - Risk management                                  │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Data Manager                                       │   │
│  │  - Real-time data collection                        │   │
│  │  - Bar aggregation                                  │   │
│  │  - Indicator calculation                            │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Journal Manager                                    │   │
│  │  - Action logging                                   │   │
│  │  - State persistence                                │   │
│  │  - Recovery mechanism                               │   │
│  └─────────────────────────────────────────────────────┘   │
└───────────────────────┬────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
┌───────┴────────┐             ┌────────┴────────┐
│   Database     │             │  Broker APIs    │
│  (MongoDB)     │             │  - IBKR (now)   │
│  - Local/Atlas │             │  - OANDA (later)│
└────────────────┘             └─────────────────┘
```

---

## Technology Stack Recommendations

### Backend
- **API Framework**: **FastAPI** (modern, async, auto-docs, WebSocket support)
- **Database**: **MongoDB** (local for development, MongoDB Atlas for cloud)
- **ODM**: **Beanie** or **Motor** (async MongoDB drivers for Python)
- **Task Queue**: **Celery** with **Redis** (for async tasks, scheduled jobs)
- **Message Broker**: **Redis** (for pub/sub, caching)

### Frontend
- **Framework**: **React** (component-based, modern)
- **UI Library**: **Material-UI** or **Ant Design** (professional, feature-rich)
- **State Management**: **Redux** or **Zustand** (for complex state)
- **Real-time**: **WebSocket** or **Server-Sent Events (SSE)**
- **Charts**: **Chart.js** or **TradingView Lightweight Charts**
- **Build Tool**: **Vite** (fast, modern)

### Infrastructure
- **Cloud Provider**: **Google Cloud Platform (GCP)**
  - **Compute Engine**: VM instances for running the trading engine
  - **MongoDB Atlas**: Managed MongoDB (or self-hosted on Compute Engine)
  - **Cloud Memorystore**: Redis for caching and message broker
  - **Cloud Load Balancing**: For API server (if multiple instances)
  - **Cloud Monitoring**: For observability
- **Local Development**: Run directly on host machine (no Docker for IBKR API)
- **Process Management**:
  - **Local**: `systemd` (Linux), `launchd` (macOS), or **supervisord**
  - **GCP**: `systemd` on Compute Engine VMs
- **Deployment**:
  - **Local**: Direct Python execution
  - **GCP**: VM-based deployment (not containerized due to IBKR API requirements)
- **Monitoring**: **GCP Cloud Monitoring** + **Grafana** (optional)

### Python Libraries
- **FastAPI**: Web framework
- **Beanie** or **Motor**: MongoDB async ODM/ODM
- **Pydantic**: Data validation
- **Celery**: Task queue
- **Redis**: Caching & message broker
- **WebSockets**: Real-time communication
- **Pandas**: Data manipulation (already used)
- **Existing IBKR/OANDA clients**: Reuse current code

---

## Database Schema Design (MongoDB)

### Core Collections

```javascript
// Trading Operations (active and historical)
{
  _id: ObjectId,
  asset: String,  // e.g., "USD-CAD"
  bar_sizes: [String],  // e.g., ["1 hour", "15 mins", "1 day"] - MULTIPLE TIMEFRAMES
  primary_bar_size: String,  // Primary timeframe for entry/exit
  strategy_name: String,  // e.g., "MomentumStrategy"
  strategy_config: Object,  // Strategy parameters
  status: String,  // 'active', 'paused', 'closed', 'error'
  // Risk management config
  stop_loss_type: String,  // 'ATR', 'PERCENTAGE', 'FIXED' (default: 'ATR')
  stop_loss_value: Number,  // Value based on type (e.g., 1.5 for ATR multiplier, 0.02 for 2%)
  take_profit_type: String,  // 'ATR', 'PERCENTAGE', 'FIXED', 'RISK_REWARD' (default: 'RISK_REWARD')
  take_profit_value: Number,  // Value based on type (e.g., 2.0 for 1:2 risk-reward, 3.0x ATR, 0.04 for 4%)
  // Crash recovery config
  crash_recovery_mode: String,  // 'CLOSE_ALL', 'RESUME', 'EMERGENCY_EXIT' (default: 'CLOSE_ALL' for paper)
  emergency_stop_loss_pct: Number,  // Emergency exit threshold (e.g., 0.05 for 5%)
  // Data retention
  data_retention_bars: Number,  // Number of bars to keep per bar_size (default: 1000)
  created_at: ISODate,
  updated_at: ISODate,
  closed_at: ISODate,
  initial_capital: Number,
  current_capital: Number,
  total_pnl: Number,
  total_pnl_pct: Number
}

// Transactions (individual buy/sell operations - 1:N with trading_operations)
{
  _id: ObjectId,
  operation_id: ObjectId,  // Reference to trading_operations (1:N relationship)
  transaction_type: String,  // 'BUY' or 'SELL'
  transaction_role: String,  // 'ENTRY' or 'EXIT' - indicates if this opens or closes a position
  position_type: String,  // 'LONG' or 'SHORT' - type of position this transaction is part of
  order_id: ObjectId,  // Reference to orders
  price: Number,  // Execution price
  quantity: Number,  // Quantity executed (positive for BUY, negative for SELL, or always positive with sign in position_type)
  commission: Number,  // Commission paid
  executed_at: ISODate,  // When transaction was executed
  profit: Number,  // Profit for this transaction (0 for ENTRY, calculated for EXIT)
  profit_pct: Number,  // Profit percentage (0 for ENTRY, calculated for EXIT)
  // For EXIT transactions, link to corresponding ENTRY transaction
  related_entry_transaction_id: ObjectId,  // Reference to ENTRY transaction (for EXIT only)
  // Position context
  position_id: ObjectId,  // Reference to positions (if part of a position)
  notes: String  // Optional notes
}

// Positions (current open positions per operation)
{
  _id: ObjectId,
  operation_id: ObjectId,  // Reference to trading_operations
  contract_symbol: String,
  quantity: Number,  // Positive = long, Negative = short
  entry_price: Number,
  current_price: Number,
  unrealized_pnl: Number,
  unrealized_pnl_pct: Number,
  stop_loss: Number,
  take_profit: Number,
  opened_at: ISODate,
  closed_at: ISODate
}

// Orders (all orders placed)
{
  _id: ObjectId,
  operation_id: ObjectId,  // Reference to trading_operations
  broker_order_id: String,  // IBKR/OANDA order ID
  order_type: String,  // 'MARKET', 'LIMIT', 'STOP', etc.
  action: String,  // 'BUY', 'SELL'
  quantity: Number,
  price: Number,
  status: String,  // 'PENDING', 'FILLED', 'CANCELLED', 'REJECTED'
  filled_quantity: Number,
  avg_fill_price: Number,
  commission: Number,
  placed_at: ISODate,
  filled_at: ISODate,
  cancelled_at: ISODate
}

// Trades (completed round-trip trades - pairs of ENTRY and EXIT transactions)
{
  _id: ObjectId,
  operation_id: ObjectId,  // Reference to trading_operations
  position_type: String,  // 'LONG' or 'SHORT'
  entry_transaction_id: ObjectId,  // Reference to transactions (ENTRY: BUY for LONG, SELL for SHORT)
  exit_transaction_id: ObjectId,  // Reference to transactions (EXIT: SELL for LONG, BUY for SHORT)
  entry_price: Number,  // From entry transaction
  exit_price: Number,  // From exit transaction
  quantity: Number,  // Absolute quantity
  pnl: Number,  // Total profit/loss
  // For LONG: pnl = exit_price - entry_price
  // For SHORT: pnl = entry_price - exit_price
  pnl_pct: Number,  // Profit/loss percentage
  total_commission: Number,  // Sum of entry + exit commissions
  entry_time: ISODate,  // From entry transaction
  exit_time: ISODate,  // From exit transaction
  duration_seconds: Number
}

// Market Data (accumulated bars) - One collection per bar_size for efficiency
// Collection name: market_data_{bar_size} (e.g., market_data_1hour)
{
  _id: ObjectId,
  operation_id: ObjectId,  // Reference to trading_operations
  asset: String,
  bar_size: String,  // e.g., "1 hour", "15 mins"
  timestamp: ISODate,
  open: Number,
  high: Number,
  low: Number,
  close: Number,
  volume: Number,
  indicators: Object,  // Store calculated indicators as nested object
  // Index: {operation_id: 1, timestamp: 1} (unique)
}

// Journal (all actions for recovery)
{
  _id: ObjectId,
  operation_id: ObjectId,  // Reference to trading_operations
  action_type: String,  // 'SIGNAL_GENERATED', 'ORDER_PLACED', 'ORDER_FILLED', 'TRANSACTION_CREATED', etc.
  action_data: Object,  // Flexible object for action details
  timestamp: ISODate,
  sequence_number: Number  // For ordering and recovery
  // Index: {operation_id: 1, sequence_number: 1}
}

// Broker Configuration
{
  _id: ObjectId,
  broker_name: String,  // 'IBKR', 'OANDA'
  account_type: String,  // 'PAPER', 'LIVE'
  host: String,
  port: Number,
  client_id: Number,
  api_key: String,  // For OANDA
  account_id: String,
  is_active: Boolean,
  config: Object  // Additional broker-specific config
}
```

### MongoDB Indexes

```javascript
// trading_operations
db.trading_operations.createIndex({ status: 1, created_at: -1 })
db.trading_operations.createIndex({ asset: 1 })

// transactions (NEW - 1:N with trading_operations)
db.transactions.createIndex({ operation_id: 1, executed_at: -1 })
db.transactions.createIndex({ operation_id: 1, transaction_type: 1 })
db.transactions.createIndex({ operation_id: 1, transaction_role: 1 })  // ENTRY or EXIT
db.transactions.createIndex({ operation_id: 1, position_type: 1 })  // LONG or SHORT
db.transactions.createIndex({ related_entry_transaction_id: 1 })

// positions
db.positions.createIndex({ operation_id: 1, closed_at: 1 })
db.positions.createIndex({ operation_id: 1, status: 1 })  // if we add status field

// orders
db.orders.createIndex({ operation_id: 1, placed_at: -1 })
db.orders.createIndex({ broker_order_id: 1 }, { unique: true, sparse: true })

// trades
db.trades.createIndex({ operation_id: 1, exit_time: -1 })
db.trades.createIndex({ operation_id: 1, position_type: 1 })  // LONG or SHORT
db.trades.createIndex({ entry_transaction_id: 1 })
db.trades.createIndex({ exit_transaction_id: 1 })

// market_data (per bar_size collection)
db.market_data_1hour.createIndex({ operation_id: 1, timestamp: 1 }, { unique: true })
db.market_data_15mins.createIndex({ operation_id: 1, timestamp: 1 }, { unique: true })
// ... for each bar_size

// journal
db.journal.createIndex({ operation_id: 1, sequence_number: 1 })
db.journal.createIndex({ timestamp: -1 })
```

### Data Model Relationships

```
Trading Operation (1)
  ├── Transactions (N) - Each BUY/SELL operation with individual profit
  │     ├── Entry Transactions (BUY for LONG, SELL for SHORT) → profit = 0
  │     └── Exit Transactions (SELL for LONG, BUY for SHORT) → profit calculated, linked to entry
  ├── Trades (N) - Completed round-trips (entry-exit pairs)
  │     ├── LONG Trade: BUY (entry) → SELL (exit)
  │     └── SHORT Trade: SELL (entry) → BUY (exit)
  ├── Positions (N) - Current open positions
  │     ├── LONG Position: quantity > 0, opened with BUY
  │     └── SHORT Position: quantity < 0, opened with SELL
  ├── Orders (N) - All orders placed
  └── Market Data (N) - Accumulated bars per bar_size
```

**Key Points:**
- **Transactions** are the atomic units: each BUY or SELL is a transaction
- **Entry Transactions**: First transaction that opens a position (BUY for LONG, SELL for SHORT) → profit = 0
- **Exit Transactions**: Transaction that closes a position (SELL for LONG, BUY for SHORT) → profit calculated
- **Trades** are pairs of transactions (entry + exit) representing completed round-trips
- Exit transactions link back to their corresponding entry transaction via `related_entry_transaction_id`
- **LONG positions**: Opened with BUY, closed with SELL (profit = exit_price - entry_price)
- **SHORT positions**: Opened with SELL, closed with BUY (profit = entry_price - exit_price)
- Operations aggregate all transactions to calculate total P/L

---

## Key Components Design

### 1. Trading Engine

**Location**: `live_trading/engine/`

**Responsibilities**:
- Orchestrate all trading operations
- Manage lifecycle of trading operations
- Coordinate between data collection, strategy execution, and order management
- Handle recovery from journal

**Key Classes**:
```python
# live_trading/engine/trading_engine.py
class TradingEngine:
    def __init__(self, db_client, broker_adapter, journal_manager):
        self.db = db_client  # MongoDB client
        self.broker = broker_adapter
        self.journal = journal_manager
        self.active_operations = {}  # operation_id -> OperationRunner

    def start_operation(self, asset, bar_sizes, strategy_name, config):
        """Start a new trading operation with multiple bar sizes

        Args:
            asset: Asset symbol (e.g., "USD-CAD")
            bar_sizes: List of bar sizes (e.g., ["1 hour", "15 mins", "1 day"])
            strategy_name: Strategy class name
            config: Strategy configuration dict
        """

    def stop_operation(self, operation_id):
        """Stop an active trading operation"""

    def pause_operation(self, operation_id):
        """Pause an operation (keep data, stop trading)"""

    def resume_operation(self, operation_id):
        """Resume a paused operation"""

    def recover_from_journal(self):
        """Recover state from journal on startup

        Steps:
        1. Load all active operations from database
        2. Check for open positions (crashed positions) - positions with closed_at = null
        3. For each operation with open positions, apply crash recovery:
           - Call OrderManager.handle_crash_recovery() based on operation's crash_recovery_mode
           - CLOSE_ALL: Immediately close all open positions via market orders
           - RESUME: Resume monitoring, apply emergency stop loss if unrealized loss > threshold
           - EMERGENCY_EXIT: Close if unrealized loss > emergency_stop_loss_pct
        4. Reconstruct strategy state from last N bars (based on data_retention_bars)
        5. Resume data collection and trading
        6. Log all recovery actions to journal
        """
```

### 2. Data Manager

**Location**: `live_trading/data/`

**Responsibilities**:
- Collect real-time market data from broker
- Aggregate ticks into bars based on bar_size
- Calculate technical indicators incrementally
- Store bars in database

**Key Classes**:
```python
# live_trading/data/data_collector.py
class DataCollector:
    def __init__(self, broker_adapter, db_client):
        self.broker = broker_adapter
        self.db = db_client  # MongoDB client
        self.bar_buffers = {}  # (operation_id, bar_size) -> BarBuffer

    def subscribe_to_market_data(self, operation_id, asset, bar_sizes):
        """Subscribe to real-time data for an operation with multiple bar sizes

        Args:
            operation_id: Operation ID
            asset: Asset symbol
            bar_sizes: List of bar sizes to collect
        """

    def on_tick(self, operation_id, bar_size, tick_data):
        """Handle incoming tick data for a specific bar size"""

    def aggregate_bar(self, operation_id, bar_size, bar):
        """Aggregate tick data into complete bar for specific bar size"""

    def get_market_data(self, operation_id, bar_size, limit=1000):
        """Get recent market data for a bar size"""

# live_trading/data/bar_buffer.py
class BarBuffer:
    """Buffer for accumulating ticks into bars"""
    def add_tick(self, tick):
        """Add tick to buffer"""

    def is_bar_complete(self):
        """Check if current bar is complete"""

    def get_complete_bar(self):
        """Get completed bar and reset buffer"""
```

### 3. Strategy Adapter

**Location**: `live_trading/strategies/`

**Responsibilities**:
- Adapt existing backtesting strategies for live trading
- Handle incremental data (bars arrive one at a time)
- Generate signals from accumulated data
- Maintain strategy state

**Key Classes**:
```python
# live_trading/strategies/live_strategy_adapter.py
class LiveStrategyAdapter:
    """Adapter to make backtesting strategies work with live data"""
    def __init__(self, strategy_class, operation_id, bar_sizes, db_client):
        self.strategy = strategy_class
        self.operation_id = operation_id
        self.bar_sizes = bar_sizes  # List of bar sizes
        self.primary_bar_size = bar_sizes[0]  # Primary for entry/exit
        self.db = db_client  # MongoDB client
        self.data_buffers = {}  # bar_size -> list of bars

    def on_new_bar(self, bar_size, bar):
        """Called when a new complete bar arrives for a specific bar size"""
        # 1. Add bar to buffer for this bar_size
        # 2. Check if we have enough data for all required bar_sizes
        # 3. Calculate indicators for all timeframes
        # 4. Generate signals (strategy may use multiple timeframes)
        # 5. Return signals

    def get_current_dataframe(self, bar_size=None):
        """Get accumulated data as DataFrame for strategy

        Args:
            bar_size: Specific bar size, or None for primary
        """

    def align_timeframes(self):
        """Align data from multiple timeframes for multi-timeframe strategies"""

**Strategy Modifications Needed**:
- Strategies currently expect full DataFrame
- Need to work with incremental data
- Options:
  1. **Wrapper Approach**: Accumulate bars, convert to DataFrame when needed
  2. **Refactor Strategies**: Make strategies stateful, work incrementally
  3. **Hybrid**: Keep wrapper, but optimize for incremental updates

**Recommendation**: Start with Wrapper Approach (easiest), optimize later.

### 4. Order Manager

**Location**: `live_trading/orders/`

**Responsibilities**:
- Place orders through broker API
- Track order status
- Manage positions
- Calculate P/L
- Handle stop loss / take profit

**Key Classes**:
```python
# live_trading/orders/order_manager.py
class OrderManager:
    def __init__(self, broker_adapter, db_client, journal_manager):
        self.broker = broker_adapter
        self.db = db_client  # MongoDB client
        self.journal = journal_manager

    def place_order(self, operation_id, signal_type, price, quantity=None):
        """Place order based on strategy signal"""

    def on_order_filled(self, order_id, fill_data):
        """Handle order fill callback
        - Determine if this is an ENTRY or EXIT transaction
        - Determine position type (LONG or SHORT)
        - Create transaction record (BUY or SELL) with role (ENTRY/EXIT)
        - For ENTRY: profit = 0
        - For EXIT: Calculate profit based on related ENTRY transaction
          * LONG: profit = exit_price - entry_price
          * SHORT: profit = entry_price - exit_price
        - Link EXIT to corresponding ENTRY transaction
        - Create trade record if position is closed (ENTRY + EXIT pair)
        """

    def create_transaction(self, operation_id, order_id, transaction_type, transaction_role, position_type, price, quantity, commission):
        """Create a transaction record (BUY or SELL)

        Args:
            transaction_type: 'BUY' or 'SELL'
            transaction_role: 'ENTRY' or 'EXIT'
            position_type: 'LONG' or 'SHORT'

        For ENTRY transactions: profit = 0
        For EXIT transactions: Calculate profit based on related ENTRY transaction
          - LONG: profit = exit_price - entry_price
          - SHORT: profit = entry_price - exit_price
        """

    def update_positions(self, operation_id):
        """Update position P/L"""

    def handle_crash_recovery(self, operation_id):
        """Handle crash recovery for an operation with open positions

        Checks crash_recovery_mode and applies appropriate strategy:
        - CLOSE_ALL: Close all open positions immediately via market orders
        - RESUME: Resume normal operation, apply emergency stop loss if needed
        - EMERGENCY_EXIT: Close positions if unrealized loss > emergency_stop_loss_pct
        """

    def close_position(self, operation_id, position_id):
        """Manually close a position
        - Determines position type (LONG or SHORT)
        - Creates EXIT transaction:
          * LONG position → SELL transaction
          * SHORT position → BUY transaction
        - Links to ENTRY transaction
        - Calculates profit
        - Creates trade record (ENTRY + EXIT pair)
        """
```

### 5. Journal Manager

**Location**: `live_trading/journal/`

**Responsibilities**:
- Log all actions to database
- Enable state recovery
- Provide audit trail

**Key Classes**:
```python
# live_trading/journal/journal_manager.py
class JournalManager:
    def __init__(self, db_client):
        self.db = db_client  # MongoDB client

    def log_action(self, operation_id, action_type, data):
        """Log an action to journal"""

    def recover_operation_state(self, operation_id):
        """Recover operation state from journal"""

    def get_operation_history(self, operation_id):
        """Get all actions for an operation"""
```

### 6. Broker Adapter (Abstract Interface)

**Location**: `live_trading/brokers/`

**Responsibilities**:
- Abstract broker-specific APIs
- Enable switching between IBKR and OANDA
- Handle connection management
- Provide unified interface

**Key Classes**:
```python
# live_trading/brokers/base_broker.py
class BaseBroker(ABC):
    @abstractmethod
    def connect(self):
        """Connect to broker"""

    @abstractmethod
    def subscribe_market_data(self, asset, callback):
        """Subscribe to real-time market data"""

    @abstractmethod
    def place_order(self, order_data):
        """Place an order"""

    @abstractmethod
    def get_positions(self):
        """Get current positions"""

# live_trading/brokers/ibkr_broker.py
class IBKRBroker(BaseBroker):
    """IBKR implementation"""
    # Reuse existing ib_api_client code

# live_trading/brokers/oanda_broker.py
class OANDABroker(BaseBroker):
    """OANDA implementation"""
    # Implement OANDA API wrapper
```

---

## Data Flow

### Starting a New Trading Operation

```
1. User creates operation via API
   POST /api/operations
   {
     "asset": "USD-CAD",
     "bar_size": "1 hour",
     "strategy": "MomentumStrategy",
     "config": {...}
   }

2. API Server → Trading Engine
   - Create operation record in DB
   - Initialize OperationRunner

3. Trading Engine → Data Collector
   - Subscribe to market data for asset
   - Start bar aggregation

4. Data Collector → Broker
   - Request real-time market data stream
   - Receive ticks

5. Data Collector (on complete bar)
   - Aggregate ticks → complete bar
   - Calculate indicators
   - Store bar in DB
   - Notify Strategy Adapter

6. Strategy Adapter
   - Receive new bar
   - Update data buffer
   - Generate signals
   - If signal → Order Manager

7. Order Manager
   - Place order via Broker (with stop loss and take profit if configured)
   - Calculate stop loss/take profit based on operation config (ATR, percentage, risk-reward)
   - Log to journal
   - When order fills:
     * Create transaction record (BUY or SELL, ENTRY or EXIT)
     * For ENTRY: profit = 0
     * For EXIT: Calculate profit, link to ENTRY transaction
     * Create trade record if position closes (ENTRY + EXIT pair)
   - Update positions
   - Monitor stop loss/take profit levels
```

### Real-time Updates to UI

```
1. Trading Engine → Journal Manager
   - Log all actions

2. Journal Manager → Database
   - Store action

3. API Server (WebSocket)
   - Monitor journal/positions for changes
   - Push updates to connected clients

4. Frontend
   - Receive WebSocket updates
   - Update UI in real-time
```

---

## Recovery Mechanism

### On Startup

1. **Load Active Operations**: Query DB for operations with status='active'
2. **Detect Crashed Positions**: Find all positions with `closed_at = null` (open positions)
3. **Apply Crash Recovery Strategy**: For each operation with open positions:
   - Check `crash_recovery_mode`:
     - **CLOSE_ALL**: Immediately place market orders to close all positions
     - **RESUME**: Resume monitoring, apply emergency stop loss if needed
     - **EMERGENCY_EXIT**: Close positions if `unrealized_pnl_pct > emergency_stop_loss_pct`
   - Log recovery action to journal
4. **Recover State**: For each operation:
   - Load last N bars from market_data (based on `data_retention_bars`)
   - Reconstruct strategy state
   - Load open positions (after recovery actions)
   - Resume data collection
5. **Replay Journal** (optional): Replay recent journal entries to ensure consistency

### On Crash

- All state is in database (operations, positions, orders, transactions)
- Journal has complete action log
- Open positions are preserved in database
- On restart:
  1. Detect open positions from crashed session
  2. Apply configured crash recovery strategy
  3. Resume normal operation or close positions based on strategy

### Crash Recovery Modes

**CLOSE_ALL** (Default for paper trading):
- Safest option
- Immediately closes all open positions on restart
- Prevents exposure to market movements during downtime
- Use when: Testing, paper trading, or when you want maximum safety

**RESUME** (For live trading):
- Resumes normal operation
- Applies emergency stop loss if position risk is too high
- Continues strategy execution
- Use when: You have confidence in the system and want to continue trading

**EMERGENCY_EXIT** (Balanced approach):
- Only closes positions if unrealized loss exceeds threshold
- Allows profitable positions to continue
- Protects against catastrophic losses
- Use when: You want protection but also want to preserve good positions

---

## API Endpoints Design

### Operations Management
```
GET    /api/operations              # List all operations
POST   /api/operations              # Create new operation
GET    /api/operations/{id}         # Get operation details
PUT    /api/operations/{id}         # Update operation
DELETE /api/operations/{id}          # Close/delete operation
POST   /api/operations/{id}/pause    # Pause operation
POST   /api/operations/{id}/resume   # Resume operation
```

### Positions & Transactions
```
GET    /api/operations/{id}/positions      # Get positions for operation
POST   /api/positions/{id}/close           # Manually close position
GET    /api/operations/{id}/transactions   # Get transaction history (all buy/sell)
GET    /api/operations/{id}/trades         # Get completed trades (buy-sell pairs)
GET    /api/operations/{id}/orders         # Get order history
```

### Statistics
```
GET    /api/operations/{id}/stats      # Get operation statistics
GET    /api/stats/overall               # Overall P/L stats
```

### WebSocket
```
WS     /ws/operations/{id}              # Real-time updates for operation
WS     /ws/overall                      # Overall updates
```

---

## Frontend UI Structure

### Pages/Views

1. **Dashboard** (Home)
   - Overall P/L summary
   - Active operations count
   - Recent trades
   - System status

2. **Operations List**
   - Table of all operations (active + historical)
   - Filters: status, asset, strategy
   - Quick actions: pause, resume, close

3. **Operation Detail**
   - Operation info
   - Current positions
   - Trade history
   - Performance charts
   - Real-time price chart
   - Manual controls (close position, pause, etc.)

4. **Create Operation**
   - Form: asset, bar size, strategy, config
   - Strategy parameter inputs
   - Preview/validation

5. **Settings**
   - Broker configuration
   - Account settings
   - Risk management settings

---

## Implementation Phases

**Note**: All trading features in initial phase, but running locally first.

### Phase 1: Core Infrastructure (Week 1-2)
- [ ] MongoDB schema design & setup (local)
- [ ] MongoDB connection & models (Beanie/Motor)
- [ ] Basic API server (FastAPI)
- [ ] Broker adapter interface
- [ ] IBKR broker implementation
- [ ] Journal manager
- [ ] Basic recovery mechanism
- [ ] Local development setup (no Docker)

### Phase 2: Data Collection with Multiple Timeframes (Week 2-3)
- [ ] Real-time data collection from IBKR
- [ ] Bar aggregation logic for multiple bar sizes
- [ ] Multiple bar size subscription management
- [ ] Incremental indicator calculation per timeframe
- [ ] MongoDB storage (collections per bar_size)
- [ ] Data alignment for multi-timeframe strategies

### Phase 3: Strategy Integration (Week 3-4)
- [ ] Live strategy adapter with multi-timeframe support
- [ ] Adapt existing strategies (especially multi-timeframe)
- [ ] Signal generation from live data (all timeframes)
- [ ] Strategy state management
- [ ] Testing with paper account

### Phase 4: Order Management (Week 4-5)
- [ ] Order manager
- [ ] Position tracking
- [ ] P/L calculation
- [ ] Manual position closing
- [ ] Risk management checks

### Phase 5: API & Frontend (Week 5-6)
- [ ] Complete REST API (all endpoints)
- [ ] WebSocket for real-time updates
- [ ] React frontend setup (Vite)
- [ ] Frontend UI components
- [ ] Dashboard with multi-timeframe support
- [ ] Operation management UI
- [ ] Position & trade history UI

### Phase 6: Local Testing & Refinement (Week 6-7)
- [ ] End-to-end testing locally
- [ ] Error handling & recovery
- [ ] Monitoring & logging
- [ ] Performance optimization
- [ ] Documentation
- [ ] Bug fixes

### Phase 7: GCP Deployment (Week 7-8)
- [ ] GCP project setup
- [ ] Compute Engine VM configuration
- [ ] MongoDB Atlas setup (or self-hosted on VM)
- [ ] Redis setup (Cloud Memorystore or VM)
- [ ] Deployment scripts
- [ ] Monitoring setup (GCP Cloud Monitoring)
- [ ] Production testing

---

## Configuration Management

### Environment Variables
```bash
# Database (MongoDB)
MONGODB_URL=mongodb://localhost:27017/trading_bot  # Local
# MONGODB_URL=mongodb+srv://user:pass@cluster.mongodb.net/trading_bot  # Atlas
MONGODB_DB_NAME=trading_bot

# Broker
BROKER_TYPE=IBKR  # or OANDA
IBKR_HOST=127.0.0.1
IBKR_PORT=7497  # 7497 for paper, 7496 for live
IBKR_CLIENT_ID=1
IBKR_ACCOUNT_TYPE=PAPER  # or LIVE

# OANDA (future)
OANDA_API_KEY=...
OANDA_ACCOUNT_ID=...
OANDA_ENVIRONMENT=PRACTICE  # or LIVE

# API
API_HOST=0.0.0.0
API_PORT=8000
SECRET_KEY=...

# Redis (for Celery)
REDIS_URL=redis://localhost:6379/0

# GCP (for cloud deployment)
GCP_PROJECT_ID=your-project-id
GCP_ZONE=us-central1-a
```

### Configuration File (config.yaml)
```yaml
broker:
  type: IBKR
  ibkr:
    host: 127.0.0.1
    port: 7497  # 7497 for paper, 7496 for live
    account_type: PAPER
  oanda:
    api_key: ${OANDA_API_KEY}
    account_id: ${OANDA_ACCOUNT_ID}
    environment: PRACTICE

database:
  mongodb:
    url: ${MONGODB_URL}
    db_name: trading_bot
    # Connection pool settings
    max_pool_size: 50
    min_pool_size: 10

risk_management:
  max_position_size: 10000
  max_daily_loss: 500
  # Stop Loss Configuration (defaults, can be overridden per operation)
  default_stop_loss_type: ATR  # 'ATR', 'PERCENTAGE', 'FIXED'
  default_stop_loss_value: 1.5  # 1.5x ATR (if ATR type), or 0.02 for 2% (if PERCENTAGE)
  # Take Profit Configuration (defaults, can be overridden per operation)
  default_take_profit_type: RISK_REWARD  # 'ATR', 'PERCENTAGE', 'FIXED', 'RISK_REWARD'
  default_take_profit_value: 2.0  # 2.0 for 1:2 risk-reward (if RISK_REWARD), or 3.0x ATR (if ATR)
  # Crash Recovery
  default_crash_recovery_mode: CLOSE_ALL  # 'CLOSE_ALL', 'RESUME', 'EMERGENCY_EXIT'
  default_emergency_stop_loss_pct: 0.05  # 5% unrealized loss threshold for EMERGENCY_EXIT
  # Data Retention
  default_data_retention_bars: 1000  # Number of bars to keep per bar_size

logging:
  level: INFO
  journal_retention_days: 90

deployment:
  mode: local  # or 'gcp'
  gcp:
    project_id: ${GCP_PROJECT_ID}
    zone: us-central1-a
    instance_name: trading-engine-vm
```

---

## Security Considerations

1. **Authentication**: JWT tokens for API access
2. **Authorization**: Role-based access (admin, trader, viewer)
3. **API Keys**: Secure storage (environment variables, secrets manager)
4. **Database**: Encrypted connections, parameterized queries
5. **Input Validation**: Pydantic models for all inputs
6. **Rate Limiting**: Prevent API abuse
7. **Audit Logging**: All actions logged with user info

---

## Monitoring & Observability

1. **Health Checks**: `/health` endpoint
2. **Metrics**:
   - Operation count
   - Active positions
   - P/L trends
   - API response times
   - Error rates
3. **Logging**: Structured logging (JSON)
4. **Alerts**: Email/Slack for critical errors
5. **Dashboard**: Grafana for metrics visualization

---

## Testing Strategy

1. **Unit Tests**: Each component in isolation
2. **Integration Tests**: Component interactions
3. **Paper Trading**: Test with IBKR paper account
4. **Mock Broker**: Simulate broker responses for testing
5. **Recovery Tests**: Simulate crashes, test recovery

---

## Future Enhancements

1. **OANDA Integration**: Full OANDA broker support
2. **Multi-Broker**: Trade same strategy on multiple brokers
3. **Advanced Risk Management**: Portfolio-level risk limits
4. **Backtesting Integration**: Compare live vs backtested performance
5. **ML Integration**: Use ML predictions in strategies
6. **Mobile App**: React Native app for monitoring
7. **Alerts**: Email/SMS notifications for trades, errors
8. **Strategy Marketplace**: Share/import strategies

---

## IBKR API & Docker Considerations

### Why Docker May Not Work

IBKR's TWS (Trader Workstation) or IB Gateway requires:
1. **Desktop Application**: TWS/IB Gateway is a desktop application that needs to run on the host
2. **Network Connection**: The API connects via localhost (127.0.0.1) to TWS/IB Gateway
3. **Port Binding**: Requires specific ports (7497 for paper, 7496 for live)
4. **GUI Dependency**: While IB Gateway can run headless, it's still a native application

### Alternatives to Docker

1. **Direct Host Execution** (Recommended for local)
   - Run Python application directly on host
   - TWS/IB Gateway runs on same machine
   - Use `systemd` (Linux) or `launchd` (macOS) for process management
   - **Pros**: Simple, no containerization issues
   - **Cons**: Less isolation

2. **GCP Compute Engine VM** (For cloud)
   - Deploy as VM instance (not container)
   - Install TWS/IB Gateway on VM
   - Run application on VM
   - Use `systemd` for service management
   - **Pros**: Full control, cloud benefits
   - **Cons**: More setup, VM management

3. **Hybrid Approach**
   - Frontend/API in containers (if needed)
   - Trading engine on VM/host (for IBKR)
   - MongoDB Atlas (managed)
   - **Pros**: Best of both worlds
   - **Cons**: More complex architecture

### Process Management Options

**Local Development:**
- **macOS**: `launchd` (LaunchAgent/LaunchDaemon)
- **Linux**: `systemd` (service files)
- **Windows**: Task Scheduler or NSSM

**GCP Deployment:**
- **Compute Engine**: `systemd` service files
- **Cloud Run**: Not suitable (containerized, no TWS)
- **GKE**: Possible but complex (need to run TWS in pod)

### Recommended Setup

**Local:**
```bash
# Run TWS/IB Gateway manually or via launchd/systemd
# Run trading engine as Python process
python -m live_trading.main
```

**GCP:**
```bash
# Create VM instance
# Install TWS/IB Gateway on VM
# Install Python application
# Create systemd service
# Auto-start on boot
```

## Questions to Consider

1. **Bar Size Handling**: ✅ **RESOLVED** - Multiple bar sizes per operation supported

2. **Strategy State**: How much state should strategies maintain?
   - ✅ **DECISION**: Keep strategies stateless, maintain state in adapter
   - **Implementation**: Strategy adapter maintains accumulated data buffers and state

3. **Data Retention**: How long to keep market data?
   - ✅ **DECISION**: Keep last N bars per bar_size (configurable, e.g., 1000), archive older
   - **Implementation**: MongoDB TTL indexes can auto-delete old data
   - **Configuration**: Add `data_retention_bars` setting (default: 1000)

4. **Order Execution**: Market orders only, or support limit/stop orders?
   - ✅ **DECISION**: Support limit/stop orders from the start
   - **Stop Loss Recommendations**:
     - **ATR-based**: 1.5x to 2x ATR from entry price (most common)
     - **Percentage-based**: 1-2% of entry price for forex (conservative), 2-3% (moderate)
     - **Support/Resistance**: Place stop below support (LONG) or above resistance (SHORT)
   - **Take Profit Recommendations**:
     - **Risk-Reward Ratio**: 1:2 or 1:3 (take profit = 2x or 3x stop loss distance)
     - **ATR-based**: 2x to 3x ATR from entry price
     - **Percentage-based**: 2-4% of entry price for forex
   - **Implementation**:
     - Add `stop_loss_type` (ATR, PERCENTAGE, FIXED) and `stop_loss_value`
     - Add `take_profit_type` (ATR, PERCENTAGE, FIXED, RISK_REWARD) and `take_profit_value`
     - Default: ATR-based with 1.5x ATR stop, 3x ATR take profit (1:2 risk-reward)

5. **Position Sizing**: Fixed size or dynamic based on strategy/risk?
   - ✅ **DECISION**: Start with fixed, add dynamic sizing later
   - **Implementation**: Fixed quantity per operation, configurable per operation

6. **Multi-Timeframe Data Synchronization**: How to handle when different bar_sizes complete at different times?
   - ✅ **DECISION**:
     - Primary bar_size triggers signal generation
     - Other timeframes use most recent available bar
     - Strategy adapter handles alignment
   - **Implementation**: Strategy adapter checks if primary bar_size has new data, then aligns other timeframes using most recent available bars

7. **Crash Recovery with Open Positions**: What to do when program crashes with open positions?
   - ✅ **DECISION**: Implement multiple recovery strategies with configurable behavior
   - **Recommended Approaches** (based on industry best practices):
     1. **Immediate Close on Restart** (Safest - Default for paper trading):
        - On startup, detect open positions from crashed session
        - Immediately place market orders to close all open positions
        - Log recovery action to journal
        - Prevents exposure to market movements during downtime
     2. **Resume with Monitoring** (For live trading with confidence):
        - On startup, detect open positions
        - Resume monitoring and strategy execution
        - Apply emergency stop loss if position is beyond acceptable risk
        - Continue normal operation
     3. **Emergency Exit Mode** (Configurable):
        - Configuration option: `crash_recovery_mode` ('CLOSE_ALL', 'RESUME', 'EMERGENCY_EXIT')
        - Emergency exit: Close positions if unrealized loss exceeds threshold
        - Send alerts/notifications about recovered positions
   - **Implementation**:
     - Add `crash_recovery_mode` to operation config (default: 'CLOSE_ALL' for paper, 'RESUME' for live)
     - Add `emergency_stop_loss_pct` threshold (e.g., 5% unrealized loss)
     - On startup, check for positions with `closed_at = null`
     - Apply recovery strategy based on mode
     - Log all recovery actions to journal
   - **Best Practice**: For paper trading, default to closing all positions. For live trading, allow resume but with emergency stop loss protection.

---

## Local Development Setup

### Prerequisites
1. **MongoDB**: Install locally or use MongoDB Atlas
2. **Redis**: Install locally (for Celery, optional initially)
3. **IBKR TWS/IB Gateway**: Install and configure
4. **Python 3.10+**: With virtual environment
5. **Node.js 18+**: For React frontend

### Project Structure
```
live_trading/
├── api/                    # FastAPI application
│   ├── main.py
│   ├── routes/
│   ├── models/
│   └── websocket/
├── engine/                 # Trading engine
│   ├── trading_engine.py
│   └── operation_runner.py
├── data/                   # Data collection
│   ├── data_collector.py
│   ├── bar_buffer.py
│   └── indicator_calculator.py
├── strategies/             # Strategy adapters
│   ├── live_strategy_adapter.py
│   └── multi_timeframe_adapter.py
├── orders/                 # Order management
│   ├── order_manager.py
│   └── position_manager.py
├── brokers/                # Broker adapters
│   ├── base_broker.py
│   ├── ibkr_broker.py
│   └── oanda_broker.py
├── journal/                # Journal management
│   └── journal_manager.py
├── models/                 # MongoDB models (Beanie)
│   ├── operation.py
│   ├── position.py
│   ├── order.py
│   ├── transaction.py      # Individual buy/sell transactions (1:N with operations)
│   └── trade.py            # Completed trades (buy-sell pairs)
├── config/                 # Configuration
│   └── settings.py
└── main.py                 # Entry point

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   ├── services/
│   └── App.jsx
├── package.json
└── vite.config.js
```

### Running Locally

**Terminal 1 - IBKR Gateway:**
```bash
# Start IB Gateway (paper trading)
# Or run TWS manually
```

**Terminal 2 - Trading Engine:**
```bash
cd live_trading
python -m live_trading.main
```

**Terminal 3 - API Server:**
```bash
cd live_trading
uvicorn api.main:app --reload --port 8000
```

**Terminal 4 - Frontend:**
```bash
cd frontend
npm run dev
```

## Next Steps

1. **Review & Approve Plan**: Discuss and refine architecture
2. **Set Up Project Structure**: Create directories, initial files
3. **Install Dependencies**: MongoDB, Redis, Python packages, Node packages
4. **Start Phase 1**: Begin core infrastructure implementation
5. **Local Testing**: Test all components locally before GCP deployment

---

## References

- Existing codebase structure
- IBKR API documentation
- OANDA API documentation
- FastAPI documentation
- SQLAlchemy documentation

