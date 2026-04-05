---
title: バグ修正
description: 発生しているバグを特定して修正する
variables:
  - name: BUG_DESCRIPTION
    description: バグの概要（例: ログイン後にセッションが切れる）
    default: ""
  - name: ERROR_MESSAGE
    description: エラーメッセージやスタックトレース（任意）
    default: ""
  - name: AFFECTED_FILE
    description: 問題が発生しているファイル（分かれば）
    default: ""
tags:
  - bugfix
  - debug
---

## バグ概要
{{BUG_DESCRIPTION}}

## エラー情報
```
{{ERROR_MESSAGE}}
```

## 調査・修正方針
- 対象ファイル: {{AFFECTED_FILE}}
- 原因を特定してから修正すること
- 修正範囲を最小限にとどめ、既存の動作を壊さないこと
- 修正後に再現手順を実行して解消を確認すること

## 完了条件
- [ ] バグが再現しなくなった
- [ ] 関連するテストが通る
- [ ] 副作用がないことを確認した
