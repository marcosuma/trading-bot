"""Hammer / Shooting Star candlestick-based forex strategy.

This refactors the original :mod:`hammer_shooting_star.hammer_shooting_star`
into a :class:`BaseForexStrategy`-compatible implementation.

The original logic:

* For each candle, compute the real body size and the lengths of upper
  and lower shadows.
* "Hammer" (bullish) when the lower shadow is much larger than the body
  (``low_open > ratio * body``) on a positive candle (close > open).
* "Shooting star" (bearish) when the upper shadow is much larger than
  the body (``high_open > ratio * body``) on a negative candle
  (close < open).
* The legacy code placed marker prices offset from the candle extremes
  by ``3 * STDEV_30``.

Here we keep the same conditions and map them to ``execute_buy`` and
``execute_sell`` so they can be used with :class:`ForexBacktestingStrategy`.
"""

from typing import List

import numpy as np
import pandas as pd

from forex_strategies.base_strategy import BaseForexStrategy


class HammerShootingStar(BaseForexStrategy):
    """Candlestick pattern strategy using Hammers and Shooting Stars."""

    def __init__(
        self,
        initial_cash: float = 5_000,
        commission: float = 0.0002,
        ratio: float = 10.0,
        stdev_multiplier: float = 3.0,
    ) -> None:
        super().__init__(initial_cash=initial_cash, commission=commission)
        self.ratio = ratio
        self.stdev_multiplier = stdev_multiplier

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate hammer / shooting-star signals.

        Expects at minimum the following columns in ``df``:

        * ``open``, ``high``, ``low``, ``close`` – OHLC prices.
        * ``STDEV_30`` – volatility measure used for price offsets.
        """

        df = df.copy()

        required_cols: List[str] = ["open", "high", "low", "close", "STDEV_30"]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(
                f"Missing required columns for HammerShootingStar: {missing}"
            )

        ratio = self.ratio

        positive = df["open"] < df["close"]
        negative = df["open"] > df["close"]
        body = (df["open"] - df["close"]).abs()
        low_open = (df["low"] - df["open"]).abs()
        high_open = (df["high"] - df["open"]).abs()

        # Hammer is a bullish sign (long)
        df["hammer"] = np.where(
            positive & (low_open > ratio * body),
            df["high"] + self.stdev_multiplier * df["STDEV_30"],
            np.nan,
        )

        # Shooting star is a bearish sign (short)
        df["shooting_star"] = np.where(
            negative & (high_open > ratio * body),
            df["low"] - self.stdev_multiplier * df["STDEV_30"],
            np.nan,
        )

        # Map pattern prices to generic execution fields used by the
        # forex backtesting adapter.
        df["execute_buy"] = df["hammer"]
        df["execute_sell"] = df["shooting_star"]

        return df
