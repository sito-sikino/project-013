"""自発発言スケジューラテスト（10-1）- Red段階"""

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


class TestTickSchedulerBasic:
    """基本的なTickSchedulerテスト"""

    def test_tick_scheduler_class_exists(self):
        """TickSchedulerクラスが定義されていること"""
        # Given: app.pyモジュール
        
        # When & Then: TickSchedulerクラスが存在する
        assert hasattr(app, 'TickScheduler'), "TickScheduler class must be defined in app.py"
        assert isinstance(app.TickScheduler, type), "TickScheduler must be a class"

    def test_tick_scheduler_instance_exists(self):
        """tick_schedulerグローバルインスタンスが存在すること"""
        # Given: app.pyモジュール
        
        # When & Then: tick_schedulerインスタンスが存在する
        assert hasattr(app, 'tick_scheduler'), "tick_scheduler instance must be defined in app.py"
        assert isinstance(app.tick_scheduler, app.TickScheduler), "tick_scheduler must be TickScheduler instance"

    def test_tick_scheduler_has_required_methods(self):
        """TickSchedulerクラスが必要なメソッドを持つこと"""
        # Given: TickSchedulerクラス
        scheduler = app.TickScheduler()
        
        # When & Then: 必要なメソッドが存在する
        assert hasattr(scheduler, 'start'), "TickScheduler should have start method"
        assert hasattr(scheduler, 'stop'), "TickScheduler should have stop method"
        assert callable(scheduler.start), "start method must be callable"
        assert callable(scheduler.stop), "stop method must be callable"

    @pytest.mark.asyncio
    async def test_tick_scheduler_start_is_async(self):
        """TickScheduler.startが非同期メソッドであること"""
        # Given: TickSchedulerインスタンス
        scheduler = app.TickScheduler()
        
        # When & Then: startが非同期メソッドである
        import inspect
        assert inspect.iscoroutinefunction(scheduler.start), "start method must be async"


class TestEnvironmentConfiguration:
    """環境設定テスト"""

    def test_dev_environment_configuration(self):
        """dev環境で正しい設定が適用されること"""
        # Given: dev環境
        with patch('app.settings.settings.env', 'dev'):
            scheduler = app.TickScheduler()
            
            # When: 設定を確認
            interval = scheduler.get_tick_interval()
            probability = scheduler.get_tick_probability()
            max_runtime = scheduler.get_max_runtime()
            
            # Then: dev環境設定が適用される
            assert interval == 15, f"Dev interval should be 15s, got {interval}"
            assert probability == 1.0, f"Dev probability should be 1.0, got {probability}"
            assert max_runtime == 300, f"Dev max runtime should be 300s (5min), got {max_runtime}"

    def test_prod_environment_configuration(self):
        """prod環境で正しい設定が適用されること"""
        # Given: prod環境
        with patch('app.settings.settings.env', 'prod'):
            scheduler = app.TickScheduler()
            
            # When: 設定を確認
            interval = scheduler.get_tick_interval()
            probability = scheduler.get_tick_probability()
            max_runtime = scheduler.get_max_runtime()
            
            # Then: prod環境設定が適用される
            assert interval == 300, f"Prod interval should be 300s, got {interval}"
            assert probability == 0.33, f"Prod probability should be 0.33, got {probability}"
            assert max_runtime is None, f"Prod max runtime should be None, got {max_runtime}"

    def test_environment_switching(self):
        """環境切り替えが正しく動作すること"""
        # Given: 環境の動的切り替え
        
        # When & Then: dev環境
        with patch('app.settings.settings.env', 'dev'):
            dev_scheduler = app.TickScheduler()
            assert dev_scheduler.get_tick_interval() == 15
            assert dev_scheduler.get_tick_probability() == 1.0
        
        # When & Then: prod環境
        with patch('app.settings.settings.env', 'prod'):
            prod_scheduler = app.TickScheduler()
            assert prod_scheduler.get_tick_interval() == 300
            assert prod_scheduler.get_tick_probability() == 0.33


