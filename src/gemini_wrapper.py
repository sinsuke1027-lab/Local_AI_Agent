"""
gemini_wrapper.py — Google Gemini SDK の共通ラッパー

nodes.py・debate_agent.py 両方から import して使う。
token_count 追跡付き（usage_metadata）。
"""

import logging
import os

logger = logging.getLogger(__name__)


class GeminiWrapper:
    """Google 公式 SDK を langchain 風インターフェースで使うラッパー。

    Usage:
        llm = GeminiWrapper("gemini-2.5-flash")
        resp = llm.invoke("こんにちは")
        print(resp.content)           # テキスト
        print(resp.usage_metadata)    # {"total_tokens": N}
    """

    def __init__(self, model_name: str):
        from google import genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY が .env に設定されていません")
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def invoke(self, prompt: str):
        """langchain の model.invoke() と同じインターフェースで呼び出す。"""
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
        )

        # トークン数を取得（input/output 分離）
        usage: dict = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_t  = getattr(response.usage_metadata, "prompt_token_count",     0) or 0
            output_t = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
            total_t  = getattr(response.usage_metadata, "total_token_count",      0) or (input_t + output_t)
            usage = {
                "input_tokens":  input_t,
                "output_tokens": output_t,
                "total_tokens":  total_t,
            }

        class _GeminiResponse:
            def __init__(self, text: str, usage_meta: dict):
                self.content = text
                self.usage_metadata = usage_meta

        return _GeminiResponse(response.text, usage)
