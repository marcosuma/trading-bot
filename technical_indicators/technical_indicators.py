import numpy as np
import pandas as pd

from technical_indicators.sma.sma import SMA
from technical_indicators.ema.ema import EMA
from technical_indicators.rsi.rsi import RSI
from technical_indicators.macd.macd import MACD
from technical_indicators.adx.adx import ADX
from technical_indicators.bollinger_bands.bollinger_bands import BollingerBands
from technical_indicators.atr.atr import ATR
from technical_indicators.local_extrema.local_extrema import LocalExtrema


class TechnicalIndicators(object):
    def __init__(self, candlestickData, fileToSave):
        self.candlestickData = candlestickData
        self.fileToSave = fileToSave
        pass

    def execute(self, df) -> pd.DataFrame:
        self.__fn_impl(df)
        df.to_csv(self.fileToSave) if self.fileToSave is not None else None
        return df

    def __fn_impl(self, df: pd.DataFrame):
        # Ensure numeric OHLCV types to avoid issues when CSVs or
        # external sources load them as strings.
        for col in ["open", "close", "high", "low", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df["shifted_open"] = df.open.shift(-1)

        SMA().calculate(df)
        EMA().calculate(df)
        RSI().calculate(df)
        MACD().calculate(df)
        ADX().calculate(df)
        ATR().calculate(df)
        BollingerBands().calculate(df)
        LocalExtrema().calculate(df)

        # from stockstats import wrap
        # ss_df = wrap(df)


"""
# View our data
        pd.set_option("display.max_columns", None)
        print(df)

        def plotFn():
            # Construct a 2 x 1 Plotly figure
            fig = make_subplots(rows=2, cols=1)
            # price Line
            fig.append_trace(
                go.Scatter(
                    x=df.index,
                    y=df['open'],
                    line=dict(color='#ff9900', width=1),
                    name='open',
                    # showlegend=False,
                    legendgroup='1',
                ), row=1, col=1
            )
            # Candlestick chart for pricing
            fig.append_trace(
                go.Candlestick(
                    x=df.index,
                    open=df['open'],
                    high=df['high'],
                    low=df['low'],
                    close=df['close'],
                    increasing_line_color='#ff9900',
                    decreasing_line_color='black',
                    showlegend=False
                ), row=1, col=1
            )





            # Make it pretty
            layout = go.Layout(
                plot_bgcolor='#efefef',
                # Font Families
                font_family='Monospace',
                font_color='#000000',
                font_size=20,
                xaxis=dict(
                    rangeslider=dict(
                        visible=False
                    )
                )
            )
            # Update options and show plot
            fig.update_layout(layout)
            fig.show()

        self.plotsQueue.append(plotFn)
"""
