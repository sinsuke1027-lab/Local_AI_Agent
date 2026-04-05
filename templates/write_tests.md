---
title: テストコード作成
description: 指定ファイルに対するテストコードを作成する
variables:
  - name: TARGET_FILE
    description: テスト対象のファイル（例: src/cost_table.py）
    default: ""
  - name: TEST_FRAMEWORK
    description: テストフレームワーク
    default: pytest
tags:
  - test
  - quality
---

## タスク概要
`{{TARGET_FILE}}` に対する {{TEST_FRAMEWORK}} テストコードを作成してください。

## 要件
- テストファイルの配置場所: `tests/test_<対象ファイル名>.py`
- 正常系・異常系の両方をカバーすること
- テスト関数名は `test_<機能名>_<条件>` の形式にすること
- フィクスチャが必要な場合は `conftest.py` に定義すること
- 外部依存（DB・API等）は `unittest.mock` でモックすること

## テスト実行コマンド
```bash
cd ~/projects/langgraph-orchestrator
.venv/bin/pytest tests/test_<対象ファイル名>.py -v
```

## 完了条件
- [ ] 全テストが PASS する
- [ ] カバレッジが主要な関数・メソッドをカバーしている
- [ ] `pytest tests/` でエラーなく実行できる
