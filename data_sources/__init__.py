"""データ取得層(すべて無料・APIキー不要)。

- prices     : USD/JPY とリスク代理資産(AUDJPY, 日経, S&P, 金, VIX)— yfinance
- rates      : 日米金利 2Y/10Y — 米財務省CSV + 財務省(MoF)JGB(任意で FRED 上書き)
- positioning: CFTC 建玉(円先物・非商業ネット)— CFTC Socrata
- load       : すべてを USD/JPY の営業日グリッドに統合した DataFrame を返す
"""
