"""日報生成・リセットテスト（11-2）- Red段階"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
import asyncio
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


class TestDailyReportGenerationBasic:
    """日報生成基本機能テスト"""

    def test_on_report_0600_function_exists(self):
        """on_report_0600関数が定義されていること"""
        # Given: app.pyモジュール
        
        # When & Then: on_report_0600関数が存在する
        assert hasattr(app, 'on_report_0600'), "on_report_0600 function must be defined in app.py"
        assert callable(app.on_report_0600), "on_report_0600 must be callable"

    @pytest.mark.asyncio
    async def test_on_report_0600_is_async_function(self):
        """on_report_0600が非同期関数であること"""
        # Given: on_report_0600関数
        
        # When & Then: on_report_0600が非同期関数である
        import inspect
        assert inspect.iscoroutinefunction(app.on_report_0600), "on_report_0600 must be async function"

    @pytest.mark.asyncio
    async def test_on_report_0600_no_longer_stub(self):
        """on_report_0600がスタブ実装でなくなっていること"""
        # Given: on_report_0600関数
        
        # When: on_report_0600を実行（モック環境で）
        with patch('app.app.common_sequence') as mock_common_sequence, \
             patch('app.store.reset') as mock_store_reset, \
             patch('app.state.set_active_channel') as mock_set_active:
            
            await app.on_report_0600()
            
            # Then: スタブではなく実際の処理が実行される（最低限common_sequenceが呼ばれる）
            mock_common_sequence.assert_called_once(), "on_report_0600 should call common_sequence (not be a stub)"


class TestDailyReportSpectraFixedPosting:
    """日報Spectra固定投稿テスト"""

    @pytest.mark.asyncio
    async def test_report_uses_spectra_fixed_bot(self):
        """日報がSpectra固定で投稿されること"""
        # Given: 日報生成機能
        with patch('app.app.common_sequence') as mock_common_sequence, \
             patch('app.store.reset') as mock_store_reset, \
             patch('app.state.set_active_channel') as mock_set_active:
            
            # When: 日報を生成
            await app.on_report_0600()
            
            # Then: common_sequenceが適切なパラメータで呼ばれる（report種別）
            mock_common_sequence.assert_called_once()
            call_args = mock_common_sequence.call_args
            assert call_args[1]['llm_kind'] == 'report', "Should use 'report' kind for daily report"

    @pytest.mark.asyncio
    async def test_report_posts_to_command_center(self):
        """日報がcommand-centerに投稿されること"""
        # Given: 日報生成機能
        with patch('app.app.common_sequence') as mock_common_sequence, \
             patch('app.store.reset') as mock_store_reset, \
             patch('app.state.set_active_channel') as mock_set_active:
            
            # When: 日報を生成
            await app.on_report_0600()
            
            # Then: command-centerが対象チャンネルとして指定される
            mock_common_sequence.assert_called_once()
            call_args = mock_common_sequence.call_args
            assert call_args[1]['channel'] == 'command-center', "Should post to command-center channel"
            assert call_args[1]['llm_channel'] == '123456789012345678', "Should use command-center Discord ID"

    @pytest.mark.asyncio
    async def test_report_event_type_and_actor(self):
        """日報のイベント種別とアクターが正しく設定されること"""
        # Given: 日報生成機能
        with patch('app.app.common_sequence') as mock_common_sequence, \
             patch('app.store.reset') as mock_store_reset, \
             patch('app.state.set_active_channel') as mock_set_active:
            
            # When: 日報を生成
            await app.on_report_0600()
            
            # Then: 適切なイベント種別とアクターが設定される
            mock_common_sequence.assert_called_once()
            call_args = mock_common_sequence.call_args
            assert call_args[1]['event_type'] == 'report', "Should use 'report' event type"
            assert call_args[1]['actor'] == 'spectra', "Should use 'spectra' as actor"


class TestDailyReportResetSequence:
    """日報後リセット処理テスト"""

    @pytest.mark.asyncio
    async def test_store_reset_called_after_report(self):
        """日報送信成功後にstore.reset()が呼ばれること"""
        # Given: 日報生成機能
        with patch('app.app.common_sequence') as mock_common_sequence, \
             patch('app.store.reset') as mock_store_reset, \
             patch('app.state.set_active_channel') as mock_set_active:
            
            # When: 日報を生成
            await app.on_report_0600()
            
            # Then: store.reset()が呼ばれる
            mock_store_reset.assert_called_once(), "Should call store.reset() after report"

    @pytest.mark.asyncio
    async def test_active_channel_set_to_command_center(self):
        """active_channelがcommand-centerに設定されること"""
        # Given: 日報生成機能
        with patch('app.app.common_sequence') as mock_common_sequence, \
             patch('app.store.reset') as mock_store_reset, \
             patch('app.state.set_active_channel') as mock_set_active:
            
            # When: 日報を生成
            await app.on_report_0600()
            
            # Then: active_channelがcommand-centerに設定される
            mock_set_active.assert_called_once_with('command-center'), "Should set active_channel to command-center"

    @pytest.mark.asyncio
    async def test_mode_set_to_active(self):
        """mode=ACTIVEに設定されること"""
        # Given: 日報生成機能
        with patch('app.app.common_sequence') as mock_common_sequence, \
             patch('app.store.reset') as mock_store_reset, \
             patch('app.state.set_active_channel') as mock_set_active, \
             patch('app.state.update_mode') as mock_update_mode:
            
            # When: 日報を生成
            await app.on_report_0600()
            
            # Then: mode=ACTIVEに設定される
            mock_update_mode.assert_called_once()
            call_args = mock_update_mode.call_args
            from app.state import Mode
            assert call_args[0][0] == Mode.ACTIVE, "Should set mode to ACTIVE"


class TestDailyReportContent:
    """日報コンテンツテスト"""

    @pytest.mark.asyncio
    async def test_report_payload_summary_contains_daily_report(self):
        """日報のペイロード要約に適切な内容が含まれること"""
        # Given: 日報生成機能
        with patch('app.app.common_sequence') as mock_common_sequence, \
             patch('app.store.reset') as mock_store_reset, \
             patch('app.state.set_active_channel') as mock_set_active:
            
            # When: 日報を生成
            await app.on_report_0600()
            
            # Then: payload_summaryに日報関連の内容が含まれる
            mock_common_sequence.assert_called_once()
            call_args = mock_common_sequence.call_args
            payload_summary = call_args[1]['payload_summary']
            assert 'daily_report' in payload_summary.lower() or 'report' in payload_summary.lower(), \
                "payload_summary should indicate this is a daily report"


class TestDailyReportExecutionOrder:
    """日報実行順序テスト"""

    @pytest.mark.asyncio
    async def test_reset_happens_after_common_sequence(self):
        """store.reset()がcommon_sequence実行後に呼ばれること"""
        # Given: 日報生成機能
        execution_order = []
        
        async def mock_common_sequence_with_tracking(*args, **kwargs):
            execution_order.append('common_sequence')
        
        def mock_reset_with_tracking():
            execution_order.append('store_reset')
        
        def mock_set_active_with_tracking(channel):
            execution_order.append('set_active_channel')
            
        with patch('app.app.common_sequence', side_effect=mock_common_sequence_with_tracking), \
             patch('app.store.reset', side_effect=mock_reset_with_tracking), \
             patch('app.state.set_active_channel', side_effect=mock_set_active_with_tracking):
            
            # When: 日報を生成
            await app.on_report_0600()
            
            # Then: 実行順序が正しい（common_sequence → reset → set_active_channel）
            assert len(execution_order) >= 2, "Should execute multiple operations"
            assert execution_order[0] == 'common_sequence', "common_sequence should be executed first"
            assert 'store_reset' in execution_order, "store_reset should be executed"
            assert 'set_active_channel' in execution_order, "set_active_channel should be executed"


class TestDailyReportErrorHandling:
    """日報エラーハンドリングテスト"""

    @pytest.mark.asyncio
    async def test_reset_not_called_if_common_sequence_fails(self):
        """common_sequenceが失敗した場合はリセット処理が呼ばれないこと（Fail-Fast）"""
        # Given: common_sequenceが失敗する状況
        with patch('app.app.common_sequence', side_effect=Exception("Report generation failed")), \
             patch('app.store.reset') as mock_store_reset, \
             patch('app.state.set_active_channel') as mock_set_active:
            
            # When & Then: common_sequenceの失敗でon_report_0600も失敗し、リセットは呼ばれない
            with pytest.raises(Exception, match="Report generation failed"):
                await app.on_report_0600()
            
            mock_store_reset.assert_not_called(), "Should not call store.reset() if common_sequence fails (Fail-Fast)"
            mock_set_active.assert_not_called(), "Should not call set_active_channel if common_sequence fails (Fail-Fast)"


class TestDailyReportIntegration:
    """日報統合テスト"""

    @pytest.mark.asyncio
    async def test_on_report_0600_full_integration(self):
        """on_report_0600の完全統合テスト"""
        # Given: すべてのモック設定
        with patch('app.app.common_sequence') as mock_common_sequence, \
             patch('app.store.reset') as mock_store_reset, \
             patch('app.state.set_active_channel') as mock_set_active, \
             patch('app.state.update_mode') as mock_update_mode:
            
            # When: on_report_0600を実行
            await app.on_report_0600()
            
            # Then: すべての必要な処理が実行される
            # 1. common_sequenceが適切なパラメータで呼ばれる
            mock_common_sequence.assert_called_once()
            call_args = mock_common_sequence.call_args
            expected_kwargs = {
                'event_type': 'report',
                'channel': 'command-center',
                'actor': 'spectra',
                'llm_kind': 'report',
                'llm_channel': '123456789012345678'
            }
            for key, value in expected_kwargs.items():
                assert call_args[1][key] == value, f"{key} should be {value}"
            
            # 2. store.reset()が呼ばれる
            mock_store_reset.assert_called_once()
            
            # 3. active_channel=command-centerに設定される
            mock_set_active.assert_called_once_with('command-center')
            
            # 4. mode=ACTIVEに設定される
            from app.state import Mode
            mock_update_mode.assert_called_once_with(Mode.ACTIVE)