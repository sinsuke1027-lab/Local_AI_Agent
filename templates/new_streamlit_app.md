---
title: Streamlitアプリ新規作成
description: 新しいStreamlitアプリを作成してサービスマネージャーで起動する
variables:
  - name: APP_NAME
    description: アプリ名（ファイル名にも使用。例: dashboard、data_viewer）
    default: ""
  - name: APP_PURPOSE
    description: アプリの目的・概要（例: 売上データをグラフで可視化する）
    default: ""
  - name: DATA_SOURCE
    description: データソース（例: SQLite DB、CSV ファイル、FastAPI エンドポイント）
    default: ""
tags:
  - streamlit
  - feature
  - development
---

## タスク概要
{{APP_PURPOSE}} を実現する Streamlit アプリを新規作成してください。

## 仕様
- ファイル名: `{{APP_NAME}}.py`（プロジェクトルートに配置）
- データソース: {{DATA_SOURCE}}
- Streamlit の標準コンポーネント（st.dataframe / st.chart 等）を活用すること
- シンプルで直感的な UI を心がけること

## 実装要件
- ページタイトルと説明文を含めること（st.title / st.caption）
- エラー時に st.error で分かりやすいメッセージを表示すること
- データが空の場合の空状態表示を実装すること
- `if __name__ == "__main__":` ブロックは不要（streamlit run で実行するため）

## 起動確認
実装後、以下のコマンドで動作確認してください:
```bash
streamlit run {{APP_NAME}}.py --server.port 8502
```

その後、Streamlit Control Panel の「🚀 サービス管理」ページからも起動・確認できます。

## 完了条件
- [ ] アプリが起動してエラーなく表示される
- [ ] データが正常に表示される
- [ ] エラーハンドリングが機能する
