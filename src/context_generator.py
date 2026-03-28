import os
import json
from typing import Dict, Optional


class ContextGenerator:
    """プロジェクトのディレクトリを走査してcontext.mdを自動生成する"""

    IGNORE_DIRS = {
        ".venv", "__pycache__", ".git", "node_modules",
        ".chroma", ".roo", ".mypy_cache", ".pytest_cache",
        "dist", "build", ".egg-info",
    }
    IGNORE_FILES = {
        ".DS_Store", ".env", "mcp_config.json",
    }
    CODE_EXTENSIONS = {
        ".py", ".js", ".ts", ".jsx", ".tsx",
        ".html", ".css", ".json", ".yaml", ".yml",
        ".md", ".txt", ".sh", ".toml", ".cfg",
    }

    def __init__(self):
        self.projects_json_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "projects.json"
        )

    def _load_projects(self) -> Dict:
        """projects.jsonを読み込む"""
        if not os.path.exists(self.projects_json_path):
            return {}
        with open(self.projects_json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _get_project_info(self, project_dir: str) -> Optional[Dict]:
        """projects.jsonからプロジェクト情報を取得する"""
        data = self._load_projects()
        project_name = os.path.basename(os.path.expanduser(project_dir))
        return data.get("projects", {}).get(project_name)

    def _build_tree(self, root: str, prefix: str = "", max_depth: int = 3, current_depth: int = 0) -> str:
        """ディレクトリツリーを文字列として構築する"""
        if current_depth >= max_depth:
            return ""

        root = os.path.expanduser(root)
        if not os.path.isdir(root):
            return ""

        lines = []
        try:
            entries = sorted(os.listdir(root))
        except PermissionError:
            return ""

        # ディレクトリとファイルを分離
        dirs = [e for e in entries if os.path.isdir(os.path.join(root, e)) and e not in self.IGNORE_DIRS and not e.startswith(".")]
        files = [e for e in entries if os.path.isfile(os.path.join(root, e)) and e not in self.IGNORE_FILES]

        all_items = dirs + files
        for i, name in enumerate(all_items):
            is_last = (i == len(all_items) - 1)
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{name}")

            if name in dirs:
                extension = "    " if is_last else "│   "
                subtree = self._build_tree(
                    os.path.join(root, name),
                    prefix=prefix + extension,
                    max_depth=max_depth,
                    current_depth=current_depth + 1,
                )
                if subtree:
                    lines.append(subtree)

        return "\n".join(lines)

    def _detect_tech_stack(self, project_dir: str) -> list:
        """技術スタックを自動検出する"""
        project_dir = os.path.expanduser(project_dir)
        stack = []

        # Python
        req_path = os.path.join(project_dir, "requirements.txt")
        if os.path.exists(req_path):
            stack.append("Python")
            try:
                with open(req_path, "r", encoding="utf-8") as f:
                    content = f.read().lower()
                if "fastapi" in content:
                    stack.append("FastAPI")
                if "flask" in content:
                    stack.append("Flask")
                if "django" in content:
                    stack.append("Django")
                if "langchain" in content:
                    stack.append("LangChain")
                if "langgraph" in content:
                    stack.append("LangGraph")
                if "langfuse" in content:
                    stack.append("Langfuse")
                if "chromadb" in content:
                    stack.append("ChromaDB")
                if "ollama" in content:
                    stack.append("Ollama")
                if "playwright" in content:
                    stack.append("Playwright")
                if "discord" in content:
                    stack.append("Discord.py")
                if "pytest" in content:
                    stack.append("pytest")
            except Exception:
                pass

        # Node.js
        pkg_path = os.path.join(project_dir, "package.json")
        if os.path.exists(pkg_path):
            stack.append("Node.js")
            try:
                with open(pkg_path, "r", encoding="utf-8") as f:
                    pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "react" in deps:
                    stack.append("React")
                if "next" in deps:
                    stack.append("Next.js")
                if "vue" in deps:
                    stack.append("Vue.js")
                if "express" in deps:
                    stack.append("Express")
            except Exception:
                pass

        # Docker
        if os.path.exists(os.path.join(project_dir, "docker-compose.yml")) or \
           os.path.exists(os.path.join(project_dir, "docker-compose.yaml")) or \
           os.path.exists(os.path.join(project_dir, "Dockerfile")):
            stack.append("Docker")

        return stack

    def _get_file_descriptions(self, project_dir: str) -> list:
        """主要ファイルのdocstringやコメントを抽出する"""
        project_dir = os.path.expanduser(project_dir)
        descriptions = []

        try:
            entries = os.listdir(project_dir)
        except PermissionError:
            return descriptions

        for name in sorted(entries):
            path = os.path.join(project_dir, name)
            if not os.path.isfile(path):
                continue
            _, ext = os.path.splitext(name)
            if ext not in self.CODE_EXTENSIONS:
                continue
            if name in self.IGNORE_FILES:
                continue

            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()[:10]
                # 先頭のコメントやdocstringを取得
                desc = ""
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("#") and not stripped.startswith("#!"):
                        desc = stripped.lstrip("# ").strip()
                        break
                    if stripped.startswith('"""') or stripped.startswith("'''"):
                        desc = stripped.strip('"""').strip("'''").strip()
                        break
                if desc:
                    descriptions.append(f"- `{name}`: {desc}")
                else:
                    descriptions.append(f"- `{name}`")
            except Exception:
                descriptions.append(f"- `{name}`")

        # src/ ディレクトリも走査
        src_dir = os.path.join(project_dir, "src")
        if os.path.isdir(src_dir):
            for name in sorted(os.listdir(src_dir)):
                path = os.path.join(src_dir, name)
                if not os.path.isfile(path):
                    continue
                _, ext = os.path.splitext(name)
                if ext not in self.CODE_EXTENSIONS:
                    continue

                try:
                    with open(path, "r", encoding="utf-8") as f:
                        lines = f.readlines()[:10]
                    desc = ""
                    for line in lines:
                        stripped = line.strip()
                        if stripped.startswith("#") and not stripped.startswith("#!"):
                            desc = stripped.lstrip("# ").strip()
                            break
                        if stripped.startswith('"""') or stripped.startswith("'''"):
                            desc = stripped.strip('"""').strip("'''").strip()
                            break
                    if desc:
                        descriptions.append(f"- `src/{name}`: {desc}")
                    else:
                        descriptions.append(f"- `src/{name}`")
                except Exception:
                    descriptions.append(f"- `src/{name}`")

        return descriptions

    def generate(self, project_dir: str) -> str:
        """context.mdの内容を生成する"""
        project_dir = os.path.expanduser(project_dir)
        project_name = os.path.basename(project_dir)
        project_info = self._get_project_info(project_dir)

        # 概要
        description = ""
        if project_info:
            description = project_info.get("description", "")

        # 技術スタック
        tech_stack = self._detect_tech_stack(project_dir)

        # ディレクトリ構造
        tree = self._build_tree(project_dir)

        # 主要ファイル
        file_descs = self._get_file_descriptions(project_dir)

        # Python バージョン
        python_version = ""
        if project_info:
            python_version = project_info.get("python_version", "")

        # 機密フラグ
        confidential = False
        if project_info:
            confidential = project_info.get("confidential", False)

        # context.md を組み立て
        lines = [f"# {project_name}", ""]

        if description:
            lines.extend(["## 概要", description, ""])

        if confidential:
            lines.extend(["## ⚠️ 機密プロジェクト", "クラウドAPIの使用禁止。ローカルモデルのみ使用すること。", ""])

        if tech_stack:
            lines.extend(["## 技術スタック"])
            if python_version:
                lines.append(f"- Python {python_version}")
            for t in tech_stack:
                if t != "Python":
                    lines.append(f"- {t}")
            lines.append("")

        if tree:
            lines.extend(["## ディレクトリ構造", "```", tree, "```", ""])

        if file_descs:
            lines.extend(["## 主要ファイル"] + file_descs + [""])

        # 憲法の存在確認
        constitution_path = os.path.join(project_dir, "constitution.md")
        project_constitution_path = os.path.join(project_dir, "project_constitution.md")
        if os.path.exists(constitution_path) or os.path.exists(project_constitution_path):
            lines.extend(["## 注意事項", "プロジェクト固有の憲法あり。タスク実行前に参照すること。", ""])

        return "\n".join(lines)

    def generate_and_save(self, project_dir: str) -> str:
        """context.mdを生成してファイルに保存する"""
        project_dir = os.path.expanduser(project_dir)
        content = self.generate(project_dir)
        output_path = os.path.join(project_dir, "context.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        return output_path

    def load_context(self, project_dir: str) -> str:
        """既存のcontext.mdを読み込む。なければ生成して返す"""
        project_dir = os.path.expanduser(project_dir)
        context_path = os.path.join(project_dir, "context.md")
        if os.path.exists(context_path):
            with open(context_path, "r", encoding="utf-8") as f:
                return f.read()
        # なければ生成
        self.generate_and_save(project_dir)
        with open(context_path, "r", encoding="utf-8") as f:
            return f.read()
