import uuid
import os
import asyncio
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from src.state import TaskState
from src.task_history_indexer import TaskHistoryIndexer
from src.complexity_scorer import score_complexity
from src.debate_agent import run_debate, DebateResult
from src.prompt_loader import render_prompt

logger = logging.getLogger(__name__)

load_dotenv()

# ── モデル設定 ──────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_DEFAULT   = "qwen2.5-coder:14b"
MODEL_DEBUG     = "deepseek-r1:14b"
MODEL_FAST      = "gemini-2.5-flash"
MODEL_LOCAL_FAST  = "qwen2.5-coder:7b"

# P9: ディベート閾値（projects.jsonのdefaults.debate_thresholdで上書き可能）
DEBATE_THRESHOLD = 7


class GeminiWrapper:
    """Google公式SDKをlangchain風のインターフェースで使うラッパー"""

    def __init__(self, model_name: str):
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY が .env に設定されていません")
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def invoke(self, prompt: str):
        """langchainのmodel.invoke()と同じインターフェースで呼び出す"""
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
        )

        # langchain風のレスポンスオブジェクトを返す
        class GeminiResponse:
            def __init__(self, text, usage):
                self.content = text
                self.usage_metadata = usage

        # トークン数を取得
        usage = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = {
                "total_tokens": (
                    getattr(response.usage_metadata, "total_token_count", 0) or
                    (getattr(response.usage_metadata, "prompt_token_count", 0) or 0) +
                    (getattr(response.usage_metadata, "candidates_token_count", 0) or 0)
                )
            }

        return GeminiResponse(response.text, usage)


def get_model(model_name: str):
    """モデル名に応じてOllamaまたはGeminiのモデルを返す"""
    if "gemini" in model_name.lower():
        return GeminiWrapper(model_name)
    return ChatOllama(
        model=model_name,
        base_url=OLLAMA_BASE_URL,
    )


def _resolve_project_dir(state: TaskState) -> str:
    """stateからプロジェクトディレクトリを推定する"""
    import re
    instruction = state.get("instruction", "")

    # 絶対パスを検索
    match = re.search(r"/Users/[^/\s]+/projects/([^/\s,、。]+)", instruction)
    if match:
        return os.path.expanduser(f"~/projects/{match.group(1)}")

    # ~/projects/ 形式を検索
    match = re.search(r"~/projects/([^/\s,、。]+)", instruction)
    if match:
        return os.path.expanduser(f"~/projects/{match.group(1)}")

    # project_idから推定
    project_id = state.get("project_id", "")
    if project_id and project_id != "default":
        return os.path.expanduser(f"~/projects/{project_id}")

    return os.path.expanduser("~/projects/langgraph-orchestrator")


def _load_constitution(project_dir: str) -> str:
    """共通憲法 + プロジェクト固有憲法を読み込む"""
    sections = []

    # 共通憲法
    global_path = os.path.expanduser(
        "~/projects/langgraph-orchestrator/constitution.md"
    )
    if os.path.exists(global_path):
        try:
            with open(global_path, "r", encoding="utf-8") as f:
                sections.append(f.read()[:2000])
        except Exception:
            pass

    # プロジェクト固有憲法
    for name in ["constitution.md", "project_constitution.md"]:
        proj_path = os.path.join(project_dir, name)
        if os.path.exists(proj_path):
            try:
                with open(proj_path, "r", encoding="utf-8") as f:
                    sections.append(f.read()[:1500])
            except Exception:
                pass

    if sections:
        return "\n\n".join(sections)
    return ""


