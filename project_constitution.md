# langgraph-orchestrator 固有憲法

## プロジェクト固有ルール
- FastAPI は port 8001 で起動する
- LangGraph のノード追加時は必ず graph.py のルーティングも更新する
- state.py の TaskState に新フィールドを追加する場合は Optional で定義する
- MCP サーバーとの通信は subprocess + JSON-RPC で行う（既存パターンに合わせる）

## 使用ライブラリ制約
- langchain==0.2.16 / langchain-core==0.2.39 で固定（上位バージョンは互換性未検証）
- langfuse==2.60.0 で固定
- langgraph==0.2.28 で固定
- 新しいライブラリ追加時は .venv 内でテストしてから requirements.txt に追記する

## 環境
- Python 3.11（pyenv 管理）
- 仮想環境: ~/projects/langgraph-orchestrator/.venv/
- Ollama: http://localhost:11434
- Langfuse: http://localhost:3000
- n8n: http://localhost:5678

## 注意事項
- Python 3.14 は使用禁止（langfuse・langchain が非対応）
- Discord Bot Token は .env に格納（GitHub push protection で過去にブロックされた）
- mcp_config.json に Brave API キーが含まれるため .gitignore 必須
