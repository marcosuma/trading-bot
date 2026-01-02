import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import matplotlib.pyplot as plt


class MACD(object):
    def calculate(self, df: pd.DataFrame):
        # Get the 26-day EMA of the closing price
        k = df["close"].ewm(span=12, adjust=False, min_periods=12).mean()
        # Get the 12-day EMA of the closing price
        d = df["close"].ewm(span=26, adjust=False, min_periods=26).mean()
        # Subtract the 26-day EMA from the 12-Day EMA to get the MACD
        macd = k - d
        # Get the 9-Day EMA of the MACD for the Trigger line
        macd_s = macd.ewm(span=9, adjust=False, min_periods=9).mean()
        # Calculate the difference between the MACD - Trigger for the Convergence/Divergence value
        macd_h = macd - macd_s
        # Add all of our new values for the MACD to the dataframe.
        # NOTE: assign directly instead of using df.index.map(...) to avoid
        # pandas "Reindexing only valid with uniquely valued Index objects"
        # when the index contains duplicate timestamps (common in some
        # aggregated timeframes like 1 day).
        df["macd"] = macd
        df["macd_h"] = macd_h
        df["macd_s"] = macd_s
