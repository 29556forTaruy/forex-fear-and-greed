"""価格データ(yfinance、無料・キー不要)。

- fetch_prices(pair)  : ペア終値 "price" + 共通リスクバスケット(vix, sp500, nikkei, audjpy, gold)
- fetch_breadth_basket(): JPY クロス各種の終値(JPY-strength breadth 用)
返り値は日次 DataFrame。結果は parquet にキャッシュ。
"""

from __future__ import annotations

import os

import pandas as pd

from config import CONFIG, pair_config


def _yf_close(ticker: str, start: str) -> pd.Series:
    import yfinance as yf
    try:
        h = yf.Ticker(ticker).history(start=start, auto_adjust=True)
    except Exception:
        return pd.Series(dtype=float)
    if h is None or h.empty or "Close" not in h:
        return pd.Series(dtype=float)
    close = h["Close"].copy()
    idx = pd.DatetimeIndex(close.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    close.index = idx.normalize()
    return close.dropna()


def _fetch_set(tickers: dict[str, str], start: str) -> pd.DataFrame:
    series = {}
    for key, ticker in tickers.items():
        s = _yf_close(ticker, start)
        if not s.empty:
            series[key] = s
    df = pd.DataFrame(series).sort_index()
    df.index.name = "date"
    return df


def fetch_prices(pair: str = "USDJPY", start: str | None = None,
                 force: bool = False) -> pd.DataFrame:
    """ペア終値 "price" + リスクバスケットの日次 DataFrame。"""
    start = start or CONFIG["fetch_start"]
    pc = pair_config(pair)
    cache = os.path.join(CONFIG["data"]["cache_dir"], f"prices_{pair}.parquet")
    if os.path.exists(cache) and not force:
        try:
            return pd.read_parquet(cache)
        except Exception:
            pass

    tickers = {"price": pc["yf_ticker"], **CONFIG["risk_basket"]}
    df = _fetch_set(tickers, start)
    if "price" not in df.columns or df["price"].dropna().empty:
        raise RuntimeError(f"{pair} の価格取得に失敗しました(yfinance)。")

    os.makedirs(CONFIG["data"]["cache_dir"], exist_ok=True)
    try:
        df.to_parquet(cache)
    except Exception:
        pass
    return df


def fetch_breadth_basket(start: str | None = None, force: bool = False) -> pd.DataFrame:
    """JPY クロス各種の終値(breadth 用)。"""
    start = start or CONFIG["fetch_start"]
    cache = os.path.join(CONFIG["data"]["cache_dir"], "breadth_basket.parquet")
    if os.path.exists(cache) and not force:
        try:
            return pd.read_parquet(cache)
        except Exception:
            pass
    df = _fetch_set(CONFIG["breadth_basket"], start)
    os.makedirs(CONFIG["data"]["cache_dir"], exist_ok=True)
    try:
        df.to_parquet(cache)
    except Exception:
        pass
    return df
