# Strategy Examples

Example trading strategies with code.

## Momentum Strategies

### MomentumStrategy

Uses MACD and RSI for momentum signals.

```python
from forex_strategies.momentum_strategy import MomentumStrategy

strategy = MomentumStrategy()
```

### TrendMomentumStrategy

EMA crossover with trend confirmation.

```python
from forex_strategies.momentum_strategy import TrendMomentumStrategy

strategy = TrendMomentumStrategy()
```

## Mean Reversion Strategies

### BollingerBandsMeanReversion

Price at bands + RSI confirmation.

```python
from forex_strategies.mean_reversion_strategy import BollingerBandsMeanReversion

strategy = BollingerBandsMeanReversion(
    rsi_oversold=30,
    rsi_overbought=70
)
```

### RSI2MeanReversion

Simple RSI oversold/overbought.

```python
from forex_strategies.mean_reversion_strategy import RSI2MeanReversion

strategy = RSI2MeanReversion()
```

## Breakout Strategies

### SupportResistanceBreakout

Breakout above/below support/resistance.

```python
from forex_strategies.breakout_strategy import SupportResistanceBreakout

strategy = SupportResistanceBreakout(
    lookback_period=20,
    breakout_threshold=0.001
)
```

### ATRBreakout

ATR-based breakout levels.

```python
from forex_strategies.breakout_strategy import ATRBreakout

strategy = ATRBreakout(
    lookback_period=20,
    atr_multiplier=1.5
)
```

## Multi-Timeframe Strategies

### AdaptiveMultiTimeframeStrategy

Uses higher timeframes for trend confirmation.

```python
from forex_strategies.multi_timeframe_strategy import AdaptiveMultiTimeframeStrategy

strategy = AdaptiveMultiTimeframeStrategy(
    lower_timeframe="15 mins",
    higher_timeframe="1 hour"
)
```

## Pattern-Based Strategies

### PatternStrategy

Chart pattern detection.

```python
from forex_strategies.pattern_strategy import PatternStrategy

strategy = PatternStrategy()
```

### TriangleStrategy

Triangle breakout detection.

```python
from forex_strategies.triangle_strategy import TriangleStrategy

strategy = TriangleStrategy()
```

### PatternTriangleStrategy

Combined pattern + triangle with filters.

```python
from forex_strategies.pattern_triangle_strategy import PatternTriangleStrategy

strategy = PatternTriangleStrategy()
```

## Creating Custom Strategies

See [Strategies Guide](strategies.md#strategy-development) for details on creating new strategies.

## Related Documentation

- [Strategies Guide](strategies.md) - Strategy development
- [Pattern Detection](patterns-triangles.md) - Pattern-based strategies
- [Technical Indicators](technical-indicators.md) - Available indicators

