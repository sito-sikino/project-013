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


async def common_sequence(
    event_type: str,
    channel: str,
    actor: str,
    payload_summary: str,
    llm_kind: str,
    llm_channel: str,
) -> None:
    """7-2: 共通シーケンス実行（Redis→LLM→Typing→Send→Redis→log_ok）

    Args:
        event_type: イベントタイプ（slash|user_msg|auto_tick|report）
        channel: チャンネル名（command-center|creation|development|lounge）
        actor: アクター（user|spectra|lynq|paz|system）
        payload_summary: ペイロード要約
        llm_kind: LLM種別（reply|auto|report）
        llm_channel: Discord チャンネル ID
    """
    from app import store, supervisor, discord, logger, settings, state

    try:
        # Stage 1: Redis 全文読み
        context_records = store.read_all()
        # Handle both Record objects and dict formats for testing compatibility
        context_lines = []
        for r in context_records:
            if hasattr(r, "agent"):  # Record object
                context_lines.append(f"{r.agent}: {r.text}")
            else:  # dict format (for tests)
                context_lines.append(f"{r['agent']}: {r['text']}")
        context = "\n".join(context_lines)

        # Stage 2: LLM 生成
        current_state = state.get_state()
        task_content = current_state.task.content or "自然な会話を継続"

        # settings から制限値を取得
        limits = {
            "cc": settings.settings.channel_limits.limit_cc,
            "cr": settings.settings.channel_limits.limit_cr,
            "dev": settings.settings.channel_limits.limit_dev,
            "lo": settings.settings.channel_limits.limit_lo,
        }

        # ペルソナとレポート設定（基本実装）
        persona = {"default": "Discord Multi-Agent System"}
        report_config = {"format": "daily", "max_chars": 500}

        result = await supervisor.generate(
            kind=llm_kind,
            channel=llm_channel,
            task=task_content,
            context=context,
            limits=limits,
            persona=persona,
            report_config=report_config,
        )

        # Stage 3: Discord typing
        await discord.typing(result["speaker"], llm_channel)

        # Stage 4: Discord send
        await discord.send(result["speaker"], llm_channel, result["text"])

        # Stage 5: Redis 追記
        store.append(result["speaker"], llm_channel, result["text"])

        # Stage 6: log_ok
        summary_chars = min(len(payload_summary), 15)
        log_summary = f"{llm_kind}:{summary_chars}chars"
        logger.log_ok(event_type, channel, actor, log_summary)

    except Exception as e:
        # Fail-Fast: エラー時は段階に応じたerror_stageでlog_err後SystemExit
        error_stage = "memory"  # デフォルト

        # エラー種別の推定
        error_str = str(e).lower()
        if "redis" in error_str or "store" in error_str:
            error_stage = "memory"
        elif "llm" in error_str or "gemini" in error_str or "generate" in error_str:
            error_stage = "plan"
        elif "typing" in error_str:
            error_stage = "typing"
        elif "send" in error_str or "discord" in error_str:
            error_stage = "send"

        logger.log_err(event_type, channel, actor, payload_summary, error_stage, str(e))
        import sys

        sys.exit(1)


if __name__ == "__main__":
    from app.discord import start_spectra_client

    # 動作確認用メイン関数
    asyncio.run(start_spectra_client())
