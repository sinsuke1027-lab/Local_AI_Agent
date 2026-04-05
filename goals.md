# langgraph-orchestrator ゴール・マイルストーン

最終更新: 2026-04-05

## ビジョン
Mac mini M4上に、Claude Codeに並ぶ・超えるローカル自律AI開発環境を構築する。
コストを最小限に抑えながら、自律的なアプリ開発・タスク実行ができる仕組みを実現する。

## マイルストーン

### M1: 自律開発の基盤完成 ✅
- タスク投入 → コード生成 → レビュー → ファイル作成 → テスト実行の自動パイプライン
- ローカルLLM（Ollama）による完全オフライン動作
- Discord経由の双方向タスク管理

### M2: 情報収集・コンテキスト活用 ✅
- ChromaDBによる既存コードベースの検索・活用
- Brave Searchによるweb検索
- Playwrightによるブラウザ操作・ページ取得

### M3: 自律改善サイクル ✅
- エラー教訓の自動蓄積と再発防止（lessons.json / lesson_manager）
- 共通憲法・プロジェクト固有憲法による品質維持（constitution.md）
- タスク自動洗い出し・バックログ管理（task_planner / backlog_manager）
- context.md自動生成によるプロジェクト把握
- テストコード自動生成（test_generator）
- 日次/週次レポート生成（report_generator）

### M4: 自律性の強化 ✅
- 夜間バッチ開発モード（P7: batch_runner + launchd）
- タスク履歴RAG学習（P8: task_history_indexer + ChromaDB）
- マルチエージェントディベート（P9: 3視点 + 統合判定）
- 自己改善分析エージェント（P10a: self_improver）
- プロンプト外部化（P10b: prompt_loader + prompts/*.md）

### M5: 外部アクセス・UI拡張 ✅
- M5-1: リモートアクセス基盤（Tailscale + FastAPI認証）✅
- M5-2: Streamlit Agent Control Panel（タスク投入・履歴・承認・レポート）✅
  - Phase 2-A: レポート閲覧ページ ✅
  - Phase 2-B: プロンプト編集UI ✅
  - HITL 承認モード（2段階承認フロー）✅
  - Phase 3: プロジェクト自動取得 & 選択UI ✅
- M5-3: スクリーンショット → Claude Vision連携 ✅
  - screenshot_agent（Playwright自動撮影）→ vision_agent（claude-sonnet-4-6解釈）
  - 生成タスク指示文をStreamlit上で編集・投入

### M6: 品質・コスト最適化（一部完了）
- M6-1: 複雑度スコアに基づくモデル自動選択 ✅
  - score ≤ 3 → qwen2.5-coder:7b / 4〜6 → 14b / ≥ 7 → gemini-2.5-flash
- M6-2: Gemini APIコスト追跡の精緻化 ✅
  - src/cost_table.py（モデル別単価テーブル + calculate_cost()）
  - input_tokens / output_tokens / cost_usd / cost_jpy を SQLite に記録
  - docs/cost_tracking.md（照合ワークフロー）
- M6-3: タスクテンプレート（未着手）
- M6-4: プロダクト・コンサルタント（相談・要件定義モード）✅
  - consultant_agent ノード + prompts/consultant_agent.md

### M7: スケールアップ（並列・非同期）（一部完了）
- M7-1: FastAPI 非同期化（asyncio.to_thread）✅
- M7-2: LangGraph並列実行 & タスクキュー ✅
  - asyncio.Queue（MAX_CONCURRENT_TASKS=2）
  - debate / search / browser agent の ThreadPoolExecutor 並列化
  - Streamlit キュー状態表示
- M7-3: GitHub連携強化（PR自動作成・マージ）未着手
- M7-4: A2A Protocol対応（未着手）

### M8: プロジェクト実行・プレビュー基盤 ✅
- M8-1: サービスマネージャー（service_manager.py）✅
  - AIが作成したStreamlitアプリを別プロセスで起動・停止・管理
  - 空きポート（8502〜8510）の自動割り当て
- M8-2: ダイレクト・プレビューUI ✅
  - iframeによる左右分割表示（指示パネル + アプリ画面）
  - 修正指示をその場でタスク投入できるUI
- M8-3: フィードバック・キャプチャ ✅
  - Playwrightによる実行中アプリの自動スクリーンショット撮影
  - state.screenshot_path 経由で M5-3 に接続

### 技術的負債解消 ✅（2026-04-05）
- T1: GeminiWrapper を src/gemini_wrapper.py に統合（循環import解消・token追跡統一）
- T2: debate_threshold を projects.json から動的取得（per-project対応）
- T3: tasks.json の FAILED タスク43件をすべてARCHIVED（サンプルコード向けと判断）
- T4: プロジェクト固有憲法リンク（Pattern A: projects.json の constitution_path + Pattern B: 自動検索）
- T5: テストファイル統合（root の test_*.py を tests/ に移動、tests/__init__.py 作成）

## 次のフォーカス
- M6-2: Gemini APIコスト追跡の精緻化（src/cost_table.py 新規）
- M6-3: タスクテンプレート（templates/*.md + Streamlit UI）
- M7-3: GitHub連携強化（PR自動作成・マージ）

## 成功指標
- 単純なアプリ開発タスクを人間の介入なしで完遂できる
- エラー発生時に過去の教訓を参照して自力で解決できる
- タスク完了後に次のアクションを自動提案できる
- 機密案件をローカルモデルのみで安全に処理できる
- 月間のAPI/インフラコストを5,000円以下に抑える
