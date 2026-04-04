"""
human_approval.py — HITL（ヒューマン・イン・ザ・ループ）承認管理

pending_approvals テーブルを通じて、LangGraph の一時停止・再開を制御する。

フロー:
  1. checkpoint ノードが create_pending() を呼び出す
  2. checkpoint ノードは poll_for_approval() でDB更新を待つ
  3. FastAPIの /approve/{task_id} エンドポイントが resolve_pending() を呼ぶ
  4. checkpoint ノードがポーリングで検知 → 承認なら続行、却下ならフィードバック付きリトライ
"""

import sqlite3
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = Path.home() / ".roo" / "task_history.db"

# 承認待ちのタイムアウト（秒）: 60分
APPROVAL_TIMEOUT_SEC = 3600
# ポーリング間隔（秒）
POLL_INTERVAL_SEC = 5


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table() -> None:
    """pending_approvals テーブルを初期化（冪等）"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pending_approvals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id     TEXT NOT NULL,
            stage       TEXT NOT NULL,
            preview     TEXT,
            status      TEXT NOT NULL DEFAULT 'pending',
            feedback    TEXT,
            created_at  TEXT NOT NULL,
            resolved_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def create_pending(task_id: str, stage: str, preview: str) -> None:
    """承認待ちレコードを作成する。同タスク同ステージの既存PDは削除して上書き"""
    ensure_table()
    conn = _get_conn()
    # 既存のレコードをクリーン
    conn.execute(
        "DELETE FROM pending_approvals WHERE task_id = ? AND stage = ?",
        (task_id, stage),
    )
    conn.execute(
        """
        INSERT INTO pending_approvals (task_id, stage, preview, status, created_at)
        VALUES (?, ?, ?, 'pending', ?)
        """,
        (task_id, stage, preview[:4000], datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    logger.info("Created pending approval: task_id=%s stage=%s", task_id, stage)


def poll_for_approval(task_id: str, stage: str) -> dict:
    """
    承認結果をポーリングする（ブロッキング）。
    戻り値: {"status": "approved"|"rejected", "feedback": str}
    タイムアウトした場合は approved として扱う（自動完走フォールバック）
    """
    ensure_table()
    deadline = time.monotonic() + APPROVAL_TIMEOUT_SEC

    while time.monotonic() < deadline:
        conn = _get_conn()
        row = conn.execute(
            "SELECT status, feedback FROM pending_approvals WHERE task_id = ? AND stage = ?",
            (task_id, stage),
        ).fetchone()
        conn.close()

        if row and row["status"] in ("approved", "rejected"):
            logger.info(
                "Approval resolved: task_id=%s stage=%s status=%s",
                task_id, stage, row["status"],
            )
            return {"status": row["status"], "feedback": row["feedback"] or ""}

        time.sleep(POLL_INTERVAL_SEC)

    # タイムアウト → 自動承認（フォールバック）
    logger.warning("Approval timed out for task_id=%s stage=%s — auto-approving", task_id, stage)
    resolve_pending(task_id, stage, approved=True, feedback="（タイムアウトによる自動承認）")
    return {"status": "approved", "feedback": ""}


def resolve_pending(
    task_id: str,
    stage: str,
    approved: bool,
    feedback: str = "",
) -> bool:
    """承認または却下を記録する。対象レコードがなければ False を返す"""
    ensure_table()
    conn = _get_conn()
    status = "approved" if approved else "rejected"
    cursor = conn.execute(
        """
        UPDATE pending_approvals
        SET status = ?, feedback = ?, resolved_at = ?
        WHERE task_id = ? AND stage = ? AND status = 'pending'
        """,
        (status, feedback, datetime.now().isoformat(), task_id, stage),
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()

    if affected:
        logger.info("Resolved approval: task_id=%s stage=%s → %s", task_id, stage, status)
    else:
        logger.warning("No pending approval found for task_id=%s stage=%s", task_id, stage)

    return affected > 0


def get_pending_list() -> list[dict]:
    """承認待ち（status=pending）の一覧を返す"""
    ensure_table()
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT task_id, stage, preview, created_at
        FROM pending_approvals
        WHERE status = 'pending'
        ORDER BY created_at ASC
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_approvals(limit: int = 50) -> list[dict]:
    """承認履歴（全ステータス）を返す（Streamlit履歴表示用）"""
    ensure_table()
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT task_id, stage, preview, status, feedback, created_at, resolved_at
        FROM pending_approvals
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
