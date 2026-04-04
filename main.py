import os
import uuid
import sqlite3
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from typing import Optional
from pydantic import BaseModel
from src.graph import orchestrator
from src.auth import APIKeyMiddleware
from src.human_approval import get_pending_list, resolve_pending, get_all_approvals
from langfuse import Langfuse
from langfuse.callback import CallbackHandler

logger = logging.getLogger(__name__)

# ── Langfuse初期化 ──────────────────────────────
langfuse = Langfuse(
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    host=os.getenv("LANGFUSE_HOST"),
)

app = FastAPI(title="LangGraph Orchestrator")
app.add_middleware(APIKeyMiddleware)

# ── タスクキュー設定 ─────────────────────────────
MAX_CONCURRENT_TASKS = 2  # Mac mini M4 のメモリを考慮した同時実行数

_task_queue: asyncio.Queue           # startup で初期化
_running_tasks: dict[str, int] = {}  # task_id -> worker_id
_workers: list[asyncio.Task]   = []


# ── リクエストモデル ────────────────────────────
class TaskRequest(BaseModel):
    instruction:      str
    input_mode:       str  = "text"
    project_id:       str  = "default"
    requester:        str  = "unknown"
    channel_id:       str  = ""
    model:            Optional[str] = os.getenv("DEFAULT_AI_MODEL", "qwen2.5-coder:14b")
    thread_id:        Optional[str] = "default_thread"
    require_approval: bool = False   # HITLモード ON/OFF


class ApproveRequest(BaseModel):
    approved: bool
    feedback: str = ""


class StatusResponse(BaseModel):
    status:  str
    message: str


# ── コアワーカー ────────────────────────────────
async def _run_orchestrator(initial_state: dict, config: dict, task_id: str) -> None:
    """LangGraphをバックグラウンドスレッドで実行する（FastAPIをブロックしない）"""
    try:
        logger.info("Starting task: task_id=%s", task_id)
        await asyncio.to_thread(orchestrator.invoke, initial_state, config)
        logger.info("Completed task: task_id=%s", task_id)
    except Exception as e:
        logger.exception("Task failed: task_id=%s error=%s", task_id, e)
    finally:
        _running_tasks.pop(task_id, None)


async def _worker(worker_id: int) -> None:
    """キューからタスクを取り出して順次実行するワーカー"""
    logger.info("Worker %d started", worker_id)
    while True:
        try:
            item = await _task_queue.get()
        except asyncio.CancelledError:
            logger.info("Worker %d cancelled", worker_id)
            break

        task_id = item["task_id"]
        _running_tasks[task_id] = worker_id
        logger.info(
            "Worker %d picked up task_id=%s (queue remaining: %d)",
            worker_id, task_id, _task_queue.qsize(),
        )
        try:
            await _run_orchestrator(item["initial_state"], item["config"], task_id)
        except Exception as e:
            logger.exception("Worker %d unexpected error for task_id=%s: %s", worker_id, task_id, e)
            _running_tasks.pop(task_id, None)
        finally:
            _task_queue.task_done()


@app.on_event("startup")
async def startup() -> None:
    global _task_queue, _workers
    _task_queue = asyncio.Queue()
    _workers = []
    for i in range(MAX_CONCURRENT_TASKS):
        t = asyncio.create_task(_worker(i))
        _workers.append(t)
    logger.info("Started %d task workers (MAX_CONCURRENT_TASKS=%d)", MAX_CONCURRENT_TASKS, MAX_CONCURRENT_TASKS)


@app.on_event("shutdown")
async def shutdown() -> None:
    for w in _workers:
        w.cancel()
    await asyncio.gather(*_workers, return_exceptions=True)
    logger.info("All workers stopped")


