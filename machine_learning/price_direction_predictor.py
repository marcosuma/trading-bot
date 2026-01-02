"""
Price Direction Predictor using Machine Learning

This module trains a model to predict the direction of price movement
(up or down) over the next N bars. This is often easier and more accurate
than predicting exact extrema points.

Binary classification: Will price go up or down?
"""

import numpy as np
import pandas as pd
import os
import pickle
from typing import Tuple
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    precision_recall_fscore_support,
)

# Import LightGBM (preferred) or XGBoost
try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False
    try:
        import xgboost as xgb
    except ImportError:
        raise ImportError("Either LightGBM or XGBoost must be installed")


class PriceDirectionPredictor:
    """
    Train and use ML models to predict price direction (up/down).

    This is often more accurate than predicting extrema because:
    - Binary classification is simpler than multi-class
    - Direction is more predictable than exact turning points
    - Can be used to filter trades or confirm signals
    """

    def __init__(
        self,
        lookback_bars: int = 10,
        prediction_horizon: int = 1,
        model_dir: str = None,
        use_technical_indicators: bool = True,
        model_type: str = "lightgbm",
    ):
        """
        Initialize the Price Direction Predictor.

        Args:
            lookback_bars: Number of previous bars to use as features
            prediction_horizon: Number of bars ahead to predict (default: 1 = next bar)
            model_dir: Directory to save/load models
            use_technical_indicators: Whether to include technical indicators
            model_type: "lightgbm" or "xgboost"
        """
        self.lookback_bars = lookback_bars
        self.prediction_horizon = prediction_horizon
        self.use_technical_indicators = use_technical_indicators
        self.model_type = model_type

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
        """Create features and target (price direction)."""
        df = df.copy()

        # Create target: will price go up or down in next N bars?
        if self.prediction_horizon == 1:
            df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)  # 1 = up, 0 = down
        else:
            future_close = df["close"].shift(-self.prediction_horizon)
            df["target"] = (future_close > df["close"]).astype(int)

        # Remove rows where target is NaN
        df = df[df["target"].notna()].copy()

        # Create feature list (similar to extrema predictor)
        feature_cols = []

        # Basic OHLCV features
        basic_features = ["open", "high", "low", "close", "volume"]
        for col in basic_features:
            if col in df.columns:
                feature_cols.append(col)

        # Price-based derived features
        if all(col in df.columns for col in ["open", "close", "high", "low"]):
            # Add small epsilon to prevent division by zero
            epsilon = 1e-8
            df["price_change"] = (df["close"] - df["open"]) / (df["open"] + epsilon)
            df["high_low_range"] = (df["high"] - df["low"]) / (df["low"] + epsilon)
            df["upper_shadow"] = (df["high"] - df[["open", "close"]].max(axis=1)) / (df["close"] + epsilon)
            df["lower_shadow"] = (df[["open", "close"]].min(axis=1) - df["low"]) / (df["close"] + epsilon)
            feature_cols.extend(["price_change", "high_low_range", "upper_shadow", "lower_shadow"])

        # Technical indicators
        if self.use_technical_indicators:
            indicator_features = [
                "SMA_50", "SMA_200", "EMA_10", "EMA_20", "EMA_50",
                "RSI_14", "macd", "macd_s", "macd_h",
                "adx", "plus_di", "minus_di",
                "atr", "bb_upper", "bb_middle", "bb_lower",
            ]

            for col in indicator_features:
                if col in df.columns:
                    feature_cols.append(col)

            # Create ratios
            epsilon = 1e-8
            if "SMA_50" in df.columns and "SMA_200" in df.columns:
                df["sma_diff"] = (df["SMA_50"] - df["SMA_200"]) / (df["SMA_200"] + epsilon)
                feature_cols.append("sma_diff")

            if "close" in df.columns and "EMA_10" in df.columns:
                df["ema_delta"] = (df["close"] - df["EMA_10"]) / (df["EMA_10"] + epsilon)
                feature_cols.append("ema_delta")

            if "close" in df.columns and "bb_upper" in df.columns and "bb_lower" in df.columns:
                bb_range = df["bb_upper"] - df["bb_lower"]
                df["bb_position"] = (df["close"] - df["bb_lower"]) / (bb_range + epsilon)
                feature_cols.append("bb_position")

        # Add momentum features
        if "close" in df.columns:
            epsilon = 1e-8
            for period in [3, 5, 10]:
                shifted_close = df["close"].shift(period)
                df[f"roc_{period}"] = (df["close"] - shifted_close) / (shifted_close + epsilon)
                feature_cols.append(f"roc_{period}")

        # Create lagged features
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

        all_features = lagged_features

        # Remove rows with NaN
        df = df.dropna(subset=all_features + ["target"]).copy()

        X = df[all_features].copy()
        y = df["target"].copy().astype(int)

        # Handle infinity and extreme values
        # Replace infinity with NaN
        X = X.replace([np.inf, -np.inf], np.nan)

        # Clip extreme values to prevent overflow (values beyond 3 standard deviations)
        for col in X.columns:
            if X[col].dtype in [np.float64, np.float32]:
                # Calculate reasonable bounds
                col_mean = X[col].mean()
                col_std = X[col].std()
                if col_std > 0:
                    # Clip to ±10 standard deviations (very permissive but safe)
                    lower_bound = col_mean - 10 * col_std
                    upper_bound = col_mean + 10 * col_std
                    X[col] = X[col].clip(lower=lower_bound, upper=upper_bound)

        # Remove rows that still have NaN after handling infinity
        valid_mask = ~X.isna().any(axis=1)
        X = X[valid_mask].copy()
        y = y[valid_mask].copy()

        # Final check: ensure no infinity or extreme values remain
        if np.isinf(X.values).any():
            print("Warning: Infinity values detected, replacing with NaN")
            X = X.replace([np.inf, -np.inf], np.nan)
            valid_mask = ~X.isna().any(axis=1)
            X = X[valid_mask].copy()
            y = y[valid_mask].copy()

        self.feature_names = all_features

        return X, y

    def train(
        self,
        df: pd.DataFrame,
        test_size: float = 0.2,
        validation_size: float = 0.1,
        random_state: int = 42,
        model_name: str = "price_direction_predictor",
        retrain: bool = False,
    ) -> dict:
        """Train the model to predict price direction."""
        print("Creating features...")
        X, y = self._create_features(df)

        if len(X) == 0:
            raise ValueError("No valid samples after feature creation.")

        print(f"Created {len(X)} samples with {len(self.feature_names)} features")
        print(f"Target distribution: {y.value_counts().to_dict()}")

        # Split data
        X_train_val, X_test, y_train_val, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )

        val_size_adjusted = validation_size / (1 - test_size)
        X_train, X_val, y_train, y_val = train_test_split(
            X_train_val, y_train_val, test_size=val_size_adjusted, random_state=random_state, stratify=y_train_val
        )

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)
        X_test_scaled = self.scaler.transform(X_test)

        # Model paths
        model_path = os.path.join(self.model_dir, f"{model_name}.pkl")
        scaler_path = os.path.join(self.model_dir, f"{model_name}_scaler.pkl")

        if not retrain and os.path.exists(model_path) and os.path.exists(scaler_path):
            print(f"Loading existing model from {model_path}...")
            self.model = pickle.load(open(model_path, "rb"))
            self.scaler = pickle.load(open(scaler_path, "rb"))
            self.is_trained = True
            print("Model loaded successfully")
        else:
            print(f"Training new {self.model_type.upper()} model...")

            if self.model_type == "lightgbm" and HAS_LIGHTGBM:
                self.model = lgb.LGBMClassifier(
                    objective="binary",
                    n_estimators=1000,
                    max_depth=10,
                    learning_rate=0.02,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    random_state=random_state,
                    early_stopping_rounds=100,
                    verbose=-1,
                    class_weight='balanced',
                )

                self.model.fit(
                    X_train_scaled,
                    y_train,
                    eval_set=[(X_val_scaled, y_val)],
                    callbacks=[lgb.early_stopping(stopping_rounds=100), lgb.log_evaluation(period=50)],
                )
            else:
                # XGBoost fallback
                self.model = xgb.XGBClassifier(
                    objective="binary:logistic",
                    n_estimators=1000,
                    max_depth=10,
                    learning_rate=0.02,
                    random_state=random_state,
                    early_stopping_rounds=100,
                    eval_metric="logloss",
                    use_label_encoder=False,
                )

                self.model.fit(
                    X_train_scaled,
                    y_train,
                    eval_set=[(X_val_scaled, y_val)],
                    verbose=True,
                )

            # Save model
            pickle.dump(self.model, open(model_path, "wb"))
            pickle.dump(self.scaler, open(scaler_path, "wb"))
            print(f"Model saved to {model_path}")
            self.is_trained = True

        # Evaluate
        print("\nEvaluating on test set...")
        y_pred = self.model.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        precision, recall, f1, _ = precision_recall_fscore_support(y_test, y_pred, average=None, zero_division=0)

        metrics = {
            "accuracy": accuracy,
            "precision_up": precision[1] if len(precision) > 1 else 0,
            "recall_up": recall[1] if len(recall) > 1 else 0,
            "f1_up": f1[1] if len(f1) > 1 else 0,
            "precision_down": precision[0],
            "recall_down": recall[0],
            "f1_down": f1[0],
            "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        }

        print(f"\nTest Accuracy: {accuracy:.4f}")
        print(f"Precision (Up): {metrics['precision_up']:.4f}")
        print(f"Precision (Down): {metrics['precision_down']:.4f}")
        print(f"Recall (Up): {metrics['recall_up']:.4f}")
        print(f"Recall (Down): {metrics['recall_down']:.4f}")

        return metrics

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """Predict price direction for new data."""
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")

        X, _ = self._create_features(df)

        if len(X) == 0:
            df_result = df.copy()
            df_result["predicted_direction"] = None
            df_result["predicted_direction_prob"] = None
            return df_result

        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)

        df_result = df.copy()
        df_result["predicted_direction"] = None
        df_result["predicted_direction_prob"] = None

        for i, idx in enumerate(X.index):
            df_result.loc[idx, "predicted_direction"] = "UP" if predictions[i] == 1 else "DOWN"
            df_result.loc[idx, "predicted_direction_prob"] = float(probabilities[i].max())

        return df_result

