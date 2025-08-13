"""共通シーケンステスト（7-2）- Red段階"""

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
os.environ.setdefault("CHAN_CREATION", "123456789012345678")
os.environ.setdefault("CHAN_DEVELOPMENT", "123456789012345678")
os.environ.setdefault("CHAN_LOUNGE", "123456789012345678")
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


class TestCommonSequenceFunction:
    """共通シーケンス関数のテスト"""

    def test_common_sequence_function_exists(self):
        """common_sequence関数が定義されていること"""
        # Given: app.pyモジュール
        
        # When & Then: common_sequence関数が存在する
        assert hasattr(app, 'common_sequence'), "common_sequence function must be defined in app.py"
        assert callable(app.common_sequence), "common_sequence must be callable"

    @pytest.mark.asyncio
    async def test_common_sequence_is_async_function(self):
        """common_sequence関数が非同期関数であること"""
        # Given: common_sequence関数
        
        # When & Then: 非同期関数である
        import inspect
        assert inspect.iscoroutinefunction(app.common_sequence), "common_sequence must be an async function"

    def test_common_sequence_has_correct_signature(self):
        """common_sequence関数が正しいシグネチャを持つこと"""
        # Given: common_sequence関数
        
        # When: 関数シグネチャを確認
        import inspect
        sig = inspect.signature(app.common_sequence)
        
        # Then: 必要なパラメータを持つ
        required_params = ['event_type', 'channel', 'actor', 'payload_summary', 'llm_kind', 'llm_channel']
        param_names = list(sig.parameters.keys())
        
        for param in required_params:
            assert param in param_names, f"common_sequence should have parameter: {param}"


