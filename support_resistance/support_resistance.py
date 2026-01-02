import numpy as np
import pandas as pd
import plotly.graph_objects as go
from sklearn.cluster import KMeans


class SupportResistance(object):
    def __init__(self, candlestickData, plotsQueue, fileToSave):
        self.candlestickData = candlestickData
        self.plotsQueue = plotsQueue
        self.fileToSave = fileToSave
        pass

    def process_data_with_file(self, df):
        print("Data loaded from file")
        self.__fn_impl(df)

    # Uses LSTM (Long Short Term Memory) to predict the closing price of an asset
    # Uses past 60 days
    def process_data(self, reqId: int, start: str, end: str):
        df = pd.DataFrame(
            data=np.array(self.candlestickData),
            columns=["date", "open", "close", "high", "low", "volume"],
        )
        df["close"] = df["close"].astype(float)
        # df.to_csv(self.fileToSave)
        # print(df)

        self.__fn_impl(df)

    def __fn_impl(self, df: pd.DataFrame):
        prices = np.array(df["close"])
        K = 4
        kmeans = KMeans(n_clusters=K).fit(prices.reshape(-1, 1))

        # predict which cluster each price is in
        clusters = kmeans.predict(prices.reshape(-1, 1))
        print("Clusters:\n", clusters)

        # Create list to hold values, initialized with infinite values
        min_max_values = []
        # init for each cluster group
        for i in range(K):
            # Add values for which no price could be greater or less
            min_max_values.append([np.inf, -np.inf])
        # Print initial values
        print(min_max_values)
        # Get min/max for each cluster
        for i in range(len(df["close"])):
            # Get cluster assigned to price
            cluster = clusters[i]
            # Compare for min value
            if df["close"][i] < min_max_values[cluster][0]:
                min_max_values[cluster][0] = df["close"][i]
            # Compare for max value
            if df["close"][i] > min_max_values[cluster][1]:
                min_max_values[cluster][1] = df["close"][i]
        # Print resulting values
        print(min_max_values)

        # Create container for combined values
        output = []
        # Sort based on cluster minimum
        s = sorted(min_max_values, key=lambda x: x[0])
        # For each cluster get average of
        for i, (_min, _max) in enumerate(s):
            # Append min from first cluster
            if i == 0:
                output.append(_min)
            # Append max from last cluster
            if i == len(min_max_values) - 1:
                output.append(_max)
            # Append average from cluster and adjacent for all others
            else:
                output.append(sum([_max, s[i + 1][0]]) / 2)

        def plot_fn():
            # Assigns plotly as visualization engine
            pd.options.plotting.backend = "plotly"
            # Arbitrarily 6 colors for our 6 clusters
            colors = ["red", "orange", "yellow", "green", "blue", "indigo"]
            # Create Scatter plot, assigning each point a color based
            # on it's grouping where group_number == index of color.
            fig = df.plot.scatter(
                x=df.index,
                y="close",
                color=[colors[i] for i in clusters],
            )

            # # Add horizontal lines
            # for cluster_min, cluster_max in min_max_values:
            #     fig.add_hline(y=cluster_min, line_width=1, line_color="blue")
            #     fig.add_hline(y=cluster_max, line_width=1, line_color="blue")
            # Add horizontal lines
            for cluster_avg in output:
                fig.add_hline(y=cluster_avg, line_width=1, line_color="blue")

            # Add a trace of the price for better clarity
            fig.add_trace(
                go.Trace(x=df.index, y=df["close"], line_color="black", line_width=1)
            )

            # Configure some styles
            layout = go.Layout(
                plot_bgcolor="#efefef",
                showlegend=False,
                # Font Families
                font_family="Monospace",
                font_color="#000000",
                font_size=20,
                xaxis=dict(rangeslider=dict(visible=False)),
            )
            fig.update_layout(layout)
            # Display plot in local browser window
            fig.show()

        self.plotsQueue.append(plot_fn)
