# /Users/yvchuan/Desktop/Projects/Alphapilot/alphapilot/tools/technical_indicators.py

from __future__ import annotations

import pandas as pd


def compute_kdj(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    n: int = 9,
    m1: int = 3,
    m2: int = 3,
) -> tuple[float, float, float]:
    low_n = low.rolling(window=n).min()
    high_n = high.rolling(window=n).max()
    rsv = ((close - low_n) / (high_n - low_n + 1e-9) * 100)

    k_vals: list[float] = []
    d_vals: list[float] = []
    prev_k = 50.0
    prev_d = 50.0

    for v in rsv.dropna():
        prev_k = (m1 - 1) / m1 * prev_k + 1 / m1 * float(v)
        k_vals.append(prev_k)
        prev_d = (m2 - 1) / m2 * prev_d + 1 / m2 * prev_k
        d_vals.append(prev_d)

    if not k_vals:
        return 0.0, 0.0, 0.0

    k = round(k_vals[-1], 2)
    d = round(d_vals[-1], 2)
    j = round(3 * k - 2 * d, 2)
    return k, d, j


def compute_bollinger(
    close: pd.Series,
    window: int = 20,
    num_std: float = 2.0,
) -> tuple[float, float, float]:
    mid = close.rolling(window=window).mean()
    std = close.rolling(window=window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std

    if mid.empty or pd.isna(mid.iloc[-1]):
        return 0.0, 0.0, 0.0

    return (
        round(float(upper.iloc[-1]), 2),
        round(float(mid.iloc[-1]), 2),
        round(float(lower.iloc[-1]), 2),
    )


__all__ = ["compute_kdj", "compute_bollinger"]