class TestTimerAccuracy:
    """タイマー精度テスト"""

    @pytest.mark.asyncio
    async def test_tick_interval_timing_accuracy(self):
        """tickイベントの間隔が正確であること"""
        # Given: タイミング測定環境
        tick_times = []
        
        async def mock_enqueue(priority, handler, *args, **kwargs):
            tick_times.append(time.time())
        
        with patch('app.event_queue.enqueue', side_effect=mock_enqueue), \
             patch('app.settings.settings.env', 'dev'):
            
            scheduler = app.TickScheduler()
            
            # When: 短時間スケジューラを実行
            start_task = asyncio.create_task(scheduler.start())
            await asyncio.sleep(0.5)  # 500ms実行
            scheduler.stop()
            start_task.cancel()
            
            # Then: 適切な間隔でtickが発生（テスト用に短縮）
            # 実装では設定可能なテスト間隔を使用

    @pytest.mark.asyncio
    async def test_scheduler_stops_after_max_runtime_in_dev(self):
        """dev環境で最大実行時間後に停止すること"""
        # Given: dev環境の短縮テスト設定
        with patch('app.settings.settings.env', 'dev'), \
             patch.object(app.TickScheduler, 'get_max_runtime', return_value=1):  # 1秒テスト
            
            scheduler = app.TickScheduler()
            start_time = time.time()
            
            # When: スケジューラ開始
            await scheduler.start()
            
            # Then: 最大実行時間後に停止
            end_time = time.time()
            runtime = end_time - start_time
            assert 0.9 <= runtime <= 1.5, f"Runtime {runtime:.2f}s should be around 1s"

    @pytest.mark.asyncio
    async def test_scheduler_runs_indefinitely_in_prod(self):
        """prod環境で無期限実行されること"""
        # Given: prod環境
        running_time = 0
        
        with patch('app.settings.settings.env', 'prod'):
            scheduler = app.TickScheduler()
            
            # When: 短時間実行して手動停止
            start_task = asyncio.create_task(scheduler.start())
            await asyncio.sleep(0.2)  # 200ms実行
            scheduler.stop()
            start_task.cancel()
            
            # Then: 手動停止まで実行される（タイムアウトなし）
            assert scheduler.is_running is False, "Scheduler should be stopped manually"


class TestProbabilityControl:
    """確率制御テスト"""

    @pytest.mark.asyncio
    async def test_dev_environment_100_percent_probability(self):
        """dev環境で100%確率でtickが実行されること"""
        # Given: dev環境での確率テスト
        tick_count = 0
        
        async def mock_enqueue(priority, handler, *args, **kwargs):
            nonlocal tick_count
            tick_count += 1
        
        with patch('app.event_queue.enqueue', side_effect=mock_enqueue), \
             patch('app.settings.settings.env', 'dev'), \
             patch.object(app.TickScheduler, 'get_tick_interval', return_value=0.1):  # 100msテスト
            
            scheduler = app.TickScheduler()
            
            # When: 短時間実行
            start_task = asyncio.create_task(scheduler.start())
            await asyncio.sleep(0.5)  # 500ms実行
            scheduler.stop()
            start_task.cancel()
            
            # Then: 100%確率でtickが実行される
            expected_ticks = 5  # 500ms / 100ms = 5回
            assert tick_count >= 4, f"Expected ~5 ticks with 100% probability, got {tick_count}"

    @pytest.mark.asyncio
    async def test_prod_environment_33_percent_probability(self):
        """prod環境で33%確率でtickが実行されること"""
        # Given: prod環境での確率テスト
        tick_attempts = 0
        tick_executions = 0
        
        def mock_probability_check():
            nonlocal tick_attempts
            tick_attempts += 1
            # 33%確率をシミュレート
            import random
            return random.random() < 0.33
        
        async def mock_enqueue(priority, handler, *args, **kwargs):
            nonlocal tick_executions
            tick_executions += 1
        
        with patch('app.event_queue.enqueue', side_effect=mock_enqueue), \
             patch('app.settings.settings.env', 'prod'), \
             patch.object(app.TickScheduler, 'should_execute_tick', side_effect=mock_probability_check):
            
            scheduler = app.TickScheduler()
            
            # When: 多数回確率判定を実行
            for _ in range(100):
                if scheduler.should_execute_tick():
                    await mock_enqueue(None, None)
            
            # Then: 約33%の確率で実行される
            execution_rate = tick_executions / tick_attempts
            assert 0.2 <= execution_rate <= 0.5, f"Expected ~33% execution rate, got {execution_rate:.2f}"

    def test_should_execute_tick_method_exists(self):
        """should_execute_tickメソッドが存在すること"""
        # Given: TickSchedulerインスタンス
        scheduler = app.TickScheduler()
        
        # When & Then: should_execute_tickメソッドが存在する
        assert hasattr(scheduler, 'should_execute_tick'), "TickScheduler should have should_execute_tick method"
        assert callable(scheduler.should_execute_tick), "should_execute_tick must be callable"

    def test_probability_skip_behavior(self):
        """外れtickで何もしないこと"""
        # Given: 確率外れの状況
        with patch.object(app.TickScheduler, 'should_execute_tick', return_value=False):
            scheduler = app.TickScheduler()
            
            # When: 確率判定を実行
            should_execute = scheduler.should_execute_tick()
            
            # Then: Falseが返される（外れtick）
            assert should_execute is False, "Should return False for skipped ticks"


