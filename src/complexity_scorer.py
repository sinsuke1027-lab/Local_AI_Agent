"""complexity_scorer.py - P9: タスク複雑度スコア算出"""

import logging
import re
from typing import Optional

from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL           = "http://localhost:11434"
DEFAULT_SCORE             = 5
SCORE_MODEL               = "qwen2.5-coder:7b"
SCORE_TIMEOUT             = 120   # 秒
MAX_RETRY                 = 1     # タイムアウト時のリトライ回数
RULE_BASED_SKIP_THRESHOLD = 5     # この値以下ならLLMスキップ

COMPLEXITY_PROMPT = """あなたはソフトウェア開発タスクの複雑度を評価する専門家です。
以下のタスク説明を読み、複雑度を1〜10の整数で回答してください。
数字のみ回答してください。他の文字は不要です。

評価基準:
- 1-3: 単純（変数名変更、コメント追加、1関数の小修正）
- 4-6: 中程度（新規関数追加、既存機能の拡張、バグ修正）
- 7-8: 複雑（複数ファイル変更、新規モジュール作成、API設計）
- 9-10: 高複雑（アーキテクチャ変更、セキュリティ設計、パフォーマンス最適化）

タスク説明:
{instruction}"""

# 複雑度を上げるキーワード群
HIGH_COMPLEXITY_KEYWORDS = [
    # アーキテクチャ系
    "設計", "アーキテクチャ", "リファクタ", "マイグレーション", "移行",
    # セキュリティ系
    "認証", "認可", "セキュリティ", "暗号", "oauth", "jwt", "cors",
    # パフォーマンス系
    "最適化", "キャッシュ", "非同期", "並列", "パフォーマンス", "async",
    # 複数ファイル系
    "api設計", "エンドポイント", "websocket", "データベース", "スキーマ",
    # インフラ系
    "docker", "ci/cd", "デプロイ", "kubernetes",
]

# 複雑度を下げるキーワード群
LOW_COMPLEXITY_KEYWORDS = [
    "変数名", "コメント", "typo", "タイポ", "リネーム", "rename",
    "ログ追加", "print", "表示", "メッセージ変更", "文言",
]


def score_complexity_rule_based(instruction: str) -> int:
    """ルールベースの複雑度スコア算出。

    キーワードマッチ + 文字数で簡易判定する。
    戻り値が RULE_BASED_SKIP_THRESHOLD 以下ならLLMスキップ可能。

    Args:
        instruction: タスク説明文
    Returns:
        int: 1-10の簡易複雑度スコア
    """
    if not instruction:
        return DEFAULT_SCORE

    text = instruction.lower()
    score = 4  # ベーススコア

    # 低複雑度キーワードで減点（1回だけ）
    for kw in LOW_COMPLEXITY_KEYWORDS:
        if kw.lower() in text:
            score -= 2
            break

    # 高複雑度キーワードで加点（最大+4）
    hits = sum(1 for kw in HIGH_COMPLEXITY_KEYWORDS if kw.lower() in text)
    score += min(hits * 2, 4)

    # 文字数による補正
    length = len(instruction)
    if length < 30:
        score -= 1
    elif length > 200:
        score += 1

    return max(1, min(10, score))


def score_complexity(instruction: str, model: Optional[str] = None) -> int:
    """複雑度スコアを算出する。

    まずルールベースで簡易判定し、「複雑かも」の場合のみLLM判定を行う。

    Args:
        instruction: タスク説明文
        model: LLM判定で使用するモデル（デフォルト: qwen2.5-coder:7b）
    Returns:
        int: 1-10の複雑度スコア
    """
    # --- ステップ1: ルールベース事前フィルタ ---
    rule_score = score_complexity_rule_based(instruction)
    logger.info("Rule-based complexity score: %d", rule_score)

    if rule_score <= RULE_BASED_SKIP_THRESHOLD:
        logger.info(
            "Complexity below threshold (%d <= %d) — skipping LLM scoring",
            rule_score, RULE_BASED_SKIP_THRESHOLD,
        )
        return rule_score

    # --- ステップ2: LLM判定（複雑かもしれないタスクのみ） ---
    logger.info(
        "Complexity may be high (%d > %d) — running LLM scoring",
        rule_score, RULE_BASED_SKIP_THRESHOLD,
    )

    model = model or SCORE_MODEL
    prompt = COMPLEXITY_PROMPT.format(instruction=instruction)

    for attempt in range(MAX_RETRY + 1):
        try:
            llm = ChatOllama(
                model=model,
                base_url=OLLAMA_BASE_URL,
                temperature=0,
                timeout=SCORE_TIMEOUT,
            )
            response = llm.invoke(prompt)
            raw = response.content.strip()

            match = re.search(r"\b(\d{1,2})\b", raw)
            if match:
                score = int(match.group(1))
                score = max(1, min(10, score))
                logger.info(
                    "LLM complexity score: %d (raw: %s, attempt: %d)",
                    score, raw[:50], attempt + 1,
                )
                return score

            logger.warning(
                "Could not parse complexity score from: %s (attempt: %d)",
                raw[:100], attempt + 1,
            )
            return rule_score  # パース失敗時はルールベーススコアで代替

        except Exception as e:
            if attempt < MAX_RETRY:
                logger.warning(
                    "Complexity scoring attempt %d failed: %s — retrying...",
                    attempt + 1, e,
                )
                continue
            else:
                logger.warning(
                    "Complexity scoring failed after %d attempts: %s — using rule-based score %d",
                    attempt + 1, e, rule_score,
                )
                return rule_score  # LLM失敗時もルールベーススコアで代替

    return rule_score
