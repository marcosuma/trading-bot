"""
Triangle-based trading strategy.

Detects triangle patterns (ascending, descending, symmetrical) and generates
trading signals based on triangle breakouts.
"""
import pandas as pd
import numpy as np
from scipy.stats import linregress
from forex_strategies.base_strategy import BaseForexStrategy


class TriangleStrategy(BaseForexStrategy):
    """
    Strategy that trades based on triangle pattern breakouts.

    Detects triangles using pivot points and linear regression:
    - Buy on breakout above upper trendline (resistance)
    - Sell on breakdown below lower trendline (support)
    """

    def __init__(
        self,
        initial_cash=10000,
        commission=0.0002,
        backcandles=100,
        pivot_lookback=3,
        pivot_lookforward=3,
    ):
        super().__init__(initial_cash, commission)
        self.backcandles = backcandles
        self.pivot_lookback = pivot_lookback
        self.pivot_lookforward = pivot_lookforward

    def _pivotid(self, df: pd.DataFrame, l: int, n1: int, n2: int):
        """Identify pivot points (swing highs and lows)."""
        if l - n1 < 0 or l + n2 >= len(df):
            return 0

        pividlow = 1
        pividhigh = 1
        for i in range(l - n1, l + n2 + 1):
            if df.iloc[l]["low"] > df.iloc[i]["low"]:
                pividlow = 0
            if df.iloc[l]["high"] < df.iloc[i]["high"]:
                pividhigh = 0

        if pividlow and pividhigh:
            return 3
        elif pividlow:
            return 1  # Pivot low
        elif pividhigh:
            return 2  # Pivot high
        else:
            return 0

    def _check_if_triangle(self, candleid: int, backcandles: int, df: pd.DataFrame):
        """Check if a triangle pattern exists at the given candle."""
        maxim = np.array([])
        minim = np.array([])
        xxmin = np.array([])
        xxmax = np.array([])

        for i in range(candleid - backcandles, candleid + 1):
            if df.iloc[i]["pivot"] == 1:  # Pivot low
                minim = np.append(minim, float(df.iloc[i]["low"]))
                xxmin = np.append(xxmin, i)
            if df.iloc[i]["pivot"] == 2:  # Pivot high
                maxim = np.append(maxim, float(df.iloc[i]["high"]))
                xxmax = np.append(xxmax, i)

        if (xxmax.size < 5 and xxmin.size < 5) or xxmax.size == 0 or xxmin.size == 0:
            raise ValueError("No triangle found - insufficient pivot points")

        # Linear regression on pivot points
        slmin, intercmin, rmin, pmin, semin = linregress(xxmin, minim)
        slmax, intercmax, rmax, pmax, semax = linregress(xxmax, maxim)

        # Triangle condition: converging trendlines
        # Support slope >= 0 (rising or flat), Resistance slope <= 0 (falling or flat)
        if (slmin >= 0 and slmax < 0) or (slmin > 0 and slmax <= 0):
            return slmin, intercmin, slmax, intercmax, xxmin, xxmax

        raise ValueError("No triangle found - trendlines not converging")

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate trading signals based on triangle breakouts."""
        df = df.copy()

        # Store original index
        original_index = df.index.copy()

        # Reset index for easier integer-based access
        df = df.reset_index(drop=True)

        # Initialize signal columns
        df["execute_buy"] = np.nan
        df["execute_sell"] = np.nan

        # Find pivot points
        df["pivot"] = df.apply(
            lambda x: self._pivotid(df, x.name, self.pivot_lookback, self.pivot_lookforward),
            axis=1,
        )

        # Detect triangles and generate signals
        candleid = self.backcandles
        while candleid < len(df) - 1:
            try:
                slmin, intercmin, slmax, intercmax, xxmin, xxmax = self._check_if_triangle(
                    candleid, self.backcandles, df
                )

                # Calculate trendline values at current candle
                upper_line = slmax * candleid + intercmax
                lower_line = slmin * candleid + intercmin

                current_close = df.iloc[candleid]["close"]
                current_high = df.iloc[candleid]["high"]
                current_low = df.iloc[candleid]["low"]

                # Buy signal: Breakout above upper trendline (resistance)
                if current_close > upper_line or current_high > upper_line:
                    df.iloc[candleid, df.columns.get_loc("execute_buy")] = current_close

                # Sell signal: Breakdown below lower trendline (support)
                if current_close < lower_line or current_low < lower_line:
                    df.iloc[candleid, df.columns.get_loc("execute_sell")] = current_close

                # Move forward
                candleid += int(self.backcandles * 0.5)

            except ValueError:
                # No triangle found, continue
                candleid += 1
                continue
            except Exception as e:
                # Other error, skip
                candleid += 1
                continue

        # Restore original index
        df.index = original_index

        return df

