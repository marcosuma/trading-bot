"""
Buy and Hold Strategy - Baseline for comparison

This strategy simply buys at the beginning and holds until the end.
It serves as a baseline to compare more sophisticated strategies against.
"""

import pandas as pd
import numpy as np
from forex_strategies.base_strategy import BaseForexStrategy


class BuyAndHoldStrategy(BaseForexStrategy):
    """
    Simple buy and hold strategy.
    Buys at the first available opportunity and sells at the last bar.
    """

    def __init__(self, initial_cash=10000, commission=0.0002):
        super().__init__(initial_cash, commission)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy signal at the first bar and sell signal at the last bar.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            DataFrame with 'execute_buy' and 'execute_sell' columns
        """
        df = df.copy()

        # Initialize execute_buy and execute_sell columns with NaN
        df["execute_buy"] = np.nan
        df["execute_sell"] = np.nan

        if len(df) == 0:
            return df

        # Buy at the first valid bar (use close price)
        first_idx = df.index[0]
        if "close" in df.columns:
            df.loc[first_idx, "execute_buy"] = df.loc[first_idx, "close"]
        else:
            # Fallback to open if close not available
            df.loc[first_idx, "execute_buy"] = df.loc[first_idx, "open"]

        # Sell at the last valid bar (use close price)
        last_idx = df.index[-1]
        if "close" in df.columns:
            df.loc[last_idx, "execute_sell"] = df.loc[last_idx, "close"]
        else:
            # Fallback to open if close not available
            df.loc[last_idx, "execute_sell"] = df.loc[last_idx, "open"]

        return df

