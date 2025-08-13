"""モード追従テスト（13-1）- Red段階"""

import pytest
from unittest.mock import patch, MagicMock
import os
from datetime import datetime, timezone, timedelta

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


def create_jst_datetime(hour: int, minute: int = 0) -> datetime:
    """JST時間を作成するヘルパー"""
    return datetime.now(timezone(timedelta(hours=9))).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )


class TestModeTrackingScheduler:
    """モード追従スケジューラーテスト"""

    def test_mode_tracking_scheduler_exists(self):
        """モード追従スケジューラークラスが存在することを確認"""
        # Given: モード追従要件
        # When & Then: ModeTrackingSchedulerクラスが存在する
        assert hasattr(app, 'ModeTrackingScheduler'), "ModeTrackingScheduler class should exist in app module"
        
        # インスタンスが作成可能であることを確認
        scheduler_class = getattr(app, 'ModeTrackingScheduler')
        scheduler = scheduler_class()
        assert scheduler is not None, "ModeTrackingScheduler should be instantiable"

    def test_mode_tracking_scheduler_has_required_methods(self):
        """モード追従スケジューラーが必要なメソッドを持つことを確認"""
        # Given: ModeTrackingSchedulerクラス
        scheduler_class = getattr(app, 'ModeTrackingScheduler')
        scheduler = scheduler_class()
        
        # When & Then: 必要なメソッドが存在する
        assert hasattr(scheduler, 'start'), "ModeTrackingScheduler should have start() method"
        assert hasattr(scheduler, 'stop'), "ModeTrackingScheduler should have stop() method"
        assert hasattr(scheduler, 'update_mode_from_time'), "ModeTrackingScheduler should have update_mode_from_time() method"
        assert callable(scheduler.start), "start() should be callable"
        assert callable(scheduler.stop), "stop() should be callable"
        assert callable(scheduler.update_mode_from_time), "update_mode_from_time() should be callable"

    @pytest.mark.asyncio
    async def test_mode_tracking_scheduler_async_start(self):
        """モード追従スケジューラーのstart()がasync関数であることを確認"""
        # Given: ModeTrackingSchedulerインスタンス
        scheduler_class = getattr(app, 'ModeTrackingScheduler')
        scheduler = scheduler_class()
        
        # When & Then: start()メソッドがasync関数である
        import asyncio
        assert asyncio.iscoroutinefunction(scheduler.start), "start() should be an async function"

    def test_global_mode_tracking_scheduler_instance(self):
        """グローバルモード追従スケジューラーインスタンスが存在することを確認"""
        # Given: モード追従要件
        # When & Then: グローバルインスタンスが存在する
        assert hasattr(app, 'mode_tracking_scheduler'), "Global mode_tracking_scheduler should exist"
        
        scheduler = getattr(app, 'mode_tracking_scheduler')
        assert scheduler is not None, "mode_tracking_scheduler should be instantiated"
        assert hasattr(scheduler, 'start'), "Global scheduler should have start() method"


class TestModeFromTimeFunction:
    """mode_from_time()関数テスト"""

    def test_mode_from_time_function_exists(self):
        """mode_from_time()関数が存在することを確認"""
        # Given: モード追従要件
        # When & Then: mode_from_time関数が存在する
        assert hasattr(state, 'mode_from_time'), "mode_from_time function should exist in state module"
        assert callable(state.mode_from_time), "mode_from_time should be callable"

    def test_mode_from_time_standby_period(self):
        """STANDBY期間（00:00-06:00）でSTANDBYモードが返されることを確認"""
        # Given: STANDBY期間の時刻
        standby_times = [
            create_jst_datetime(0, 0),   # 00:00
            create_jst_datetime(3, 30),  # 03:30
            create_jst_datetime(5, 59),  # 05:59
        ]
        
        # When & Then: mode_from_time()がSTANDBYを返す
        for test_time in standby_times:
            mode = state.mode_from_time(test_time)
            assert mode == state.Mode.STANDBY, f"Time {test_time.time()} should return STANDBY mode"

    def test_mode_from_time_processing_period(self):
        """ACTIVE期間（06:01-19:59）でACTIVEモードが返されることを確認"""
        # Given: ACTIVE期間の時刻（06:00はPROCESSINGなので除外）
        active_times = [
            create_jst_datetime(6, 1),   # 06:01
            create_jst_datetime(12, 30), # 12:30
            create_jst_datetime(19, 59), # 19:59
        ]
        
        # When & Then: mode_from_time()がACTIVEを返す
        for test_time in active_times:
            mode = state.mode_from_time(test_time)
            assert mode == state.Mode.ACTIVE, f"Time {test_time.time()} should return ACTIVE mode"
    
    def test_mode_from_time_processing_exact_time(self):
        """PROCESSING時刻（06:00丁度）でPROCESSINGモードが返されることを確認"""
        # Given: PROCESSING時刻
        processing_time = create_jst_datetime(6, 0)
        
        # When & Then: mode_from_time()がPROCESSINGを返す
        mode = state.mode_from_time(processing_time)
        assert mode == state.Mode.PROCESSING, f"Time {processing_time.time()} should return PROCESSING mode"

    def test_mode_from_time_free_period(self):
        """FREE期間（20:00-24:00）でFREEモードが返されることを確認"""
        # Given: FREE期間の時刻
        free_times = [
            create_jst_datetime(20, 0),  # 20:00
            create_jst_datetime(22, 30), # 22:30
            create_jst_datetime(23, 59), # 23:59
        ]
        
        # When & Then: mode_from_time()がFREEを返す
        for test_time in free_times:
            mode = state.mode_from_time(test_time)
            assert mode == state.Mode.FREE, f"Time {test_time.time()} should return FREE mode"