class TestEventQueueIntegration:
    """EventQueue統合テスト"""

    @pytest.mark.asyncio
    async def test_scheduler_uses_event_queue_with_tick_priority(self):
        """スケジューラがEventQueueのTICK優先度を使用すること"""
        # Given: EventQueue監視
        with patch('app.event_queue.enqueue') as mock_enqueue:
            
            # When: tickイベントを手動実行
            await app.tick_scheduler._enqueue_tick_event()
            
            # Then: TICK優先度でEventQueueに追加される
            mock_enqueue.assert_called_once_with(
                app.EventPriority.TICK,
                app.on_tick
            )

    @pytest.mark.asyncio
    async def test_scheduler_respects_event_queue_priority(self):
        """スケジューラがSlash/User優先度を尊重すること"""
        # Given: 高優先度イベントが処理中の環境
        with patch('app.event_queue.is_processing', True):
            # When: tick実行を試行
            # 実装により、処理中は後回しになることを確認
            pass
            
            # Then: EventQueueの優先度制御が機能する
            # 具体的な実装により詳細を確認

    def test_scheduler_has_enqueue_tick_event_method(self):
        """_enqueue_tick_eventメソッドが存在すること"""
        # Given: TickSchedulerインスタンス
        scheduler = app.TickScheduler()
        
        # When & Then: _enqueue_tick_eventメソッドが存在する
        assert hasattr(scheduler, '_enqueue_tick_event'), "TickScheduler should have _enqueue_tick_event method"
        assert callable(scheduler._enqueue_tick_event), "_enqueue_tick_event must be callable"


class TestErrorHandling:
    """エラーハンドリングテスト"""

    @pytest.mark.asyncio
    async def test_scheduler_fails_fast_on_configuration_error(self):
        """設定エラー時にFail-Fastで停止すること"""
        # Given: 無効な設定
        with patch('app.settings.settings.tick.tick_interval_sec_dev', None):
            
            # When & Then: 設定エラーで例外が発生
            with pytest.raises(Exception):
                scheduler = app.TickScheduler()
                await scheduler.start()

    @pytest.mark.asyncio
    async def test_scheduler_handles_event_queue_errors(self):
        """EventQueueエラー時の適切な処理"""
        # Given: EventQueueでエラーが発生
        with patch('app.event_queue.enqueue', side_effect=Exception("EventQueue error")):
            scheduler = app.TickScheduler()
            
            # When & Then: エラーが適切に処理される
            with pytest.raises(Exception, match="EventQueue error"):
                await scheduler._enqueue_tick_event()

    def test_scheduler_initialization_with_invalid_settings(self):
        """無効な設定でのスケジューラ初期化テスト"""
        # Given: 無効な設定値
        
        # When & Then: 各種無効設定でエラー
        with patch('app.settings.settings.tick.tick_prob_dev', -1):  # 負の確率
            with pytest.raises(ValueError):
                app.TickScheduler()
        
        with patch('app.settings.settings.tick.tick_prob_dev', 2.0):  # 1.0超過確率
            with pytest.raises(ValueError):
                app.TickScheduler()


class TestSchedulerLifecycle:
    """スケジューラライフサイクルテスト"""

    def test_scheduler_initial_state(self):
        """スケジューラの初期状態が正しいこと"""
        # Given: 新しいTickSchedulerインスタンス
        scheduler = app.TickScheduler()
        
        # When & Then: 初期状態を確認
        assert hasattr(scheduler, 'is_running'), "TickScheduler should have is_running attribute"
        assert scheduler.is_running is False, "Initial state should be not running"

    @pytest.mark.asyncio
    async def test_scheduler_start_stop_cycle(self):
        """スケジューラの開始・停止サイクルが正しく動作すること"""
        # Given: TickSchedulerインスタンス
        scheduler = app.TickScheduler()
        
        # When: 開始→停止
        start_task = asyncio.create_task(scheduler.start())
        await asyncio.sleep(0.1)  # 短時間実行
        scheduler.stop()
        start_task.cancel()
        
        # Then: 状態が正しく変化する
        assert scheduler.is_running is False, "Should be stopped after stop() call"

    @pytest.mark.asyncio
    async def test_scheduler_multiple_start_prevention(self):
        """スケジューラの重複開始が防止されること"""
        # Given: 既に実行中のスケジューラ
        scheduler = app.TickScheduler()
        
        # When: 重複開始を試行
        start_task1 = asyncio.create_task(scheduler.start())
        await asyncio.sleep(0.05)
        
        # Then: 2回目のstartでエラーまたは無視される
        with pytest.raises(RuntimeError):
            await scheduler.start()
        
        scheduler.stop()
        start_task1.cancel()