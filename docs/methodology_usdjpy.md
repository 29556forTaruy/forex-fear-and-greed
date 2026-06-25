# ② USD/JPY Fear & Greed Index の設計

CNN の手法([methodology_cnn.md](methodology_cnn.md))を **為替(USD/JPY)** に翻案したもの。

## 0. 最重要: 符号規約(リスク選好型 / CNN流)

円は **安全通貨** なので、世界的な *恐怖* は円 *高* =**USD/JPY 下落** を生む(株式の恐怖=価格下落とは逆の関係)。
本指数は次のように定義する:

> - **0 = Extreme Fear** … リスクオフ / 円高 / キャリー巻き戻し / USD/JPY 下落。
> - **100 = Extreme Greed** … リスクオン / 円安 / キャリー過熱 / USD/JPY 上昇。

全6要素を「**高スコア = Greed = リスク選好 = USD/JPY 上昇圧力**」に揃える(必要な要素は内部反転)。
副次効果として、**極端な強欲は「キャリー過熱・反転リスク」の警告** にもなる(過去の巻き戻しは極端な
円ネットショート + 薄いキャリー対ボラ比で起きた)。

## 1. 正規化(全要素共通)

各要素の生シグナル `x_t` を **直近252営業日(=1年、変更可)の percentile** に変換 → 0–100。
反転要素は `100 − percentile`。
percentile は z-score よりレジーム変化に頑健(例: 2024→2026 の日米金利差圧縮 ~525bp→~250-300bp)。
実装: [`fng/indicators.py`](../fng/indicators.py) `rolling_percentile()` / `to_score()`。

## 2. 6 構成要素

| # | 要素 | 生シグナル | 反転 | 重み | データ源 | 状態 |
|---|------|-----------|------|------|----------|------|
| 1 | **モメンタム** | `(price − MA125)/MA125` | 否 | 0.18 | yfinance | 稼働 |
| 2 | **52週レンジ位置** | `(price − 安値)/(高値 − 安値)`×100 | 否 | 0.12 | yfinance | 稼働 |
| 3 | **実現ボラ(通貨VIX)** | 20日log-return標準偏差×√252 | **是** | 0.18 | yfinance | 稼働(近似) |
| 4 | **金利差&勢い** | (base−quote) 2Y/10Y の level と60日変化 | 否 | 0.18 | 米財務省 + MoF + (FRED) | 稼働 |
| 5 | **クロスアセット・リスク** | AUDJPY/日経/S&P モメンタム + VIX(反転) | 否 | 0.14 | yfinance | 稼働 |
| 6 | **投機筋ポジション(COT)** | ペア符号付きネット(+base −quote) | 否 | 0.10 | CFTC Socrata | 稼働(週次) |
| 7 | **JPY-strength breadth** | クロス円が上昇(円安)している割合 | 否 | 0.10 | yfinance | 稼働(JPYペアのみ) |

実装: [`fng/components.py`](../fng/components.py)。各要素の向き(全て高=greed):

1. **モメンタム** — USD/JPY が125日MA上 = 上昇トレンド = リスクオン = greed。
2. **52週レンジ位置** — 年初来高値圏 = 円安進行 = greed。
3. **実現ボラ** — 高ボラ = 動揺 = fear なので **反転**。「通貨VIX」の主指標(§4)。
4. **日米金利差** — 米金利が日本より高い/拡大 = キャリーが USD/JPY を支える = greed。
   2Y(政策期待)と10Y(期間/実質金利)の両方を使用。日本側欠損時は米単独で代用。
5. **クロスアセット・リスク** — AUDJPY(リスクの先行指標)・日経・S&P のモメンタム + VIX(内部反転)の平均。
   リスクオン = 円安要因 = greed。円の安全通貨性を指数に織り込む。
6. **COT** — 各通貨のCME先物(対USD)非商業ネットを `+base −quote` で合成(USDは numéraire)。
   USD/JPY なら `−JPYネット`(円ネットショート=キャリー過熱=greed)。EUR/JPY なら `+EUR −JPY`。
   ※ 反転リスクの警告として UI に併記すべき。週次・公表ラグあり。
7. **JPY-strength breadth**(段階3追加) — クロス円バスケット(USDJPY/EURJPY/GBPJPY/AUDJPY/CADJPY/CHFJPY)の
   うち20日モメンタムが正(=円安方向)の割合を percentile 化。広範な円安=リスクオン=greed。JPYクロスにのみ適用。

