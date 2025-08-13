"""日報トリガーテスト（11-1）- Red段階"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
import asyncio
import time
from datetime import datetime, timezone, timedelta
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


class TestDailyReportTriggerBasic:
    """日報トリガー基本機能テスト"""

    def test_daily_report_scheduler_class_exists(self):
        """DailyReportSchedulerクラスが定義されていること"""
        # Given: app.pyモジュール
        
        # When & Then: DailyReportSchedulerクラスが存在する
        assert hasattr(app, 'DailyReportScheduler'), "DailyReportScheduler class must be defined in app.py"
        assert isinstance(app.DailyReportScheduler, type), "DailyReportScheduler must be a class"

    def test_daily_report_scheduler_instance_exists(self):
        """daily_report_schedulerグローバルインスタンスが存在すること"""
        # Given: app.pyモジュール
        
        # When & Then: daily_report_schedulerインスタンスが存在する
        assert hasattr(app, 'daily_report_scheduler'), "daily_report_scheduler instance must be defined in app.py"
        assert isinstance(app.daily_report_scheduler, app.DailyReportScheduler), "daily_report_scheduler must be DailyReportScheduler instance"

    def test_daily_report_scheduler_has_required_methods(self):
        """DailyReportSchedulerクラスが必要なメソッドを持つこと"""
        # Given: DailyReportSchedulerクラス
        scheduler = app.DailyReportScheduler()
        
        # When & Then: 必要なメソッドが存在する
        assert hasattr(scheduler, 'should_trigger_report'), "DailyReportScheduler should have should_trigger_report method"
        assert hasattr(scheduler, 'start'), "DailyReportScheduler should have start method"
        assert hasattr(scheduler, 'stop'), "DailyReportScheduler should have stop method"
        assert callable(scheduler.should_trigger_report), "should_trigger_report method must be callable"
        assert callable(scheduler.start), "start method must be callable"
        assert callable(scheduler.stop), "stop method must be callable"

    @pytest.mark.asyncio
    async def test_daily_report_scheduler_start_is_async(self):
        """DailyReportScheduler.startが非同期メソッドであること"""
        # Given: DailyReportSchedulerインスタンス
        scheduler = app.DailyReportScheduler()
        
        # When & Then: startが非同期メソッドである
        import inspect
        assert inspect.iscoroutinefunction(scheduler.start), "start method must be async"


class TestJSTTimeManagement:
    """JST時間管理テスト"""

    def test_jst_time_calculation(self):
        """JST時間の正しい計算ができること"""
        # Given: JST時間計算機能
        scheduler = app.DailyReportScheduler()
        
        # When & Then: JST時間取得メソッドが存在する
        assert hasattr(scheduler, 'get_current_jst_time'), "DailyReportScheduler should have get_current_jst_time method"
        assert callable(scheduler.get_current_jst_time), "get_current_jst_time must be callable"
    
    def test_report_time_parsing(self):
        """06:00設定時刻の正しい解析ができること"""
        # Given: DailyReportSchedulerインスタンス
        scheduler = app.DailyReportScheduler()
        
        # When: 設定からreport時刻を取得
        report_time = scheduler.get_report_time()
        
        # Then: 06:00が正しく取得される
        assert report_time.hour == 6, f"Report time hour should be 6, got {report_time.hour}"
        assert report_time.minute == 0, f"Report time minute should be 0, got {report_time.minute}"

    def test_jst_timezone_handling(self):
        """JST（Asia/Tokyo）タイムゾーンが正しく処理されること"""
        # Given: DailyReportSchedulerインスタンス
        scheduler = app.DailyReportScheduler()
        
        # When: 現在のJST時間を取得
        jst_time = scheduler.get_current_jst_time()
        
        # Then: JST（+09:00）タイムゾーンである
        expected_tz_offset = timedelta(hours=9)
        assert jst_time.utcoffset() == expected_tz_offset, "Time should be in JST (UTC+9)"


class TestDailyTriggerLogic:
    """1日1回トリガーロジックテスト"""

    @pytest.mark.asyncio 
    async def test_trigger_only_once_per_day(self):
        """1日1回のみトリガーが実行されること"""
        # Given: 同日の複数回実行テスト
        scheduler = app.DailyReportScheduler()
        trigger_count = 0
        
        async def mock_report_handler():
            nonlocal trigger_count
            trigger_count += 1
        
        with patch.object(scheduler, '_execute_daily_report', side_effect=mock_report_handler):
            # When: 06:00時刻で複数回should_trigger_reportを呼び出し
            # 最初の呼び出し
            with patch.object(scheduler, 'get_current_jst_time') as mock_time:
                mock_time.return_value = datetime(2025, 8, 13, 6, 0, 0, tzinfo=timezone(timedelta(hours=9)))
                should_trigger_1 = scheduler.should_trigger_report()
                if should_trigger_1:
                    await scheduler._execute_daily_report()
                
                # 同日の2回目の呼び出し（同じ06:00）
                should_trigger_2 = scheduler.should_trigger_report()
                if should_trigger_2:
                    await scheduler._execute_daily_report()
            
            # Then: 1日1回のみ実行される
            assert trigger_count <= 1, f"Daily report should trigger only once per day, got {trigger_count} times"

    def test_trigger_at_exact_0600_time(self):
        """正確に06:00でのみトリガーが発生すること"""
        # Given: 異なる時刻でのテスト
        test_times = [
            (5, 59),  # 06:00前
            (6, 0),   # 正確に06:00
            (6, 1),   # 06:00後
            (6, 30),  # 06:30
            (7, 0),   # 07:00
        ]
        
        for hour, minute in test_times:
            # 新しいスケジューラーインスタンスを作成（起動時間リセットのため）
            scheduler = app.DailyReportScheduler()
            
            with patch.object(scheduler, 'get_current_jst_time') as mock_current_time, \
                 patch.object(scheduler, '_is_after_report_time', return_value=False):  # バックフィル無効化を一時停止
                
                # When: 各時刻でトリガー判定
                mock_current_time.return_value = datetime(2025, 8, 13, hour, minute, 0, tzinfo=timezone(timedelta(hours=9)))
                should_trigger = scheduler.should_trigger_report()
                
                # Then: 06:00のみでトリガー
                if hour == 6 and minute == 0:
                    assert should_trigger, f"Should trigger at 06:00, but didn't"
                else:
                    assert not should_trigger, f"Should not trigger at {hour:02d}:{minute:02d}, but did"

    def test_no_backfill_after_startup(self):
        """起動時刻が06:00後の場合はスキップされること（バックフィル無し）"""
        # Given: 06:00後の起動シナリオ
        scheduler = app.DailyReportScheduler()
        
        late_startup_times = [
            (6, 30),   # 06:30起動
            (8, 0),    # 08:00起動
            (12, 0),   # 12:00起動
            (18, 0),   # 18:00起動
        ]
        
        for hour, minute in late_startup_times:
            with patch.object(scheduler, 'get_current_jst_time') as mock_time:
                # When: 06:00後の時刻で起動
                mock_time.return_value = datetime(2025, 8, 13, hour, minute, 0, tzinfo=timezone(timedelta(hours=9)))
                should_trigger = scheduler.should_trigger_report()
                
                # Then: トリガーされない（バックフィル無し）
                assert not should_trigger, f"Should not backfill report when starting at {hour:02d}:{minute:02d}, but did"


class TestReportExecutionTracking:
    """日報実行追跡テスト"""

    def test_execution_state_tracking(self):
        """日報実行状態の追跡機能があること"""
        # Given: DailyReportSchedulerインスタンス
        scheduler = app.DailyReportScheduler()
        
        # When & Then: 実行状態追跡メソッドが存在する
        assert hasattr(scheduler, '_last_execution_date'), "Scheduler should track last execution date"
        assert hasattr(scheduler, '_mark_execution_completed'), "Scheduler should have _mark_execution_completed method"
        assert callable(scheduler._mark_execution_completed), "_mark_execution_completed must be callable"

    @pytest.mark.asyncio
    async def test_execution_marking_prevents_duplicate_runs(self):
        """実行マーキングが重複実行を防ぐこと"""
        # Given: DailyReportSchedulerインスタンス
        scheduler = app.DailyReportScheduler()
        execution_count = 0
        
        async def mock_report_handler():
            nonlocal execution_count
            execution_count += 1
        
        with patch.object(scheduler, '_execute_daily_report', side_effect=mock_report_handler):
            # When: 06:00時刻で実行マーキングテスト
            current_date = datetime(2025, 8, 13, 6, 0, 0, tzinfo=timezone(timedelta(hours=9)))
            
            with patch.object(scheduler, 'get_current_jst_time', return_value=current_date), \
                 patch.object(scheduler, '_is_after_report_time', return_value=False):  # バックフィル無効化を一時停止
                
                # 最初の実行
                if scheduler.should_trigger_report():
                    await scheduler._execute_daily_report()
                    scheduler._mark_execution_completed(current_date.date())
                
                # 同日の2回目の試行
                if scheduler.should_trigger_report():
                    await scheduler._execute_daily_report()
            
            # Then: 重複実行されない
            assert execution_count == 1, f"Should execute only once per day, got {execution_count} times"


class TestSchedulerIntegration:
    """スケジューラー統合テスト"""

    @pytest.mark.asyncio
    async def test_daily_report_scheduler_calls_on_report_0600(self):
        """DailyReportSchedulerがon_report_0600を呼び出すこと"""
        # Given: モック化されたon_report_0600
        with patch('app.app.on_report_0600') as mock_on_report:
            scheduler = app.DailyReportScheduler()
            
            # When: 日報実行メソッドを呼び出し
            await scheduler._execute_daily_report()
            
            # Then: on_report_0600が呼ばれる
            mock_on_report.assert_called_once()

    @pytest.mark.asyncio
    async def test_scheduler_respects_system_startup_time(self):
        """スケジューラーがシステム起動時間を考慮すること"""
        # Given: 起動時間追跡機能
        scheduler = app.DailyReportScheduler()
        
        # When & Then: 起動時間関連メソッドが存在する
        assert hasattr(scheduler, '_startup_time'), "Scheduler should track startup time"
        assert hasattr(scheduler, '_is_after_report_time'), "Scheduler should check if current time is after report time"
        assert callable(scheduler._is_after_report_time), "_is_after_report_time must be callable"

    def test_scheduler_lifecycle_management(self):
        """スケジューラーのライフサイクル管理ができること"""
        # Given: DailyReportSchedulerインスタンス
        scheduler = app.DailyReportScheduler()
        
        # When & Then: ライフサイクル管理機能が存在する
        assert hasattr(scheduler, 'is_running'), "Scheduler should have is_running state"
        assert hasattr(scheduler, 'start'), "Scheduler should have start method"
        assert hasattr(scheduler, 'stop'), "Scheduler should have stop method"
        
        # 初期状態は停止
        assert scheduler.is_running is False, "Initial state should be stopped"

    @pytest.mark.asyncio
    async def test_scheduler_monitoring_loop(self):
        """スケジューラー監視ループが正しく動作すること"""
        # Given: 監視ループのテスト
        scheduler = app.DailyReportScheduler()
        loop_iterations = 0
        
        async def mock_monitoring_iteration():
            nonlocal loop_iterations
            loop_iterations += 1
            if loop_iterations >= 3:  # 3回で停止
                scheduler.stop()
        
        with patch.object(scheduler, '_monitoring_iteration', side_effect=mock_monitoring_iteration):
            # When: 短時間監視ループを実行
            start_task = asyncio.create_task(scheduler.start())
            await asyncio.sleep(0.1)  # 短時間実行
            if not start_task.done():
                start_task.cancel()
            
            # Then: 監視ループが実行される
            assert loop_iterations >= 1, "Monitoring loop should execute at least once"


class TestErrorHandling:
    """エラーハンドリングテスト"""

    @pytest.mark.asyncio
    async def test_scheduler_handles_report_execution_errors(self):
        """日報実行エラーが適切に処理されること"""
        # Given: on_report_0600でエラーが発生
        with patch('app.app.on_report_0600', side_effect=Exception("Report generation error")):
            scheduler = app.DailyReportScheduler()
            
            # When & Then: エラーが適切に処理される（Fail-Fast原則）
            with pytest.raises(Exception, match="Report generation error"):
                await scheduler._execute_daily_report()

    def test_scheduler_handles_invalid_time_configuration(self):
        """無効な時間設定エラーが適切に処理されること"""
        # Given: DailyReportSchedulerインスタンス
        scheduler = app.DailyReportScheduler()
        
        # When: 無効な設定をモック
        with patch.object(scheduler, 'get_report_time', side_effect=ValueError("Invalid time format")):
            
            # Then: 設定エラーが適切に処理される
            with pytest.raises(ValueError, match="Invalid time format"):
                scheduler.should_trigger_report()

    @pytest.mark.asyncio
    async def test_scheduler_fails_fast_on_critical_errors(self):
        """重要エラー時にFail-Fastで停止すること"""
        # Given: 重要システムエラー
        scheduler = app.DailyReportScheduler()
        
        with patch.object(scheduler, 'get_current_jst_time', side_effect=Exception("System time error")):
            # When & Then: システムエラーでFail-Fast停止
            with pytest.raises(Exception, match="System time error"):
                scheduler.should_trigger_report()


class TestConfigurationIntegration:
    """設定統合テスト"""

    def test_scheduler_uses_processing_at_setting(self):
        """スケジューラーがPROCESSING_AT設定を使用すること"""
        # Given: 設定値の確認
        scheduler = app.DailyReportScheduler()
        
        # When: 設定から日報時刻を取得
        report_time = scheduler.get_report_time()
        
        # Then: PROCESSING_AT（06:00）設定が使用される
        assert report_time.hour == 6, "Should use PROCESSING_AT hour setting (6)"
        assert report_time.minute == 0, "Should use PROCESSING_AT minute setting (0)"

    def test_scheduler_respects_jst_timezone_setting(self):
        """スケジューラーがJSTタイムゾーン設定を尊重すること"""
        # Given: TZ=Asia/Tokyo設定
        scheduler = app.DailyReportScheduler()
        
        # When: JST時間を取得
        jst_time = scheduler.get_current_jst_time()
        
        # Then: JST（UTC+9）タイムゾーンが使用される
        expected_offset = timedelta(hours=9)
        assert jst_time.utcoffset() == expected_offset, "Should use JST timezone (UTC+9)"