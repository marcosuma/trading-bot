# Patterns and Triangles Analysis

## Overview

This document explains what the `patterns/` and `triangles/` modules do and how they can be integrated into trading strategies.

See [Strategies Guide](strategies.md) for information on using patterns in strategies.

## Patterns Module (`patterns/patterns.py`)

### What It Does

The Patterns module detects classic chart patterns in price data using:
1. **Kernel Regression**: Smooths price data to reduce noise
2. **Extrema Detection**: Finds local maxima and minima in the smoothed data
3. **Pattern Recognition**: Identifies specific chart patterns based on extrema relationships

### Detected Patterns

1. **HS (Head and Shoulders)**: Reversal pattern
   - Three peaks: middle peak (head) is highest
   - Two outer peaks (shoulders) are roughly equal height
   - Bearish reversal signal

2. **IHS (Inverse Head and Shoulders)**: Reversal pattern
   - Three troughs: middle trough (head) is lowest
   - Two outer troughs (shoulders) are roughly equal depth
   - Bullish reversal signal

3. **BTOP (Broadening Top)**: Continuation/reversal pattern
   - Expanding triangle with higher highs and lower lows
   - Often indicates volatility increase

4. **BBOT (Broadening Bottom)**: Continuation/reversal pattern
   - Expanding triangle with lower lows and higher highs
   - Often indicates volatility increase

5. **TTOP (Triangle Top)**: Continuation pattern
   - Converging trendlines with lower highs and higher lows
   - Bearish continuation

6. **TBOT (Triangle Bottom)**: Continuation pattern
   - Converging trendlines with higher lows and lower highs
   - Bullish continuation

7. **RTOP (Rectangle Top)**: Consolidation pattern
   - Horizontal support and resistance levels
   - Breakout direction determines trend

8. **RBOT (Rectangle Bottom)**: Consolidation pattern
   - Horizontal support and resistance levels
   - Breakout direction determines trend

### Current Implementation

- **Input**: DataFrame with OHLCV data
- **Output**: Dictionary of detected patterns with start/end indices
- **Visualization**: Plots patterns using matplotlib
- **Limitation**: Does NOT generate trading signals, only detects patterns

### How to Use in Strategies

To create a trading strategy from patterns:

1. **Pattern Completion Strategy**:
   - Detect when a pattern completes (reaches the last extrema)
   - Generate buy signal on bullish patterns (IHS, TBOT, RBOT)
   - Generate sell signal on bearish patterns (HS, TTOP, RTOP)
   - Entry: On pattern completion
   - Exit: After target move or pattern invalidation

2. **Pattern Breakout Strategy**:
   - Detect rectangle/triangle patterns
   - Buy on breakout above resistance
   - Sell on breakdown below support
   - Use volume confirmation if available

3. **Pattern Confirmation Strategy**:
   - Use patterns as confirmation for other indicators
   - Only trade when pattern aligns with trend/momentum signals

### Example Integration

```python
from patterns.patterns import Patterns

class PatternTradingStrategy(BaseForexStrategy):
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        # Detect patterns
        pattern_detector = Patterns(None, None, None)
        patterns = pattern_detector._find_patterns(extrema)

        # Generate signals based on pattern completion
        df["execute_buy"] = np.nan
        df["execute_sell"] = np.nan

        # Buy on bullish pattern completion
        for pattern_type, periods in patterns.items():
            if pattern_type in ["IHS", "TBOT", "RBOT"]:
                for start, end in periods:
                    df.loc[end, "execute_buy"] = df.loc[end, "close"]

        # Sell on bearish pattern completion
        for pattern_type, periods in patterns.items():
            if pattern_type in ["HS", "TTOP", "RTOP"]:
                for start, end in periods:
                    df.loc[end, "execute_sell"] = df.loc[end, "close"]

        return df
```

---

## Triangles Module (`triangles/triangles.py`)

### What It Does

The Triangles module detects triangle patterns (ascending, descending, symmetrical) using:
1. **Pivot Points**: Identifies swing highs and lows
2. **Linear Regression**: Fits trendlines to pivot points
3. **Triangle Detection**: Finds converging trendlines (support and resistance)

### Triangle Types

