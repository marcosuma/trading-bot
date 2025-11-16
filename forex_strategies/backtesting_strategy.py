"""
Backtesting strategy class for forex strategies.
"""
from backtesting import Strategy
import numpy as np
import pandas as pd


class ForexBacktestingStrategy(Strategy):
    """Generic backtesting strategy that uses execute_buy and execute_sell signals."""

    def init(self):
        super().init()

    def next(self):
        super().next()

        # Check for buy signal
        if hasattr(self.data, "execute_buy"):
            buy_signal = self.data.execute_buy[-1]
            if not pd.isna(buy_signal):
                if not self.position or not self.position.is_long:
                    self.buy()

        # Check for sell signal
        if hasattr(self.data, "execute_sell"):
            sell_signal = self.data.execute_sell[-1]
            if not pd.isna(sell_signal):
                if not self.position or not self.position.is_short:
                    self.sell()

