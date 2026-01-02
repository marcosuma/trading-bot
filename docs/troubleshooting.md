# Troubleshooting

Common issues and solutions.

## IBKR Connection Issues

### "Waiting for connection to server"

**Causes**:
- TWS/Gateway not running
- API not enabled
- Wrong port
- IP not whitelisted

**Solutions**:
1. Verify TWS/Gateway is running
2. Check API settings: Configure → Global Configuration → API → Settings
3. Verify port: 7497 (paper) or 7496 (live)
4. Add 127.0.0.1 to Trusted IPs

### "Client ID already in use"

**Cause**: Multiple connections using same client ID

**Solution**: The system now generates unique client IDs automatically. If issue persists, restart TWS/Gateway.

### "No security definition found" (Error 200)

**Cause**: Contract specification incorrect or pair not available

**Solution**:
- Verify contract format in `contracts.json`
- Check if pair is available on IBKR
- Verify exchange is correct (IDEALPRO for forex)

## Data Issues

### No data downloaded

**Causes**:
- IBKR connection failed
- Contract not found
- Market data subscription missing

**Solutions**:
1. Check IBKR connection logs
2. Verify contract in `contracts.json`
3. For real-time data: Check market data subscriptions
4. For delayed data: Should work without subscription

### Data file not found

**Cause**: Data not downloaded yet

**Solution**: Run `python cli.py download-and-process` first

## MongoDB Issues

### SSL handshake failed

**Cause**: IP not whitelisted in MongoDB Atlas

**Solution**:
1. Go to MongoDB Atlas → Network Access
2. Add your IP address (or 0.0.0.0/0 for development)
3. Wait a few minutes for changes to propagate

### Connection timeout

**Cause**: Wrong connection string or network issues

**Solution**:
1. Verify connection string format
2. Check username and password
3. Verify cluster is running (not paused)

## Python/Environment Issues

### TA-Lib import errors

**Cause**: System library not installed

**Solution**:
```bash
# macOS
brew install ta-lib
pip install TA-Lib

# Linux
sudo apt-get install ta-lib
pip install TA-Lib
```

### XGBoost/LightGBM errors (macOS)

**Cause**: Missing OpenMP library

**Solution**:
```bash
brew install libomp
pip install --upgrade xgboost lightgbm
```

### Module not found errors

**Cause**: Dependencies not installed

**Solution**:
```bash
pip install -r requirements.txt
pip install -r live_trading/requirements.txt
```

## Live Trading Issues

### No market data received

**Causes**:
- Broker not connected
- Market data not subscribed
- Contract not found

**Solutions**:
1. Check broker connection logs
2. Verify operation is active
3. Check [Real-Time Data Flow](live-trading/data-flow.md) documentation
4. Verify contract specification

### Operation not starting

**Causes**:
- Strategy not found
- Invalid configuration
- Database connection failed

**Solutions**:
1. Check operation logs
2. Verify strategy name exists
3. Check MongoDB connection
4. Review operation configuration

## Frontend Issues

### "Cannot GET /"

**Causes**:
- Dev server not running
- Wrong port
- Port conflict

**Solutions**:
1. Start dev server: `cd live_trading/frontend && npm run dev`
2. Check terminal for actual port
3. Access the URL shown in terminal

See [Frontend Troubleshooting](live-trading/frontend-troubleshooting.md) for details.

## Strategy Issues

### Strategy not found

**Cause**: Strategy not in registry

**Solution**: Ensure strategy file is in `forex_strategies/` and inherits from `BaseForexStrategy`

### Strategy returns 0% return

**Causes**:
- No signals generated
- Signals not in correct format
- Commission too high

**Solutions**:
1. Check if `execute_buy` and `execute_sell` columns contain price values
2. Verify signals are being generated
3. Check commission rate

## Getting More Help

- Check logs for detailed error messages
- Review relevant documentation sections
- Verify configuration files
- Test with minimal configuration first

## Related Documentation

- [Installation Guide](installation.md) - Setup instructions
- [Configuration](configuration.md) - Configuration options
- [Live Trading Troubleshooting](live-trading/frontend-troubleshooting.md) - Frontend issues

