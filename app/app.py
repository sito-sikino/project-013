# Discord Multi-Agent System - Main Application
# メインアプリケーションエントリーポイント

import asyncio
import time
from typing import Optional, Callable, Union
from enum import Enum
from dataclasses import dataclass


def get_channel_name_from_id(channel_id: str) -> str:
    """Discord チャンネルIDを論理チャンネル名にマッピング
    
    Args:
        channel_id: Discord チャンネルID
        
    Returns:
        str: 論理チャンネル名 (command-center|creation|development|lounge|unknown)
    """
    from app import settings
    
    channel_mapping = {
        settings.settings.discord.chan_command_center: "command-center",
        settings.settings.discord.chan_creation: "creation",
        settings.settings.discord.chan_development: "development", 
        settings.settings.discord.chan_lounge: "lounge"
    }
    return channel_mapping.get(channel_id, "unknown")


def select_typing_bot(channel_name: str, text: str) -> str:
    """即時Typing用の簡単なボット選択
    
    Args:
        channel_name: 論理チャンネル名
        text: ユーザーメッセージ
        
    Returns:
        str: 選択されたボット名 (spectra|lynq|paz)
    """
    # チャンネル基準の簡単な選択ルール（LLMによる最終選択は後で実行）
    channel_bot_preference = {
        "command-center": "spectra",  # 汎用・管理系
        "creation": "paz",           # 創作系
        "development": "lynq",       # 開発系
        "lounge": "spectra",         # 雑談系
        "unknown": "spectra"         # デフォルト
    }
    return channel_bot_preference.get(channel_name, "spectra")


async def on_user(channel: str, text: str, user_id: str) -> None:
    """ユーザーメッセージ受信ハンドラ"""
    # Fail-Fast: 必須パラメータ検証
    if not channel:
        raise ValueError("Channel ID cannot be empty")
    if not text:
        raise ValueError("Message text cannot be empty")
    if not user_id:
        raise ValueError("User ID cannot be empty")

    from app import store, discord
    
    # チャンネルIDを論理チャンネル名にマッピング
    channel_name = get_channel_name_from_id(channel)
    
    # 即時Typing表示（体感速度向上）
    typing_bot = select_typing_bot(channel_name, text)
    await discord.typing(typing_bot, channel)
    
    # ユーザーメッセージをRedisに格納
    store.append("user", channel_name, text)
    
    # 共通シーケンスで応答（選定Bot名義・Typing→Send→Redis追記）
    payload_summary = text[:80]  # 80文字以内に切り詰め
    await common_sequence(
        event_type="user_msg",
        channel=channel_name, 
        actor="user",
        payload_summary=payload_summary,
        llm_kind="reply",
        llm_channel=channel
    )


async def on_slash(
    channel: Optional[str] = None, content: Optional[str] = None
) -> None:
    """スラッシュコマンド受信ハンドラ"""
    # 8-2: execute_slash_commandに委譲
    await execute_slash_command(channel, content)


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


class TickScheduler:
    """自発発言スケジューラ（10-1：dev=15s/100%・prod=300s/33%・確率制御）"""

    def __init__(self):
        """スケジューラ初期化"""
        self.is_running = False
        self._task = None
        self._start_time = None
        
        # 設定値をバリデーション（Fail-Fast）
        self._validate_settings()

    def _validate_settings(self):
        """設定値検証（Fail-Fast原則）"""
        from app import settings
        
        prob_dev = settings.settings.tick.tick_prob_dev
        prob_prod = settings.settings.tick.tick_prob_prod
        
        if not (0.0 <= prob_dev <= 1.0):
            raise ValueError(f"Invalid tick_prob_dev: {prob_dev}. Must be 0.0-1.0")
        if not (0.0 <= prob_prod <= 1.0):
            raise ValueError(f"Invalid tick_prob_prod: {prob_prod}. Must be 0.0-1.0")

    def get_tick_interval(self) -> int:
        """環境別tick間隔取得"""
        from app import settings
        
        if settings.settings.env == "dev":
            return settings.settings.tick.tick_interval_sec_dev
        else:
            return settings.settings.tick.tick_interval_sec_prod

    def get_tick_probability(self) -> float:
        """環境別tick確率取得"""
        from app import settings
        
        if settings.settings.env == "dev":
            return settings.settings.tick.tick_prob_dev
        else:
            return settings.settings.tick.tick_prob_prod

    def get_max_runtime(self) -> Optional[int]:
        """最大実行時間取得（dev環境のみ）"""
        from app import settings
        
        if settings.settings.env == "dev":
            return settings.settings.tick.max_test_minutes * 60  # 分→秒変換
        else:
            return None  # prod環境は無制限

    def should_execute_tick(self) -> bool:
        """確率判定でtick実行可否を決定"""
        import random
        probability = self.get_tick_probability()
        return random.random() < probability

    async def _enqueue_tick_event(self):
        """EventQueueにtickイベントを追加"""
        await event_queue.enqueue(EventPriority.TICK, on_tick)

    async def start(self):
        """スケジューラ開始"""
        if self.is_running:
            raise RuntimeError("TickScheduler is already running")
        
        self.is_running = True
        self._start_time = time.time()
        
        try:
            await self._run_loop()
        finally:
            self.is_running = False

    async def _run_loop(self):
        """メインスケジューリングループ"""
        import time
        
        interval = self.get_tick_interval()
        max_runtime = self.get_max_runtime()
        
        while self.is_running:
            # dev環境での最大実行時間チェック
            if max_runtime and self._start_time:
                elapsed = time.time() - self._start_time
                if elapsed >= max_runtime:
                    break
            
            # 確率判定
            if self.should_execute_tick():
                await self._enqueue_tick_event()
            
            # 次のtickまで待機
            await asyncio.sleep(interval)

    def stop(self):
        """スケジューラ停止"""
        self.is_running = False


