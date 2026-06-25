"""為替版 Fear & Greed Index の単一設定ソース(config-as-code)。

段階3で多通貨対応に一般化。通貨レジストリ(`currencies`)が各通貨の CFTC 名・利回り源を持ち、
`pairs` は base/quote の組で定義する。全要素は「高スコア = Greed = リスクオン = ペア上昇」に揃える。

APIキー: FRED_API_KEY(任意)。EUR/GBP/AUD の利回りは FRED 由来のため、これらを base/quote に持つ
ペアの金利差要素(rate_diff)には FRED キーが必要。US=米財務省 / JP=財務省MoF は無料・キー不要。
"""

from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.abspath(__file__))


def _p(*parts: str) -> str:
    return os.path.join(ROOT, *parts)


CONFIG = {
    "root": ROOT,

    "data": {
        "cache_dir": _p("data", "cache"),
        "reports_dir": _p("data", "reports"),
    },

    # 符号規約: リスク選好型。高=Greed=リスクオン=ペア上昇 / 低=Fear=リスクオフ=ペア下落。
    "polarity": "risk_appetite",

    "normalization": {"window": 252, "min_periods": 60},

    # CNN のラベル境界(0–100、ペア非依存表現)。
    "labels": [
        (0, 24, "Extreme Fear", "極度の恐怖(リスクオフ)"),
        (25, 44, "Fear", "恐怖"),
        (45, 55, "Neutral", "中立"),
        (56, 75, "Greed", "強欲"),
        (76, 100, "Extreme Greed", "極度の強欲(リスクオン)"),
    ],

    # 7 構成要素(invert=True は score=100−percentile)。breadth は JPY クロスのみ適用。
    "components": {
        "momentum":     {"weight": 0.18, "invert": False, "ma_window": 125},
        "strength":     {"weight": 0.12, "invert": False, "lookback": 252},
        "realized_vol": {"weight": 0.18, "invert": True,  "vol_window": 20, "ann_factor": 252},
        "rate_diff":    {"weight": 0.18, "invert": False, "roc_window": 60},
        "risk_regime":  {"weight": 0.14, "invert": False},
        "cot":          {"weight": 0.10, "invert": False, "cot_window_weeks": 156},
        "breadth":      {"weight": 0.10, "invert": False, "mom_window": 20},
    },

    "fetch_start": "2019-01-01",

    # 通貨レジストリ: CFTC名(USDは numéraire のため無し)+ 利回り源 (source, key)。
    #   source: "ust"=米財務省CSVの列名 / "mof"=財務省JGBの列名 / "fred"=FRED系列ID。
    "currencies": {
        "USD": {"cot": None,                "yields": {"2y": ("ust", "2 Yr"),  "10y": ("ust", "10 Yr")}},
        "JPY": {"cot": "JAPANESE YEN",       "yields": {"2y": ("mof", "2年"),    "10y": ("mof", "10年")}},
        "EUR": {"cot": "EURO FX",            "yields": {"10y": ("fred", "IRLTLT01DEM156N")}},
        "GBP": {"cot": "BRITISH POUND",      "yields": {"10y": ("fred", "IRLTLT01GBM156N")}},
        "AUD": {"cot": "AUSTRALIAN DOLLAR",  "yields": {"10y": ("fred", "IRLTLT01AUM156N")}},
    },

    # 通貨ペア定義(base/quote)。is_jpy=True は JPY クロス(breadth 要素を適用)。
    "pairs": {
        "USDJPY": {"yf_ticker": "USDJPY=X", "base": "USD", "quote": "JPY", "is_jpy": True},
        "EURJPY": {"yf_ticker": "EURJPY=X", "base": "EUR", "quote": "JPY", "is_jpy": True},
        "GBPJPY": {"yf_ticker": "GBPJPY=X", "base": "GBP", "quote": "JPY", "is_jpy": True},
        "AUDJPY": {"yf_ticker": "AUDJPY=X", "base": "AUD", "quote": "JPY", "is_jpy": True},
        "EURUSD": {"yf_ticker": "EURUSD=X", "base": "EUR", "quote": "USD", "is_jpy": False},
        "GBPUSD": {"yf_ticker": "GBPUSD=X", "base": "GBP", "quote": "USD", "is_jpy": False},
    },

    # クロスアセット・リスク要素の入力(全ペア共通、yfinance)。
    "risk_basket": {"vix": "^VIX", "sp500": "^GSPC", "nikkei": "^N225",
                    "audjpy": "AUDJPY=X", "gold": "GC=F"},

    # JPY-strength breadth 用バスケット(クロス円が上昇=広範な円安=greed)。
    "breadth_basket": {
        "USDJPY": "USDJPY=X", "EURJPY": "EURJPY=X", "GBPJPY": "GBPJPY=X",
        "AUDJPY": "AUDJPY=X", "CADJPY": "CADJPY=X", "CHFJPY": "CHFJPY=X",
    },

    # 金利エンドポイント(キー不要)。
    "ust": {
        "base_url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{year}/all",
        "params": "?type=daily_treasury_yield_curve&field_tdr_date_value={year}&_format=csv",
    },
    "mof": {"url": "https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv"},

    # FRED(任意・EUR/GBP/AUD利回り用) / CFTC。
    "fred": {
        "base_url": "https://api.stlouisfed.org/fred/series/observations",
        "api_key_env": "FRED_API_KEY",
    },
    "cftc": {
        "base_url": "https://publicreporting.cftc.gov/resource/6dca-aqww.json",
        "app_token_env": "CFTC_APP_TOKEN",
    },
}


def pair_config(pair: str = "USDJPY") -> dict:
    if pair not in CONFIG["pairs"]:
        raise KeyError(f"未定義の通貨ペア: {pair}. 定義済み: {list(CONFIG['pairs'])}")
    return CONFIG["pairs"][pair]


def fred_api_key() -> str | None:
    return os.environ.get(CONFIG["fred"]["api_key_env"])
