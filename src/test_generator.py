import os
import re
from typing import Optional
from langchain_ollama import ChatOllama


OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_DEFAULT = "qwen2.5-coder:14b"


class TestGenerator:
    """実装コードからpytestテストコードを自動生成する"""

    def __init__(self):
        pass

    def _read_file(self, file_path: str) -> str:
        """ファイルの内容を読み込む"""
        file_path = os.path.expanduser(file_path)
        if not os.path.exists(file_path):
            return ""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def _get_test_path(self, source_path: str) -> str:
        """ソースファイルに対応するテストファイルのパスを返す"""
        source_path = os.path.expanduser(source_path)
        dir_name = os.path.dirname(source_path)
        base_name = os.path.basename(source_path)

        # tests/ ディレクトリがあればそこに配置
        tests_dir = os.path.join(os.path.dirname(dir_name), "tests")
        if os.path.isdir(tests_dir):
            return os.path.join(tests_dir, f"test_{base_name}")

        # なければ同じディレクトリに配置
        return os.path.join(dir_name, f"test_{base_name}")

    def _extract_functions_and_classes(self, code: str) -> str:
        """コードから関数名・クラス名・docstringを抽出してサマリーを返す"""
        lines = []
        for match in re.finditer(
            r'^(class\s+\w+.*?:|def\s+\w+.*?:)\s*\n(\s+""".*?"""|\s+\'\'\'.*?\'\'\')?',
            code,
            re.MULTILINE | re.DOTALL,
        ):
            signature = match.group(1).strip()
            docstring = match.group(2).strip().strip('"""').strip("'''").strip() if match.group(2) else ""
            if docstring:
                lines.append(f"{signature}  # {docstring}")
            else:
                lines.append(signature)
        return "\n".join(lines)

    def generate_test(
        self,
        source_path: str,
        instruction: str = "",
    ) -> Optional[str]:
        """ソースファイルからテストコードを生成する"""
        source_code = self._read_file(source_path)
        if not source_code:
            return None

        model = ChatOllama(model=MODEL_DEFAULT, base_url=OLLAMA_BASE_URL)

        # 関数・クラスのサマリー
        summary = self._extract_functions_and_classes(source_code)

        prompt = (
            "あなたはテストエンジニアです。\n"
            "以下のPythonソースコードに対するpytestテストコードを生成してください。\n\n"
            f"ソースファイル: {source_path}\n\n"
            f"ソースコード:\n```python\n{source_code[:4000]}\n```\n\n"
        )

        if summary:
            prompt += f"関数・クラス一覧:\n{summary}\n\n"

        if instruction:
            prompt += f"追加の指示: {instruction}\n\n"

        prompt += (
            "以下のルールに従ってください:\n"
            "- pytest を使用すること\n"
            "- 各関数に対して正常系・異常系のテストを含めること\n"
            "- テスト関数名は test_ で始めること\n"
            "- 外部依存（API呼び出し、ファイルI/O等）はモック化すること\n"
            "- テストコードのみを出力すること（説明文は不要）\n"
            "- ```python と ``` で囲むこと"
        )

        try:
            response = model.invoke(prompt)
            content = response.content.strip()

            # コードブロックを抽出
            code_match = re.search(r'```python\n([\s\S]*?)```', content)
            if code_match:
                return code_match.group(1).strip()

            # コードブロックがない場合はそのまま返す
            if content.startswith("import") or content.startswith("from") or content.startswith("def test_"):
                return content

            return None

        except Exception:
            return None

    def generate_and_save(
        self,
        source_path: str,
        instruction: str = "",
        output_path: str = None,
    ) -> Optional[str]:
        """テストコードを生成してファイルに保存する"""
        test_code = self.generate_test(source_path, instruction)
        if not test_code:
            return None

        if not output_path:
            output_path = self._get_test_path(source_path)

        output_path = os.path.expanduser(output_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(test_code)

        return output_path

    def generate_for_changed_files(
        self,
        changed_files: list,
        instruction: str = "",
    ) -> list:
        """変更されたファイル群に対してテストを一括生成する"""
        generated = []

        for file_path in changed_files:
            if not file_path.endswith(".py"):
                continue
            # テストファイル自体はスキップ
            if os.path.basename(file_path).startswith("test_"):
                continue
            # __init__.py はスキップ
            if os.path.basename(file_path) == "__init__.py":
                continue

            result = self.generate_and_save(file_path, instruction)
            if result:
                generated.append(result)

        return generated
