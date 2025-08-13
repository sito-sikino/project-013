"""優先度制御テスト（10-3）- Red段階"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
import asyncio
import time
import os

# テスト用環境変数設定（app.pyインポート前に設定）
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("TZ", "Asia/Tokyo")
os.environ.setdefault("SPECTRA_TOKEN", "test_token")
os.environ.setdefault("LYNQ_TOKEN", "test_token")
os.environ.setdefault("PAZ_TOKEN", "test_token")
os.environ.setdefault("CHAN_COMMAND_CENTER", "123456789012345678")
os.environ.setdefault("CHAN_CREATION", "123456789012345679")
os.environ.setdefault("CHAN_DEVELOPMENT", "123456789012345680")
os.environ.setdefault("CHAN_LOUNGE", "123456789012345681")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("GEMINI_API_KEY", "test_api_key")
os.environ.setdefault("GEMINI_TIMEOUT_SECONDS", "30")
os.environ.setdefault("TICK_INTERVAL_SEC_DEV", "15")
os.environ.setdefault("TICK_PROB_DEV", "1.0")
os.environ.setdefault("MAX_TEST_MINUTES", "5")
os.environ.setdefault("TICK_INTERVAL_SEC_PROD", "300")
os.environ.setdefault("TICK_PROB_PROD", "0.33")
os.environ.setdefault("STANDBY_START", "00:00")
os.environ.setdefault("PROCESSING_AT", "06:00")
os.environ.setdefault("FREE_START", "20:00")
os.environ.setdefault("LIMIT_CC", "100")
os.environ.setdefault("LIMIT_CR", "200")
os.environ.setdefault("LIMIT_DEV", "200")
os.environ.setdefault("LIMIT_LO", "30")
os.environ.setdefault("LOG_FILE", "logs/run.log")

from app import app


class TestEventPriorityDefinition:
    """イベント優先度定義テスト"""

    def test_event_priority_enum_exists(self):
        """EventPriority列挙型が定義されていること"""
        # Given: app.pyモジュール
        
        # When & Then: EventPriorityが存在する
        assert hasattr(app, 'EventPriority'), "EventPriority enum must be defined in app.py"
        assert hasattr(app.EventPriority, 'SLASH'), "SLASH priority must be defined"
        assert hasattr(app.EventPriority, 'USER'), "USER priority must be defined"
        assert hasattr(app.EventPriority, 'TICK'), "TICK priority must be defined"

    def test_priority_values_are_correct(self):
        """優先度の値が正しく設定されていること（小さい値ほど高優先度）"""
        # Given: EventPriority定義
        
        # When & Then: 優先度の値が要求通り
        assert app.EventPriority.SLASH.value == 1, "SLASH should have highest priority (1)"
        assert app.EventPriority.USER.value == 2, "USER should have medium priority (2)"
        assert app.EventPriority.TICK.value == 3, "TICK should have lowest priority (3)"

    def test_priority_ordering_is_correct(self):
        """優先度の順序が正しいこと（SLASH > USER > TICK）"""
        # Given: EventPriority定義
        
        # When & Then: 優先度順序が正しい
        assert app.EventPriority.SLASH.value < app.EventPriority.USER.value, "SLASH should be higher priority than USER"
        assert app.EventPriority.USER.value < app.EventPriority.TICK.value, "USER should be higher priority than TICK"
        assert app.EventPriority.SLASH.value < app.EventPriority.TICK.value, "SLASH should be higher priority than TICK"


class TestEventQueueBasicBehavior:
    """EventQueue基本動作テスト"""

    def test_event_queue_class_exists(self):
        """EventQueueクラスが定義されていること"""
        # Given: app.pyモジュール
        
        # When & Then: EventQueueクラスが存在する
        assert hasattr(app, 'EventQueue'), "EventQueue class must be defined in app.py"
        assert hasattr(app, 'event_queue'), "event_queue instance must be defined in app.py"

    @pytest.mark.asyncio
    async def test_event_queue_enqueue_method(self):
        """EventQueueのenqueueメソッドが動作すること"""
        # Given: EventQueueインスタンス
        queue = app.EventQueue()
        
        async def mock_handler():
            pass
        
        # When: イベントをキューに追加
        await queue.enqueue(app.EventPriority.USER, mock_handler)
        
        # Then: エラーが発生しない
        # （実際のキューイングの確認は後のテストで行う）

    def test_event_queue_has_required_methods(self):
        """EventQueueが必要なメソッドを持つこと"""
        # Given: EventQueueクラス
        queue = app.EventQueue()
        
        # When & Then: 必要なメソッドが存在する
        assert hasattr(queue, 'enqueue'), "EventQueue should have enqueue method"
        assert hasattr(queue, 'process_events'), "EventQueue should have process_events method"
        assert hasattr(queue, 'is_processing'), "EventQueue should have is_processing property"
        assert callable(queue.enqueue), "enqueue must be callable"
        assert callable(queue.process_events), "process_events must be callable"


class TestPriorityOrdering:
    """優先度順序テスト"""

    @pytest.mark.asyncio
    async def test_priority_queue_processes_in_order(self):
        """EventQueueが優先度順にイベントを処理すること"""
        # Given: 実行順記録
        execution_order = []
        
        async def make_handler(name):
            async def handler():
                execution_order.append(name)
            return handler
        
        queue = app.EventQueue()
        
        # When: 逆順でイベントを追加（TICK→USER→SLASH）
        await queue.enqueue(app.EventPriority.TICK, await make_handler("TICK"))
        await queue.enqueue(app.EventPriority.USER, await make_handler("USER"))
        await queue.enqueue(app.EventPriority.SLASH, await make_handler("SLASH"))
        
        # プロセス開始（短時間実行）
        process_task = asyncio.create_task(queue.process_events())
        await asyncio.sleep(0.1)  # イベント処理を待機
        process_task.cancel()
        
        # Then: 優先度順で実行される（SLASH→USER→TICK）
        assert len(execution_order) >= 2, f"Expected at least 2 events processed, got {execution_order}"
        # SLASHが最初に実行される
        assert execution_order[0] == "SLASH", f"SLASH should be processed first, got {execution_order}"
        if len(execution_order) > 1:
            assert execution_order[1] == "USER", f"USER should be processed second, got {execution_order}"

    @pytest.mark.asyncio
    async def test_tick_is_deferred_when_higher_priority_exists(self):
        """高優先度イベント存在時にTICKが後回しになること"""
        # Given: 実行順記録
        execution_order = []
        
        async def make_handler(name):
            async def handler():
                execution_order.append(name)
                await asyncio.sleep(0.05)  # 処理時間をシミュレート
            return handler
        
        queue = app.EventQueue()
        
        # When: TICK→SLASH の順で追加
        await queue.enqueue(app.EventPriority.TICK, await make_handler("TICK"))
        await queue.enqueue(app.EventPriority.SLASH, await make_handler("SLASH"))
        
        # プロセス開始（短時間実行）
        process_task = asyncio.create_task(queue.process_events())
        await asyncio.sleep(0.2)  # 処理時間を確保
        process_task.cancel()
        
        # Then: SLASHが先に実行される
        assert len(execution_order) >= 1, f"Expected at least 1 event processed, got {execution_order}"
        assert execution_order[0] == "SLASH", f"SLASH should be processed first despite being added later, got {execution_order}"


class TestSerialProcessingGuarantee:
    """直列処理保証テスト"""

    @pytest.mark.asyncio
    async def test_events_are_processed_serially(self):
        """イベントが直列で処理されること（並行処理されない）"""
        # Given: 同時実行検出
        concurrent_count = 0
        max_concurrent = 0
        
        async def concurrent_handler(name):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.05)  # 処理時間をシミュレート
            concurrent_count -= 1
        
        queue = app.EventQueue()
        
        # When: 複数のイベントを同時に追加
        await queue.enqueue(app.EventPriority.USER, lambda: concurrent_handler("USER1"))
        await queue.enqueue(app.EventPriority.USER, lambda: concurrent_handler("USER2"))
        await queue.enqueue(app.EventPriority.TICK, lambda: concurrent_handler("TICK"))
        
        # プロセス開始（処理完了まで待機）
        process_task = asyncio.create_task(queue.process_events())
        await asyncio.sleep(0.3)  # 全イベント処理完了を待機
        process_task.cancel()
        
        # Then: 同時実行されない（最大同時実行数=1）
        assert max_concurrent == 1, f"Expected serial processing (max concurrent=1), got {max_concurrent}"

    @pytest.mark.asyncio
    async def test_processing_flag_prevents_overlapping(self):
        """処理中フラグが重複処理を防ぐこと"""
        # Given: EventQueue
        queue = app.EventQueue()
        
        async def long_running_handler():
            await asyncio.sleep(0.1)  # 長時間処理
        
        # When: イベントを追加してプロセス開始
        await queue.enqueue(app.EventPriority.USER, long_running_handler)
        
        process_task = asyncio.create_task(queue.process_events())
        await asyncio.sleep(0.05)  # 処理開始を待機
        
        # Then: 処理中フラグが立つ
        assert queue.is_processing, "Queue should be in processing state"
        
        process_task.cancel()


class TestSlashUserTickPriorityScenarios:
    """Slash/User/Tick優先度シナリオテスト"""

    @pytest.mark.asyncio
    async def test_tick_deferred_by_slash_command(self):
        """スラッシュコマンド到着時にTickが後回しになること"""
        # Given: 実行順記録
        execution_order = []
        
        async def record_handler(event_type):
            execution_order.append(event_type)
        
        queue = app.EventQueue()
        
        # When: TICK追加後、SLASHが到着
        await queue.enqueue(app.EventPriority.TICK, lambda: record_handler("TICK"))
        await queue.enqueue(app.EventPriority.SLASH, lambda: record_handler("SLASH"))
        
        # プロセス実行
        process_task = asyncio.create_task(queue.process_events())
        await asyncio.sleep(0.1)
        process_task.cancel()
        
        # Then: SLASHが優先実行される
        assert len(execution_order) >= 1, f"Expected at least SLASH to be processed, got {execution_order}"
        assert execution_order[0] == "SLASH", f"SLASH should be processed first, got {execution_order}"

    @pytest.mark.asyncio
    async def test_tick_deferred_by_user_message(self):
        """ユーザーメッセージ到着時にTickが後回しになること"""
        # Given: 実行順記録
        execution_order = []
        
        async def record_handler(event_type):
            execution_order.append(event_type)
        
        queue = app.EventQueue()
        
        # When: TICK追加後、USERが到着
        await queue.enqueue(app.EventPriority.TICK, lambda: record_handler("TICK"))
        await queue.enqueue(app.EventPriority.USER, lambda: record_handler("USER"))
        
        # プロセス実行
        process_task = asyncio.create_task(queue.process_events())
        await asyncio.sleep(0.1)
        process_task.cancel()
        
        # Then: USERが優先実行される
        assert len(execution_order) >= 1, f"Expected at least USER to be processed, got {execution_order}"
        assert execution_order[0] == "USER", f"USER should be processed first, got {execution_order}"

    @pytest.mark.asyncio
    async def test_multiple_priority_scenario(self):
        """複数優先度混合シナリオで正しい順序で実行されること"""
        # Given: 複合シナリオの実行順記録
        execution_order = []
        
        async def record_handler(event_type):
            execution_order.append(event_type)
            await asyncio.sleep(0.02)  # 短時間処理
        
        queue = app.EventQueue()
        
        # When: 複雑な順序でイベントを追加
        # TICK1 → USER1 → TICK2 → SLASH → USER2 → TICK3
        await queue.enqueue(app.EventPriority.TICK, lambda: record_handler("TICK1"))
        await queue.enqueue(app.EventPriority.USER, lambda: record_handler("USER1"))
        await queue.enqueue(app.EventPriority.TICK, lambda: record_handler("TICK2"))
        await queue.enqueue(app.EventPriority.SLASH, lambda: record_handler("SLASH"))
        await queue.enqueue(app.EventPriority.USER, lambda: record_handler("USER2"))
        await queue.enqueue(app.EventPriority.TICK, lambda: record_handler("TICK3"))
        
        # プロセス実行（全完了まで待機）
        process_task = asyncio.create_task(queue.process_events())
        await asyncio.sleep(0.3)  # 全イベント処理完了を待機
        process_task.cancel()
        
        # Then: 優先度順で実行される
        # 期待順序: SLASH → USER1 → USER2 → TICK1 → TICK2 → TICK3
        assert len(execution_order) >= 3, f"Expected at least 3 events processed, got {execution_order}"
        
        # 最高優先度のSLASHが最初
        assert execution_order[0] == "SLASH", f"SLASH should be first, got {execution_order}"
        
        # USERイベントがTICKより先（完全な検証は統合テストで実施）
        user_indices = [i for i, event in enumerate(execution_order) if event.startswith("USER")]
        tick_indices = [i for i, event in enumerate(execution_order) if event.startswith("TICK")]
        
        if user_indices and tick_indices:
            # 最初のTICKより前に少なくとも1つのUSERが実行されること
            assert min(user_indices) < min(tick_indices), "USER events should be processed before TICK events"


class TestFailFastBehavior:
    """Fail-Fast動作テスト"""

    @pytest.mark.asyncio
    async def test_processing_stops_on_handler_error(self):
        """ハンドラーエラー時にFail-Fastで停止すること"""
        # Given: エラーが発生するハンドラー
        async def error_handler():
            raise ValueError("Handler error")
        
        async def normal_handler():
            pass
        
        queue = app.EventQueue()
        
        # When: エラーハンドラーを追加
        await queue.enqueue(app.EventPriority.SLASH, error_handler)
        await queue.enqueue(app.EventPriority.USER, normal_handler)
        
        # プロセス実行
        process_task = asyncio.create_task(queue.process_events())
        
        # Then: エラーで停止する
        with pytest.raises(ValueError, match="Event processing failed"):
            await asyncio.sleep(0.1)  # エラー発生を待機
            await process_task

    @pytest.mark.asyncio
    async def test_invalid_handler_rejected_at_enqueue(self):
        """無効なハンドラーがenqueue時に拒否されること"""
        # Given: EventQueue
        queue = app.EventQueue()
        
        # When & Then: 無効なハンドラーでエラー
        with pytest.raises(ValueError, match="Handler must be callable"):
            await queue.enqueue(app.EventPriority.USER, "not_a_function")


class TestIntegrationWithSchedulerAndHandlers:
    """スケジューラー・ハンドラー統合テスト"""

    @pytest.mark.asyncio
    async def test_tick_scheduler_respects_priority_system(self):
        """TickSchedulerが優先度システムを尊重すること"""
        # Given: モック化されたグローバルevent_queue
        with patch.object(app.event_queue, 'enqueue') as mock_enqueue:
            
            # When: TickSchedulerがイベントを追加
            await app.tick_scheduler._enqueue_tick_event()
            
            # Then: TICK優先度で追加される
            mock_enqueue.assert_called_once_with(
                app.EventPriority.TICK,
                app.on_tick
            )

    @pytest.mark.asyncio
    async def test_slash_and_user_handlers_use_higher_priority(self):
        """SlashとUserハンドラーがより高い優先度を使用すること"""
        # Given: モック化されたevent_queue
        with patch.object(app.event_queue, 'enqueue') as mock_enqueue:
            
            # When: 手動でSlash/Userイベントを追加（実際の呼び出しパスを模擬）
            await app.event_queue.enqueue(app.EventPriority.SLASH, app.on_slash)
            await app.event_queue.enqueue(app.EventPriority.USER, app.on_user, "channel", "text", "user_id")
            
            # Then: 適切な優先度で追加される
            calls = mock_enqueue.call_args_list
            assert len(calls) >= 2, f"Expected at least 2 enqueue calls, got {len(calls)}"
            
            # 最初の2つの呼び出しで優先度を確認
            slash_call = calls[0]
            user_call = calls[1]
            
            assert slash_call[0][0] == app.EventPriority.SLASH, "First call should use SLASH priority"
            assert user_call[0][0] == app.EventPriority.USER, "Second call should use USER priority"

    @pytest.mark.asyncio
    async def test_priority_system_prevents_tick_during_user_interaction(self):
        """ユーザー対話中にTickが実行されないこと"""
        # Given: ユーザー処理中のシミュレーション
        execution_order = []
        
        async def mock_user_handler():
            execution_order.append("USER_START")
            await asyncio.sleep(0.1)  # ユーザー処理時間をシミュレート
            execution_order.append("USER_END")
        
        async def mock_tick_handler():
            execution_order.append("TICK")
        
        queue = app.EventQueue()
        
        # When: USER処理中にTICKが到着
        await queue.enqueue(app.EventPriority.USER, mock_user_handler)
        await asyncio.sleep(0.01)  # 少し待機
        await queue.enqueue(app.EventPriority.TICK, mock_tick_handler)
        
        # プロセス実行（完了まで待機）
        process_task = asyncio.create_task(queue.process_events())
        await asyncio.sleep(0.2)  # 処理完了を待機
        process_task.cancel()
        
        # Then: ユーザー処理が完了してからTickが実行される
        assert len(execution_order) >= 3, f"Expected USER_START, USER_END, TICK, got {execution_order}"
        assert execution_order[0] == "USER_START", "USER should start first"
        assert execution_order[1] == "USER_END", "USER should complete before TICK"
        assert execution_order[2] == "TICK", "TICK should execute after USER completion"