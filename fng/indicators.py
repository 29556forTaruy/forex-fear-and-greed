"""純関数の指標群(leak-free)。

すべて pandas Series/DataFrame を入出力とし、状態を持たない。時刻 t の値は
t までの情報のみで決まる(rolling は過去のみ参照、shift は使わない実装)。
ForexProjection/pipeline/engineer.py の設計思想を踏襲。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def log_returns(close: pd.Series) -> pd.Series:
    """日次対数リターン。"""
    return np.log(close / close.shift(1))


def moving_average(close: pd.Series, window: int) -> pd.Series:
    """単純移動平均(過去 window 本)。"""
    return close.rolling(window, min_periods=max(2, window // 2)).mean()


def realized_vol(close: pd.Series, window: int = 20, ann_factor: int = 252) -> pd.Series:
    """年率実現ボラティリティ = stdev(日次log return, window) × sqrt(ann_factor)。

    「通貨VIX」の主指標。値は年率(例 0.094 = 9.4%)。
    """
    r = log_returns(close)
    return r.rolling(window, min_periods=max(5, window // 2)).std(ddof=0) * np.sqrt(ann_factor)


def range_position(close: pd.Series, lookback: int = 252) -> pd.Series:
    """52週(lookback本)レンジ内の位置 0–1。

    (price − rolling_low) / (rolling_high − rolling_low)。
    高値圏=1(強い), 安値圏=0(弱い)。
    """
    hi = close.rolling(lookback, min_periods=max(20, lookback // 5)).max()
    lo = close.rolling(lookback, min_periods=max(20, lookback // 5)).min()
    denom = (hi - lo).replace(0, np.nan)
    return ((close - lo) / denom).clip(0, 1)


def rate_of_change(series: pd.Series, window: int) -> pd.Series:
    """window 本前からの変化量(差分)。金利差の「勢い」用。"""
    return series - series.shift(window)


def rolling_percentile(series: pd.Series, window: int = 252, min_periods: int = 60) -> pd.Series:
    """直近 window 営業日における現在値の percentile(0–100)。

    各時点 t で、過去 window 本(t を含む)の分布における close[t] の順位を返す。
    厳密な z-score よりレジーム変化に頑健。leak-free(未来は参照しない)。
    """
    def _pct_rank(arr: np.ndarray) -> float:
        last = arr[-1]
        valid = arr[~np.isnan(arr)]
        if valid.size < min_periods or np.isnan(last):
            return np.nan
        # 「現在値以下の割合」(< は厳密順位、== は半分カウントで tie 調整)。
        below = np.sum(valid < last)
        equal = np.sum(valid == last)
        return 100.0 * (below + 0.5 * equal) / valid.size

    return series.rolling(window, min_periods=min_periods).apply(_pct_rank, raw=True)


def to_score(series: pd.Series, window: int, min_periods: int, invert: bool = False) -> pd.Series:
    """生シグナル → 0–100 スコア。invert=True なら 100 − percentile。"""
    pct = rolling_percentile(series, window=window, min_periods=min_periods)
    return (100.0 - pct) if invert else pct


def zscore(series: pd.Series, window: int, min_periods: int = 20) -> pd.Series:
    """rolling z-score(参考/補助用)。"""
    mu = series.rolling(window, min_periods=min_periods).mean()
    sd = series.rolling(window, min_periods=min_periods).std(ddof=0)
    return (series - mu) / sd.replace(0, np.nan)