> **多通貨への一般化(段階3)**: 上記は USD/JPY を例にしているが、フレームワークは base/quote の組で一般化済み
> ([`config.py`](../config.py) の `currencies`/`pairs`)。対応ペア: USDJPY/EURJPY/GBPJPY/AUDJPY/EURUSD/GBPUSD。
> EUR/GBP/AUD の利回りは FRED 由来のため、それらを含むペアの金利差要素は FRED キーで有効化(US/JP は無料)。
> 欠損要素は重み再正規化で自動的に除外される。

## 3. 集約

```
score_i   = percentile(x_i)         (反転要素は 100 − percentile)
FearGreed = Σ w_i · score_i / Σ w_i   (その時点で利用可能な要素のみ。欠損は重み再正規化)
重み: momentum .20, strength .15, realized_vol .20, rate_diff .20, risk_regime .15, cot .10
```

ラベルは CNN のバンド(0–24 極度の恐怖 / 25–44 恐怖 / 45–55 中立 / 56–75 強欲 / 76–100 極度の強欲)。
実装: [`fng/index.py`](../fng/index.py) `aggregate()` / `snapshot()`。

## 4. 通貨VIX(実現ボラゲージ)

**無料の FX インプライド・ボラ源が存在しない** ため(CBOE JYVIX は実質終了、CVIX/VXY は有料・端末限定、
オプションATMボラ/25Δリスクリバーサルは有料)、MVP では **USD/JPY の実現ボラティリティ** を通貨VIXとする。

- 主指標: `RV20 = stdev(日次log return, 20) × √252`(年率%)。
- 文脈: `^VIX`(株式の恐怖指数)を副線で併記。
- 指数の要素3と同一値を使い、別パネルでも「現在RV + 1年percentile + Calm/Normal/Stressed ラベル + スパークライン」で表示。
- **限界**: 終値ベースで日中レンジを過小評価しがち / インプライドではなく実現(後ろ向き) / スキュー情報なし。
  → これが本指数の主要な「盲点」(§6)。

## 5. データ源(すべて無料)

| データ | 源 | キー | 備考 |
|--------|-----|------|------|
| USD/JPY, AUDJPY, 日経, S&P, 金, VIX | **yfinance** | 不要 | 日次終値。stooq はボット検証で不可。 |
| 米国債 2Y/10Y | **米財務省 日次CSV** | 不要 | 年別 CSV を結合。 |
| 日本国債 2Y/10Y | **財務省(MoF)JGB CSV** | 不要 | Shift-JIS、和暦、全history。 |
| CFTC 建玉(円先物) | **CFTC Socrata** | 不要 | 週次。net = 非商業 long − short。 |
| (任意) 金利の高品質版 | **FRED** | 無料キー | `FRED_API_KEY` があれば金利を上書き。 |

実装: [`data_sources/`](../data_sources/)(prices/rates/positioning/load)。

## 6. 検証結果(2024年8月キャリー巻き戻し)

2019–2026 の再構成で符号規約を検証:

- 2024年7月初: F&G **≈78(強欲)**、USD/JPY ≈161、COT スコア ≈99(極端な円ネットショート=キャリー過熱)。
- 2024年8月: F&G **≈7–12(極度の恐怖)** へ急落、USD/JPY ≈142 へ暴落、COT スコア ≈0(ショートカバー=投げ)。
- COVID(2020年3月)でも極度の恐怖を記録。

→ 指数は「リスクオフ=円高=恐怖」を正しく捉え、極端な強欲がキャリー過熱の警告として機能した。
チャート: [`data/reports/validation_overview.png`](../data/reports/validation_overview.png),
[`data/reports/validation_aug2024.png`](../data/reports/validation_aug2024.png)。

## 7. 既知の限界と今後の高度化

- **盲点**: 無料の FX インプライドボラ/25Δリスクリバーサル(オプション・スキュー)が無い。
  有料フィード(Refinitiv 等)導入時に、実現ボラ→1Mインプライドボラへ差し替え、第7要素「オプション・スキュー」を追加。
- 実現ボラは **Garman-Klass / Parkinson(OHLC)** 推定に強化可能(日中レンジを反映)。
- リテール建玉(IG/OANDA 等)を逆張り副要素として追加可能。
- 経済イベントリスク(BOJ/Fed/CPI 近接)要素の追加。
- COT は週次・ラグありのため、極端値の「警告」用途に限定して解釈。
- 段階3で他通貨へ拡張する際は、ペアごとに安全通貨性・キャリー脚の符号を [`config.py`](../config.py) で定義。
