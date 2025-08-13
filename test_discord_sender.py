"""Discord送信機能テスト（5-2）- Red段階"""

import pytest
from unittest.mock import MagicMock, patch
from app.discord import typing, send


class TestDiscordSender:
    """Discord送信機能のテスト"""

    @pytest.mark.asyncio
    async def test_typing_returns_success_status(self):
        """typing機能が2xxステータスを返すこと"""
        # Given: モックされたhttpxレスポンス
        mock_response = MagicMock()
        mock_response.status_code = 204

        # When: typing APIを呼び出す
        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            status_code = await typing(bot="spectra", channel_id="123456789")

        # Then: 2xxステータスが返る
        assert status_code == 204
        mock_post.assert_called_once()
        # Discord API typing endpoint の確認
        call_args = mock_post.call_args
        assert "typing" in str(call_args)

    @pytest.mark.asyncio
    async def test_send_returns_message_id(self):
        """send機能がmessage_idを返すこと"""
        # Given: モックされたhttpxレスポンス（メッセージ送信成功）
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "message_123456"}

        # When: send APIを呼び出す
        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            message_id = await send(
                bot="lynq", channel_id="987654321", text="Hello World"
            )

        # Then: message_idが返る
        assert message_id == "message_123456"
        mock_post.assert_called_once()
        # Discord API messages endpoint の確認
        call_args = mock_post.call_args
        assert "messages" in str(call_args)

    @pytest.mark.asyncio
    async def test_typing_uses_correct_bot_token(self):
        """typing機能が正しいBotトークンを使用すること"""
        # Given: モックされたhttpxレスポンス
        mock_response = MagicMock()
        mock_response.status_code = 204

        # When: 異なるBotでtyping APIを呼び出す
        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            await typing(bot="paz", channel_id="555666777")

        # Then: PAZ Botのトークンがヘッダーに設定される
        call_args = mock_post.call_args
        headers = call_args.kwargs.get("headers", {})
        # 実装後に具体的なトークンチェックを追加予定
        assert "Authorization" in headers

    @pytest.mark.asyncio
    async def test_send_uses_correct_message_payload(self):
        """send機能が正しいメッセージペイロードを送信すること"""
        # Given: モックされたhttpxレスポンス
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "msg_999"}

        # When: send APIを呼び出す
        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            await send(bot="spectra", channel_id="111222333", text="Test message")

        # Then: 正しいJSONペイロードが送信される
        call_args = mock_post.call_args
        json_data = call_args.kwargs.get("json", {})
        assert json_data.get("content") == "Test message"
