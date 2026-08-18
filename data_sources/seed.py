"""同梱データ(seed)の読み書き。

公開デプロイ時の課題は「初回アクセスが遅い」「クラウドIPからの外部取得が失敗しうる」の2点。
そこで `build_dataset()` の出力を parquet として **リポジトリに同梱**(data/seed/)し、
アプリは既定でこれを即座に読み込む。seed は GitHub Actions が日次で更新する。

本指数は日次終値ベースなので、seed が最大1営業日古くても指数値は変わらない。
最新値が要る場面のためにアプリ側に「最新データに更新」(ライブ取得)を残してある。
"""

from __future__ import annotations

import json
import os

import pandas as pd

from config import CONFIG

SEED_DIR = os.path.join(CONFIG["root"], "data", "seed")
MANIFEST = os.path.join(SEED_DIR, "manifest.json")


def seed_path(pair: str) -> str:
    return os.path.join(SEED_DIR, f"dataset_{pair}.parquet")


def save_seed(pair: str, df: pd.DataFrame) -> str:
    os.makedirs(SEED_DIR, exist_ok=True)
    path = seed_path(pair)
    df.to_parquet(path)
    return path


def load_seed(pair: str) -> pd.DataFrame | None:
    """同梱 seed を読む。無い/壊れている場合は None。"""
    path = seed_path(pair)
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_parquet(path)
    except Exception:
        return None
    if df.empty or "price" not in df:
        return None
    df.attrs["source"] = "seed"
    df.attrs["last_date"] = str(df.index[-1].date())
    df.attrs["built_at"] = read_manifest().get("built_at")
    return df


def read_manifest() -> dict:
    try:
        with open(MANIFEST, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def write_manifest(info: dict) -> str:
    os.makedirs(SEED_DIR, exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    return MANIFEST


def available_pairs() -> list[str]:
    return [p for p in CONFIG["pairs"] if os.path.exists(seed_path(p))]
