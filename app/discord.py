# Discord Interface - Discord送受信管理
# 受信: discord.py / 送信: httpx REST API

import discord
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
