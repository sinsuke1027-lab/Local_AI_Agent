"""chroma_client.py - ChromaDB共有クライアント

全モジュールがこのシングルトンを使うことで、同一パスに対する
複数インスタンスの衝突を防ぐ。
"""

import logging
from pathlib import Path

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

CHROMA_DB_DIR = Path.home() / ".roo" / "chroma_db"

_client = None


def get_chroma_client(chroma_dir: Path = None) -> chromadb.ClientAPI:
    """ChromaDB PersistentClientのシングルトンを返す。

    初回呼び出し時のみインスタンスを生成し、以降は同一インスタンスを返す。

    Args:
        chroma_dir: ChromaDBの保存先（デフォルト: ~/.roo/chroma_db）
    Returns:
        chromadb.ClientAPI
    """
    global _client
    if _client is None:
        path = str(chroma_dir or CHROMA_DB_DIR)
        _client = chromadb.PersistentClient(
            path=path,
            settings=Settings(anonymized_telemetry=False),
        )
        logger.info("ChromaDB client initialized: %s", path)
    return _client
