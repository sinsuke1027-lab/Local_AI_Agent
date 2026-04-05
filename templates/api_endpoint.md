---
title: FastAPIエンドポイント追加
description: FastAPI アプリケーションに新しいエンドポイントを追加する
variables:
  - name: ENDPOINT_PATH
    description: エンドポイントのパス（例: /items/{id}、/reports/summary）
    default: ""
  - name: HTTP_METHOD
    description: HTTPメソッド（GET / POST / PUT / DELETE）
    default: GET
  - name: REQUEST_SCHEMA
    description: リクエストの形式（例: {"name": str, "value": int}、パスパラメータのみなど）
    default: ""
  - name: RESPONSE_SCHEMA
    description: レスポンスの形式（例: {"result": str, "count": int}）
    default: ""
tags:
  - api
  - feature
  - development
---

## タスク概要
FastAPI に `{{HTTP_METHOD}} {{ENDPOINT_PATH}}` エンドポイントを追加してください。

## 仕様

### リクエスト
{{REQUEST_SCHEMA}}

### レスポンス
{{RESPONSE_SCHEMA}}

## 実装要件
- 既存の `main.py` に追加すること（新規ファイルは作らない）
- Pydantic モデルでリクエスト/レスポンスのスキーマを定義すること
- 適切なエラーレスポンス（HTTPException）を実装すること
- エンドポイントに docstring を記載すること
- 認証が必要な場合は既存の `src/auth.py` の `verify_api_key` を使うこと

## 完了条件
- [ ] エンドポイントが正常にレスポンスを返す
- [ ] Swagger UI（/docs）でエンドポイントが確認できる
- [ ] エラーケースが適切にハンドリングされる
