# Live Trading System

A comprehensive live trading system for executing trading strategies in real-time.

## Features

- **Real-time Data Collection**: Collects and aggregates market data into bars
- **Multi-Timeframe Support**: Supports multiple bar sizes per operation
- **Strategy Integration**: Adapts backtesting strategies for live trading
- **Order Management**: Places orders with stop loss and take profit
- **Position Tracking**: Tracks open positions and calculates P/L
- **Crash Recovery**: Recovers from crashes with configurable recovery modes
- **REST API**: FastAPI-based REST API for operation management
- **MongoDB Storage**: Persistent storage using MongoDB with Beanie ODM
- **React Frontend**: Modern web interface for managing operations

## Architecture

See `LIVE_TRADING_ARCHITECTURE.md` in the project root for detailed architecture documentation.

## Setup

### Prerequisites

1. **MongoDB**:
   - **Local**: Install MongoDB locally
   - **Atlas**: Create a MongoDB Atlas account and cluster
2. **IBKR TWS/Gateway**: Install and configure (for IBKR broker)
3. **Python 3.10+**: With virtual environment
4. **Node.js 18+**: For frontend (optional)

### Installation

1. Create and activate a Python virtual environment:
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

2. Install Python dependencies:
```bash
pip install -r live_trading/requirements.txt
```

For MongoDB Atlas support (mongodb+srv://), you may also need:
```bash
python -m pip install "pymongo[srv]"
```

3. Install IBKR API (required for IBKR broker):
```bash
# Install from local IBJts directory
pip install -e ./IBJts/source/pythonclient
```

3. Install frontend dependencies (optional):
```bash
cd live_trading/frontend
npm install
```

3. Configure environment variables (create `.env` file in project root):
```env
# MongoDB Configuration
# For local MongoDB:
MONGODB_URL=mongodb://localhost:27017
# For MongoDB Atlas (uncomment and replace with your connection string):
# MONGODB_URL=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority

MONGODB_DB_NAME=trading_bot

# Broker Configuration
BROKER_TYPE=IBKR
IBKR_HOST=127.0.0.1
IBKR_PORT=7497  # 7497 for paper, 7496 for live
IBKR_ACCOUNT_TYPE=PAPER

# API Server
API_HOST=0.0.0.0
API_PORT=8000
SECRET_KEY=change-me-in-production

# Risk Management Defaults
DEFAULT_STOP_LOSS_TYPE=ATR
DEFAULT_STOP_LOSS_VALUE=1.5
DEFAULT_TAKE_PROFIT_TYPE=RISK_REWARD
DEFAULT_TAKE_PROFIT_VALUE=2.0
DEFAULT_CRASH_RECOVERY_MODE=CLOSE_ALL
DEFAULT_EMERGENCY_STOP_LOSS_PCT=0.05
DEFAULT_DATA_RETENTION_BARS=1000

# Logging
LOG_LEVEL=INFO
```

### MongoDB Atlas Setup

1. Create a MongoDB Atlas account at https://www.mongodb.com/cloud/atlas
2. Create a new cluster (free tier available)
3. Create a database user:
   - Go to "Database Access"
   - Add a new user with username and password
   - Grant "Atlas admin" or "Read and write to any database" role
4. Whitelist your IP address:
   - Go to "Network Access"
   - Add your current IP address (or 0.0.0.0/0 for development)
5. Get your connection string:
   - Go to "Database" → "Connect"
   - Choose "Connect your application"
   - Copy the connection string
   - Replace `<password>` with your database user password
   - Example: `mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`
6. Set `MONGODB_URL` in your `.env` file

### Running the System

1. Start MongoDB (if running locally):
```bash
mongod
```

2. Start IBKR TWS or Gateway

3. Start the backend API server:
```bash
python -m live_trading.main
```

The API will be available at `http://localhost:8000`

4. (Optional) Start the frontend:
```bash
cd live_trading/frontend
npm run dev
```

The frontend will be available at `http://localhost:3000`

## API Endpoints

### Operations

- `POST /api/operations` - Create a new trading operation
- `GET /api/operations` - List all operations
- `GET /api/operations/{id}` - Get operation details
- `DELETE /api/operations/{id}` - Stop an operation
- `POST /api/operations/{id}/pause` - Pause an operation
- `POST /api/operations/{id}/resume` - Resume an operation

### Positions

- `GET /api/operations/{id}/positions` - Get positions for an operation

### Transactions

- `GET /api/operations/{id}/transactions` - Get transactions for an operation

### Trades

- `GET /api/operations/{id}/trades` - Get completed trades for an operation

### Orders

- `GET /api/operations/{id}/orders` - Get orders for an operation

### Statistics

- `GET /api/operations/{id}/stats` - Get operation statistics
- `GET /api/stats/overall` - Get overall statistics

## Example: Creating an Operation

```bash
curl -X POST "http://localhost:8000/api/operations" \
  -H "Content-Type: application/json" \
  -d '{
    "asset": "USD-CAD",
    "bar_sizes": ["1 hour", "15 mins"],
    "primary_bar_size": "1 hour",
    "strategy_name": "MomentumStrategy",
    "strategy_config": {},
    "initial_capital": 10000,
    "stop_loss_type": "ATR",
    "stop_loss_value": 1.5,
    "take_profit_type": "RISK_REWARD",
    "take_profit_value": 2.0
  }'
```

## Crash Recovery

The system supports three crash recovery modes:

1. **CLOSE_ALL** (default for paper trading): Immediately closes all open positions on restart
2. **RESUME**: Resumes normal operation with emergency stop loss protection
3. **EMERGENCY_EXIT**: Closes positions only if unrealized loss exceeds threshold

Configure via `crash_recovery_mode` when creating an operation.

## Risk Management

### Stop Loss

- **ATR-based**: Stop loss = entry_price ± (stop_loss_value × ATR)
- **Percentage-based**: Stop loss = entry_price ± (stop_loss_value × entry_price)
- **Fixed**: Stop loss = stop_loss_value (absolute price)

### Take Profit

- **Risk-Reward**: Take profit based on risk-reward ratio (e.g., 1:2)
- **ATR-based**: Take profit = entry_price ± (take_profit_value × ATR)
- **Percentage-based**: Take profit = entry_price ± (take_profit_value × entry_price)
- **Fixed**: Take profit = take_profit_value (absolute price)

## Development

The system is designed to be modular and extensible. Key components:

- `live_trading/models/` - MongoDB models (Beanie ODM)
- `live_trading/brokers/` - Broker adapters (IBKR, OANDA)
- `live_trading/data/` - Data collection and bar aggregation
- `live_trading/strategies/` - Strategy adapter for live trading
- `live_trading/orders/` - Order management and position tracking
- `live_trading/engine/` - Trading engine and operation orchestration
- `live_trading/api/` - FastAPI REST API
- `live_trading/journal/` - Action logging and recovery
- `live_trading/frontend/` - React frontend application

## License

See project root LICENSE file.
