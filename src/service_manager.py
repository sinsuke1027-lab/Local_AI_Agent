"""
service_manager.py — M8-1: AIが生成したStreamlitアプリのプロセス管理

AIが生成した Streamlit アプリを別ポートで起動・停止・一覧表示する。
状態は ~/.roo/task_history.db の services テーブルで永続化する。
"""

import os
import signal
import socket
import sqlite3
import subprocess
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH      = Path.home() / ".roo" / "task_history.db"
PORT_RANGE   = range(8502, 8511)   # 8501 は Orchestrator 本体が使用中
VENV_PYTHON  = Path(__file__).parents[1] / ".venv" / "bin" / "python3"
STREAMLIT_BIN = Path(__file__).parents[1] / ".venv" / "bin" / "streamlit"


# ── DB ヘルパー ─────────────────────────────────────────────
def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table() -> None:
    """services テーブルを初期化（冪等）"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS services (
            service_id   TEXT PRIMARY KEY,
            project_name TEXT NOT NULL,
            app_path     TEXT NOT NULL,
            port         INTEGER NOT NULL,
            pid          INTEGER,
            status       TEXT NOT NULL DEFAULT 'stopped',
            started_at   TEXT,
            url          TEXT
        )
    """)
    conn.commit()
    conn.close()


# ── ポートユーティリティ ────────────────────────────────────
def _is_port_in_use(port: int) -> bool:
    """指定ポートが使用中か確認する"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect(("localhost", port))
            return True
        except (ConnectionRefusedError, OSError):
            return False


def _find_free_port() -> Optional[int]:
    """PORT_RANGE 内で使用されていないポートを返す。なければ None"""
    for port in PORT_RANGE:
        if not _is_port_in_use(port):
            return port
    return None


def _is_pid_alive(pid: int) -> bool:
    """指定 PID のプロセスが生存しているか確認する"""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


# ── ServiceManager ──────────────────────────────────────────
class ServiceManager:
    """Streamlit アプリのライフサイクルを管理するクラス"""

    def __init__(self):
        ensure_table()

    def start(self, project_name: str, app_path: str) -> dict:
        """
        Streamlit アプリを起動する。

        Args:
            project_name: プロジェクト名（表示用）
            app_path: 起動する .py ファイルの絶対パス（~ 展開対応）

        Returns:
            サービス情報 dict

        Raises:
            FileNotFoundError: app_path が存在しない場合
            RuntimeError: 空きポートがない / すでに起動済みの場合
        """
        app_path = str(Path(app_path).expanduser().resolve())

        if not Path(app_path).exists():
            raise FileNotFoundError(f"アプリファイルが見つかりません: {app_path}")

        # 同一パスの二重起動防止
        existing = self._find_by_path(app_path)
        if existing and existing["status"] == "running":
            if _is_pid_alive(existing["pid"]):
                raise RuntimeError(
                    f"すでに起動中です (port={existing['port']}, pid={existing['pid']})"
                )
            # プロセスが死んでいれば DB を修正して続行
            self._update_status(existing["service_id"], "stopped")

        port = _find_free_port()
        if port is None:
            raise RuntimeError(f"空きポートがありません（範囲: {PORT_RANGE.start}〜{PORT_RANGE.stop - 1}）")

        # streamlit コマンドを決定（venv 内 → PATH 上の順でフォールバック）
        streamlit_cmd = (
            str(STREAMLIT_BIN) if STREAMLIT_BIN.exists() else "streamlit"
        )

        cmd = [
            streamlit_cmd, "run", app_path,
            "--server.port",               str(port),
            "--server.headless",           "true",
            "--server.address",            "0.0.0.0",
            # iframe埋め込みのためにCORS/XSRFを無効化（M8-2）
            # Streamlit はデフォルトで X-Frame-Options: SAMEORIGIN を返すが、
            # これらのオプションで同一ホスト内 iframe 表示を許可する
            "--server.enableCORS",         "false",
            "--server.enableXsrfProtection", "false",
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,   # シグナルがOrchestratorに伝播しないようにする
            )
        except Exception as e:
            raise RuntimeError(f"起動に失敗しました: {e}") from e

        service_id = str(uuid.uuid4())[:8]
        url        = f"http://localhost:{port}"
        started_at = datetime.now().isoformat()

        conn = _get_conn()
        conn.execute(
            """
            INSERT INTO services (service_id, project_name, app_path, port, pid, status, started_at, url)
            VALUES (?, ?, ?, ?, ?, 'running', ?, ?)
            """,
            (service_id, project_name, app_path, port, proc.pid, started_at, url),
        )
        conn.commit()
        conn.close()

        logger.info(
            "Service started: service_id=%s project=%s port=%d pid=%d",
            service_id, project_name, port, proc.pid,
        )

        return {
            "service_id":   service_id,
            "project_name": project_name,
            "app_path":     app_path,
            "port":         port,
            "pid":          proc.pid,
            "status":       "running",
            "started_at":   started_at,
            "url":          url,
        }

    def stop(self, service_id: str) -> bool:
        """
        サービスを停止する。

        Returns:
            True: 停止成功 / False: 該当サービスなし
        """
        conn = _get_conn()
        row = conn.execute(
            "SELECT pid, status FROM services WHERE service_id = ?", (service_id,)
        ).fetchone()
        conn.close()

        if not row:
            logger.warning("stop: service_id=%s not found", service_id)
            return False

        pid = row["pid"]
        if pid and _is_pid_alive(pid):
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                logger.info("Sent SIGTERM to pgid of pid=%d", pid)
            except Exception:
                try:
                    os.kill(pid, signal.SIGTERM)
                    logger.info("Sent SIGTERM to pid=%d", pid)
                except Exception as e:
                    logger.warning("Failed to kill pid=%d: %s", pid, e)

        self._update_status(service_id, "stopped")
        logger.info("Service stopped: service_id=%s", service_id)
        return True

    def list_services(self, include_stopped: bool = False) -> list[dict]:
        """
        サービス一覧を返す。同時にゾンビプロセスの検出・ステータス更新も行う。

        Args:
            include_stopped: True の場合は停止済みも含める
        """
        ensure_table()
        conn = _get_conn()
        if include_stopped:
            rows = conn.execute(
                "SELECT * FROM services ORDER BY started_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM services WHERE status = 'running' ORDER BY started_at DESC"
            ).fetchall()
        conn.close()

        services = []
        for row in rows:
            svc = dict(row)
            # プロセス生存確認でステータスを自動修正
            if svc["status"] == "running" and svc["pid"]:
                if not _is_pid_alive(svc["pid"]):
                    self._update_status(svc["service_id"], "error")
                    svc["status"] = "error"
            services.append(svc)

        return services

    def get(self, service_id: str) -> Optional[dict]:
        """service_id でサービス情報を取得する"""
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM services WHERE service_id = ?", (service_id,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    # ── プライベートメソッド ──────────────────────────────
    def _find_by_path(self, app_path: str) -> Optional[dict]:
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM services WHERE app_path = ? ORDER BY started_at DESC LIMIT 1",
            (app_path,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def _update_status(self, service_id: str, status: str) -> None:
        conn = _get_conn()
        conn.execute(
            "UPDATE services SET status = ? WHERE service_id = ?",
            (status, service_id),
        )
        conn.commit()
        conn.close()
