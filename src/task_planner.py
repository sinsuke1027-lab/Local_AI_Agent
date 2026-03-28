import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from langchain_ollama import ChatOllama


OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_DEFAULT = "qwen2.5-coder:14b"


class TaskPlanner:
    """タスク完了時に次タスクを自動洗い出し、tasks.jsonで管理する"""

    def __init__(self):
        pass

    def _get_tasks_path(self, project_dir: str) -> str:
        """プロジェクトのtasks.jsonパスを返す"""
        return os.path.join(os.path.expanduser(project_dir), "tasks.json")

    def _load(self, project_dir: str) -> Dict:
        """tasks.jsonを読み込む"""
        path = self._get_tasks_path(project_dir)
        if not os.path.exists(path):
            return {"tasks": []}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"tasks": []}

    def _save(self, project_dir: str, data: Dict) -> None:
        """tasks.jsonに保存する"""
        path = self._get_tasks_path(project_dir)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _generate_id(self, tasks: List[Dict]) -> str:
        """次のタスクIDを生成する"""
        if not tasks:
            return "T001"
        max_num = 0
        for t in tasks:
            tid = t.get("id", "T000")
            if tid.startswith("T"):
                try:
                    num = int(tid[1:])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass
        return f"T{max_num + 1:03d}"

    def get_tasks(self, project_dir: str, status: str = None) -> List[Dict]:
        """タスク一覧を取得する（statusでフィルタ可能）"""
        data = self._load(project_dir)
        tasks = data.get("tasks", [])
        if status:
            tasks = [t for t in tasks if t.get("status") == status]
        return tasks

    def get_next_task(self, project_dir: str) -> Optional[Dict]:
        """次に実行すべきTODOタスクを1つ返す（優先度順）"""
        todos = self.get_tasks(project_dir, status="TODO")
        if not todos:
            return None
        # priority昇順（1が最優先）
        todos.sort(key=lambda t: t.get("priority", 999))
        return todos[0]

    def add_task(
        self,
        project_dir: str,
        title: str,
        description: str = "",
        priority: int = 5,
        depends_on: List[str] = None,
    ) -> Dict:
        """タスクを手動追加する"""
        data = self._load(project_dir)
        tasks = data.get("tasks", [])

        new_task = {
            "id": self._generate_id(tasks),
            "title": title,
            "description": description,
            "status": "TODO",
            "priority": priority,
            "depends_on": depends_on or [],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "completed_at": None,
        }
        tasks.append(new_task)
        data["tasks"] = tasks
        self._save(project_dir, data)
        return new_task

    def update_status(self, project_dir: str, task_id: str, status: str) -> Optional[Dict]:
        """タスクのステータスを更新する"""
        data = self._load(project_dir)
        tasks = data.get("tasks", [])

        for task in tasks:
            if task["id"] == task_id:
                task["status"] = status
                if status == "DONE":
                    task["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                data["tasks"] = tasks
                self._save(project_dir, data)
                return task
        return None

    def plan_next_tasks(
        self,
        project_dir: str,
        completed_instruction: str,
        completed_result: str,
        context_md: str = "",
    ) -> List[Dict]:
        """完了タスクの結果から次にやるべきタスクをLLMで洗い出す"""
        model = ChatOllama(model=MODEL_DEFAULT, base_url=OLLAMA_BASE_URL)

        # 現在のTODOタスクを取得
        current_todos = self.get_tasks(project_dir, status="TODO")
        current_todos_text = ""
        if current_todos:
            current_todos_text = "\n現在のTODOタスク:\n"
            for t in current_todos:
                current_todos_text += f"- [{t['id']}] {t['title']}\n"

        prompt = (
            "あなたはプロジェクトマネージャーです。\n"
            "以下の完了タスクの結果を分析し、次にやるべきタスクを1〜3個提案してください。\n\n"
            f"完了タスク: {completed_instruction}\n\n"
            f"結果:\n{completed_result[:2000]}\n\n"
            f"プロジェクト情報:\n{context_md[:1000]}\n"
            f"{current_todos_text}\n\n"
            "以下のJSON配列形式で出力してください（JSON以外は出力しないこと）:\n"
            '[\n'
            '  {\n'
            '    "title": "タスクのタイトル（1行で）",\n'
            '    "description": "タスクの詳細説明",\n'
            '    "priority": 1〜10の整数（1が最優先）\n'
            '  }\n'
            ']\n\n'
            "注意:\n"
            "- 既存のTODOタスクと重複しないこと\n"
            "- 実装可能な具体的なタスクにすること\n"
            "- 優先度は直前のタスクとの関連性で判断すること"
        )

        try:
            response = model.invoke(prompt)
            content = response.content.strip()

            # JSON配列部分を抽出
            import re
            json_match = re.search(r'\[[\s\S]*\]', content)
            if not json_match:
                return []

            proposed_tasks = json.loads(json_match.group())
            added_tasks = []

            for task_data in proposed_tasks:
                if not isinstance(task_data, dict):
                    continue
                if not task_data.get("title"):
                    continue
                new_task = self.add_task(
                    project_dir=project_dir,
                    title=task_data["title"],
                    description=task_data.get("description", ""),
                    priority=task_data.get("priority", 5),
                )
                added_tasks.append(new_task)

            return added_tasks

        except Exception:
            return []

    def get_summary(self, project_dir: str) -> str:
        """タスク状況のサマリーテキストを返す"""
        data = self._load(project_dir)
        tasks = data.get("tasks", [])

        todo = [t for t in tasks if t.get("status") == "TODO"]
        in_progress = [t for t in tasks if t.get("status") == "IN_PROGRESS"]
        done = [t for t in tasks if t.get("status") == "DONE"]

        lines = [f"【タスク状況】TODO: {len(todo)} / 進行中: {len(in_progress)} / 完了: {len(done)}"]

        if todo:
            lines.append("\n次のタスク:")
            for t in sorted(todo, key=lambda x: x.get("priority", 999))[:3]:
                lines.append(f"  [{t['id']}] P{t['priority']} - {t['title']}")

        return "\n".join(lines)
