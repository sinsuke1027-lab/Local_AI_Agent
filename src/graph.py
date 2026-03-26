from langgraph.graph import StateGraph, END
from src.state import TaskState
from src.nodes import (
    task_analyzer, coder_agent, reviewer_agent,
    file_agent, bash_agent, search_agent, save_history
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

    needs_search = any(w in instruction for w in [
        "調べて", "リサーチ", "検索", "調査", "最新",
        "競合", "市場", "トレンド", "方法", "とは",
        "search", "research", "find", "latest",
    ])

    if needs_search:
        return "search_agent"
    return "coder_agent"


def route_after_review(state: TaskState) -> str:
    """レビュー後のルーティング"""
    next_node   = state.get("next_node", "save_history")
    retry_count = state.get("retry_count", 0)

    if next_node == "retry" and retry_count < MAX_RETRY:
        return "retry"

    if state.get("needs_file_operation", False):
        return "file_agent"

    return "save_history"


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


def build_graph():
    graph = StateGraph(TaskState)

    # ── ノードを追加 ──
    graph.add_node("task_analyzer",   task_analyzer)
    graph.add_node("search_agent",    search_agent)
    graph.add_node("coder_agent",     coder_agent)
    graph.add_node("reviewer_agent",  reviewer_agent)
    graph.add_node("increment_retry", increment_retry)
    graph.add_node("file_agent",      file_agent)
    graph.add_node("bash_agent",      bash_agent)
    graph.add_node("save_history",    save_history)

    # ── エッジを追加 ──
    graph.set_entry_point("task_analyzer")

    graph.add_conditional_edges(
        "task_analyzer",
        route_after_analyzer,
        {
            "search_agent": "search_agent",
            "coder_agent":  "coder_agent",
        }
    )

    graph.add_edge("search_agent",    "coder_agent")
    graph.add_edge("coder_agent",     "reviewer_agent")

    graph.add_conditional_edges(
        "reviewer_agent",
        route_after_review,
        {
            "retry":        "increment_retry",
            "file_agent":   "file_agent",
            "save_history": "save_history",
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
    graph.add_edge("bash_agent",      "save_history")
    graph.add_edge("save_history",    END)

    return graph.compile()


orchestrator = build_graph()