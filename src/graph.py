from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.state import TaskState
from src.nodes import (
    task_analyzer, coder_agent, reviewer_agent, debate_agent,
    file_agent, bash_agent, search_agent, save_history, browser_agent,
    design_checkpoint, prefile_checkpoint, consultant_agent,
    DEBATE_THRESHOLD,
)

MAX_RETRY = 3


def increment_retry(state: TaskState) -> TaskState:
    return {
        **state,
        "retry_count": state.get("retry_count", 0) + 1,
    }


def route_after_analyzer(state: TaskState) -> str:
    """タスク分析後のルーティング：検索が必要かどうか判断"""
    instruction = state.get("instruction", "").lower()

    # M6-4: 相談モードはリサーチ → コンサルタントへ
    if state.get("is_consultation"):
        return "search_agent"

    # URLが含まれているか、ブラウザ関連のワードがあればブラウザエージェントへ
    needs_browser = any(w in instruction for w in [
        "http://", "https://", "ブラウザ", "スクレイピング", "読み込んで"
    ])
    if needs_browser:
        return "browser_agent"

    needs_search = any(w in instruction for w in [
        "調べて", "リサーチ", "検索", "調査", "最新",
        "競合", "市場", "トレンド", "方法", "とは",
        "search", "research", "find", "latest",
    ])

    if needs_search:
        return "search_agent"
    return "coder_agent"


def route_after_search(state: TaskState) -> str:
    """検索後のルーティング: 相談モードならconsultant_agent、通常はdesign_checkpoint"""
    if state.get("is_consultation"):
        return "consultant_agent"
    return "design_checkpoint"

def route_after_bash(state: TaskState) -> str:
    """bash実行後のルーティング：エラーがあればリトライ"""
    next_node   = state.get("next_node", "save_history")
    retry_count = state.get("retry_count", 0)

    if next_node == "retry" and retry_count < MAX_RETRY:
        return "retry"
    return "save_history"

def route_after_review(state: TaskState) -> str:
    """レビュー後のルーティング"""
    next_node   = state.get("next_node", "save_history")
    retry_count = state.get("retry_count", 0)

    # REJECTED → 通常リトライ（ディベート不要）
    if next_node == "retry" and retry_count < MAX_RETRY:
        return "retry"

    # APPROVED かつ複雑度が高い かつ未ディベート → debate_agent
    complexity       = state.get("complexity_score", 0)
    already_debated  = state.get("debate_triggered", False)
    debate_threshold = state.get("debate_threshold", DEBATE_THRESHOLD)

    if complexity >= debate_threshold and not already_debated:
        return "debate_agent"

    if state.get("needs_file_operation", False):
        return "file_agent"

    return "save_history"


def route_after_debate(state: TaskState) -> str:
    """ディベート後のルーティング"""
    next_node   = state.get("next_node", "save_history")
    retry_count = state.get("retry_count", 0)

    if next_node == "retry" and retry_count < MAX_RETRY:
        return "increment_retry"

    if state.get("needs_file_operation", False):
        return "prefile_checkpoint"

    return "save_history"


def route_after_design_checkpoint(state: TaskState) -> str:
    """設計確認後のルーティング"""
    if state.get("next_node") == "retry":
        # 相談モードの修正依頼はコンサルタントへ戻す、通常はretry
        if state.get("is_consultation"):
            return "consultant_agent"
        return "increment_retry"
    # 相談モードで承認 → 保存して終了
    if state.get("is_consultation"):
        return "save_history"
    return "coder_agent"


def route_after_prefile_checkpoint(state: TaskState) -> str:
    """ファイル保存前確認後のルーティング"""
    if state.get("next_node") == "retry":
        return "increment_retry"
    return "file_agent"


def route_after_file(state: TaskState) -> str:
    """ファイル操作後のルーティング"""
    instruction = state.get("instruction", "").lower()

    needs_bash = any(w in instruction for w in [
        "インストール", "install", "実行", "run",
        "テスト", "test", "git", "pytest",
        "pip", "npm", "起動", "環境構築",
    ])

    if needs_bash:
        return "bash_agent"
    return "save_history"


