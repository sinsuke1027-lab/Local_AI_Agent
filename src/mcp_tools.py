import asyncio
import json
from langchain_mcp_adapters.client import MultiServerMCPClient


def get_mcp_client():
    """MCPクライアントを返す"""
    with open("mcp_config.json") as f:
        config = json.load(f)

    return MultiServerMCPClient(config["mcpServers"])


async def get_mcp_tools():
    """MCP toolsを取得して返す"""
    async with get_mcp_client() as client:
        return client.get_tools()