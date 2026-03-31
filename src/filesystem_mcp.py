import subprocess
import json
import os
from typing import Any


class FilesystemMCP:
    """filesystem MCPサーバーを直接呼び出すクライアント"""

    def __init__(self, allowed_dir: str = None):
        self.allowed_dir = allowed_dir or os.path.expanduser("~/projects")

    def _call(self, tool_name: str, arguments: dict) -> Any:
        """MCPサーバーにリクエストを送る"""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        input_data = json.dumps(request) + "\n"
        npx = (
            "/opt/homebrew/bin/npx"
            if os.path.exists("/opt/homebrew/bin/npx")
            else "npx"
        )
        proc = subprocess.run(
            [npx, "-y", "@modelcontextprotocol/server-filesystem", self.allowed_dir],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=30,
        )
        for line in proc.stdout.splitlines():
            try:
                resp = json.loads(line)
                if "result" in resp:
                    return resp["result"]
            except Exception:
                continue
        return None

    def read_file(self, path: str) -> str:
        result = self._call("read_file", {"path": path})
        if result and "content" in result:
            for item in result["content"]:
                if item.get("type") == "text":
                    return item["text"]
        return ""

    def write_file(self, path: str, content: str) -> bool:
        result = self._call("write_file", {"path": path, "content": content})
        return result is not None

    def create_directory(self, path: str) -> bool:
        result = self._call("create_directory", {"path": path})
        return result is not None

    def list_directory(self, path: str) -> list:
        result = self._call("list_directory", {"path": path})
        if result and "content" in result:
            for item in result["content"]:
                if item.get("type") == "text":
                    return item["text"].splitlines()
        return []