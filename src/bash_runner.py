import subprocess
import os
from typing import Tuple, Dict


class BashRunner:
    """安全なbashコマンド実行クライアント"""

    ALLOWED_COMMANDS = [
        "python", "python3", "pip", "pip3",
        "npm", "node", "npx",
        "git", "mkdir", "ls", "cat", "echo",
        "pytest", "uvicorn", "which", "pwd",
        "touch", "cp", "mv", "rm",
        "brew", "curl", "find", "grep",
        "flask", "bash", "sh", "playwright"
    ]

    def __init__(self, work_dir: str = None):
        self.work_dir = work_dir or os.path.expanduser("~/projects")

    def is_safe(self, command: str) -> bool:
        """コマンドが安全かチェック"""
        # バッククォートと&&を除去して最初のコマンドを取得
        cmd = command.strip().strip("`").split("&&")[0].strip()
        first_word = cmd.split()[0].split("/")[-1] if cmd.split() else ""
        return first_word in self.ALLOWED_COMMANDS

    def run(self, command: str, cwd: str = None) -> Tuple[bool, str, str]:
        """コマンドを実行する。Returns: (success, stdout, stderr)"""
        if cwd:
            cwd = os.path.expanduser(cwd)
        command = command.replace("~/", os.path.expanduser("~/"))

        if not self.is_safe(command):
            return False, "", f"許可されていないコマンドです: {command}"

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=cwd or self.work_dir,
            )
            return (
                result.returncode == 0,
                result.stdout,
                result.stderr,
            )
        except subprocess.TimeoutExpired:
            return False, "", "タイムアウトしました（120秒）"
        except Exception as e:
            return False, "", str(e)

    def setup_venv(self, project_dir: str) -> Dict[str, str]:
        """仮想環境を作成してパスを返す"""
        project_dir = os.path.expanduser(project_dir)
        venv_dir    = os.path.join(project_dir, ".venv")

        # プロジェクトフォルダ作成
        os.makedirs(project_dir, exist_ok=True)

        # 仮想環境が存在しない場合のみ作成
        if not os.path.exists(venv_dir):
            self.run(f"python3 -m venv {venv_dir}")

        return {
            "python": os.path.join(venv_dir, "bin", "python3"),
            "pip":    os.path.join(venv_dir, "bin", "pip"),
            "venv":   venv_dir,
        }

    def resolve_command(self, command: str, venv_paths: Dict[str, str]) -> str:
        """pip/pythonコマンドを仮想環境のパスに置き換える"""
        cmd = command.strip()

        # pip install → .venv/bin/pip install
        if cmd.startswith("pip install") or cmd.startswith("pip3 install"):
            return cmd.replace("pip3 ", venv_paths["pip"] + " ") \
                      .replace("pip ", venv_paths["pip"] + " ", 1)

        # python xxx.py → .venv/bin/python3 xxx.py
        if cmd.startswith("python ") or cmd.startswith("python3 "):
            return cmd.replace("python3 ", venv_paths["python"] + " ") \
                      .replace("python ", venv_paths["python"] + " ", 1)

        # pytest → .venv/bin/pytest
        if cmd.startswith("pytest"):
            pytest_path = os.path.join(venv_paths["venv"], "bin", "pytest")
            return cmd.replace("pytest", pytest_path, 1)

        return cmd

    def check_syntax(self, file_path: str, venv_paths: Dict[str, str]) -> Tuple[bool, str]:
        """Pythonファイルの構文チェック"""
        file_path = os.path.expanduser(file_path)
        success, stdout, stderr = self.run(
            f"{venv_paths['python']} -m py_compile {file_path}"
        )
        return success, stderr