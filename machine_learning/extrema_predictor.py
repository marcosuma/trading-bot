"""
Local Extrema Predictor using Machine Learning

This module trains a model to predict when local minima (buy points) and
local maxima (sell points) will occur based on technical indicators from
previous bars.

The model uses XGBoost, which is well-suited for:
- Tabular data with many features (technical indicators)
- Non-linear relationships
- Feature importance interpretation
- Handling class imbalance (extrema are rare events)
"""

import numpy as np
import pandas as pd
import os
import pickle
from typing import Tuple, Optional, List
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    precision_recall_fscore_support,
)

# Import XGBoost with helpful error message if OpenMP is missing
# On macOS, try to set library path automatically if libomp is installed
import sys
import os

if sys.platform == "darwin":  # macOS
    libomp_path = "/opt/homebrew/opt/libomp/lib"
    if os.path.exists(libomp_path):
        # Try to add to library path if not already there
        env_lib_path = os.environ.get("DYLD_LIBRARY_PATH", "")
        if libomp_path not in env_lib_path:
            os.environ["DYLD_LIBRARY_PATH"] = f"{libomp_path}:{env_lib_path}" if env_lib_path else libomp_path

try:
    import xgboost as xgb
except Exception as e:
    error_msg = str(e)
    if "libomp" in error_msg or "OpenMP" in error_msg:
        raise ImportError(
            "XGBoost requires OpenMP runtime library (libomp) on macOS.\n"
            "Please install it by running: brew install libomp\n"
            "After installation, you may need to restart your terminal or set:\n"
            "  export DYLD_LIBRARY_PATH=/opt/homebrew/opt/libomp/lib:$DYLD_LIBRARY_PATH\n"
            "If the issue persists, try reinstalling xgboost:\n"
            "  pip uninstall xgboost && pip install xgboost"
        ) from e
    else:
        raise

from local_extrema.local_extrema import LOCAL_MAX, LOCAL_MIN


