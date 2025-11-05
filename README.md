## Trading Bot (IBKR + OANDA)

A modular Python framework for quantitative research, visualization, and
semi-automated trading. It fetches historical market data from Interactive
Brokers (IBKR), computes technical indicators and strategy signals, optionally
leverages machine learning models (SVM/LSTM), visualizes results, and can place
trades via OANDA. IBKR order placement scaffolding exists but is currently
commented out.

### Key Features

- **Data ingestion**: Requests historical OHLCV data from IBKR TWS/Gateway for
  contracts listed in `contracts.json` and caches them as CSVs in `data/`.
- **Indicators & patterns**: Computes RSI, MACD, EMA/SMA, ATR, ADX, Bollinger
  Bands, support/resistance, and candlestick patterns.
- **Strategies**: Includes RSI and MARSI strategies, plus pattern-based logic
  and support/resistance reactions. Strategy markers are plotted for analysis.
- **Machine learning**: SVM/LSTM trainers and predictors for experimentation
  with predictive signals.
- **Visualization**: Generates plots (Matplotlib/Plotly) showing price series,
  indicators, and strategy markers.
- **Execution**: Order routing implemented for **OANDA**; IBKR order code is
  scaffolded but intentionally disabled.
- **Threaded state**: Background threads keep OANDA positions and account
  summary current.

### High-Level Architecture

- `main.py` orchestrates the workflow:
  - Starts IBKR client (`ib_api_client.IBApiClient`) in a background thread.
  - Spins up OANDA account/positions updater threads.
  - Iterates `contracts.json`, requests IBKR historical data (or loads from
    cached CSVs), computes indicators, runs strategies, and enqueues plot
    renderers.
- `request_historical_data/` handles IBKR historical data requests and
  callbacks.
- `technical_indicators/` provides a unified executor and specific indicators:
  `rsi/`, `macd/`, `ema/`, `sma/`, `atr/`, `adx/`, `bollinger_bands/`.
- `patterns/` and `hammer_shooting_star/` detect candle formations.
- `rsi_strategy/` and `marsi_strategy/` implement strategy logic;
  `support_resistance/` computes price levels and reactions.
- `plot/` renders charts and markers.
- `trader/` defines `Trader` for coordinating orders and simple position/budget
  tracking. OANDA execution is active; IBKR code is present but commented.
- `machine_learning/` provides `svm_model_trainer.py`, `lstm_model_trainer.py`,
  and predictors for ML-based signals.

### Data Flow

1. Load `contracts` from `contracts.json`.
2. For each contract, request historical bars via IBKR or load from cache.
3. Compute indicators with `technical_indicators.TechnicalIndicators`.
4. Run strategies (e.g., MARSI) and support/resistance detection; produce marker
   callbacks and lines to plot.
5. Optionally train/score ML models (SVM/LSTM) if enabled.
6. Enqueue plots and render them continuously.
7. If execution is enabled, route signals to `trader.Trader` for OANDA order
   placement with basic risk inputs.

### Execution and Brokers

- **IBKR**: Used for market data. Requires TWS/Gateway listening on
  `127.0.0.1:7497`. Order placement paths exist but are commented in `trader/`
  and `main.py`.
- **OANDA**: Active order execution via `place_order/oanda_place_order.py`.
  Background threads keep `positions` and `account summary` updated using
  `oandapyV20`.

### Strategies and Indicators

- Indicators: RSI, MACD, EMA, SMA, ATR, ADX, Bollinger Bands, plus combined
  pipelines via `technical_indicators/technical_indicators.py`.
- Patterns: Candlestick (including hammer/shooting star) via `patterns/` and
  `hammer_shooting_star/`.
- Strategies: `rsi_strategy/` and `marsi_strategy/` generate entry/exit markers;
  `support_resistance/` computes levels and reactions.

### Machine Learning

- `machine_learning/` contains SVM and LSTM tools for training and backtesting
  predictive models.
- ML usage in `main.py` is optional and largely commented. Enable as needed when
  experimenting.

### Requirements

See `requirements.txt` for Python dependencies, including `pandas`, `numpy`,
`TA_Lib`, `pandas_ta`, `scikit-learn`, `keras`, `matplotlib`, `plotly`, and
`Backtesting`.

### Behavior:

Connects to IBKR, starts threads, iterates contracts, fetches data or loads
cached CSVs from `data/`, computes indicators, runs strategies, and renders
plots in a loop.

### CLI usage

Run modular workflows without editing source files:

```
python cli.py fetch-process-plot --interval "6 M" --bar-size "1 hour" --refresh
python cli.py train-svm --input data/your.csv --output out/
python cli.py train-lstm --input data/your.csv --output out/
```

Notes:

- IBKR TWS/Gateway must be running and reachable at `127.0.0.1:7497` for
  `fetch-process-plot`.
- CSV inputs for training should match the format produced in `data/` by the
  fetch step.

### Running with Python virtual environment (macOS)

#### 1) Install system dependency (TA-Lib)

```
brew install ta-lib
```

#### 2) Create and activate a virtual environment

```
cd /Users/marco.suma/Personal/trading-bot
python3 -m venv .venv
source .venv/bin/activate
```

#### 3) Install Python dependencies

