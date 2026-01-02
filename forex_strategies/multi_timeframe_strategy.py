"""
Multi-Timeframe Strategy Base Class

This module provides a base class for strategies that analyze multiple bar sizes
simultaneously. Higher timeframes (e.g., 1 day) are used for trend confirmation,
while lower timeframes (e.g., 15 mins, 1 hour) are used for precise entry/exit signals.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from forex_strategies.base_strategy import BaseForexStrategy
from forex_strategies.adaptive_multi_indicator_strategy import AdaptiveMultiIndicatorStrategy


class MultiTimeframeStrategy(BaseForexStrategy):
    """
    Base class for multi-timeframe strategies.

    This strategy analyzes multiple bar sizes:
    - Higher timeframes (1 day, 4 hours) for trend confirmation
    - Lower timeframes (1 hour, 15 mins, 5 mins) for entry/exit signals

    The strategy aligns data from different timeframes and uses them together
    to make trading decisions.
    """

    def __init__(
        self,
        initial_cash=10000,
        commission=0.0002,
        higher_timeframes: List[str] = ["1 day", "4 hours"],
        lower_timeframes: List[str] = ["1 hour", "15 mins"],
        base_strategy_class=None,
    ):
        """
        Initialize multi-timeframe strategy.

        Args:
            initial_cash: Starting capital
            commission: Commission rate
            higher_timeframes: List of bar sizes to use for trend confirmation
            lower_timeframes: List of bar sizes to use for entry/exit signals
            base_strategy_class: The base strategy class to use for signal generation
        """
        super().__init__(initial_cash, commission)
        self.higher_timeframes = higher_timeframes
        self.lower_timeframes = lower_timeframes
        self.base_strategy_class = base_strategy_class or AdaptiveMultiIndicatorStrategy

    def _load_timeframe_data(
        self, base_df: pd.DataFrame, data_dir: str, contract_name: str
    ) -> Dict[str, pd.DataFrame]:
        """
        Load data for all required timeframes.

        Args:
            base_df: The base DataFrame (from the input CSV)
            data_dir: Base directory containing contract folders
            contract_name: Contract name (e.g., "USD-CAD")

        Returns:
            Dictionary mapping bar size to DataFrame
        """
        import os
        import glob

        timeframe_data = {}

        # Extract contract info from base_df or contract_name
        # Try to infer from the CSV path or use contract_name
        contract_folder = os.path.join(data_dir, contract_name)

        if not os.path.exists(contract_folder):
            # Fallback: try to find contract folder
            possible_folders = [
                os.path.join(data_dir, d)
                for d in os.listdir(data_dir)
                if os.path.isdir(os.path.join(data_dir, d))
            ]
            if possible_folders:
                contract_folder = possible_folders[0]

        if not os.path.exists(contract_folder):
            return timeframe_data

        # Bar size to file pattern mapping
        bar_size_patterns = {
            "1 day": "*1 day*.csv",
            "4 hours": "*4 hours*.csv",
            "1 hour": "*1 hour*.csv",
            "15 mins": "*15 mins*.csv",
            "5 mins": "*5 mins*.csv",
            "1 week": "*1 week*.csv",
        }

        all_timeframes = self.higher_timeframes + self.lower_timeframes

        for bar_size in all_timeframes:
            pattern = bar_size_patterns.get(bar_size, f"*{bar_size}*.csv")
            csv_files = glob.glob(os.path.join(contract_folder, pattern))

            if csv_files:
                # Use the first matching file
                try:
                    df = pd.read_csv(csv_files[0], index_col=[0])
                    if not isinstance(df.index, pd.DatetimeIndex):
                        df.index = pd.to_datetime(df.index, errors="coerce")
                    df = df[df.index.notna()]
                    if len(df) > 0:
                        timeframe_data[bar_size] = df
                except Exception as e:
                    print(f"Warning: Could not load {bar_size} data: {e}")
                    continue

        return timeframe_data

    def _align_timeframes(
        self, timeframe_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, pd.DataFrame]:
        """
        Align multiple timeframes to a common index (using the lowest timeframe).

        Args:
            timeframe_data: Dictionary mapping bar size to DataFrame

        Returns:
            Dictionary with aligned DataFrames
        """
        if not timeframe_data:
            return {}

        # Use the lowest timeframe as the base (most granular)
        if self.lower_timeframes:
            base_timeframe = self.lower_timeframes[0]
        else:
            base_timeframe = list(timeframe_data.keys())[0]

        if base_timeframe not in timeframe_data:
            return timeframe_data

        base_df = timeframe_data[base_timeframe]
        base_index = base_df.index

        aligned_data = {base_timeframe: base_df}

        # Align other timeframes to base index using forward fill
        for bar_size, df in timeframe_data.items():
            if bar_size == base_timeframe:
                continue

            # Reindex to base index and forward fill
            aligned_df = df.reindex(base_index, method="ffill")
            aligned_data[bar_size] = aligned_df

        return aligned_data

    def _get_trend_from_higher_timeframe(
        self, aligned_data: Dict[str, pd.DataFrame]
    ) -> pd.Series:
        """
        Determine overall trend from higher timeframes.

        Args:
            aligned_data: Dictionary of aligned DataFrames

        Returns:
            Series with trend signals: 1 for uptrend, -1 for downtrend, 0 for unclear
        """
        trend_signals = pd.Series(0, index=list(aligned_data.values())[0].index)

        for bar_size in self.higher_timeframes:
            if bar_size not in aligned_data:
                continue

            df = aligned_data[bar_size]

            # Check for required indicators
            required_cols = ["adx", "plus_di", "minus_di", "SMA_50", "close"]
            if not all(col in df.columns for col in required_cols):
                continue

            # Trend conditions from higher timeframe
            strong_trend = df["adx"] > 25
            bullish = df["plus_di"] > df["minus_di"]
            bearish = df["minus_di"] > df["plus_di"]
            price_above_sma = df["close"] > df["SMA_50"]
            price_below_sma = df["close"] < df["SMA_50"]

            # Uptrend: strong trend + bullish + price above SMA
            uptrend = strong_trend & bullish & price_above_sma
            # Downtrend: strong trend + bearish + price below SMA
            downtrend = strong_trend & bearish & price_below_sma

            # Combine signals (higher timeframes have more weight)
            trend_signals = trend_signals + (uptrend.astype(int) - downtrend.astype(int))

        # Normalize: if multiple higher timeframes agree, signal is stronger
        # For now, just use sign: >0 = uptrend, <0 = downtrend
        return np.sign(trend_signals)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate signals using multi-timeframe analysis.

        Args:
            df: Base DataFrame (from input CSV, typically the lowest timeframe)

        Returns:
            DataFrame with execute_buy and execute_sell signals
        """
        # This is a base implementation - subclasses should override
        # For now, we'll create a wrapper that uses the base strategy
        # but filters by higher timeframe trend

        # Try to infer contract name and data directory from the DataFrame
        # This is a limitation - we need the data directory and contract name
        # For now, assume they're passed via instance variables or we use defaults

        # Use the base strategy to generate signals on the lower timeframe
        base_strategy = self.base_strategy_class(
            initial_cash=self.initial_cash,
            commission=self.commission,
        )

        # Generate base signals
        df = base_strategy.generate_signals(df)

        # Note: Full multi-timeframe implementation would require:
        # 1. Loading data from multiple bar sizes
        # 2. Aligning them
        # 3. Using higher timeframe for trend filter
        # 4. Using lower timeframe for entry signals

        return df