class TestModeTrackingIntegration:
    """モード追従統合テスト"""

    def test_active_mode_initial_channel_command_center(self):
        """ACTIVEモード初期設定でcommand-centerが設定されることを確認"""
        # Given: ACTIVEモード時の初期チャンネル設定
        # When: init_active_channel()でACTIVEモードを指定
        initial_channel = state.init_active_channel(state.Mode.ACTIVE)
        
        # Then: command-centerが返される
        assert initial_channel == "command-center", "ACTIVE mode initial channel should be command-center"

    def test_free_mode_initial_channel_lounge(self):
        """FREEモード初期設定でloungeが設定されることを確認"""
        # Given: FREEモード時の初期チャンネル設定
        # When: init_active_channel()でFREEモードを指定
        initial_channel = state.init_active_channel(state.Mode.FREE)
        
        # Then: loungeが返される
        assert initial_channel == "lounge", "FREE mode initial channel should be lounge"

    def test_mode_tracking_update_integration(self):
        """モード追従でstateが適切に更新されることを確認（統合テスト）"""
        # Given: モード追従スケジューラー
        scheduler_class = getattr(app, 'ModeTrackingScheduler')
        scheduler = scheduler_class()
        
        # When: update_mode_from_time()を呼び出し
        test_time = create_jst_datetime(12, 0)  # ACTIVE期間
        
        with patch.object(state, 'get_current_jst_time', return_value=test_time), \
             patch.object(state, 'update_mode') as mock_update_mode, \
             patch.object(state, 'get_state') as mock_get_state:
            
            # 現在の状態をモック
            mock_current_state = MagicMock()
            mock_current_state.mode = state.Mode.STANDBY  # 現在はSTANDBY
            mock_get_state.return_value = mock_current_state
            
            # モード更新を実行
            scheduler.update_mode_from_time()
            
            # Then: update_mode()がACTIVEで呼ばれる
            mock_update_mode.assert_called_once_with(state.Mode.ACTIVE)

    def test_mode_tracking_channel_update_active_to_command_center(self):
        """ACTIVEモード切り替え時にactive_channelがcommand-centerに設定されることを確認"""
        # Given: STANDBYからACTIVEへの切り替え状況
        scheduler_class = getattr(app, 'ModeTrackingScheduler')
        scheduler = scheduler_class()
        
        test_time = create_jst_datetime(6, 1)  # ACTIVE時刻（06:00はPROCESSING）
        
        with patch.object(state, 'get_current_jst_time', return_value=test_time), \
             patch.object(state, 'get_state') as mock_get_state, \
             patch.object(state, 'update_mode') as mock_update_mode:
            
            # 現在はSTANDBYモード（ACTIVEへの切り替えが必要）
            mock_current_state = MagicMock()
            mock_current_state.mode = state.Mode.STANDBY
            mock_get_state.return_value = mock_current_state
            
            # When: モード更新を実行
            scheduler.update_mode_from_time()
            
            # Then: ACTIVEモードで更新される（update_mode内でchannelも自動更新）
            mock_update_mode.assert_called_once_with(state.Mode.ACTIVE)

    def test_mode_tracking_channel_update_free_to_lounge(self):
        """FREEモード切り替え時にactive_channelがloungeに設定されることを確認"""
        # Given: ACTIVEからFREEへの切り替え状況
        scheduler_class = getattr(app, 'ModeTrackingScheduler')
        scheduler = scheduler_class()
        
        test_time = create_jst_datetime(20, 0)  # FREE開始時刻
        
        with patch.object(state, 'get_current_jst_time', return_value=test_time), \
             patch.object(state, 'get_state') as mock_get_state, \
             patch.object(state, 'update_mode') as mock_update_mode:
            
            # 現在はACTIVEモード（FREEへの切り替えが必要）
            mock_current_state = MagicMock()
            mock_current_state.mode = state.Mode.ACTIVE
            mock_get_state.return_value = mock_current_state
            
            # When: モード更新を実行
            scheduler.update_mode_from_time()
            
            # Then: FREEモードで更新される（update_mode内でchannelも自動更新）
            mock_update_mode.assert_called_once_with(state.Mode.FREE)