def _get_model_for_project(project_dir: str, is_debug: bool = False) -> str:
    """projects.jsonからプロジェクトに適したモデルを決定する"""
    projects_path = os.path.expanduser(
        "~/projects/langgraph-orchestrator/projects.json"
    )

    if os.path.exists(projects_path):
        try:
            with open(projects_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            project_name = os.path.basename(project_dir)
            project_info = data.get("projects", {}).get(project_name, {})

            # model_overrideがあれば最優先
            if project_info.get("model_override"):
                return project_info["model_override"]

            # 機密プロジェクトはローカルモデル強制
            if project_info.get("confidential", False):
                return data.get("defaults", {}).get(
                    "model_confidential", MODEL_DEFAULT
                )
        except Exception:
            pass

    return MODEL_DEBUG if is_debug else MODEL_DEFAULT


# ── ノード① タスク分析 ───────────────────────
def task_analyzer(state: TaskState) -> TaskState:
    """タスクを分析してモデルと次のノードを決定する"""
    instruction = state["instruction"].lower()
    project_dir = _resolve_project_dir(state)

    # 複雑度スコアリング
    is_debug = any(w in instruction for w in [
        "バグ", "エラー", "デバッグ", "bug", "error", "fix"
    ])

    # プロジェクト設定に基づくモデル選択
    model = _get_model_for_project(project_dir, is_debug)

    # ファイル操作が必要かどうかを判定
    needs_file = any(w in instruction for w in [
        "作成", "ファイル", "フォルダ", "実装して", "書いて", "保存",
        "create", "file", "folder", "write", "save", "mkdir"
    ])

    # ChromaDBから関連コードを検索
    context_summary = ""
    try:
        from src.chroma_search import ChromaSearch
        searcher = ChromaSearch()
        context_summary = searcher.get_context_summary(instruction, project_path=project_dir)
    except Exception:
        context_summary = ""

    # context.mdを読み込み/生成
    project_context = ""
    try:
        from src.context_generator import ContextGenerator
        generator = ContextGenerator()
        project_context = generator.load_context(project_dir)
    except Exception:
        project_context = ""

    # 教訓を検索
    lesson_text = ""
    try:
        from src.lesson_manager import LessonManager
        manager = LessonManager()
        lesson_text = manager.get_prompt_injection(instruction, project_dir=project_dir)
    except Exception:
        lesson_text = ""

    # 全コンテキストを結合
    full_context_parts = []
    if project_context:
        full_context_parts.append(f"【プロジェクト情報】\n{project_context[:1500]}")
    if context_summary:
        full_context_parts.append(context_summary)
    if lesson_text:
        full_context_parts.append(lesson_text)
    full_context = "\n\n".join(full_context_parts)

    # --- P8: 過去の成功パターン検索 ---
    success_patterns = ""
    try:
        indexer = TaskHistoryIndexer()
        success_patterns = indexer.get_success_patterns(
            task_description=state.get("instruction", ""),
            n=3,
        )
        if success_patterns:
            logger.info("Found success patterns for task (length=%d)", len(success_patterns))
        else:
            logger.info("No success patterns found for this task")
    except Exception as e:
        logger.warning("Failed to search success patterns: %s", e)

    # --- P9: 複雑度スコア算出 ---
    complexity = 5  # DEFAULT_SCORE
    try:
        complexity = score_complexity(state.get("instruction", ""))
        logger.info("Complexity score: %d", complexity)
    except Exception as e:
        logger.warning("Complexity scoring failed: %s", e)

    return {
        **state,
        "task_id":              state.get("task_id") or str(uuid.uuid4())[:8],
        "model_used":           model,
        "started_at":           datetime.now().isoformat(),
        "retry_count":          state.get("retry_count") or 0,
        "needs_file_operation": needs_file,
        "diff_summary":         full_context,
        "success_patterns":     success_patterns,
        "complexity_score":     complexity,
        "debate_triggered":     False,
    }


# ── ノード② コード実行エージェント ──────────────
def coder_agent(state: TaskState) -> TaskState:
    """選択されたモデルでタスクを実行する"""
    model       = get_model(state["model_used"])
    instruction = state["instruction"]
    retry_count = state.get("retry_count", 0)
    previous_result = state.get("result", "")
    project_dir = _resolve_project_dir(state)

    # コンテキストを取得
    context = state.get("diff_summary", "")
    context_section = f"\n\n{context}" if context else ""

    # 憲法を読み込み
    constitution = _load_constitution(project_dir)
    constitution_section = f"\n\n【遵守事項（憲法）】\n{constitution}" if constitution else ""

    # リトライ時は過去のエラー情報をプロンプトに含める
    error_feedback = ""
    if retry_count > 0 and previous_result:
        error_feedback = (
            f"\n\n【前回のテスト実行で以下のエラーが発生しました。原因を分析してコードを修正してください】\n"
            f"{previous_result[-3000:]}\n"
        )

    # 通常の会話の続きの場合は、過去の記憶を読み込ませる
    memory_feedback = ""
    if retry_count == 0 and previous_result:
        memory_feedback = (
            f"\n\n【過去の作業の記憶（コンテキスト）】\n"
            f"あなたは直前に以下の作業を完了しています：\n"
            f"{previous_result[-3000:]}\n\n"
            f"※今回の指示（「さっきの〜」「それを〜」など）は、この過去の作業を指しています。文脈を引き継いで回答してください。\n"
        )

    # --- P8: 成功パターンをプロンプトに注入 ---
    success_patterns = state.get("success_patterns", "")
    success_patterns_section = ""
    if success_patterns:
        success_patterns_section = f"""

## 過去の成功パターン（参考）
以下は類似タスクで成功した過去の実装例です。参考にしてください:

{success_patterns}
"""

    # --- P9: ディベートフィードバックをプロンプトに注入 ---
    debate_feedback = state.get("debate_feedback", "")
    debate_feedback_section = f"\n\n{debate_feedback}" if debate_feedback else ""

    prompt = render_prompt(
        "coder_agent",
        instruction=instruction,
        context_section=context_section,
        constitution_section=constitution_section,
        error_feedback=error_feedback,
        memory_feedback=memory_feedback,
        success_patterns_section=success_patterns_section,
        debate_feedback_section=debate_feedback_section,
    )

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


# ── ノード③ 履歴保存 + 教訓抽出 + 次タスク提案 ──
def _ensure_debate_columns(conn) -> None:
    """debate関連カラムが存在しなければ追加する（冪等）。"""
    cursor = conn.execute("PRAGMA table_info(tasks)")
    existing = {row[1] for row in cursor.fetchall()}

    stmts = []
    if "complexity_score" not in existing:
        stmts.append("ALTER TABLE tasks ADD COLUMN complexity_score INTEGER")
    if "debate_triggered" not in existing:
        stmts.append("ALTER TABLE tasks ADD COLUMN debate_triggered BOOLEAN DEFAULT 0")
    if "debate_result" not in existing:
        stmts.append("ALTER TABLE tasks ADD COLUMN debate_result TEXT")

    for stmt in stmts:
        conn.execute(stmt)
    if stmts:
        conn.commit()
        logger.info("Added %d debate columns to tasks table", len(stmts))


def save_history(state: TaskState) -> TaskState:
    """タスク履歴をSQLiteに保存し、必要に応じて教訓抽出と次タスク提案を行う"""
    import sqlite3

    db_path = os.path.expanduser("~/.roo/task_history.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id          TEXT PRIMARY KEY,
            project_id       TEXT,
            instruction      TEXT,
            model_used       TEXT,
            token_count      INTEGER,
            cost_estimate    REAL,
            result           TEXT,
            error_message    TEXT,
            started_at       TEXT,
            completed_at     TEXT,
            channel_id       TEXT,
            requester        TEXT
        )
    """)

    # P9: debate関連カラムのマイグレーション（初回のみ実行、以降はスキップ）
    _ensure_debate_columns(conn)

    completed_at = datetime.now().isoformat()
    conn.execute("""
        INSERT OR REPLACE INTO tasks
            (task_id, project_id, instruction, model_used, token_count, cost_estimate,
             result, error_message, started_at, completed_at, channel_id, requester,
             complexity_score, debate_triggered, debate_result)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
        state.get("complexity_score"),
        1 if state.get("debate_triggered") else 0,
        state.get("debate_result", ""),
    ))
    conn.commit()
    conn.close()

    project_dir = _resolve_project_dir(state)

    # エラーがあった場合、教訓を自動抽出
    error_message = state.get("error_message", "")
    if error_message and state.get("retry_count", 0) > 0:
        try:
            from src.lesson_manager import LessonManager
            manager = LessonManager()
            manager.extract_and_save_lesson(
                error_message=error_message,
                solution_result=state.get("result", ""),
                instruction=state.get("instruction", ""),
                project_dir=project_dir,
            )
        except Exception:
            pass

    # タスク成功時に次タスク提案
    if not error_message:
        try:
            from src.task_planner import TaskPlanner
            planner = TaskPlanner()

            # 現在のタスクをDONEに（tasks.jsonにあれば）
            # 次タスクを自動洗い出し
            context_md = ""
            try:
                from src.context_generator import ContextGenerator
                gen = ContextGenerator()
                context_md = gen.load_context(project_dir)
            except Exception:
                pass

            planner.plan_next_tasks(
                project_dir=project_dir,
                completed_instruction=state.get("instruction", ""),
                completed_result=state.get("result", "")[:2000],
                context_md=context_md,
            )
        except Exception:
            pass

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
    project_dir = _resolve_project_dir(state)

    # 憲法をレビュー基準に含める
    constitution = _load_constitution(project_dir)
    constitution_section = ""
    if constitution:
        constitution_section = f"\n\n【レビュー時の遵守事項（憲法）】\n{constitution[:1500]}"

    prompt = render_prompt(
        "reviewer_agent",
        instruction=instruction,
        result=result,
        constitution_section=constitution_section,
    )

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



