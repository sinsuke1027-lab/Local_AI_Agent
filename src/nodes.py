import uuid
import os
import asyncio
import json
from datetime import datetime
from langchain_ollama import ChatOllama
from src.state import TaskState


# ── モデル設定 ──────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_DEFAULT   = "qwen2.5-coder:14b"
MODEL_DEBUG     = "deepseek-r1:14b"


def get_model(model_name: str):
    return ChatOllama(
        model=model_name,
        base_url=OLLAMA_BASE_URL,
    )


# ── ノード① タスク分析 ───────────────────────
def task_analyzer(state: TaskState) -> TaskState:
    """タスクを分析してモデルと次のノードを決定する"""
    instruction = state["instruction"].lower()

    # 複雑度スコアリング
    is_debug = any(w in instruction for w in [
        "バグ", "エラー", "デバッグ", "bug", "error", "fix"
    ])

    # モデル選択
    model = MODEL_DEBUG if is_debug else MODEL_DEFAULT

    # ファイル操作が必要かどうかを判定
    needs_file = any(w in instruction for w in [
        "作成", "ファイル", "フォルダ", "実装して", "書いて", "保存",
        "create", "file", "folder", "write", "save", "mkdir"
    ])

    # ChromaDBから関連コードを検索
    context_summary = ""
    try:
        from src.chroma_search import ChromaSearch
        import re as _re2
        searcher = ChromaSearch()

        # プロジェクトパスを推定
        proj_match = _re2.search(r"~/projects/([^/\s,、。]+)|/Users/[^/]+/projects/([^/\s,、。]+)", state.get("instruction", ""))
        if proj_match:
            proj_name = proj_match.group(1) or proj_match.group(2)
            proj_path = os.path.expanduser(f"~/projects/{proj_name}")
        else:
            proj_path = os.path.expanduser("~/projects/langgraph-orchestrator")

        context_summary = searcher.get_context_summary(instruction, project_path=proj_path)
    except Exception:
        context_summary = ""

    return {
        **state,
        "task_id":              state.get("task_id") or str(uuid.uuid4())[:8],
        "model_used":           model,
        "started_at":           datetime.now().isoformat(),
        "retry_count":          state.get("retry_count") or 0,
        "needs_file_operation": needs_file,
        "diff_summary":         context_summary,
    }


# ── ノード② コード実行エージェント ──────────────
def coder_agent(state: TaskState) -> TaskState:
    """選択されたモデルでタスクを実行する"""
    model       = get_model(state["model_used"])
    instruction = state["instruction"]
    retry_count = state.get("retry_count", 0)          # ←追加
    previous_result = state.get("result", "")          # ←追加

    # コンテキストを取得
    context = state.get("diff_summary", "")
    context_section = f"\n\n{context}" if context else ""

    # リトライ時は過去のエラー情報をプロンプトに含める ===
    error_feedback = ""
    if retry_count > 0 and previous_result:
        error_feedback = (
            f"\n\n【前回のテスト実行で以下のエラーが発生しました。原因を分析してコードを修正してください】\n"
            f"{previous_result[-3000:]}\n"
        )
    # 通常の会話の続きの場合は、過去の記憶を読み込ませる
    memory_feedback = ""
    # リトライではなく、かつ過去の履歴（previous_result）が残っている場合
    if retry_count == 0 and previous_result:
        memory_feedback = (
            f"\n\n【過去の作業の記憶（コンテキスト）】\n"
            f"あなたは直前に以下の作業を完了しています：\n"
            f"{previous_result[-3000:]}\n\n"
            f"※今回の指示（「さっきの〜」「それを〜」など）は、この過去の作業を指しています。文脈を引き継いで回答してください。\n"
        )

    prompt = f"""あなたは優秀なAIソフトウェアエンジニアです。
以下のタスクを実行してください。

タスク：{instruction}
{context_section}
{error_feedback}


【指示】
タスクの目的を的確に判断し、以下のルールに従って回答してください。
1. 「調査」「要約」「説明」のみを求めているタスクの場合：
   コードは一切記述せず、分かりやすいテキストだけで結果をまとめてください。
2. 「作成」「実装」「テスト」「スクリプト」などを求めているタスクの場合：
   実装方針を説明した上で、必ずPythonで実装コードを出力してください。
   また、pytest等の実行が必要な場合は、必ず「CMD: pytest ファイル名」の形式で記述してください。
3. Web検索やブラウザ取得結果がある場合は、その情報を最大限活用してください。
4. 既存コードがある場合はそのスタイルに合わせてください。"""

    try:
        response    = model.invoke(prompt)
        result      = response.content
        token_count = (
            response.usage_metadata.get("total_tokens", 0)
            if hasattr(response, "usage_metadata") and response.usage_metadata
            else 0
        )

        return {
            **state,
            "result":        result,
            "token_count":   token_count,
            "cost_estimate": round(token_count * 0.000002, 4),
        }
    except Exception as e:
        return {
            **state,
            "error_message": str(e),
            "result":        f"エラーが発生しました: {str(e)}",
        }


