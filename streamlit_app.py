"""streamlit_app.py - LangGraph Orchestrator Control Panel"""

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from src.template_loader import list_templates, load_template, render_template

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


PROJECTS_DIR = Path.home() / "projects"


def get_project_list() -> list[str]:
    """~/projects/ のディレクトリ一覧 + task_history.db の project_id を結合して返す"""
    names: set[str] = set()

    # 1. ~/projects/ 内のディレクトリ（隠しフォルダ除外）
    if PROJECTS_DIR.exists():
        for p in PROJECTS_DIR.iterdir():
            if p.is_dir() and not p.name.startswith("."):
                names.add(p.name)

    # 2. task_history.db からユニークな project_id
    try:
        conn = sqlite3.connect(str(TASK_HISTORY_DB))
        rows = conn.execute(
            "SELECT DISTINCT project_id FROM tasks WHERE project_id IS NOT NULL AND project_id != ''"
        ).fetchall()
        conn.close()
        for (pid,) in rows:
            names.add(pid)
    except Exception:
        pass

    return sorted(names)


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
    ["📊 ステータス", "📝 タスク投入", "📋 タスク履歴", "🔔 承認待ち", "📈 レポート", "⚙️ プロンプト", "🚀 サービス管理"],
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

    # キュー状態
    st.markdown("---")
    st.subheader("⚙️ タスクキュー状態")
    try:
        qresp = requests.get(f"{FASTAPI_URL}/queue/status", headers=get_headers(), timeout=3)
        if qresp.status_code == 200:
            qdata = qresp.json()
            qc1, qc2, qc3 = st.columns(3)
            qc1.metric("▶ 実行中", qdata.get("running", 0), help="現在処理中のタスク数")
            qc2.metric("⏳ 待機中", qdata.get("queued", 0),  help="キューで待機中のタスク数")
            qc3.metric("⚡ 最大同時実行", qdata.get("max_concurrent", 2))
            running_ids = qdata.get("running_task_ids", [])
            if running_ids:
                st.caption(f"実行中 task_id: {', '.join(running_ids)}")
    except Exception:
        st.caption("キュー状態取得失敗")

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

    # ── プロジェクト選択（フォーム外: 動的に text_input を表示するため）──
    existing_projects = get_project_list()
    NEW_PROJECT_LABEL = "(新規作成)"
    project_options = [NEW_PROJECT_LABEL] + existing_projects

    current_dir_name = Path(__file__).parent.name
    default_index = (
        project_options.index(current_dir_name)
        if current_dir_name in project_options
        else 0
    )

    col1_outer, col2_outer = st.columns(2)
    with col1_outer:
        selected_project = st.selectbox(
            "プロジェクト名",
            options=project_options,
            index=default_index,
        )
        if selected_project == NEW_PROJECT_LABEL:
            new_project_name = st.text_input(
                "新規プロジェクト名を入力",
                placeholder="例: my-new-project",
            )
        else:
            new_project_name = ""

    # ── テンプレート選択（フォーム外: 指示文フィールドへの注入のため）──
    with st.expander("📋 テンプレートから入力する", expanded=False):
        try:
            templates = list_templates()
        except Exception:
            templates = []

        if not templates:
            st.caption("テンプレートが見つかりません（templates/*.md を確認してください）")
        else:
            template_options = {"（なし）": None} | {t["title"]: t["id"] for t in templates}
            selected_title = st.selectbox(
                "テンプレート",
                list(template_options.keys()),
                key="tmpl_select",
            )
            selected_id = template_options[selected_title]

            if selected_id:
                try:
                    tmpl = load_template(selected_id)
                    st.caption(tmpl["description"])

                    var_values: dict[str, str] = {}
                    for var in tmpl["variables"]:
                        var_values[var["name"]] = st.text_input(
                            label=var["description"],
                            value=var["default"],
                            key=f"tvar_{var['name']}",
                        )

                    if st.button("📝 指示文に反映", key="tmpl_apply"):
                        rendered = render_template(selected_id, var_values)
                        st.session_state["template_rendered"] = rendered
                        st.success("指示文フィールドに反映しました")
                        st.rerun()
                except Exception as e:
                    st.error(f"テンプレート読み込みエラー: {e}")

    # ── 指示文（フォーム外: テンプレート展開結果を注入するため）──
    default_instruction = st.session_state.pop("template_rendered", "")
    instruction = st.text_area(
        "タスク内容",
        value=default_instruction,
        height=180,
        placeholder="例: Pythonで1から10までの合計を計算する関数を書いて",
        key="task_instruction",
    )

    # ── 送信フォーム ──
    with st.form("task_form"):
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

        require_approval = st.toggle(
            "🔔 承認モード（2段階確認）",
            value=False,
            help="ONにすると、①設計確認 と ②ファイル保存前 の2回、あなたの承認を待ってから処理を進めます。"
        )

        submitted = st.form_submit_button("🚀 タスク送信", use_container_width=True)

    if submitted:
        # project_id の確定
        if selected_project == NEW_PROJECT_LABEL:
            project_id = new_project_name.strip()
        else:
            project_id = selected_project

        if not instruction.strip():
            st.warning("タスク内容を入力してください")
        elif selected_project == NEW_PROJECT_LABEL and not project_id:
            st.warning("新規プロジェクト名を入力してください")
        else:
            payload: dict = {
                "instruction": instruction.strip(),
                "project_id":  project_id or "default",
                "requester":   "streamlit",
                "require_approval": require_approval,
            }
            if model != "（デフォルト）":
                payload["model"] = model

            with st.spinner("タスクをキューに追加中..."):
                try:
                    resp = requests.post(
                        f"{FASTAPI_URL}/task",
                        json=payload,
                        headers=get_headers(),
                        timeout=30,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        task_id        = data.get("task_id", "")
                        queue_pos      = data.get("queue_position", 0)
                        needs_approval = data.get("require_approval", False)

                        st.success(f"✅ タスクをキューに追加しました（待機: {queue_pos}件）")
                        st.code(f"task_id: {task_id}")

                        if needs_approval:
                            st.info("🔔 承認モードON: 「🔔 承認待ち」ページで設計確認が必要です。")
                        else:
                            st.info("⏳ バックグラウンドで処理中です。「📋 タスク履歴」で結果を確認してください。")
                    elif resp.status_code == 401:
                        st.error("認証エラー: API Keyを確認してください")
                    else:
                        st.error(f"送信失敗: {resp.status_code} — {resp.text[:200]}")
                except requests.exceptions.Timeout:
                    st.warning("タイムアウト（FastAPIが応答しませんでした）")
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


# ══════════════════════════════════════════════════════════════
# ページ4: 承認待ち
# ══════════════════════════════════════════════════════════════
elif page == "🔔 承認待ち":
    st.header("🔔 承認待ちタスク")

    col_refresh, col_auto = st.columns([1, 3])
    with col_refresh:
        if st.button("🔄 更新"):
            st.rerun()
    with col_auto:
        st.caption("承認が完了するとバックグラウンドのタスクが自動再開されます")

    try:
        resp = requests.get(f"{FASTAPI_URL}/approvals", headers=get_headers(), timeout=5)
        if resp.status_code == 200:
            pending = resp.json().get("pending", [])
            if not pending:
                st.success("✅ 現在、承認待ちのタスクはありません")
            else:
                for item in pending:
                    task_id = item["task_id"]
                    stage   = item["stage"]
                    stage_label = "① 設計確認" if stage == "design" else "② ファイル保存前確認"
                    created = item.get("created_at", "")[:16]

                    with st.expander(f"🕐 [{stage_label}] task_id: {task_id}  ({created})", expanded=True):
                        st.markdown(item.get("preview", ""))
                        st.markdown("---")

                        col_ok, col_ng = st.columns(2)
                        with col_ok:
                            if st.button("✅ 承認して続行", key=f"approve_{task_id}_{stage}", use_container_width=True):
                                r = requests.post(
                                    f"{FASTAPI_URL}/approve/{task_id}/{stage}",
                                    json={"approved": True, "feedback": ""},
                                    headers=get_headers(), timeout=5,
                                )
                                if r.status_code == 200:
                                    st.success("✅ 承認しました。タスクを再開します。")
                                    st.rerun()
                                else:
                                    st.error(f"エラー: {r.text}")

                        with col_ng:
                            with st.form(key=f"reject_form_{task_id}_{stage}"):
                                feedback = st.text_area(
                                    "✏️ 修正指示を入力して却下",
                                    placeholder="例: 変数名を snake_case に統一して",
                                    height=80,
                                    key=f"fb_{task_id}_{stage}",
                                )
                                if st.form_submit_button("❌ 却下して修正依頼", use_container_width=True):
                                    if not feedback.strip():
                                        st.warning("修正指示を入力してください")
                                    else:
                                        r = requests.post(
                                            f"{FASTAPI_URL}/approve/{task_id}/{stage}",
                                            json={"approved": False, "feedback": feedback.strip()},
                                            headers=get_headers(), timeout=5,
                                        )
                                        if r.status_code == 200:
                                            st.warning("🔄 却下しました。修正指示を送信しました。")
                                            st.rerun()
                                        else:
                                            st.error(f"エラー: {r.text}")
        else:
            st.error(f"承認待ち取得失敗: {resp.status_code}")
    except requests.exceptions.ConnectionError:
        st.error("FastAPIに接続できません")
    except Exception as e:
        st.error(f"エラー: {e}")

    # 承認履歴
    st.markdown("---")
    st.subheader("📜 承認履歴")
    try:
        resp = requests.get(f"{FASTAPI_URL}/approvals/history", headers=get_headers(), timeout=5)
        if resp.status_code == 200:
            history = resp.json().get("history", [])
            if history:
                import pandas as pd
                df_hist = pd.DataFrame(history)
                df_hist["status"] = df_hist["status"].map(
                    {"pending": "⏳", "approved": "✅", "rejected": "❌"}
                ).fillna(df_hist["status"])
                st.dataframe(
                    df_hist[["task_id", "stage", "status", "feedback", "created_at", "resolved_at"]],
                    use_container_width=True, hide_index=True,
                )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
# ページ5: レポート閲覧
# ══════════════════════════════════════════════════════════════
elif page == "📈 レポート":
    st.header("📈 レポート閲覧")

    reports_dir = Path(__file__).parent / "reports"
    if not reports_dir.exists():
        st.warning("reports/ ディレクトリが存在しません")
    else:
        md_files = sorted(reports_dir.glob("*.md"), reverse=True)
        if not md_files:
            st.info("レポートファイルがありません")
        else:
            file_names = [f.name for f in md_files]
            selected = st.selectbox("📄 レポートを選択", file_names)
            if selected:
                report_path = reports_dir / selected
                content = report_path.read_text(encoding="utf-8")
                st.markdown(f"**ファイル**: `{selected}` | **サイズ**: {len(content):,} bytes")
                st.markdown("---")
                st.markdown(content)


# ══════════════════════════════════════════════════════════════
# ページ6: プロンプト編集
# ══════════════════════════════════════════════════════════════
elif page == "⚙️ プロンプト":
    st.header("⚙️ プロンプト編集")
    st.caption("agents のプロンプトをブラウザ上で編集・保存できます。変更は即時反映されます。")

    prompts_dir = Path(__file__).parent / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    prompt_files = sorted(prompts_dir.glob("*.md"))

    if not prompt_files:
        st.warning("prompts/ ディレクトリにファイルがありません")
    else:
        agent_names  = [f.stem for f in prompt_files]
        selected_agent = st.selectbox("🤖 エージェントを選択", agent_names)

        if selected_agent:
            prompt_path   = prompts_dir / f"{selected_agent}.md"
            original_text = prompt_path.read_text(encoding="utf-8")

            edited_text = st.text_area(
                "プロンプト内容",
                value=original_text,
                height=400,
                key=f"prompt_editor_{selected_agent}",
            )

            # 差分表示
            if edited_text != original_text:
                import difflib
                diff = difflib.unified_diff(
                    original_text.splitlines(keepends=True),
                    edited_text.splitlines(keepends=True),
                    fromfile="現在",
                    tofile="編集後",
                )
                diff_text = "".join(diff)
                if diff_text:
                    st.subheader("📊 変更差分")
                    st.code(diff_text, language="diff")

            col_save, col_reset = st.columns(2)
            with col_save:
                if st.button("💾 保存", use_container_width=True, type="primary"):
                    prompt_path.write_text(edited_text, encoding="utf-8")
                    st.success(f"✅ {selected_agent}.md を保存しました")
                    st.rerun()

            with col_reset:
                if st.button("🔄 デフォルトにリセット", use_container_width=True):
                    try:
                        import sys
                        sys.path.insert(0, str(Path(__file__).parent))
                        from src.prompt_loader import reset_prompt
                        reset_prompt(selected_agent)
                        st.success(f"✅ {selected_agent}.md をリセットしました")
                        st.rerun()
                    except Exception as e:
                        st.error(f"リセット失敗: {e}")


# ══════════════════════════════════════════════════════════════
# ページ7: サービス管理
# ══════════════════════════════════════════════════════════════
elif page == "🚀 サービス管理":
    import streamlit.components.v1 as components
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent))
    from src.service_manager import ServiceManager

    st.header("🚀 サービス管理")
    st.caption("AIが生成した Streamlit アプリを起動・停止・プレビューできます（ポート: 8502〜8510）")

    sm = ServiceManager()

    # ── session_state 初期化 ─────────────────────────────────
    if "preview_service_id" not in st.session_state:
        st.session_state["preview_service_id"] = None
    # iframeを強制再読み込みするためのカウンター
    if "iframe_reload_count" not in st.session_state:
        st.session_state["iframe_reload_count"] = 0

    # ── セクション1: 起動中サービス一覧 ──────────────────────
    st.subheader("📋 起動中サービス一覧")

    col_ref, col_all = st.columns([1, 3])
    with col_ref:
        if st.button("🔄 更新"):
            st.rerun()
    with col_all:
        show_stopped = st.checkbox("停止済みも表示", value=False)

    try:
        services = sm.list_services(include_stopped=show_stopped)
    except Exception as e:
        st.error(f"一覧取得失敗: {e}")
        services = []

    if not services:
        st.info("起動中のサービスはありません")
    else:
        for svc in services:
            status      = svc.get("status", "unknown")
            status_icon = "🟢" if status == "running" else ("🔴" if status == "error" else "⚫")
            port        = svc.get("port", "?")
            url         = svc.get("url", f"http://localhost:{port}")
            tailscale_url = f"http://100.72.133.8:{port}"
            started     = (svc.get("started_at") or "")[:16]
            sid         = svc["service_id"]
            is_previewing = st.session_state["preview_service_id"] == sid

            with st.expander(
                f"{status_icon} **{svc['project_name']}** — port {port}  ({started})",
                expanded=(status == "running"),
            ):
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.caption(f"📂 {svc['app_path']}")
                c2.caption(f"PID: {svc.get('pid', '-')}")
                c3.caption(f"状態: {status}")

                if status == "running":
                    b1, b2, b3, b4 = st.columns(4)
                    with b1:
                        preview_label = "📺 プレビュー中" if is_previewing else "📺 プレビュー"
                        if st.button(preview_label, key=f"prev_{sid}", use_container_width=True, type="primary" if is_previewing else "secondary"):
                            if is_previewing:
                                st.session_state["preview_service_id"] = None
                            else:
                                st.session_state["preview_service_id"] = sid
                            st.rerun()
                    with b2:
                        st.link_button("🔗 別タブ", url, use_container_width=True)
                    with b3:
                        st.link_button("🌐 Tailscale", tailscale_url, use_container_width=True)
                    with b4:
                        if st.button("⏹ 停止", key=f"stop_{sid}", use_container_width=True):
                            try:
                                sm.stop(sid)
                                if st.session_state["preview_service_id"] == sid:
                                    st.session_state["preview_service_id"] = None
                                st.success("停止しました")
                                st.rerun()
                            except Exception as e:
                                st.error(f"停止失敗: {e}")

    # ── セクション2: プレビューエリア（左右分割） ──────────────
    preview_id = st.session_state.get("preview_service_id")
    if preview_id:
        preview_svc = sm.get(preview_id)

        if not preview_svc or preview_svc.get("status") != "running":
            st.session_state["preview_service_id"] = None
            st.warning("サービスが停止しています。プレビューを閉じました。")
            st.rerun()
        else:
            port = preview_svc["port"]
            url  = preview_svc["url"]
            tailscale_url = f"http://100.72.133.8:{port}"

            st.markdown("---")
            st.subheader(f"📺 プレビュー: {preview_svc['project_name']}")

            left_col, right_col = st.columns([1, 2])

            # ── 左パネル: 指示パネル ─────────────────────────
            with left_col:
                st.caption(f"📂 **{preview_svc['project_name']}**")
                st.caption(f"🔗 {url}")
                st.caption(f"🌐 Tailscale: {tailscale_url}")

                b_r, b_s, b_l = st.columns(3)
                with b_r:
                    if st.button("🔄 再読込", key="iframe_reload", use_container_width=True):
                        st.session_state["iframe_reload_count"] += 1
                        st.rerun()
                with b_s:
                    if st.button("⏹ 停止", key="preview_stop", use_container_width=True):
                        sm.stop(preview_id)
                        st.session_state["preview_service_id"] = None
                        st.success("停止しました")
                        st.rerun()
                with b_l:
                    st.link_button("🔗 別タブ", url, use_container_width=True)

                # ── M8-3: スクリーンショット ───────────────────
                st.divider()
                st.subheader("📸 スクリーンショット")

                from src.screenshot_agent import capture_screenshot as _capture

                if st.button("📸 今の画面をキャプチャ", use_container_width=True, key="capture_btn"):
                    with st.spinner("撮影中..."):
                        cap_result = _capture(
                            url=url,
                            project_name=preview_svc["project_name"],
                        )
                    if cap_result["success"]:
                        st.session_state["last_capture"] = cap_result
                        st.success(f"撮影完了: {Path(cap_result['path']).name}")
                    else:
                        st.error(f"撮影失敗: {cap_result['error']}")

                # 撮影済み画像の表示と添付
                if "last_capture" in st.session_state:
                    cap = st.session_state["last_capture"]
                    if cap.get("path") and Path(cap["path"]).exists():
                        st.image(
                            cap["path"],
                            caption=f"撮影: {(cap.get('captured_at') or '')[:19]}",
                            use_container_width=True,
                        )
                        attach_col, clear_col = st.columns(2)
                        with attach_col:
                            if st.button("📎 修正指示に添付", use_container_width=True, key="attach_btn"):
                                st.session_state["attach_screenshot"] = cap["path"]
                                st.info("添付しました。下の修正指示を入力して投入してください。")
                        with clear_col:
                            if st.button("🗑 クリア", use_container_width=True, key="clear_cap_btn"):
                                del st.session_state["last_capture"]
                                st.session_state.pop("attach_screenshot", None)
                                st.rerun()

                st.divider()

                # タスク投入エリア
                st.subheader("📝 修正指示")

                # 添付中スクリーンショットの表示
                if "attach_screenshot" in st.session_state:
                    attach_path = st.session_state["attach_screenshot"]
                    if Path(attach_path).exists():
                        st.image(attach_path, caption="添付中のスクリーンショット", width=200)
                    if st.button("❌ 添付を外す", key="detach_btn"):
                        for k in ("attach_screenshot", "vision_instruction"):
                            st.session_state.pop(k, None)
                        st.rerun()

                    # ── M5-3: Vision 解釈エリア ───────────────────
                    st.divider()
                    st.subheader("🔍 Vision 解釈")

                    vision_hint = st.text_input(
                        "修正のポイントを一言で（任意）",
                        placeholder="例: ボタンが見づらい / レイアウトを整えて",
                        key="vision_hint",
                    )

                    if st.button("🔍 AIに画像を解釈させる", use_container_width=True, key="vision_btn"):
                        from src.vision_agent import interpret_screenshot as _interpret
                        with st.spinner("Vision API で解釈中..."):
                            v_result = _interpret(
                                image_path=st.session_state["attach_screenshot"],
                                user_instruction=vision_hint or "UIの問題点を特定して修正指示を生成してください",
                                project_name=preview_svc["project_name"],
                            )
                        if v_result["success"]:
                            st.session_state["vision_instruction"] = v_result["interpreted_instruction"]
                            st.success("解釈完了")
                        else:
                            st.error(f"解釈失敗: {v_result['error']}")

                    # 解釈結果の表示・編集 + 専用投入ボタン
                    if "vision_instruction" in st.session_state:
                        st.caption("生成された指示文（編集可）")
                        edited_vision = st.text_area(
                            label="指示文",
                            value=st.session_state["vision_instruction"],
                            height=100,
                            key="edited_vision_instruction",
                            label_visibility="collapsed",
                        )
                        require_approval_vision = st.checkbox(
                            "🔔 承認モード", value=False, key="vision_approval"
                        )
                        if st.button("📝 この指示でタスク投入", use_container_width=True, type="primary", key="vision_submit"):
                            vision_payload = {
                                "instruction":      edited_vision.strip(),
                                "project_id":       preview_svc["project_name"],
                                "requester":        "streamlit_vision",
                                "require_approval": require_approval_vision,
                            }
                            try:
                                resp = requests.post(
                                    f"{FASTAPI_URL}/task",
                                    json=vision_payload,
                                    headers=get_headers(),
                                    timeout=30,
                                )
                                if resp.status_code == 200:
                                    data = resp.json()
                                    st.toast("タスクを投入しました 🚀")
                                    st.caption(f"Task ID: {data.get('task_id', '')}")
                                    # 使用済みセッションをクリア
                                    for k in ("attach_screenshot", "vision_instruction"):
                                        st.session_state.pop(k, None)
                                else:
                                    st.error(f"投入失敗: {resp.status_code}")
                            except requests.exceptions.ConnectionError:
                                st.error("FastAPIに接続できません")
                            except Exception as e:
                                st.error(f"エラー: {e}")

                st.divider()

                # ── 手動タスク投入エリア ──────────────────────
                task_input = st.text_area(
                    "このアプリへの修正指示",
                    placeholder="例: ボタンを画面中央に配置して\n例: タイトルのフォントを大きくして",
                    height=130,
                    key="preview_task_input",
                )
                require_approval_preview = st.checkbox(
                    "🔔 承認モード", value=False, key="preview_approval"
                )

                if st.button("📝 タスク投入", use_container_width=True, type="primary", key="preview_submit"):
                    if not task_input.strip():
                        st.warning("修正指示を入力してください")
                    else:
                        # スクリーンショットパスを指示文に含める（Pattern C）
                        # Vision 解釈済みの場合はそちらを使うことを推奨するが、
                        # 手動入力でも独立して使用できる。
                        final_instruction = task_input.strip()
                        screenshot_path = st.session_state.get("attach_screenshot")
                        if screenshot_path:
                            final_instruction += f"\n\n[参考スクリーンショット: {screenshot_path}]"

                        payload = {
                            "instruction":      final_instruction,
                            "project_id":       preview_svc["project_name"],
                            "requester":        "streamlit_preview",
                            "require_approval": require_approval_preview,
                        }
                        try:
                            resp = requests.post(
                                f"{FASTAPI_URL}/task",
                                json=payload,
                                headers=get_headers(),
                                timeout=30,
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                st.toast("タスクを投入しました 🚀")
                                st.caption(f"Task ID: {data.get('task_id', '')}")
                                st.session_state.pop("attach_screenshot", None)
                            else:
                                st.error(f"投入失敗: {resp.status_code}")
                        except requests.exceptions.ConnectionError:
                            st.error("FastAPIに接続できません")
                        except Exception as e:
                            st.error(f"エラー: {e}")

            # ── 右パネル: iframe ─────────────────────────────
            with right_col:
                # iframe src にリロードカウンターをクエリパラメータとして付与し
                # 「🔄 再読込」ボタン押下時に新しい src として認識させる
                reload_count = st.session_state["iframe_reload_count"]
                iframe_src = f"{url}?_r={reload_count}"

                try:
                    components.iframe(iframe_src, height=700, scrolling=True)
                except Exception:
                    # iframe がブロックされた場合のフォールバック
                    st.warning(
                        "iframe の表示がブロックされました。\n"
                        "別タブでアプリを確認してください。"
                    )
                    st.link_button("🔗 アプリを別タブで開く", url, use_container_width=True)
                    st.link_button("🌐 Tailscale で開く", tailscale_url, use_container_width=True)

    # ── セクション3: 新規起動フォーム ────────────────────────
    st.markdown("---")
    st.subheader("▶ 新規起動")

    with st.form("launch_form"):
        launch_project = st.text_input(
            "プロジェクト名",
            placeholder="例: my-dashboard",
        )
        launch_path = st.text_input(
            "アプリファイルパス",
            placeholder="例: ~/projects/myapp/app.py",
        )
        launched = st.form_submit_button("🚀 起動", use_container_width=True, type="primary")

    if launched:
        if not launch_project.strip():
            st.warning("プロジェクト名を入力してください")
        elif not launch_path.strip():
            st.warning("アプリファイルパスを入力してください")
        else:
            try:
                svc = sm.start(launch_project.strip(), launch_path.strip())
                st.success(f"✅ 起動しました → {svc['url']}  (port {svc['port']})")
                col_a, col_b = st.columns(2)
                with col_a:
                    st.link_button("🔗 別タブで開く", svc["url"], use_container_width=True)
                with col_b:
                    if st.button("📺 プレビューを開く", use_container_width=True, key="open_preview_after_launch"):
                        st.session_state["preview_service_id"] = svc["service_id"]
                st.rerun()
            except FileNotFoundError as e:
                st.error(f"ファイルが見つかりません: {e}")
            except RuntimeError as e:
                st.error(f"起動失敗: {e}")
            except Exception as e:
                st.error(f"予期しないエラー: {e}")