def route_after_review_hitl(state: TaskState) -> str:
    """レビュー後のルーティング（HITL統合版）"""
    next_node   = state.get("next_node", "save_history")
    retry_count = state.get("retry_count", 0)

    if next_node == "retry" and retry_count < MAX_RETRY:
        return "retry"

    complexity       = state.get("complexity_score", 0)
    already_debated  = state.get("debate_triggered", False)
    debate_threshold = state.get("debate_threshold", DEBATE_THRESHOLD)

    if complexity >= debate_threshold and not already_debated:
        return "debate_agent"

    if state.get("needs_file_operation", False):
        return "prefile_checkpoint"  # HITL追加：ファイル保存前に確認

    return "save_history"


def build_graph():
    graph = StateGraph(TaskState)

    # ── ノードを追加 ──
    graph.add_node("task_analyzer",       task_analyzer)
    graph.add_node("search_agent",        search_agent)
    graph.add_node("consultant_agent",    consultant_agent)    # M6-4
    graph.add_node("browser_agent",       browser_agent)
    graph.add_node("design_checkpoint",   design_checkpoint)   # HITL①
    graph.add_node("coder_agent",         coder_agent)
    graph.add_node("reviewer_agent",      reviewer_agent)
    graph.add_node("debate_agent",        debate_agent)
    graph.add_node("prefile_checkpoint",  prefile_checkpoint)  # HITL②
    graph.add_node("increment_retry",     increment_retry)
    graph.add_node("file_agent",          file_agent)
    graph.add_node("bash_agent",          bash_agent)
    graph.add_node("save_history",        save_history)

    # ── エッジを追加 ──
    graph.set_entry_point("task_analyzer")

    # task_analyzer → design_checkpoint（HITL①）→ coder_agent
    graph.add_conditional_edges(
        "task_analyzer",
        route_after_analyzer,
        {
            "browser_agent":      "browser_agent",
            "search_agent":       "search_agent",
            "coder_agent":        "design_checkpoint",  # 必ずdesign_checkpointを経由
        }
    )

    graph.add_edge("browser_agent", "design_checkpoint")

    # search_agent → consultant_agent (相談モード) or design_checkpoint (通常)
    graph.add_conditional_edges(
        "search_agent",
        route_after_search,
        {
            "consultant_agent": "consultant_agent",
            "design_checkpoint": "design_checkpoint",
        }
    )

    # consultant_agent → design_checkpoint (HITL①でユーザー確認)
    graph.add_edge("consultant_agent", "design_checkpoint")

    graph.add_conditional_edges(
        "design_checkpoint",
        route_after_design_checkpoint,
        {
            "coder_agent":      "coder_agent",
            "consultant_agent": "consultant_agent",
            "save_history":     "save_history",
            "increment_retry":  "increment_retry",
        }
    )

    graph.add_edge("coder_agent", "reviewer_agent")

    # reviewer_agent → prefile_checkpoint（HITL②）or debate or save
    graph.add_conditional_edges(
        "reviewer_agent",
        route_after_review_hitl,
        {
            "retry":              "increment_retry",
            "debate_agent":       "debate_agent",
            "prefile_checkpoint": "prefile_checkpoint",
            "save_history":       "save_history",
        }
    )

    graph.add_conditional_edges(
        "debate_agent",
        route_after_debate,
        {
            "increment_retry":    "increment_retry",
            "prefile_checkpoint": "prefile_checkpoint",
            "save_history":       "save_history",
        }
    )

    graph.add_conditional_edges(
        "prefile_checkpoint",
        route_after_prefile_checkpoint,
        {
            "file_agent":     "file_agent",
            "increment_retry": "increment_retry",
        }
    )

    graph.add_conditional_edges(
        "file_agent",
        route_after_file,
        {
            "bash_agent":   "bash_agent",
            "save_history": "save_history",
        }
    )

    graph.add_edge("increment_retry", "coder_agent")
    graph.add_conditional_edges(
        "bash_agent",
        route_after_bash,
        {
            "retry":        "increment_retry",
            "save_history": "save_history",
        }
    )
    graph.add_edge("save_history", END)

    # 記憶領域（インメモリ）の初期化
    memory = MemorySaver()

    # グラフのコンパイル（checkpointerとしてmemoryを渡す）
    return graph.compile(checkpointer=memory)


orchestrator = build_graph()