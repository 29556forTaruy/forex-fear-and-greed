# Forex Fear & Greed Index

CNN の [Fear & Greed Index](https://edition.cnn.com/markets/fear-and-greed) を **為替** に翻案するプロジェクト。
まず **USD/JPY** から始め、最終的に複数通貨の F&G 指数 + 通貨VIX + 現在値を表示するアプリを目指す。

## ゴール
1. **① CNN 指数の解明** — [`docs/methodology_cnn.md`](docs/methodology_cnn.md)
2. **② USD/JPY 版 F&G 指数** — [`docs/methodology_usdjpy.md`](docs/methodology_usdjpy.md)
3. **③ 多通貨アプリ**(F&G + 通貨VIX + 現在値)— 段階2以降

## 指数の考え方(リスク選好型)
円は安全通貨のため、**高スコア = Greed = リスクオン = 円安 = USD/JPY 上昇**、
**低スコア = Fear = リスクオフ = 円高 = USD/JPY 下落**。極端な強欲はキャリー過熱・反転リスクの警告も兼ねる。

7 構成要素(すべて無料データ)。重みは [config.py](config.py) の `components` が単一ソース:

| 要素 | 重み | 内容 |
|---|---|---|
| momentum | 0.18 | 価格 vs 125日移動平均 |
| realized_vol | 0.18 | 20日実現ボラ(通貨VIX)・反転 |
| rate_diff | 0.18 | base−quote 金利差の水準 + 60日変化 |
| risk_regime | 0.14 | VIX / 日経 / S&P500 / AUDJPY のクロスアセット |
| strength | 0.12 | 52週レンジ位置 |
| cot | 0.10 | CFTC 投機筋ネット建玉 |
| breadth | 0.10 | クロス円の上昇の広がり(JPYペアのみ) |

ある時点で欠損している要素は分子・分母の両方から外し、残りの重みを再正規化する
([`fng/index.py`](fng/index.py) `aggregate`)。非JPYペアでは breadth が無いため分母は 0.90 になる。

## かんたん起動
- **Mac**: `run.command` を **ダブルクリック**(初回だけ自動セットアップ → ブラウザが開く)
- **ターミナル**: `./run.sh`(同一Wi-Fiのスマホ等から見るなら `SHARE=1 ./run.sh`)

## セットアップ(手動)
```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt   # アプリ実行のみ
# .venv/bin/python -m pip install -r requirements-dev.txt  # ノートブック生成も行う場合
```
データはすべて **無料・APIキー不要**(yfinance / 米財務省 / 財務省JGB / CFTC)。
任意で `FRED_API_KEY` を設定すると EUR/GBP/AUD を含むペアの金利差要素が有効化。

## Web公開(Streamlit Community Cloud・無料)

### 同梱データ方式(なぜ速いか)
公開環境では「初回アクセスが遅い」「クラウドIPからの外部API取得が失敗しうる」の2点が問題になる。
そこで `build_dataset()` の出力を **リポジトリに同梱**(`data/seed/*.parquet`・全6ペアで約700KB)し、
アプリは既定でこれを読む。**全6ペアの読み込みが 23秒 → 0.5秒**になり、外部APIが落ちていても表示できる。

本指数は日次終値ベースなので、同梱データが最大1営業日古くても指数値は変わらない。
同梱データは GitHub Actions([`.github/workflows/refresh-seed.yml`](.github/workflows/refresh-seed.yml))が
**毎日 23:00 UTC(NYクローズ後)に更新**してコミットする。手動更新は下記:

```bash
.venv/bin/python scripts/refresh_seed.py            # 全ペア
.venv/bin/python scripts/refresh_seed.py --pair USDJPY
```

アプリ内のサイドバー「🔄 最新データを取得」を押すと、その場でライブ取得に切り替わる
(失敗した場合は同梱データに自動フォールバックし、空ページにはならない)。

### デプロイ手順
1. このリポジトリを GitHub に push。
2. https://share.streamlit.io にGitHubでログイン → **New app**。
3. リポジトリ / ブランチ `main` / Main file path `app.py` を選択(Python は 3.12 推奨)。
4. **Deploy** → 数分で `https://<name>.streamlit.app` が発行され、どこからでも閲覧可能。
   - 任意: Advanced settings → Secrets に `FRED_API_KEY="..."` を入れると金利差要素が全ペアで有効化。
   - 同じキーを GitHub の **Settings → Secrets and variables → Actions** に `FRED_API_KEY` として
     登録すると、日次更新される同梱データ側にも金利差要素が入る。

## 使い方
```bash
# 📊 ダッシュボード(段階2)— headlineゲージ + FX F&G時系列チャート + 6要素 + 通貨VIX + 現在値
.venv/bin/streamlit run app.py            # http://localhost:8501

# 当日のスナップショット(headline + 6要素内訳)を表示
.venv/bin/python -m fng.index --pair USDJPY

# 段階1 検証ノートブック(生成・実行済み)
#   notebooks/01_usdjpy_validation.ipynb をJupyterで開く、または再生成:
.venv/bin/python notebooks/_build_notebook.py
```

### ダッシュボードの内容
- **headline ゲージ**(0–100・5ゾーン色分け・1週前比デルタ)
- **FX Fear & Greed Index の時系列チャート**(ゾーン背景 + USD/JPY オーバーレイ・期間切替)
- **6 構成要素の内訳**(横棒)
- **過去との比較**(現在 / 1週間前 / 1ヶ月前 / 1年前)
- **通貨VIX**(USD/JPY 実現ボラ + 株式VIX)と **USD/JPY 現在値**(50/200日MA)

## ディレクトリ構成
```
app.py                 Streamlit ダッシュボード
config.py              設定の単一ソース(重み・窓・ペア・データ源)
docs/                  方法論ドキュメント(CNN解明 / USDJPY設計 / 詳細解説)
data_sources/          取得層(prices/rates/positioning/load/seed)
fng/                   計算コア(indicators/components/index)+ viz(plotlyチャート)
scripts/refresh_seed.py 同梱データの再生成
.github/workflows/     同梱データの日次更新(GitHub Actions)
notebooks/             段階1 検証ノートブック
data/seed/             同梱データ(Gitで追跡・アプリの既定の読み込み元)
data/cache/            ライブ取得時の作業キャッシュ(gitignore)
data/reports/          検証チャート
```

## 検証(2024年8月キャリー巻き戻し)
指数は強欲(≈78)→ 極度の恐怖(≈7-12)へ正しく急落。COT は円ネットショート過熱(≈99)→ 投げ(≈0)。
→ [`data/reports/validation_overview.png`](data/reports/validation_overview.png) /
[`data/reports/validation_aug2024.png`](data/reports/validation_aug2024.png)

## 対応通貨ペア(段階3)
JPY クロス: **USDJPY / EURJPY / GBPJPY / AUDJPY**、主要: **EURUSD / GBPUSD**。
ペアは [config.py](config.py) の `currencies`(CFTC名・利回り源)+ `pairs`(base/quote)で定義し、追加は数行で可能。
JPY クロスには **JPY-strength breadth**(クロス円の上昇広がり)要素を追加。
EUR/GBP/AUD を含むペアの金利差要素は無料の **FRED キー** で有効化(US/JP は無料・キー不要)。

## ロードマップ
- **段階1(完了)**: USD/JPY 指数をノートブックで構築・検証。
- **段階2(完了)**: Streamlit ダッシュボード化(FX F&G 時系列チャート含む)。
- **段階3(完了)**: 多通貨化(6ペア)+ JPY-strength breadth 要素 + 多通貨概要タブ。
- **公開(完了)**: 同梱データ + GitHub Actions 日次更新で、Streamlit Cloud に常時公開できる状態に。
- **今後**: (予算次第で)インプライドボラ/25Δリスクリバーサル(スキュー)への高度化、対応ペア拡充。

## 関連
データ取得・指標計算・config-as-code は隣接プロジェクト `../ForexProjection`(NZDJPY パイプライン)の設計を踏襲。
