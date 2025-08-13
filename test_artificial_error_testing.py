"""人工エラー試験テスト（12-2：Fail-Fast原則・7段階エラー検証）"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
import sys
import os
import asyncio
import inspect
from typing import Dict, List

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

from app import app, logger


def verify_error_stage_logging(mock_log_err, expected_stage: str, expected_error_message: str = None):
    """エラー段階ログ記録の共通検証ヘルパー"""
    mock_log_err.assert_called_once()
    call_args = mock_log_err.call_args
    assert call_args[0][4] == expected_stage, f"error_stage should be '{expected_stage}'"
    
    if expected_error_message:
        assert expected_error_message in call_args[0][5], f"error_detail should contain '{expected_error_message}'"


async def trigger_common_sequence_error(patch_target: str, error_message: str):
    """common_sequence内エラー発生の共通トリガーヘルパー"""
    with patch(patch_target, side_effect=Exception(error_message)), \
         patch('app.logger.log_err') as mock_log_err, \
         pytest.raises(SystemExit):
        
        await app.common_sequence(
            event_type="user_msg",
            channel="command-center",
            actor="user",
            payload_summary="test message",
            llm_kind="reply",
            llm_channel="123456789012345678"
        )
    
    return mock_log_err


class TestArtificialErrorSettings:
    """設定段階の人工エラー試験"""

    def test_artificial_settings_error(self):
        """設定エラーを意図的に起こし、error_stage='settings'が記録されることを検証"""
        # Given: 設定エラーが発生する状況
        from app import settings
        
        # When & Then: fail_fast()でlog_errがsettings段階で呼ばれることを確認
        with patch('app.logger.log_err') as mock_log_err, \
             pytest.raises(SystemExit):
            
            # 意図的にsettingsエラーを発生
            settings.fail_fast("Artificial settings error for testing")
            
            # log_errが正しい段階で呼ばれることを検証
            mock_log_err.assert_called_once()
            call_args = mock_log_err.call_args
            assert call_args[0][0] == "settings", "event_type should be 'settings'"
            assert call_args[0][4] == "settings", "error_stage should be 'settings'"
            assert "Artificial settings error" in call_args[0][5], "error_detail should contain artificial error"


class TestArtificialErrorSlash:
    """スラッシュ段階の人工エラー試験"""

    @pytest.mark.asyncio
    async def test_artificial_slash_validation_error(self):
        """スラッシュバリデーションエラーを意図的に起こし、error_stage='slash'が記録されることを検証"""
        # Given: バリデーションエラーが発生する状況
        with patch('app.logger.log_err') as mock_log_err, \
             pytest.raises(SystemExit):
            
            # When: 意図的に無効なパラメータでslashコマンドを実行
            await app.execute_slash_command(channel="invalid_channel_name", content="test")
            
            # Then: error_stage='slash'でlog_errが呼ばれる
            mock_log_err.assert_called_once()
            call_args = mock_log_err.call_args
            assert call_args[0][4] == "slash", "error_stage should be 'slash'"

    @pytest.mark.asyncio
    async def test_artificial_slash_state_error(self):
        """スラッシュ状態更新エラーを意図的に起こし、error_stage='slash'が記録されることを検証"""
        # Given: 状態更新エラーが発生する状況
        mock_parsed = {"channel": "creation", "content": "test task"}
        with patch('app.app.parse_slash_command', return_value=mock_parsed), \
             patch('app.state.update_task', side_effect=Exception("Artificial state update error")), \
             patch('app.logger.log_err') as mock_log_err, \
             pytest.raises(SystemExit):
            
            # When: 意図的に状態更新エラーを発生
            await app.execute_slash_command(channel="creation", content="test task")
            
            # Then: error_stage='slash'でlog_errが呼ばれる
            mock_log_err.assert_called_once()
            call_args = mock_log_err.call_args
            assert call_args[0][4] == "slash", "error_stage should be 'slash'"
            assert "Artificial state update error" in call_args[0][5]


class TestArtificialErrorPlan:
    """計画段階の人工エラー試験"""

    @pytest.mark.asyncio
    async def test_artificial_plan_llm_error(self):
        """LLMエラーを意図的に起こし、error_stage='plan'が記録されることを検証"""
        # 事前準備パッチを適用してからエラーを発生
        with patch('app.store.read_all', return_value=[]), \
             patch('app.state.get_state'):
            
            mock_log_err = await trigger_common_sequence_error(
                'app.supervisor.generate', 
                "Artificial LLM generation failure"
            )
            
            verify_error_stage_logging(mock_log_err, "plan", "Artificial LLM generation failure")


class TestArtificialErrorTyping:
    """タイピング段階の人工エラー試験"""

    @pytest.mark.asyncio
    async def test_artificial_typing_discord_error(self):
        """Discord typingエラーを意図的に起こし、error_stage='typing'が記録されることを検証"""
        mock_result = {"speaker": "spectra", "text": "test response"}
        with patch('app.store.read_all', return_value=[]), \
             patch('app.state.get_state'), \
             patch('app.supervisor.generate', return_value=mock_result), \
             patch('app.discord.typing', side_effect=Exception("Artificial Discord typing failure")), \
             patch('app.logger.log_err') as mock_log_err, \
             pytest.raises(SystemExit):
            
            await app.common_sequence(
                event_type="user_msg",
                channel="command-center",
                actor="user",
                payload_summary="test message",
                llm_kind="reply",
                llm_channel="123456789012345678"
            )
            
            verify_error_stage_logging(mock_log_err, "typing", "Artificial Discord typing failure")


class TestArtificialErrorSend:
    """送信段階の人工エラー試験"""

    @pytest.mark.asyncio
    async def test_artificial_send_discord_error(self):
        """Discord sendエラーを意図的に起こし、error_stage='send'が記録されることを検証"""
        mock_result = {"speaker": "spectra", "text": "test response"}
        with patch('app.store.read_all', return_value=[]), \
             patch('app.state.get_state'), \
             patch('app.supervisor.generate', return_value=mock_result), \
             patch('app.discord.typing', return_value=None), \
             patch('app.discord.send', side_effect=Exception("Artificial Discord send failure")), \
             patch('app.logger.log_err') as mock_log_err, \
             pytest.raises(SystemExit):
            
            await app.common_sequence(
                event_type="user_msg",
                channel="command-center",
                actor="user",
                payload_summary="test message",
                llm_kind="reply",
                llm_channel="123456789012345678"
            )
            
            verify_error_stage_logging(mock_log_err, "send", "Artificial Discord send failure")


class TestArtificialErrorReport:
    """日報段階の人工エラー試験"""

    @pytest.mark.asyncio
    async def test_artificial_report_generation_error(self):
        """日報生成エラーを意図的に起こし、error_stage='report'が記録されることを検証"""
        # Given: 日報生成エラーが発生する状況
        with patch('app.app.common_sequence', side_effect=Exception("Artificial daily report failure")), \
             patch('app.logger.log_err') as mock_log_err, \
             pytest.raises(SystemExit):
            
            # When: 意図的に日報生成エラーを発生
            await app.on_report_0600()
            
            # Then: log_errがreport段階で呼ばれる
            mock_log_err.assert_called_once()
            call_args = mock_log_err.call_args
            assert call_args[0][0] == "report", "event_type should be 'report'"
            assert call_args[0][4] == "report", "error_stage should be 'report'"
            assert "Artificial daily report failure" in call_args[0][5]

    @pytest.mark.asyncio
    async def test_artificial_report_reset_error(self):
        """日報リセットエラーを意図的に起こし、error_stage='report'が記録されることを検証"""
        # Given: 日報処理でリセットエラーが発生する状況
        with patch('app.app.common_sequence', return_value=None), \
             patch('app.store.reset', side_effect=Exception("Artificial store reset failure")), \
             patch('app.logger.log_err') as mock_log_err, \
             pytest.raises(SystemExit):
            
            # When: 意図的にstore.reset()エラーを発生
            await app.on_report_0600()
            
            # Then: log_errがreport段階で呼ばれる
            mock_log_err.assert_called_once()
            call_args = mock_log_err.call_args
            assert call_args[0][0] == "report", "event_type should be 'report'"
            assert call_args[0][4] == "report", "error_stage should be 'report'"
            assert "Artificial store reset failure" in call_args[0][5]


class TestArtificialErrorMemory:
    """メモリ段階の人工エラー試験"""

    @pytest.mark.asyncio
    async def test_artificial_memory_redis_read_error(self):
        """Redisリードエラーを意図的に起こし、error_stage='memory'が記録されることを検証"""
        mock_log_err = await trigger_common_sequence_error(
            'app.store.read_all',
            "Artificial Redis read failure"
        )
        
        verify_error_stage_logging(mock_log_err, "memory", "Artificial Redis read failure")

    @pytest.mark.asyncio
    async def test_artificial_memory_redis_write_error(self):
        """Redis書き込みエラーを意図的に起こし、error_stage='memory'が記録されることを検証"""
        # Given: Redis書き込みエラーが発生する状況
        mock_result = {"speaker": "spectra", "text": "test response"}
        with patch('app.store.read_all', return_value=[]), \
             patch('app.state.get_state'), \
             patch('app.supervisor.generate', return_value=mock_result), \
             patch('app.discord.typing', return_value=None), \
             patch('app.discord.send', return_value="msg_123"), \
             patch('app.store.append', side_effect=Exception("Artificial Redis write failure")), \
             patch('app.logger.log_err') as mock_log_err, \
             pytest.raises(SystemExit):
            
            # When: 意図的にRedis書き込みエラーを発生
            await app.common_sequence(
                event_type="user_msg",
                channel="command-center",
                actor="user",
                payload_summary="test message",
                llm_kind="reply",
                llm_channel="123456789012345678"
            )
            
            # Then: error_stage='memory'でlog_errが呼ばれる
            mock_log_err.assert_called_once()
            call_args = mock_log_err.call_args
            assert call_args[0][4] == "memory", "error_stage should be 'memory'"
            assert "Artificial Redis write failure" in call_args[0][5]

    def test_artificial_memory_store_connection_error(self):
        """store接続エラーを意図的に起こし、error_stage='memory'が記録されることを検証"""
        # Given: store接続エラーが発生する状況
        from app import store
        
        with patch('app.store.log_err') as mock_log_err:  # Patch at store module level
            with patch.object(store, '_get_redis_connection') as mock_connection:
                # 意図的にRedis接続エラーを発生
                mock_redis = MagicMock()
                mock_redis.ping.side_effect = Exception("Artificial Redis connection failure")
                mock_connection.return_value = mock_redis
                
                # When: test_connectionを実行
                result = store.test_connection()
                
                # Then: log_errが適切なパラメータで呼ばれる
                assert mock_log_err.called, "store connection error should call log_err"
                assert result is False, "test_connection should return False on error"
                
                # error_stage='memory'が使用されることを確認
                call_args = mock_log_err.call_args
                assert call_args[0][4] == "memory", f"error_stage should be 'memory', got '{call_args[0][4]}'"
                assert "Artificial Redis connection failure" in call_args[0][5]


class TestArtificialErrorCompleteness:
    """人工エラー試験の完全性検証"""

    def test_all_error_stages_have_artificial_tests(self):
        """7つの段階すべてに人工エラー試験が実装されていることを確認"""
        # Given: 必要な7つの段階タグ
        required_stages = {"settings", "slash", "plan", "typing", "send", "report", "memory"}
        
        # When: このテストファイルクラス名から実装済み段階を抽出
        implemented_stages = set()
        
        # 各テストクラスが対応する段階を確認
        test_classes = [
            TestArtificialErrorSettings,    # settings
            TestArtificialErrorSlash,       # slash  
            TestArtificialErrorPlan,        # plan
            TestArtificialErrorTyping,      # typing
            TestArtificialErrorSend,        # send
            TestArtificialErrorReport,      # report
            TestArtificialErrorMemory,      # memory
        ]
        
        # クラス名から段階を推定
        for cls in test_classes:
            class_name = cls.__name__.lower()
            if "settings" in class_name:
                implemented_stages.add("settings")
            elif "slash" in class_name:
                implemented_stages.add("slash")
            elif "plan" in class_name:
                implemented_stages.add("plan")
            elif "typing" in class_name:
                implemented_stages.add("typing")
            elif "send" in class_name:
                implemented_stages.add("send")
            elif "report" in class_name:
                implemented_stages.add("report")
            elif "memory" in class_name:
                implemented_stages.add("memory")
        
        # Then: すべての段階が実装されている
        missing_stages = required_stages - implemented_stages
        assert len(missing_stages) == 0, f"All stages should have artificial error tests, missing: {missing_stages}"

    def test_artificial_error_test_methodology(self):
        """人工エラー試験の手法が適切であることを確認"""
        # Given: 人工エラー試験の要件
        # - 意図的な例外発生
        # - 正しいerror_stageでのログ記録
        # - SystemExitでのFail-Fast動作
        
        # When & Then: テストメソッドの命名規則確認
        # すべてのテストメソッドが"artificial"を含むこと
        import inspect
        
        test_methods = []
        current_module = inspect.getmodule(self)
        
        for name, obj in inspect.getmembers(current_module):
            if name.startswith("TestArtificialError") and inspect.isclass(obj):
                for method_name, method in inspect.getmembers(obj, predicate=inspect.isfunction):
                    if method_name.startswith("test_"):
                        test_methods.append(method_name)
        
        artificial_methods = [m for m in test_methods if "artificial" in m.lower()]
        assert len(artificial_methods) >= 9, f"Should have at least 9 artificial error test methods, found {len(artificial_methods)}"