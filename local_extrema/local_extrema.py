"""Detection and annotation of local minima and maxima in price series.

This module operates on CSV files like the ones under the `data/` folder.
It adds a column that marks each row as a local minimum, local maximum,
or neither.

NOTE: This module is maintained for backward compatibility. The actual
implementation has been moved to technical_indicators.local_extrema.local_extrema
as a proper technical indicator class. The constants LOCAL_MAX and LOCAL_MIN
are defined here and re-exported by the technical indicator module.
"""

from __future__ import annotations

import os
from typing import Literal

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

# Define constants here for backward compatibility
LOCAL_MAX: Literal["LOCAL_MAX"] = "LOCAL_MAX"
LOCAL_MIN: Literal["LOCAL_MIN"] = "LOCAL_MIN"


def add_local_extrema_column(
    df: pd.DataFrame,
    price_column: str = "close",
    output_column: str = "local_extrema",
    *,
    min_distance: int = 5,
    prominence_factor: float = 0.5,
) -> pd.DataFrame:
    """Add a column marking robust local minima and maxima based on `price_column`.

    This uses ``scipy.signal.find_peaks``, which is widely recommended in
    quantitative finance discussions for identifying swing highs/lows in
    noisy price series (see SciPy documentation and multiple algotrading
    threads that propose ``find_peaks`` + prominence filters).

    Algorithm (for the given ``price_column``, typically ``"close"``):

    1. Convert to a numeric series and forward/back-fill missing values.
    2. Compute a volatility-based "prominence" threshold as
       ``prominence_factor * std(close)``.
    3. Use ``find_peaks`` with:
       - ``distance=min_distance``: minimum number of bars between extrema.
       - ``prominence=volatility_based_threshold``: ignore tiny wiggles.
    4. Apply it once to the price series (local maxima) and once to the
       negated series (local minima).

    All detected swing highs are tagged ``LOCAL_MAX`` and swing lows are
    tagged ``LOCAL_MIN`` in a new column; other rows are ``None``.
    """

    if price_column not in df.columns:
        raise ValueError(f"Price column '{price_column}' not found in DataFrame")

    # Ensure numeric series on a copy; fill gaps to keep SciPy happy
    series = pd.to_numeric(df[price_column], errors="coerce").copy()
    series = series.ffill().bfill()

    values = series.to_numpy(dtype=float)

    # Volatility-based prominence threshold. This follows common practice
    # in peak detection on financial time series: require that a swing
    # stands out relative to recent volatility instead of using a fixed
    # price threshold.
    std = float(np.nanstd(values))
    prominence = std * float(prominence_factor) if std > 0 else None

    peak_kwargs = {"distance": max(int(min_distance), 1)}
    if prominence is not None and prominence > 0:
        peak_kwargs["prominence"] = prominence

    # Swing highs
    max_idx, _ = find_peaks(values, **peak_kwargs)
    # Swing lows (peaks on the inverted series)
    min_idx, _ = find_peaks(-values, **peak_kwargs)

    # Create an object-typed column with None by default
    result = pd.Series(index=df.index, dtype="object")
    if len(max_idx):
        result.iloc[max_idx] = LOCAL_MAX
    if len(min_idx):
        result.iloc[min_idx] = LOCAL_MIN

    df[output_column] = result
    return df


def annotate_csv_with_local_extrema(
    csv_path: str,
    price_column: str = "close",
    output_column: str = "local_extrema",
) -> bool:
    """Load a CSV, annotate local extrema, and save it back in-place.

    Returns True on success, False otherwise.
    """

    if not os.path.exists(csv_path):
        print(f"  CSV file not found: {csv_path}")
        return False

    try:
        df = pd.read_csv(csv_path, index_col=[0])
        df = add_local_extrema_column(
            df,
            price_column=price_column,
            output_column=output_column,
        )
        df.to_csv(csv_path)
        print(f"  Added local extrema to {os.path.basename(csv_path)}")
        return True
    except Exception as e:
        print(f"  Error adding local extrema to {os.path.basename(csv_path)}: {e}")
        return False