```
pip install --upgrade pip setuptools
pip install -r requirements.txt
```

#### 4) Add OANDA credentials

Create a `.env` file in the project root:

```
cat > .env << 'EOF'
OANDA_ACCESS_TOKEN=your_token
OANDA_ACCOUNT_ID=your_account_id
EOF
```

#### 5) Prepare data directory

```
mkdir -p data
```

#### 6) Start IBKR TWS/Gateway

- Launch TWS/Gateway (Paper recommended).
- Enable API: File → Global Configuration → API → Settings:
  - Check “Enable ActiveX and Socket Clients”
  - Socket port: 7497
  - Add 127.0.0.1 to “Trusted IPs”

#### 7) Run the application

```
python main.py
```

You should see it connect to IBKR, iterate `contracts.json`, fetch/cached data,
compute indicators/strategies, and render plots. Provide entries like
"SYMBOL,CURRENCY,SECTYPE,EXCHANGE" per line in the `contracts` array.

#### 8) Deactivate the environment (when done)

```
deactivate
```

Notes:

- If you get TA-Lib import errors, ensure step 1 ran before step 3.
- If stuck on “Waiting for connection to server”, verify TWS is running, API is
  enabled, and port is 7497.

### Running with Docker (NOT TESTED)

- IBKR connectivity from a container requires reaching your host's TWS/Gateway.
  By default `main.py` uses `127.0.0.1`, which from inside Docker refers to the
  container itself. Use one of the following:

  1. Change IBKR host in `main.py` to `host.docker.internal`:
     - Replace `client.connect('127.0.0.1', 7497, 123)` with
       `client.connect('host.docker.internal', 7497, 123)`.

  2. Or add a compose override to resolve `host.docker.internal`:
     - Add `extra_hosts: ["host.docker.internal:host-gateway"]` to the service.

- Build and run:

```
docker compose up --build
```

- For debug mode (waits for debugger on port 5678):

```
docker compose -f docker-compose.debug.yml up --build
```

- Ensure TWS/Gateway is running on your host at port 7497 before starting the
  container. Create a `data/` folder if you want cached CSVs persisted:

```
mkdir -p data
```

### Configuration

- `contracts.json`: Controls which instruments are processed.
- `request_historical_data/`: Adjust intervals and bar sizes (`interval`,
  `timePeriod`) used by `main.py`.
- `main.py`: Toggle strategy/ML sections, plotting, and execution hooks by
  (un)commenting relevant lines.

### Outputs

- `data/data-<SYMBOL>-<SECTYPE>-<EXCHANGE>-<CURRENCY>-<INTERVAL>-<TIMEPERIOD>.csv`:
  Cached time series.
- Plots: On-screen charts with indicators and strategy markers.
- ML artifacts: Produced when ML trainers are enabled.

### Backtesting

- Strategy-specific backtesting utilities in `rsi_strategy/backtesting/` and
  `marsi_strategy/backtesting/`.
- Additional SVM backtesting utilities in `machine_learning/svm_backtesting/`.

### Risk Management

- Basic max loss is currently hard-coded around OANDA orders in `trader/`.
  Comprehensive risk controls (position sizing, portfolio constraints, slippage,
  latency, etc.) are not fully implemented. Use with caution.

### Repository Structure (selected)

- `main.py`: Entry point orchestrating data, indicators, strategies, plotting,
  and (optional) execution.
- `contracts.json`: List of instruments to process.
- `ib_api_client/`, `IBJts/`: IBKR API client and vendor library.
- `request_historical_data/`: Historical data requests and callbacks.
- `technical_indicators/`: Indicator implementations and an executor pipeline.
- `patterns/`, `hammer_shooting_star/`: Pattern detection.
- `rsi_strategy/`, `marsi_strategy/`, `support_resistance/`: Strategy and level
  analysis.
- `machine_learning/`: ML training and predictors.
- `plot/`: Visualization utilities.
- `place_order/`: OANDA and IBKR order execution components.
- `trader/`: Trading coordination and order routing.

### Notes

- IBKR order placement code is scaffolded but disabled by default. OANDA
  execution is active.
- Requires IBKR TWS/Gateway running locally and valid OANDA credentials.

### Troubleshooting

- Stuck on "Waiting for connection to server":
  - Verify TWS/Gateway is running, API enabled, and listening on the expected
    port (default paper: 7497).
  - Native run: host should be `127.0.0.1`.
  - Docker run: host should be `host.docker.internal` (or use compose
    `extra_hosts`).

- OANDA errors about authentication or permissions:
  - Confirm `.env` contains valid `OANDA_ACCESS_TOKEN` and `OANDA_ACCOUNT_ID`.
  - Check account type (practice vs live) and instrument permissions.

- `TA_Lib` import errors (native):
  - Install system lib first, then Python package. On macOS:

```
brew install ta-lib
pip install TA-Lib
```

- No plots appear:
  - Ensure the process remains running; plots are executed from a queue in the
    main loop. Give it time to fetch data and compute indicators.
  - Check that the instrument in `contracts.json` returns data for the chosen
    `interval` and `timePeriod`.

### Disclaimer

This project is for educational and research purposes. Trading involves
significant risk. Use at your own risk and verify behavior on paper
trading/sandbox environments before any live deployment.
