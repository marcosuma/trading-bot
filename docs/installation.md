# Installation Guide

Complete installation instructions for the Trading Bot.

## Prerequisites

- **Python 3.10+**: Required for all features
- **IBKR TWS/Gateway**: For market data and trading (see [Broker Setup](live-trading/brokers.md))
- **MongoDB**: For live trading system (local or Atlas)
- **Node.js 18+**: For frontend (optional, only for live trading UI)

## System Dependencies

### macOS

```bash
# Install TA-Lib and OpenMP (required for XGBoost/LightGBM)
brew install ta-lib libomp
```

### Linux (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install ta-lib libomp-dev
```

### Windows

1. Download TA-Lib from https://ta-lib.org/install/
2. Install OpenMP (usually included with Visual Studio Build Tools)

## Python Environment Setup

### 1. Create Virtual Environment

```bash
cd /path/to/trading-bot
python3 -m venv .venv
```

### 2. Activate Virtual Environment

**macOS/Linux**:
```bash
source .venv/bin/activate
```

**Windows**:
```bash
.venv\Scripts\activate
```

### 3. Install Python Dependencies

```bash
pip install --upgrade pip setuptools
pip install -r requirements.txt
```

### 4. Install IBKR API

```bash
# Install from local IBJts directory
pip install -e ./IBJts/source/pythonclient
```

### 5. Install Additional Dependencies (for live trading)

```bash
pip install -r live_trading/requirements.txt

# For MongoDB Atlas support
pip install "pymongo[srv]"
```

## IBKR Setup

1. **Download and Install**:
   - TWS (Trader Workstation) or IB Gateway
   - Available from https://www.interactivebrokers.com/

2. **Configure API Access**:
   - Launch TWS/Gateway
   - Go to: Configure → Global Configuration → API → Settings
   - Check "Enable ActiveX and Socket Clients"
   - Set Socket port: **7497** (paper) or **7496** (live)
   - Add `127.0.0.1` to "Trusted IPs"

3. **Market Data Subscriptions**:
   - For delayed data (free): No subscription needed
   - For real-time data: Subscribe to required market data feeds
   - See [Broker Integration](live-trading/brokers.md) for details

## MongoDB Setup

### Option 1: Local MongoDB

1. **Install MongoDB**:
   ```bash
   # macOS
   brew install mongodb-community

   # Linux
   sudo apt-get install mongodb

   # Windows: Download from https://www.mongodb.com/try/download/community
   ```

2. **Start MongoDB**:
   ```bash
   mongod
   ```

3. **Connection String**: `mongodb://localhost:27017`

### Option 2: MongoDB Atlas (Cloud)

1. Create account at https://www.mongodb.com/cloud/atlas
2. Create a free cluster
3. Create database user (Database Access)
4. Whitelist your IP (Network Access)
5. Get connection string (Database → Connect → Connect your application)
6. Connection string format: `mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`

See [Live Trading Setup](live-trading/README.md#mongodb-atlas-setup) for detailed steps.

## Environment Configuration

Create a `.env` file in the project root:

```env
# Optional: OANDA credentials (for OANDA trading)
OANDA_ACCESS_TOKEN=your_token
OANDA_ACCOUNT_ID=your_account_id

# MongoDB (for live trading)
MONGODB_URL=mongodb://localhost:27017
# Or for Atlas:
# MONGODB_URL=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
MONGODB_DB_NAME=trading_bot

# IBKR (for live trading)
IBKR_HOST=127.0.0.1
IBKR_PORT=7497  # 7497 for paper, 7496 for live
IBKR_ACCOUNT_TYPE=PAPER

# API Server (for live trading)
API_HOST=0.0.0.0
API_PORT=8000
SECRET_KEY=change-me-in-production

# Risk Management Defaults (for live trading)
DEFAULT_STOP_LOSS_TYPE=ATR
DEFAULT_STOP_LOSS_VALUE=1.5
DEFAULT_TAKE_PROFIT_TYPE=RISK_REWARD
DEFAULT_TAKE_PROFIT_VALUE=2.0
```

## Frontend Setup (Optional)

Only needed for the live trading web interface:

```bash
cd live_trading/frontend
npm install
```

See [Frontend Guide](live-trading/frontend.md) for details.

## Verification

### Test Backtesting System

```bash
python cli.py download-and-process
python cli.py test-forex-strategies --asset USD-CAD
```

### Test Live Trading System

```bash
# Start backend
python -m live_trading.main

# In another terminal, start frontend
cd live_trading/frontend
npm run dev
```

Access API at `http://localhost:8000` and frontend at `http://localhost:3000`.

## Troubleshooting

See [Troubleshooting Guide](troubleshooting.md) for common issues.

### Common Issues

- **TA-Lib import errors**: Ensure system library is installed before Python package
- **IBKR connection fails**: Verify TWS/Gateway is running and API is enabled
- **MongoDB connection fails**: Check connection string and IP whitelist (for Atlas)
- **XGBoost/LightGBM errors**: Install `libomp` (macOS: `brew install libomp`)

## Next Steps

- [Quick Start Guide](quick-start.md) - Get started quickly
- [Configuration](configuration.md) - Configure the system
- [Live Trading Setup](live-trading/README.md) - Set up live trading

