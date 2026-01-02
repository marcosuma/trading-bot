# Technical Indicators

Available technical indicators and their usage.

## Available Indicators

### Trend Indicators

- **SMA (Simple Moving Average)**: `SMA_50`, `SMA_200`
- **EMA (Exponential Moving Average)**: `EMA_10`, `EMA_20`, `EMA_50`
- **MACD**: `macd`, `macd_s`, `macd_h`
- **ADX**: `adx`, `plus_di`, `minus_di`

### Momentum Indicators

- **RSI (Relative Strength Index)**: `RSI_14`
- **Rate of Change (ROC)**: `ROC_14`
- **Price Acceleration**: `price_acceleration`

### Volatility Indicators

- **ATR (Average True Range)**: `ATR_14`
- **Bollinger Bands**: `bollinger_up`, `bollinger_down`, `bollinger_mid`
- **Volatility Ratio**: `volatility_ratio`

### Volume Indicators

- **Volume MA Ratio**: `volume_ma_ratio`
- **Volume Change**: `volume_change`

### Pattern Indicators

- **Local Extrema**: `LOCAL_MAX`, `LOCAL_MIN`

## Usage in Strategies

All indicators are automatically calculated when using `TechnicalIndicators`:

```python
from technical_indicators.technical_indicators import TechnicalIndicators

ti = TechnicalIndicators()
df_with_indicators = ti.execute(df)
```

Then access indicators as DataFrame columns:

```python
# In your strategy
def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
    # RSI is available
    df["rsi_oversold"] = df["RSI_14"] < 30

    # MACD is available
    df["macd_bullish"] = df["macd"] > df["macd_s"]

    # ATR is available
    df["stop_loss"] = df["close"] - (df["ATR_14"] * 1.5)

    return df
```

## Indicator Details

### RSI (Relative Strength Index)

- **Column**: `RSI_14`
- **Period**: 14 (default)
- **Range**: 0-100
- **Usage**: Oversold (<30), Overbought (>70)

### MACD (Moving Average Convergence Divergence)

- **Columns**: `macd`, `macd_s`, `macd_h`
- **Parameters**: Fast EMA (12), Slow EMA (26), Signal EMA (9)
- **Usage**: Trend direction, crossovers

### ATR (Average True Range)

- **Column**: `ATR_14`
- **Period**: 14 (default)
- **Usage**: Volatility measurement, stop loss calculation

### Bollinger Bands

- **Columns**: `bollinger_up`, `bollinger_down`, `bollinger_mid`
- **Parameters**: SMA (20), Std Dev (2)
- **Usage**: Mean reversion, volatility

### Local Extrema

- **Columns**: `LOCAL_MAX`, `LOCAL_MIN`
- **Method**: `scipy.signal.find_peaks`
- **Usage**: Swing high/low detection, pattern recognition

## Adding Custom Indicators

To add a new indicator:

1. Create indicator class in `technical_indicators/{indicator_name}/`:

```python
class MyIndicator:
    def calculate(self, df: pd.DataFrame):
        # Calculate indicator
        df["my_indicator"] = ...
```

2. Add to `TechnicalIndicators.__fn_impl()`:

```python
from technical_indicators.my_indicator.my_indicator import MyIndicator

class TechnicalIndicators:
    def __fn_impl(self, df: pd.DataFrame):
        # ... existing indicators ...
        MyIndicator().calculate(df)
```

## Related Documentation

- [Strategies Guide](strategies.md) - Using indicators in strategies
- [Data Management](data-management.md) - How indicators are calculated
- [Architecture](architecture.md) - System architecture

