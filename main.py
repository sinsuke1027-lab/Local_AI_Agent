import os
import uuid
import sqlite3
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from pydantic import BaseModel
from src.graph import orchestrator
from langfuse import Langfuse
from langfuse.callback import CallbackHandler

# ── Langfuse初期化 ──────────────────────────────
langfuse = Langfuse(
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    host=os.getenv("LANGFUSE_HOST"),
)

app = FastAPI(title="LangGraph Orchestrator")


# ── リクエストモデル ────────────────────────────
class TaskRequest(BaseModel):
    instruction: str
    input_mode:  str = "text"
    project_id:  str = "default"
    requester:   str = "unknown"
    channel_id:  str = ""


class StatusResponse(BaseModel):
    status:  str
    message: str


# ── エンドポイント① タスク投入 ──────────────────
@app.post("/task")
async def create_task(req: TaskRequest):
    task_id = str(uuid.uuid4())[:8]

    # 初期stateを作成
    initial_state = {
        "task_id":     task_id,
        "instruction": req.instruction,
        "input_mode":  req.input_mode,
        "project_id":  req.project_id,
        "requester":   req.requester,
        "channel_id":  req.channel_id,
    }

    # LangfuseのCallbackHandlerを設定
    langfuse_handler = CallbackHandler(
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        host=os.getenv("LANGFUSE_HOST"),
        session_id=task_id,
        user_id=req.requester,
    )

    # LangGraphを実行（Langfuseトレース付き）
    result = orchestrator.invoke(
        initial_state,
        config={"callbacks": [langfuse_handler]}
    )

    return {
        "task_id": task_id,
        "status":  "completed",
        "result":  result.get("result", ""),
        "model":   result.get("model_used", ""),
        "tokens":  result.get("token_count", 0),
        "cost":    result.get("cost_estimate", 0),
    }


# ── エンドポイント② 最新タスク状態確認 ──────────
@app.get("/status/latest")
async def get_latest_status():
    db_path = os.path.expanduser("~/.roo/task_history.db")
    if not os.path.exists(db_path):
        return {"status": "no_tasks", "message": "タスク履歴がありません"}
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT task_id, instruction, model_used, token_count, cost_estimate, completed_at, error_message FROM tasks ORDER BY completed_at DESC LIMIT 1").fetchone()
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
    return {"status": "ok", "service": "LangGraph Orchestrator"}
