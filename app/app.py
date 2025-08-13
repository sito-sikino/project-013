# Discord Multi-Agent System - Main Application
# メインアプリケーションエントリーポイント

import asyncio
from typing import Optional, Callable
from enum import Enum
from dataclasses import dataclass


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


async def on_tick() -> None:
    """自発発言処理ハンドラ（低優先度）"""
    print("Tick event received - Low priority auto posting")
    # TODO: 本格実装（自発発言・LLM処理等）


async def on_report_0600() -> None:
    """日報処理ハンドラ（特別タイミング）"""
    print("Daily report event received at 06:00")
    # TODO: 本格実装（日報生成・Redis全リセット等）


# 7-1: 優先度制御の基本構造（Slash→User→Tick）
class EventPriority(Enum):
    """イベント優先度定義（数値が小さいほど高優先度）"""

    SLASH = 1  # 最高優先度: スラッシュコマンド
    USER = 2  # 中優先度: ユーザーメッセージ
    TICK = 3  # 低優先度: 自発発言


@dataclass
class EventItem:
    """イベントアイテム定義"""

    priority: EventPriority
    handler: Callable
    args: tuple
    kwargs: dict


class EventQueue:
    """イベント優先度制御キュー（直列処理）"""

    def __init__(self):
        self._queue = asyncio.PriorityQueue()
        self._processing = False

    async def enqueue(
        self, priority: EventPriority, handler: Callable, *args, **kwargs
    ):
        """イベントをキューに追加"""
        # Fail-Fast: パラメータ検証
        if not callable(handler):
            raise ValueError("Handler must be callable")

        item = EventItem(priority, handler, args, kwargs)
        await self._queue.put((priority.value, item))

    async def process_events(self):
        """キュー内イベントを順次処理（直列実行・Fail-Fast）"""
        while True:
            try:
                if self._processing:
                    await asyncio.sleep(0.01)  # 処理中は短時間待機
                    continue

                priority_value, item = await self._queue.get()
                self._processing = True

                # Fail-Fast: 直列実行で例外時は即中断
                await item.handler(*item.args, **item.kwargs)

                self._queue.task_done()
                self._processing = False

            except Exception as e:
                self._processing = False
                # Fail-Fast原則: 例外を再送出して処理中断
                raise ValueError(f"Event processing failed: {e}") from e

    @property
    def is_processing(self) -> bool:
        """処理中状態の確認"""
        return self._processing


# グローバルイベントキュー
event_queue = EventQueue()


if __name__ == "__main__":
    from app.discord import start_spectra_client

    # 動作確認用メイン関数
    asyncio.run(start_spectra_client())
