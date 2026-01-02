# Broker Integration

Guide to setting up and using brokers (IBKR and OANDA) with the live trading system.

## IBKR Setup

### Prerequisites

1. **Install IBKR TWS or Gateway**:
   - Download from https://www.interactivebrokers.com/
   - TWS (Trader Workstation) or IB Gateway

2. **Configure API Access**:
   - Launch TWS/Gateway
   - Go to: Configure → Global Configuration → API → Settings
   - Check "Enable ActiveX and Socket Clients"
   - Set Socket port: **7497** (paper) or **7496** (live)
   - Add `127.0.0.1` to "Trusted IPs"

3. **Market Data Subscriptions**:
   - For delayed data (free): No subscription needed
   - For real-time data: Subscribe to required market data feeds
   - See [Alternative Data Sources](alternative-data-sources.md) for free alternatives

### Installation

Install the IBKR Python API:

```bash
pip install -e ./IBJts/source/pythonclient
```

### Configuration

In `.env`:
```env
BROKER_TYPE=IBKR
IBKR_HOST=127.0.0.1
IBKR_PORT=7497  # 7497 for paper, 7496 for live
IBKR_ACCOUNT_TYPE=PAPER  # PAPER or LIVE
```

### Market Data Type

The system requests **DELAYED** data by default (free, 15-20 min delay). If you receive REALTIME data, check TWS/Gateway settings:

1. TWS: Configure → Global Configuration → API → Settings
   - Uncheck "Enable ActiveX and Socket Clients" market data subscriptions
2. Gateway: Check market data subscriptions in settings

See [Real-Time Data Flow](data-flow.md) for details on how data flows.

## OANDA Setup

### Prerequisites

1. **Create OANDA Account**:
   - Sign up at https://www.oanda.com/
   - Create a practice account for paper trading

2. **Get API Credentials**:
   - Go to: Manage API Access
   - Generate API token
   - Note your Account ID

### Configuration

In `.env`:
```env
BROKER_TYPE=OANDA
OANDA_ACCESS_TOKEN=your_token
OANDA_ACCOUNT_ID=your_account_id
OANDA_ENVIRONMENT=practice  # practice or live
```

### Installation

OANDA API is included in requirements:
```bash
pip install oandapyV20
```

## Broker Comparison

| Feature | IBKR | OANDA |
|---------|------|-------|
| **Forex Data** | ✅ | ✅ |
| **Stocks/Crypto** | ✅ | ❌ |
| **Paper Trading** | ✅ | ✅ |
| **Real-time Data** | ✅ (subscription) | ✅ (free) |
| **Delayed Data** | ✅ (free) | ❌ |
| **API Complexity** | Medium | Low |
| **Market Data Fees** | Yes (real-time) | No (forex) |

## Switching Brokers

The system supports switching brokers via configuration:

1. Update `.env` with new broker settings
2. Restart the system
3. Existing operations will use the new broker

## Troubleshooting

### IBKR Connection Issues

- **"Waiting for connection"**: Verify TWS/Gateway is running and API is enabled
- **"Client ID already in use"**: System generates unique IDs automatically
- **"No security definition found"**: Check contract specification

See [Troubleshooting](../troubleshooting.md) for more issues.

### OANDA Connection Issues

- **Authentication errors**: Verify API token and Account ID
- **Permission errors**: Check account type (practice vs live)

## Related Documentation

- [Real-Time Data Flow](data-flow.md) - How data flows from brokers
- [Alternative Data Sources](alternative-data-sources.md) - Free data alternatives
- [Installation Guide](../installation.md) - Complete setup
- [Troubleshooting](../troubleshooting.md) - Common issues

