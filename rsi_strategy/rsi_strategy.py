import numpy as np
from backtesting import Backtest

from rsi_strategy.backtesting.Backtesting import BacktestingStrategy
from tester.tester import Tester as MyBacktest

import plotly.graph_objects as go


class RSIStrategy(object):
    def execute(self, df):
        rsi_above_70 = np.where(df["RSI_14"] >= 70, 1, 0)
        rsi_below_30 = np.where(df["RSI_14"] <= 30, 1, 0)
        hist = 5
        for i in range(hist, len(df.index) - hist):
            df.loc[i, "rsi_long_signal"] = (
                True if rsi_below_30[i - hist : i].sum() == hist else False
            )
            df.loc[i, "rsi_short_signal"] = (
                True if rsi_above_70[i - hist : i].sum() == hist else False
            )

        df["rsi_execute_buy"] = np.where(
            df["rsi_long_signal"] == True, df.close + 3 * df.STDEV_30, np.nan
        )
        df["rsi_execute_sell"] = np.where(
            df["rsi_short_signal"] == True, df.close - 3 * df.STDEV_30, np.nan
        )

        cash = 5_000

        def buy_pred_fn(row):
            return row.rsi_execute_buy != np.nan

        def sell_pred_fn(row):
            return row.rsi_execute_sell != np.nan

        MyBacktest().test(df, cash, buy_pred_fn, sell_pred_fn)

        df["Open"] = df.open
        df["Close"] = df.close
        df["High"] = df.high
        df["Low"] = df.low
        bt = Backtest(
            df, BacktestingStrategy, cash=cash, commission=0.0002, exclusive_orders=True
        )
        stat = bt.run()
        print(stat)

        def printStrategyMarkersFn(fig):
            pass
            fig.append_trace(
                go.Scatter(
                    x=df.index,
                    y=df["rsi_execute_buy"],
                    name="Buy Action",
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
                    y=df["rsi_execute_sell"],
                    name="Sell Action",
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
