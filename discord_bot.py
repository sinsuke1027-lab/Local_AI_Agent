import discord
import httpx
import asyncio

# ── 設定 ──────────────────────────────────
import os
DISCORD_TOKEN  = os.getenv("DISCORD_TOKEN")
N8N_WEBHOOK    = "http://localhost:5678/webhook/discord-receive"
# ──────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"Bot起動完了: {client.user}")


@client.event
async def on_message(message):
    # Bot自身のメッセージは無視
    if message.author == client.user:
        return

    # /で始まるコマンドのみ転送
    if not message.content.startswith("/"):
        return

    print(f"コマンド受信: {message.content} from {message.author}")

    # n8n Webhookに転送
    async with httpx.AsyncClient() as http:
        await http.post(
            N8N_WEBHOOK,
            json={
                "content":    message.content,
                "author":     str(message.author),
                "channel_id": str(message.channel.id),
                "message_id": str(message.id),
            },
            timeout=180.0  # LangGraph実行を待つため長めに設定
        )


client.run(DISCORD_TOKEN)