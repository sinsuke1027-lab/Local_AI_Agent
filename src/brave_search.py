import subprocess
import json
import os
from typing import List, Dict


class BraveSearch:
    """Brave Search MCPサーバーを直接呼び出すクライアント"""

    def __init__(self):
        with open("mcp_config.json") as f:
            config = json.load(f)
        self.api_key = config["mcpServers"]["brave-search"]["env"]["BRAVE_API_KEY"]

    def search(self, query: str, count: int = 5) -> List[Dict]:
        """Web検索を実行して結果を返す"""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "brave_web_search",
                "arguments": {
                    "query": query,
                    "count": count,
                }
            }
        }

        try:
            proc = subprocess.run(
                ["npx", "-y", "@modelcontextprotocol/server-brave-search"],
                input=json.dumps(request) + "\n",
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "BRAVE_API_KEY": self.api_key},
            )

            for line in proc.stdout.splitlines():
                try:
                    resp = json.loads(line)
                    if "result" in resp:
                        content = resp["result"].get("content", [])
                        for item in content:
                            if item.get("type") == "text":
                                text = item["text"]
                                results = []
                                entries = text.strip().split("\n\n")
                                for entry in entries:
                                    lines = entry.strip().splitlines()
                                    r = {}
                                    for line2 in lines:
                                        if line2.startswith("Title: "):
                                            r["title"] = line2[7:]
                                        elif line2.startswith("Description: "):
                                            r["description"] = line2[13:]
                                        elif line2.startswith("URL: "):
                                            r["url"] = line2[5:]
                                    if r:
                                        results.append(r)
                                return results
                except Exception:
                    continue
            return []

        except Exception as e:
            return []

    def search_summary(self, query: str, count: int = 3) -> str:
        """検索結果をLLMに渡しやすい形式にまとめる"""
        results = self.search(query, count=count)

        if not results:
            return ""

        lines = [f"【Web検索結果：{query}】"]
        for r in results:
            title = r.get("title", "")
            url   = r.get("url", "")
            desc  = r.get("description", "")
            lines.append(f"\n・{title}\n  {desc}\n  URL: {url}")

        return "\n".join(lines)
