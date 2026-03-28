# langgraph-orchestrator

## 概要
ローカルAIエージェント基盤（LangGraph + Ollama）

## 技術スタック
- Python 3.11
- FastAPI
- Flask
- LangChain
- LangGraph
- Langfuse
- ChromaDB
- Ollama
- Playwright
- Discord.py
- pytest

## ディレクトリ構造
```
├── scripts
│   └── start_all.sh
├── src
│   ├── __init__.py
│   ├── backlog_manager.py
│   ├── bash_runner.py
│   ├── brave_search.py
│   ├── browser_client.py
│   ├── calc.py
│   ├── chroma_search.py
│   ├── context_generator.py
│   ├── file_watcher.py
│   ├── filesystem_mcp.py
│   ├── graph.py
│   ├── lesson_manager.py
│   ├── mcp_tools.py
│   ├── nodes.py
│   ├── report_generator.py
│   ├── state.py
│   ├── task_planner.py
│   └── test_generator.py
├── .env.example
├── .gitignore
├── README.md
├── bash_runner.py
├── calc.py
├── constitution.md
├── discord_bot.py
├── goals.md
├── index.html
├── lessons.json
├── main.py
├── mcp_config.example.json
├── project_constitution.md
├── projects.json
├── requirements.txt
├── test_calc.py
├── test_example.py
├── test_fail.py
├── test_hello.py
├── test_playwright.py
└── ファイル名
```

## 主要ファイル
- `README.md`: LangGraph Orchestrator
- `bash_runner.py`
- `calc.py`: --- src/calc.py ---
- `constitution.md`: 共通憲法（Global Constitution）
- `discord_bot.py`: ── 設定 ──────────────────────────────────
- `goals.md`: langgraph-orchestrator ゴール・マイルストーン
- `index.html`
- `lessons.json`
- `main.py`
- `mcp_config.example.json`
- `project_constitution.md`: langgraph-orchestrator 固有憲法
- `projects.json`
- `requirements.txt`
- `test_calc.py`: test_calc.py
- `test_example.py`: ~/projects/langgraph-orchestrator/test_example.py
- `test_fail.py`: test_fail.py
- `test_hello.py`
- `test_playwright.py`: ヘッドレスモードでChromiumを起動
- `src/__init__.py`
- `src/backlog_manager.py`
- `src/bash_runner.py`: 安全なbashコマンド実行クライアント
- `src/brave_search.py`: Brave Search MCPサーバーを直接呼び出すクライアント
- `src/browser_client.py`: src/browser_client.py
- `src/calc.py`: 2つの数の和を計算する
- `src/chroma_search.py`: ChromaDBからコードベースを検索するクライアント
- `src/context_generator.py`: プロジェクトのディレクトリを走査してcontext.mdを自動生成する
- `src/file_watcher.py`
- `src/filesystem_mcp.py`: filesystem MCPサーバーを直接呼び出すクライアント
- `src/graph.py`
- `src/lesson_manager.py`
- `src/mcp_tools.py`: MCPクライアントを返す
- `src/nodes.py`: ── モデル設定 ──────────────────────────────
- `src/report_generator.py`
- `src/state.py`: 基本情報
- `src/task_planner.py`
- `src/test_generator.py`

## 注意事項
プロジェクト固有の憲法あり。タスク実行前に参照すること。
