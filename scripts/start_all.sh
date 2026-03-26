#!/bin/bash

# ログディレクトリ作成
mkdir -p ~/logs

# Python 3.11（pyenv）のパスを設定
export PATH="$HOME/.pyenv/versions/3.11.9/bin:$PATH"
PYTHON="$HOME/.pyenv/versions/3.11.9/bin/python3.11"
VENV="$HOME/projects/langgraph-orchestrator/.venv/bin"

# ① n8n起動
echo "n8n起動中..."
nohup n8n start > ~/logs/n8n.log 2>&1 &
echo "n8n PID: $!"

# 少し待つ
sleep 3

# ② FastAPI（LangGraph）起動
echo "FastAPI起動中..."
cd ~/projects/langgraph-orchestrator
nohup $VENV/uvicorn main:app --host 0.0.0.0 --port 8001 > ~/logs/fastapi.log 2>&1 &
echo "FastAPI PID: $!"

# 少し待つ
sleep 2

# ③ Discord Bot起動
echo "Discord Bot起動中..."
nohup $VENV/python ~/projects/langgraph-orchestrator/discord_bot.py > ~/logs/discord_bot.log 2>&1 &
echo "Discord Bot PID: $!"

echo "全プロセス起動完了"