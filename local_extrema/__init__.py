"""Utilities for annotating local minima and maxima in OHLCV CSV files."""

from .local_extrema import (
    LOCAL_MAX,
    LOCAL_MIN,
    add_local_extrema_column,
    annotate_csv_with_local_extrema,
)

