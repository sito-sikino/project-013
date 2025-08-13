# Discord Multi-Agent System - Main Application
# メインアプリケーションエントリーポイント

import asyncio
import time
from typing import Optional, Callable, Union, Any, Tuple
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta, date, time as datetime_time


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


def get_channel_id_from_name(channel_name: str) -> str:
    """論理チャンネル名をDiscord IDにマッピング
    
    Args:
        channel_name: 論理チャンネル名
        
    Returns:
        str: Discord チャンネルID
    """
    from app import settings
    
    channel_mapping = {
        "command-center": settings.settings.discord.chan_command_center,
        "creation": settings.settings.discord.chan_creation,
        "development": settings.settings.discord.chan_development,
        "lounge": settings.settings.discord.chan_lounge
    }
    return channel_mapping.get(channel_name, settings.settings.discord.chan_command_center)


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
    from app import state
    
    # active_channelに自発発言投稿（10-2: 選定Bot名義・Typing→Send・LLM1回・Redis追記・log_ok）
    active_channel = state.get_active_channel()
    channel_id = get_channel_id_from_name(active_channel)
    payload_summary = f"auto_tick:{active_channel}"
    
    await common_sequence(
        event_type="auto_tick",
        channel=active_channel,
        actor="system",
        payload_summary=payload_summary,
        llm_kind="auto",
        llm_channel=channel_id
    )


async def on_report_0600() -> None:
    """日報処理ハンドラ（11-2：06:00特別タイミング）
    
    毎日JST 06:00に実行される日報生成・投稿・システムリセット処理。
    以下の順序で処理を実行します：
    
    1. common_sequence経由でSpectra固定・500字以内の日報をcommand-centerに投稿
    2. 投稿成功後にRedis全文脈をリセット
    3. システム状態をACTIVEモード・command-centerアクティブに設定
    
    Features:
        - Spectra固定投稿（Bot選択なし）
        - LLM1回実行（500字制限内）
        - Fail-Fast原則（エラー時は即座停止）
        - 送信成功後の確実なリセット処理
    
    Raises:
        Exception: common_sequence実行時のエラー（Fail-Fast原則で即座停止）
        SystemExit: store.reset()またはstate操作での致命的エラー
        
    Note:
        このハンドラはTask 11-1のDailyReportSchedulerから呼び出されます。
        エラー時はFail-Fast原則により、後続のリセット処理は実行されません。
    """
    from app import store, state, settings, logger
    
    try:
        # Stage 1: 日報生成・投稿（common_sequenceでSpectra固定・command-center）
        # Fail-Fast: common_sequenceでのエラーは例外として伝播し、後続処理は実行しない
        await common_sequence(
            event_type="report",
            channel="command-center",
            actor="spectra",
            payload_summary="daily_report_0600",
            llm_kind="report",
            llm_channel=settings.settings.discord.chan_command_center
        )
        
        # Stage 2: 全文脈リセット（日報送信成功後のみ実行）
        # Fail-Fast: store.reset()でのエラーはSystemExitで即座停止
        store.reset()
        
        # Stage 3: 状態更新（mode=ACTIVE・active_channel=command-center）
        # Fail-Fast: state操作でのエラーは例外として伝播
        from app.state import Mode
        state.update_mode(Mode.ACTIVE)
        state.set_active_channel("command-center")
        
    except Exception as e:
        # Fail-Fast: 日報関連エラーは全てerror_stage='report'で記録後SystemExit
        logger.log_err(
            event_type="report",
            channel="command-center", 
            actor="spectra",
            payload_summary="daily_report_0600",
            error_stage="report",
            error_detail=str(e)
        )
        import sys
        sys.exit(1)


# 7-1: 優先度制御の基本構造（Slash→User→Tick）
class EventPriority(Enum):
    """イベント優先度定義（数値が小さいほど高優先度）"""

    SLASH = 1  # 最高優先度: スラッシュコマンド
    USER = 2  # 中優先度: ユーザーメッセージ
    TICK = 3  # 低優先度: 自発発言


@dataclass
class EventItem:
    """イベントアイテム定義
    
    優先度キューで使用するイベント情報を格納します。
    優先度での比較をサポートし、同じ優先度の場合は安定ソートを提供します。
    """

    priority: EventPriority
    handler: Callable[..., Any]
    args: Tuple[Any, ...]
    kwargs: dict[str, Any]
    
    def __lt__(self, other: 'EventItem') -> bool:
        """優先度での比較（同じ優先度の場合はオブジェクトIDで比較）
        
        Args:
            other: 比較対象のEventItem
            
        Returns:
            bool: 自身が他方より高優先度（小さい値）の場合True
            
        Note:
            同じ優先度の場合はオブジェクトIDで比較し、安定的な順序を保証します。
        """
        if not isinstance(other, EventItem):
            return NotImplemented
        if self.priority != other.priority:
            return self.priority.value < other.priority.value
        # 同じ優先度の場合はオブジェクトIDで比較（安定的な順序保証）
        return id(self) < id(other)


