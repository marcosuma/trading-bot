# Configuration Guide

Configuration options for the Trading Bot.

## Environment Variables

Create a `.env` file in the project root. All variables are optional unless specified.

### OANDA Configuration

```env
OANDA_ACCESS_TOKEN=your_token
OANDA_ACCOUNT_ID=your_account_id
```

Required only if using OANDA for trading.

### MongoDB Configuration

```env
# Local MongoDB
MONGODB_URL=mongodb://localhost:27017

# MongoDB Atlas
MONGODB_URL=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority

MONGODB_DB_NAME=trading_bot
MONGODB_CONNECT_TIMEOUT_MS=30000
```

Required for live trading system.

### IBKR Configuration

```env
IBKR_HOST=127.0.0.1
IBKR_PORT=7497  # 7497 for paper, 7496 for live
IBKR_ACCOUNT_TYPE=PAPER  # PAPER or LIVE
IBKR_CLIENT_ID_PREFIX=live_trading_
```

Required for IBKR broker.

### API Server Configuration

```env
API_HOST=0.0.0.0
API_PORT=8000
SECRET_KEY=change-me-in-production
```

Required for live trading API.

### Risk Management Defaults

```env
DEFAULT_STOP_LOSS_TYPE=ATR  # ATR, PERCENTAGE, FIXED
DEFAULT_STOP_LOSS_VALUE=1.5
DEFAULT_TAKE_PROFIT_TYPE=RISK_REWARD  # RISK_REWARD, ATR, PERCENTAGE, FIXED
DEFAULT_TAKE_PROFIT_VALUE=2.0
DEFAULT_CRASH_RECOVERY_MODE=CLOSE_ALL  # CLOSE_ALL, RESUME, EMERGENCY_EXIT
DEFAULT_EMERGENCY_STOP_LOSS_PCT=0.05
DEFAULT_DATA_RETENTION_BARS=1000
```

### Logging

```env
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
JOURNAL_RETENTION_DAYS=90
```

### Debug Mode

```env
DEBUG=true  # Enable debug output
```

## Contracts Configuration

Edit `contracts.json` to control which instruments are processed:

```json
{
  "contracts": [
    {
      "contract": "USD,CAD,CASH,IDEALPRO",
      "enabled": true
    },
    {
      "contract": "EUR,USD,CASH,IDEALPRO",
      "enabled": false
    }
  ]
}
```

## CLI Configuration

Most settings can be overridden via command-line arguments. See [CLI Reference](cli-reference.md).

## Live Trading Configuration

See [Live Trading Configuration](live-trading/README.md#configuration) for live trading specific settings.

