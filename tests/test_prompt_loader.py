"""
tests/test_prompt_loader.py — P10b: プロンプト外部化テスト
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from src.prompt_loader import (
    load_prompt,
    render_prompt,
    reset_prompt,
    list_prompts,
    DEFAULT_PROMPTS,
    PROMPTS_DIR,
)


# ── テスト1: プロンプトファイルが自動生成されること ──────────
def test_load_prompt_auto_creates_file(tmp_path, monkeypatch):
    """ファイルが無い場合にデフォルトから自動生成されること"""
    import src.prompt_loader as pl
    monkeypatch.setattr(pl, "PROMPTS_DIR", tmp_path)

    result = pl.load_prompt("coder_agent")

    generated = tmp_path / "coder_agent.md"
    assert generated.exists(), "プロンプトファイルが自動生成されていない"
    assert result == DEFAULT_PROMPTS["coder_agent"]


# ── テスト2: テンプレートの内容確認 ──────────────────────
def test_default_prompts_contain_required_keys():
    """DEFAULT_PROMPTSに必要な5エージェントが含まれること"""
    expected_agents = {"coder_agent", "reviewer_agent", "file_agent", "bash_agent", "search_agent"}
    assert expected_agents == set(DEFAULT_PROMPTS.keys())


def test_coder_agent_template_has_placeholders():
    """coder_agentテンプレートに必要なプレースホルダーが含まれること"""
    template = DEFAULT_PROMPTS["coder_agent"]
    for placeholder in ["{instruction}", "{context_section}", "{constitution_section}",
                         "{error_feedback}", "{memory_feedback}",
                         "{success_patterns_section}", "{debate_feedback_section}"]:
        assert placeholder in template, f"{placeholder} がテンプレートに含まれていない"


# ── テスト3: render_promptで変数が正しく埋め込まれること ──────
def test_render_prompt_injects_variables(tmp_path, monkeypatch):
    """render_promptが変数を正しく埋め込むこと"""
    import src.prompt_loader as pl
    monkeypatch.setattr(pl, "PROMPTS_DIR", tmp_path)

    result = pl.render_prompt(
        "search_agent",
        instruction="FastAPI の使い方を調べる",
    )

    assert "FastAPI の使い方を調べる" in result
    assert "{instruction}" not in result


def test_render_prompt_reviewer(tmp_path, monkeypatch):
    """reviewer_agentのrender_promptが正しく動作すること"""
    import src.prompt_loader as pl
    monkeypatch.setattr(pl, "PROMPTS_DIR", tmp_path)

    result = pl.render_prompt(
        "reviewer_agent",
        instruction="テストタスク",
        result="def foo(): pass",
        constitution_section="",
    )

    assert "テストタスク" in result
    assert "def foo(): pass" in result
    assert "APPROVED" in result


# ── テスト4: ファイル削除後にデフォルトにフォールバックすること ──
def test_load_prompt_fallback_after_delete(tmp_path, monkeypatch):
    """ファイル削除後に再度ロードするとデフォルトから復元されること"""
    import src.prompt_loader as pl
    monkeypatch.setattr(pl, "PROMPTS_DIR", tmp_path)

    # 初回生成
    pl.load_prompt("bash_agent")
    prompt_file = tmp_path / "bash_agent.md"
    assert prompt_file.exists()

    # 削除
    prompt_file.unlink()
    assert not prompt_file.exists()

    # 再ロード → デフォルトから復元
    result = pl.load_prompt("bash_agent")
    assert prompt_file.exists(), "削除後のフォールバックでファイルが復元されていない"
    assert result == DEFAULT_PROMPTS["bash_agent"]


# ── テスト5: カスタムプロンプトが優先されること ──────────────
def test_custom_prompt_overrides_default(tmp_path, monkeypatch):
    """prompts/ディレクトリのファイルを編集するとカスタム内容が使われること"""
    import src.prompt_loader as pl
    monkeypatch.setattr(pl, "PROMPTS_DIR", tmp_path)

    custom = "カスタムプロンプト: タスク={instruction}"
    (tmp_path / "search_agent.md").write_text(custom, encoding="utf-8")

    result = pl.load_prompt("search_agent")
    assert result == custom

    rendered = pl.render_prompt("search_agent", instruction="テスト")
    assert rendered == "カスタムプロンプト: タスク=テスト"


# ── テスト6: reset_promptが動作すること ─────────────────────
def test_reset_prompt_restores_default(tmp_path, monkeypatch):
    """reset_promptがカスタム内容をデフォルトに戻すこと"""
    import src.prompt_loader as pl
    monkeypatch.setattr(pl, "PROMPTS_DIR", tmp_path)

    # カスタム内容を書く
    (tmp_path / "file_agent.md").write_text("カスタム内容", encoding="utf-8")

    pl.reset_prompt("file_agent")

    content = (tmp_path / "file_agent.md").read_text(encoding="utf-8")
    assert content == DEFAULT_PROMPTS["file_agent"]


# ── テスト7: list_prompts ─────────────────────────────────
def test_list_prompts_returns_all_agents():
    """list_promptsが5エージェント名を返すこと"""
    result = list_prompts()
    assert len(result) == 5
    assert "coder_agent" in result
    assert "search_agent" in result


# ── テスト8: 未知エージェント名でValueError ──────────────────
def test_load_prompt_unknown_agent_raises(tmp_path, monkeypatch):
    """未知のエージェント名でValueErrorが発生すること"""
    import src.prompt_loader as pl
    monkeypatch.setattr(pl, "PROMPTS_DIR", tmp_path)

    with pytest.raises(ValueError, match="Unknown agent"):
        pl.load_prompt("nonexistent_agent")
