---
title: 新機能追加
description: 既存プロジェクトに新しい機能を追加する
variables:
  - name: FEATURE_NAME
    description: 機能名（例: ユーザー認証、CSV出力）
    default: ""
  - name: TARGET_FILE
    description: 主な変更対象ファイル（例: src/exporter.py）
    default: ""
  - name: REQUIREMENTS
    description: 追加要件・制約（任意）
    default: ""
tags:
  - feature
  - development
---

## タスク概要
{{FEATURE_NAME}} を実装してください。

## 要件
- 対象ファイル: {{TARGET_FILE}}
- 既存のコードスタイル・命名規則に従うこと
- エラーハンドリングを適切に実装すること
- 実装後に動作確認用のテストコマンドを提示すること
{{REQUIREMENTS}}

## 完了条件
- [ ] 機能が正常に動作する
- [ ] 既存のテストが通る
- [ ] 必要に応じてドキュメントを更新する
