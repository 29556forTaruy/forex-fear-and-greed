#!/bin/bash
# ターミナルから起動: ./run.sh   (同一Wi-Fiの他端末からも見たい場合は SHARE=1 ./run.sh)
cd "$(dirname "$0")"

if [ ! -x .venv/bin/streamlit ]; then
  echo "初回セットアップ中です(数分かかります)…"
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
fi

ARGS="--server.port 8501"
if [ "$SHARE" = "1" ]; then
  # 同一ネットワークの他端末(スマホ等)からアクセス可能にする
  ARGS="$ARGS --server.address 0.0.0.0"
  IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')
  echo "同一Wi-Fiの端末から:  http://$IP:8501  でアクセスできます"
fi

.venv/bin/python -m streamlit run app.py $ARGS
