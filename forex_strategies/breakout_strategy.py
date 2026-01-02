"""
Breakout strategies for forex.
Works well in trending markets after consolidation.
"""
import pandas as pd
import numpy as np
from forex_strategies.base_strategy import BaseForexStrategy


class SupportResistanceBreakout(BaseForexStrategy):
    """
    Breakout strategy using support/resistance levels:
    - Buy on breakout above resistance with volume confirmation
    - Sell on breakdown below support with volume confirmation
    """

    def __init__(
        self,
        initial_cash=10000,
        commission=0.0002,
        lookback_period=20,
        breakout_threshold=0.001,  # 0.1% breakout
    ):
        super().__init__(initial_cash, commission)
        self.lookback_period = lookback_period
        self.breakout_threshold = breakout_threshold

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate breakout signals."""
        df = df.copy()

        # Calculate support and resistance levels
        df["resistance"] = df["high"].rolling(window=self.lookback_period).max()
        df["support"] = df["low"].rolling(window=self.lookback_period).min()

        # Breakout conditions
        df["breakout_up"] = df["close"] > df["resistance"].shift(1) * (
            1 + self.breakout_threshold
        )
        df["breakout_down"] = df["close"] < df["support"].shift(1) * (
            1 - self.breakout_threshold
        )

        # Volume confirmation (if available)
        if "volume" in df.columns:
            df["volume_avg"] = df["volume"].rolling(window=self.lookback_period).mean()
            df["high_volume"] = df["volume"] > df["volume_avg"] * 1.2
            buy_condition = df["breakout_up"] & df["high_volume"]
            sell_condition = df["breakout_down"] & df["high_volume"]
        else:
            buy_condition = df["breakout_up"]
            sell_condition = df["breakout_down"]

        df["execute_buy"] = np.where(buy_condition, df["close"], np.nan)
        df["execute_sell"] = np.where(sell_condition, df["close"], np.nan)

        return df


class ATRBreakout(BaseForexStrategy):
    """
    ATR-based breakout strategy:
    - Uses ATR to determine breakout threshold
    - Buy when price breaks above recent high + ATR
    - Sell when price breaks below recent low - ATR
    """

    def __init__(
        self,
        initial_cash=10000,
        commission=0.0002,
        lookback_period=20,
        atr_multiplier=1.5,
    ):
        super().__init__(initial_cash, commission)
        self.lookback_period = lookback_period
        self.atr_multiplier = atr_multiplier

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate ATR-based breakout signals."""
        df = df.copy()

        if "atr" not in df.columns:
            raise ValueError("atr indicator required")

        # Recent highs and lows
        df["recent_high"] = df["high"].rolling(window=self.lookback_period).max()
        df["recent_low"] = df["low"].rolling(window=self.lookback_period).min()

        # Breakout levels
        df["breakout_level_up"] = df["recent_high"] + (
            df["atr"] * self.atr_multiplier
        )
        df["breakout_level_down"] = df["recent_low"] - (
            df["atr"] * self.atr_multiplier
        )

        # Breakout signals
        df["breakout_up"] = df["close"] > df["breakout_level_up"].shift(1)
        df["breakout_down"] = df["close"] < df["breakout_level_down"].shift(1)

        df["execute_buy"] = np.where(df["breakout_up"], df["close"], np.nan)
        df["execute_sell"] = np.where(df["breakout_down"], df["close"], np.nan)

        return df