# ── エンドポイント① タスク投入 ──────────────────
@app.post("/task")
async def create_task(req: TaskRequest):
    task_id = str(uuid.uuid4())[:8]

    # 前回の記憶をグラフから引き出す
    config_for_memory = {"configurable": {"thread_id": req.thread_id}}
    past_memory = ""
    try:
        current_state = orchestrator.get_state(config_for_memory)
        if current_state and hasattr(current_state, "values") and current_state.values:
            past_memory = current_state.values.get("result", "")
    except Exception:
        pass

    # 前回の記憶を指示に付加
    final_instruction = req.instruction
    if past_memory:
        final_instruction += (
            f"\n\n【前回の作業結果（これを前提に作業してください）】\n{past_memory[-2000:]}"
        )

    initial_state = {
        "task_id":          task_id,
        "instruction":      req.instruction,
        "input_mode":       req.input_mode,
        "project_id":       req.project_id,
        "requester":        req.requester,
        "channel_id":       req.channel_id,
        "require_approval": req.require_approval,
    }

    langfuse_handler = CallbackHandler(
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        host=os.getenv("LANGFUSE_HOST"),
        session_id=task_id,
        user_id=req.requester,
    )

    config = {
        "callbacks":    [langfuse_handler],
        "configurable": {"thread_id": req.thread_id},
    }

    # 常にキューへ追加（非同期処理）
    await _task_queue.put({
        "initial_state": initial_state,
        "config":        config,
        "task_id":       task_id,
    })

    queue_size = _task_queue.qsize()
    logger.info("Task queued: task_id=%s queue_size=%d", task_id, queue_size)

    return {
        "task_id":          task_id,
        "status":           "queued",
        "queue_position":   queue_size,
        "message":          f"タスクをキューに追加しました（待機中: {queue_size}件）",
        "require_approval": req.require_approval,
    }


# ── エンドポイント② キュー状態確認 ──────────────
@app.get("/queue/status")
async def queue_status():
    return {
        "queued":          _task_queue.qsize(),
        "running":         len(_running_tasks),
        "running_task_ids": list(_running_tasks.keys()),
        "max_concurrent":  MAX_CONCURRENT_TASKS,
    }


# ── エンドポイント③ 承認待ち一覧 ────────────────
@app.get("/approvals")
async def list_approvals():
    pending = get_pending_list()
    return {"pending": pending, "count": len(pending)}


# ── エンドポイント④ 承認・却下 ──────────────────
@app.post("/approve/{task_id}/{stage}")
async def approve_task(task_id: str, stage: str, req: ApproveRequest):
    if stage not in ("design", "pre_file"):
        raise HTTPException(status_code=400, detail="stage は 'design' または 'pre_file' を指定してください")

    success = resolve_pending(
        task_id=task_id,
        stage=stage,
        approved=req.approved,
        feedback=req.feedback,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"task_id={task_id} stage={stage} の承認待ちレコードが見つかりません",
        )

    return {
        "task_id":  task_id,
        "stage":    stage,
        "approved": req.approved,
        "message":  "承認しました" if req.approved else f"却下しました（フィードバック: {req.feedback}）",
    }


# ── エンドポイント⑤ 承認履歴 ────────────────────
@app.get("/approvals/history")
async def approval_history(limit: int = 50):
    return {"history": get_all_approvals(limit=limit)}


# ── エンドポイント⑥ 最新タスク状態確認 ──────────
@app.get("/status/latest")
async def get_latest_status():
    db_path = os.path.expanduser("~/.roo/task_history.db")
    if not os.path.exists(db_path):
        return {"status": "no_tasks", "message": "タスク履歴がありません"}
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT task_id, instruction, model_used, token_count, cost_estimate, completed_at, error_message "
        "FROM tasks ORDER BY completed_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return {"status": "no_tasks", "message": "タスク履歴がありません"}
    return {
        "status":       "completed" if not row[6] else "failed",
        "task_id":      row[0],
        "instruction":  row[1],
        "model_used":   row[2],
        "token_count":  row[3],
        "cost_jpy":     round((row[4] or 0) * 150, 2),
        "completed_at": row[5],
        "error":        row[6],
    }


# ── ヘルスチェック ──────────────────────────────
@app.get("/health")
async def health():
    return {
        "status":          "ok",
        "service":         "LangGraph Orchestrator",
        "running_tasks":   len(_running_tasks),
        "queued_tasks":    _task_queue.qsize() if "_task_queue" in globals() else 0,
        "max_concurrent":  MAX_CONCURRENT_TASKS,
    }
