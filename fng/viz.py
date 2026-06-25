"""ダッシュボード用の plotly 図ビルダ(純関数)。

plotly はブラウザ描画のため日本語ラベル可。各関数は data を受け取り go.Figure を返す。
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

# Fear & Greed のゾーン(下限, 上限, 色, ラベル)。
ZONES = [
    (0, 25, "#c0392b", "極度の恐怖"),
    (25, 45, "#e67e22", "恐怖"),
    (45, 55, "#95a5a6", "中立"),
    (55, 75, "#27ae60", "強欲"),
    (75, 100, "#145a32", "極度の強欲"),
]

# 構成要素の日本語ラベル。
COMPONENT_LABELS_JA = {
    "momentum": "モメンタム",
    "strength": "52週レンジ位置",
    "realized_vol": "実現ボラ(逆=安定)",
    "rate_diff": "日米金利差",
    "risk_regime": "リスク選好(株/VIX)",
    "cot": "投機筋ポジション(COT)",
}


def _zone_color(value: float) -> str:
    for lo, hi, color, _ in ZONES:
        if lo <= value <= hi:
            return color
    return "#95a5a6"


def gauge_figure(value: float, label_ja: str, ref: float | None = None) -> go.Figure:
    """headline 値の 0–100 ゲージ(5ゾーン色分け + 1週前比のデルタ)。"""
    mode = "gauge+number+delta" if ref is not None else "gauge+number"
    fig = go.Figure(go.Indicator(
        mode=mode,
        value=round(value, 1),
        number={"font": {"size": 44}},
        delta=({"reference": round(ref, 1), "increasing": {"color": "#27ae60"},
                "decreasing": {"color": "#c0392b"}} if ref is not None else None),
        title={"text": f"<b>{label_ja}</b>", "font": {"size": 20}},
        gauge={
            "axis": {"range": [0, 100], "tickvals": [0, 25, 45, 55, 75, 100]},
            "bar": {"color": "rgba(0,0,0,0.75)", "thickness": 0.25},
            "steps": [{"range": [lo, hi], "color": color} for lo, hi, color, _ in ZONES],
            "threshold": {"line": {"color": "black", "width": 3}, "thickness": 0.8, "value": value},
        },
    ))
    fig.update_layout(height=300, margin=dict(l=30, r=30, t=60, b=10))
    return fig


def index_timeseries_figure(fear_greed: pd.Series, price: pd.Series | None = None,
                            overlay_price: bool = True) -> go.Figure:
    """FX Fear & Greed Index の時系列(ゾーン背景 + USD/JPY オーバーレイ)。"""
    fig = go.Figure()
    for lo, hi, color, _ in ZONES:
        fig.add_hrect(y0=lo, y1=hi, fillcolor=color, opacity=0.12,
                      line_width=0, layer="below")
    fig.add_trace(go.Scatter(
        x=fear_greed.index, y=fear_greed.values, name="Fear & Greed",
        line=dict(color="black", width=1.6), hovertemplate="%{x|%Y-%m-%d}<br>F&G %{y:.1f}<extra></extra>"))
    if overlay_price and price is not None and not price.empty:
        fig.add_trace(go.Scatter(
            x=price.index, y=price.values, name="USD/JPY", yaxis="y2",
            line=dict(color="#1f3a93", width=1, dash="dot"),
            hovertemplate="%{x|%Y-%m-%d}<br>USD/JPY %{y:.2f}<extra></extra>"))
    fig.update_layout(
        height=420, margin=dict(l=40, r=50, t=30, b=30),
        yaxis=dict(title="Fear & Greed (0-100)", range=[0, 100],
                   tickvals=[0, 25, 45, 55, 75, 100]),
        yaxis2=dict(title="USD/JPY", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hovermode="x unified",
    )
    return fig


def component_bar_figure(components: pd.Series) -> go.Figure:
    """6 構成要素の横棒(0=恐怖 .. 100=強欲)。"""
    comp = components.dropna()
    labels = [COMPONENT_LABELS_JA.get(k, k) for k in comp.index]
    colors = ["#27ae60" if v >= 55 else ("#c0392b" if v <= 45 else "#95a5a6") for v in comp.values]
    fig = go.Figure(go.Bar(
        x=comp.values, y=labels, orientation="h", marker_color=colors,
        text=[f"{v:.0f}" for v in comp.values], textposition="outside",
        hovertemplate="%{y}: %{x:.1f}<extra></extra>"))
    fig.add_vline(x=50, line_dash="dash", line_color="gray")
    fig.update_layout(
        height=300, margin=dict(l=10, r=20, t=20, b=30),
        xaxis=dict(title="スコア(0=恐怖 .. 100=強欲)", range=[0, 105]),
        yaxis=dict(autorange="reversed"))
    return fig


def vix_figure(realized_vol_pct: pd.Series, vix: pd.Series | None = None) -> go.Figure:
    """通貨VIX(USD/JPY 実現ボラ年率%)と 株式VIX のオーバーレイ。"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=realized_vol_pct.index, y=realized_vol_pct.values, name="USD/JPY 実現ボラ(年率%)",
        line=dict(color="#c0392b", width=1.4),
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:.1f}%<extra></extra>"))
    if vix is not None and not vix.empty:
        fig.add_trace(go.Scatter(
            x=vix.index, y=vix.values, name="株式VIX", yaxis="y2",
            line=dict(color="#7f8c8d", width=0.9),
            hovertemplate="%{x|%Y-%m-%d}<br>VIX %{y:.1f}<extra></extra>"))
    fig.update_layout(
        height=320, margin=dict(l=40, r=50, t=30, b=30),
        yaxis=dict(title="USD/JPY 実現ボラ(%)"),
        yaxis2=dict(title="株式VIX", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hovermode="x unified")
    return fig


def overview_bar_figure(pairs: list[str], values: list[float]) -> go.Figure:
    """多通貨概要: 各ペアの Fear & Greed を横棒で(ゾーン色 + 背景帯)。"""
    colors = [_zone_color(v) for v in values]
    fig = go.Figure(go.Bar(
        x=values, y=pairs, orientation="h", marker_color=colors,
        text=[f"{v:.0f}" for v in values], textposition="outside",
        hovertemplate="%{y}: %{x:.1f}<extra></extra>"))
    for lo, hi, color, _ in ZONES:
        fig.add_vrect(x0=lo, x1=hi, fillcolor=color, opacity=0.10, line_width=0, layer="below")
    fig.update_layout(
        height=max(220, 52 * len(pairs)), margin=dict(l=10, r=20, t=20, b=30),
        xaxis=dict(title="Fear & Greed(0=恐怖 .. 100=強欲)", range=[0, 105],
                   tickvals=[0, 25, 45, 55, 75, 100]),
        yaxis=dict(autorange="reversed"))
    return fig


def price_figure(price: pd.Series, ma_fast: pd.Series | None = None,
                 ma_slow: pd.Series | None = None) -> go.Figure:
    """USD/JPY 現在値チャート(50/200日移動平均)。"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=price.index, y=price.values, name="USD/JPY",
                             line=dict(color="#1f3a93", width=1.4)))
    if ma_fast is not None:
        fig.add_trace(go.Scatter(x=ma_fast.index, y=ma_fast.values, name="50日MA",
                                 line=dict(color="#e67e22", width=1, dash="dash")))
    if ma_slow is not None:
        fig.add_trace(go.Scatter(x=ma_slow.index, y=ma_slow.values, name="200日MA",
                                 line=dict(color="#27ae60", width=1, dash="dash")))
    fig.update_layout(height=320, margin=dict(l=40, r=20, t=30, b=30),
                      yaxis=dict(title="USD/JPY"),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                      hovermode="x unified")
    return fig