# ── ノード③ 履歴保存 ────────────────────────
def save_history(state: TaskState) -> TaskState:
    """タスク履歴をSQLiteに保存する"""
    import sqlite3
    import os

    db_path = os.path.expanduser("~/.roo/task_history.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id       TEXT PRIMARY KEY,
            project_id    TEXT,
            instruction   TEXT,
            model_used    TEXT,
            token_count   INTEGER,
            cost_estimate REAL,
            result        TEXT,
            error_message TEXT,
            started_at    TEXT,
            completed_at  TEXT,
            channel_id    TEXT,
            requester     TEXT
        )
    """)
    completed_at = datetime.now().isoformat()
    conn.execute("""
        INSERT OR REPLACE INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        state.get("task_id"),
        state.get("project_id"),
        state.get("instruction"),
        state.get("model_used"),
        state.get("token_count"),
        state.get("cost_estimate"),
        state.get("result"),
        state.get("error_message"),
        state.get("started_at"),
        completed_at,
        state.get("channel_id"),
        state.get("requester"),
    ))
    conn.commit()
    conn.close()

    return {
        **state,
        "completed_at": completed_at,
    }


# ── ノード④ レビューエージェント ────────────────
def reviewer_agent(state: TaskState) -> TaskState:
    """実装結果をレビューして合否を判定する"""
    model       = get_model(MODEL_DEBUG)
    instruction = state["instruction"]
    result      = state.get("result", "")
    retry_count = state.get("retry_count", 0)

    prompt = f"""あなたはシニアエンジニアです。
以下のタスクと実装結果をレビューしてください。

タスク：{instruction}

実装結果：
{result}

以下の基準で評価してください：
1. タスクの要件を満たしているか
2. コードに明らかなバグや問題がないか
3. 基本的な品質基準を満たしているか

最初の行に必ず以下のどちらかだけを記載してください：
APPROVED（承認）またはREJECTED（却下）

2行目以降にレビューコメントを記載してください。"""

    try:
        response       = model.invoke(prompt)
        review_content = response.content
        first_line     = review_content.strip().split('\n')[0].upper()
        approved       = 'APPROVED' in first_line

        return {
            **state,
            "quality_score": 1.0 if approved else 0.0,
            "review_result": review_content,
            "retry_count":   retry_count,
            "next_node":     "save_history" if approved else "retry",
        }
    except Exception as e:
        return {
            **state,
            "quality_score": 1.0,
            "next_node":     "save_history",
            "error_message": str(e),
        }


