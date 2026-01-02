"""
Momentum-based forex strategy using RSI and MACD.
Entry: Strong momentum confirmed by multiple indicators
Exit: Momentum reversal or profit target
"""
import pandas as pd
import numpy as np
from forex_strategies.base_strategy import BaseForexStrategy


class MomentumStrategy(BaseForexStrategy):
    """
    Momentum strategy for forex:
    - Buy when RSI oversold (<30) AND MACD bullish crossover
    - Sell when RSI overbought (>70) AND MACD bearish crossover
    - Uses ATR for stop loss and take profit
    """

    def __init__(
        self,
        initial_cash=10000,
        commission=0.0002,
        rsi_period=14,
        rsi_oversold=30,
        rsi_overbought=70,
        atr_multiplier=2.0,
    ):
        super().__init__(initial_cash, commission)
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.atr_multiplier = atr_multiplier

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate momentum-based trading signals."""
        df = df.copy()

        # Ensure required indicators exist
        required_cols = ["RSI_14", "macd", "macd_s", "atr"]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required indicators: {missing}")

        # MACD signals
        df["macd_above_signal"] = (df["macd"] > df["macd_s"]).fillna(False).astype(bool)
        macd_above_signal_shifted = df["macd_above_signal"].shift(1).fillna(False).astype(bool)
        df["macd_cross_up"] = df["macd_above_signal"] & (~macd_above_signal_shifted)
        df["macd_cross_down"] = (~df["macd_above_signal"]) & macd_above_signal_shifted

        # RSI conditions
        df["rsi_oversold"] = df["RSI_14"] < self.rsi_oversold
        df["rsi_overbought"] = df["RSI_14"] > self.rsi_overbought

        # Buy signal: RSI oversold + MACD bullish crossover
        buy_condition = df["rsi_oversold"] & df["macd_cross_up"]

        # Sell signal: RSI overbought + MACD bearish crossover
        sell_condition = df["rsi_overbought"] & df["macd_cross_down"]

        # Entry prices with ATR-based stops
        df["execute_buy"] = np.where(
            buy_condition, df["close"] + df["atr"] * self.atr_multiplier, np.nan
        )
        df["execute_sell"] = np.where(
            sell_condition, df["close"] - df["atr"] * self.atr_multiplier, np.nan
        )

        return df


class TrendMomentumStrategy(BaseForexStrategy):
    """
    Trend-following momentum strategy:
    - Uses ADX to confirm trend strength
    - EMA crossover for entry
    - RSI for confirmation
    """

    def __init__(
        self,
        initial_cash=10000,
        commission=0.0002,
        adx_threshold=25,
        ema_fast=12,
        ema_slow=26,
        rsi_period=14,
    ):
        super().__init__(initial_cash, commission)
        self.adx_threshold = adx_threshold
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.rsi_period = rsi_period

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate trend-following signals."""
        df = df.copy()

        # Ensure required indicators
        required_cols = ["adx", "EMA_10", "RSI_14", "plus_di", "minus_di"]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required indicators: {missing}")

        # Calculate EMAs if not present
        if f"EMA_{self.ema_fast}" not in df.columns:
            df[f"EMA_{self.ema_fast}"] = df["close"].ewm(span=self.ema_fast).mean()
        if f"EMA_{self.ema_slow}" not in df.columns:
            df[f"EMA_{self.ema_slow}"] = df["close"].ewm(span=self.ema_slow).mean()

        # Trend conditions
        df["strong_trend"] = (df["adx"] > self.adx_threshold).fillna(False).astype(bool)
        df["ema_fast_above_slow"] = (df[f"EMA_{self.ema_fast}"] > df[f"EMA_{self.ema_slow}"]).fillna(False).astype(bool)
        ema_fast_above_slow_shifted = df["ema_fast_above_slow"].shift(1).fillna(False).astype(bool)
        df["ema_cross_up"] = df["ema_fast_above_slow"] & (~ema_fast_above_slow_shifted)
        df["ema_cross_down"] = (~df["ema_fast_above_slow"]) & ema_fast_above_slow_shifted

        # Buy: Strong uptrend + EMA cross up + RSI not overbought + +DI > -DI
        buy_condition = (
            df["strong_trend"]
            & df["ema_cross_up"]
            & (df["RSI_14"] < 70)
            & (df["plus_di"] > df["minus_di"])
        )

        # Sell: Strong downtrend + EMA cross down + RSI not oversold + -DI > +DI
        sell_condition = (
            df["strong_trend"]
            & df["ema_cross_down"]
            & (df["RSI_14"] > 30)
            & (df["minus_di"] > df["plus_di"])
        )

        df["execute_buy"] = np.where(buy_condition, df["close"], np.nan)
        df["execute_sell"] = np.where(sell_condition, df["close"], np.nan)

        return df

