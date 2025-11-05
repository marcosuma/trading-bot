import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class Plot(object):
    def __init__(self, df, plotsQueue, contract):
        self.df = df
        self.plotsQueue = plotsQueue
        self.contract = contract

    def plot(self, *printStrategyMarkersFns):
        df = self.df
        plotsQueue = self.plotsQueue

        def plotFn():
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, subplot_titles=["{}/{}".format(self.contract.symbol, self.contract.currency), "", ""])
            # price Line
            # Candlestick chart for pricing
            fig.append_trace(
                go.Candlestick(
                    x=df.index,
                    open=df["open"],
                    high=df["high"],
                    low=df["low"],
                    close=df["close"],
                    increasing_line_color="green",
                    decreasing_line_color="red",
                    showlegend=False,
                ),
                row=1,
                col=1,
            )

            for fn in printStrategyMarkersFns:
                if fn is None:
                    continue
                fn(fig)

            # # EMA 10
            # fig.append_trace(
            #     go.Scatter(
            #         x=df.index,
            #         y=df['EMA_10'],
            #         line=dict(color='black', width=2),
            #         name='EMA 10',
            #         # showlegend=False,
            #         legendgroup='2',
            #     ), row=1, col=1
            # )
            # # Bollinger up
            # fig.append_trace(
            #     go.Scatter(
            #         x=df.index,
            #         y=df['bollinger_up'],
            #         line=dict(color='blue', width=2),
            #         name='BB_up',
            #         # showlegend=False,
            #         legendgroup='2',
            #     ), row=1, col=1
            # )
            # # Bollinger down
            # fig.append_trace(
            #     go.Scatter(
            #         x=df.index,
            #         y=df['bollinger_down'],
            #         line=dict(color='blue', width=2),
            #         name='BB_down',
            #         # showlegend=False,
            #         legendgroup='2',
            #     ), row=1, col=1
            # )

            # Make RSI Plot
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["RSI_14"],
                    line=dict(color="#ff9900", width=2),
                    showlegend=False,
                ),
                row=2,
                col=1,
            )
            # Add upper/lower bounds
            fig.update_yaxes(range=[-10, 110], row=2, col=1)
            fig.add_hline(y=0, col=1, row=2, line_color="#666", line_width=2)
            fig.add_hline(y=100, col=1, row=2, line_color="#666", line_width=2)
            # Add overbought/oversold
            fig.add_hline(
                y=30, col=1, row=2, line_color="#336699", line_width=2, line_dash="dash"
            )
            fig.add_hline(
                y=70, col=1, row=2, line_color="#336699", line_width=2, line_dash="dash"
            )

            # plotMACD(fig, 3, 1)

            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["adx"],
                    line=dict(color="#2196f3", width=2),
                    showlegend=False,
                ),
                row=3,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["plus_di"],
                    line=dict(color=self.__hex_to_rgba("#26a69a", 0.3), width=1),
                    showlegend=False,
                ),
                row=3,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["minus_di"],
                    line=dict(color=self.__hex_to_rgba("#f44336", 0.3), width=1),
                    showlegend=False,
                ),
                row=3,
                col=1,
            )

            # Make it pretty
            layout = go.Layout(
                plot_bgcolor="#efefef",
                # Font Families
                font_family="Monospace",
                font_color="#000000",
                font_size=20,
                xaxis=dict(rangeslider=dict(visible=False)),
            )
            # Update options and show plot
            fig.update_layout(layout)
            fig.show()

        def plotMACD(fig, row, col):
            # MACD
            # Fast Signal (%k)
            fig.append_trace(
                go.Scatter(
                    x=df.index,
                    y=df["macd"],
                    line=dict(color="#ff9900", width=2),
                    name="macd",
                    # showlegend=False,
                    legendgroup="2",
                ),
                row=row,
                col=col,
            )
            # Slow signal (%d)
            fig.append_trace(
                go.Scatter(
                    x=df.index,
                    y=df["macd_s"],
                    line=dict(color="#000000", width=2),
                    # showlegend=False,
                    legendgroup="2",
                    name="signal",
                ),
                row=row,
                col=col,
            )
            # Colorize the histogram values
            colors = np.where(df["macd_h"] < 0, "red", "green")
            # Plot the histogram
            fig.append_trace(
                go.Bar(
                    x=df.index,
                    y=df["macd_h"],
                    name="histogram",
                    marker_color=colors,
                ),
                row=row,
                col=col,
            )

        plotsQueue.append(plotFn)

    def __hex_to_rgba(self, h, alpha):
        """
        converts color value in hex format to rgba format with alpha transparency
        """
        return "rgba" + str(
            tuple([int(h.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)] + [alpha])
        )
