"""構成要素を 0–100 スコアへ変換する(全ペア共通、生成スキーマ駆動)。

符号規約: すべての要素で **高スコア = Greed = リスクオン = ペア上昇**。
入力 `df` の想定列(欠損可):
  price, vix, sp500, nikkei, audjpy, gold,
  base_2y, base_10y, quote_2y, quote_10y, cot_signal, breadth_pct
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import CONFIG
from . import indicators as ind


def _norm(cfg):
    n = cfg["normalization"]
    return n["window"], n["min_periods"]


def momentum_score(close: pd.Series, cfg=CONFIG) -> pd.Series:
    """要素1: 価格 vs 移動平均。上抜け=greed。"""
    w = cfg["components"]["momentum"]["ma_window"]
    win, mp = _norm(cfg)
    ma = ind.moving_average(close, w)
    return ind.to_score((close - ma) / ma, window=win, min_periods=mp, invert=False)


def strength_score(close: pd.Series, cfg=CONFIG) -> pd.Series:
    """要素2: 52週レンジ位置(0–100)。高値圏=greed。"""
    lb = cfg["components"]["strength"]["lookback"]
    return ind.range_position(close, lookback=lb) * 100.0


def realized_vol_raw(close: pd.Series, cfg=CONFIG) -> pd.Series:
    c = cfg["components"]["realized_vol"]
    return ind.realized_vol(close, window=c["vol_window"], ann_factor=c["ann_factor"])


def realized_vol_score(close: pd.Series, cfg=CONFIG) -> pd.Series:
    """要素3: 実現ボラ。高ボラ=fear なので反転。"""
    win, mp = _norm(cfg)
    return ind.to_score(realized_vol_raw(close, cfg), window=win, min_periods=mp, invert=True)


def _diff_signals(df, base_col, quote_col, win, mp, roc_w):
    """1テナーの金利差(base − quote)→ level・60日変化 percentile の2系列。"""
    if base_col not in df or df[base_col].isna().all():
        return []
    if quote_col in df and df[quote_col].notna().any():
        diff = df[base_col] - df[quote_col]
    else:
        diff = df[base_col]  # quote欠損時は base 単独で代用
    level = ind.to_score(diff, window=win, min_periods=mp, invert=False)
    roc = ind.to_score(ind.rate_of_change(diff, roc_w), window=win, min_periods=mp, invert=False)
    return [level, roc]


def rate_diff_score(df: pd.DataFrame, cfg=CONFIG) -> pd.Series:
    """要素4: base−quote 金利差と勢い。広い/拡大=ペア上昇支援=greed。"""
    win, mp = _norm(cfg)
    roc_w = cfg["components"]["rate_diff"]["roc_window"]
    parts = []
    parts += _diff_signals(df, "base_10y", "quote_10y", win, mp, roc_w)
    parts += _diff_signals(df, "base_2y", "quote_2y", win, mp, roc_w)
    if not parts:
        return pd.Series(np.nan, index=df.index)
    return pd.concat(parts, axis=1).mean(axis=1)


def risk_regime_score(df: pd.DataFrame, cfg=CONFIG) -> pd.Series:
    """要素5: クロスアセット・リスク。リスクオン=greed(全ペア共通)。"""
    win, mp = _norm(cfg)
    parts = []
    for col, ma_w in (("audjpy", 60), ("nikkei", 125), ("sp500", 125)):
        if col in df and df[col].notna().any():
            ma = ind.moving_average(df[col], ma_w)
            parts.append(ind.to_score((df[col] - ma) / ma, window=win, min_periods=mp, invert=False))
    if "vix" in df and df["vix"].notna().any():
        parts.append(ind.to_score(df["vix"], window=win, min_periods=mp, invert=True))
    if not parts:
        return pd.Series(np.nan, index=df.index)
    return pd.concat(parts, axis=1).mean(axis=1)


def cot_score(df: pd.DataFrame, cfg=CONFIG) -> pd.Series:
    """要素6: CFTC 投機筋ポジション。cot_signal は既にペア符号付き(高=greed)。"""
    if "cot_signal" not in df or not df["cot_signal"].notna().any():
        return pd.Series(np.nan, index=df.index)
    weeks = cfg["components"]["cot"]["cot_window_weeks"]
    win = weeks * 5
    mp = max(20, win // 8)
    return ind.to_score(df["cot_signal"], window=win, min_periods=mp, invert=False)


def breadth_score(df: pd.DataFrame, cfg=CONFIG) -> pd.Series:
    """要素7: JPY-strength breadth。クロス円が広く上昇(円安)=greed。JPYペアのみ。"""
    if "breadth_pct" not in df or not df["breadth_pct"].notna().any():
        return pd.Series(np.nan, index=df.index)
    win, mp = _norm(cfg)
    # breadth_pct は 0–1。percentile 化して相対的な「広がり」を測る。
    return ind.to_score(df["breadth_pct"], window=win, min_periods=mp, invert=False)


def compute_components(df: pd.DataFrame, cfg=CONFIG) -> pd.DataFrame:
    """構成要素スコア(0–100)を DataFrame で返す。"""
    if "price" not in df:
        raise KeyError("入力 df に 'price' 列が必要です。")
    close = df["price"]
    out = pd.DataFrame(index=df.index)
    out["momentum"] = momentum_score(close, cfg)
    out["strength"] = strength_score(close, cfg)
    out["realized_vol"] = realized_vol_score(close, cfg)
    out["rate_diff"] = rate_diff_score(df, cfg)
    out["risk_regime"] = risk_regime_score(df, cfg)
    out["cot"] = cot_score(df, cfg)
    out["breadth"] = breadth_score(df, cfg)
    return out