# ── ノード⑤ ファイル操作エージェント ────────────
def file_agent(state: TaskState) -> TaskState:
    """LLMの出力からコードを抽出してファイルに書き込む"""
    import re
    import os
    from src.filesystem_mcp import FilesystemMCP

    instruction = state["instruction"]
    result      = state.get("result", "")
    fs          = FilesystemMCP()
    model       = get_model(MODEL_DEFAULT)

    # プロジェクトディレクトリを推定
    import re as _re
    dir_pattern = r"/Users/[^/\s]+/projects/([^/\s]+)"
    dir_match   = _re.search(dir_pattern, instruction)
    if dir_match:
        proj_name = dir_match.group(1)
    else:
        tilde_match = _re.search(r"~/projects/([^/\s,、。]+)", instruction)
        proj_name   = tilde_match.group(1) if tilde_match else "myapp"
    proj_dir = f"/Users/shinsukeimanaka/projects/{proj_name}"

    prompt = (
        "あなたはファイル操作の専門家です。\n"
        "タスクと実装内容を元に、実際にファイルを作成してください。\n\n"
        f"タスク：{instruction}\n\n"
        f"実装内容：\n{result[:3000]}\n\n"
        f"プロジェクトディレクトリ：{proj_dir}\n\n"
        "必ず以下の形式でファイルを指定してください（この形式以外は使わないこと）：\n"
        f"FILE: {proj_dir}/ファイル名\n"
        "```python\n"
        "ファイルの内容\n"
        "```\n\n"
        "複数ファイルがある場合は繰り返してください。\n"
        "FILE:の行は必ず絶対パスで記述してください。"
    )

    try:
        response      = model.invoke(prompt)
        output        = response.content
        import re
        pattern       = r"FILE:\s*([^\n]+)\n```(?:\w+)?\n([\s\S]+?)```"
        matches       = re.findall(pattern, output)
        created_files = []

        for file_path, file_content in matches:
            file_path = file_path.strip()
            dir_path  = os.path.dirname(file_path)
            if dir_path:
                fs.create_directory(dir_path)
            if fs.write_file(file_path, file_content):
                created_files.append(file_path)

        file_result = (
            "以下のファイルを作成しました:\n" + "\n".join(created_files)
            if created_files else "ファイル操作はありませんでした"
        )

        return {
            **state,
            "changed_files": created_files,
            "result": state.get("result", "") + "\n\n【ファイル操作完了】\n" + file_result,
        }
    except Exception as e:
        return {
            **state,
            "error_message": f"ファイル操作エラー: {str(e)}",
        }

# ── ノード⑥ bash実行エージェント ────────────────
def bash_agent(state: TaskState) -> TaskState:
    """仮想環境セットアップ・コマンド実行・構文チェックを行う"""
    import re
    from src.bash_runner import BashRunner

    instruction   = state["instruction"]
    result        = state.get("result", "")
    changed_files = state.get("changed_files", [])
    model         = get_model(MODEL_DEFAULT)
    runner        = BashRunner()

    # プロジェクトディレクトリを推定
    project_dir = None
    for f in changed_files:
        project_dir = os.path.dirname(f)
        break
    if not project_dir:
        dir_pattern = r"/Users/[^/]+/projects/([^/\s]+)"
        match = re.search(dir_pattern, instruction + result)
        if match:
            project_dir = os.path.expanduser(
                f"~/projects/{match.group(1)}"
            )

    # 仮想環境のセットアップ
    venv_paths = None
    if project_dir:
        venv_paths = runner.setup_venv(project_dir)

    # LLMにコマンド計画を作成させる
    prompt = (
        "あなたはbash実行の専門家です。\n"
        "タスクと実装内容を元に、必要なbashコマンドを指定してください。\n\n"
        f"タスク：{instruction}\n\n"
        f"実装内容：\n{result[:2000]}\n\n"
        f"プロジェクトディレクトリ：{project_dir or '不明'}\n\n"
        "実行すべきコマンドを以下の形式で指定してください：\n"
        "CMD: コマンド（pip install・git init・pytest など）\n\n"
        "注意：\n"
        "・source activate は不要です（自動で仮想環境を使います）\n"
        "・python/pipのパスは自動で仮想環境のものに変換されます\n"
        "・mkdir は不要です（自動で作成されます）\n"
        "・アプリの起動コマンドは含めないでください"
    )

    try:
        response = model.invoke(prompt)
        output   = response.content
        pattern  = r"CMD:\s*([^\n]+)"
        commands = re.findall(pattern, output)

        results = []
        has_command_error = False  # ← 追加：コマンドエラーを追跡するフラグ

        for cmd in commands:
            cmd = cmd.strip()

            if venv_paths:
                cmd = runner.resolve_command(cmd, venv_paths)

            success, stdout, stderr = runner.run(cmd, cwd=project_dir)
            status = "✅" if success else "❌"
            
            if not success:
                has_command_error = True  # ← 追加：失敗したらフラグを立てる
                
            output_text = stdout.strip() or stderr.strip()
            results.append(f"{status} {cmd}\n{output_text[:300]}")

        # Pythonファイルの構文チェック
        syntax_results = []
        if venv_paths and changed_files:
            for f in changed_files:
                if f.endswith(".py"):
                    ok, err = runner.check_syntax(f, venv_paths)
                    if ok:
                        syntax_results.append(f"✅ 構文OK: {f}")
                    else:
                        syntax_results.append(f"❌ 構文エラー: {f}\n{err}")

        bash_result = "\n".join(results) if results else "実行するコマンドはありませんでした"
        if syntax_results:
            bash_result += "\n\n【構文チェック】\n" + "\n".join(syntax_results)

        has_syntax_error = any("構文エラー" in r for r in syntax_results)
        
        # 追加：コマンドエラーか構文エラーのどちらかがあればリトライ
        needs_retry = has_command_error or has_syntax_error

        return {
            **state,
            "result":           state.get("result", "") + f"\n\n【コマンド実行結果】\n{bash_result}",
            "next_node":        "retry" if needs_retry else "save_history",
            "retry_count":      state.get("retry_count", 0),
        }

    except Exception as e:
        return {
            **state,
            "error_message": f"bash実行エラー: {str(e)}",
        }

