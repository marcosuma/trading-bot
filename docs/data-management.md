# Data Management

How the system handles historical and real-time market data.

## Historical Data

### Download Process

1. **Source**: IBKR TWS/Gateway
2. **Contracts**: Defined in `contracts.json` (with `enabled` flag)
3. **Bar Sizes**: 5 mins, 15 mins, 1 hour, 4 hours, 1 day, 1 week
4. **Storage**: CSV files in `data/{ASSET}/` directory

### Download Command

```bash
python cli.py download-and-process
```

Options:
- `--include-1min`: Include 1-minute bars (limited to 2 months)
- `--force-refresh`: Re-download existing data
- `--bar-sizes`: Specify custom bar sizes

### IBKR API Limitations

- **1-minute bars**: Maximum ~2 months
- **5-minute bars**: Maximum ~1 year
- **15-minute bars**: Maximum ~2 years
- **1-hour+ bars**: Maximum ~20 years

The system automatically uses appropriate intervals for each bar size.

### Data Organization

```
data/
├── USD-CAD/
│   ├── data-USD-CASH-IDEALPRO-CAD-1 Y-5 mins.csv
│   ├── data-USD-CASH-IDEALPRO-CAD-1 Y-15 mins.csv
│   ├── data-USD-CASH-IDEALPRO-CAD-1 Y-1 hour.csv
│   └── ...
├── EUR-USD/
│   └── ...
```

### Processing Pipeline

1. **Download**: Raw OHLCV data from IBKR
2. **Cache**: Save as CSV
3. **Indicators**: Calculate technical indicators
4. **Update CSV**: Add indicator columns

See [Technical Indicators](technical-indicators.md) for available indicators.

## Real-Time Data (Live Trading)

### Data Collection

- **Source**: IBKR or OANDA via broker adapters
- **Format**: Real-time ticks aggregated into bars
- **Storage**: MongoDB `market_data` collection

### Bar Aggregation

Ticks are aggregated into bars based on bar size:
- **1 hour**: Aggregates ticks into hourly bars
- **15 mins**: Aggregates ticks into 15-minute bars
- etc.

See [Real-Time Data Flow](live-trading/data-flow.md) for details.

### Data Retention

- **Default**: Last 1000 bars per bar size
- **Configurable**: Per operation via `data_retention_bars`
- **Archival**: Older data is automatically removed

### Indicator Calculation

Indicators are calculated incrementally as new bars complete:
- Uses the same `TechnicalIndicators` pipeline as historical data
- Calculated on the retained bar buffer
- Stored with each bar in MongoDB

## Data Formats

### CSV Format (Historical)

```csv
date,open,high,low,close,volume,RSI_14,macd,macd_s,ATR_14,...
2024-01-01 00:00:00,1.3456,1.3460,1.3450,1.3458,1000000,55.2,0.001,0.0008,0.002,...
```

### MongoDB Format (Real-Time)

```json
{
  "operation_id": ObjectId("..."),
  "bar_size": "1 hour",
  "timestamp": ISODate("2024-01-01T00:00:00Z"),
  "open": 1.3456,
  "high": 1.3460,
  "low": 1.3450,
  "close": 1.3458,
  "volume": 1000000,
  "indicators": {
    "RSI_14": 55.2,
    "macd": 0.001,
    "ATR_14": 0.002
  }
}
```

## Related Documentation

- [Real-Time Data Flow](live-trading/data-flow.md) - How real-time data works
- [Technical Indicators](technical-indicators.md) - Available indicators
- [Live Trading System](live-trading/README.md) - Live trading overview

