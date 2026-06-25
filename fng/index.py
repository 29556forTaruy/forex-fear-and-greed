"""構成要素を集約して headline Fear & Greed 指数(0–100)を算出する。

  FearGreed_t = Σ_i w_i · score_i,t / Σ_i w_i   （その時点で利用可能な要素のみ）

要素が欠損(NaN)している時点では、その要素を分子・分母から除いて重みを再正規化する。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import CONFIG
from .components import compute_components, realized_vol_raw


def label_for(value: float, cfg=CONFIG) -> tuple[str, str]:
    """0–100 値 → (英語ラベル, 日本語ラベル)。NaN は ('N/A','データ不足')。"""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ("N/A", "データ不足")
    for lo, hi, en, ja in cfg["labels"]:
        if lo <= value <= hi:
            return (en, ja)
    return ("N/A", "範囲外")


def aggregate(components: pd.DataFrame, cfg=CONFIG) -> pd.Series:
    """要素スコア DataFrame → headline 指数 Series(0–100)。

    各時点で利用可能な要素のみで加重平均(重みを再正規化)。
    """
    weights = {name: cfg["components"][name]["weight"] for name in components.columns}
    w = pd.Series(weights)
    present = components.notna()                      # True/False マスク
    wmat = present.mul(w, axis=1)                     # 欠損要素の重みは0
    denom = wmat.sum(axis=1)
    num = (components.fillna(0.0) * wmat).sum(axis=1)
    headline = num / denom.replace(0, np.nan)
    headline.name = "fear_greed"
    return headline


def compute_index(df: pd.DataFrame, cfg=CONFIG) -> pd.DataFrame:
    """入力 df から要素スコア + headline + 通貨VIX(実現ボラ生値)を一括算出。

    返り値の列: [6要素スコア..., fear_greed, realized_vol_pct(=実現ボラ年率%)]
    """
    comps = compute_components(df, cfg)
    headline = aggregate(comps, cfg)
    result = comps.copy()
    result["fear_greed"] = headline
    # 通貨VIX(年率実現ボラ、%表示)を併載。
    result["realized_vol_pct"] = realized_vol_raw(df["price"], cfg) * 100.0
    return result


def snapshot(df: pd.DataFrame, cfg=CONFIG, date=None, pair: str = "USDJPY") -> dict:
    """指定日(既定: 最新)の headline・ラベル・要素内訳・現在値をまとめて返す。"""
    res = compute_index(df, cfg)
    res = res.dropna(subset=["fear_greed"])
    if res.empty:
        raise ValueError("有効な指数値がありません(データ不足)。")
    row = res.iloc[-1] if date is None else res.loc[:date].iloc[-1]
    when = row.name
    en, ja = label_for(row["fear_greed"], cfg)
    comp_names = list(cfg["components"].keys())
    px = df["price"].loc[:when].iloc[-1]
    return {
        "pair": pair,
        "date": str(when.date()) if hasattr(when, "date") else str(when),
        "fear_greed": round(float(row["fear_greed"]), 1),
        "label_en": en,
        "label_ja": ja,
        "components": {k: (None if pd.isna(row[k]) else round(float(row[k]), 1)) for k in comp_names},
        "price": None if pd.isna(px) else round(float(px), 4),
        "realized_vol_pct": None if pd.isna(row["realized_vol_pct"]) else round(float(row["realized_vol_pct"]), 2),
    }


def _cli() -> None:
    """`python -m fng.index --pair USDJPY [--date YYYY-MM-DD] [--force]` で当日値を表示。"""
    import argparse
    import json
    from data_sources.load import build_dataset

    ap = argparse.ArgumentParser(description="USD/JPY Fear & Greed Index — 当日のスナップショット")
    ap.add_argument("--pair", default="USDJPY")
    ap.add_argument("--date", default=None, help="基準日(既定: 最新)")
    ap.add_argument("--start", default=None, help="取得開始日(既定: config の fetch_start)")
    ap.add_argument("--force", action="store_true", help="キャッシュを無視して再取得")
    args = ap.parse_args()

    df = build_dataset(args.pair, start=args.start, force=args.force)
    snap = snapshot(df, date=args.date, pair=args.pair)
    print(json.dumps(snap, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _cli()
