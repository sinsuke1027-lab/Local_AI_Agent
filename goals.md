# langgraph-orchestrator ゴール・マイルストーン

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

### M3: 自律改善サイクル（現在）
- エラー教訓の自動蓄積と再発防止
- 共通憲法・プロジェクト固有憲法による品質維持
- タスク自動洗い出し・バックログ管理
- context.md自動生成によるプロジェクト把握

### M4: 外部アクセス・UI ✅
- Tailscale + Cloudflare Tunnelによるリモートアクセス
- Streamlit Agent Control Panel
- 手書き修正指示（Claude Vision連携）

### M5: 外部アクセス・UI（拡張）
- M5-1: リモートアクセス基盤 ✅
- M5-2: Streamlit Agent Control Panel ✅
- M5-3: 手書き修正指示（Claude Vision連携）✅
  - スクリーンショット → Vision API（claude-sonnet-4-6）で解釈
  - 生成されたタスク指示文をStreamlit上で編集・投入
  - M8-3（フィードバック・キャプチャ）からの自然な接続

### M5（旧）: 品質・コスト最適化
- Langfuseダッシュボード活用
- タスクテンプレート
- クラウドAPI連携（Claude / Gemini）と複雑度による自動切替

### M6: スケールアップ
- LangGraph並列実行
- GitHub連携強化（PR自動作成・マージ）
- A2A Protocol対応

### M7: スケールアップ（並列・非同期）
- FastAPI asyncio.Queue によるタスクキュー（MAX_CONCURRENT_TASKS=2）
- debate_agent / search_agent / browser_agent の ThreadPoolExecutor 並列化
- コンサルタントエージェント（相談・要件定義モード）

### M8: プロジェクト実行・プレビュー基盤
- M8-1: サービスマネージャーの実装 ✅
  - AIが作成したStreamlitアプリを別プロセスで起動・停止・管理する
  - 空きポート（8502〜8510）の自動割り当て
  - Streamlit Control Panelからの起動・停止・リンク表示
- M8-2: ダイレクト・プレビューUI ✅
  - iframeによる左右分割表示（指示パネル + アプリ画面）
  - 修正指示をその場でタスク投入できるUI
- M8-3: フィードバック・キャプチャ ✅
  - Playwrightによる実行中アプリの自動スクリーンショット撮影
  - 撮影画像を修正指示タスクに添付する仕組み
  - M5-3（Claude Vision連携）への接続点を確保（state.screenshot_path）

## 成功指標
- 単純なアプリ開発タスクを人間の介入なしで完遂できる
- エラー発生時に過去の教訓を参照して自力で解決できる
- タスク完了後に次のアクションを自動提案できる
- 機密案件をローカルモデルのみで安全に処理できる
- 月間のAPI/インフラコストを5,000円以下に抑える