class TestCommonSequenceExecution:
    """共通シーケンス実行のテスト"""

    @pytest.mark.asyncio
    async def test_common_sequence_executes_6_stage_flow(self):
        """共通シーケンスが6段階フローを実行すること"""
        # Given: モックされた依存関数
        with patch('app.store.read_all') as mock_read_all, \
             patch('app.supervisor.generate') as mock_generate, \
             patch('app.discord.typing') as mock_typing, \
             patch('app.discord.send') as mock_send, \
             patch('app.store.append') as mock_append, \
             patch('app.logger.log_ok') as mock_log_ok:
            
            # モック設定
            mock_read_all.return_value = [{"agent": "user", "channel": "test", "text": "hello"}]
            mock_generate.return_value = {"speaker": "spectra", "text": "response"}
            mock_typing.return_value = 200
            mock_send.return_value = "msg_123"
            
            # When: common_sequence関数を呼び出す
            await app.common_sequence(
                event_type="test",
                channel="test_channel",
                actor="test_actor",
                payload_summary="test_payload",
                llm_kind="reply",
                llm_channel="test_llm_channel"
            )
            
            # Then: 6段階すべてが順次実行される
            mock_read_all.assert_called_once()
            mock_generate.assert_called_once()
            mock_typing.assert_called_once()
            mock_send.assert_called_once()
            mock_append.assert_called_once()
            mock_log_ok.assert_called_once()

    @pytest.mark.asyncio
    async def test_common_sequence_stage1_redis_read_all(self):
        """Stage1: Redis全文読みが正しく実行されること"""
        # Given: モックされたstore.read_all
        with patch('app.store.read_all') as mock_read_all, \
             patch('app.supervisor.generate') as mock_generate, \
             patch('app.discord.typing') as mock_typing, \
             patch('app.discord.send') as mock_send, \
             patch('app.store.append') as mock_append, \
             patch('app.logger.log_ok') as mock_log_ok:
            
            mock_records = [
                {"agent": "user", "channel": "dev", "timestamp": "2025-01-01T10:00:00Z", "text": "hello"},
                {"agent": "spectra", "channel": "dev", "timestamp": "2025-01-01T10:01:00Z", "text": "hi there"}
            ]
            mock_read_all.return_value = mock_records
            mock_generate.return_value = {"speaker": "lynq", "text": "test response"}
            mock_typing.return_value = 200
            mock_send.return_value = "msg_123"
            
            # When: common_sequence実行
            await app.common_sequence(
                event_type="user_msg",
                channel="development", 
                actor="user123",
                payload_summary="test message",
                llm_kind="reply",
                llm_channel="123456789012345678"
            )
            
            # Then: read_all呼び出しと文脈フォーマットが正しい
            mock_read_all.assert_called_once()
            mock_generate.assert_called_once()
            
            # generate呼び出し時にcontextパラメータが渡されていることを確認
            call_args = mock_generate.call_args
            assert 'context' in call_args.kwargs

    @pytest.mark.asyncio
    async def test_common_sequence_stage2_llm_generate(self):
        """Stage2: LLM生成が正しく実行されること"""
        # Given: モック設定
        with patch('app.store.read_all') as mock_read_all, \
             patch('app.supervisor.generate') as mock_generate, \
             patch('app.discord.typing') as mock_typing, \
             patch('app.discord.send') as mock_send, \
             patch('app.store.append') as mock_append, \
             patch('app.logger.log_ok') as mock_log_ok:
            
            mock_read_all.return_value = []
            mock_generate.return_value = {"speaker": "paz", "text": "generated response"}
            mock_typing.return_value = 200
            mock_send.return_value = "msg_456"
            
            # When: common_sequence実行
            await app.common_sequence(
                event_type="auto_tick",
                channel="lounge",
                actor="system",
                payload_summary="auto posting",
                llm_kind="auto", 
                llm_channel="123456789012345678"
            )
            
            # Then: generate関数が正しいパラメータで呼び出される
            mock_generate.assert_called_once()
            call_args = mock_generate.call_args
            
            assert call_args.kwargs['kind'] == "auto"
            assert call_args.kwargs['channel'] == "123456789012345678"
            assert 'limits' in call_args.kwargs
            assert 'persona' in call_args.kwargs

    @pytest.mark.asyncio
    async def test_common_sequence_stage3_discord_typing(self):
        """Stage3: Discord typing送信が正しく実行されること"""
        # Given: モック設定
        with patch('app.store.read_all') as mock_read_all, \
             patch('app.supervisor.generate') as mock_generate, \
             patch('app.discord.typing') as mock_typing, \
             patch('app.discord.send') as mock_send, \
             patch('app.store.append') as mock_append, \
             patch('app.logger.log_ok') as mock_log_ok:
            
            mock_read_all.return_value = []
            mock_generate.return_value = {"speaker": "lynq", "text": "test message"}
            mock_typing.return_value = 200
            mock_send.return_value = "msg_789"
            
            # When: common_sequence実行
            await app.common_sequence(
                event_type="slash",
                channel="command-center",
                actor="spectra", 
                payload_summary="slash command",
                llm_kind="reply",
                llm_channel="123456789012345678"
            )
            
            # Then: typing関数が正しいパラメータで呼び出される
            mock_typing.assert_called_once_with("lynq", "123456789012345678")

    @pytest.mark.asyncio
    async def test_common_sequence_stage4_discord_send(self):
        """Stage4: Discord メッセージ送信が正しく実行されること"""
        # Given: モック設定
        with patch('app.store.read_all') as mock_read_all, \
             patch('app.supervisor.generate') as mock_generate, \
             patch('app.discord.typing') as mock_typing, \
             patch('app.discord.send') as mock_send, \
             patch('app.store.append') as mock_append, \
             patch('app.logger.log_ok') as mock_log_ok:
            
            mock_read_all.return_value = []
            mock_generate.return_value = {"speaker": "spectra", "text": "final response"}
            mock_typing.return_value = 200
            mock_send.return_value = "msg_final"
            
            # When: common_sequence実行
            await app.common_sequence(
                event_type="user_msg",
                channel="development",
                actor="user456",
                payload_summary="user question",
                llm_kind="reply",
                llm_channel="123456789012345678"
            )
            
            # Then: send関数が正しいパラメータで呼び出される
            mock_send.assert_called_once_with("spectra", "123456789012345678", "final response")

    @pytest.mark.asyncio
    async def test_common_sequence_stage5_redis_append(self):
        """Stage5: Redis追記が正しく実行されること"""
        # Given: モック設定
        with patch('app.store.read_all') as mock_read_all, \
             patch('app.supervisor.generate') as mock_generate, \
             patch('app.discord.typing') as mock_typing, \
             patch('app.discord.send') as mock_send, \
             patch('app.store.append') as mock_append, \
             patch('app.logger.log_ok') as mock_log_ok:
            
            mock_read_all.return_value = []
            mock_generate.return_value = {"speaker": "paz", "text": "append test"}
            mock_typing.return_value = 200
            mock_send.return_value = "msg_append"
            
            # When: common_sequence実行
            await app.common_sequence(
                event_type="auto_tick",
                channel="lounge",
                actor="system",
                payload_summary="auto append test",
                llm_kind="auto",
                llm_channel="123456789012345678"
            )
            
            # Then: append関数が正しいパラメータで呼び出される
            mock_append.assert_called_once_with("paz", "123456789012345678", "append test")

    @pytest.mark.asyncio
    async def test_common_sequence_stage6_log_ok(self):
        """Stage6: log_okが正しく実行されること"""
        # Given: モック設定
        with patch('app.store.read_all') as mock_read_all, \
             patch('app.supervisor.generate') as mock_generate, \
             patch('app.discord.typing') as mock_typing, \
             patch('app.discord.send') as mock_send, \
             patch('app.store.append') as mock_append, \
             patch('app.logger.log_ok') as mock_log_ok:
            
            mock_read_all.return_value = []
            mock_generate.return_value = {"speaker": "spectra", "text": "success message"}
            mock_typing.return_value = 200
            mock_send.return_value = "msg_success"
            
            # When: common_sequence実行
            await app.common_sequence(
                event_type="slash",
                channel="command-center",
                actor="spectra",
                payload_summary="success test",
                llm_kind="reply",
                llm_channel="123456789012345678"
            )
            
            # Then: log_ok関数が正しいパラメータで呼び出される
            mock_log_ok.assert_called_once_with(
                "slash",
                "command-center", 
                "spectra",
                "reply:12chars"  # ペイロード要約フォーマット（"success test"=12文字）
            )


