# LangGraph Orchestrator — 開発ロードマップ

**最終更新: 2026-04-04 (M7-2完)**

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
  - [x] complexity_scorer.py（ルールベース事前フィルタ RULE_BASED_SKIP_THRESHOLD=5 + LLM判定）
  - [x] debate_agent.py（architect / security / performance 3視点 + 統合判定）
  - [x] debate_feedback 別フィールド化（instruction肥大化対策）
  - [x] debate結果のSQLite保存（complexity_score / debate_triggered / debate_result カラム追加）
  - [x] ChromaDB衝突修正（chroma_client.py シングルトンパターン）
- [x] P10a: 分析基盤（self_improver.py — モデル統計分析・改善提案・Discord通知）
- [x] P10b: プロンプト外部化（prompt_loader.py + prompts/*.md 全5エージェント）
  - [x] render_prompt() 空行圧縮（`\n{3,}` → `\n\n`、LLMのプロンプトエコー防止）

### M5-1: リモートアクセス基盤
- [x] Discord Bot 常時起動（launchd: com.langgraph.discord-bot）
- [x] FastAPI 常時起動（launchd: com.langgraph.fastapi、ポート8001）
- [x] FastAPI 認証追加（src/auth.py — X-API-Key ヘッダー、/health はスキップ）
- [x] .env バグ修正（LANGFUSE_HOST/DISCORD_TOKEN が同一行に結合されていた問題）
- [x] discord_bot.py に load_dotenv() 追加
- [x] batch_runner.py API Key ヘッダー追加
- [x] Tailscale インストール・接続（Mac mini + スマホ、100.72.133.8 で接続確認済み）
- [x] n8n API Key ヘッダー設定（手動）

### M5-2 Phase 1: Streamlit Agent Control Panel
- [x] streamlit_app.py 新規作成（3ページ構成）
  - 📊 ステータス: 最新タスク情報 + 直近24h統計（SQLite直接）
  - 📝 タスク投入: フォーム → FastAPI /task（timeout=600s）
  - 📋 タスク履歴: フィルタ/検索/詳細表示（SQLite直接）
- [x] launchd 常時起動（com.langgraph.streamlit、0.0.0.0:8501）
- [x] filesystem_mcp.py の npx フルパス対応（launchd環境で /opt/homebrew/bin/npx が未検索）

### M5-2 Phase 2: Streamlit 機能拡張 & HITL
- [x] **Phase 2-A: レポート閲覧ページ**
  - [x] reports/ ディレクトリのMarkdownファイル一覧表示・閲覧（st.markdown）
- [x] **Phase 2-B: プロンプト編集UI**
  - [x] prompts/*.md の表示・編集・保存・リセット機能
  - [x] 編集前後の差分表示（difflib）
- [x] **HITL (Human-in-the-loop) 承認モード**
  - [x] 2段階承認フロー（①設計確認 ②ファイル保存前確認）の実装
  - [x] SQLite `pending_approvals` テーブルによる非同期承認待ち管理
  - [x] Streamlit「🔔 承認待ち」ページ追加

### M5-2 Phase 3: プロジェクト管理の効率化
- [x] **プロジェクト自動取得 & 選択UI**
  - [x] `~/projects/` およびタスク履歴DBからのプロジェクト名自動抽出
  - [x] Streamlit 上でのプルダウン選択（プロジェクト切り替え）機能
  - [x] 「(新規作成)」モードによる動的なプロジェクト追加対応


### M7-1: FastAPI 非同期化
- [x] `asyncio.to_thread()` によるバックグラウンドタスク実行の実装
- [x] タスク投入時の即時レスポンス（Task ID返却）と非同期処理の分離


**アクセス先**: http://localhost:8501 / http://192.168.1.10:8501 / http://(Tailscale IP):8501

---

## 🔧 残タスク（優先度順）



---

### 🟠 M5-3: 手書き修正指示（Claude Vision連携）
- [ ] 設計・要件策定
- [ ] 写真アップロード → Claude Vision API（claude-opus-4-6 / claude-sonnet-4-6）でOCR+解釈
- [ ] 解釈結果をタスク形式に変換
- [ ] Streamlit UI からの投入（写真アップロード → タスク投入フォームに反映）
- [ ] またはDiscord経由（画像添付 → Bot経由で解釈）

**実装ファイル**: `src/vision_agent.py`（新規）、`streamlit_app.py`（ページ追加）

---

### 🟡 M6: 品質・コスト最適化

#### M6-1: モデル自動選択
- [x] complexity_score に基づくモデル自動切替ロジック整備
  - score ≤ 3: qwen2.5-coder:7b
  - score 4〜6: qwen2.5-coder:14b
  - score ≥ 7: gemini-2.5-flash
- [x] projects.json の model_override との組み合わせルール（優先順: model_override > confidential > is_debug > complexity）

**実装ファイル**: `src/nodes.py`（`_get_model_by_complexity()` 追加、`task_analyzer` 順序修正）

#### M6-2: コスト追跡の精緻化
- [ ] Gemini API コストの正確な記録（現在 token_count * 0.000002 でOllama想定計算）
- [ ] モデル別の単価定数テーブル（src/cost_table.py 新規）
- [ ] Langfuse ダッシュボードとの照合ワークフロー確立

#### M6-3: タスクテンプレート
- [ ] よく使うタスクパターンのテンプレート化（templates/*.md）
- [ ] Streamlit UI からテンプレート選択 → タスク投入

#### M6-4: プロダクト・コンサルタント (相談モード)
- [x] **企画・要件定義エージェントの実装**
  - [x] `prompts/consultant_agent.md` の作成（PM/建築家ロール）
  - [x] `task_analyzer` による相談内容の自動検知ロジック
  - [x] `consultant_agent` ノードによるリサーチ&要件定義提案
  - [x] 相談結果を `docs/plans/` へ自動保存する仕組み



---

### 🟡 M7: スケールアップ



#### M7-2: LangGraph 並列実行 & タスクキュー
- [x] **複数タスクの同時処理（asyncio.Queue + Worker方式）**
  - [x] `MAX_CONCURRENT_TASKS=2` によるリソース保護と並列実行の両立
- [x] **エージェント内部の並列化**
  - [x] `debate_agent` の3視点レビューを `ThreadPoolExecutor` で並列化し高速化
- [x] **待ち行列の可視化**
  - [x] Streamlit 上でのキュー状態（待ち数・実行中タスク）の表示

#### M7-3: GitHub 連携強化
- [ ] PR 自動作成（gh CLI or PyGithub）
- [ ] レビュー結果に基づく自動マージ
- [ ] GitHub Actions との連携

#### M7-4: A2A Protocol 対応
- [ ] エージェント間通信の標準化（Google A2A Protocol）
- [ ] 外部エージェントへのタスク委譲

---

### 🔵 P9 残課題（優先度低）
- [ ] GeminiWrapper 二重実装の統合（debate_agent.py と nodes.py で別々に定義）
- [ ] reviewer_agent REJECTED後のリトライと debate_agent の関係整理（現状はリトライ後にdebateが再トリガーされる可能性）
- [ ] debate_threshold の projects.json からの動的読み込み（現状は nodes.py の定数 DEBATE_THRESHOLD=7 固定）

---

### 🔵 その他技術課題（優先度低）
- [ ] プロジェクト固有憲法の projects.json 紐付け（project_constitution.md はあるが未連携）
- [ ] tasks.json の FAILED タスク群の棚卸し（T003〜T033 に多数のFAILEDあり）
- [ ] test_generator で生成されたテストファイルの整理（ルートに散在中）

---

## 📊 進捗サマリー

| フェーズ | 完了 | 残り | 状態 |
|---------|------|------|------|
| M1〜M4 + P7〜P10b | 全完了 | 0 | ✅ |
| M5-1 リモートアクセス | 全完了 | 0 | ✅ |
| M5-2 Streamlit機能拡張 | 全完了 | 0 | ✅ |
| HITL 承認モード | 全完了 | 0 | ✅ |
| M5-3 Claude Vision | 0 | 5 | 🔧 次フェーズ |
| M6 品質・コスト最適化 | 2 | 4 | ✅ / 🟡 |
| M7 スケールアップ (並列化・行列対応済) | 2 | 6 | ✅ / 🟡 |
| P9残課題 | 0 | 3 | 🔵 低優先 |
| その他技術課題 | 0 | 3 | 🔵 低優先 |

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

## 🔑 認証・アクセス
- FastAPI: `X-API-Key` ヘッダー必須（`FASTAPI_API_KEY` in .env）
- Streamlit: 認証なし（Tailscale VPN内のみ公開）
- Tailscale IP: 100.72.133.8（Mac mini）

## 📁 主要ファイル構成
```
src/
  nodes.py          # LangGraphノード定義（10ノード）
  graph.py          # グラフ構築・ルーティング
  state.py          # TaskState定義
  auth.py           # FastAPI API Key認証
  prompt_loader.py  # プロンプト外部化（render_prompt）
  complexity_scorer.py  # タスク複雑度判定
  debate_agent.py   # マルチエージェントディベート
  self_improver.py  # 自己改善分析エージェント
  chroma_client.py  # ChromaDB シングルトンクライアント
  task_history_indexer.py  # タスク履歴RAGインデックス
  batch_runner.py   # 夜間バッチエンジン
  report_generator.py  # 日次/週次レポート生成
prompts/            # エージェントプロンプトテンプレート（*.md）
  coder_agent.md
  reviewer_agent.md
  file_agent.md
  bash_agent.md
  search_agent.md
streamlit_app.py    # Streamlit Control Panel
main.py             # FastAPI エントリーポイント
discord_bot.py      # Discord Bot
```

## 🗃️ データ
- `~/.roo/task_history.db` — SQLite（tasksテーブル、15カラム）
- `~/.roo/chroma_db/` — ChromaDB（codebase + task_history コレクション）
- `~/projects/langgraph-orchestrator/reports/` — 日次/週次/バッチレポート
- `~/projects/langgraph-orchestrator/lessons.json` — エラー教訓DB
