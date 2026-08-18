"""同梱データ(data/seed/)を最新化する。

  .venv/bin/python scripts/refresh_seed.py            # 全ペア
  .venv/bin/python scripts/refresh_seed.py --pair USDJPY

GitHub Actions が日次で実行し、差分があればコミットする。ローカルで手動実行してもよい。
1ペアでも失敗した場合、そのペアの既存 seed は残したまま続行する(全滅時のみ exit 1)。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import CONFIG, fred_api_key            # noqa: E402
from data_sources import seed as _seed             # noqa: E402
from data_sources.load import build_dataset        # noqa: E402
from fng.index import compute_index, snapshot      # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="data/seed/ を最新化")
    ap.add_argument("--pair", action="append", help="対象ペア(複数可)。既定は全ペア")
    args = ap.parse_args()

    pairs = args.pair or list(CONFIG["pairs"].keys())
    built, failed, summary = [], [], {}

    for p in pairs:
        t0 = time.time()
        try:
            df = build_dataset(p, start=CONFIG["fetch_start"], force=True)
            compute_index(df)                       # 壊れたデータを同梱しないための健全性チェック
            snap = snapshot(df, pair=p)
            _seed.save_seed(p, df)
            built.append(p)
            summary[p] = {"last_date": snap["date"], "fear_greed": snap["fear_greed"],
                          "label_en": snap["label_en"], "rows": len(df)}
            print(f"✓ {p:7s} {time.time()-t0:5.1f}s  {snap['date']}  "
                  f"F&G={snap['fear_greed']:5.1f} ({snap['label_en']})", flush=True)
        except Exception as e:  # noqa: BLE001
            failed.append(p)
            print(f"✗ {p:7s} {time.time()-t0:5.1f}s  失敗: {type(e).__name__}: {e}", flush=True)

    if built:
        _seed.write_manifest({
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "fred_key_used": bool(fred_api_key()),
            "pairs": summary,
            "failed": failed,
        })

    print(f"\n成功 {len(built)}/{len(pairs)} ペア" + (f" / 失敗: {failed}" if failed else ""))
    if not fred_api_key():
        print("注意: FRED_API_KEY 未設定のため EUR/GBP/AUD の金利差要素は NaN のまま同梱されます。")
    return 0 if built else 1


if __name__ == "__main__":
    raise SystemExit(main())
