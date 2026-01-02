# Trading Strategies

Guide to developing and using trading strategies.

## Strategy Framework

All strategies inherit from `BaseForexStrategy` and implement:

```python
def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
    """Generate buy/sell signals."""
    # Add execute_buy and execute_sell columns
    df["execute_buy"] = ...
    df["execute_sell"] = ...
    return df
```

## Available Strategies

### Momentum Strategies

- **MomentumStrategy**: MACD and RSI-based momentum
- **TrendMomentumStrategy**: EMA crossover with trend confirmation

See [Momentum Strategies](strategy-examples.md#momentum-strategies) for details.

### Mean Reversion Strategies

- **BollingerBandsMeanReversion**: Price at bands + RSI confirmation
- **RSI2MeanReversion**: Simple RSI oversold/overbought

See [Mean Reversion Strategies](strategy-examples.md#mean-reversion-strategies) for details.

### Breakout Strategies

- **SupportResistanceBreakout**: Breakout above/below support/resistance
- **ATRBreakout**: ATR-based breakout levels

See [Breakout Strategies](strategy-examples.md#breakout-strategies) for details.

### Multi-Timeframe Strategies

- **AdaptiveMultiTimeframeStrategy**: Uses higher timeframes for trend confirmation

See [Multi-Timeframe Strategies](strategy-examples.md#multi-timeframe-strategies) for details.

### Pattern-Based Strategies

- **PatternStrategy**: Chart pattern detection (Head & Shoulders, etc.)
- **TriangleStrategy**: Triangle breakout detection
- **PatternTriangleStrategy**: Combined pattern + triangle with filters

See [Pattern Detection](patterns-triangles.md) for details.

### Adaptive Strategies

- **AdaptiveMultiIndicatorStrategy**: Combines multiple indicators based on market regime

## Strategy Testing

### Test All Strategies

```bash
python cli.py test-forex-strategies
```

### Test Specific Strategies

```bash
python cli.py test-forex-strategies --strategies "MomentumStrategy,RSIStrategy"
```

### Test on Specific Asset/Bar Size

```bash
python cli.py test-forex-strategies --asset USD-CAD --bar-size "1 hour"
```

### Multi-Timeframe Testing

The system automatically tests all valid higher timeframe combinations:

```bash
# Tests 5 mins with 15 mins, 1 hour, 4 hours, 1 day, 1 week
# Tests 15 mins with 1 hour, 4 hours, 1 day, 1 week
# etc.
python cli.py test-forex-strategies
```

## Strategy Development

### Creating a New Strategy

1. **Create strategy file** in `forex_strategies/`:

```python
from forex_strategies.base_strategy import BaseForexStrategy
import pandas as pd
import numpy as np

class MyStrategy(BaseForexStrategy):
    def __init__(self, initial_cash=10000, commission=0.0002):
        super().__init__(initial_cash, commission)
        self.name = "MyStrategy"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # Your logic here
        df["execute_buy"] = np.where(condition, df["close"], np.nan)
        df["execute_sell"] = np.where(condition, df["close"], np.nan)
        return df
```

2. **Register strategy** (automatic if in `forex_strategies/` folder)

3. **Test strategy**:
```bash
python cli.py test-forex-strategies --strategies "MyStrategy"
```

### Strategy Requirements

- Must inherit from `BaseForexStrategy`
- Must implement `generate_signals()` returning DataFrame with `execute_buy` and `execute_sell`
- `execute_buy` and `execute_sell` should contain price values (not just True/False)
- Can use any technical indicators from `TechnicalIndicators`

## Strategy Performance Metrics

When testing, strategies are evaluated on:

- **Return [%]**: Total return percentage
- **Sharpe Ratio**: Risk-adjusted return
- **Max Drawdown [%]**: Maximum peak-to-trough decline
- **Win Rate [%]**: Percentage of winning trades
- **# Trades**: Total number of trades
- **Avg Trade [%]**: Average profit per trade

Results are compared against a Buy & Hold baseline.

## Related Documentation

- [Strategy Examples](strategy-examples.md) - Example strategies with code
- [Pattern Detection](patterns-triangles.md) - Pattern-based strategies
- [Strategy Analysis](strategy-analysis.md) - Performance analysis
- [Backtesting Framework](architecture.md#strategy-framework) - How backtesting works

