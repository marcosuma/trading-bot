# Quick Start Guide

Get up and running with the Trading Bot in 5 minutes.

## Prerequisites

- Python 3.10+ installed
- IBKR TWS/Gateway running (for data)
- Virtual environment activated

## 1. Install Dependencies

```bash
# Install system dependencies (macOS)
brew install ta-lib libomp

# Install Python dependencies
pip install -r requirements.txt
pip install -e ./IBJts/source/pythonclient
```

## 2. Start IBKR TWS/Gateway

- Launch TWS or Gateway
- Enable API: Configure → Global Configuration → API → Settings
- Port: 7497 (paper) or 7496 (live)

## 3. Download Data

```bash
python cli.py download-and-process
```

This downloads historical data for all enabled contracts in `contracts.json`.

## 4. Test Strategies

```bash
python cli.py test-forex-strategies --asset USD-CAD
```

This tests all available strategies on USD-CAD data.

## 5. Interactive Mode

```bash
python cli.py
```

Then in the shell:
```
trading-bot> help
trading-bot> download-and-process
trading-bot> test-forex-strategies --asset USD-CAD --bar-size "1 hour"
trading-bot> exit
```

## Next Steps

- [Installation Guide](installation.md) - Complete setup instructions
- [CLI Reference](cli-reference.md) - All available commands
- [Strategies Guide](strategies.md) - Develop your own strategies
- [Live Trading](live-trading/README.md) - Set up live trading

