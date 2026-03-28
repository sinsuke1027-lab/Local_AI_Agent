#!/bin/bash
# 夜間バッチ開発モード起動スクリプト
# cron/launchdから呼び出す用

LOG_DIR="$HOME/projects/langgraph-orchestrator/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/night_batch_$(date +%Y-%m-%d).log"

echo "=== 夜間バッチ開始: $(date) ===" >> "$LOG_FILE"

# プロジェクトディレクトリに移動
cd "$HOME/projects/langgraph-orchestrator" || exit 1

# 仮想環境を有効化
source .venv/bin/activate

# FastAPIが起動しているか確認、していなければ起動
if ! curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo "FastAPIが未起動のため起動します..." >> "$LOG_FILE"
    uvicorn main:app --host 0.0.0.0 --port 8001 &
    sleep 5
fi

# バッチ実行
python -m src.batch_runner --max-tasks 10 >> "$LOG_FILE" 2>&1

echo "=== 夜間バッチ完了: $(date) ===" >> "$LOG_FILE"