class ExtremaPredictor:
    """
    Train and use ML models to predict local extrema (buy/sell points).

    The model predicts whether the next bar will be:
    - LOCAL_MIN (ideal buy point)
    - LOCAL_MAX (ideal sell point)
    - None (no extrema)

    Features include technical indicators from previous N bars.
    """

    def __init__(
        self,
        lookback_bars: int = 10,
        model_dir: str = None,
        use_technical_indicators: bool = True,
        model_type: str = "lightgbm",  # "xgboost", "lightgbm", or "ensemble"
        use_feature_selection: bool = True,
    ):
        """
        Initialize the Extrema Predictor.

        Args:
            lookback_bars: Number of previous bars to use as features (default: 10)
            model_dir: Directory to save/load models (default: machine_learning/models/)
            use_technical_indicators: Whether to include technical indicators as features
            model_type: Type of model to use - "xgboost", "lightgbm", or "ensemble" (default: "lightgbm")
            use_feature_selection: Whether to use feature selection based on importance (default: True)
        """
        self.lookback_bars = lookback_bars
        self.use_technical_indicators = use_technical_indicators
        self.model_type = model_type
        self.use_feature_selection = use_feature_selection

        if model_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            model_dir = os.path.join(base_dir, "models")
        self.model_dir = model_dir
        os.makedirs(self.model_dir, exist_ok=True)

        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []
        self.selected_features = None  # Features selected after importance analysis
        self.is_trained = False
        self.class_mapping = None  # Store mapping from encoded classes to original labels

    def _create_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Create features from previous bars and extract target labels.

        Args:
            df: DataFrame with OHLCV data and technical indicators

        Returns:
            Tuple of (features_df, target_series)
        """
        df = df.copy()

        # Ensure local_extrema column exists
        if "local_extrema" not in df.columns:
            raise ValueError("DataFrame must have 'local_extrema' column. Run TechnicalIndicators first.")

        # Create target: predict extrema within next N bars (more realistic than just next bar)
        # This makes the prediction task more achievable
        # Use a longer horizon for better signal-to-noise ratio
        prediction_horizon = min(5, max(2, self.lookback_bars // 2))  # Predict within next 5 bars or half lookback

        # Find if extrema occurs within prediction horizon
        target_values = []
        for i in range(len(df)):
            if i + prediction_horizon < len(df):
                # Check if any extrema occurs in the next N bars
                future_extrema = df["local_extrema"].iloc[i+1:i+1+prediction_horizon]
                if (future_extrema == LOCAL_MIN).any():
                    target_values.append(LOCAL_MIN)
                elif (future_extrema == LOCAL_MAX).any():
                    target_values.append(LOCAL_MAX)
                else:
                    target_values.append(None)
            else:
                target_values.append(None)

        df["target"] = target_values

        # Remove rows where target is NaN (last rows that don't have enough future data)
        df = df[df["target"].notna()].copy()

        # Create feature list
        feature_cols = []

        # Basic OHLCV features
        basic_features = ["open", "high", "low", "close", "volume"]
        for col in basic_features:
            if col in df.columns:
                feature_cols.append(col)

        # Price-based derived features
        if all(col in df.columns for col in ["open", "close", "high", "low"]):
            df["price_change"] = (df["close"] - df["open"]) / df["open"]
            df["high_low_range"] = (df["high"] - df["low"]) / df["low"]
            df["upper_shadow"] = (df["high"] - df[["open", "close"]].max(axis=1)) / df["close"]
            df["lower_shadow"] = (df[["open", "close"]].min(axis=1) - df["low"]) / df["close"]
            feature_cols.extend(["price_change", "high_low_range", "upper_shadow", "lower_shadow"])

        # Technical indicators
        if self.use_technical_indicators:
            indicator_features = [
                # Moving averages
                "SMA_50", "SMA_200", "EMA_10", "EMA_20", "EMA_50",
                # Momentum
                "RSI_14", "macd", "macd_s", "macd_h",
                # Trend
                "adx", "plus_di", "minus_di",
                # Volatility
                "atr", "bb_upper", "bb_middle", "bb_lower",
            ]

            for col in indicator_features:
                if col in df.columns:
                    feature_cols.append(col)

            # Create ratios and differences
            if "SMA_50" in df.columns and "SMA_200" in df.columns:
                df["sma_diff"] = (df["SMA_50"] - df["SMA_200"]) / df["SMA_200"]
                feature_cols.append("sma_diff")

            if "close" in df.columns and "EMA_10" in df.columns:
                df["ema_delta"] = (df["close"] - df["EMA_10"]) / df["EMA_10"]
                feature_cols.append("ema_delta")

            if "close" in df.columns and "bb_upper" in df.columns and "bb_lower" in df.columns:
                df["bb_position"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"] + 1e-8)  # Avoid division by zero
                feature_cols.append("bb_position")
                df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["close"]  # Bollinger Band width
                feature_cols.append("bb_width")

        # Add momentum and rate of change features
        if "close" in df.columns:
            for period in [3, 5, 10]:
                df[f"roc_{period}"] = (df["close"] - df["close"].shift(period)) / df["close"].shift(period)
                feature_cols.append(f"roc_{period}")

            # Price acceleration (rate of change of rate of change)
            if "roc_5" in df.columns:
                df["price_acceleration"] = df["roc_5"] - df["roc_5"].shift(1)
                feature_cols.append("price_acceleration")

        # Add volume features if available
        if "volume" in df.columns:
            df["volume_ma_ratio"] = df["volume"] / (df["volume"].rolling(window=20).mean() + 1e-8)
            feature_cols.append("volume_ma_ratio")
            df["volume_change"] = df["volume"].pct_change()
            feature_cols.append("volume_change")

        # Add volatility features
        if "high" in df.columns and "low" in df.columns:
            df["true_range"] = pd.concat([
                df["high"] - df["low"],
                (df["high"] - df["close"].shift(1)).abs(),
                (df["low"] - df["close"].shift(1)).abs()
            ], axis=1).max(axis=1)
            df["volatility_ratio"] = df["true_range"] / (df["close"] + 1e-8)
            feature_cols.append("volatility_ratio")

        # Add pattern-based features that capture price action leading to extrema
        if "close" in df.columns:
            # Recent price trend (slope over last N bars)
            for window in [3, 5, 10]:
                df[f"price_slope_{window}"] = df["close"].rolling(window=window).apply(
                    lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) == window else np.nan, raw=False
                )
                feature_cols.append(f"price_slope_{window}")

            # Price position in recent range
            for window in [5, 10, 20]:
                rolling_high = df["high"].rolling(window=window).max()
                rolling_low = df["low"].rolling(window=window).min()
                df[f"price_position_{window}"] = (df["close"] - rolling_low) / (rolling_high - rolling_low + 1e-8)
                feature_cols.append(f"price_position_{window}")

            # Consecutive up/down bars (momentum indicator)
            df["is_up_bar"] = (df["close"] > df["open"]).astype(int)
            df["consecutive_up"] = (df["is_up_bar"] * (df["is_up_bar"].groupby((df["is_up_bar"] != df["is_up_bar"].shift()).cumsum()).cumcount() + 1))
            df["consecutive_down"] = ((1 - df["is_up_bar"]) * ((1 - df["is_up_bar"]).groupby(((1 - df["is_up_bar"]) != (1 - df["is_up_bar"]).shift()).cumsum()).cumcount() + 1))
            feature_cols.extend(["consecutive_up", "consecutive_down"])

        # Add features that capture "distance" to recent extrema
        if "local_extrema" in df.columns and "close" in df.columns:
            # Create a numeric index for efficient computation
            df_reset = df.reset_index()

            # Distance (in bars) to last LOCAL_MIN
            min_mask = df_reset["local_extrema"] == LOCAL_MIN
            if min_mask.any():
                # For each row, find the index of the most recent min before it
                min_indices = df_reset[min_mask].index.values
                bars_since_min = []
                for i in range(len(df_reset)):
                    prev_mins = min_indices[min_indices < i]
                    if len(prev_mins) > 0:
                        bars_since_min.append(i - prev_mins[-1])
                    else:
                        bars_since_min.append(len(df_reset))  # Large value if no previous min
                df["bars_since_min"] = bars_since_min
                feature_cols.append("bars_since_min")

                # Price change since last min
                last_min_close = df_reset.loc[min_indices, "close"].reindex(df_reset.index, method='ffill')
                df["price_change_since_min"] = (df["close"].values - last_min_close.values) / (df["close"].values + 1e-8)
                feature_cols.append("price_change_since_min")

            # Distance (in bars) to last LOCAL_MAX
            max_mask = df_reset["local_extrema"] == LOCAL_MAX
            if max_mask.any():
                max_indices = df_reset[max_mask].index.values
                bars_since_max = []
                for i in range(len(df_reset)):
                    prev_maxs = max_indices[max_indices < i]
                    if len(prev_maxs) > 0:
                        bars_since_max.append(i - prev_maxs[-1])
                    else:
                        bars_since_max.append(len(df_reset))
                df["bars_since_max"] = bars_since_max
                feature_cols.append("bars_since_max")

                # Price change since last max
                last_max_close = df_reset.loc[max_indices, "close"].reindex(df_reset.index, method='ffill')
                df["price_change_since_max"] = (df["close"].values - last_max_close.values) / (df["close"].values + 1e-8)
                feature_cols.append("price_change_since_max")

        # Create lagged features (previous N bars)
        # Build all lagged features at once to avoid DataFrame fragmentation
        lagged_data = {}
        lagged_features = []
        for lag in range(1, self.lookback_bars + 1):
            for col in feature_cols:
                lagged_col = f"{col}_lag{lag}"
                lagged_data[lagged_col] = df[col].shift(lag)
                lagged_features.append(lagged_col)

        # Add all lagged features at once using concat
        if lagged_data:
            lagged_df = pd.DataFrame(lagged_data, index=df.index)
            df = pd.concat([df, lagged_df], axis=1)

        # Use lagged features as input (we predict future extrema based on past)
        all_features = lagged_features

        # Remove rows with NaN (from lagging)
        df = df.dropna(subset=all_features + ["target"]).copy()

        # Extract features and target
        X = df[all_features].copy()
        y = df["target"].copy()

        # Encode target: None -> 0, LOCAL_MIN -> 1, LOCAL_MAX -> 2
        y_encoded = y.map({None: 0, LOCAL_MIN: 1, LOCAL_MAX: 2}).fillna(0).astype(int)

        self.feature_names = all_features

        return X, y_encoded

    def train(
        self,
        df: pd.DataFrame,
        test_size: float = 0.2,
        validation_size: float = 0.1,
        random_state: int = 42,
        model_name: str = "extrema_predictor",
        retrain: bool = False,
    ) -> dict:
        """
        Train the XGBoost model to predict local extrema.

        Args:
            df: DataFrame with OHLCV data and technical indicators
            test_size: Fraction of data for testing (default: 0.2)
            validation_size: Fraction of training data for validation (default: 0.1)
            random_state: Random seed for reproducibility
            model_name: Name to save the model
            retrain: If True, retrain even if model exists

        Returns:
            Dictionary with training metrics
        """
        print("Creating features...")
        X, y = self._create_features(df)

        if len(X) == 0:
            raise ValueError("No valid samples after feature creation. Check data quality.")

        print(f"Created {len(X)} samples with {len(self.feature_names)} features")
        print(f"Target distribution: {y.value_counts().to_dict()}")

        # Calculate class weights to handle imbalance
        class_counts = y.value_counts().sort_index()
        total_samples = len(y)
        class_weights = {}
        for cls in class_counts.index:
            # Inverse frequency weighting: more frequent classes get lower weight
            class_weights[cls] = total_samples / (len(class_counts) * class_counts[cls])

        print(f"Class weights: {class_weights}")

        # Check class distribution
        class_counts = y.value_counts().sort_index()
        print(f"Class distribution: {class_counts.to_dict()}")

        # Ensure we have at least 2 samples per class for stratification
        # If a class has < 2 samples, we can't stratify properly
        min_samples_per_class = 2
        classes_to_keep = class_counts[class_counts >= min_samples_per_class].index.tolist()

        if len(classes_to_keep) < 2:
            raise ValueError(
                f"Need at least 2 classes with {min_samples_per_class}+ samples each. "
                f"Found classes: {class_counts.to_dict()}"
            )

        # Filter to keep only classes with enough samples
        if len(classes_to_keep) < len(class_counts):
            print(f"Warning: Filtering to classes with {min_samples_per_class}+ samples: {classes_to_keep}")
            mask = y.isin(classes_to_keep)
            X = X[mask]
            y = y[mask]

        # Re-encode to ensure classes are 0, 1, 2 (or 0, 1 if only 2 classes)
        unique_classes = sorted(y.unique())
        class_mapping = {old_class: new_class for new_class, old_class in enumerate(unique_classes)}
        reverse_mapping = {new_class: old_class for old_class, new_class in class_mapping.items()}
        y = y.map(class_mapping)

        # Store mapping for later use in predictions
        self.class_mapping = reverse_mapping

        print(f"Final class distribution after filtering: {y.value_counts().sort_index().to_dict()}")
        print(f"Class mapping (encoded -> original): {reverse_mapping}")

        # Use stratification only if we have enough samples per class
        stratify_y = y if all(y.value_counts() >= 2) else None

        # Split data: train -> (train + val), test
        X_train_val, X_test, y_train_val, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=stratify_y
        )

        # Split train_val: train, val
        val_size_adjusted = validation_size / (1 - test_size)
        stratify_train_val = y_train_val if all(y_train_val.value_counts() >= 2) else None
        X_train, X_val, y_train, y_val = train_test_split(
            X_train_val, y_train_val, test_size=val_size_adjusted, random_state=random_state, stratify=stratify_train_val
        )

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)
        X_test_scaled = self.scaler.transform(X_test)

        # Model path
        model_path = os.path.join(self.model_dir, f"{model_name}.pkl")
        scaler_path = os.path.join(self.model_dir, f"{model_name}_scaler.pkl")

        # Load existing model or train new one
        mapping_path = os.path.join(self.model_dir, f"{model_name}_mapping.pkl")
        if not retrain and os.path.exists(model_path) and os.path.exists(scaler_path):
            print(f"Loading existing model from {model_path}...")
            self.model = pickle.load(open(model_path, "rb"))
            self.scaler = pickle.load(open(scaler_path, "rb"))
            if os.path.exists(mapping_path):
                self.class_mapping = pickle.load(open(mapping_path, "rb"))
            else:
                # Fallback: assume standard mapping if not saved
                self.class_mapping = {0: 0, 1: 1, 2: 2}
            self.is_trained = True
            print("Model loaded successfully")
        else:
            print(f"Training new {self.model_type.upper()} model...")

            # Determine number of classes from training data
            n_classes = len(y_train.unique())
            print(f"Training with {n_classes} classes: {sorted(y_train.unique())}")

            # Calculate class weights for training set
            train_class_counts = y_train.value_counts().sort_index()
            train_total = len(y_train)
            sample_weights = y_train.map({
                cls: train_total / (n_classes * count)
                for cls, count in train_class_counts.items()
            }).values

            # Feature selection: train a quick model to identify important features
            if self.use_feature_selection and len(self.feature_names) > 50:
                print("Performing feature selection...")
                from sklearn.ensemble import RandomForestClassifier
                rf_selector = RandomForestClassifier(n_estimators=100, random_state=random_state, n_jobs=-1)
                rf_selector.fit(X_train_scaled, y_train, sample_weight=sample_weights)

                # Select top features based on importance
                feature_importance = pd.DataFrame({
                    "feature": self.feature_names,
                    "importance": rf_selector.feature_importances_
                }).sort_values("importance", ascending=False)

                # Keep top 80% of features or at least 50
                n_features_to_keep = max(50, int(len(self.feature_names) * 0.8))
                self.selected_features = feature_importance.head(n_features_to_keep)["feature"].tolist()

                print(f"Selected {len(self.selected_features)} features from {len(self.feature_names)} total")

                # Filter features
                X_train_scaled = pd.DataFrame(X_train_scaled, columns=self.feature_names)[self.selected_features].values
                X_val_scaled = pd.DataFrame(X_val_scaled, columns=self.feature_names)[self.selected_features].values
                X_test_scaled = pd.DataFrame(X_test_scaled, columns=self.feature_names)[self.selected_features].values
                self.feature_names = self.selected_features
            else:
                self.selected_features = self.feature_names

            # Choose model type
            if self.model_type == "lightgbm":
                try:
                    import lightgbm as lgb

                    if n_classes == 2:
                        objective = "binary"
                        metric = "binary_logloss"
                    else:
                        objective = "multiclass"
                        metric = "multi_logloss"

                    self.model = lgb.LGBMClassifier(
                        objective=objective,
                        num_class=n_classes if n_classes > 2 else None,
                        n_estimators=1000,
                        max_depth=12,
                        learning_rate=0.02,
                        subsample=0.8,
                        colsample_bytree=0.8,
                        min_child_samples=20,
                        reg_alpha=0.0,
                        reg_lambda=0.5,
                        random_state=random_state,
                        metric=metric,
                        early_stopping_rounds=100,
                        verbose=-1,
                        class_weight='balanced',  # Handle imbalance automatically
                    )

                    self.model.fit(
                        X_train_scaled,
                        y_train,
                        eval_set=[(X_val_scaled, y_val)],
                        callbacks=[lgb.early_stopping(stopping_rounds=100), lgb.log_evaluation(period=50)],
                    )
                except ImportError:
                    print("LightGBM not available, falling back to XGBoost")
                    self.model_type = "xgboost"

            if self.model_type == "xgboost":
                # XGBoost parameters optimized for classification
                if n_classes == 2:
                    objective = "binary:logistic"
                    eval_metric = "logloss"
                else:
                    objective = "multi:softprob"
                    eval_metric = "mlogloss"

                self.model = xgb.XGBClassifier(
                    objective=objective,
                    num_class=n_classes if n_classes > 2 else None,
                    n_estimators=1000,
                    max_depth=12,
                    learning_rate=0.02,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    colsample_bylevel=0.8,
                    colsample_bynode=0.8,
                    min_child_weight=0.5,
                    gamma=0.0,
                    reg_alpha=0.0,
                    reg_lambda=0.5,
                    random_state=random_state,
                    eval_metric=eval_metric,
                    use_label_encoder=False,
                    early_stopping_rounds=100,
                    tree_method='hist',
                    grow_policy='lossguide',
                    max_leaves=256,
                )

                self.model.fit(
                    X_train_scaled,
                    y_train,
                    sample_weight=sample_weights,
                    eval_set=[(X_val_scaled, y_val)],
                    verbose=True,
                )

            elif self.model_type == "ensemble":
                # Train both XGBoost and LightGBM, then combine
                print("Training ensemble of XGBoost and LightGBm...")
                import lightgbm as lgb
                from sklearn.ensemble import VotingClassifier

                # XGBoost model
                if n_classes == 2:
                    xgb_objective = "binary:logistic"
                    lgb_objective = "binary"
                else:
                    xgb_objective = "multi:softprob"
                    lgb_objective = "multiclass"

                xgb_model = xgb.XGBClassifier(
                    objective=xgb_objective,
                    num_class=n_classes if n_classes > 2 else None,
                    n_estimators=500,
                    max_depth=10,
                    learning_rate=0.03,
                    random_state=random_state,
                    early_stopping_rounds=50,
                    eval_metric="mlogloss" if n_classes > 2 else "logloss",
                    use_label_encoder=False,
                )

                lgb_model = lgb.LGBMClassifier(
                    objective=lgb_objective,
                    num_class=n_classes if n_classes > 2 else None,
                    n_estimators=500,
                    max_depth=10,
                    learning_rate=0.03,
                    random_state=random_state,
                    early_stopping_rounds=50,
                    class_weight='balanced',
                )

                self.model = VotingClassifier(
                    estimators=[('xgb', xgb_model), ('lgb', lgb_model)],
                    voting='soft',
                    weights=[1, 1]
                )

                # For ensemble, we need to fit with eval_set support
                # Fit XGBoost first
                xgb_model.fit(
                    X_train_scaled,
                    y_train,
                    sample_weight=sample_weights,
                    eval_set=[(X_val_scaled, y_val)],
                    verbose=False,
                )

                # Fit LightGBM
                lgb_model.fit(
                    X_train_scaled,
                    y_train,
                    eval_set=[(X_val_scaled, y_val)],
                    callbacks=[lgb.early_stopping(stopping_rounds=50), lgb.log_evaluation(period=0)],
                )

                # VotingClassifier will use the fitted models
                self.model.estimators_ = [xgb_model, lgb_model]
                self.model.classes_ = np.unique(y_train)
                self.model.named_estimators_ = {'xgb': xgb_model, 'lgb': lgb_model}

            # Save model, scaler, and class mapping
            pickle.dump(self.model, open(model_path, "wb"))
            pickle.dump(self.scaler, open(scaler_path, "wb"))
            mapping_path = os.path.join(self.model_dir, f"{model_name}_mapping.pkl")
            pickle.dump(self.class_mapping, open(mapping_path, "wb"))
            print(f"Model saved to {model_path}")
            print(f"Class mapping saved to {mapping_path}")
            self.is_trained = True

        # Evaluate on test set
        print("\nEvaluating on test set...")
        y_pred = self.model.predict(X_test_scaled)

        # Calculate metrics
        accuracy = accuracy_score(y_test, y_pred)

        # Get unique classes from test data
        unique_test_classes = sorted(y_test.unique())
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_test, y_pred, average=None, labels=unique_test_classes, zero_division=0
        )

        # Map class indices back to names (based on original encoding)
        # Use the stored class mapping to get original class values, then map to names
        original_label_map = {0: "None", 1: "LOCAL_MIN", 2: "LOCAL_MAX"}
        class_names = []
        for encoded_cls in unique_test_classes:
            if self.class_mapping is not None:
                original_cls = self.class_mapping.get(encoded_cls, encoded_cls)
            else:
                original_cls = encoded_cls
            class_names.append(original_label_map.get(original_cls, f"Class_{original_cls}"))

        # Build metrics dictionary
        metrics = {
            "accuracy": accuracy,
            "precision": {class_names[i]: precision[i] for i in range(len(class_names))},
            "recall": {class_names[i]: recall[i] for i in range(len(class_names))},
            "f1_score": {class_names[i]: f1[i] for i in range(len(class_names))},
        }

        # Confusion matrix with all possible classes (0, 1, 2) or just the ones we have
        cm_labels = sorted(set(unique_test_classes) | set(y_pred))
        metrics["confusion_matrix"] = confusion_matrix(y_test, y_pred, labels=cm_labels).tolist()

        print(f"\nTest Accuracy: {accuracy:.4f}")
        print("\nPer-class metrics:")
        for i, name in enumerate(class_names):
            print(f"  {name}:")
            print(f"    Precision: {precision[i]:.4f}")
            print(f"    Recall: {recall[i]:.4f}")
            print(f"    F1-Score: {f1[i]:.4f}")

        print("\nClassification Report:")
        print(classification_report(y_test, y_pred, target_names=class_names))

        # Feature importance and selection
        if hasattr(self.model, "feature_importances_"):
            print("\nTop 30 Most Important Features:")
            feature_importance = pd.DataFrame({
                "feature": self.feature_names,
                "importance": self.model.feature_importances_
            }).sort_values("importance", ascending=False)

            for idx, row in feature_importance.head(30).iterrows():
                print(f"  {row['feature']}: {row['importance']:.4f}")

            # Store top features for potential future feature selection
            self.top_features = feature_importance.head(50)["feature"].tolist()

        # Additional diagnostics
        print(f"\nClass distribution in test set:")
        test_class_counts = pd.Series(y_test).value_counts().sort_index()
        for cls, count in test_class_counts.items():
            pct = 100 * count / len(y_test)
            print(f"  Class {cls}: {count} ({pct:.1f}%)")

        return metrics

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Predict local extrema for new data.

        Args:
            df: DataFrame with OHLCV data and technical indicators

        Returns:
            DataFrame with added 'predicted_extrema' and 'predicted_extrema_prob' columns
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")

        # Create features (same as training)
        # Note: _create_features shifts target forward, so we predict extrema at current bar
        # based on previous bars. The returned X has indices that correspond to bars
        # where we can make predictions (after accounting for lookback and NaN removal)
        X, _ = self._create_features(df)

        if len(X) == 0:
            df_result = df.copy()
            df_result["predicted_extrema"] = None
            df_result["predicted_extrema_prob"] = None
            return df_result

        # Scale features
        X_scaled = self.scaler.transform(X)

        # Predict
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)

        # Map back to original labels using stored class mapping
        # First map from encoded classes (0, 1, 2) back to original encoded values
        # Then map to actual labels
        original_label_map = {0: None, 1: LOCAL_MIN, 2: LOCAL_MAX}

        if self.class_mapping is not None:
            # Use stored mapping to convert predictions back
            predicted_labels = []
            for pred in predictions:
                encoded_pred = int(pred)
                # Map from encoded class back to original encoded value
                original_encoded = self.class_mapping.get(encoded_pred, encoded_pred)
                # Map to actual label
                predicted_labels.append(original_label_map.get(original_encoded, None))
        else:
            # Fallback if no mapping stored (shouldn't happen if model was trained properly)
            predicted_labels = [original_label_map.get(int(pred), None) for pred in predictions]

        # Add predictions to dataframe
        # X.index contains the indices from the original df (after dropping NaN)
        # These correspond to bars where we can make predictions
        df_result = df.copy()
        df_result["predicted_extrema"] = None
        df_result["predicted_extrema_prob"] = None

        # Align predictions with dataframe indices
        for i, idx in enumerate(X.index):
            df_result.loc[idx, "predicted_extrema"] = predicted_labels[i]
            # Store max probability (confidence)
            df_result.loc[idx, "predicted_extrema_prob"] = float(probabilities[i].max())

        return df_result

    def load_model(self, model_name: str = "extrema_predictor"):
        """Load a previously trained model."""
        model_path = os.path.join(self.model_dir, f"{model_name}.pkl")
        scaler_path = os.path.join(self.model_dir, f"{model_name}_scaler.pkl")
        mapping_path = os.path.join(self.model_dir, f"{model_name}_mapping.pkl")

        if not os.path.exists(model_path) or not os.path.exists(scaler_path):
            raise FileNotFoundError(f"Model files not found: {model_path} or {scaler_path}")

        self.model = pickle.load(open(model_path, "rb"))
        self.scaler = pickle.load(open(scaler_path, "rb"))
        if os.path.exists(mapping_path):
            self.class_mapping = pickle.load(open(mapping_path, "rb"))
        else:
            # Fallback: assume standard mapping if not saved
            self.class_mapping = {0: 0, 1: 1, 2: 2}
        self.is_trained = True
        print(f"Model loaded from {model_path}")

