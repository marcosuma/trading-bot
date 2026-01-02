"""Plot helpers for visualising LOCAL_MAX / LOCAL_MIN extrema on price charts.

This module is designed to integrate with the existing Plot class used by the
`fetch-process-plot` command. It provides a small utility class that inspects a
DataFrame for the `local_extrema` column produced by `local_extrema.local_extrema`
(and containing the string labels LOCAL_MAX / LOCAL_MIN) and builds a marker
function compatible with Plot.plot(...).
"""

from __future__ import annotations

from typing import Callable, Optional

import plotly.graph_objects as go
import pandas as pd

from .local_extrema import LOCAL_MAX, LOCAL_MIN


class PlotLocalExtrema:
    """Create Plotly marker functions for LOCAL_MAX / LOCAL_MIN extrema.

    The main entrypoint is :meth:`execute`, which accepts a price DataFrame and
    returns a callable ``fn(fig)`` suitable for passing into ``Plot.plot``.
    If the required ``local_extrema`` column is missing, or if no extrema are
    present, it returns ``None``.
    """

    def __init__(self, column: str = "local_extrema", price_column: str = "close"):
        self.column = column
        self.price_column = price_column

    def execute(self, df: pd.DataFrame) -> Optional[Callable[[go.Figure], None]]:
        """Return a marker function that adds LOCAL_MAX / LOCAL_MIN markers.

        The returned function expects a Plotly ``Figure`` created by
        ``plot.plot.Plot`` (3-row subplot with the price in row 1). It will
        add two scatter traces with marker-only points at the locations of
        local maxima and minima on the first row of the chart.
        """

        if self.column not in df.columns:
            # Nothing to plot; caller can treat this as "no-op".
            return None

        if self.price_column not in df.columns:
            # Malformed input for our purposes; also treat as no-op.
            return None

        extrema = df[self.column]
        price = df[self.price_column]

        max_mask = extrema == LOCAL_MAX
        min_mask = extrema == LOCAL_MIN

        if not max_mask.any() and not min_mask.any():
            return None

        x_max = df.index[max_mask]
        y_max = price[max_mask]
        x_min = df.index[min_mask]
        y_min = price[min_mask]

        def markers_fn(fig: go.Figure) -> None:
            # Plot swing highs as red downward triangles *above* price
            # Shift markers up by +20% of their value so they don't overlap candles.
            if len(x_max):
                y_max_shifted = y_max * 1.01
                fig.add_trace(
                    go.Scatter(
                        x=x_max,
                        y=y_max_shifted,
                        mode="markers",
                        marker=dict(symbol="triangle-down", color="red", size=10),
                        name="LOCAL_MAX",
                        showlegend=False,
                    ),
                    row=1,
                    col=1,
                )

            # Plot swing lows as green upward triangles *below* price
            # Shift markers down by -20% of their value so they don't overlap candles.
            if len(x_min):
                y_min_shifted = y_min * 0.99
                fig.add_trace(
                    go.Scatter(
                        x=x_min,
                        y=y_min_shifted,
                        mode="markers",
                        marker=dict(symbol="triangle-up", color="green", size=10),
                        name="LOCAL_MIN",
                        showlegend=False,
                    ),
                    row=1,
                    col=1,
                )

        return markers_fn

