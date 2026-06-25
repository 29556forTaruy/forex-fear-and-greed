"""為替版 Fear & Greed Index — Streamlit ダッシュボード(段階3: 多通貨)。

  .venv/bin/streamlit run app.py

タブ:
  - 単一ペア詳細: headline ゲージ / FX F&G 時系列 / 7要素内訳 / 過去比較 / 通貨VIX / 価格
  - 多通貨概要: 全ペアの F&G を一覧(バー + テーブル)
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CONFIG, fred_api_key            # noqa: E402
from data_sources.load import build_dataset        # noqa: E402
from fng.index import compute_index, snapshot, label_for  # noqa: E402
from fng import viz                                  # noqa: E402

st.set_page_config(page_title="Forex Fear & Greed", page_icon="📊", layout="wide")

PERIODS = {"1ヶ月": 21, "3ヶ月": 63, "6ヶ月": 126, "1年": 252, "全期間": None}


@st.cache_data(ttl=3600, show_spinner="データ取得中…")
def load_pair(pair: str, start: str):
    df = build_dataset(pair, start=start, force=False)
    res = compute_index(df)
    return df, res


@st.cache_data(ttl=3600, show_spinner="全ペアを計算中…")
def load_overview(pairs: tuple, start: str):
    rows = []
    for p in pairs:
        try:
            df, _ = load_pair(p, start)
            rows.append(snapshot(df, pair=p))
        except Exception as e:  # noqa: BLE001
            rows.append({"pair": p, "fear_greed": None, "label_ja": f"取得失敗({e})",
                         "price": None, "realized_vol_pct": None})
    return rows


def _fmt_price(p) -> str:
    if p is None:
        return "—"
    return f"{p:.4f}" if abs(p) < 10 else f"{p:.3f}"


def _at_offset(series: pd.Series, k: int):
    s = series.dropna()
    return float(s.iloc[-1 - k]) if len(s) > k else None


# ----------------------------------------------------------------------------- サイドバー
st.sidebar.title("⚙️ 設定")
pair = st.sidebar.selectbox("通貨ペア", list(CONFIG["pairs"].keys()), index=0)
period = st.sidebar.radio("表示期間", list(PERIODS.keys()), index=3)
overlay = st.sidebar.checkbox("チャートに価格を重ねる", value=True)
if st.sidebar.button("🔄 データ再取得"):
    load_pair.clear()
    load_overview.clear()
    st.rerun()
st.sidebar.caption("金利源: " + ("FRED(キー有)" if fred_api_key() else "米財務省+MoF(無料)。EUR/GBP/AUD金利差はFREDキーで有効化"))
st.sidebar.caption("価格: yfinance / 建玉: CFTC")

tab_detail, tab_overview = st.tabs(["📊 単一ペア詳細", "🌐 多通貨概要"])

# ============================================================================= 単一ペア詳細
with tab_detail:
    df, res = load_pair(pair, CONFIG["fetch_start"])
    snap = snapshot(df, pair=pair)
    n = PERIODS[period]
    res_v = res if n is None else res.tail(n)
    df_v = df if n is None else df.tail(n)
    fg = res["fear_greed"].dropna()

    pc = CONFIG["pairs"][pair]
    st.title(f"📊 為替版 Fear & Greed Index — {pair}")
    st.caption(
        f"**高スコア = 強欲 = リスクオン = {pair} 上昇** / **低スコア = 恐怖 = リスクオフ = {pair} 下落**。 "
        f"base={pc['base']} / quote={pc['quote']}。 最終データ: **{snap['date']}**")

    c1, c2, c3 = st.columns([1.4, 1, 1])
    with c1:
        st.plotly_chart(viz.gauge_figure(snap["fear_greed"], snap["label_ja"], _at_offset(fg, 5)),
                        use_container_width=True)
    with c2:
        st.markdown(f"#### {pair}")
        last2 = df["price"].dropna().tail(2)
        delta = float(last2.iloc[-1] - last2.iloc[-2]) if len(last2) == 2 else None
        st.metric("現在値", _fmt_price(snap["price"]),
                  f"{delta:+.4f}" if delta is not None else None)
        ma50 = df["price"].rolling(50).mean().iloc[-1]
        ma200 = df["price"].rolling(200).mean().iloc[-1]
        st.metric("50日 / 200日 移動平均", f"{_fmt_price(ma50)} / {_fmt_price(ma200)}",
                  "上昇トレンド" if snap["price"] > ma200 else "下降トレンド", delta_color="off")
    with c3:
        st.markdown("#### 通貨VIX(実現ボラ)")
        rv = res["realized_vol_pct"].dropna()
        cur = float(rv.iloc[-1]); pctl = float((rv.tail(252) < cur).mean() * 100)
        regime = "落ち着き" if pctl < 33 else ("ストレス" if pctl > 66 else "通常")
        st.metric("年率実現ボラ", f"{cur:.1f}%", f"{regime}(1年内 {pctl:.0f}パーセンタイル)", delta_color="off")
        st.caption("※ 無料のFXインプライドボラ源が無いため実現ボラで代替")

    st.divider()
    st.subheader(f"📈 FX Fear & Greed Index の推移({period})")
    st.plotly_chart(
        viz.index_timeseries_figure(res_v["fear_greed"].dropna(), df_v["price"], overlay_price=overlay),
        use_container_width=True)

    left, right = st.columns([1.3, 1])
    with left:
        st.subheader("🧩 構成要素の内訳")
        comp_names = list(CONFIG["components"].keys())
        latest_comp = res[comp_names].dropna(how="all").iloc[-1]
        st.plotly_chart(viz.component_bar_figure(latest_comp), use_container_width=True)
        if pd.isna(latest_comp.get("rate_diff")):
            st.caption("※ 金利差は未取得(EUR/GBP/AUD は FRED キーで有効化)")
    with right:
        st.subheader("🕒 過去との比較")
        for name, v in [("現在", _at_offset(fg, 0)), ("1週間前", _at_offset(fg, 5)),
                        ("1ヶ月前", _at_offset(fg, 21)), ("1年前", _at_offset(fg, 252))]:
            if v is not None:
                st.metric(name, f"{v:.1f}  〔{label_for(v)[1]}〕")

    st.divider()
    v1, v2 = st.columns(2)
    with v1:
        st.subheader("🌡️ 通貨VIX(実現ボラ + 株式VIX)")
        st.plotly_chart(
            viz.vix_figure(res_v["realized_vol_pct"].dropna(), df_v.get("vix")),
            use_container_width=True)
    with v2:
        st.subheader(f"💱 {pair} 現在値と移動平均")
        st.plotly_chart(
            viz.price_figure(df_v["price"],
                             df["price"].rolling(50).mean().reindex(df_v.index),
                             df["price"].rolling(200).mean().reindex(df_v.index)),
            use_container_width=True)

# ============================================================================= 多通貨概要
with tab_overview:
    st.subheader("🌐 多通貨 Fear & Greed 概要")
    st.caption("全通貨ペアのセンチメントを一覧。高=強欲(リスクオン)/低=恐怖(リスクオフ)。")
    rows = load_overview(tuple(CONFIG["pairs"].keys()), CONFIG["fetch_start"])
    valid = [r for r in rows if r.get("fear_greed") is not None]
    if valid:
        st.plotly_chart(
            viz.overview_bar_figure([r["pair"] for r in valid], [r["fear_greed"] for r in valid]),
            use_container_width=True)
        table = pd.DataFrame([{
            "ペア": r["pair"],
            "Fear & Greed": r["fear_greed"],
            "判定": r["label_ja"],
            "現在値": _fmt_price(r["price"]),
            "実現ボラ%": r["realized_vol_pct"],
        } for r in rows])
        st.dataframe(table, use_container_width=True, hide_index=True)
    else:
        st.warning("データを取得できませんでした。")

st.divider()
st.caption(
    "データ源(無料): 価格=yfinance / 米国債=米財務省 / 日本国債=財務省MoF / 建玉=CFTC / "
    "EUR・GBP・AUD金利=FRED(任意キー)。 方法論: docs/methodology_usdjpy.md。 "
    "限界: 実現ボラは終値ベース・無料のFXインプライドボラ/リスクリバーサルは未対応。")
