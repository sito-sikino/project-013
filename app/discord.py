# Discord Interface - Discord送受信管理
# 受信: discord.py / 送信: httpx REST API

import discord
import httpx
from app.settings import settings
import app.app as app_module


class SpectraDiscordClient(discord.Client):
    """Spectra Bot Discord受信専用クライアント"""

    def __init__(self):
        # メッセージ内容読み取りIntentを有効化
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(intents=intents)

    async def on_ready(self) -> None:
        """Bot起動完了時の処理"""
        if not self.user:
            raise RuntimeError("Discord client failed to initialize user")
        print(f"Spectra Discord Client ready: {self.user}")
        
        # スラッシュコマンド登録
        await self._register_slash_commands()

    async def _register_slash_commands(self) -> None:
        """スラッシュコマンド登録処理"""
        try:
            # /task コマンドの定義
            task_command = {
                "name": "task",
                "description": "タスクのコミットとチャンネル切り替え",
                "options": [
                    {
                        "name": "channel",
                        "description": "切り替え先チャンネル",
                        "type": 3,  # STRING type
                        "required": False,
                        "choices": [
                            {"name": "creation", "value": "creation"},
                            {"name": "development", "value": "development"}
                        ]
                    },
                    {
                        "name": "content",
                        "description": "タスク内容",
                        "type": 3,  # STRING type
                        "required": False
                    }
                ]
            }
            
            # 環境に応じてギルド登録（dev）またはグローバル登録（prod）を選択
            if settings.environment.env == "dev":
                # 開発環境：ギルド登録（即座反映）
                url = f"https://discord.com/api/v10/applications/{self.user.id}/guilds/{settings.discord.guild_id}/commands"
                registration_type = "Guild"
            else:
                # 本番環境：グローバル登録（遅延反映）
                url = f"https://discord.com/api/v10/applications/{self.user.id}/commands"
                registration_type = "Global"
            
            headers = {
                "Authorization": f"Bot {settings.discord.spectra_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=task_command)
                if response.status_code in [200, 201]:
                    print(f"✅ /task スラッシュコマンド登録完了 ({registration_type})")
                else:
                    print(f"❌ スラッシュコマンド登録エラー ({registration_type}): {response.status_code} - {response.text}")
                    
        except Exception as e:
            print(f"❌ スラッシュコマンド登録でエラー: {e}")

    async def on_message(self, message: discord.Message) -> None:
        """メッセージ受信処理"""
        # Bot自身のメッセージは無視
        if message.author.bot:
            return

        # Fail-Fast: 必須フィールド検証
        if not message.content:
            raise ValueError("Message content is empty")
        if not message.channel:
            raise ValueError("Message channel is missing")
        if not message.author:
            raise ValueError("Message author is missing")

        # app.pyのon_userに委譲
        await app_module.on_user(
            channel=str(message.channel.id),
            text=message.content,
            user_id=str(message.author.id),
        )

    async def on_interaction(self, interaction: discord.Interaction) -> None:
        """スラッシュコマンド受信処理"""
        # Fail-Fast: インタラクション検証
        if not interaction.data:
            raise ValueError("Interaction data is missing")

        if interaction.type == discord.InteractionType.application_command:
            command_name = interaction.data.get("name")
            if not command_name:
                raise ValueError("Command name is missing from interaction data")

            if command_name == "task":
                # オプション解析
                options_data = interaction.data.get("options", [])
                options = {}
                if isinstance(options_data, list):
                    for opt in options_data:
                        if isinstance(opt, dict) and "name" in opt and "value" in opt:
                            options[opt["name"]] = opt["value"]

                # app.pyのon_slashに委譲
                await app_module.on_slash(
                    channel=options.get("channel"), content=options.get("content")
                )

                # 即座にレスポンス（最小実装）
                await interaction.response.send_message(
                    "受け付けました", ephemeral=True
                )


async def start_spectra_client() -> None:
    """Spectraクライアント起動"""
    # Fail-Fast: 設定値検証
    if not settings.discord.spectra_token:
        raise ValueError("SPECTRA_TOKEN is not configured")

    client = SpectraDiscordClient()
    await client.start(settings.discord.spectra_token)


def get_bot_token(bot: str) -> str:
    """Bot名からトークンを取得"""
    tokens = {
        "spectra": settings.discord.spectra_token,
        "lynq": settings.discord.lynq_token,
        "paz": settings.discord.paz_token,
    }
    if bot not in tokens:
        raise ValueError(f"Unknown bot: {bot}")
    return tokens[bot]


async def typing(bot: str, channel_id: str) -> int:
    """Discord REST API: typing indicator送信"""
    # Fail-Fast: パラメータ検証
    if not bot:
        raise ValueError("Bot name cannot be empty")
    if not channel_id:
        raise ValueError("Channel ID cannot be empty")

    token = get_bot_token(bot)
    url = f"https://discord.com/api/v10/channels/{channel_id}/typing"
    headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers)
            return response.status_code
    except httpx.RequestError as e:
        raise ValueError(f"Failed to send typing indicator: {e}") from e


async def send(bot: str, channel_id: str, text: str) -> str:
    """Discord REST API: メッセージ送信"""
    # Fail-Fast: パラメータ検証
    if not bot:
        raise ValueError("Bot name cannot be empty")
    if not channel_id:
        raise ValueError("Channel ID cannot be empty")
    if not text:
        raise ValueError("Message text cannot be empty")
    if len(text) > 2000:
        raise ValueError(f"Message text too long: {len(text)} characters (max 2000)")

    token = get_bot_token(bot)
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
    payload = {"content": text}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                data = response.json()
                message_id = data.get("id")
                if not message_id:
                    raise ValueError("Discord API returned empty message ID")
                return message_id
            else:
                raise ValueError(
                    f"Discord API error: {response.status_code} - {response.text}"
                )
    except httpx.RequestError as e:
        raise ValueError(f"Failed to send message: {e}") from e