class EventQueue:
    """イベント優先度制御キュー（直列処理）
    
    Slash（最高）→ User（中）→ Tick（低）の優先度でイベントを管理し、
    直列処理を保証する非同期キューシステムです。
    
    Features:
        - 優先度付きキューによる順序制御
        - 直列実行保証（同時実行なし）
        - Fail-Fast原則（エラー時即中断）
    """

    def __init__(self) -> None:
        """EventQueue初期化
        
        内部的にasyncio.PriorityQueueを使用し、
        処理中フラグで直列実行を制御します。
        """
        self._queue: asyncio.PriorityQueue[Tuple[int, EventItem]] = asyncio.PriorityQueue()
        self._processing: bool = False

    async def enqueue(
        self, priority: EventPriority, handler: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> None:
        """イベントをキューに追加
        
        Args:
            priority: イベント優先度（EventPriority）
            handler: 実行するハンドラー関数
            *args: ハンドラーに渡す位置引数
            **kwargs: ハンドラーに渡すキーワード引数
            
        Raises:
            ValueError: handlerがcallableでない場合
        """
        # Fail-Fast: パラメータ検証
        if not callable(handler):
            raise ValueError("Handler must be callable")

        item = EventItem(priority, handler, args, kwargs)
        await self._queue.put((priority.value, item))

    async def process_events(self) -> None:
        """キュー内イベントを順次処理（直列実行・Fail-Fast）
        
        無限ループでキューからイベントを取得し、優先度順に直列実行します。
        処理中は他のイベントをブロックし、エラー時はFail-Fast原則で即座に中断します。
        
        Raises:
            ValueError: イベント処理中にエラーが発生した場合
        """
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
        
        prob_dev = settings.settings.tick.prob_dev
        prob_prod = settings.settings.tick.prob_prod
        
        if not (0.0 <= prob_dev <= 1.0):
            raise ValueError(f"Invalid tick_prob_dev: {prob_dev}. Must be 0.0-1.0")
        if not (0.0 <= prob_prod <= 1.0):
            raise ValueError(f"Invalid tick_prob_prod: {prob_prod}. Must be 0.0-1.0")

    def get_tick_interval(self) -> int:
        """環境別tick間隔取得"""
        from app import settings
        
        if settings.settings.environment.env == "dev":
            return settings.settings.tick.interval_sec_dev
        else:
            return settings.settings.tick.interval_sec_prod

    def get_tick_probability(self) -> float:
        """環境別tick確率取得"""
        from app import settings
        
        if settings.settings.environment.env == "dev":
            return settings.settings.tick.prob_dev
        else:
            return settings.settings.tick.prob_prod

    def get_max_runtime(self) -> Optional[int]:
        """最大実行時間取得（dev環境のみ）"""
        from app import settings
        
        if settings.settings.environment.env == "dev":
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


class DailyReportScheduler:
    """日報スケジューラ（11-1：JST 06:00に1日1回のみ実行）
    
    毎日JST 06:00に1回だけ日報を生成する機能を提供します。
    システム起動が06:00後の場合はバックフィル無し（スキップ）で動作し、
    同日内の重複実行を防止する仕組みを持ちます。
    
    Features:
        - JST（Asia/Tokyo）タイムゾーン対応
        - 1日1回のみ実行保証（重複実行防止）
        - バックフィル無し（06:00後起動時はスキップ）
        - Fail-Fast原則（エラー時即中断）
        - 1分間隔での監視ループ
    """
    
    def __init__(self) -> None:
        """DailyReportScheduler初期化
        
        システム起動時刻を記録し、JST時間での動作準備を行います。
        """
        self.is_running: bool = False
        self._last_execution_date: Optional[str] = None  # YYYY-MM-DD形式
        self._startup_time: datetime = datetime.now(timezone(timedelta(hours=9)))  # JST
        self._task: Optional[asyncio.Task] = None
        
    def get_current_jst_time(self) -> datetime:
        """現在のJST時間を取得
        
        Returns:
            datetime: JST（UTC+9）タイムゾーンでの現在時刻
        """
        return datetime.now(timezone(timedelta(hours=9)))
    
    def get_report_time(self) -> datetime_time:
        """設定からレポート時刻（06:00）を取得
        
        PROCESSING_AT環境変数から日報実行時刻を読み込みます。
        
        Returns:
            datetime_time: 日報実行時刻（通常は06:00）
            
        Raises:
            ValueError: 時刻フォーマットが不正な場合
        """
        from app import settings
        
        processing_time_str = settings.settings.schedule.processing_at  # "06:00"
        hour, minute = map(int, processing_time_str.split(":"))
        return datetime_time(hour, minute)
    
    def should_trigger_report(self) -> bool:
        """日報トリガーが必要かどうか判定
        
        以下の条件をすべて満たす場合のみTrueを返します：
        1. 現在時刻が設定時刻（06:00）と一致
        2. システム起動時刻が設定時刻以前（バックフィル無し原則）
        3. 同日内でまだ実行されていない（重複実行防止）
        
        Returns:
            bool: 日報実行が必要な場合True、そうでなければFalse
        """
        current_jst = self.get_current_jst_time()
        report_time = self.get_report_time()
        
        # 06:00丁度でなければトリガーしない
        if not (current_jst.hour == report_time.hour and current_jst.minute == report_time.minute):
            return False
            
        # 起動時間が06:00後の場合はスキップ（バックフィル無し）
        if self._is_after_report_time():
            return False
            
        # 同日に既に実行済みの場合はスキップ
        current_date_str = current_jst.date().strftime("%Y-%m-%d")
        if self._last_execution_date == current_date_str:
            return False
            
        return True
    
    def _is_after_report_time(self) -> bool:
        """システム起動時刻がレポート時刻（06:00）後かどうか判定
        
        バックフィル無し原則により、システム起動が06:00後の場合は
        その日の日報生成をスキップします。
        
        Returns:
            bool: 起動時刻が日報時刻より後の場合True
        """
        startup_time = self._startup_time.time()
        report_time = self.get_report_time()
        
        # 起動時刻が06:00以降の場合は後回し（バックフィル無し）
        return startup_time > report_time
    
    def _mark_execution_completed(self, execution_date: date) -> None:
        """実行完了マーキング
        
        指定された日付での日報実行完了を記録し、重複実行を防止します。
        
        Args:
            execution_date: 実行完了日（date型）
        """
        self._last_execution_date = execution_date.strftime("%Y-%m-%d")
    
    async def _execute_daily_report(self) -> None:
        """日報実行処理（on_report_0600呼び出し）
        
        実際の日報生成処理を実行し、完了後に実行済みマーキングを行います。
        
        Raises:
            Exception: on_report_0600実行でエラーが発生した場合（Fail-Fast）
        """
        await on_report_0600()
        self._mark_execution_completed(self.get_current_jst_time().date())
    
    async def _monitoring_iteration(self) -> None:
        """監視イテレーション（1回分）
        
        トリガー条件をチェックし、必要に応じて日報実行を行います。
        1分間隔の監視ループから呼び出されます。
        """
        if self.should_trigger_report():
            await self._execute_daily_report()
    
    async def start(self) -> None:
        """スケジューラ開始（監視ループ）
        
        1分間隔でトリガー条件を監視し、06:00になった際に日報を実行します。
        すでに動作中の場合はエラーとなります。
        
        Raises:
            RuntimeError: 既にスケジューラが動作中の場合
        """
        if self.is_running:
            raise RuntimeError("DailyReportScheduler is already running")
        
        self.is_running = True
        
        try:
            # 1分間隔で監視（06:00判定のため）
            while self.is_running:
                await self._monitoring_iteration()
                await asyncio.sleep(60)  # 1分待機
        finally:
            self.is_running = False
    
    def stop(self) -> None:
        """スケジューラ停止
        
        監視ループを停止します。現在実行中の日報処理は完了を待ちません。
        """
        self.is_running = False


# グローバル日報スケジューラインスタンス
daily_report_scheduler = DailyReportScheduler()


async def common_sequence(
    event_type: str,
    channel: str,
    actor: str,
    payload_summary: str,
    llm_kind: str,
    llm_channel: str,
) -> None:
    """7-2: 共通シーケンス実行（Redis→LLM→Typing→Send→Redis→log_ok）
    
    Discord Multi-Agent Systemの中核処理シーケンス。
    Redis全文脈読み取り → LLM生成 → Discord投稿 → Redis追記の流れで実行し、
    各段階でのエラーはFail-Fast原則で即座停止します。

    Args:
        event_type: イベントタイプ（slash|user_msg|auto_tick|report）
        channel: チャンネル名（command-center|creation|development|lounge）
        actor: アクター（user|spectra|lynq|paz|system）
        payload_summary: ペイロード要約
        llm_kind: LLM種別（reply|auto|report）
        llm_channel: Discord チャンネル ID
        
    Raises:
        SystemExit: 任意の段階でエラーが発生した場合（Fail-Fast原則）
        
    Error Stages:
        - memory: Redis/store関連エラー（Stage 1, 5）
        - plan: LLM生成エラー（Stage 2）
        - typing: Discord typing エラー（Stage 3）
        - send: Discord send エラー（Stage 4）
    """
    from app import store, supervisor, discord, logger, settings, state
    from app.error_stages import determine_error_stage

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
        error_stage = determine_error_stage(e, "common_sequence")

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
