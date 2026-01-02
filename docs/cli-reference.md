# CLI Reference

Complete reference for all CLI commands.

## Interactive Mode

Run `python cli.py` without arguments to enter interactive mode:

```
trading-bot> help
trading-bot> <command> [options]
trading-bot> exit
```

## Commands

### download-and-process

Download historical data and process with indicators.

```bash
python cli.py download-and-process [options]
```

**Options**:
- `--include-1min`: Include 1-minute bars (limited to 2 months)
- `--force-refresh`: Re-download even if data exists
- `--bar-sizes`: Custom bar sizes (comma-separated, e.g., "1 day,1 hour")

**Examples**:
```bash
python cli.py download-and-process
python cli.py download-and-process --include-1min
python cli.py download-and-process --bar-sizes "1 day,1 hour,15 mins"
```

### fetch-process-plot

Fetch data, compute indicators, run strategies, and plot.

```bash
python cli.py fetch-process-plot [options]
```

**Options**:
- `--interval`: Time period (e.g., "6 M", "1 Y")
- `--bar-size`: Bar size (e.g., "1 hour", "15 mins")
- `--use-rsi`: Enable RSI strategy
- `--use-marsi`: Enable MARSI strategy
- `--use-hammer`: Enable Hammer/Shooting Star patterns
- `--use-support-resistance-v1`: Enable Support/Resistance V1
- `--use-support-resistance`: Enable Support/Resistance
- `--refresh`: Ignore cached data

### test-forex-strategies

Test and compare forex trading strategies.

```bash
python cli.py test-forex-strategies [options]
```

**Options**:
- `--asset`: Asset name (e.g., "USD-CAD"). If not provided, tests all assets
- `--bar-size`: Bar size (e.g., "1 hour"). If not provided, tests all bar sizes
- `--strategies`: Comma-separated list of strategy names (e.g., "MomentumStrategy,RSIStrategy"). If not provided, tests all strategies
- `--cash`: Initial capital (default: 10000)
- `--commission`: Commission rate (default: 0.0002)
- `--plot`: Plot the best performing configuration

**Examples**:
```bash
# Test all strategies on all assets
python cli.py test-forex-strategies

# Test specific strategies on specific asset
python cli.py test-forex-strategies --asset USD-CAD --strategies "MomentumStrategy"

# Test with custom capital and commission
python cli.py test-forex-strategies --cash 50000 --commission 0.0001
```

### train-extrema-predictor

Train ML model to predict local extrema.

```bash
python cli.py train-extrema-predictor [options]
```

**Options**:
- `--asset`: Asset name (e.g., "USD-CAD"). If not provided, uses all assets
- `--lookback-bars`: Number of previous bars to use (default: 20)
- `--test-size`: Test set size (default: 0.2)
- `--validation-size`: Validation set size (default: 0.1)
- `--model-type`: Model type: xgboost, lightgbm, ensemble (default: xgboost)
- `--use-feature-selection`: Enable automatic feature selection
- `--model-name`: Custom model name (default: extrema_predictor)

### train-price-direction-predictor

Train ML model to predict price direction.

```bash
python cli.py train-price-direction-predictor [options]
```

**Options**: Same as `train-extrema-predictor`

### train-volatility-predictor

Train ML model to predict volatility.

```bash
python cli.py train-volatility-predictor [options]
```

**Options**: Same as `train-extrema-predictor`

### train-trend-predictor

Train ML model to predict trend.

```bash
python cli.py train-trend-predictor [options]
```

**Options**: Same as `train-extrema-predictor`

## Getting Help

Use `--help` with any command:

```bash
python cli.py test-forex-strategies --help
```

## Related Documentation

- [Quick Start Guide](quick-start.md) - Get started quickly
- [Strategies Guide](strategies.md) - Strategy development
- [Machine Learning](machine-learning.md) - ML model training

