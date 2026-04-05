# LangGraph Orchestrator — 開発ロードマップ

**最終更新: 2026-04-05 (技術的負債 T1-T5 完了)**

---

## ✅ 完了済み

### M1: 自律開発の基盤
- [x] FastAPI + LangGraph パイプライン構築
- [x] Ollama ローカルLLM統合（qwen2.5-coder:14b / deepseek-r1:14b / qwen2.5-coder:7b）
- [x] Discord Bot タスク投入・結果返信（n8n Webhook経由）
- [x] コード生成 → レビュー → ファイル作成 → テスト実行の自動化

### M2: 情報収集・コンテキスト活用
- [x] ChromaDB コードベース検索（chroma_search.py）
- [x] Brave Search Web検索（brave_search.py）
- [x] Playwright ブラウザ操作・ページ取得（browser_client.py）

### M3: 自律改善サイクル
- [x] lessons.json / lesson_manager（エラー教訓の蓄積）
- [x] constitution.md（共通憲法 + project_constitution.md）
- [x] task_planner / backlog_manager
- [x] context.md 自動生成
- [x] test_generator（テストコード自動生成）
- [x] file_watcher（ファイル変更監視）
- [x] report_generator（日次/週次レポート）

### M4: 自律性の強化
- [x] P7: 夜間バッチ開発モード（batch_runner.py + launchd: com.langgraph.nightbatch）
- [x] P8: タスク履歴RAG学習（task_history_indexer.py + ChromaDB collection: task_history）
- [x] P9: マルチエージェントディベート
  - [x] complexity_scorer.py（ルールベース事前フィルタ + LLM判定）
  - [x] debate_agent.py（architect / security / performance 3視点 + 統合判定）
  - [x] debate_feedback 別フィールド化（instruction肥大化対策）
  - [x] debate結果のSQLite保存（complexity_score / debate_triggered / debate_result カラム）
  - [x] ChromaDB衝突修正（chroma_client.py シングルトンパターン）
