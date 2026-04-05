"""
template_loader.py — タスクテンプレートの読み込み・変数展開

templates/*.md（フロントマター + 指示文本文）を扱う。
"""

import re
from pathlib import Path
from typing import Any

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """
    --- で囲まれた YAML フロントマターを解析して (meta, body) を返す。
    PyYAML が使えない場合は簡易パーサーで処理する。
    """
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not match:
        return {}, text

    raw_yaml, body = match.group(1), match.group(2)

    try:
        import yaml
        meta = yaml.safe_load(raw_yaml) or {}
    except Exception:
        meta = _simple_yaml_parse(raw_yaml)

    return meta, body.strip()


def _simple_yaml_parse(text: str) -> dict[str, Any]:
    """PyYAML 非依存の簡易 YAML パーサー（スカラー + リスト + 1段ネスト対応）"""
    result: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list | None = None
    current_map: dict | None = None

    for line in text.splitlines():
        # トップレベルのキー
        top = re.match(r"^(\w+):\s*(.*)", line)
        if top and not line.startswith(" "):
            if current_key and current_list is not None:
                result[current_key] = current_list
            elif current_key and current_map is not None:
                if current_map:
                    result.setdefault(current_key, []).append(current_map)

            current_key = top.group(1)
            val = top.group(2).strip()
            current_list = None
            current_map = None

            if val:
                result[current_key] = val
            else:
                current_list = []
            continue

        # リスト要素 - name: ...
        list_item = re.match(r"^\s+-\s+(\w+):\s*(.*)", line)
        if list_item and current_key:
            key, val = list_item.group(1), list_item.group(2).strip()
            if current_map is None:
                if current_list and current_map is not None:
                    current_list.append(current_map)
                current_map = {}
            current_map[key] = val
            continue

        # シンプルリスト要素 - value
        simple_item = re.match(r"^\s+-\s+(.*)", line)
        if simple_item and current_key and current_list is not None and current_map is None:
            current_list.append(simple_item.group(1).strip())
            continue

        # ネストされたキー（インデント付き）
        nested = re.match(r"^\s+(\w+):\s*(.*)", line)
        if nested and current_map is not None:
            current_map[nested.group(1)] = nested.group(2).strip()

    # 末尾の flush
    if current_key:
        if current_map is not None and current_map:
            result.setdefault(current_key, []).append(current_map)
        elif current_list is not None:
            result[current_key] = current_list

    return result


def list_templates() -> list[dict]:
    """
    利用可能なテンプレート一覧を返す。

    Returns:
        [{"id": str, "title": str, "description": str, "tags": list[str]}]
    """
    if not TEMPLATES_DIR.exists():
        return []

    templates = []
    for path in sorted(TEMPLATES_DIR.glob("*.md")):
        if path.name == "README.md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
            meta, _ = _parse_frontmatter(text)
            templates.append({
                "id":          path.stem,
                "title":       meta.get("title", path.stem),
                "description": meta.get("description", ""),
                "tags":        meta.get("tags", []),
            })
        except Exception:
            pass

    return templates


def load_template(template_id: str) -> dict:
    """
    テンプレートを読み込んでフロントマターと本文を返す。

    Returns:
        {
            "id":          str,
            "title":       str,
            "description": str,
            "variables":   [{"name": str, "description": str, "default": str}],
            "tags":        list[str],
            "body":        str   # 変数未展開の本文
        }
    """
    path = TEMPLATES_DIR / f"{template_id}.md"
    if not path.exists():
        raise FileNotFoundError(f"テンプレートが見つかりません: {template_id}")

    text = path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)

    # variables を正規化
    raw_vars = meta.get("variables", [])
    variables = []
    for v in raw_vars:
        if isinstance(v, dict):
            variables.append({
                "name":        v.get("name", ""),
                "description": v.get("description", ""),
                "default":     v.get("default", ""),
            })

    return {
        "id":          template_id,
        "title":       meta.get("title", template_id),
        "description": meta.get("description", ""),
        "variables":   variables,
        "tags":        meta.get("tags", []),
        "body":        body,
    }


def render_template(template_id: str, variables: dict[str, str]) -> str:
    """
    テンプレートに変数を展開して完成した指示文を返す。

    Args:
        template_id: テンプレートID（ファイル名の stem）
        variables:   {"FEATURE_NAME": "CSV出力機能", ...}

    Returns:
        変数展開済みの指示文文字列。未入力変数は空文字で展開する。
    """
    tmpl = load_template(template_id)
    body = tmpl["body"]

    for key, value in variables.items():
        body = body.replace(f"{{{{{key}}}}}", value)

    # 残っている未展開変数を空文字に
    body = re.sub(r"\{\{[A-Z_]+\}\}", "", body)

    return body
