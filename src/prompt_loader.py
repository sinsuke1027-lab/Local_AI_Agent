"""
prompt_loader.py — P10b: プロンプト外部化

prompts/*.md からエージェントのプロンプトを読み込み、
変数を埋め込んで返す。ファイルが無い場合はDEFAULT_PROMPTSを使用し
自動生成する。

使い方:
    from src.prompt_loader import render_prompt
    prompt = render_prompt("coder_agent", instruction="...", ...)

CLI:
    python -m src.prompt_loader list
    python -m src.prompt_loader init
    python -m src.prompt_loader show coder_agent
    python -m src.prompt_loader reset coder_agent
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

DEFAULT_PROMPTS: dict[str, str] = {
    "coder_agent": """あなたは優秀なAIソフトウェアエンジニアです。
以下のタスクを実行してください。

タスク：{instruction}
{context_section}
{constitution_section}
{error_feedback}
{memory_feedback}
{success_patterns_section}
{debate_feedback_section}
【指示】
タスクの目的を的確に判断し、以下のルールに従って回答してください。
1. 「調査」「要約」「説明」のみを求めているタスクの場合：
   コードは一切記述せず、分かりやすいテキストだけで結果をまとめてください。
2. 「作成」「実装」「テスト」「スクリプト」などを求めているタスクの場合：
   実装方針を説明した上で、必ずPythonで実装コードを出力してください。
   また、pytest等の実行が必要な場合は、必ず「CMD: pytest ファイル名」の形式で記述してください。
3. Web検索やブラウザ取得結果がある場合は、その情報を最大限活用してください。
4. 既存コードがある場合はそのスタイルに合わせてください。""",

    "reviewer_agent": """あなたはシニアエンジニアです。
以下のタスクと実装結果をレビューしてください。

タスク：{instruction}

実装結果：
{result}
{constitution_section}

以下の基準で評価してください：
1. タスクの要件を満たしているか
2. コードに明らかなバグや問題がないか
3. 基本的な品質基準を満たしているか
4. 憲法（コーディング規約・セキュリティルール）に違反していないか

最初の行に必ず以下のどちらかだけを記載してください：
APPROVED（承認）またはREJECTED（却下）

2行目以降にレビューコメントを記載してください。""",

    "file_agent": """あなたはファイル操作の専門家です。
タスクと実装内容を元に、実際にファイルを作成してください。

タスク：{instruction}

実装内容：
{result}

プロジェクトディレクトリ：{project_dir}

必ず以下の形式でファイルを指定してください（この形式以外は使わないこと）：
FILE: {project_dir}/ファイル名
```python
ファイルの内容
```

複数ファイルがある場合は繰り返してください。
FILE:の行は必ず絶対パスで記述してください。""",

    "bash_agent": """あなたはbash実行の専門家です。
タスクと実装内容を元に、必要なbashコマンドを指定してください。

タスク：{instruction}

実装内容：
{result}

プロジェクトディレクトリ：{project_dir}

実行すべきコマンドを以下の形式で指定してください：
CMD: コマンド（pip install・git init・pytest など）

注意：
・source activate は不要です（自動で仮想環境を使います）
・python/pipのパスは自動で仮想環境のものに変換されます
・mkdir は不要です（自動で作成されます）
・アプリの起動コマンドは含めないでください""",

    "search_agent": """以下のタスクに必要なWeb検索クエリを1〜3個生成してください。
タスク：{instruction}

検索クエリのみを1行ずつ出力してください。説明は不要です。""",
}


def load_prompt(agent_name: str) -> str:
    """プロンプトをファイルから読み込む。ファイルが無い場合はデフォルトを自動生成して返す。"""
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    prompt_file = PROMPTS_DIR / f"{agent_name}.md"

    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")

    default = DEFAULT_PROMPTS.get(agent_name)
    if default is None:
        raise ValueError(f"Unknown agent: {agent_name}")

    prompt_file.write_text(default, encoding="utf-8")
    return default


def render_prompt(agent_name: str, **kwargs) -> str:
    """プロンプトを読み込み、変数を埋め込んで返す。
    空セクションによる連続空行（3行以上）を1行に圧縮する。
    """
    import re
    template = load_prompt(agent_name)
    rendered = template.format(**kwargs)
    # 3行以上の連続空行を1行に圧縮（空セクションの積み重なりを防ぐ）
    return re.sub(r'\n{3,}', '\n\n', rendered)


def list_prompts() -> list[str]:
    """利用可能なエージェント名のリストを返す。"""
    return list(DEFAULT_PROMPTS.keys())


def reset_prompt(agent_name: str) -> str:
    """プロンプトファイルをデフォルトにリセットする。"""
    default = DEFAULT_PROMPTS.get(agent_name)
    if default is None:
        raise ValueError(f"Unknown agent: {agent_name}")

    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    prompt_file = PROMPTS_DIR / f"{agent_name}.md"
    prompt_file.write_text(default, encoding="utf-8")
    return default


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prompt Loader CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="利用可能なエージェント一覧")
    sub.add_parser("init", help="全プロンプトファイルを初期化")

    show_p = sub.add_parser("show", help="プロンプトを表示")
    show_p.add_argument("agent", help="エージェント名")

    reset_p = sub.add_parser("reset", help="プロンプトをデフォルトにリセット")
    reset_p.add_argument("agent", help="エージェント名")

    args = parser.parse_args()

    if args.command == "list":
        for name in list_prompts():
            prompt_file = PROMPTS_DIR / f"{name}.md"
            status = "✅" if prompt_file.exists() else "⬜"
            print(f"  {status} {name}")
    elif args.command == "init":
        PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
        for name, content in DEFAULT_PROMPTS.items():
            path = PROMPTS_DIR / f"{name}.md"
            path.write_text(content, encoding="utf-8")
            print(f"  Created: {path}")
    elif args.command == "show":
        print(load_prompt(args.agent))
    elif args.command == "reset":
        reset_prompt(args.agent)
        print(f"  Reset: prompts/{args.agent}.md")
    else:
        parser.print_help()
