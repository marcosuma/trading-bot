"""\
MARSI-based forex strategy using RSI and MACD.

This refactors the original :mod:`marsi_strategy.marsi_strategy` into a
"proper" forex strategy that follows the same pattern as the other
strategies in :mod:`forex_strategies`.

The core idea is preserved:
    * Use RSI oversold/overbought conditions over a lookback window.
    * Combine them with MACD trend reversals.
    * Place buy/sell executions offset by a volatility measure
      (here, the pre-computed ``STDEV_30`` column).
"""

from typing import Optional

import numpy as np
import pandas as pd

from forex_strategies.base_strategy import BaseForexStrategy


class MARSIStrategy(BaseForexStrategy):
    """Momentum/RSI strategy based on the original MARSI implementation.

    The logic is equivalent to the old :class:`MARSIStrategy` class that
    lived under :mod:`marsi_strategy.marsi_strategy`, but now implemented
    as a :class:`BaseForexStrategy` so it can be used with the generic
    forex backtesting infrastructure (``ForexBacktestingStrategy``,
    ``StrategyTester`` etc.).
    """

    def __init__(
        self,
        initial_cash: float = 5_000,
        commission: float = 0.0002,
        rsi_overbought: float = 70.0,
        rsi_oversold: float = 30.0,
        lookback_bars: int = 7,
    ) -> None:
        """Initialize MARSI strategy.

        Args:
            initial_cash: Starting capital (default matches original MARSI).
            commission: Commission rate per trade.
            rsi_overbought: RSI level considered overbought.
            rsi_oversold: RSI level considered oversold.
            lookback_bars: Number of bars to look back when checking whether
                RSI has been oversold/overbought recently ("hist" in the
                original implementation).
        """

        super().__init__(initial_cash=initial_cash, commission=commission)
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.lookback_bars = lookback_bars

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate buy/sell signals for the MARSI strategy.

        This reproduces the previous behaviour:

        * ``RSI_30_ok`` is true when RSI has been oversold (<= 30) at
          least once in the *preceding* ``lookback_bars`` candles.
        * ``RSI_70_ok`` is true when RSI has been overbought (>= 70) at
          least once in the preceding window.
        * ``macd_trend`` is -1 when MACD is below its signal line,
          +1 otherwise. Buy/sell signals are generated on changes in this
          trend sign.
        * ``execute_buy`` / ``execute_sell`` are placed at
          ``close ± STDEV_30`` when the corresponding combined
          conditions are met.
        """

        df = df.copy()

        required_cols = [
            "RSI_14",
            "macd",
            "macd_s",
            "STDEV_30",
            "close",
        ]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(
                f"Missing required indicators for MARSIStrategy: {missing}"
            )

        # Basic RSI conditions
        rsi = df["RSI_14"]
        rsi_below_30 = rsi <= self.rsi_oversold
        rsi_above_70 = rsi >= self.rsi_overbought

        # Replicate the original loop logic using rolling windows.
        #
        # Original code did, for each index i:
        #   RSI_30_ok[i] = any(rsi_below_30[i-hist : i])
        # i.e. "has RSI been oversold at least once in the *preceding*
        #      `hist` bars?"  We mirror that with rolling + shift.
        window = self.lookback_bars

        below_int = rsi_below_30.astype(int)
        above_int = rsi_above_70.astype(int)

        recent_below = (
            below_int.rolling(window=window, min_periods=1).sum().shift(1)
        )
        recent_above = (
            above_int.rolling(window=window, min_periods=1).sum().shift(1)
        )

        df["RSI_30_ok"] = recent_below.fillna(0).gt(0)
        df["RSI_70_ok"] = recent_above.fillna(0).gt(0)

        # MACD trend and cross detection (same as original logic)
        df["macd_trend"] = np.where(df["macd"] < df["macd_s"], -1, 1)
        macd_trend_sign = np.sign(df["macd_trend"])
        df["macd_buy_signal"] = macd_trend_sign.diff().gt(0)
        df["macd_sell_signal"] = macd_trend_sign.diff().lt(0)

        # Execute buy/sell around close, offset by volatility measure.
        df["execute_buy"] = np.where(
            df["macd_buy_signal"] & df["RSI_30_ok"],
            df["close"] + df["STDEV_30"],
            np.nan,
        )
        df["execute_sell"] = np.where(
            df["macd_sell_signal"] & df["RSI_70_ok"],
            df["close"] - df["STDEV_30"],
            np.nan,
        )

        return df
