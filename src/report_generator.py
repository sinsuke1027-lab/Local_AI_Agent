import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from langchain_ollama import ChatOllama


OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_DEFAULT = "qwen2.5-coder:14b"


class ReportGenerator:
    """日次/週次の振り返りレポートを自動生成する"""

    def __init__(self):
        self.db_path = os.path.expanduser("~/.roo/task_history.db")
        self.reports_dir = os.path.expanduser(
            "~/projects/langgraph-orchestrator/reports"
        )
        os.makedirs(self.reports_dir, exist_ok=True)

    def _get_tasks(self, since: str, until: str = None) -> List[Dict]:
        """指定期間のタスク履歴をSQLiteから取得する"""
        if not os.path.exists(self.db_path):
            return []

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        if until:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE completed_at >= ? AND completed_at < ? ORDER BY completed_at",
                (since, until),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE completed_at >= ? ORDER BY completed_at",
                (since,),
            ).fetchall()

        conn.close()
        return [dict(row) for row in rows]

    def _get_lessons(self, since: str, project_dir: str = None) -> List[Dict]:
        """指定期間に追加された教訓を取得する"""
        paths = [
            os.path.expanduser("~/projects/langgraph-orchestrator/lessons.json")
        ]
        if project_dir:
            proj_lessons = os.path.join(os.path.expanduser(project_dir), "lessons.json")
            if os.path.exists(proj_lessons):
                paths.append(proj_lessons)

        lessons = []
        for path in paths:
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for lesson in data.get("lessons", []):
                    if lesson.get("created_at", "") >= since[:10]:
                        lessons.append(lesson)
            except Exception:
                pass

        return lessons

    def _calc_stats(self, tasks: List[Dict]) -> Dict:
        """タスク統計を計算する"""
        total = len(tasks)
        succeeded = len([t for t in tasks if not t.get("error_message")])
        failed = total - succeeded
        total_tokens = sum(t.get("token_count", 0) or 0 for t in tasks)
        total_cost = sum(t.get("cost_estimate", 0) or 0 for t in tasks)
        cost_jpy = round(total_cost * 150, 2)

        models_used = {}
        projects_touched = set()
        for t in tasks:
            model = t.get("model_used", "unknown")
            models_used[model] = models_used.get(model, 0) + 1
            proj = t.get("project_id")
            if proj:
                projects_touched.add(proj)

        return {
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
            "success_rate": round(succeeded / total * 100, 1) if total > 0 else 0,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
            "total_cost_jpy": cost_jpy,
            "models_used": models_used,
            "projects_touched": list(projects_touched),
        }

    def generate_daily_report(self, date: str = None) -> str:
        """日次レポートを生成する"""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        next_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        tasks = self._get_tasks(since=date, until=next_date)
        lessons = self._get_lessons(since=date)
        stats = self._calc_stats(tasks)

        lines = [
            f"# 日次レポート: {date}",
            "",
            "## サマリー",
            f"- タスク実行数: {stats['total']}（成功: {stats['succeeded']} / 失敗: {stats['failed']}）",
            f"- 成功率: {stats['success_rate']}%",
            f"- 総トークン数: {stats['total_tokens']:,}",
            f"- 推定コスト: ${stats['total_cost_usd']} (約{stats['total_cost_jpy']}円)",
            "",
        ]

        if stats["models_used"]:
            lines.append("## 使用モデル")
            for model, count in stats["models_used"].items():
                lines.append(f"- {model}: {count}回")
            lines.append("")

        if stats["projects_touched"]:
            lines.append("## 作業プロジェクト")
            for proj in stats["projects_touched"]:
                lines.append(f"- {proj}")
            lines.append("")

        if tasks:
            lines.append("## タスク一覧")
            for t in tasks:
                status = "✅" if not t.get("error_message") else "❌"
                instruction = (t.get("instruction") or "")[:80]
                lines.append(f"- {status} [{t.get('task_id')}] {instruction}")
            lines.append("")

        if lessons:
            lines.append("## 今日学んだ教訓")
            for lesson in lessons:
                lines.append(f"- **{lesson.get('error_pattern', '')}**")
                lines.append(f"  対策: {lesson.get('solution', '')}")
            lines.append("")

        # 失敗タスクがあれば分析
        failed_tasks = [t for t in tasks if t.get("error_message")]
        if failed_tasks:
            lines.append("## 失敗タスクの分析")
            for t in failed_tasks:
                lines.append(f"- [{t.get('task_id')}] {(t.get('instruction') or '')[:60]}")
                lines.append(f"  エラー: {(t.get('error_message') or '')[:200]}")
            lines.append("")

        return "\n".join(lines)

    def generate_weekly_report(self, end_date: str = None) -> str:
        """週次レポートを生成する"""
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=7)
        start_date = start_dt.strftime("%Y-%m-%d")

        tasks = self._get_tasks(since=start_date, until=end_date)
        lessons = self._get_lessons(since=start_date)
        stats = self._calc_stats(tasks)

        # 日別の集計
        daily_counts = {}
        for t in tasks:
            day = (t.get("completed_at") or "")[:10]
            if day:
                daily_counts[day] = daily_counts.get(day, 0) + 1

        lines = [
            f"# 週次レポート: {start_date} 〜 {end_date}",
            "",
            "## サマリー",
            f"- タスク実行数: {stats['total']}（成功: {stats['succeeded']} / 失敗: {stats['failed']}）",
            f"- 成功率: {stats['success_rate']}%",
            f"- 総トークン数: {stats['total_tokens']:,}",
            f"- 推定コスト: ${stats['total_cost_usd']} (約{stats['total_cost_jpy']}円)",
            "",
        ]

        if daily_counts:
            lines.append("## 日別タスク数")
            for day in sorted(daily_counts.keys()):
                bar = "█" * daily_counts[day]
                lines.append(f"- {day}: {bar} ({daily_counts[day]})")
            lines.append("")

        if stats["models_used"]:
            lines.append("## 使用モデル")
            for model, count in stats["models_used"].items():
                lines.append(f"- {model}: {count}回")
            lines.append("")

        if lessons:
            lines.append(f"## 今週の教訓（{len(lessons)}件）")
            for lesson in lessons:
                severity = "🔴" if lesson.get("severity") == "critical" else "🟡"
                lines.append(f"- {severity} {lesson.get('error_pattern', '')}")
                lines.append(f"  対策: {lesson.get('solution', '')}")
            lines.append("")

        # LLMによるサマリー生成
        if tasks:
            model = ChatOllama(model=MODEL_DEFAULT, base_url=OLLAMA_BASE_URL)
            task_list = "\n".join(
                f"- {(t.get('instruction') or '')[:60]}" for t in tasks[:20]
            )
            prompt = (
                "以下は今週実行されたタスクの一覧です。\n"
                "3行以内で今週の進捗と来週の注力ポイントを日本語でまとめてください。\n\n"
                f"{task_list}"
            )
            try:
                response = model.invoke(prompt)
                lines.extend(["## AI分析", response.content.strip(), ""])
            except Exception:
                pass

        # --- P10a: 自己改善分析セクション追加 ---
        try:
            from src.self_improver import SelfImprover
            improver = SelfImprover()
            analysis_text = improver.run(days=7)
            lines.extend(["", "---", "", analysis_text])
        except Exception as e:
            logger.warning("P10a analysis failed: %s", e)
            lines.extend(["", "---", "", "（自己改善分析の生成に失敗しました）"])

        return "\n".join(lines)

    def save_report(self, content: str, filename: str) -> str:
        """レポートをファイルに保存する"""
        path = os.path.join(self.reports_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def generate_and_save_daily(self, date: str = None) -> str:
        """日次レポートを生成して保存する"""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        content = self.generate_daily_report(date)
        return self.save_report(content, f"daily_{date}.md")

    def generate_and_save_weekly(self, end_date: str = None) -> str:
        """週次レポートを生成して保存する"""
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        content = self.generate_weekly_report(end_date)
        start_date = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
        return self.save_report(content, f"weekly_{start_date}_{end_date}.md")

    def get_discord_summary(self, date: str = None) -> str:
        """Discord通知用の短いサマリーを返す"""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        next_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        tasks = self._get_tasks(since=date, until=next_date)
        stats = self._calc_stats(tasks)

        return (
            f"📊 **日次サマリー ({date})**\n"
            f"タスク: {stats['total']}件（✅{stats['succeeded']} ❌{stats['failed']}）\n"
            f"成功率: {stats['success_rate']}% | "
            f"コスト: 約{stats['total_cost_jpy']}円"
        )
