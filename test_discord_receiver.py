"""Discord受信機能テスト（5-1）- Red段階"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from app.discord import SpectraDiscordClient


class TestDiscordReceiver:
    """Discord受信機能のテスト"""

    @pytest.mark.asyncio
    async def test_on_message_calls_on_user(self):
        """メッセージ受信時にapp.on_userが呼ばれること"""
        # Given: モックされたメッセージとクライアント
        mock_message = MagicMock()
        mock_message.author.bot = False
        mock_message.channel.id = "123456789"
        mock_message.content = "テストメッセージ"
        mock_message.author.id = "user123"

        client = SpectraDiscordClient()

        # When: on_messageが呼ばれる
        with patch("app.app.on_user") as mock_on_user:
            await client.on_message(mock_message)

        # Then: on_userが正しい引数で呼ばれる
        mock_on_user.assert_called_once_with(
            channel="123456789", text="テストメッセージ", user_id="user123"
        )

    @pytest.mark.asyncio
    async def test_slash_task_commit_calls_on_slash(self):
        """スラッシュコマンド受信時にapp.on_slashが呼ばれること"""
        # Given: モックされたInteractionとクライアント
        mock_interaction = MagicMock()
        mock_interaction.type = discord.InteractionType.application_command
        mock_interaction.data = {
            "name": "task",
            "options": [
                {"name": "channel", "value": "development"},
                {"name": "content", "value": "タスク内容"},
            ],
        }
        mock_interaction.response.send_message = AsyncMock()

        client = SpectraDiscordClient()

        # When: スラッシュコマンドが呼ばれる
        with patch("app.app.on_slash") as mock_on_slash:
            await client.on_interaction(mock_interaction)

        # Then: on_slashが正しい引数で呼ばれる
        mock_on_slash.assert_called_once_with(
            channel="development", content="タスク内容"
        )

    def test_client_initialization_with_intents(self):
        """Clientが正しいIntentで初期化されること"""
        # When: クライアントを初期化
        client = SpectraDiscordClient()

        # Then: メッセージ内容を読むIntentが有効（現在は未実装でFalse）
        assert client.intents.message_content is True  # 失敗するはず
        assert client.intents.guilds is True
