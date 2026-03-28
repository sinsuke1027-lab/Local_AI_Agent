import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from langchain_ollama import ChatOllama


OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_DEFAULT = "qwen2.5-coder:14b"


class BacklogManager:
    """機能完結後に追加機能候補を提案し、優先度を管理する"""

    def __init__(self):
        pass

    def _get_backlog_path(self, project_dir: str) -> str:
        """プロジェクトのbacklog.jsonパスを返す"""
        return os.path.join(os.path.expanduser(project_dir), "backlog.json")

    def _get_goals_path(self, project_dir: str) -> str:
        """プロジェクトのgoals.mdパスを返す"""
        return os.path.join(os.path.expanduser(project_dir), "goals.md")

    def _load(self, project_dir: str) -> Dict:
        """backlog.jsonを読み込む"""
        path = self._get_backlog_path(project_dir)
        if not os.path.exists(path):
            return {"backlog": []}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"backlog": []}

    def _save(self, project_dir: str, data: Dict) -> None:
        """backlog.jsonに保存する"""
        path = self._get_backlog_path(project_dir)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_goals(self, project_dir: str) -> str:
        """goals.mdを読み込む"""
        path = self._get_goals_path(project_dir)
        if not os.path.exists(path):
            return ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def _generate_id(self, items: List[Dict]) -> str:
        """次のIDを生成する"""
        if not items:
            return "B001"
        max_num = 0
        for item in items:
            bid = item.get("id", "B000")
            if bid.startswith("B"):
                try:
                    num = int(bid[1:])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass
        return f"B{max_num + 1:03d}"

    def get_backlog(self, project_dir: str, status: str = None) -> List[Dict]:
        """バックログ一覧を取得する"""
        data = self._load(project_dir)
        items = data.get("backlog", [])
        if status:
            items = [i for i in items if i.get("status") == status]
        return items

    def add_item(
        self,
        project_dir: str,
        title: str,
        description: str = "",
        priority: int = 5,
        effort: str = "medium",
        category: str = "feature",
    ) -> Dict:
        """バックログアイテムを追加する"""
        data = self._load(project_dir)
        items = data.get("backlog", [])

        new_item = {
            "id": self._generate_id(items),
            "title": title,
            "description": description,
            "status": "proposed",
            "priority": priority,
            "effort": effort,
            "category": category,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "promoted_to_task": None,
        }
        items.append(new_item)
        data["backlog"] = items
        self._save(project_dir, data)
        return new_item

    def update_status(self, project_dir: str, item_id: str, status: str) -> Optional[Dict]:
        """バックログアイテムのステータスを更新する"""
        data = self._load(project_dir)
        items = data.get("backlog", [])

        for item in items:
            if item["id"] == item_id:
                item["status"] = status
                data["backlog"] = items
                self._save(project_dir, data)
                return item
        return None

    def promote_to_task(self, project_dir: str, item_id: str) -> Optional[Dict]:
        """バックログアイテムをtasks.jsonのTODOに昇格させる"""
        from src.task_planner import TaskPlanner

        data = self._load(project_dir)
        items = data.get("backlog", [])

        target = None
        for item in items:
            if item["id"] == item_id:
                target = item
                break

        if not target:
            return None

        planner = TaskPlanner()
        new_task = planner.add_task(
            project_dir=project_dir,
            title=target["title"],
            description=target.get("description", ""),
            priority=target.get("priority", 5),
        )

        target["status"] = "promoted"
        target["promoted_to_task"] = new_task["id"]
        data["backlog"] = items
        self._save(project_dir, data)
        return new_task

    def propose_features(
        self,
        project_dir: str,
        completed_feature: str,
        completed_result: str,
        context_md: str = "",
    ) -> List[Dict]:
        """完了した機能を分析し、追加機能候補を提案する"""
        model = ChatOllama(model=MODEL_DEFAULT, base_url=OLLAMA_BASE_URL)

        goals = self._load_goals(project_dir)
        current_backlog = self.get_backlog(project_dir, status="proposed")
        backlog_text = ""
        if current_backlog:
            backlog_text = "\n現在のバックログ:\n"
            for item in current_backlog:
                backlog_text += f"- [{item['id']}] {item['title']}\n"

        prompt = (
            "あなたはプロダクトマネージャーです。\n"
            "以下の完了した機能を分析し、次に追加すべき機能候補を2〜5個提案してください。\n\n"
            f"完了した機能: {completed_feature}\n\n"
            f"実装結果:\n{completed_result[:2000]}\n\n"
        )

        if goals:
            prompt += f"プロジェクトのゴール:\n{goals[:1000]}\n\n"

        if context_md:
            prompt += f"プロジェクト情報:\n{context_md[:1000]}\n\n"

        prompt += (
            f"{backlog_text}\n\n"
            "以下のJSON配列形式で出力してください（JSON以外は出力しないこと）:\n"
            '[\n'
            '  {\n'
            '    "title": "機能のタイトル（1行で）",\n'
            '    "description": "機能の詳細説明",\n'
            '    "priority": 1〜10の整数（1が最優先）,\n'
            '    "effort": "small / medium / large のいずれか",\n'
            '    "category": "feature / improvement / bugfix / refactor のいずれか"\n'
            '  }\n'
            ']\n\n'
            "注意:\n"
            "- プロジェクトのゴールに沿った提案をすること\n"
            "- 既存のバックログと重複しないこと\n"
            "- 実装可能で具体的な提案にすること\n"
            "- 優先度はゴールへの貢献度と工数のバランスで判断すること"
        )

        try:
            response = model.invoke(prompt)
            content = response.content.strip()

            import re
            json_match = re.search(r'\[[\s\S]*\]', content)
            if not json_match:
                return []

            proposed = json.loads(json_match.group())
            added_items = []

            for item_data in proposed:
                if not isinstance(item_data, dict):
                    continue
                if not item_data.get("title"):
                    continue
                new_item = self.add_item(
                    project_dir=project_dir,
                    title=item_data["title"],
                    description=item_data.get("description", ""),
                    priority=item_data.get("priority", 5),
                    effort=item_data.get("effort", "medium"),
                    category=item_data.get("category", "feature"),
                )
                added_items.append(new_item)

            return added_items

        except Exception:
            return []

    def get_summary(self, project_dir: str) -> str:
        """バックログのサマリーテキストを返す"""
        data = self._load(project_dir)
        items = data.get("backlog", [])

        proposed = [i for i in items if i.get("status") == "proposed"]
        promoted = [i for i in items if i.get("status") == "promoted"]
        rejected = [i for i in items if i.get("status") == "rejected"]

        lines = [f"【バックログ状況】提案: {len(proposed)} / 採用済: {len(promoted)} / 却下: {len(rejected)}"]

        if proposed:
            lines.append("\n優先度の高い候補:")
            for item in sorted(proposed, key=lambda x: x.get("priority", 999))[:5]:
                lines.append(f"  [{item['id']}] P{item['priority']} ({item['effort']}) - {item['title']}")

        return "\n".join(lines)