1. **Ascending Triangle**:
   - Horizontal resistance, rising support
   - Bullish continuation pattern
   - Breakout typically upward

2. **Descending Triangle**:
   - Horizontal support, falling resistance
   - Bearish continuation pattern
   - Breakout typically downward

3. **Symmetrical Triangle**:
   - Converging support and resistance
   - Neutral pattern, breakout direction determines trend

### Current Implementation

- **Input**: DataFrame with OHLCV data
- **Output**: Visual plot showing detected triangles
- **Pivot Detection**: Uses 3-bar lookback/forward to identify pivots
- **Triangle Detection**: Requires at least 5 pivot points (3 highs, 2 lows or vice versa)
- **Limitation**: Does NOT generate trading signals, only visualizes triangles

### How to Use in Strategies

To create a trading strategy from triangles:

1. **Triangle Breakout Strategy**:
   - Detect triangle formation
   - Buy on breakout above upper trendline (resistance)
   - Sell on breakdown below lower trendline (support)
   - Entry: On breakout with volume confirmation
   - Exit: Target = triangle height, Stop = opposite trendline

2. **Triangle Reversal Strategy**:
   - Detect triangle completion
   - Trade the reversal if breakout fails
   - Use RSI/MACD for confirmation

3. **Triangle Continuation Strategy**:
   - Detect triangle in existing trend
   - Trade continuation after breakout
   - Use ADX to confirm trend strength

### Example Integration

```python
from triangles.triangles import Triangles

class TriangleBreakoutStrategy(BaseForexStrategy):
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        # Detect triangles
        triangle_detector = Triangles(None, None, None)

        # Find pivot points
        df["pivot"] = df.apply(
            lambda x: triangle_detector._pivotid(df, x.name, 3, 3), axis=1
        )

        # Detect triangle breakouts
        df["execute_buy"] = np.nan
        df["execute_sell"] = np.nan

        for i in range(100, len(df)):
            try:
                slmin, intercmin, slmax, intercmax, xxmin, xxmax = \
                    triangle_detector._check_if_triangle(i, 100, df)

                # Calculate trendlines
                upper_line = slmax * df.index[i] + intercmax
                lower_line = slmin * df.index[i] + intercmin

                # Buy on breakout above upper trendline
                if df.loc[i, "close"] > upper_line:
                    df.loc[i, "execute_buy"] = df.loc[i, "close"]

                # Sell on breakdown below lower trendline
                if df.loc[i, "close"] < lower_line:
                    df.loc[i, "execute_sell"] = df.loc[i, "close"]
            except ValueError:
                continue

        return df
```

---

## Recommendations

### Immediate Use

1. **Keep as Analysis Tools**: Use patterns and triangles for visual analysis and confirmation
2. **Add to Reports**: Include pattern/triangle detection in strategy test reports
3. **Manual Trading**: Use detected patterns for manual trade decisions

### Future Integration

1. **Create Strategy Classes**: Convert pattern/triangle detection into `BaseForexStrategy` subclasses
2. **Add to CLI**: Include pattern/triangle strategies in `test-forex-strategies` command
3. **Combine with Indicators**: Use patterns as confirmation for existing strategies
4. **Backtest Performance**: Test pattern-based strategies against historical data

### Challenges

1. **Pattern Reliability**: Not all patterns lead to profitable trades
2. **False Breakouts**: Triangles can have false breakouts
3. **Timing**: Pattern completion may not align with optimal entry
4. **Market Conditions**: Patterns work better in certain market regimes

### Suggested Approach

1. **Start Simple**: Create basic pattern completion strategy
2. **Add Filters**: Use ADX, RSI, volume to filter patterns
3. **Test Thoroughly**: Backtest on multiple assets and timeframes
4. **Combine**: Use patterns as one component of a multi-signal strategy

---

## Summary

Both `patterns/` and `triangles/` modules provide valuable pattern detection capabilities but currently only visualize patterns. To use them in trading:

1. **Patterns**: Can be used to detect reversal/continuation patterns and generate signals on pattern completion
2. **Triangles**: Can be used to detect triangle formations and generate signals on breakout

The next step would be to create strategy classes that integrate these pattern detection capabilities into the existing strategy testing framework.