class TestCommonSequenceErrorHandling:
    """共通シーケンスエラーハンドリングのテスト"""

    @pytest.mark.asyncio
    async def test_common_sequence_stage1_error_memory(self):
        """Stage1エラー時にerror_stage='memory'でlog_errが呼ばれること"""
        # Given: Stage1でエラーが発生するモック
        with patch('app.store.read_all') as mock_read_all, \
             patch('app.logger.log_err') as mock_log_err:
            
            mock_read_all.side_effect = Exception("Redis connection failed")
            
            # When & Then: Stage1エラーで例外が発生する
            with pytest.raises(SystemExit):
                await app.common_sequence(
                    event_type="test",
                    channel="test",
                    actor="test",
                    payload_summary="test",
                    llm_kind="reply",
                    llm_channel="test"
                )
            
            # Then: log_errがmemoryステージで呼ばれる
            mock_log_err.assert_called_once()
            call_args = mock_log_err.call_args
            assert call_args[0][4] == "memory"  # error_stage

    @pytest.mark.asyncio 
    async def test_common_sequence_stage2_error_plan(self):
        """Stage2エラー時にerror_stage='plan'でlog_errが呼ばれること"""
        # Given: Stage2でエラーが発生するモック
        with patch('app.store.read_all') as mock_read_all, \
             patch('app.supervisor.generate') as mock_generate, \
             patch('app.logger.log_err') as mock_log_err:
            
            mock_read_all.return_value = []
            mock_generate.side_effect = Exception("LLM generation failed")
            
            # When & Then: Stage2エラーで例外が発生する
            with pytest.raises(SystemExit):
                await app.common_sequence(
                    event_type="test",
                    channel="test", 
                    actor="test",
                    payload_summary="test",
                    llm_kind="reply",
                    llm_channel="test"
                )
            
            # Then: log_errがplanステージで呼ばれる
            mock_log_err.assert_called_once()
            call_args = mock_log_err.call_args
            assert call_args[0][4] == "plan"  # error_stage

    @pytest.mark.asyncio
    async def test_common_sequence_stage3_error_typing(self):
        """Stage3エラー時にerror_stage='typing'でlog_errが呼ばれること"""
        # Given: Stage3でエラーが発生するモック
        with patch('app.store.read_all') as mock_read_all, \
             patch('app.supervisor.generate') as mock_generate, \
             patch('app.discord.typing') as mock_typing, \
             patch('app.logger.log_err') as mock_log_err:
            
            mock_read_all.return_value = []
            mock_generate.return_value = {"speaker": "spectra", "text": "test"}
            mock_typing.side_effect = Exception("Typing API failed")
            
            # When & Then: Stage3エラーで例外が発生する
            with pytest.raises(SystemExit):
                await app.common_sequence(
                    event_type="test",
                    channel="test",
                    actor="test", 
                    payload_summary="test",
                    llm_kind="reply",
                    llm_channel="test"
                )
            
            # Then: log_errがtypingステージで呼ばれる
            mock_log_err.assert_called_once()
            call_args = mock_log_err.call_args
            assert call_args[0][4] == "typing"  # error_stage

    @pytest.mark.asyncio
    async def test_common_sequence_stage4_error_send(self):
        """Stage4エラー時にerror_stage='send'でlog_errが呼ばれること"""
        # Given: Stage4でエラーが発生するモック
        with patch('app.store.read_all') as mock_read_all, \
             patch('app.supervisor.generate') as mock_generate, \
             patch('app.discord.typing') as mock_typing, \
             patch('app.discord.send') as mock_send, \
             patch('app.logger.log_err') as mock_log_err:
            
            mock_read_all.return_value = []
            mock_generate.return_value = {"speaker": "lynq", "text": "test"}
            mock_typing.return_value = 200
            mock_send.side_effect = Exception("Send API failed")
            
            # When & Then: Stage4エラーで例外が発生する
            with pytest.raises(SystemExit):
                await app.common_sequence(
                    event_type="test",
                    channel="test",
                    actor="test",
                    payload_summary="test", 
                    llm_kind="reply",
                    llm_channel="test"
                )
            
            # Then: log_errがsendステージで呼ばれる
            mock_log_err.assert_called_once()
            call_args = mock_log_err.call_args
            assert call_args[0][4] == "send"  # error_stage

    @pytest.mark.asyncio
    async def test_common_sequence_stage5_error_memory_append(self):
        """Stage5エラー時にerror_stage='memory'でlog_errが呼ばれること"""
        # Given: Stage5でエラーが発生するモック
        with patch('app.store.read_all') as mock_read_all, \
             patch('app.supervisor.generate') as mock_generate, \
             patch('app.discord.typing') as mock_typing, \
             patch('app.discord.send') as mock_send, \
             patch('app.store.append') as mock_append, \
             patch('app.logger.log_err') as mock_log_err:
            
            mock_read_all.return_value = []
            mock_generate.return_value = {"speaker": "paz", "text": "test"}
            mock_typing.return_value = 200
            mock_send.return_value = "msg_123"
            mock_append.side_effect = Exception("Redis append failed")
            
            # When & Then: Stage5エラーで例外が発生する
            with pytest.raises(SystemExit):
                await app.common_sequence(
                    event_type="test",
                    channel="test",
                    actor="test",
                    payload_summary="test",
                    llm_kind="reply", 
                    llm_channel="test"
                )
            
            # Then: log_errがmemoryステージで呼ばれる
            mock_log_err.assert_called_once()
            call_args = mock_log_err.call_args
            assert call_args[0][4] == "memory"  # error_stage

    @pytest.mark.asyncio
    async def test_common_sequence_fail_fast_no_retry(self):
        """エラー時にリトライせずFail-Fastで即座停止すること"""
        # Given: 複数段階でエラーが発生する可能性
        with patch('app.store.read_all') as mock_read_all, \
             patch('app.logger.log_err') as mock_log_err:
            
            mock_read_all.side_effect = Exception("Redis failed")
            
            # When & Then: 1回のエラーで即座に停止
            with pytest.raises(SystemExit):
                await app.common_sequence(
                    event_type="test",
                    channel="test",
                    actor="test",
                    payload_summary="test",
                    llm_kind="reply",
                    llm_channel="test"
                )
            
            # Then: read_allが1回だけ呼ばれた（リトライなし）
            assert mock_read_all.call_count == 1
            assert mock_log_err.call_count == 1


