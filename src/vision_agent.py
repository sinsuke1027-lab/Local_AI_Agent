"""
vision_agent.py — M5-3: Claude Vision API によるスクリーンショット解釈

スクリーンショット画像 + テキスト指示を Claude Vision API（claude-sonnet-4-6）に渡し、
具体的なタスク指示文を生成する。

接続関係:
  M8-3 screenshot_agent.py → screenshots/*.png
     ↓
  vision_agent.interpret_screenshot()
     ↓
  タスク指示文 → orchestrator /task エンドポイント

ANTHROPIC_API_KEY は .env の ANTHROPIC_API_KEY から取得する。
未設定の場合は RuntimeError を raise するので、呼び出し元は try/except で囲むこと。
"""

import base64
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

VISION_MODEL  = "claude-sonnet-4-6"
MAX_TOKENS    = 512

SYSTEM_PROMPT = """あなたはUIレビュアーです。
ユーザーが提供するスクリーンショットと修正指示を分析し、
開発者が実装できる具体的なタスク指示文を日本語で生成してください。

出力形式:
- 何を（対象コンポーネント）
- どのように（具体的な変更内容）
- なぜ（UX上の理由、省略可）

を含む、1〜3文の明確な指示文を出力してください。
余分な説明や前置きは不要です。指示文のみ出力してください。"""


def _load_image_as_base64(image_path: str) -> tuple[str, str]:
    """画像ファイルをBase64エンコードして (data, media_type) を返す"""
    path = Path(image_path)
    media_type_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
    media_type = media_type_map.get(path.suffix.lower(), "image/png")
    with open(path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return data, media_type


def interpret_screenshot(
    image_path: str,
    user_instruction: str,
    project_name: str = "",
) -> dict:
    """
    スクリーンショットとユーザー指示を Vision API に渡し、タスク指示文を生成する。

    Args:
        image_path       : スクリーンショットのローカルパス（絶対パス）
        user_instruction : ユーザーの自然言語指示
        project_name     : プロジェクト名（コンテキスト補強用、任意）

    Returns:
        {
            "success"               : bool,
            "interpreted_instruction": str,   # 生成されたタスク指示文
            "raw_response"          : str,    # API の生レスポンス（デバッグ用）
            "error"                 : str | None
        }
    """
    # ── ファイル存在チェック ─────────────────────────────
    if not Path(image_path).exists():
        msg = f"画像ファイルが見つかりません: {image_path}"
        logger.warning(msg)
        return {"success": False, "interpreted_instruction": "", "raw_response": "", "error": msg}

    # ── API KEY チェック ────────────────────────────────
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        msg = (
            "ANTHROPIC_API_KEY が設定されていません。"
            ".env に ANTHROPIC_API_KEY=<your_key> を追加してください。"
        )
        logger.error(msg)
        return {"success": False, "interpreted_instruction": "", "raw_response": "", "error": msg}

    try:
        import anthropic

        image_data, media_type = _load_image_as_base64(image_path)
        logger.info(
            "vision_agent: calling %s for %s (project=%s)",
            VISION_MODEL, Path(image_path).name, project_name or "未指定",
        )

        client = anthropic.Anthropic(api_key=api_key)

        user_content = [
            {
                "type": "image",
                "source": {
                    "type":       "base64",
                    "media_type": media_type,
                    "data":       image_data,
                },
            },
            {
                "type": "text",
                "text": (
                    f"プロジェクト: {project_name}\n"
                    f"ユーザー指示: {user_instruction}\n\n"
                    "上記スクリーンショットを見て、具体的なタスク指示文を生成してください。"
                ),
            },
        ]

        response = client.messages.create(
            model=VISION_MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        interpreted = response.content[0].text.strip()
        logger.info("vision_agent: generated instruction (%d chars)", len(interpreted))

        return {
            "success":                True,
            "interpreted_instruction": interpreted,
            "raw_response":           interpreted,
            "error":                  None,
        }

    except Exception as e:
        msg = str(e)
        logger.error("vision_agent: API call failed — %s", msg)
        return {
            "success":                False,
            "interpreted_instruction": "",
            "raw_response":           "",
            "error":                  msg,
        }
