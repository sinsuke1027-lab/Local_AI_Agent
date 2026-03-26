import os
from typing import List, Dict


class ChromaSearch:
    """ChromaDBからコードベースを検索するクライアント"""

    def __init__(self):
        self.chroma_path = os.path.expanduser("~/.roo/chroma_db")
        self._client     = None
        self._collection = None
        self._model      = None

    def _init(self):
        """遅延初期化"""
        if self._client is not None:
            return

        import chromadb
        from sentence_transformers import SentenceTransformer

        self._client     = chromadb.PersistentClient(path=self.chroma_path)
        self._model      = SentenceTransformer("all-MiniLM-L6-v2")

        try:
            self._collection = self._client.get_collection("codebase")
        except Exception:
            self._collection = None

    def search(self, query: str, n_results: int = 5, project_path: str = None) -> List[Dict]:
        """クエリに関連するコードを検索する"""
        self._init()

        if self._collection is None:
            return []

        try:
            embedding = self._model.encode(query).tolist()

            where = {"project": project_path} if project_path else None

            results = self._collection.query(
                query_embeddings=[embedding],
                n_results=n_results,
                where=where,
            )

            output = []
            for i, doc in enumerate(results["documents"][0]):
                output.append({
                    "content":  doc,
                    "path":     results["metadatas"][0][i].get("path", ""),
                    "project":  results["metadatas"][0][i].get("project", ""),
                })
            return output

        except Exception as e:
            return []

    def get_context_summary(self, query: str, project_path: str = None) -> str:
        """検索結果をLLMに渡しやすい形式にまとめる"""
        results = self.search(query, n_results=3, project_path=project_path)

        if not results:
            return ""

        lines = ["【既存コードのコンテキスト】"]
        for r in results:
            lines.append(f"\n--- {r['path']} ---")
            lines.append(r["content"][:500])

        return "\n".join(lines)

    def index_project(self, project_path: str) -> int:
        """プロジェクトをインデックス化する"""
        import subprocess
        script = os.path.expanduser("~/.roo/scripts/index-codebase.py")
        result = subprocess.run(
            ["python3", script, project_path],
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.returncode