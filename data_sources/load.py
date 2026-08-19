"""価格・金利・建玉・breadth をペアの営業日グリッドに統合する。

返り値の列(取得できたもの):
  price, vix, sp500, nikkei, audjpy, gold,
  base_2y, base_10y, quote_2y, quote_10y, cot_signal, breadth_pct
これが fng.index.compute_index() の入力になる。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import CONFIG, pair_config
from . import prices as _prices
from . import rates as _rates
from . import positioning as _positioning
from . import seed as _seed


def _breadth_pct(master: pd.Index, start: str, force: bool, window: int) -> pd.Series:
    """JPY クロスのうち window 日モメンタムが正(円安方向)の割合 0–1。"""
    bb = _prices.fetch_breadth_basket(start=start, force=force)
    if bb.empty:
        return pd.Series(np.nan, index=master)
    rising = (bb / bb.shift(window) - 1.0) > 0      # 各クロスが上昇=円安か
    pct = rising.mean(axis=1, skipna=True)          # 上昇しているクロスの割合
    return pct.reindex(master.union(pct.index)).ffill(limit=5).reindex(master)


def build_dataset(pair: str = "USDJPY", start: str | None = None,
                  force: bool = False, use_cot: bool = True) -> pd.DataFrame:
    start = start or CONFIG["fetch_start"]
    pc = pair_config(pair)

    px = _prices.fetch_prices(pair, start=start, force=force)
    rt = _rates.fetch_rates(pair, start=start, force=force)

    master = px["price"].dropna().index
    df = pd.DataFrame(index=master)
    df.index.name = "date"

    df["price"] = px["price"].reindex(master)
    for col in ("vix", "sp500", "nikkei", "audjpy", "gold"):
        if col in px:
            df[col] = px[col].reindex(master).ffill(limit=5)

    for col in ("base_2y", "base_10y", "quote_2y", "quote_10y"):
        if col in rt:
            df[col] = rt[col].reindex(master).ffill(limit=45)

    if use_cot:
        try:
            cot = _positioning.fetch_cot_signal(pair, start=start)
        except Exception:
            cot = pd.Series(dtype=float)
        if not cot.empty:
            cot = cot[~cot.index.duplicated(keep="last")].sort_index()
            df["cot_signal"] = cot.reindex(master, method="ffill", limit=10)

    if pc.get("is_jpy"):
        df["breadth_pct"] = _breadth_pct(master, start, force,
                                         CONFIG["components"]["breadth"]["mom_window"])

    df.attrs["source"] = "live"
    df.attrs["last_date"] = str(df.index[-1].date()) if len(df) else None
    return df


def cache_dataset(df: pd.DataFrame, pair: str = "USDJPY") -> str:
    import os
    os.makedirs(CONFIG["data"]["cache_dir"], exist_ok=True)
    path = os.path.join(CONFIG["data"]["cache_dir"], f"dataset_{pair}.parquet")
    try:
        df.to_parquet(path)
    except Exception:
        path = path.replace(".parquet", ".csv")
        df.to_csv(path)
    return path


def get_dataset(pair: str = "USDJPY", start: str | None = None,
                live: bool = False) -> pd.DataFrame:
    """アプリ向けの取得口。

    live=False(既定): 同梱 seed を即座に返す(公開環境での初回表示が一瞬・外部依存ゼロ)。
                      seed が無ければライブ取得にフォールバック。
    live=True       : ライブ取得。失敗したら seed にフォールバックする(空ページを出さない)。

    返り値の `df.attrs["source"]` が "seed" / "live" のどちらかを示す。
    """
    if not live:
        df = _seed.load_seed(pair)
        if df is not None:
            return df
    try:
        return build_dataset(pair, start=start, force=live)
    except Exception:
        df = _seed.load_seed(pair)
        if df is None:
            raise
        df.attrs["source"] = "seed_fallback"
        return df
