import collections
import math
import statistics
import numpy as np
import pandas as pd

import matplotlib.pyplot as plt

from scipy.signal import argrelextrema
import plotly.graph_objects as go
from sklearn.cluster import KMeans

colors = [
    "#fff100",
    "#ff8c00",
    "#e81123",
    "#ec008c",
    "#68217a",
    "#00188f",
    "#00bcf2",
    "#00b294",
    "#009e49",
    "#bad80a",
]


class SupportResistanceV1(object):
    def __init__(self, plotsQueue, fileToSave):
        self.plotsQueue = plotsQueue
        self.fileToSave = fileToSave
        pass

    def execute(self, df):
        # __fn_impl returns (marker_fn, y_lines) tuple
        marker_fn, y_lines = self.__fn_impl(df)
        # df.to_csv(self.fileToSave)
        return marker_fn, y_lines

    def __cluster_values(self, values):
        # Choose number of clusters up to 6 but not more than the number
        # of available points, to avoid sklearn complaining when
        # n_samples < n_clusters.
        K = min(6, len(values))
        kmeans = KMeans(n_clusters=K, n_init=K).fit(values.reshape(-1, 1))

        # predict which cluster each price is in
        clusters = kmeans.predict(values.reshape(-1, 1))
        return clusters

    def __fn_impl(self, df: pd.DataFrame):
        n = 200  # number of points to be checked before and after
        df["min"] = df.iloc[
            argrelextrema(df["close"].values, np.less_equal, order=n)[0]
        ]["close"]
        df["max"] = df.iloc[
            argrelextrema(df["close"].values, np.greater_equal, order=n)[0]
        ]["close"]

        # Extract non-null local minima and maxima as 1D float Series
        min_values = df["min"].dropna()
        max_values = df["max"].dropna()

        # Combine minima and maxima into a single Series ordered by index
        # (time). This avoids using Series.combine + math.isnan, which can
        # end up feeding whole Series objects into math.isnan and trigger
        # "cannot convert the series to <class 'float'>" errors.
        min_max = pd.concat([min_values, max_values]).sort_index()

        # Convert to a plain 1D numpy array of floats for KMeans
        values = np.asarray(min_max, dtype=float)

        # If we have fewer points than K, reduce K to avoid sklearn errors
        if values.size == 0:
            # No levels detected; return a no-op marker function
            def empty_markers(fig):
                return

            return empty_markers, []

        clusters = self.__cluster_values(values)
        min_max_values = pd.DataFrame({"values": min_max})
        min_max_values["cluster"] = clusters.tolist()
        min_max_values["color"] = min_max_values.apply(
            lambda row: colors[int(row.cluster)], axis=1
        )

        values_by_cluster = collections.defaultdict(lambda: [])
        for i, cluster in enumerate(clusters):
            values_by_cluster[cluster].append(min_max.tolist()[i])

        avgs = []
        for cluster in values_by_cluster:
            values = values_by_cluster[cluster]
            avgs.append(statistics.mean(values))

        def printStrategyMarkersFn(fig):
            for avg in avgs:
                fig.add_hline(y=avg)

        return printStrategyMarkersFn, avgs
