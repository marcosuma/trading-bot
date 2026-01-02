"""
Volatility Predictor using Machine Learning

Predicts future volatility (high/low) which can be used for:
- Position sizing
- Stop-loss placement
- Strategy selection (trend-following vs mean reversion)
"""

import numpy as np
import pandas as pd
import os
import pickle
from typing import Tuple
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, accuracy_score

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False
    import xgboost as xgb


class VolatilityPredictor:
    """Predict whether volatility will be high or low in the next N bars."""

    def __init__(self, lookback_bars=10, prediction_horizon=5, model_dir=None):
        self.lookback_bars = lookback_bars
        self.prediction_horizon = prediction_horizon

        if model_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            model_dir = os.path.join(base_dir, "models")
        self.model_dir = model_dir
        os.makedirs(self.model_dir, exist_ok=True)

        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []
        self.is_trained = False
        self.volatility_threshold = None  # Median volatility

    def _create_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Create features and target (high/low volatility)."""
        df = df.copy()

        # Calculate ATR as volatility measure
        if "atr" not in df.columns:
            # Calculate True Range
            high_low = df["high"] - df["low"]
            high_close = (df["high"] - df["close"].shift(1)).abs()
            low_close = (df["low"] - df["close"].shift(1)).abs()
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            df["atr"] = tr.rolling(window=14).mean()

        # Target: Will volatility be high in next N bars?
        future_atr = df["atr"].shift(-self.prediction_horizon)
        current_median = df["atr"].rolling(window=50).median()
        df["target"] = (future_atr > current_median).astype(int)  # 1 = high vol, 0 = low vol

        df = df[df["target"].notna()].copy()

        # Features: volatility indicators, price action, technical indicators
        feature_cols = []

        epsilon = 1e-8
        if "atr" in df.columns:
            feature_cols.append("atr")
            df["atr_ratio"] = df["atr"] / (df["close"] + epsilon)
            feature_cols.append("atr_ratio")

        if all(col in df.columns for col in ["high", "low", "close"]):
            df["range"] = (df["high"] - df["low"]) / (df["close"] + epsilon)
            feature_cols.append("range")

        if "RSI_14" in df.columns:
            feature_cols.append("RSI_14")

        if "adx" in df.columns:
            feature_cols.append("adx")

        if "bb_upper" in df.columns and "bb_lower" in df.columns and "close" in df.columns:
            df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / (df["close"] + epsilon)
            feature_cols.append("bb_width")

        # Lagged features
        lagged_data = {}
        lagged_features = []
        for lag in range(1, self.lookback_bars + 1):
            for col in feature_cols:
                lagged_col = f"{col}_lag{lag}"
                lagged_data[lagged_col] = df[col].shift(lag)
                lagged_features.append(lagged_col)

        if lagged_data:
            lagged_df = pd.DataFrame(lagged_data, index=df.index)
            df = pd.concat([df, lagged_df], axis=1)

        df = df.dropna(subset=lagged_features + ["target"]).copy()
        X = df[lagged_features].copy()
        y = df["target"].copy().astype(int)

        # Handle infinity and extreme values
        X = X.replace([np.inf, -np.inf], np.nan)

        # Clip extreme values
        for col in X.columns:
            if X[col].dtype in [np.float64, np.float32]:
                col_mean = X[col].mean()
                col_std = X[col].std()
                if col_std > 0:
                    lower_bound = col_mean - 10 * col_std
                    upper_bound = col_mean + 10 * col_std
                    X[col] = X[col].clip(lower=lower_bound, upper=upper_bound)

        # Remove rows with NaN after handling infinity
        valid_mask = ~X.isna().any(axis=1)
        X = X[valid_mask].copy()
        y = y[valid_mask].copy()

        self.feature_names = lagged_features
        return X, y

    def train(self, df: pd.DataFrame, test_size=0.2, model_name="volatility_predictor", retrain=False):
        """Train volatility prediction model."""
        X, y = self._create_features(df)

        if len(X) == 0:
            raise ValueError("No valid samples.")

        print(f"Created {len(X)} samples with {len(self.feature_names)} features")

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )

        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        model_path = os.path.join(self.model_dir, f"{model_name}.pkl")
        scaler_path = os.path.join(self.model_dir, f"{model_name}_scaler.pkl")

        if not retrain and os.path.exists(model_path):
            self.model = pickle.load(open(model_path, "rb"))
            self.scaler = pickle.load(open(scaler_path, "rb"))
            self.is_trained = True
        else:
            if HAS_LIGHTGBM:
                self.model = lgb.LGBMClassifier(
                    objective="binary",
                    n_estimators=500,
                    learning_rate=0.05,
                    random_state=42,
                    class_weight='balanced',
                )
            else:
                self.model = xgb.XGBClassifier(
                    objective="binary:logistic",
                    n_estimators=500,
                    learning_rate=0.05,
                    random_state=42,
                )

            self.model.fit(X_train_scaled, y_train)
            pickle.dump(self.model, open(model_path, "wb"))
            pickle.dump(self.scaler, open(scaler_path, "wb"))
            self.is_trained = True

        y_pred = self.model.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        print(f"Test Accuracy: {accuracy:.4f}")
        print(classification_report(y_test, y_pred))

        return {"accuracy": accuracy}

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """Predict volatility for new data."""
        if not self.is_trained:
            raise ValueError("Model not trained.")

        X, _ = self._create_features(df)
        if len(X) == 0:
            df["predicted_volatility"] = None
            return df

        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)

        df_result = df.copy()
        df_result["predicted_volatility"] = None
        for i, idx in enumerate(X.index):
            df_result.loc[idx, "predicted_volatility"] = "HIGH" if predictions[i] == 1 else "LOW"

        return df_result

