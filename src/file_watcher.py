import os
import time
import json
import threading
import httpx
from datetime import datetime
from typing import Dict, Set, Optional, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent


class ProjectFileHandler(FileSystemEventHandler):
    """プロジェクトファイルの変更を検知するハンドラー"""

    IGNORE_DIRS = {
        ".venv", "__pycache__", ".git", "node_modules",
        ".chroma", ".mypy_cache", ".pytest_cache",
    }
    WATCH_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".yaml", ".yml"}

    def __init__(self, project_dir: str, callback: Callable):
        self.project_dir = os.path.expanduser(project_dir)
        self.callback = callback
        self._debounce_timers: Dict[str, threading.Timer] = {}
        self._debounce_seconds = 2.0

    def _should_ignore(self, path: str) -> bool:
        """無視すべきパスかどうか判定"""
        parts = path.split(os.sep)
        for part in parts:
            if part in self.IGNORE_DIRS:
                return True
        return False

    def _should_watch(self, path: str) -> bool:
        """監視対象のファイルかどうか判定"""
        _, ext = os.path.splitext(path)
        return ext in self.WATCH_EXTENSIONS

    def _debounced_callback(self, file_path: str, event_type: str):
        """デバウンス付きでコールバックを実行（短時間の連続変更をまとめる）"""
        # 既存のタイマーがあればキャンセル
        if file_path in self._debounce_timers:
            self._debounce_timers[file_path].cancel()

        timer = threading.Timer(
            self._debounce_seconds,
            self.callback,
            args=(file_path, event_type, self.project_dir),
        )
        self._debounce_timers[file_path] = timer
        timer.start()

    def on_modified(self, event):
        if event.is_directory:
            return
        if self._should_ignore(event.src_path):
            return
        if not self._should_watch(event.src_path):
            return
        self._debounced_callback(event.src_path, "modified")

    def on_created(self, event):
        if event.is_directory:
            return
        if self._should_ignore(event.src_path):
            return
        if not self._should_watch(event.src_path):
            return
        self._debounced_callback(event.src_path, "created")


class FileWatcher:
    """複数プロジェクトのファイル変更を監視し、自動アクションをトリガーする"""

    def __init__(self, orchestrator_url: str = "http://localhost:8001"):
        self.orchestrator_url = orchestrator_url
        self.observers: Dict[str, Observer] = {}
        self._running = False
        self.log_path = os.path.expanduser(
            "~/projects/langgraph-orchestrator/file_watcher.log"
        )

    def _log(self, message: str):
        """ログを記録する"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        print(log_line)
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(log_line + "\n")
        except Exception:
            pass

    def _on_file_change(self, file_path: str, event_type: str, project_dir: str):
        """ファイル変更時のコールバック"""
        relative_path = os.path.relpath(file_path, project_dir)
        project_name = os.path.basename(project_dir)
        self._log(f"変更検知: {project_name}/{relative_path} ({event_type})")

        # Pythonファイルの場合は構文チェック + テスト実行をトリガー
        if file_path.endswith(".py") and not os.path.basename(file_path).startswith("test_"):
            self._trigger_task(
                instruction=f"以下のファイルの構文チェックとテスト実行を行ってください: {file_path}",
                project_id=project_name,
                requester="file_watcher",
            )

    def _trigger_task(self, instruction: str, project_id: str, requester: str):
        """FastAPIにタスクを投入する"""
        try:
            response = httpx.post(
                f"{self.orchestrator_url}/task",
                json={
                    "instruction": instruction,
                    "project_id": project_id,
                    "requester": requester,
                },
                timeout=300.0,
            )
            if response.status_code == 200:
                result = response.json()
                self._log(f"タスク完了: {result.get('task_id')} - {result.get('status')}")
            else:
                self._log(f"タスク投入エラー: HTTP {response.status_code}")
        except Exception as e:
            self._log(f"タスク投入エラー: {str(e)}")

    def watch_project(self, project_dir: str):
        """プロジェクトの監視を開始する"""
        project_dir = os.path.expanduser(project_dir)
        project_name = os.path.basename(project_dir)

        if project_name in self.observers:
            self._log(f"既に監視中: {project_name}")
            return

        handler = ProjectFileHandler(project_dir, self._on_file_change)
        observer = Observer()
        observer.schedule(handler, project_dir, recursive=True)
        observer.start()

        self.observers[project_name] = observer
        self._log(f"監視開始: {project_name} ({project_dir})")

    def stop_project(self, project_name: str):
        """プロジェクトの監視を停止する"""
        if project_name in self.observers:
            self.observers[project_name].stop()
            self.observers[project_name].join()
            del self.observers[project_name]
            self._log(f"監視停止: {project_name}")

    def watch_all_active(self):
        """projects.jsonのactiveプロジェクトを全て監視する"""
        projects_path = os.path.expanduser(
            "~/projects/langgraph-orchestrator/projects.json"
        )
        if not os.path.exists(projects_path):
            self._log("projects.jsonが見つかりません")
            return

        with open(projects_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for name, info in data.get("projects", {}).items():
            if info.get("active", False):
                project_path = os.path.expanduser(info["path"])
                if os.path.isdir(project_path):
                    self.watch_project(project_path)

    def stop_all(self):
        """全ての監視を停止する"""
        for name in list(self.observers.keys()):
            self.stop_project(name)
        self._log("全監視停止")

    def run(self):
        """メインループ（Ctrl+Cで終了）"""
        self._running = True
        self.watch_all_active()
        self._log("FileWatcher起動完了。Ctrl+Cで終了。")

        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self._log("終了シグナル受信")
        finally:
            self.stop_all()


if __name__ == "__main__":
    watcher = FileWatcher()
    watcher.run()
