import os
import json
import time
import httpx
from datetime import datetime
from typing import List, Dict, Optional


class BatchRunner:
    """tasks.jsonのTODOタスクを順番に自動実行するバッチエンジン"""

    def __init__(
        self,
        orchestrator_url: str = "http://localhost:8001",
        discord_webhook_url: str = None,
    ):
        self.orchestrator_url = orchestrator_url
        self.discord_webhook_url = discord_webhook_url
        self.log_path = os.path.expanduser(
            "~/projects/langgraph-orchestrator/batch_runner.log"
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

    def _load_tasks(self, project_dir: str) -> Dict:
        """tasks.jsonを読み込む"""
        path = os.path.join(os.path.expanduser(project_dir), "tasks.json")
        if not os.path.exists(path):
            return {"tasks": []}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_tasks(self, project_dir: str, data: Dict):
        """tasks.jsonを保存する"""
        path = os.path.join(os.path.expanduser(project_dir), "tasks.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _execute_task(self, task: Dict, project_name: str) -> Dict:
        """1タスクをFastAPIに投入して結果を返す"""
        try:
            response = httpx.post(
                f"{self.orchestrator_url}/task",
                json={
                    "instruction": task["title"] + "\n" + task.get("description", ""),
                    "project_id": project_name,
                    "requester": "batch_runner",
                },
                headers={"X-API-Key": os.getenv("FASTAPI_API_KEY", "")},
                timeout=600.0,
            )
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "status": "error",
                    "result": f"HTTP {response.status_code}",
                }
        except Exception as e:
            return {
                "status": "error",
                "result": str(e),
            }

    def _send_discord_notification(self, message: str):
        """Discord Botのチャンネルに通知を送る（n8n Webhook経由）"""
        try:
            httpx.post(
                "http://localhost:5678/webhook/discord-send",
                json={"content": message},
                timeout=30.0,
            )
        except Exception as e:
            self._log(f"Discord通知エラー: {str(e)}")

    def run_project(
        self,
        project_dir: str,
        max_tasks: int = 10,
        stop_on_failure: bool = False,
    ) -> List[Dict]:
        """指定プロジェクトのTODOタスクを順に実行する"""
        project_dir = os.path.expanduser(project_dir)
        project_name = os.path.basename(project_dir)
        data = self._load_tasks(project_dir)
        tasks = data.get("tasks", [])

        # TODOタスクを優先度順に取得
        todos = [t for t in tasks if t.get("status") == "TODO"]
        todos.sort(key=lambda t: t.get("priority", 999))
        todos = todos[:max_tasks]

        if not todos:
            self._log(f"[{project_name}] 実行するTODOタスクがありません")
            return []

        self._log(f"[{project_name}] バッチ開始: {len(todos)}タスク")
        results = []

        for i, task in enumerate(todos):
            task_id = task["id"]
            title = task["title"]
            self._log(f"[{project_name}] ({i+1}/{len(todos)}) {task_id}: {title}")

            # ステータスをIN_PROGRESSに更新
            for t in tasks:
                if t["id"] == task_id:
                    t["status"] = "IN_PROGRESS"
            self._save_tasks(project_dir, data)

            # タスク実行
            start_time = time.time()
            result = self._execute_task(task, project_name)
            elapsed = round(time.time() - start_time, 1)

            # 結果判定
            success = result.get("status") == "completed"
            status_emoji = "✅" if success else "❌"

            # ステータス更新
            new_status = "DONE" if success else "FAILED"
            for t in tasks:
                if t["id"] == task_id:
                    t["status"] = new_status
                    t["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            self._save_tasks(project_dir, data)

            result_entry = {
                "task_id": task_id,
                "title": title,
                "success": success,
                "elapsed_seconds": elapsed,
                "result": result,
            }
            results.append(result_entry)
            self._log(f"  {status_emoji} {elapsed}秒 - {result.get('result', '')[:100]}")

            if not success and stop_on_failure:
                self._log(f"[{project_name}] 失敗により中断")
                break

        return results

    def run_all_active(
        self,
        max_tasks_per_project: int = 10,
        stop_on_failure: bool = False,
    ) -> Dict[str, List[Dict]]:
        """projects.jsonのactiveプロジェクト全てのTODOを実行する"""
        projects_path = os.path.expanduser(
            "~/projects/langgraph-orchestrator/projects.json"
        )
        if not os.path.exists(projects_path):
            self._log("projects.jsonが見つかりません")
            return {}

        with open(projects_path, "r", encoding="utf-8") as f:
            proj_data = json.load(f)

        all_results = {}
        for name, info in proj_data.get("projects", {}).items():
            if not info.get("active", False):
                continue
            project_dir = os.path.expanduser(info["path"])
            tasks_path = os.path.join(project_dir, "tasks.json")
            if not os.path.exists(tasks_path):
                continue
            results = self.run_project(
                project_dir,
                max_tasks=max_tasks_per_project,
                stop_on_failure=stop_on_failure,
            )
            if results:
                all_results[name] = results

        return all_results

    def generate_batch_report(self, all_results: Dict[str, List[Dict]]) -> str:
        """バッチ実行結果のレポートを生成する"""
        total_tasks = 0
        total_success = 0
        total_failed = 0
        total_time = 0

        lines = [
            f"🌙 **夜間バッチレポート ({datetime.now().strftime('%Y-%m-%d %H:%M')})**",
            "",
        ]

        for project_name, results in all_results.items():
            succeeded = len([r for r in results if r["success"]])
            failed = len(results) - succeeded
            total_tasks += len(results)
            total_success += succeeded
            total_failed += failed

            lines.append(f"**{project_name}** ({succeeded}✅ {failed}❌)")
            for r in results:
                emoji = "✅" if r["success"] else "❌"
                lines.append(f"  {emoji} [{r['task_id']}] {r['title']} ({r['elapsed_seconds']}秒)")
                total_time += r["elapsed_seconds"]
            lines.append("")

        lines.insert(1, f"合計: {total_tasks}タスク（✅{total_success} ❌{total_failed}）| 総実行時間: {round(total_time/60, 1)}分")

        return "\n".join(lines)

    def run_night_batch(
        self,
        max_tasks_per_project: int = 10,
        stop_on_failure: bool = False,
        notify_discord: bool = True,
    ):
        """夜間バッチの完全実行（実行→レポート→Discord通知）"""
        self._log("=== 夜間バッチ開始 ===")

        # --- P8: バッチ実行前にタスク履歴をインデックス更新 ---
        from src.task_history_indexer import TaskHistoryIndexer
        try:
            indexer = TaskHistoryIndexer()
            count = indexer.index_recent(hours=24)
            self._log(f"Pre-batch index: {count} tasks indexed")
        except Exception as e:
            self._log(f"Pre-batch index failed: {e}")

        # 全プロジェクトのTODOを実行
        all_results = self.run_all_active(
            max_tasks_per_project=max_tasks_per_project,
            stop_on_failure=stop_on_failure,
        )

        if not all_results:
            self._log("実行するタスクがありませんでした")
            return

        # レポート生成
        report = self.generate_batch_report(all_results)
        self._log(report)

        # レポートをファイル保存
        reports_dir = os.path.expanduser(
            "~/projects/langgraph-orchestrator/reports"
        )
        os.makedirs(reports_dir, exist_ok=True)
        report_path = os.path.join(
            reports_dir,
            f"batch_{datetime.now().strftime('%Y-%m-%d_%H%M')}.md"
        )
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        # 日次レポートも生成
        try:
            from src.report_generator import ReportGenerator
            rg = ReportGenerator()
            rg.generate_and_save_daily()
        except Exception:
            pass

        # Discord通知
        if notify_discord:
            self._send_discord_notification(report)

        # --- P10a: 週次バッチ時に改善提案をDiscord通知 ---
        try:
            from src.self_improver import SelfImprover
            improver = SelfImprover()
            analysis = improver.analyze(days=7)
            suggestions = improver.generate_suggestions(analysis)
            if suggestions:
                improver.notify_suggestions(suggestions)
                self._log(f"P10a: {len(suggestions)}件の改善提案をDiscordに送信")
            else:
                self._log("P10a: 改善提案なし")
        except Exception as e:
            self._log(f"P10a notification failed: {e}")

        self._log("=== 夜間バッチ完了 ===")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="夜間バッチ開発モード")
    parser.add_argument("--max-tasks", type=int, default=10, help="プロジェクトあたりの最大タスク数")
    parser.add_argument("--stop-on-failure", action="store_true", help="失敗時に中断")
    parser.add_argument("--no-discord", action="store_true", help="Discord通知を無効化")
    parser.add_argument("--project", type=str, default=None, help="特定プロジェクトのみ実行")
    args = parser.parse_args()

    runner = BatchRunner()

    if args.project:
        results = runner.run_project(
            os.path.expanduser(f"~/projects/{args.project}"),
            max_tasks=args.max_tasks,
            stop_on_failure=args.stop_on_failure,
        )
        report = runner.generate_batch_report({args.project: results})
        print(report)
        if not args.no_discord:
            runner._send_discord_notification(report)
    else:
        runner.run_night_batch(
            max_tasks_per_project=args.max_tasks,
            stop_on_failure=args.stop_on_failure,
            notify_discord=not args.no_discord,
        )
