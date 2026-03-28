import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from langchain_ollama import ChatOllama


OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_DEFAULT = "qwen2.5-coder:14b"


class LessonManager:
    """エラー教訓の保存・検索・プロンプト注入を行うマネージャー"""

    def __init__(self):
        self.global_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "lessons.json"
        )

    def _get_project_path(self, project_dir: str) -> str:
        """プロジェクト固有のlessons.jsonパスを返す"""
        return os.path.join(os.path.expanduser(project_dir), "lessons.json")

    def _load(self, path: str) -> List[Dict]:
        """lessons.jsonを読み込む"""
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("lessons", [])
        except Exception:
            return []

    def _save(self, path: str, lessons: List[Dict]) -> None:
        """lessons.jsonに保存する"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"lessons": lessons}, f, ensure_ascii=False, indent=2)

    def _generate_id(self, lessons: List[Dict]) -> str:
        """次のIDを生成する"""
        if not lessons:
            return "L001"
        max_num = max(int(l["id"][1:]) for l in lessons if l["id"].startswith("L"))
        return f"L{max_num + 1:03d}"

    def search(self, query: str, project_dir: str = None, max_results: int = 5) -> List[Dict]:
        """キーワードに関連する教訓を検索する（グローバル + プロジェクト固有）"""
        all_lessons = self._load(self.global_path)

        if project_dir:
            project_lessons = self._load(self._get_project_path(project_dir))
            all_lessons.extend(project_lessons)

        query_lower = query.lower()
        scored = []
        for lesson in all_lessons:
            score = 0
            searchable = " ".join([
                lesson.get("error_pattern", ""),
                lesson.get("root_cause", ""),
                lesson.get("solution", ""),
                " ".join(lesson.get("tags", [])),
            ]).lower()
            for word in query_lower.split():
                if word in searchable:
                    score += 1
            if score > 0:
                scored.append((score, lesson))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:max_results]]

    def get_prompt_injection(self, instruction: str, project_dir: str = None) -> str:
        """タスク指示に関連する教訓をプロンプト注入用テキストとして返す"""
        lessons = self.search(instruction, project_dir=project_dir)

        if not lessons:
            return ""

        lines = ["【過去のエラー教訓（同じミスを繰り返さないこと）】"]
        for lesson in lessons:
            lines.append(
                f"\n- エラー: {lesson['error_pattern']}\n"
                f"  原因: {lesson['root_cause']}\n"
                f"  対策: {lesson['solution']}"
            )

        return "\n".join(lines)

    def add_lesson(
        self,
        error_pattern: str,
        root_cause: str,
        solution: str,
        tags: List[str],
        project_dir: str = None,
        severity: str = "normal",
    ) -> Dict:
        """教訓を追加する（project_dir指定でプロジェクト固有、なければグローバル）"""
        if project_dir:
            path = self._get_project_path(project_dir)
        else:
            path = self.global_path

        lessons = self._load(path)
        new_lesson = {
            "id": self._generate_id(lessons),
            "created_at": datetime.now().strftime("%Y-%m-%d"),
            "project": os.path.basename(project_dir) if project_dir else "global",
            "error_pattern": error_pattern,
            "root_cause": root_cause,
            "solution": solution,
            "tags": tags,
            "severity": severity,
        }
        lessons.append(new_lesson)
        self._save(path, lessons)
        return new_lesson

    def extract_and_save_lesson(
        self,
        error_message: str,
        solution_result: str,
        instruction: str,
        project_dir: str = None,
    ) -> Optional[Dict]:
        """エラーと解決結果からLLMで教訓を自動抽出して保存する"""
        model = ChatOllama(model=MODEL_DEFAULT, base_url=OLLAMA_BASE_URL)

        prompt = (
            "以下のエラーと解決結果から、今後同じミスを防ぐための教訓を抽出してください。\n\n"
            f"タスク: {instruction}\n\n"
            f"発生したエラー:\n{error_message[:2000]}\n\n"
            f"解決結果:\n{solution_result[:2000]}\n\n"
            "以下のJSON形式で出力してください（JSON以外は出力しないこと）:\n"
            '{\n'
            '  "error_pattern": "どんなエラーが起きたか（1行で）",\n'
            '  "root_cause": "根本原因（1行で）",\n'
            '  "solution": "解決策（1行で）",\n'
            '  "tags": ["関連キーワード1", "関連キーワード2"],\n'
            '  "severity": "critical または normal"\n'
            '}'
        )

        try:
            response = model.invoke(prompt)
            content = response.content.strip()

            # JSON部分を抽出
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if not json_match:
                return None

            lesson_data = json.loads(json_match.group())

            return self.add_lesson(
                error_pattern=lesson_data["error_pattern"],
                root_cause=lesson_data["root_cause"],
                solution=lesson_data["solution"],
                tags=lesson_data.get("tags", []),
                project_dir=project_dir,
                severity=lesson_data.get("severity", "normal"),
            )
        except Exception:
            return None