class AdaptiveMultiTimeframeStrategy(MultiTimeframeStrategy):
    """
    Multi-timeframe version of AdaptiveMultiIndicatorStrategy.

    Uses higher timeframes (1 day, 4 hours) to confirm trend direction,
    and lower timeframes (1 hour, 15 mins) for precise entry/exit signals.
    """

    def __init__(
        self,
        initial_cash=10000,
        commission=0.0002,
        higher_timeframes: List[str] = ["1 day", "4 hours"],
        lower_timeframes: List[str] = ["1 hour", "15 mins"],
        # Parameters from AdaptiveMultiIndicatorStrategy
        adx_trend_threshold=25,
        adx_range_threshold=20,
        rsi_trend_min=40,
        rsi_trend_max=65,
        rsi_oversold=35,
        rsi_overbought=65,
        atr_stop_multiplier=2.0,
        atr_take_profit_multiplier=2.5,
        atr_extreme_multiplier=3.0,
        extrema_lookback=20,
        data_dir: str = "data",
        contract_name: Optional[str] = None,
    ):
        super().__init__(
            initial_cash=initial_cash,
            commission=commission,
            higher_timeframes=higher_timeframes,
            lower_timeframes=lower_timeframes,
        )
        self.adx_trend_threshold = adx_trend_threshold
        self.adx_range_threshold = adx_range_threshold
        self.rsi_trend_min = rsi_trend_min
        self.rsi_trend_max = rsi_trend_max
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.atr_stop_multiplier = atr_stop_multiplier
        self.atr_take_profit_multiplier = atr_take_profit_multiplier
        self.atr_extreme_multiplier = atr_extreme_multiplier
        self.extrema_lookback = extrema_lookback
        self.data_dir = data_dir
        self.contract_name = contract_name

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate multi-timeframe trading signals.

        Strategy:
        1. Load data from higher and lower timeframes
        2. Use higher timeframes to determine overall trend
        3. Use lower timeframe for entry/exit signals
        4. Only take trades in the direction of the higher timeframe trend
        """
        df = df.copy()

        # Contract name must be provided
        contract_name = self.contract_name
        if contract_name is None:
            raise ValueError("contract_name must be provided for multi-timeframe strategy")

        # Load multi-timeframe data
        timeframe_data = self._load_timeframe_data(df, self.data_dir, contract_name)

        if not timeframe_data:
            # Fallback: use single timeframe if multi-timeframe data not available
            print("Warning: Multi-timeframe data not available, using single timeframe")
            base_strategy = AdaptiveMultiIndicatorStrategy(
                initial_cash=self.initial_cash,
                commission=self.commission,
                adx_trend_threshold=self.adx_trend_threshold,
                adx_range_threshold=self.adx_range_threshold,
                rsi_trend_min=self.rsi_trend_min,
                rsi_trend_max=self.rsi_trend_max,
                rsi_oversold=self.rsi_oversold,
                rsi_overbought=self.rsi_overbought,
                atr_stop_multiplier=self.atr_stop_multiplier,
                atr_take_profit_multiplier=self.atr_take_profit_multiplier,
                atr_extreme_multiplier=self.atr_extreme_multiplier,
                extrema_lookback=self.extrema_lookback,
            )
            return base_strategy.generate_signals(df)

        # Align timeframes
        aligned_data = self._align_timeframes(timeframe_data)

        if not aligned_data:
            return df

        # Get trend from higher timeframes
        higher_trend = self._get_trend_from_higher_timeframe(aligned_data)

        # Use the lowest timeframe for entry signals
        if self.lower_timeframes:
            signal_timeframe = self.lower_timeframes[0]
        else:
            signal_timeframe = list(aligned_data.keys())[0]

        if signal_timeframe not in aligned_data:
            return df

        signal_df = aligned_data[signal_timeframe].copy()

        # Generate base signals using AdaptiveMultiIndicatorStrategy logic
        # Import here to avoid circular dependency
        from forex_strategies.adaptive_multi_indicator_strategy import AdaptiveMultiIndicatorStrategy

        base_strategy = AdaptiveMultiIndicatorStrategy(
            initial_cash=self.initial_cash,
            commission=self.commission,
            adx_trend_threshold=self.adx_trend_threshold,
            adx_range_threshold=self.adx_range_threshold,
            rsi_trend_min=self.rsi_trend_min,
            rsi_trend_max=self.rsi_trend_max,
            rsi_oversold=self.rsi_oversold,
            rsi_overbought=self.rsi_overbought,
            atr_stop_multiplier=self.atr_stop_multiplier,
            atr_take_profit_multiplier=self.atr_take_profit_multiplier,
            atr_extreme_multiplier=self.atr_extreme_multiplier,
            extrema_lookback=self.extrema_lookback,
        )

        # Generate signals on the lower timeframe
        signal_df = base_strategy.generate_signals(signal_df)

        # Filter signals by higher timeframe trend
        # Only buy when higher timeframe is uptrend (1) or neutral (0)
        # Only sell when higher timeframe is downtrend (-1) or neutral (0)

        # Align higher_trend to signal_df index
        higher_trend_aligned = higher_trend.reindex(signal_df.index, method="ffill").fillna(0)

        # Filter buy signals: only when higher timeframe is not strongly bearish
        buy_allowed = higher_trend_aligned >= 0  # Uptrend or neutral
        signal_df["execute_buy"] = np.where(
            buy_allowed & signal_df["execute_buy"].notna(),
            signal_df["execute_buy"],
            np.nan,
        )

        # Filter sell signals: only when higher timeframe is not strongly bullish
        sell_allowed = higher_trend_aligned <= 0  # Downtrend or neutral
        signal_df["execute_sell"] = np.where(
            sell_allowed & signal_df["execute_sell"].notna(),
            signal_df["execute_sell"],
            np.nan,
        )

        # Map signals back to original df index
        # The original df might have a different timeframe, so we need to align
        if len(df) != len(signal_df) or not df.index.equals(signal_df.index):
            # Reindex signal_df to match original df index
            # Use forward fill to propagate signals to matching timestamps
            df["execute_buy"] = signal_df["execute_buy"].reindex(df.index, method="ffill")
            df["execute_sell"] = signal_df["execute_sell"].reindex(df.index, method="ffill")
        else:
            df["execute_buy"] = signal_df["execute_buy"]
            df["execute_sell"] = signal_df["execute_sell"]

        return df