# グローバルスケジューラインスタンス
tick_scheduler = TickScheduler()


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


def parse_slash_command(
    channel: Optional[str] = None, content: Optional[str] = None
) -> dict:
    """8-1: Slashコマンドパース/バリデーション

    Args:
        channel: チャンネル名（creation|development）
        content: タスク内容（文字列）

    Returns:
        dict: {"channel": str|None, "content": str|None}

    Raises:
        ValueError: バリデーション失敗時（Fail-Fast）
    """
    # Fail-Fast: 少なくとも一方は必須
    if channel is None and content is None:
        raise ValueError("At least one of channel or content must be provided")

    # Fail-Fast: channelバリデーション
    if channel is not None:
        if not isinstance(channel, str) or channel == "":
            raise ValueError("Invalid channel: must be non-empty string")
        if channel not in ["creation", "development"]:
            raise ValueError(
                f"Invalid channel: {channel}. Must be 'creation' or 'development'"
            )

    # Fail-Fast: contentバリデーション
    if content is not None:
        if not isinstance(content, str):
            raise ValueError("Content must be a string or None")
        if content == "":
            raise ValueError("Content cannot be empty string")

    return {"channel": channel, "content": content}


async def execute_slash_command(
    channel: Optional[str] = None, content: Optional[str] = None
) -> None:
    """8-2: Slashコマンド実行（状態更新/決定通知）

    Args:
        channel: チャンネル名（creation|development|None）
        content: タスク内容（文字列|None）

    処理フロー:
        1. バリデーション（parse_slash_command使用）
        2. 状態更新（task + active_channel即座上書き）
        3. 決定通知（command-centerにSpectra名義）
        4. Redis追記（ユーザー入力記録）
        5. ログ記録（log_ok）

    Raises:
        SystemExit: エラー時（Fail-Fast）
    """
    from app import state, store, logger, settings

    try:
        # 1. バリデーション
        parsed = parse_slash_command(channel, content)
        validated_channel = parsed["channel"]
        validated_content = parsed["content"]

        # 2. 状態更新
        state.update_task(content=validated_content, channel=validated_channel)
        if validated_channel is not None:
            # 即座上書き
            state.set_active_channel(validated_channel)

        # 3. 決定通知用のペイロード作成
        if validated_channel and validated_content:
            notification_text = f"タスク決定: [{validated_channel}] {validated_content}"
        elif validated_channel:
            notification_text = f"チャンネル切替: {validated_channel}"
        elif validated_content:
            notification_text = f"タスク更新: {validated_content}"
        else:
            notification_text = "設定更新"

        # 4. Redis追記（ユーザー入力）
        user_input_summary = f"channel={validated_channel}, content={validated_content}"
        store.append("user", "command-center", f"/task commit {user_input_summary}")

        # 5. 決定通知（command-centerにSpectra名義）
        await common_sequence(
            event_type="slash",
            channel="command-center",
            actor="spectra",
            payload_summary=notification_text,
            llm_kind="reply",
            llm_channel=settings.settings.discord.chan_command_center,
        )

        # 6. 成功ログ
        logger.log_ok("slash", "command-center", "spectra", "slash_execution_completed")

    except Exception as e:
        # Fail-Fast: エラー時はlog_err後SystemExit
        error_stage = "slash"  # Slashコマンド実行段階

        # エラー種別の推定
        error_str = str(e).lower()
        if "invalid" in error_str or "validation" in error_str:
            error_stage = "slash"
        elif "state" in error_str:
            error_stage = "slash"
        elif "redis" in error_str or "store" in error_str:
            error_stage = "memory"
        elif "common_sequence" in error_str or "notification" in error_str:
            error_stage = "send"

        logger.log_err(
            "slash",
            "command-center",
            "spectra",
            f"channel={channel}, content={content}",
            error_stage,
            str(e),
        )
        import sys

        sys.exit(1)


if __name__ == "__main__":
    from app.discord import start_spectra_client

    # 動作確認用メイン関数
    asyncio.run(start_spectra_client())
