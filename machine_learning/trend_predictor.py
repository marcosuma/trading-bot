"""
Trend Predictor using Machine Learning

Predicts whether the trend will continue or reverse.
This is often more actionable than predicting exact extrema.
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


class TrendPredictor:
    """Predict trend continuation vs reversal."""

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

    def _create_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Create features and target (trend continuation vs reversal)."""
        df = df.copy()

        # Determine current trend (using moving averages)
        if "SMA_50" in df.columns and "SMA_200" in df.columns:
            current_trend = (df["SMA_50"] > df["SMA_200"]).astype(int)  # 1 = uptrend, 0 = downtrend
        elif "EMA_10" in df.columns and "EMA_20" in df.columns:
            current_trend = (df["EMA_10"] > df["EMA_20"]).astype(int)
        else:
            # Simple price trend
            current_trend = (df["close"] > df["close"].shift(10)).astype(int)

        # Target: Will trend continue or reverse?
        future_price = df["close"].shift(-self.prediction_horizon)
        future_trend = (future_price > df["close"]).astype(int)

        # 1 = trend continues, 0 = trend reverses
        df["target"] = (current_trend == future_trend).astype(int)
        df = df[df["target"].notna()].copy()

        # Features
        feature_cols = []

        if "SMA_50" in df.columns and "SMA_200" in df.columns:
            df["sma_trend"] = (df["SMA_50"] > df["SMA_200"]).astype(int)
            df["sma_distance"] = (df["SMA_50"] - df["SMA_200"]) / df["SMA_200"]
            feature_cols.extend(["sma_trend", "sma_distance"])

        if "RSI_14" in df.columns:
            feature_cols.append("RSI_14")
            df["rsi_extreme"] = ((df["RSI_14"] > 70) | (df["RSI_14"] < 30)).astype(int)
            feature_cols.append("rsi_extreme")

        if "adx" in df.columns:
            feature_cols.append("adx")

        if "macd" in df.columns and "macd_s" in df.columns:
            df["macd_cross"] = (df["macd"] > df["macd_s"]).astype(int)
            feature_cols.append("macd_cross")

        # Momentum
        epsilon = 1e-8
        for period in [5, 10, 20]:
            shifted_close = df["close"].shift(period)
            df[f"momentum_{period}"] = (df["close"] - shifted_close) / (shifted_close + epsilon)
            feature_cols.append(f"momentum_{period}")

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

    def train(self, df: pd.DataFrame, test_size=0.2, model_name="trend_predictor", retrain=False):
        """Train trend prediction model."""
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
        """Predict trend continuation for new data."""
        if not self.is_trained:
            raise ValueError("Model not trained.")

        X, _ = self._create_features(df)
        if len(X) == 0:
            df["predicted_trend"] = None
            return df

        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)

        df_result = df.copy()
        df_result["predicted_trend"] = None
        for i, idx in enumerate(X.index):
            df_result.loc[idx, "predicted_trend"] = "CONTINUE" if predictions[i] == 1 else "REVERSE"

        return df_result

