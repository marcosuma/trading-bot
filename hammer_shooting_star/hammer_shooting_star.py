import numpy as np
from backtesting import Backtest

from rsi_strategy.backtesting.Backtesting import BacktestingStrategy
from tester.tester import Tester as MyBacktest

import plotly.graph_objects as go


class HammerShootingStar(object):
    def execute(self, df):
        ratio = 10
        for i in range(len(df.index)):
            positive = df.loc[i, "open"] < df.loc[i, "close"]
            negative = df.loc[i, "open"] > df.loc[i, "close"]
            body = abs(df.loc[i, "open"] - df.loc[i, "close"])
            low_open = abs(df.loc[i, "low"] - df.loc[i, "open"])
            high_open = abs(df.loc[i, "high"] - df.loc[i, "open"])
            # shooting star is a bearish sign (short)
            df.loc[i, "shooting_star"] = (
                df.loc[i, "low"] - 3 * df.loc[i, "STDEV_30"]
                if negative and high_open > ratio * body
                else np.nan
            )
            # hammer is a bullish sign (long)
            df.loc[i, "hammer"] = (
                df.loc[i, "high"] + 3 * df.loc[i, "STDEV_30"]
                if positive and low_open > ratio * body
                else np.nan
            )

        def printStrategyMarkersFn(fig):
            pass
            fig.append_trace(
                go.Scatter(
                    x=df.index,
                    y=df["hammer"],
                    name="Hammer",
                    # showlegend=False,
                    legendgroup="2",
                    mode="markers",
                    marker=dict(
                        color="green",
                        line=dict(color="green", width=2),
                        symbol="triangle-down",
                    ),
                    connectgaps=False,
                ),
                row=1,
                col=1,
            )
            fig.append_trace(
                go.Scatter(
                    x=df.index,
                    y=df["shooting_star"],
                    name="Shooting star",
                    # showlegend=False,
                    legendgroup="2",
                    mode="markers",
                    marker=dict(
                        color="red",
                        line=dict(color="red", width=2),
                        symbol="triangle-up",
                    ),
                ),
                row=1,
                col=1,
            )

        return printStrategyMarkersFn
