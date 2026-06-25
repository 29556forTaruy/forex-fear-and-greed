"""CFTC 建玉 → ペアの投機筋ポジション信号(週次)。

各通貨の CME 先物(対USD)の非商業ネット(long − short)を取得し、ペアの符号で合成する:
    cot_signal = (+base通貨ネット) + (−quote通貨ネット)
USD は numéraire(先物なし)で寄与ゼロ。
  - EUR/USD : +EUR(ネットロングEUR=EUR/USD上昇=greed)
  - USD/JPY : −JPY(ネットロングJPY=USD/JPY下落=fear → 符号反転で greed=円ネットショート)
  - EUR/JPY : +EUR −JPY
高い cot_signal = greed(ペア上昇方向に賭けが傾く)。取得失敗時は空 Series。
"""

from __future__ import annotations

import os

import pandas as pd
import requests

from config import CONFIG, pair_config

_HEADERS = {"User-Agent": "Mozilla/5.0 (forex-fng research)"}


def _currency_net(name_contains: str, start: str) -> pd.Series:
    """1 通貨の非商業ネット(long − short)週次 Series。"""
    params = {
        "$select": ("report_date_as_yyyy_mm_dd,"
                    "noncomm_positions_long_all,noncomm_positions_short_all"),
        "$where": (f"market_and_exchange_names like '%{name_contains}%' "
                   f"AND report_date_as_yyyy_mm_dd >= '{start}T00:00:00.000'"),
        "$order": "report_date_as_yyyy_mm_dd",
        "$limit": 5000,
    }
    headers = dict(_HEADERS)
    tok_env = CONFIG["cftc"].get("app_token_env")
    if tok_env and os.environ.get(tok_env):
        headers["X-App-Token"] = os.environ[tok_env]
    try:
        r = requests.get(CONFIG["cftc"]["base_url"], params=params, headers=headers, timeout=40)
        rows = r.json()
    except Exception:
        return pd.Series(dtype=float)
    if not isinstance(rows, list) or not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rows)
    need = {"report_date_as_yyyy_mm_dd", "noncomm_positions_long_all", "noncomm_positions_short_all"}
    if not need.issubset(df.columns):
        return pd.Series(dtype=float)
    longs = pd.to_numeric(df["noncomm_positions_long_all"], errors="coerce")
    shorts = pd.to_numeric(df["noncomm_positions_short_all"], errors="coerce")
    net = (longs - shorts)
    net.index = pd.to_datetime(df["report_date_as_yyyy_mm_dd"]).dt.normalize()
    net = net.sort_index().dropna()
    return net[~net.index.duplicated(keep="last")]


def fetch_cot_signal(pair: str = "USDJPY", start: str | None = None) -> pd.Series:
    """ペアの COT 信号(+base −quote の合成、週次)を返す。"""
    start = start or CONFIG["fetch_start"]
    pc = pair_config(pair)
    cur = CONFIG["currencies"]
    legs = []  # (符号, Series)
    for sign, ccy in ((+1, pc["base"]), (-1, pc["quote"])):
        name = cur[ccy].get("cot")
        if name:
            s = _currency_net(name, start)
            if not s.empty:
                legs.append((sign, s))
    if not legs:
        return pd.Series(dtype=float, name="cot_signal")

    idx = legs[0][1].index
    for _, s in legs[1:]:
        idx = idx.union(s.index)
    signal = pd.Series(0.0, index=idx)
    for sign, s in legs:
        signal = signal.add(sign * s.reindex(idx).ffill(), fill_value=0.0)
    signal.name = "cot_signal"
    return signal.sort_index()
