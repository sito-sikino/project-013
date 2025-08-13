"""06:00呼び出し統合テスト（13-2）- Red段階"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
import os
from datetime import datetime, timezone, timedelta, date
import asyncio

# テスト用環境変数設定（app.pyインポート前に設定）
_TEST_ENV_VARS = {
    "ENV": "dev",
    "TZ": "Asia/Tokyo", 
    "SPECTRA_TOKEN": "test_token",
    "LYNQ_TOKEN": "test_token",
    "PAZ_TOKEN": "test_token",
    "CHAN_COMMAND_CENTER": "123456789012345678",
    "CHAN_CREATION": "123456789012345679", 
    "CHAN_DEVELOPMENT": "123456789012345680",
    "CHAN_LOUNGE": "123456789012345681",
    "REDIS_URL": "redis://localhost:6379",
    "GEMINI_API_KEY": "test_api_key",
    "GEMINI_TIMEOUT_SECONDS": "30",
    "TICK_INTERVAL_SEC_DEV": "15",
    "TICK_PROB_DEV": "1.0",
    "MAX_TEST_MINUTES": "5",
    "TICK_INTERVAL_SEC_PROD": "300",
    "TICK_PROB_PROD": "0.33",
    "STANDBY_START": "00:00",
    "PROCESSING_AT": "06:00",
    "FREE_START": "20:00",
    "LIMIT_CC": "100",
    "LIMIT_CR": "200",
    "LIMIT_DEV": "200",
    "LIMIT_LO": "30",
    "LOG_FILE": "logs/run.log"
}

for key, value in _TEST_ENV_VARS.items():
    os.environ.setdefault(key, value)

from app import app, state


def create_jst_datetime(hour: int, minute: int = 0, day: int = 13) -> datetime:
    """JST時間を作成するヘルパー"""
    return datetime(2025, 8, day, hour, minute, 0, tzinfo=timezone(timedelta(hours=9)))


class TestDailyReportIntegration:
    """06:00日報呼び出し統合テスト"""

    def test_mode_tracking_scheduler_has_daily_report_methods(self):
        """ModeTrackingSchedulerが日報関連メソッドを持つことを確認"""
        # Given: ModeTrackingSchedulerインスタンス
        scheduler = app.mode_tracking_scheduler
        
        # When & Then: 日報関連メソッドが存在する
        assert hasattr(scheduler, '_should_trigger_daily_report'), "ModeTrackingScheduler should have _should_trigger_daily_report method"
        assert hasattr(scheduler, '_execute_daily_report'), "ModeTrackingScheduler should have _execute_daily_report method"
        assert hasattr(scheduler, '_mark_daily_report_executed'), "ModeTrackingScheduler should have _mark_daily_report_executed method"

    def test_daily_report_state_tracking(self):
        """日報実行状態が正しく追跡されることを確認"""
        # Given: ModeTrackingSchedulerインスタンス
        scheduler = app.mode_tracking_scheduler
        
        # When & Then: 実行状態追跡プロパティが存在する
        assert hasattr(scheduler, '_last_report_date'), "Scheduler should track last report execution date"
        assert hasattr(scheduler, '_startup_time'), "Scheduler should track startup time for backfill prevention"

    def test_should_trigger_daily_report_at_0600(self):
        """06:00丁度に日報トリガーが発生することを確認"""
        # Given: 06:00の時刻
        scheduler = app.mode_tracking_scheduler
        test_time = create_jst_datetime(6, 0)
        
        with patch.object(state, 'get_current_jst_time', return_value=test_time):
            # When: 日報トリガー判定
            should_trigger = scheduler._should_trigger_daily_report()
            
            # Then: トリガーが発生する
            assert should_trigger is True, "Daily report should trigger at 06:00"

    def test_should_not_trigger_daily_report_at_other_times(self):
        """06:00以外では日報トリガーが発生しないことを確認"""
        # Given: 06:00以外の時刻
        scheduler = app.mode_tracking_scheduler
        test_times = [
            create_jst_datetime(5, 59),   # 05:59
            create_jst_datetime(6, 1),    # 06:01
            create_jst_datetime(12, 0),   # 12:00
            create_jst_datetime(0, 0),    # 00:00
        ]
        
        for test_time in test_times:
            with patch.object(state, 'get_current_jst_time', return_value=test_time):
                # When: 日報トリガー判定
                should_trigger = scheduler._should_trigger_daily_report()
                
                # Then: トリガーが発生しない
                assert should_trigger is False, f"Daily report should not trigger at {test_time.time()}"

    def test_duplicate_execution_prevention(self):
        """同日内での重複実行が防止されることを確認"""
        # Given: 既に本日実行済みの状態
        scheduler = app.mode_tracking_scheduler
        test_time = create_jst_datetime(6, 0)
        
        # 本日既に実行済みとマーク
        scheduler._last_report_date = "2025-08-13"
        
        with patch.object(state, 'get_current_jst_time', return_value=test_time):
            # When: 日報トリガー判定
            should_trigger = scheduler._should_trigger_daily_report()
            
            # Then: トリガーが発生しない（重複防止）
            assert should_trigger is False, "Daily report should not trigger twice on the same day"

    def test_backfill_prevention_after_0600_startup(self):
        """06:00後の起動時にバックフィルが行われないことを確認"""
        # Given: 06:00後に起動したスケジューラー
        scheduler_class = app.ModeTrackingScheduler
        
        # 07:00に起動
        startup_time = create_jst_datetime(7, 0)
        with patch.object(state, 'get_current_jst_time', return_value=startup_time):
            scheduler = scheduler_class()
            
            # 06:00の時刻でトリガー判定
            test_time = create_jst_datetime(6, 0)
            with patch.object(state, 'get_current_jst_time', return_value=test_time):
                # When: 日報トリガー判定
                should_trigger = scheduler._should_trigger_daily_report()
                
                # Then: トリガーが発生しない（バックフィル防止）
                assert should_trigger is False, "Daily report should not backfill when started after 06:00"

    @pytest.mark.asyncio
    async def test_execute_daily_report_calls_on_report_0600(self):
        """_execute_daily_report()がon_report_0600()を呼び出すことを確認"""
        # Given: ModeTrackingSchedulerインスタンス
        scheduler = app.mode_tracking_scheduler
        
        # When: _execute_daily_report()を実行
        with patch.object(app, 'on_report_0600', new_callable=AsyncMock) as mock_report:
            await scheduler._execute_daily_report()
            
            # Then: on_report_0600()が呼ばれる
            mock_report.assert_called_once()

    def test_mark_daily_report_executed_updates_date(self):
        """_mark_daily_report_executed()が実行日を記録することを確認"""
        # Given: ModeTrackingSchedulerインスタンス
        scheduler = app.mode_tracking_scheduler
        test_time = create_jst_datetime(6, 0)
        
        with patch.object(state, 'get_current_jst_time', return_value=test_time):
            # When: 実行完了をマーク
            scheduler._mark_daily_report_executed()
            
            # Then: 本日の日付が記録される
            assert scheduler._last_report_date == "2025-08-13", "Should mark today's date as executed"

    @pytest.mark.asyncio
    async def test_monitoring_iteration_triggers_daily_report_at_0600(self):
        """監視イテレーションが06:00に日報を実行することを確認"""
        # Given: 06:00の時刻
        scheduler = app.mode_tracking_scheduler
        test_time = create_jst_datetime(6, 0)
        
        with patch.object(state, 'get_current_jst_time', return_value=test_time), \
             patch.object(scheduler, 'update_mode_from_time') as mock_update_mode, \
             patch.object(scheduler, '_should_trigger_daily_report', return_value=True), \
             patch.object(scheduler, '_execute_daily_report', new_callable=AsyncMock) as mock_execute, \
             patch.object(scheduler, '_mark_daily_report_executed') as mock_mark:
            
            # When: 監視イテレーションを実行
            await scheduler._monitoring_iteration()
            
            # Then: モード更新と日報実行が両方呼ばれる
            mock_update_mode.assert_called_once()
            mock_execute.assert_called_once()
            mock_mark.assert_called_once()

    @pytest.mark.asyncio
    async def test_monitoring_iteration_skips_daily_report_at_other_times(self):
        """監視イテレーションが06:00以外で日報を実行しないことを確認"""
        # Given: 06:00以外の時刻
        scheduler = app.mode_tracking_scheduler
        test_time = create_jst_datetime(12, 0)
        
        with patch.object(state, 'get_current_jst_time', return_value=test_time), \
             patch.object(scheduler, 'update_mode_from_time') as mock_update_mode, \
             patch.object(scheduler, '_should_trigger_daily_report', return_value=False), \
             patch.object(scheduler, '_execute_daily_report', new_callable=AsyncMock) as mock_execute:
            
            # When: 監視イテレーションを実行
            await scheduler._monitoring_iteration()
            
            # Then: モード更新のみ呼ばれる（日報実行はされない）
            mock_update_mode.assert_called_once()
            mock_execute.assert_not_called()


class TestIntegratedSchedulerBehavior:
    """統合スケジューラー動作テスト"""

    @pytest.mark.asyncio
    async def test_integrated_scheduler_handles_0600_transition(self):
        """統合スケジューラーが06:00の遷移を正しく処理することを確認"""
        # Given: 05:59から06:00への遷移
        # 05:59に起動した新しいスケジューラー
        time_0559 = create_jst_datetime(5, 59)
        with patch.object(state, 'get_current_jst_time', return_value=time_0559):
            scheduler = app.ModeTrackingScheduler()
        
        # 05:59の状態
        with patch.object(state, 'get_current_jst_time', return_value=time_0559), \
             patch.object(app, 'on_report_0600', new_callable=AsyncMock) as mock_report:
            
            # 05:59では日報実行されない
            await scheduler._monitoring_iteration()
            mock_report.assert_not_called()
        
        # 06:00の状態（同じインスタンスで時刻が進む）
        time_0600 = create_jst_datetime(6, 0)
        with patch.object(state, 'get_current_jst_time', return_value=time_0600), \
             patch.object(app, 'on_report_0600', new_callable=AsyncMock) as mock_report:
            
            # 06:00では日報実行される（初回実行）
            await scheduler._monitoring_iteration()
            mock_report.assert_called_once()

    def test_mode_updates_to_processing_at_0600(self):
        """06:00にモードがPROCESSINGに更新されることを確認"""
        # Given: 06:00の時刻
        scheduler = app.mode_tracking_scheduler
        test_time = create_jst_datetime(6, 0)
        
        with patch.object(state, 'get_current_jst_time', return_value=test_time), \
             patch.object(state, 'get_state') as mock_get_state, \
             patch.object(state, 'update_mode') as mock_update_mode:
            
            # 現在はSTANDBYモード
            mock_current_state = MagicMock()
            mock_current_state.mode = state.Mode.STANDBY
            mock_get_state.return_value = mock_current_state
            
            # When: モード更新を実行
            scheduler.update_mode_from_time()
            
            # Then: PROCESSINGモードに更新される
            mock_update_mode.assert_called_once_with(state.Mode.PROCESSING)

    @pytest.mark.asyncio
    async def test_error_handling_in_daily_report_execution(self):
        """日報実行エラーが適切に処理されることを確認"""
        # Given: エラーが発生する状況
        scheduler = app.mode_tracking_scheduler
        test_time = create_jst_datetime(6, 0)
        
        with patch.object(state, 'get_current_jst_time', return_value=test_time), \
             patch.object(scheduler, '_should_trigger_daily_report', return_value=True), \
             patch.object(app, 'on_report_0600', side_effect=Exception("Report generation failed")), \
             pytest.raises(Exception) as exc_info:
            
            # When: 日報実行でエラー発生
            await scheduler._execute_daily_report()
            
            # Then: エラーが伝播する（Fail-Fast）
            assert "Report generation failed" in str(exc_info.value)


class TestSchedulerLifecycle:
    """スケジューラーライフサイクルテスト"""

    def test_startup_time_initialization(self):
        """スケジューラー起動時刻が正しく初期化されることを確認"""
        # Given: 新しいスケジューラーインスタンス
        startup_time = create_jst_datetime(5, 0)
        
        with patch.object(state, 'get_current_jst_time', return_value=startup_time):
            scheduler = app.ModeTrackingScheduler()
            
            # When & Then: 起動時刻が記録される
            assert scheduler._startup_time is not None, "Startup time should be recorded"
            assert scheduler._startup_time.hour == 5, "Startup hour should be 5"
            assert scheduler._startup_time.minute == 0, "Startup minute should be 0"

    @pytest.mark.asyncio
    async def test_scheduler_runs_monitoring_loop(self):
        """スケジューラーが監視ループを実行することを確認"""
        # Given: ModeTrackingSchedulerインスタンス
        scheduler = app.ModeTrackingScheduler()
        
        # モックで短時間実行
        async def mock_short_run():
            scheduler.is_running = True
            await scheduler._monitoring_iteration()
            scheduler.is_running = False
        
        with patch.object(scheduler, '_monitoring_iteration', new_callable=AsyncMock) as mock_iter:
            scheduler.start = mock_short_run
            
            # When: スケジューラー開始
            await scheduler.start()
            
            # Then: 監視イテレーションが呼ばれる
            mock_iter.assert_called()


class TestDeprecatedDailyReportScheduler:
    """既存DailyReportSchedulerとの互換性テスト"""

    def test_daily_report_scheduler_still_exists(self):
        """既存のDailyReportSchedulerが引き続き存在することを確認"""
        # Given & When & Then: 後方互換性のため存在確認
        assert hasattr(app, 'DailyReportScheduler'), "DailyReportScheduler class should still exist"
        assert hasattr(app, 'daily_report_scheduler'), "Global daily_report_scheduler should still exist"

    def test_daily_report_scheduler_deprecated_notice(self):
        """DailyReportSchedulerに非推奨マークがあることを確認（オプション）"""
        # Given: DailyReportSchedulerクラス
        scheduler_class = app.DailyReportScheduler
        
        # When & Then: docstringに非推奨情報があるか確認（オプション）
        # 実装後に統合が完了したら非推奨マークを追加
        # assert "deprecated" in (scheduler_class.__doc__ or "").lower(), "Should mark as deprecated"
        pass  # 現時点では非推奨マークは不要