- [x] P10a: 分析基盤（self_improver.py — モデル統計分析・改善提案・Discord通知）
- [x] P10b: プロンプト外部化（prompt_loader.py + prompts/*.md 全6エージェント）
  - [x] render_prompt() 空行圧縮（`\n{3,}` → `\n\n`）

### M5-1: リモートアクセス基盤
- [x] Discord Bot 常時起動（launchd: com.langgraph.discord-bot）
- [x] FastAPI 常時起動（launchd: com.langgraph.fastapi、ポート8001）
- [x] FastAPI 認証追加（src/auth.py — X-API-Key ヘッダー）
- [x] Tailscale インストール・接続（Mac mini + スマホ、100.72.133.8 で接続確認済み）

### M5-2: Streamlit Agent Control Panel
- [x] streamlit_app.py（タスク投入・ステータス・履歴・承認・レポート・プロンプト編集）
- [x] launchd 常時起動（com.langgraph.streamlit、0.0.0.0:8501）
- [x] Phase 2-A: レポート閲覧ページ（reports/*.md 一覧表示・閲覧）
- [x] Phase 2-B: プロンプト編集UI（prompts/*.md 表示・編集・差分表示）
- [x] HITL 承認モード（2段階承認フロー + SQLite pending_approvals テーブル）
- [x] Phase 3: プロジェクト自動取得 & 選択UI（~/projects/ + DB 自動抽出）

### M5-3: スクリーンショット → Claude Vision 連携
- [x] screenshot_agent.py（Playwright による実行中アプリの自動撮影）
  - sync_playwright + ThreadPoolExecutor + macOS launchd 対応引数
- [x] vision_agent.py（claude-sonnet-4-6 で撮影画像を解釈 → タスク指示文生成）
- [x] Streamlit UI: 📸撮影 → AIに解釈させる → 指示文編集 → タスク投入フロー
- [x] state.screenshot_path / state.vision_hint フィールド追加

### M6-1: モデル自動選択
- [x] complexity_score に基づくモデル自動切替
  - score ≤ 3: qwen2.5-coder:7b / 4〜6: qwen2.5-coder:14b / ≥ 7: gemini-2.5-flash
- [x] projects.json の model_override との組み合わせルール

### M6-4: プロダクト・コンサルタント（相談モード）
- [x] prompts/consultant_agent.md 作成（PM/アーキテクトロール）
- [x] task_analyzer による相談内容の自動検知（"相談"/"要件"/"設計" 等のキーワード）
- [x] consultant_agent ノード実装（リサーチ & 要件定義提案 → HITL 承認フロー）

### M7-1: FastAPI 非同期化
- [x] asyncio.to_thread() によるバックグラウンドタスク実行

### M7-2: LangGraph 並列実行 & タスクキュー
- [x] asyncio.Queue（MAX_CONCURRENT_TASKS=2）によるタスクキュー
- [x] debate_agent の3視点を ThreadPoolExecutor で並列化
- [x] search_agent / browser_agent の複数クエリ並列化
- [x] Streamlit キュー状態表示（GET /queue/status）

### M8: プロジェクト実行・プレビュー基盤
- [x] M8-1: service_manager.py（Streamlitアプリを別プロセスで起動・停止・管理、ポート8502〜8510）
- [x] M8-2: ダイレクト・プレビューUI（iframeによる左右分割表示 + 修正タスク投入）
- [x] M8-3: フィードバック・キャプチャ（Playwright自動撮影 → state.screenshot_path → M5-3接続）

### 技術的負債解消（T1〜T5）
- [x] T1: GeminiWrapper を src/gemini_wrapper.py に統合（token追跡付き、循環import解消）
- [x] T2: debate_threshold の動的取得（projects.json の per-project / defaults から優先順位で取得）
- [x] T3: tasks.json の FAILED タスク43件をすべて ARCHIVED（サンプルコード向けと判断、tasks.json.bak にバックアップ）
- [x] T4: プロジェクト固有憲法リンク（Pattern A: projects.json の constitution_path + Pattern B: 自動検索）
- [x] T5: テストファイル統合（root の test_*.py を tests/ に移動、tests/__init__.py 作成）

---

## 🔧 残タスク（優先度順）

### 🟡 M6: 品質・コスト最適化（残り）

#### M6-2: コスト追跡の精緻化
- [ ] Gemini API コストの正確な記録（src/cost_table.py 新規 — モデル別単価定数テーブル）
- [ ] Langfuse ダッシュボードとの照合ワークフロー確立

#### M6-3: タスクテンプレート
- [ ] よく使うタスクパターンのテンプレート化（templates/*.md）
- [ ] Streamlit UI からテンプレート選択 → タスク投入

---

### 🟡 M7: スケールアップ（残り）

#### M7-3: GitHub 連携強化
- [ ] PR 自動作成（gh CLI or PyGithub）
- [ ] レビュー結果に基づく自動マージ
- [ ] GitHub Actions との連携

#### M7-4: A2A Protocol 対応
- [ ] エージェント間通信の標準化（Google A2A Protocol）
- [ ] 外部エージェントへのタスク委譲

---

### 🔵 残課題（優先度低）
- [ ] reviewer_agent REJECTED後のリトライと debate_agent の関係整理（リトライ後に debate が再トリガーされる可能性）
- [ ] Langfuse ダッシュボード活用の本格化（コスト・トレース可視化）

---

## 📊 進捗サマリー

| フェーズ | 完了 | 残り | 状態 |
|---------|------|------|------|
| M1〜M4 + P7〜P10b | 全完了 | 0 | ✅ |
| M5-1 リモートアクセス | 全完了 | 0 | ✅ |
| M5-2 Streamlit機能拡張 | 全完了 | 0 | ✅ |
| M5-3 Claude Vision | 全完了 | 0 | ✅ |
| M6 品質・コスト最適化 | M6-1, M6-4 完了 | M6-2, M6-3 | 🟡 |
| M7 スケールアップ | M7-1, M7-2 完了 | M7-3, M7-4 | 🟡 |
| M8 プレビュー基盤 | 全完了 | 0 | ✅ |
| 技術的負債 T1〜T5 | 全完了 | 0 | ✅ |

---

## 🏗️ 現在の稼働サービス構成

| サービス | ポート | 起動方法 | 状態 |
|---------|--------|---------|------|
| FastAPI (LangGraph Orchestrator) | 8001 | launchd: com.langgraph.fastapi | ✅ 常時起動 |
| Streamlit Control Panel | 8501 | launchd: com.langgraph.streamlit | ✅ 常時起動 |
| Discord Bot | — | launchd: com.langgraph.discord-bot | ✅ 常時起動 |
| 夜間バッチ | — | launchd: com.langgraph.nightbatch | ✅ cron登録済み |
| Langfuse | 3000 | Docker | ✅ 常時起動 |
| n8n | 5678 | Docker | ✅ 常時起動 |
| Ollama | 11434 | システム常駐 | ✅ 常時起動 |
| Managed Streamlit Apps | 8502〜8510 | service_manager.py（on demand） | 動的起動 |

## 🔑 認証・アクセス
- FastAPI: `X-API-Key` ヘッダー必須（`FASTAPI_API_KEY` in .env）
- Streamlit: 認証なし（Tailscale VPN内のみ公開）
- Tailscale IP: 100.72.133.8（Mac mini）

## 📁 主要ファイル構成
```
src/
  nodes.py               # LangGraphノード定義（13ノード）
  graph.py               # グラフ構築・ルーティング
  state.py               # TaskState定義
  auth.py                # FastAPI API Key認証
  prompt_loader.py       # プロンプト外部化（render_prompt）
  complexity_scorer.py   # タスク複雑度判定
  gemini_wrapper.py      # Google Gemini SDK 共通ラッパー（token追跡付き）
  debate_agent.py        # マルチエージェントディベート（3視点並列）
  screenshot_agent.py    # Playwright 自動スクリーンショット撮影
  service_manager.py     # Streamlitアプリ プロセス管理
  vision_agent.py        # Claude Vision API 画像解釈
  self_improver.py       # 自己改善分析エージェント
  chroma_client.py       # ChromaDB シングルトンクライアント
  task_history_indexer.py # タスク履歴RAGインデックス
  batch_runner.py        # 夜間バッチエンジン
  report_generator.py    # 日次/週次レポート生成
prompts/                 # エージェントプロンプトテンプレート（*.md）
  coder_agent.md
  reviewer_agent.md
  file_agent.md
  bash_agent.md
  search_agent.md
  consultant_agent.md
tests/                   # テストファイル（統合済み）
streamlit_app.py         # Streamlit Control Panel
main.py                  # FastAPI エントリーポイント
discord_bot.py           # Discord Bot
projects.json            # プロジェクト設定（モデル・憲法パス・debate閾値）
```

## 🗃️ データ
- `~/.roo/task_history.db` — SQLite（tasks / pending_approvals / services テーブル）
- `~/.roo/chroma_db/` — ChromaDB（codebase + task_history コレクション）
- `~/projects/langgraph-orchestrator/reports/` — 日次/週次/バッチレポート
- `~/projects/langgraph-orchestrator/lessons.json` — エラー教訓DB
- `~/projects/langgraph-orchestrator/screenshots/` — 自動撮影スクリーンショット
