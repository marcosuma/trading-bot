# Architecture Overview

High-level architecture of the Trading Bot system.

## System Components

The system consists of two main subsystems:

### 1. Backtesting & Research System

**Purpose**: Historical data analysis, strategy development, and backtesting.

**Components**:
- **CLI Interface** (`cli.py`): Interactive shell for commands
- **Data Manager**: Downloads and caches historical data
- **Technical Indicators**: Calculates indicators from OHLCV data
- **Strategy Framework**: Extensible strategy base classes
- **Backtesting Engine**: Executes strategies on historical data
- **ML Pipeline**: Feature engineering and model training

**Data Flow**:
```
IBKR → CSV Cache → Technical Indicators → Strategies → Backtesting → Reports
```

### 2. Live Trading System

**Purpose**: Real-time trading execution with risk management.

**Components**:
- **Trading Engine**: Orchestrates trading operations
- **Data Manager**: Real-time data collection and bar aggregation
- **Strategy Adapter**: Adapts backtesting strategies for live trading
- **Order Manager**: Order placement and position tracking
- **Broker Adapters**: IBKR and OANDA integration
- **REST API**: FastAPI-based API for control
- **Frontend**: React web interface

**Data Flow**:
```
Broker → Real-time Ticks → Bar Aggregation → Indicators → Strategy → Orders → Broker
```

See [Live Trading Architecture](live-trading-architecture.md) for detailed architecture.

## Key Design Principles

1. **Modularity**: Components are loosely coupled and can be used independently
2. **Extensibility**: Easy to add new strategies, indicators, or brokers
3. **Separation of Concerns**: Backtesting and live trading share strategies but have separate execution paths
4. **Data-Driven**: Strategies operate on DataFrames, making them testable and debuggable

## Data Management

### Historical Data

- **Source**: IBKR TWS/Gateway
- **Storage**: CSV files in `data/` directory
- **Format**: OHLCV with technical indicators
- **Organization**: `data/{ASSET}/{bar-size}.csv`

### Real-Time Data

- **Source**: IBKR or OANDA via broker adapters
- **Storage**: MongoDB (for live trading)
- **Processing**: Real-time tick aggregation into bars
- **Retention**: Configurable (default: 1000 bars per bar size)

See [Data Management](data-management.md) for details.

## Strategy Framework

All strategies inherit from `BaseForexStrategy` and implement:
- `generate_signals()`: Returns DataFrame with `execute_buy` and `execute_sell` signals
- `execute()`: Runs backtesting on the signals

Strategies can be:
- **Backtested**: Using the `Backtesting.py` framework
- **Live Traded**: Via the `StrategyAdapter` in live trading system

See [Strategies Guide](strategies.md) for details.

## Broker Integration

### IBKR

- **Market Data**: Historical and real-time (delayed or real-time)
- **Order Execution**: Paper and live trading
- **API**: Native Python API (`ibapi`)

### OANDA

- **Market Data**: Real-time forex data
- **Order Execution**: Paper and live trading
- **API**: REST API (`oandapyV20`)

See [Broker Integration](live-trading/brokers.md) for setup.

## Machine Learning

ML models predict:
- **Extrema**: Local minima/maxima (buy/sell points)
- **Price Direction**: Up/down/sideways
- **Volatility**: High/low volatility periods
- **Trend**: Uptrend/downtrend/sideways

Models use:
- **Features**: OHLCV, technical indicators, derived features
- **Algorithms**: XGBoost, LightGBM, Ensemble
- **Training**: Historical data with cross-validation

See [Machine Learning Guide](machine-learning.md) for details.

## Related Documentation

- [Live Trading Architecture](live-trading-architecture.md) - Detailed live trading architecture
- [Data Management](data-management.md) - Data handling details
- [Strategies Guide](strategies.md) - Strategy development
- [Real-Time Data Flow](live-trading/data-flow.md) - How real-time data works

