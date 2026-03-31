"""streamlit_app.py - LangGraph Orchestrator Control Panel"""

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

# --- 設定 ---
FASTAPI_URL = "http://localhost:8001"
TASK_HISTORY_DB = Path.home() / ".roo" / "task_history.db"

# API Keyを.envから読む
API_KEY = os.getenv("FASTAPI_API_KEY", "")
if not API_KEY:
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("FASTAPI_API_KEY="):
                API_KEY = line.split("=", 1)[1].strip()
                break


def get_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    return headers


def fetch_health() -> bool:
    try:
        r = requests.get(f"{FASTAPI_URL}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


# ── ページ設定 ──────────────────────────────────────────────
st.set_page_config(
    page_title="LangGraph Orchestrator",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 LangGraph Orchestrator")

# ── サイドバー ──────────────────────────────────────────────
page = st.sidebar.radio(
    "ページ",
    ["📊 ステータス", "📝 タスク投入", "📋 タスク履歴"],
)

st.sidebar.markdown("---")
st.sidebar.markdown("### サービス状態")
if fetch_health():
    st.sidebar.success("FastAPI: 稼働中")
else:
    st.sidebar.error("FastAPI: 接続不可")


# ══════════════════════════════════════════════════════════════
# ページ1: リアルタイムステータス
# ══════════════════════════════════════════════════════════════
if page == "📊 ステータス":
    st.header("📊 リアルタイムステータス")

    # 最新タスク（FastAPI経由）
    try:
        resp = requests.get(
            f"{FASTAPI_URL}/status/latest",
            headers=get_headers(),
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            col1, col2, col3, col4 = st.columns(4)
            status_label = "✅ 完了" if data.get("status") == "completed" else "❌ 失敗"
            col1.metric("ステータス", status_label)
            col2.metric("モデル", data.get("model_used") or "不明")
            col3.metric("トークン", f"{data.get('token_count') or 0:,}")
            col4.metric("コスト", f"¥{data.get('cost_jpy', 0)}")

            st.subheader("タスク内容")
            st.text(data.get("instruction") or "なし")

            if data.get("result"):
                st.subheader("結果")
                st.code(data["result"], language="python")

            if data.get("error"):
                st.subheader("エラー")
                st.error(data["error"])

        elif resp.status_code == 401:
            st.error("認証エラー: API Keyを確認してください")
        elif resp.status_code == 404:
            st.info("タスク履歴がありません")
        else:
            st.warning(f"ステータス取得失敗: {resp.status_code}")
    except requests.exceptions.ConnectionError:
        st.error("FastAPIに接続できません")
    except Exception as e:
        st.error(f"エラー: {e}")

    if st.button("🔄 更新"):
        st.rerun()

    # 直近24時間の統計（SQLite直接）
    st.markdown("---")
    st.subheader("直近24時間の統計")
    try:
        conn = sqlite3.connect(str(TASK_HISTORY_DB))
        since = (datetime.now() - timedelta(hours=24)).isoformat()
        row = conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN error_message IS NULL THEN 1 ELSE 0 END) as success,
                SUM(CASE WHEN error_message IS NOT NULL THEN 1 ELSE 0 END) as failed,
                SUM(token_count) as total_tokens
            FROM tasks
            WHERE completed_at >= ?
            """,
            [since],
        ).fetchone()
        conn.close()

        if row:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("タスク数", row[0])
            c2.metric("✅ 成功", row[1] or 0)
            c3.metric("❌ 失敗", row[2] or 0)
            c4.metric("総トークン", f"{row[3] or 0:,}")
    except Exception as e:
        st.warning(f"統計取得失敗: {e}")


# ══════════════════════════════════════════════════════════════
# ページ2: タスク投入
# ══════════════════════════════════════════════════════════════
elif page == "📝 タスク投入":
    st.header("📝 タスク投入")

    with st.form("task_form"):
        instruction = st.text_area(
            "タスク内容",
            height=150,
            placeholder="例: Pythonで1から10までの合計を計算する関数を書いて",
        )

        col1, col2 = st.columns(2)
        with col1:
            project = st.text_input("プロジェクト名", value="langgraph-orchestrator")
        with col2:
            model = st.selectbox(
                "モデル",
                [
                    "（デフォルト）",
                    "qwen2.5-coder:14b",
                    "qwen2.5-coder:7b",
                    "deepseek-r1:14b",
                    "gemini-2.5-flash",
                ],
            )

        submitted = st.form_submit_button("🚀 タスク送信", use_container_width=True)

    if submitted:
        if not instruction.strip():
            st.warning("タスク内容を入力してください")
        else:
            payload: dict = {
                "instruction": instruction.strip(),
                "project_id": project or "default",
                "requester": "streamlit",
            }
            if model != "（デフォルト）":
                payload["model"] = model

            with st.spinner("タスクを実行中... (完了まで数分かかる場合があります)"):
                try:
                    resp = requests.post(
                        f"{FASTAPI_URL}/task",
                        json=payload,
                        headers=get_headers(),
                        timeout=600,
                    )
                    if resp.status_code == 200:
                        st.success("✅ タスクが完了しました！")
                        data = resp.json()
                        c1, c2, c3 = st.columns(3)
                        c1.metric("task_id", data.get("task_id", ""))
                        c2.metric("トークン", f"{data.get('tokens', 0):,}")
                        c3.metric("複雑度スコア", data.get("complexity_score") or "-")
                        if data.get("result"):
                            st.subheader("実行結果")
                            st.code(data["result"], language="python")
                    elif resp.status_code == 401:
                        st.error("認証エラー: API Keyを確認してください")
                    else:
                        st.error(f"送信失敗: {resp.status_code} — {resp.text[:200]}")
                except requests.exceptions.Timeout:
                    st.warning("タイムアウトしました（タスクはバックグラウンドで実行中の可能性があります）")
                except requests.exceptions.ConnectionError:
                    st.error("FastAPIに接続できません")
                except Exception as e:
                    st.error(f"エラー: {e}")


# ══════════════════════════════════════════════════════════════
# ページ3: タスク履歴
# ══════════════════════════════════════════════════════════════
elif page == "📋 タスク履歴":
    st.header("📋 タスク履歴")

    # フィルタ
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        status_filter = st.selectbox("ステータス", ["全て", "✅ 成功のみ", "❌ 失敗のみ"])
    with col2:
        model_filter = st.selectbox(
            "モデル",
            ["全て", "qwen2.5-coder:14b", "deepseek-r1:14b", "qwen2.5-coder:7b", "gemini-2.5-flash"],
        )
    with col3:
        days_filter = st.selectbox("期間", ["直近7日", "直近30日", "全期間"])
    with col4:
        search_query = st.text_input("キーワード検索", placeholder="タスク内容を検索")

    # クエリ構築
    conditions = []
    params: list = []

    if status_filter == "✅ 成功のみ":
        conditions.append("error_message IS NULL")
    elif status_filter == "❌ 失敗のみ":
        conditions.append("error_message IS NOT NULL")

    if model_filter != "全て":
        conditions.append("model_used = ?")
        params.append(model_filter)

    if days_filter == "直近7日":
        conditions.append("completed_at >= ?")
        params.append((datetime.now() - timedelta(days=7)).isoformat())
    elif days_filter == "直近30日":
        conditions.append("completed_at >= ?")
        params.append((datetime.now() - timedelta(days=30)).isoformat())

    if search_query:
        conditions.append("instruction LIKE ?")
        params.append(f"%{search_query}%")

    where = " AND ".join(conditions) if conditions else "1=1"

    try:
        conn = sqlite3.connect(str(TASK_HISTORY_DB))
        df = pd.read_sql_query(
            f"""
            SELECT
                task_id,
                substr(instruction, 1, 80)    AS instruction,
                CASE WHEN error_message IS NULL THEN '✅' ELSE '❌' END AS status,
                model_used,
                complexity_score,
                CASE WHEN debate_triggered = 1 THEN '🔵' ELSE '' END AS debate,
                token_count,
                substr(completed_at, 1, 16)   AS completed_at
            FROM tasks
            WHERE {where}
            ORDER BY completed_at DESC
            LIMIT 100
            """,
            conn,
            params=params,
        )
        conn.close()

        st.dataframe(
            df,
            column_config={
                "task_id":          st.column_config.TextColumn("ID",       width="small"),
                "instruction":      st.column_config.TextColumn("タスク",   width="large"),
                "status":           st.column_config.TextColumn("結果",     width="small"),
                "model_used":       st.column_config.TextColumn("モデル",   width="medium"),
                "complexity_score": st.column_config.NumberColumn("複雑度", width="small"),
                "debate":           st.column_config.TextColumn("議論",     width="small"),
                "token_count":      st.column_config.NumberColumn("Token",  width="small"),
                "completed_at":     st.column_config.TextColumn("完了日時", width="medium"),
            },
            use_container_width=True,
            hide_index=True,
        )
        st.caption(f"{len(df)} 件表示（最大100件）")

        # 詳細表示
        if not df.empty:
            st.markdown("---")
            st.subheader("タスク詳細")
            selected_id = st.selectbox("タスクIDを選択", df["task_id"].tolist())
            if selected_id:
                conn = sqlite3.connect(str(TASK_HISTORY_DB))
                row = conn.execute(
                    "SELECT * FROM tasks WHERE task_id = ?", [selected_id]
                ).fetchone()
                col_names = [d[0] for d in conn.execute(
                    "SELECT * FROM tasks WHERE task_id = ?", [selected_id]
                ).description or []]
                conn.close()

                if row:
                    # カラム名で辞書化
                    conn2 = sqlite3.connect(str(TASK_HISTORY_DB))
                    conn2.row_factory = sqlite3.Row
                    detail = dict(conn2.execute(
                        "SELECT * FROM tasks WHERE task_id = ?", [selected_id]
                    ).fetchone())
                    conn2.close()

                    c1, c2, c3 = st.columns(3)
                    c1.text(f"ID: {detail.get('task_id', '')}")
                    c2.text(f"モデル: {detail.get('model_used', '')}")
                    c3.text(f"複雑度: {detail.get('complexity_score', 'N/A')}")
                    st.text(f"完了日時: {detail.get('completed_at', '')}")

                    st.subheader("指示")
                    st.text(detail.get("instruction", ""))

                    if detail.get("result"):
                        st.subheader("結果")
                        st.code(detail["result"], language="python")

                    if detail.get("error_message"):
                        st.subheader("エラー")
                        st.error(detail["error_message"])

                    if detail.get("debate_result"):
                        st.subheader("ディベート結果")
                        st.info(detail["debate_result"])

    except Exception as e:
        st.error(f"履歴取得失敗: {e}")