class TestCommonSequenceIntegration:
    """共通シーケンス統合テスト"""

    @pytest.mark.asyncio
    async def test_common_sequence_with_report_kind(self):
        """kind='report'での共通シーケンス実行テスト"""
        # Given: reportモードでのモック設定
        with patch('app.store.read_all') as mock_read_all, \
             patch('app.supervisor.generate') as mock_generate, \
             patch('app.discord.typing') as mock_typing, \
             patch('app.discord.send') as mock_send, \
             patch('app.store.append') as mock_append, \
             patch('app.logger.log_ok') as mock_log_ok:
            
            mock_read_all.return_value = [{"agent": "system", "channel": "cc", "text": "daily summary"}]
            mock_generate.return_value = {"speaker": "spectra", "text": "日報: 本日の活動を報告します。"}
            mock_typing.return_value = 200
            mock_send.return_value = "msg_report"
            
            # When: report kindで共通シーケンス実行
            await app.common_sequence(
                event_type="daily_report",
                channel="command-center",
                actor="spectra",
                payload_summary="daily report generation", 
                llm_kind="report",
                llm_channel="123456789012345678"
            )
            
            # Then: report特有の処理が正しく実行される
            call_args = mock_generate.call_args
            assert call_args.kwargs['kind'] == "report"
            assert 'report_config' in call_args.kwargs
            
            # log_okでreport種別が記録される
            mock_log_ok.assert_called_once()
            log_call_args = mock_log_ok.call_args
            assert "report:" in log_call_args[0][3]  # payload_summary

    def test_common_sequence_parameter_validation(self):
        """common_sequence関数のパラメータ検証"""
        # Given: common_sequence関数
        
        # When: 関数シグネチャを確認
        import inspect
        sig = inspect.signature(app.common_sequence)
        
        # Then: 必要なパラメータがすべて定義されている
        expected_params = [
            'event_type', 'channel', 'actor', 'payload_summary',
            'llm_kind', 'llm_channel'
        ]
        
        actual_params = list(sig.parameters.keys())
        for param in expected_params:
            assert param in actual_params, f"Parameter {param} is required in common_sequence"