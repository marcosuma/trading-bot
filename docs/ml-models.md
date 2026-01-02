# ML Models Documentation

Detailed documentation for machine learning models used in the trading bot.

## Overview

The system includes several ML models for market prediction:

- **Extrema Predictor**: Predicts local minima/maxima (buy/sell points)
- **Price Direction Predictor**: Predicts next bar's price direction
- **Volatility Predictor**: Predicts future volatility
- **Trend Predictor**: Predicts market trend

## Extrema Predictor

### Purpose

Predicts local extrema (minima for buy points, maxima for sell points) within a prediction horizon.

### Model Types

- **XGBoost** (default): Gradient boosting classifier
- **LightGBM**: Light gradient boosting
- **Ensemble**: Voting classifier (XGBoost + LightGBM)

### Features

- OHLCV data
- Technical indicators (RSI, MACD, ATR, ADX, Bollinger Bands, etc.)
- Lagged features (previous N bars)
- Derived features (price changes, ROC, acceleration, volume ratios, volatility)

### Training

```bash
python cli.py train-extrema-predictor \
  --asset USD-CAD \
  --lookback-bars 20 \
  --model-type ensemble \
  --use-feature-selection
```

### Hyperparameters

- `n_estimators`: Number of trees (default: 200)
- `max_depth`: Maximum tree depth (default: 6)
- `learning_rate`: Learning rate (default: 0.1)
- `early_stopping_rounds`: Early stopping (default: 10)

### Evaluation

Models are evaluated on:
- Accuracy
- Precision, Recall, F1-Score (per class)
- Confusion Matrix

## Price Direction Predictor

### Purpose

Predicts the next bar's price direction (up/down/sideways).

### Training

```bash
python cli.py train-price-direction-predictor --asset USD-CAD
```

## Volatility Predictor

### Purpose

Predicts future volatility (high/low).

### Training

```bash
python cli.py train-volatility-predictor --asset USD-CAD
```

## Trend Predictor

### Purpose

Predicts market trend (uptrend/downtrend/sideways).

### Training

```bash
python cli.py train-trend-predictor --asset USD-CAD
```

## Model Storage

Trained models are saved to:
```
machine_learning/models/
├── extrema_predictor.pkl
├── extrema_predictor_metadata.json
└── ...
```

## Using Models in Strategies

```python
from machine_learning.extrema_predictor import ExtremaPredictor

predictor = ExtremaPredictor()
predictor.load_model("machine_learning/models/extrema_predictor.pkl")

# Predict extrema
predictions = predictor.predict(df)
```

## Related Documentation

- [Machine Learning Guide](machine-learning.md) - ML overview
- [Strategies Guide](strategies.md) - Strategy development
- [CLI Reference](cli-reference.md) - Training commands

