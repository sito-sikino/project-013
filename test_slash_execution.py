"""スラッシュコマンド実行テスト（8-2）- Red段階"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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


class TestSlashExecutionBasic:
    """基本的なSlashコマンド実行テスト"""

    def test_execute_slash_command_function_exists(self):
        """execute_slash_command関数が定義されていること"""
        # Given: app.pyモジュール
        
        # When & Then: execute_slash_command関数が存在する
        assert hasattr(app, 'execute_slash_command'), "execute_slash_command function must be defined in app.py"
        assert callable(app.execute_slash_command), "execute_slash_command must be callable"

    @pytest.mark.asyncio
    async def test_execute_slash_command_is_async_function(self):
        """execute_slash_command関数が非同期関数であること"""
        # Given: execute_slash_command関数
        
        # When & Then: 非同期関数である
        import inspect
        assert inspect.iscoroutinefunction(app.execute_slash_command), "execute_slash_command must be an async function"

    def test_execute_slash_command_has_correct_signature(self):
        """execute_slash_command関数が正しいシグネチャを持つこと"""
        # Given: execute_slash_command関数
        
        # When: 関数シグネチャを確認
        import inspect
        sig = inspect.signature(app.execute_slash_command)
        
        # Then: 必要なパラメータを持つ
        required_params = ['channel', 'content']
        param_names = list(sig.parameters.keys())
        
        for param in required_params:
            assert param in param_names, f"execute_slash_command should have parameter: {param}"


class TestSlashExecutionStateUpdate:
    """状態更新テスト"""

    @pytest.mark.asyncio
    async def test_execute_slash_command_updates_task_content(self):
        """contentが提供された場合にtaskが更新されること"""
        # Given: contentが提供される
        with patch('app.state.update_task') as mock_update_task, \
             patch('app.state.set_active_channel') as mock_set_channel, \
             patch('app.app.common_sequence') as mock_common_sequence, \
             patch('app.store.append') as mock_store_append, \
             patch('app.logger.log_ok') as mock_log_ok:
            
            # When: execute_slash_commandを呼び出す
            await app.execute_slash_command(channel=None, content="新しいタスク内容")
            
            # Then: update_taskが呼ばれる
            mock_update_task.assert_called_once_with(content="新しいタスク内容", channel=None)

    @pytest.mark.asyncio  
    async def test_execute_slash_command_updates_task_channel(self):
        """channelが提供された場合にtaskとactive_channelが更新されること"""
        # Given: channelが提供される
        with patch('app.state.update_task') as mock_update_task, \
             patch('app.state.set_active_channel') as mock_set_channel, \
             patch('app.app.common_sequence') as mock_common_sequence, \
             patch('app.store.append') as mock_store_append, \
             patch('app.logger.log_ok') as mock_log_ok:
            
            # When: execute_slash_commandを呼び出す
            await app.execute_slash_command(channel="development", content=None)
            
            # Then: update_taskとset_active_channelが呼ばれる
            mock_update_task.assert_called_once_with(content=None, channel="development")
            mock_set_channel.assert_called_once_with("development")

    @pytest.mark.asyncio
    async def test_execute_slash_command_updates_both_task_and_channel(self):
        """channel、content両方が提供された場合に両方が更新されること"""
        # Given: 両方のパラメータが提供される
        with patch('app.state.update_task') as mock_update_task, \
             patch('app.state.set_active_channel') as mock_set_channel, \
             patch('app.app.common_sequence') as mock_common_sequence, \
             patch('app.store.append') as mock_store_append, \
             patch('app.logger.log_ok') as mock_log_ok:
            
            # When: execute_slash_commandを呼び出す
            await app.execute_slash_command(channel="creation", content="タスク実行")
            
            # Then: 両方の更新が実行される
            mock_update_task.assert_called_once_with(content="タスク実行", channel="creation")
            mock_set_channel.assert_called_once_with("creation")

    @pytest.mark.asyncio
    async def test_execute_slash_command_immediate_channel_overwrite(self):
        """active_channelが即座に上書きされること"""
        # Given: channelが提供される
        with patch('app.state.update_task') as mock_update_task, \
             patch('app.state.set_active_channel') as mock_set_channel, \
             patch('app.app.common_sequence') as mock_common_sequence, \
             patch('app.store.append') as mock_store_append, \
             patch('app.logger.log_ok') as mock_log_ok:
            
            # When: execute_slash_commandを呼び出す
            await app.execute_slash_command(channel="creation", content="test")
            
            # Then: set_active_channelが即座に呼ばれる
            mock_set_channel.assert_called_once_with("creation")


class TestSlashExecutionDecisionNotification:
    """決定通知テスト"""

    @pytest.mark.asyncio
    async def test_execute_slash_command_sends_spectra_notification(self):
        """command-centerにSpectra名義で決定通知が送信されること"""
        # Given: 入力パラメータ
        with patch('app.state.update_task') as mock_update_task, \
             patch('app.state.set_active_channel') as mock_set_channel, \
             patch('app.app.common_sequence') as mock_common_sequence, \
             patch('app.store.append') as mock_store_append, \
             patch('app.logger.log_ok') as mock_log_ok, \
             patch('app.settings') as mock_settings:
            
            mock_settings.settings.discord.chan_command_center = "123456789012345678"
            
            # When: execute_slash_commandを呼び出す
            await app.execute_slash_command(channel="development", content="新機能開発")
            
            # Then: common_sequenceがSpectra名義・command-center宛で呼ばれる
            mock_common_sequence.assert_called_once()
            call_args = mock_common_sequence.call_args
            
            assert call_args.kwargs['event_type'] == "slash"
            assert call_args.kwargs['channel'] == "command-center"
            assert call_args.kwargs['actor'] == "spectra"
            assert call_args.kwargs['llm_kind'] == "reply"
            assert call_args.kwargs['llm_channel'] == "123456789012345678"
            assert "決定" in call_args.kwargs['payload_summary']  # 決定通知内容を含む

    @pytest.mark.asyncio
    async def test_execute_slash_command_notification_content_channel_only(self):
        """channelのみ指定時の決定通知内容が適切であること"""
        # Given: channelのみ指定
        with patch('app.state.update_task'), \
             patch('app.state.set_active_channel'), \
             patch('app.app.common_sequence') as mock_common_sequence, \
             patch('app.store.append'), \
             patch('app.logger.log_ok'), \
             patch('app.settings') as mock_settings:
            
            mock_settings.settings.discord.chan_command_center = "123456789012345678"
            
            # When: execute_slash_commandを呼び出す
            await app.execute_slash_command(channel="creation", content=None)
            
            # Then: payload_summaryにchannel情報が含まれる
            call_args = mock_common_sequence.call_args
            assert "creation" in call_args.kwargs['payload_summary']

    @pytest.mark.asyncio
    async def test_execute_slash_command_notification_content_both_provided(self):
        """channel・content両方指定時の決定通知内容が適切であること"""
        # Given: 両方指定
        with patch('app.state.update_task'), \
             patch('app.state.set_active_channel'), \
             patch('app.app.common_sequence') as mock_common_sequence, \
             patch('app.store.append'), \
             patch('app.logger.log_ok'), \
             patch('app.settings') as mock_settings:
            
            mock_settings.settings.discord.chan_command_center = "123456789012345678"
            
            # When: execute_slash_commandを呼び出す
            await app.execute_slash_command(channel="development", content="API実装タスク")
            
            # Then: payload_summaryに両方の情報が含まれる
            call_args = mock_common_sequence.call_args
            payload = call_args.kwargs['payload_summary']
            assert "development" in payload
            assert "API実装タスク" in payload


class TestSlashExecutionRedisLogging:
    """Redis追記・ログテスト"""

    @pytest.mark.asyncio
    async def test_execute_slash_command_appends_user_input_to_redis(self):
        """ユーザー入力がRedisに追記されること"""
        # Given: 入力パラメータ
        with patch('app.state.update_task'), \
             patch('app.state.set_active_channel'), \
             patch('app.app.common_sequence'), \
             patch('app.store.append') as mock_store_append, \
             patch('app.logger.log_ok'), \
             patch('app.settings') as mock_settings:
            
            mock_settings.settings.discord.chan_command_center = "123456789012345678"
            
            # When: execute_slash_commandを呼び出す
            await app.execute_slash_command(channel="creation", content="新しいタスク")
            
            # Then: ユーザー入力がRedisに追記される
            # store.appendが呼ばれることを確認（引数は後で詳細検証）
            assert mock_store_append.call_count >= 1

    @pytest.mark.asyncio
    async def test_execute_slash_command_logs_success(self):
        """成功時にlog_okが呼ばれること"""
        # Given: 正常な入力
        with patch('app.state.update_task'), \
             patch('app.state.set_active_channel'), \
             patch('app.app.common_sequence'), \
             patch('app.store.append'), \
             patch('app.logger.log_ok') as mock_log_ok, \
             patch('app.settings') as mock_settings:
            
            mock_settings.settings.discord.chan_command_center = "123456789012345678"
            
            # When: execute_slash_commandを呼び出す
            await app.execute_slash_command(channel="development", content="テスト")
            
            # Then: log_okが呼ばれる
            mock_log_ok.assert_called_once_with(
                "slash",
                "command-center", 
                "spectra",
                "slash_execution_completed"
            )


class TestSlashExecutionValidation:
    """バリデーション統合テスト"""

    @pytest.mark.asyncio
    async def test_execute_slash_command_uses_parse_slash_command(self):
        """parse_slash_commandを使用してバリデーションを行うこと"""
        # Given: 入力パラメータ
        with patch('app.app.parse_slash_command') as mock_parse, \
             patch('app.state.update_task'), \
             patch('app.state.set_active_channel'), \
             patch('app.app.common_sequence'), \
             patch('app.store.append'), \
             patch('app.logger.log_ok'), \
             patch('app.settings') as mock_settings:
            
            mock_parse.return_value = {"channel": "creation", "content": "test task"}
            mock_settings.settings.discord.chan_command_center = "123456789012345678"
            
            # When: execute_slash_commandを呼び出す
            await app.execute_slash_command(channel="creation", content="test task")
            
            # Then: parse_slash_commandが呼ばれる
            mock_parse.assert_called_once_with("creation", "test task")

    @pytest.mark.asyncio
    async def test_execute_slash_command_validation_error_propagation(self):
        """parse_slash_commandのエラーが伝播されること（Fail-Fast）"""
        # Given: 無効な入力
        with patch('app.app.parse_slash_command') as mock_parse:
            mock_parse.side_effect = ValueError("Invalid channel: bad_channel")
            
            # When & Then: SystemExitが発生する
            with pytest.raises(SystemExit):
                await app.execute_slash_command(channel="bad_channel", content="test")


class TestSlashExecutionFailFast:
    """Fail-Fast原則テスト"""

    @pytest.mark.asyncio
    async def test_execute_slash_command_fails_fast_on_state_error(self):
        """状態更新エラー時に即座に失敗すること"""
        # Given: 状態更新でエラーが発生
        with patch('app.app.parse_slash_command') as mock_parse, \
             patch('app.state.update_task') as mock_update_task, \
             patch('app.logger.log_err') as mock_log_err:
            
            mock_parse.return_value = {"channel": "creation", "content": "test"}
            mock_update_task.side_effect = Exception("State update failed")
            
            # When & Then: 例外が発生する
            with pytest.raises(SystemExit):
                await app.execute_slash_command(channel="creation", content="test")
            
            # Then: log_errが呼ばれる
            mock_log_err.assert_called_once()
            call_args = mock_log_err.call_args
            assert call_args[0][4] == "slash"  # error_stage

    @pytest.mark.asyncio
    async def test_execute_slash_command_fails_fast_on_notification_error(self):
        """通知エラー時に即座に失敗すること"""
        # Given: common_sequenceでエラーが発生
        with patch('app.app.parse_slash_command') as mock_parse, \
             patch('app.state.update_task'), \
             patch('app.state.set_active_channel'), \
             patch('app.app.common_sequence') as mock_common_sequence, \
             patch('app.logger.log_err') as mock_log_err:
            
            mock_parse.return_value = {"channel": "creation", "content": "test"}
            mock_common_sequence.side_effect = Exception("Notification failed")
            
            # When & Then: 例外が発生する
            with pytest.raises(SystemExit):
                await app.execute_slash_command(channel="creation", content="test")
            
            # Then: log_errが呼ばれる
            mock_log_err.assert_called_once()


class TestSlashExecutionE2EConsistency:
    """E2E一貫性テスト"""

    @pytest.mark.asyncio
    async def test_execute_slash_command_e2e_state_redis_discord_log_consistency(self):
        """State/Redis/Discord/Logが一貫していること"""
        # Given: 完全な実行環境
        with patch('app.app.parse_slash_command') as mock_parse, \
             patch('app.state.update_task') as mock_update_task, \
             patch('app.state.set_active_channel') as mock_set_channel, \
             patch('app.app.common_sequence') as mock_common_sequence, \
             patch('app.store.append') as mock_store_append, \
             patch('app.logger.log_ok') as mock_log_ok, \
             patch('app.settings') as mock_settings:
            
            mock_parse.return_value = {"channel": "development", "content": "新機能開発"}
            mock_settings.settings.discord.chan_command_center = "123456789012345678"
            
            # When: execute_slash_commandを呼び出す
            await app.execute_slash_command(channel="development", content="新機能開発")
            
            # Then: 一貫した実行順序で各コンポーネントが呼ばれる
            # 1. パース
            mock_parse.assert_called_once_with("development", "新機能開発")
            
            # 2. 状態更新
            mock_update_task.assert_called_once_with(content="新機能開発", channel="development")
            mock_set_channel.assert_called_once_with("development")
            
            # 3. 通知
            mock_common_sequence.assert_called_once()
            
            # 4. Redis追記（ユーザー入力）
            mock_store_append.assert_called()
            
            # 5. ログ
            mock_log_ok.assert_called_once()
            
            # 一貫性: channelが全て一致
            assert mock_update_task.call_args.kwargs['channel'] == "development"
            assert mock_set_channel.call_args[0][0] == "development"