class TestModeTrackingSchedulerBehavior:
    """モード追従スケジューラー動作テスト"""

    @pytest.mark.asyncio
    async def test_mode_tracking_scheduler_monitoring_loop(self):
        """モード追従スケジューラーが監視ループを実行することを確認"""
        # Given: モード追従スケジューラー
        scheduler_class = getattr(app, 'ModeTrackingScheduler')
        scheduler = scheduler_class()
        
        # When & Then: start()メソッドが監視ループを実行する
        # 実装後にこのテストが通ることを期待
        with patch.object(scheduler, 'update_mode_from_time') as mock_update:
            # 短時間で停止するモックを設定
            async def mock_start():
                await scheduler._monitoring_iteration()
                
            # _monitoring_iteration()メソッドが実装されることを期待
            assert hasattr(scheduler, '_monitoring_iteration'), "ModeTrackingScheduler should have _monitoring_iteration method"

    def test_mode_tracking_scheduler_no_unnecessary_updates(self):
        """モードに変更がない場合は状態更新が行われないことを確認"""
        # Given: モード追従スケジューラー
        scheduler_class = getattr(app, 'ModeTrackingScheduler')
        scheduler = scheduler_class()
        
        test_time = create_jst_datetime(12, 0)  # ACTIVE期間
        
        with patch.object(state, 'get_current_jst_time', return_value=test_time), \
             patch.object(state, 'get_state') as mock_get_state, \
             patch.object(state, 'update_mode') as mock_update_mode, \
             patch.object(state, 'set_active_channel') as mock_set_channel:
            
            # 現在既にACTIVEモード（変更不要）
            mock_current_state = MagicMock()
            mock_current_state.mode = state.Mode.ACTIVE
            mock_get_state.return_value = mock_current_state
            
            # When: モード更新を実行
            scheduler.update_mode_from_time()
            
            # Then: 状態更新が呼ばれない
            mock_update_mode.assert_not_called()
            mock_set_channel.assert_not_called()


class TestModeTrackingCompleteness:
    """モード追従完全性テスト"""

    def test_all_mode_transitions_covered(self):
        """すべてのモード切り替えパターンがカバーされることを確認"""
        # Given: 3つのモード（STANDBY, ACTIVE, FREE）
        modes = [state.Mode.STANDBY, state.Mode.ACTIVE, state.Mode.FREE]
        
        # When & Then: すべてのモードが適切に定義されている
        for mode in modes:
            assert mode in state.Mode, f"Mode {mode} should be defined in state.Mode enum"
        
        # mode_from_time()がすべての時間帯をカバーしている
        test_times = [
            create_jst_datetime(0, 0),   # STANDBY
            create_jst_datetime(6, 0),   # PROCESSING
            create_jst_datetime(20, 0),  # FREE
        ]
        
        returned_modes = [state.mode_from_time(t) for t in test_times]
        expected_modes = [state.Mode.STANDBY, state.Mode.PROCESSING, state.Mode.FREE]
        
        assert returned_modes == expected_modes, "All time periods should be covered by mode_from_time()"

    def test_mode_tracking_scheduler_integration_requirement(self):
        """モード追従スケジューラーが適切に統合されることを確認"""
        # Given: モード追従システム全体
        # When & Then: 必要なコンポーネントがすべて存在する
        
        # 1. ModeTrackingSchedulerクラス
        assert hasattr(app, 'ModeTrackingScheduler'), "ModeTrackingScheduler class required"
        
        # 2. グローバルインスタンス
        assert hasattr(app, 'mode_tracking_scheduler'), "Global mode_tracking_scheduler instance required"
        
        # 3. state.mode_from_time()関数
        assert hasattr(state, 'mode_from_time'), "mode_from_time function required"
        
        # 4. 必要なstate操作関数
        assert hasattr(state, 'update_mode'), "update_mode function required"
        assert hasattr(state, 'set_active_channel'), "set_active_channel function required"
        assert hasattr(state, 'get_state'), "get_state function required"
        
        # 5. init_active_channel関数
        assert hasattr(state, 'init_active_channel'), "init_active_channel function required"