"""
model_manager.py — Ollama モデルのロード・アンロード管理

RAM節約のため、使用後に明示的にモデルをアンロードする。
Mac mini M4 (24GB) では 14b x2 同時保持が RAM を超えるため、
フロー制御による段階的アンロードで回避する。
"""

import logging
import requests

OLLAMA_BASE_URL = "http://localhost:11434"
logger = logging.getLogger(__name__)


def unload_model(model_name: str) -> bool:
    """
    指定モデルをメモリからアンロードする。
    keep_alive=0 を送ることで即座にアンロードされる。
    """
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": model_name, "keep_alive": 0},
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info("model_manager: unloaded %s", model_name)
            return True
        logger.warning("model_manager: unload %s returned %d", model_name, resp.status_code)
        return False
    except Exception as e:
        logger.warning("model_manager: unload %s failed — %s", model_name, e)
        return False


def unload_all_models() -> int:
    """
    現在メモリにロードされている全モデルをアンロードする。
    バッチ終了時・昼間のメモリクリーンアップ時に呼び出す。

    Returns:
        アンロードしたモデル数
    """
    models = get_loaded_models()
    if not models:
        logger.info("model_manager: no models loaded, nothing to unload")
        return 0

    count = 0
    for name in models:
        if unload_model(name):
            count += 1

    logger.info("model_manager: unloaded %d/%d models", count, len(models))
    return count


def get_loaded_models() -> list[str]:
    """現在メモリにロードされているモデル名のリストを返す。"""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/ps", timeout=5)
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception as e:
        logger.debug("model_manager: get_loaded_models failed — %s", e)
        return []
