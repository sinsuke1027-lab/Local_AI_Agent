"""
cost_table.py — モデル別コスト単価テーブル（USD / 1token）
最終更新: 2026-04-05

単価が変わったときにここだけ直せばよい設計。
"""

# 為替レート（固定。月1回程度 Anthropic/Google の料金ページと照合推奨）
USD_TO_JPY = 150.0

# Ollama（ローカル実行）: 電力コスト概算
# Mac mini M4 消費電力 約20W、電気代 約27円/kWh として試算
# 1時間あたり約0.54円 ≈ 0.0036USD、生成速度 約50token/sec 想定
OLLAMA_COST_PER_TOKEN = 0.000001  # ほぼゼロ（電力コスト概算）

# Gemini 2.5 Flash（2026-04時点）
GEMINI_FLASH_INPUT_PER_TOKEN  = 0.0000003   # $0.30 / 1M tokens
GEMINI_FLASH_OUTPUT_PER_TOKEN = 0.0000025   # $2.50 / 1M tokens

# Claude Sonnet 4.6（2026-04時点）
CLAUDE_SONNET_INPUT_PER_TOKEN  = 0.000003   # $3.00 / 1M tokens
CLAUDE_SONNET_OUTPUT_PER_TOKEN = 0.000015   # $15.00 / 1M tokens

# Claude Opus 4.6（2026-04時点）
CLAUDE_OPUS_INPUT_PER_TOKEN  = 0.000005     # $5.00 / 1M tokens
CLAUDE_OPUS_OUTPUT_PER_TOKEN = 0.000025     # $25.00 / 1M tokens

# モデル名 → 単価マッピング（部分一致で検索）
MODEL_COST_TABLE: dict[str, dict[str, float]] = {
    # Ollama ローカルモデル
    "qwen2.5-coder:7b":  {"input": OLLAMA_COST_PER_TOKEN, "output": OLLAMA_COST_PER_TOKEN},
    "qwen2.5-coder:14b": {"input": OLLAMA_COST_PER_TOKEN, "output": OLLAMA_COST_PER_TOKEN},
    "deepseek-r1:14b":   {"input": OLLAMA_COST_PER_TOKEN, "output": OLLAMA_COST_PER_TOKEN},
    # Gemini
    "gemini-2.5-flash":  {"input": GEMINI_FLASH_INPUT_PER_TOKEN,  "output": GEMINI_FLASH_OUTPUT_PER_TOKEN},
    "gemini-2.0-flash":  {"input": GEMINI_FLASH_INPUT_PER_TOKEN,  "output": GEMINI_FLASH_OUTPUT_PER_TOKEN},
    # Claude
    "claude-sonnet-4-6": {"input": CLAUDE_SONNET_INPUT_PER_TOKEN, "output": CLAUDE_SONNET_OUTPUT_PER_TOKEN},
    "claude-opus-4-6":   {"input": CLAUDE_OPUS_INPUT_PER_TOKEN,   "output": CLAUDE_OPUS_OUTPUT_PER_TOKEN},
}

# フォールバック（テーブルに存在しないモデル）
DEFAULT_COST_PER_TOKEN = OLLAMA_COST_PER_TOKEN


def calculate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """
    モデル名とトークン数からコスト（USD）を計算して返す。

    Args:
        model_name:    使用モデル名（部分一致でテーブルを検索）
        input_tokens:  入力トークン数
        output_tokens: 出力トークン数

    Returns:
        コスト（USD）
    """
    matched: dict[str, float] | None = None
    for key, rates in MODEL_COST_TABLE.items():
        if key in model_name or model_name in key:
            matched = rates
            break

    if matched is None:
        return (input_tokens + output_tokens) * DEFAULT_COST_PER_TOKEN

    return (input_tokens * matched["input"]) + (output_tokens * matched["output"])


def calculate_cost_jpy(cost_usd: float) -> float:
    """USD → 円換算（固定レート USD_TO_JPY 使用）"""
    return round(cost_usd * USD_TO_JPY, 4)
