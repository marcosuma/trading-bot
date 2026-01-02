"""RSI-based forex strategy.

This refactors the original :mod:`rsi_strategy.rsi_strategy.RSIStrategy`
into a proper forex strategy that follows the common interface defined by
``BaseForexStrategy``.

The idea is:

* Look for *persistent* RSI extremes: RSI has been oversold (<= 30) or
  overbought (>= 70) for a consecutive number of bars.
* When RSI has been oversold for ``hist`` bars in a row, place a
  volatility-buffered **buy** execution above the current close.
* When RSI has been overbought for ``hist`` bars in a row, place a
  volatility-buffered **sell** execution below the current close.

The volatility buffer uses the pre-computed ``STDEV_30`` column, just
like the legacy implementation.
"""

from typing import List

import numpy as np
import pandas as pd

from forex_strategies.base_strategy import BaseForexStrategy


class RSIStrategy(BaseForexStrategy):
    """RSI extreme strategy based on consecutive oversold/overbought bars.

    This mirrors the behaviour of the legacy :class:`RSIStrategy` class
    under :mod:`rsi_strategy.rsi_strategy`:

    * ``rsi_long_signal`` is true when ``RSI_14`` has been below or equal
      to ``rsi_oversold`` for ``hist`` *consecutive* bars *preceding* the
      current bar.
    * ``rsi_short_signal`` is true when ``RSI_14`` has been above or equal
      to ``rsi_overbought`` for ``hist`` consecutive preceding bars.
    * ``execute_buy`` / ``execute_sell`` are placed at
      ``close ± stdev_multiplier * STDEV_30`` when the corresponding
      signals are active.
    """

    def __init__(
        self,
        initial_cash: float = 5_000,
        commission: float = 0.0002,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        hist: int = 5,
        stdev_multiplier: float = 3.0,
    ) -> None:
        super().__init__(initial_cash=initial_cash, commission=commission)
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.hist = hist
        self.stdev_multiplier = stdev_multiplier

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate RSI-based buy/sell signals.

        Expects at minimum the following columns in ``df``:

        * ``RSI_14`` – RSI indicator.
        * ``STDEV_30`` – 30-period standard deviation (volatility proxy).
        * ``close`` – close price.
        """

        df = df.copy()

        required_cols: List[str] = ["RSI_14", "STDEV_30", "close"]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(
                f"Missing required indicators for RSIStrategy: {missing}"
            )

        rsi = df["RSI_14"]
        rsi_below = rsi <= self.rsi_oversold
        rsi_above = rsi >= self.rsi_overbought

        # Replicate the original loop logic using vectorised rolling
        # windows. The legacy code did, for each index i:
        #
        #   rsi_long_signal[i]  = all(rsi_below[i-hist : i])
        #   rsi_short_signal[i] = all(rsi_above[i-hist : i])
        #
        # i.e. it examined the *preceding* ``hist`` bars (excluding the
        # current bar). We can achieve the same effect by computing a
        # rolling sum over ``hist`` bars and then shifting by one.
        window = self.hist

        below_int = rsi_below.astype(int)
        above_int = rsi_above.astype(int)

        below_run = below_int.rolling(window=window, min_periods=window).sum()
        above_run = above_int.rolling(window=window, min_periods=window).sum()

        df["rsi_long_signal"] = below_run.shift(1) == window
        df["rsi_short_signal"] = above_run.shift(1) == window

        # Execution prices: volatility-buffered entries around close.
        df["execute_buy"] = np.where(
            df["rsi_long_signal"],
            df["close"] + self.stdev_multiplier * df["STDEV_30"],
            np.nan,
        )
        df["execute_sell"] = np.where(
            df["rsi_short_signal"],
            df["close"] - self.stdev_multiplier * df["STDEV_30"],
            np.nan,
        )

        return df