# ── ノード⑦ Web検索エージェント ────────────────
def search_agent(state: TaskState) -> TaskState:
    """Web検索を実行してリサーチ結果をstateに追加する"""
    from src.brave_search import BraveSearch

    instruction = state["instruction"]
    model       = get_model(MODEL_DEFAULT)

    # 検索クエリを生成
    query_prompt = (
        "以下のタスクに必要なWeb検索クエリを1〜3個生成してください。\n"
        f"タスク：{instruction}\n\n"
        "検索クエリのみを1行ずつ出力してください。説明は不要です。"
    )

    try:
        response = model.invoke(query_prompt)
        queries  = [q.strip() for q in response.content.strip().splitlines() if q.strip()][:3]

        searcher     = BraveSearch()
        search_results = []

        for query in queries:
            result = searcher.search_summary(query, count=3)
            if result:
                search_results.append(result)

        combined = "\n\n".join(search_results)

        # 既存のコンテキストに検索結果を追加
        existing = state.get("diff_summary", "")
        new_context = f"{existing}\n\n{combined}" if existing else combined

        return {
            **state,
            "diff_summary": new_context,
        }

    except Exception as e:
        return {
            **state,
            "error_message": f"検索エラー: {str(e)}",
        }

# ── ノード⑧ ブラウザエージェント ────────────────
def browser_agent(state: TaskState) -> TaskState:
    """指定されたURLをブラウザで読み込み、コンテンツをコンテキストに追加する"""
    import re
    from src.browser_client import BrowserClient

    instruction = state["instruction"]

    # タスク指示からURLを抽出（http:// または https:// から始まる文字列）
    urls = re.findall(r'https?://[^\s]+', instruction)

    if not urls:
        return state

    client = BrowserClient()
    browser_results = []

    for url in urls:
        try:
            content = client.get_page_content(url)
            browser_results.append(f"【ブラウザ取得結果: {url}】\n{content}")
        except Exception as e:
            browser_results.append(f"【ブラウザ取得エラー: {url}】\n{str(e)}")

    combined_browser_info = "\n\n".join(browser_results)

    # 既存のコンテキスト（diff_summary）に追記して、coder_agentに渡す
    existing = state.get("diff_summary", "")
    new_context = f"{existing}\n\n{combined_browser_info}" if existing else combined_browser_info

    return {
        **state,
        "diff_summary": new_context,
    }