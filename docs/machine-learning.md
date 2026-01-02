# Machine Learning

ML models for market prediction and signal generation.

## Available Models

### Extrema Predictor

**Purpose**: Predict local minima (buy points) and maxima (sell points)

**Model Types**: XGBoost, LightGBM, Ensemble

**Training**:
```bash
python cli.py train-extrema-predictor --asset USD-CAD --lookback-bars 20
```

**Features**: OHLCV, technical indicators, lagged features, derived features

See [ML Models Documentation](ml-models.md) for details.

### Price Direction Predictor

**Purpose**: Predict next bar's price direction (up/down/sideways)

**Training**:
```bash
python cli.py train-price-direction-predictor --asset USD-CAD
```

### Volatility Predictor

**Purpose**: Predict future volatility (high/low)

**Training**:
```bash
python cli.py train-volatility-predictor --asset USD-CAD
```

### Trend Predictor

**Purpose**: Predict market trend (uptrend/downtrend/sideways)

**Training**:
```bash
python cli.py train-trend-predictor --asset USD-CAD
```

## Model Training

### Basic Training

```bash
# Train on single asset
python cli.py train-extrema-predictor --asset USD-CAD

# Train on all assets
python cli.py train-extrema-predictor
```

### Advanced Options

```bash
python cli.py train-extrema-predictor \
  --asset USD-CAD \
  --lookback-bars 30 \
  --test-size 0.2 \
  --validation-size 0.1 \
  --model-type ensemble \
  --use-feature-selection
```

### Model Types

- **xgboost**: XGBoost classifier (default)
- **lightgbm**: LightGBM classifier
- **ensemble**: Voting classifier (XGBoost + LightGBM)

## Feature Engineering

Models use comprehensive features:

- **OHLCV**: Open, high, low, close, volume
- **Technical Indicators**: RSI, MACD, ATR, ADX, Bollinger Bands, etc.
- **Lagged Features**: Previous N bars of all features
- **Derived Features**: Price changes, ROC, acceleration, volume ratios, volatility

## Model Evaluation

Models are evaluated on:

- **Accuracy**: Overall classification accuracy
- **Precision**: Per-class precision
- **Recall**: Per-class recall
- **F1-Score**: Per-class F1-score
- **Confusion Matrix**: Classification breakdown

## Model Storage

Trained models are saved to:
```
machine_learning/models/
├── extrema_predictor.pkl
├── extrema_predictor_metadata.json
└── ...
```

## Using Predictions in Strategies

ML predictions can be integrated into strategies:

```python
from machine_learning.extrema_predictor import ExtremaPredictor

predictor = ExtremaPredictor()
predictor.load_model("machine_learning/models/extrema_predictor.pkl")

# Predict extrema
predictions = predictor.predict(df)
```

## Related Documentation

- [ML Models Documentation](ml-models.md) - Detailed model documentation
- [Strategies Guide](strategies.md) - Integrating ML into strategies

