"""為替版 Fear & Greed Index の計算コア。

- indicators : 純関数の指標(移動平均・実現ボラ・rolling percentile 等)
- components : 6 構成要素を 0–100 スコアへ変換
- index      : 構成要素を集約し headline 指数 + ラベルを算出
"""
