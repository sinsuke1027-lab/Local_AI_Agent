# コスト追跡ワークフロー

最終更新: 2026-04-05（M6-2 実装）

## 概要

- モデル別の単価は `src/cost_table.py` で一元管理
- タスク完了時に `input_tokens` / `output_tokens` / `cost_usd` / `cost_jpy` を SQLite に記録
- Ollama ローカルモデルは電力コスト概算（ほぼゼロ）、Gemini/Claude は API 料金を適用

## 確認方法

### 直近タスクのコストを確認

```bash
python3 -c "
import sqlite3, os
conn = sqlite3.connect(os.path.expanduser('~/.roo/task_history.db'))
rows = conn.execute('''
    SELECT task_id, project_id, model_used,
           input_tokens, output_tokens, cost_usd, cost_jpy, completed_at
    FROM tasks
    WHERE cost_usd IS NOT NULL
    ORDER BY completed_at DESC
    LIMIT 20
''').fetchall()
for r in rows:
    print(r)
"
```

### 月次コスト集計

```bash
python3 -c "
import sqlite3, os
conn = sqlite3.connect(os.path.expanduser('~/.roo/task_history.db'))
rows = conn.execute('''
    SELECT
        strftime(\"%Y-%m\", completed_at) AS month,
        model_used,
        COUNT(*) AS tasks,
        SUM(input_tokens)  AS total_in,
        SUM(output_tokens) AS total_out,
        ROUND(SUM(cost_usd), 4) AS total_usd,
        ROUND(SUM(cost_jpy), 2) AS total_jpy
    FROM tasks
    WHERE cost_usd IS NOT NULL
    GROUP BY month, model_used
    ORDER BY month DESC, total_usd DESC
''').fetchall()
for r in rows:
    print(r)
"
```

### モデル別累計コスト

```bash
python3 -c "
import sqlite3, os
conn = sqlite3.connect(os.path.expanduser('~/.roo/task_history.db'))
rows = conn.execute('''
    SELECT
        model_used,
        COUNT(*) AS tasks,
        ROUND(SUM(cost_usd), 4) AS total_usd,
        ROUND(SUM(cost_jpy), 2) AS total_jpy,
        ROUND(AVG(cost_usd), 6) AS avg_usd_per_task
    FROM tasks
    WHERE cost_usd IS NOT NULL
    GROUP BY model_used
    ORDER BY total_usd DESC
''').fetchall()
for r in rows:
    print(r)
"
```

### Langfuse ダッシュボードとの照合

> 現状 Langfuse への SDK 統合はなし（将来的に M6-2 拡張として追加予定）。
> SQLite の集計結果を月1回 Langfuse の手動確認と照合すること。

1. http://localhost:3000 を開く
2. 「Traces」→ 対象タスクを選択
3. 「Usage」タブで token 数を確認
4. SQLite の `cost_usd` と概ね一致していれば正常（誤差 ±10% 以内を目安）

## 単価の更新方法

`src/cost_table.py` の定数を直接編集する。
月1回程度、Anthropic / Google の料金ページと照合することを推奨。

| 定数名 | 現在値 | 参照先 |
|--------|--------|--------|
| `GEMINI_FLASH_INPUT_PER_TOKEN` | $0.30/1M | Google AI Studio 料金ページ |
| `GEMINI_FLASH_OUTPUT_PER_TOKEN` | $2.50/1M | Google AI Studio 料金ページ |
| `CLAUDE_SONNET_INPUT_PER_TOKEN` | $3.00/1M | Anthropic 料金ページ |
| `CLAUDE_SONNET_OUTPUT_PER_TOKEN` | $15.00/1M | Anthropic 料金ページ |
| `USD_TO_JPY` | 150.0 | 固定（適宜更新） |

## 設計メモ

- `input_tokens`/`output_tokens` が取得できない Ollama モデルは `total_tokens` を 7:3 で概算分割
- `cost_estimate` フィールドは後方互換のために残存（= `cost_usd` と同値）
- `cost_jpy = cost_usd * USD_TO_JPY`（リアルタイム為替取得は保守コストに見合わないため固定）