# ── ノード⑤ P9: マルチエージェントディベート ──────
def debate_agent(state: TaskState) -> TaskState:
    """複雑度が高いタスクのコードを3視点でレビューし、必要なら修正を要求する"""
    code        = state.get("result", "")
    instruction = state.get("instruction", "")

    if not code:
        logger.warning("Debate: no code to review, skipping")
        return {
            **state,
            "debate_triggered": True,
            "debate_result":    "",
            "next_node":        "save_history",
        }

    result = run_debate(code=code, instruction=instruction)

    if result.verdict == "NEEDS_REVISION":
        # ✅ debate_feedbackに格納（instructionは不変）
        logger.info("Debate verdict: NEEDS_REVISION — routing to coder_agent retry")
        return {
            **state,
            "debate_triggered": True,
            "debate_result":    result.summary,
            "debate_feedback":  result.to_prompt_context(),
            "next_node":        "retry",
        }
    else:
        logger.info("Debate verdict: APPROVED — routing to save_history")
        return {
            **state,
            "debate_triggered": True,
            "debate_result":    result.summary,
            "debate_feedback":  "",
            "next_node":        "save_history",
        }


# ── ノード⑥ ファイル操作エージェント ────────────
def file_agent(state: TaskState) -> TaskState:
    """LLMの出力からコードを抽出してファイルに書き込む"""
    import re
    from src.filesystem_mcp import FilesystemMCP

    instruction = state["instruction"]
    result      = state.get("result", "")
    fs          = FilesystemMCP()
    model       = get_model(state.get("model_used", MODEL_DEFAULT))
    project_dir = _resolve_project_dir(state)

    prompt = render_prompt(
        "file_agent",
        instruction=instruction,
        result=result[:3000],
        project_dir=project_dir,
    )

    try:
        response      = model.invoke(prompt)
        output        = response.content
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

        # テストコード自動生成
        test_files = []
        try:
            from src.test_generator import TestGenerator
            test_gen = TestGenerator()
            test_files = test_gen.generate_for_changed_files(created_files, instruction)
        except Exception:
            pass

        file_result = (
            "以下のファイルを作成しました:\n" + "\n".join(created_files)
            if created_files else "ファイル操作はありませんでした"
        )
        if test_files:
            file_result += "\n\nテストファイルを自動生成しました:\n" + "\n".join(test_files)

        return {
            **state,
            "changed_files": created_files + test_files,
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
    model         = get_model(state.get("model_used", MODEL_DEFAULT))
    runner        = BashRunner()
    project_dir   = _resolve_project_dir(state)

    # 仮想環境のセットアップ
    venv_paths = None
    if project_dir:
        venv_paths = runner.setup_venv(project_dir)

    # LLMにコマンド計画を作成させる
    prompt = render_prompt(
        "bash_agent",
        instruction=instruction,
        result=result[:2000],
        project_dir=project_dir or "不明",
    )

    try:
        response = model.invoke(prompt)
        output   = response.content
        pattern  = r"CMD:\s*([^\n]+)"
        commands = re.findall(pattern, output)

        results = []
        has_command_error = False

        for cmd in commands:
            cmd = cmd.strip()

            if venv_paths:
                cmd = runner.resolve_command(cmd, venv_paths)

            success, stdout, stderr = runner.run(cmd, cwd=project_dir)
            status = "✅" if success else "❌"

            if not success:
                has_command_error = True

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
    model       = get_model(state.get("model_used", MODEL_DEFAULT))

    query_prompt = render_prompt(
        "search_agent",
        instruction=instruction,
    )

    try:
        response = model.invoke(query_prompt)
        queries  = [q.strip() for q in response.content.strip().splitlines() if q.strip()][:3]

        searcher       = BraveSearch()
        search_results = []

        for query in queries:
            result = searcher.search_summary(query, count=3)
            if result:
                search_results.append(result)

        combined = "\n\n".join(search_results)

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

    existing = state.get("diff_summary", "")
    new_context = f"{existing}\n\n{combined_browser_info}" if existing else combined_browser_info

    return {
        **state,
        "diff_summary": new_context,
    }
