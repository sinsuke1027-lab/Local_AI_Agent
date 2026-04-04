"""debate_agent.py - P9: マルチエージェントディベート"""

import logging
import time
import concurrent.futures
from dataclasses import dataclass, asdict
from typing import Optional

from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_DEBUG     = "deepseek-r1:14b"

# --- プロンプト定義 ---
PERSPECTIVES = {
    "architect": {
        "role": "シニアソフトウェアアーキテクト",
        "prompt": """あなたはシニアソフトウェアアーキテクトです。
以下のコードを設計の観点からレビューしてください。

評価ポイント:
- 責務の分離は適切か
- 拡張性・保守性は確保されているか
- 命名規則・コード構造は一貫しているか
- エラーハンドリングの設計は適切か

タスク説明: {instruction}
コード:
{code}

問題点と改善提案を簡潔に述べてください（日本語、箇条書き）。""",
    },
    "security": {
        "role": "セキュリティエンジニア",
        "prompt": """あなたはセキュリティエンジニアです。
以下のコードをセキュリティの観点からレビューしてください。

評価ポイント:
- 入力バリデーションは十分か
- SQLインジェクション・XSS等の脆弱性はないか
- 機密情報（APIキー・パスワード等）の扱いは安全か
- 権限管理・認証の考慮はあるか

タスク説明: {instruction}
コード:
{code}

問題点と改善提案を簡潔に述べてください（日本語、箇条書き）。""",
    },
    "performance": {
        "role": "パフォーマンスエンジニア",
        "prompt": """あなたはパフォーマンスエンジニアです。
以下のコードをパフォーマンスの観点からレビューしてください。

評価ポイント:
- 不要なループ・計算はないか
- メモリ使用量は適切か
- I/O操作のボトルネックはないか
- キャッシュやバッチ処理の活用余地はないか

タスク説明: {instruction}
コード:
{code}

問題点と改善提案を簡潔に述べてください（日本語、箇条書き）。""",
    },
}

INTEGRATION_PROMPT = """あなたは開発チームのリードエンジニアです。
3人のレビュアーの意見を統合して最終判定を出してください。

## アーキテクト視点
{architect_feedback}

## セキュリティ視点
{security_feedback}

## パフォーマンス視点
{performance_feedback}

以下のフォーマットで回答してください:
1行目: APPROVED または NEEDS_REVISION
2行目以降: 統合コメント（最も重要な改善点を3つ以内で簡潔に）"""


@dataclass
class DebateResult:
    verdict: str               # "APPROVED" or "NEEDS_REVISION"
    summary: str               # 統合コメント
    architect_feedback: str
    security_feedback: str
    performance_feedback: str
    model_used: str

    def to_dict(self) -> dict:
        return asdict(self)

    def to_prompt_context(self) -> str:
        """coder_agentに渡すフィードバックテキストを生成する。"""
        if self.verdict == "APPROVED":
            return ""
        return f"""## ディベート結果（NEEDS_REVISION）

### アーキテクト視点
{self.architect_feedback}

### セキュリティ視点
{self.security_feedback}

### パフォーマンス視点
{self.performance_feedback}

### 統合判定
{self.summary}

上記の指摘事項を踏まえてコードを修正してください。"""


def _get_llm(model: str):
    """モデル名に応じてLLMインスタンスを返す。gemini対応済み。"""
    if "gemini" in model.lower():
        # GeminiWrapperはnodes.pyで定義されているが循環importを避けるため直接実装
        import os
        from google import genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY が .env に設定されていません")

        client = genai.Client(api_key=api_key)

        class _GeminiLLM:
            def invoke(self, prompt: str):
                response = client.models.generate_content(
                    model=model, contents=prompt
                )
                class _Resp:
                    content = response.text
                return _Resp()

        return _GeminiLLM()

    # Ollama（タイムアウトなし — 完了まで待つ）
    return ChatOllama(model=model, base_url=OLLAMA_BASE_URL, temperature=0)


def run_debate(
    code: str,
    instruction: str,
    model: Optional[str] = None,
) -> DebateResult:
    """3視点ディベートを並列実行する（M7-2: ThreadPoolExecutor使用）。

    Args:
        code: レビュー対象のコード
        instruction: タスク説明文
        model: 使用モデル（デフォルト: MODEL_DEBUG）
    Returns:
        DebateResult
    """
    model = model or MODEL_DEBUG
    llm = _get_llm(model)

    def _invoke_perspective(perspective: str) -> tuple[str, str]:
        """1視点のレビューを実行してフィードバックを返す"""
        config = PERSPECTIVES[perspective]
        prompt = config["prompt"].format(instruction=instruction, code=code)
        t0 = time.monotonic()
        try:
            logger.info("Debate[parallel]: starting %s perspective...", perspective)
            response = llm.invoke(prompt)
            text = response.content.strip()
            elapsed = time.monotonic() - t0
            logger.info(
                "Debate[parallel]: %s done in %.1fs (%d chars)",
                perspective, elapsed, len(text),
            )
            return perspective, text
        except Exception as e:
            logger.warning("Debate[parallel]: %s failed: %s", perspective, e)
            return perspective, f"（{config['role']}のレビューに失敗: {e}）"

    # --- 3視点を並列実行 ---
    feedbacks: dict[str, str] = {}
    t_start = time.monotonic()

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(_invoke_perspective, p): p for p in PERSPECTIVES}
        for future in concurrent.futures.as_completed(futures):
            try:
                perspective, text = future.result()
                feedbacks[perspective] = text
            except Exception as e:
                perspective = futures[future]
                logger.warning("Debate[parallel]: future error for %s: %s", perspective, e)
                feedbacks[perspective] = f"（取得失敗: {e}）"

    elapsed_total = time.monotonic() - t_start
    logger.info(
        "Debate[parallel]: all 3 perspectives completed in %.1fs (sequential would be ~3x longer)",
        elapsed_total,
    )

    # --- 統合判定 ---
    integration_prompt = INTEGRATION_PROMPT.format(
        architect_feedback=feedbacks.get("architect", "（取得失敗）"),
        security_feedback=feedbacks.get("security", "（取得失敗）"),
        performance_feedback=feedbacks.get("performance", "（取得失敗）"),
    )
    try:
        logger.info("Debate: running integration with %s...", model)
        response = llm.invoke(integration_prompt)
        raw = response.content.strip()

        lines = raw.split("\n", 1)
        verdict_line = lines[0].strip().upper()
        verdict = "APPROVED" if "APPROVED" in verdict_line else "NEEDS_REVISION"
        summary = lines[1].strip() if len(lines) > 1 else ""

    except Exception as e:
        logger.warning("Debate: integration failed: %s", e)
        verdict = "NEEDS_REVISION"
        summary = f"統合判定に失敗しました: {e}"

    result = DebateResult(
        verdict=verdict,
        summary=summary,
        architect_feedback=feedbacks.get("architect", ""),
        security_feedback=feedbacks.get("security", ""),
        performance_feedback=feedbacks.get("performance", ""),
        model_used=model,
    )

    logger.info("Debate complete: verdict=%s (total=%.1fs)", verdict, elapsed_total)
    return result
