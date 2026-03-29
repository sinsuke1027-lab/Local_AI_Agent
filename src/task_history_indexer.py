"""
task_history_indexer.py - P8: タスク履歴RAG学習

SQLiteのタスク履歴（~/.roo/task_history.db）をChromaDBにインデックス化し、
coder_agentが過去の成功パターンを自動参照できるようにする。

使い方:
    from src.task_history_indexer import TaskHistoryIndexer
    indexer = TaskHistoryIndexer()
    indexer.index_all()                              # 初回一括インデックス
    indexer.index_recent(hours=24)                   # 差分インデックス
    patterns = indexer.get_success_patterns("FastAPIエンドポイント追加", n=3)
"""

import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from src.chroma_client import get_chroma_client

logger = logging.getLogger(__name__)

# --- 定数 ---
TASK_HISTORY_DB = Path.home() / ".roo" / "task_history.db"
CHROMA_DB_DIR = Path.home() / ".roo" / "chroma_db"
COLLECTION_NAME = "task_history"

# ChromaDBドキュメントの最大長（超過時は末尾を切り詰め）
MAX_DOC_LENGTH = 8000


class TaskHistoryIndexer:
    """SQLiteタスク履歴をChromaDBにインデックス化するクラス。"""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        chroma_dir: Optional[Path] = None,
    ):
        self.db_path = db_path or TASK_HISTORY_DB
        self.chroma_dir = chroma_dir or CHROMA_DB_DIR

        # 共有シングルトンクライアントを使用（衝突防止）
        self.chroma_client = get_chroma_client(self.chroma_dir)
        self.collection = self.chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "Task history for RAG-based success pattern lookup"},
        )
        logger.info(
            "TaskHistoryIndexer initialized: db=%s, chroma=%s, collection_count=%d",
            self.db_path,
            self.chroma_dir,
            self.collection.count(),
        )

    # ------------------------------------------------------------------
    # SQLite読み取り
    # ------------------------------------------------------------------
    def _fetch_tasks(
        self,
        since: Optional[datetime] = None,
        success_only: bool = False,
    ) -> list[dict]:
        """task_history.dbからタスクレコードを取得する。

        Args:
            since: この日時以降のレコードのみ取得（Noneなら全件）
            success_only: Trueなら成功タスク（error_message IS NULL）のみ
        Returns:
            list[dict]: タスクレコードのリスト
        """
        if not self.db_path.exists():
            logger.warning("task_history.db not found: %s", self.db_path)
            return []

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            query = "SELECT * FROM tasks WHERE 1=1"
            params: list = []

            if since is not None:
                query += " AND completed_at >= ?"
                params.append(since.isoformat())

            if success_only:
                query += " AND error_message IS NULL"

            query += " ORDER BY completed_at DESC"

            cursor = conn.execute(query, params)
            rows = [dict(row) for row in cursor.fetchall()]
            logger.info("Fetched %d tasks from SQLite (since=%s, success_only=%s)", len(rows), since, success_only)
            return rows
        except Exception:
            logger.exception("Failed to fetch tasks from SQLite")
            return []
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # ChromaDBインデックス
    # ------------------------------------------------------------------
    def _build_document(self, task: dict) -> str:
        """タスクレコードから検索用ドキュメントテキストを構築する。"""
        parts = []

        instruction = (task.get("instruction") or "").strip()
        if instruction:
            parts.append(f"[TASK]\n{instruction}")

        result = (task.get("result") or "").strip()
        if result:
            # 長大なLLM出力は切り詰め
            if len(result) > MAX_DOC_LENGTH:
                result = result[:MAX_DOC_LENGTH] + "\n... (truncated)"
            parts.append(f"[RESULT]\n{result}")

        return "\n\n".join(parts) if parts else ""

    def _build_metadata(self, task: dict) -> dict:
        """タスクレコードからChromaDBメタデータを構築する。"""
        is_success = task.get("error_message") is None
        return {
            "task_id": str(task.get("task_id", "")),
            "project_id": task.get("project_id") or "unknown",
            "model_used": task.get("model_used") or "unknown",
            "completed_at": task.get("completed_at") or "",
            "is_success": is_success,
            "token_count": task.get("token_count") or 0,
            "cost_estimate": task.get("cost_estimate") or 0.0,
            "has_error": not is_success,
            # P9追加
            "complexity_score": task.get("complexity_score") or 0,
            "debate_triggered": bool(task.get("debate_triggered", False)),
            "debate_result": task.get("debate_result") or "",
        }

    def _upsert_tasks(self, tasks: list[dict]) -> int:
        """タスクリストをChromaDBにupsertする。

        Returns:
            int: 実際にupsertしたドキュメント数
        """
        if not tasks:
            return 0

        ids = []
        documents = []
        metadatas = []

        for task in tasks:
            task_id = str(task.get("task_id", ""))
            if not task_id:
                continue

            doc = self._build_document(task)
            if not doc:
                logger.debug("Skipping task %s: empty document", task_id)
                continue

            ids.append(task_id)
            documents.append(doc)
            metadatas.append(self._build_metadata(task))

        if not ids:
            return 0

        # ChromaDBのupsertはバッチサイズ制限があるため分割
        batch_size = 100
        total = 0
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i : i + batch_size]
            batch_docs = documents[i : i + batch_size]
            batch_meta = metadatas[i : i + batch_size]

            self.collection.upsert(
                ids=batch_ids,
                documents=batch_docs,
                metadatas=batch_meta,
            )
            total += len(batch_ids)

        logger.info("Upserted %d documents to ChromaDB collection '%s'", total, COLLECTION_NAME)
        return total

    # ------------------------------------------------------------------
    # 公開API
    # ------------------------------------------------------------------
    def index_all(self) -> int:
        """全タスク履歴をChromaDBにインデックス化する（初回セットアップ用）。

        Returns:
            int: インデックスしたドキュメント数
        """
        logger.info("Starting full index of task history...")
        tasks = self._fetch_tasks()
        count = self._upsert_tasks(tasks)
        logger.info("Full index complete: %d documents indexed (total in collection: %d)", count, self.collection.count())
        return count

    def index_recent(self, hours: int = 24) -> int:
        """直近N時間の完了タスクを差分インデックスする。

        Args:
            hours: 遡る時間数（デフォルト24時間）
        Returns:
            int: インデックスしたドキュメント数
        """
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        logger.info("Starting incremental index (since %s)...", since.isoformat())
        tasks = self._fetch_tasks(since=since)
        count = self._upsert_tasks(tasks)
        logger.info("Incremental index complete: %d documents indexed", count)
        return count

    def search_similar_tasks(
        self,
        query: str,
        n_results: int = 5,
        success_only: bool = True,
    ) -> list[dict]:
        """クエリに類似した過去タスクを検索する。

        Args:
            query: 検索クエリ（タスク説明文など）
            n_results: 返す結果数
            success_only: Trueなら成功タスクのみ
        Returns:
            list[dict]: 検索結果（id, document, metadata, distance）
        """
        if self.collection.count() == 0:
            logger.warning("Collection '%s' is empty. Run index_all() first.", COLLECTION_NAME)
            return []

        where_filter = {"is_success": True} if success_only else None

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=min(n_results, self.collection.count()),
                where=where_filter,
            )
        except Exception:
            logger.exception("ChromaDB query failed")
            return []

        # 結果をフラットなリストに変換
        items = []
        if results and results["ids"] and results["ids"][0]:
            for i, task_id in enumerate(results["ids"][0]):
                items.append(
                    {
                        "task_id": task_id,
                        "document": results["documents"][0][i] if results["documents"] else "",
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else None,
                    }
                )

        logger.info("Search returned %d results for query: %.80s...", len(items), query)
        return items

    def get_success_patterns(self, task_description: str, n: int = 3) -> str:
        """タスク説明から類似の成功パターンを取得し、フォーマット済みテキストで返す。

        nodes.pyのtask_analyzerから呼ばれるメインインターフェース。

        Args:
            task_description: 現在のタスクの説明文
            n: 返すパターン数
        Returns:
            str: 成功パターンのフォーマット済みテキスト（見つからなければ空文字列）
        """
        results = self.search_similar_tasks(
            query=task_description,
            n_results=n,
            success_only=True,
        )

        if not results:
            return ""

        patterns = []
        for i, item in enumerate(results, 1):
            meta = item.get("metadata", {})
            distance = item.get("distance")

            header = f"=== 成功パターン {i} ==="
            info_parts = [
                f"プロジェクト: {meta.get('project_id', 'unknown')}",
                f"モデル: {meta.get('model_used', 'unknown')}",
                f"完了日時: {meta.get('completed_at', 'unknown')}",
            ]
            if distance is not None:
                info_parts.append(f"類似度距離: {distance:.4f}")

            doc = item.get("document", "")

            patterns.append(f"{header}\n" + "\n".join(info_parts) + f"\n\n{doc}")

        return "\n\n".join(patterns)

    def get_stats(self) -> dict:
        """コレクションの統計情報を返す。"""
        return {
            "collection_name": COLLECTION_NAME,
            "total_documents": self.collection.count(),
            "db_path": str(self.db_path),
            "db_exists": self.db_path.exists(),
        }


# ------------------------------------------------------------------
# CLI実行用
# ------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Task History Indexer for ChromaDB")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("index-all", help="Index all task history")
    recent_parser = sub.add_parser("index-recent", help="Index recent tasks")
    recent_parser.add_argument("--hours", type=int, default=24, help="Hours to look back")

    search_parser = sub.add_parser("search", help="Search similar tasks")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--n", type=int, default=5, help="Number of results")

    sub.add_parser("stats", help="Show collection stats")

    args = parser.parse_args()
    indexer = TaskHistoryIndexer()

    if args.command == "index-all":
        count = indexer.index_all()
        print(f"Indexed {count} documents.")
    elif args.command == "index-recent":
        count = indexer.index_recent(hours=args.hours)
        print(f"Indexed {count} recent documents.")
    elif args.command == "search":
        results = indexer.search_similar_tasks(args.query, n_results=args.n)
        for r in results:
            print(f"\n--- Task: {r['task_id']} (distance: {r['distance']:.4f}) ---")
            print(r["document"][:500])
    elif args.command == "stats":
        stats = indexer.get_stats()
        for k, v in stats.items():
            print(f"  {k}: {v}")
    else:
        parser.print_help()
        sys.exit(1)
