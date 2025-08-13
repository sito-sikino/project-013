# Discord Multi-Agent System - Main Application
# メインアプリケーションエントリーポイント

from typing import Optional


async def on_user(channel: str, text: str, user_id: str) -> None:
    """ユーザーメッセージ受信ハンドラ"""
    # Fail-Fast: 必須パラメータ検証
    if not channel:
        raise ValueError("Channel ID cannot be empty")
    if not text:
        raise ValueError("Message text cannot be empty")
    if not user_id:
        raise ValueError("User ID cannot be empty")

    print(f"User message received - Channel: {channel}, User: {user_id}, Text: {text}")
    # TODO: 本格実装（LLM処理・応答等）


async def on_slash(
    channel: Optional[str] = None, content: Optional[str] = None
) -> None:
    """スラッシュコマンド受信ハンドラ"""
    # Fail-Fast: コマンド必須パラメータ検証
    if not channel and not content:
        raise ValueError("Slash command requires at least channel or content parameter")

    print(f"Slash command received - Channel: {channel}, Content: {content}")
    # TODO: 本格実装（タスク更新・状態変更等）


if __name__ == "__main__":
    import asyncio
    from app.discord import start_spectra_client

    # 動作確認用メイン関数
    asyncio.run(start_spectra_client())
