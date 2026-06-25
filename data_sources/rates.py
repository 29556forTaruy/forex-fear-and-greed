"""通貨ペアの利回り: base 通貨と quote 通貨の 2Y/10Y。

利回り源は通貨レジストリ(config.currencies[ccy]["yields"])が決める:
  - "ust"  : 米財務省 日次パー利回り CSV(列名 "2 Yr"/"10 Yr")— キー不要
  - "mof"  : 財務省(MoF)JGB 日次利回り CSV(列名 "2年"/"10年")— キー不要
  - "fred" : FRED 系列(EUR=独/GBP/AUD の 10Y、月次)— FRED_API_KEY が必要
返り値は日次 DataFrame(列: base_2y, base_10y, quote_2y, quote_10y のうち取得できたもの)。
"""

from __future__ import annotations

import io

import pandas as pd
import requests

from config import CONFIG, fred_api_key, pair_config

_HEADERS = {"User-Agent": "Mozilla/5.0 (forex-fng research)"}
_ERA_BASE = {"M": 1867, "T": 1911, "S": 1925, "H": 1988, "R": 2018}


def _parse_wareki(s: str):
    """'R8.5.29' / 'S49.9.24' → Timestamp。失敗時 None。"""
    try:
        era, rest = s[0], s[1:]
        y, m, d = rest.split(".")
        return pd.Timestamp(_ERA_BASE[era] + int(y), int(m), int(d))
    except Exception:
        return None


def _ust_frame(start: str) -> pd.DataFrame:
    """米財務省 日次パー利回りを年別 CSV から結合(列 "2 Yr"/"10 Yr" 等を保持)。"""
    start_ts = pd.Timestamp(start)
    frames = []
    for yr in range(start_ts.year, pd.Timestamp.today().year + 1):
        url = CONFIG["ust"]["base_url"].format(year=yr) + CONFIG["ust"]["params"].format(year=yr)
        try:
            r = requests.get(url, headers=_HEADERS, timeout=30)
            if r.status_code != 200 or "Date" not in r.text[:50]:
                continue
            d = pd.read_csv(io.StringIO(r.text))
        except Exception:
            continue
        d.index = pd.DatetimeIndex(pd.to_datetime(d["Date"], format="%m/%d/%Y", errors="coerce"))
        keep = [c for c in ("2 Yr", "10 Yr") if c in d.columns]
        frames.append(d[keep].apply(pd.to_numeric, errors="coerce"))
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    out.index.name = "date"
    return out


def _mof_frame(start: str) -> pd.DataFrame:
    """財務省 JGB 日次利回り(列 "2年"/"10年" 等)。"""
    try:
        r = requests.get(CONFIG["mof"]["url"], headers=_HEADERS, timeout=60)
        text = r.content.decode("cp932")
    except Exception:
        return pd.DataFrame()
    df = pd.read_csv(io.StringIO(text), skiprows=1)
    dates = df[df.columns[0]].astype(str).map(_parse_wareki)
    out = pd.DataFrame(index=pd.DatetimeIndex(dates))
    for col in ("2年", "10年"):
        if col in df.columns:
            out[col] = pd.to_numeric(df[col].replace("-", pd.NA).values, errors="coerce")
    out = out[out.index.notna()].sort_index()
    out.index.name = "date"
    return out[out.index >= pd.Timestamp(start)]


def _fred_series(series_id: str, api_key: str, start: str) -> pd.Series:
    params = {"series_id": series_id, "api_key": api_key,
              "file_type": "json", "observation_start": start}
    try:
        r = requests.get(CONFIG["fred"]["base_url"], params=params, timeout=30)
        obs = r.json().get("observations", [])
    except Exception:
        return pd.Series(dtype=float)
    if not obs:
        return pd.Series(dtype=float)
    d = pd.DataFrame(obs)
    d["date"] = pd.to_datetime(d["date"]).dt.normalize()
    d["value"] = pd.to_numeric(d["value"], errors="coerce")
    return d.set_index("date")["value"].dropna()


def _yield_series(source: str, key: str, start: str, cache: dict) -> pd.Series | None:
    """(source, key) から 1 つの利回り系列を返す。取得不可なら None。"""
    if source == "ust":
        if "ust" not in cache:
            cache["ust"] = _ust_frame(start)
        f = cache["ust"]
        return f[key] if key in f.columns else None
    if source == "mof":
        if "mof" not in cache:
            cache["mof"] = _mof_frame(start)
        f = cache["mof"]
        return f[key] if key in f.columns else None
    if source == "fred":
        ak = fred_api_key()
        if not ak:
            return None
        s = _fred_series(key, ak, start)
        return s if not s.empty else None
    return None


def fetch_rates(pair: str = "USDJPY", start: str | None = None,
                force: bool = False) -> pd.DataFrame:
    """ペアの利回り(base_2y, base_10y, quote_2y, quote_10y のうち取得分)を返す。"""
    start = start or CONFIG["fetch_start"]
    pc = pair_config(pair)
    cur = CONFIG["currencies"]
    out = {}
    cache: dict = {}
    for leg, ccy in (("base", pc["base"]), ("quote", pc["quote"])):
        ydef = cur[ccy].get("yields", {})
        for tenor in ("2y", "10y"):
            if tenor in ydef:
                src, key = ydef[tenor]
                s = _yield_series(src, key, start, cache)
                if s is not None and len(s):
                    out[f"{leg}_{tenor}"] = s
    if not out:
        return pd.DataFrame()
    df = pd.DataFrame(out).sort_index()
    df.index.name = "date"
    return df
