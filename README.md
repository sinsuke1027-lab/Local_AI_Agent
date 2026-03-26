# LangGraph Orchestrator

ローカルAIエージェント自律開発基盤

## セットアップ
```bash
# 1. 仮想環境作成
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. 環境変数設定
cp .env.example .env
# .envを編集してAPIキーを設定

# 3. MCP設定
cp mcp_config.example.json mcp_config.json
# mcp_config.jsonを編集してAPIキーを設定

# 4. 起動
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

## 環境変数

`.env.example`を参照してください。
