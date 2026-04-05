# タスクテンプレートの追加方法

このディレクトリのテンプレートは Streamlit の「📝 タスク投入」ページから選択できます。

## ファイル形式

`templates/*.md` に以下の形式で作成してください。`README.md` は一覧に表示されません。

## フロントマター（必須）

```yaml
---
title: テンプレートの表示名
description: どんな用途向けか（1〜2文）
variables:
  - name: 変数名（大文字スネークケース）
    description: Streamlit UI での入力欄ラベル
    default: デフォルト値（空でも可）
tags:
  - タグ（feature / bugfix / refactor / test / api / streamlit など）
---
```

## 本文

変数は `{{変数名}}` で参照します。

```markdown
## タスク概要
{{FEATURE_NAME}} を実装してください。

対象ファイル: {{TARGET_FILE}}
```

## 組み込みテンプレート一覧

| ファイル | 用途 |
|--------|------|
| `new_feature.md` | 新機能追加 |
| `bug_fix.md` | バグ修正 |
| `refactor.md` | リファクタリング |
| `new_streamlit_app.md` | Streamlit アプリ新規作成 |
| `api_endpoint.md` | FastAPI エンドポイント追加 |
| `write_tests.md` | テストコード作成 |
