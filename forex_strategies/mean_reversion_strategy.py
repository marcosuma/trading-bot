"""
Mean reversion strategies for forex.
Works well in ranging markets.
"""
import pandas as pd
import numpy as np
from forex_strategies.base_strategy import BaseForexStrategy


class BollingerBandsMeanReversion(BaseForexStrategy):
    """
    Mean reversion using Bollinger Bands:
    - Buy when price touches lower band and RSI oversold
    - Sell when price touches upper band and RSI overbought
    """

    def __init__(
        self,
        initial_cash=10000,
        commission=0.0002,
        rsi_oversold=30,
        rsi_overbought=70,
        bb_std=2.0,
    ):
        super().__init__(initial_cash, commission)
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.bb_std = bb_std

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate mean reversion signals."""
        df = df.copy()

        required_cols = ["bollinger_up", "bollinger_down", "RSI_14", "SMA_50"]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required indicators: {missing}")

        # Price relative to bands
        df["at_lower_band"] = df["close"] <= df["bollinger_down"]
        df["at_upper_band"] = df["close"] >= df["bollinger_up"]

        # RSI conditions
        df["rsi_oversold"] = df["RSI_14"] < self.rsi_oversold
        df["rsi_overbought"] = df["RSI_14"] > self.rsi_overbought

        # Buy: Price at lower band + RSI oversold + price below SMA (downtrend bounce)
        buy_condition = (
            df["at_lower_band"] & df["rsi_oversold"] & (df["close"] < df["SMA_50"])
        )

        # Sell: Price at upper band + RSI overbought + price above SMA (uptrend rejection)
        sell_condition = (
            df["at_upper_band"] & df["rsi_overbought"] & (df["close"] > df["SMA_50"])
        )

        df["execute_buy"] = np.where(buy_condition, df["close"], np.nan)
        df["execute_sell"] = np.where(sell_condition, df["close"], np.nan)

        return df


class RSI2MeanReversion(BaseForexStrategy):
    """
    Simple RSI mean reversion:
    - Buy when RSI < 30
    - Sell when RSI > 70
    - Works best in ranging markets
    """

    def __init__(
        self,
        initial_cash=10000,
        commission=0.0002,
        rsi_period=14,
        rsi_oversold=30,
        rsi_overbought=70,
    ):
        super().__init__(initial_cash, commission)
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate RSI mean reversion signals."""
        df = df.copy()

        if "RSI_14" not in df.columns:
            raise ValueError("RSI_14 indicator required")

        # Simple RSI signals
        df["rsi_oversold"] = df["RSI_14"] < self.rsi_oversold
        df["rsi_overbought"] = df["RSI_14"] > self.rsi_overbought

        # Buy when RSI crosses above oversold
        df["rsi_cross_above_oversold"] = (
            (df["RSI_14"] >= self.rsi_oversold)
            & (df["RSI_14"].shift(1) < self.rsi_oversold)
        )

        # Sell when RSI crosses below overbought
        df["rsi_cross_below_overbought"] = (
            (df["RSI_14"] <= self.rsi_overbought)
            & (df["RSI_14"].shift(1) > self.rsi_overbought)
        )

        df["execute_buy"] = np.where(
            df["rsi_cross_above_oversold"], df["close"], np.nan
        )
        df["execute_sell"] = np.where(
            df["rsi_cross_below_overbought"], df["close"], np.nan
        )

        return df

