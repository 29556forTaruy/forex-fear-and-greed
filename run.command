#!/bin/bash
# ダブルクリックで起動(macOS)。初回だけ依存をインストールし、ブラウザが自動で開く。
cd "$(dirname "$0")"

if [ ! -x .venv/bin/streamlit ]; then
  echo "初回セットアップ中です(数分かかります)…"
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
fi

echo ""
echo "ダッシュボードを起動します。ブラウザが自動で開きます。"
echo "終了するには このウィンドウで Ctrl+C を押すか、ウィンドウを閉じてください。"
echo ""
.venv/bin/python -m streamlit run app.py --server.port 8501
