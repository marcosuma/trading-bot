"""
Combined Pattern and Triangle Strategy with Filters.

This strategy combines:
- Chart pattern detection (Head & Shoulders, Triangles, Rectangles)
- Triangle breakout detection
- Technical indicator filters (ADX, RSI, Volume)

Only trades when patterns/triangles are confirmed by indicator filters.
"""
import pandas as pd
import numpy as np
from forex_strategies.base_strategy import BaseForexStrategy
from forex_strategies.pattern_strategy import PatternStrategy
from forex_strategies.triangle_strategy import TriangleStrategy


class PatternTriangleStrategy(BaseForexStrategy):
    """
    Combined pattern and triangle strategy with indicator filters.

    Strategy Logic:
    1. Detect patterns (HS, IHS, Triangles, Rectangles)
    2. Detect triangle breakouts
    3. Apply filters:
       - ADX: Only trade in trending markets (ADX > 20)
       - RSI: Avoid extreme overbought/oversold (30 < RSI < 70)
       - Volume: Confirm with volume if available
    4. Generate signals only when pattern/triangle + filters align
    """

    def __init__(
        self,
        initial_cash=10000,
        commission=0.0002,
        # Pattern detection parameters
        max_bars=35,
        prominence_factor=0.5,
        min_distance=5,
        # Triangle detection parameters
        backcandles=100,
        pivot_lookback=3,
        pivot_lookforward=3,
        # Filter parameters
        adx_min=20,
        rsi_min=30,
        rsi_max=70,
        volume_multiplier=1.2,
    ):
        super().__init__(initial_cash, commission)

        # Initialize sub-strategies
        self.pattern_strategy = PatternStrategy(
            initial_cash=initial_cash,
            commission=commission,
            max_bars=max_bars,
            prominence_factor=prominence_factor,
            min_distance=min_distance,
        )
        self.triangle_strategy = TriangleStrategy(
            initial_cash=initial_cash,
            commission=commission,
            backcandles=backcandles,
            pivot_lookback=pivot_lookback,
            pivot_lookforward=pivot_lookforward,
        )

        # Filter parameters
        self.adx_min = adx_min
        self.rsi_min = rsi_min
        self.rsi_max = rsi_max
        self.volume_multiplier = volume_multiplier

    def _apply_filters(self, df: pd.DataFrame, signal_type: str) -> pd.Series:
        """
        Apply technical indicator filters to signals.

        Args:
            df: DataFrame with indicators
            signal_type: 'buy' or 'sell'

        Returns:
            Boolean Series indicating which signals pass filters
        """
        filter_mask = pd.Series(True, index=df.index)

        # ADX filter: Only trade in trending markets
        if "adx" in df.columns:
            filter_mask = filter_mask & (df["adx"] > self.adx_min)
        else:
            # If ADX not available, allow all signals
            pass

        # RSI filter: Avoid extreme conditions
        if "RSI_14" in df.columns:
            if signal_type == "buy":
                # For buy signals, RSI should not be overbought
                filter_mask = filter_mask & (df["RSI_14"] < self.rsi_max)
            elif signal_type == "sell":
                # For sell signals, RSI should not be oversold
                filter_mask = filter_mask & (df["RSI_14"] > self.rsi_min)
        else:
            # If RSI not available, allow all signals
            pass

        # Volume filter: Confirm with volume if available
        if "volume" in df.columns:
            volume_avg = df["volume"].rolling(window=20).mean()
            high_volume = df["volume"] > (volume_avg * self.volume_multiplier)
            filter_mask = filter_mask & high_volume
        else:
            # If volume not available, skip volume filter
            pass

        return filter_mask

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate filtered trading signals from patterns and triangles."""
        df = df.copy()

        # Initialize signal columns
        df["execute_buy"] = np.nan
        df["execute_sell"] = np.nan

        # Get signals from pattern strategy
        try:
            pattern_df = self.pattern_strategy.generate_signals(df.copy())
            pattern_buy_signals = pattern_df["execute_buy"].notna()
            pattern_sell_signals = pattern_df["execute_sell"].notna()
        except Exception as e:
            print(f"Warning: Pattern detection failed: {e}")
            pattern_buy_signals = pd.Series(False, index=df.index)
            pattern_sell_signals = pd.Series(False, index=df.index)

        # Get signals from triangle strategy
        try:
            triangle_df = self.triangle_strategy.generate_signals(df.copy())
            triangle_buy_signals = triangle_df["execute_buy"].notna()
            triangle_sell_signals = triangle_df["execute_sell"].notna()
        except Exception as e:
            print(f"Warning: Triangle detection failed: {e}")
            triangle_buy_signals = pd.Series(False, index=df.index)
            triangle_sell_signals = pd.Series(False, index=df.index)

        # Combine pattern and triangle signals
        combined_buy_signals = pattern_buy_signals | triangle_buy_signals
        combined_sell_signals = pattern_sell_signals | triangle_sell_signals

        # Apply filters to buy signals
        buy_filter_mask = self._apply_filters(df, "buy")
        filtered_buy_signals = combined_buy_signals & buy_filter_mask

        # Apply filters to sell signals
        sell_filter_mask = self._apply_filters(df, "sell")
        filtered_sell_signals = combined_sell_signals & sell_filter_mask

        # Set execute_buy signals
        buy_indices = df.index[filtered_buy_signals]
        if len(buy_indices) > 0:
            df.loc[buy_indices, "execute_buy"] = df.loc[buy_indices, "close"]

        # Set execute_sell signals
        sell_indices = df.index[filtered_sell_signals]
        if len(sell_indices) > 0:
            df.loc[sell_indices, "execute_sell"] = df.loc[sell_indices, "close"]

        return df

