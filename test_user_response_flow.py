"""ユーザー応答フローテスト（9-1）- Red段階"""

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


class TestUserResponseFlowBasic:
    """基本的なユーザー応答フローテスト"""

    def test_on_user_function_exists(self):
        """on_user関数が定義されていること"""
        # Given: app.pyモジュール
        
        # When & Then: on_user関数が存在する
        assert hasattr(app, 'on_user'), "on_user function must be defined in app.py"
        assert callable(app.on_user), "on_user must be callable"

    @pytest.mark.asyncio
    async def test_on_user_is_async_function(self):
        """on_user関数が非同期関数であること"""
        # Given: on_user関数
        
        # When & Then: 非同期関数である
        import inspect
        assert inspect.iscoroutinefunction(app.on_user), "on_user must be an async function"

    def test_on_user_has_correct_signature(self):
        """on_user関数が正しいシグネチャを持つこと"""
        # Given: on_user関数
        
        # When: 関数シグネチャを確認
        import inspect
        sig = inspect.signature(app.on_user)
        
        # Then: 必要なパラメータを持つ
        required_params = ['channel', 'text', 'user_id']
        param_names = list(sig.parameters.keys())
        
        for param in required_params:
            assert param in param_names, f"on_user should have parameter: {param}"

    def test_get_channel_name_from_id_function_exists(self):
        """get_channel_name_from_id関数が定義されていること"""
        # Given: app.pyモジュール
        
        # When & Then: get_channel_name_from_id関数が存在する
        assert hasattr(app, 'get_channel_name_from_id'), "get_channel_name_from_id function must be defined in app.py"
        assert callable(app.get_channel_name_from_id), "get_channel_name_from_id must be callable"


class TestChannelMapping:
    """チャンネルIDマッピングテスト"""

    def test_channel_mapping_command_center(self):
        """command-centerチャンネルIDが正しくマッピングされること"""
        # Given: command-centerのチャンネルID
        command_center_id = "123456789012345678"
        
        # When: get_channel_name_from_idを呼び出す
        result = app.get_channel_name_from_id(command_center_id)
        
        # Then: "command-center"が返される
        assert result == "command-center"

    def test_channel_mapping_creation(self):
        """creationチャンネルIDが正しくマッピングされること"""
        # Given: creationのチャンネルID
        creation_id = "123456789012345679"
        
        # When: get_channel_name_from_idを呼び出す
        result = app.get_channel_name_from_id(creation_id)
        
        # Then: "creation"が返される
        assert result == "creation"

    def test_channel_mapping_development(self):
        """developmentチャンネルIDが正しくマッピングされること"""
        # Given: developmentのチャンネルID
        development_id = "123456789012345680"
        
        # When: get_channel_name_from_idを呼び出す
        result = app.get_channel_name_from_id(development_id)
        
        # Then: "development"が返される
        assert result == "development"

    def test_channel_mapping_lounge(self):
        """loungeチャンネルIDが正しくマッピングされること"""
        # Given: loungeのチャンネルID
        lounge_id = "123456789012345681"
        
        # When: get_channel_name_from_idを呼び出す
        result = app.get_channel_name_from_id(lounge_id)
        
        # Then: "lounge"が返される
        assert result == "lounge"

    def test_channel_mapping_unknown_channel(self):
        """未知のチャンネルIDで適切にフォールバックすること"""
        # Given: 未知のチャンネルID
        unknown_id = "999999999999999999"
        
        # When: get_channel_name_from_idを呼び出す
        result = app.get_channel_name_from_id(unknown_id)
        
        # Then: "unknown"が返される
        assert result == "unknown"


class TestUserMessageStorage:
    """ユーザーメッセージストレージテスト"""

    @pytest.mark.asyncio
    async def test_on_user_stores_user_message_before_llm_processing(self):
        """LLM処理前にユーザーメッセージがRedisに格納されること"""
        # Given: ユーザーメッセージ
        with patch('app.store.append') as mock_store_append, \
             patch('app.app.common_sequence') as mock_common_sequence:
            
            # When: on_userを呼び出す
            await app.on_user("123456789012345678", "テストメッセージ", "user123")
            
            # Then: store.appendがuser名義で呼ばれる
            mock_store_append.assert_called_once_with("user", "command-center", "テストメッセージ")

    @pytest.mark.asyncio
    async def test_on_user_stores_user_message_with_correct_channel_mapping(self):
        """チャンネルマッピングが正しく適用されてストレージされること"""
        # Given: developmentチャンネルのユーザーメッセージ
        with patch('app.store.append') as mock_store_append, \
             patch('app.app.common_sequence') as mock_common_sequence:
            
            # When: on_userを呼び出す
            await app.on_user("123456789012345680", "開発メッセージ", "user456")
            
            # Then: store.appendが正しいチャンネル名で呼ばれる
            mock_store_append.assert_called_once_with("user", "development", "開発メッセージ")


class TestCommonSequenceIntegration:
    """共通シーケンス統合テスト"""

    @pytest.mark.asyncio
    async def test_on_user_calls_common_sequence_with_correct_parameters(self):
        """on_userが正しいパラメータでcommon_sequenceを呼び出すこと"""
        # Given: ユーザーメッセージ
        with patch('app.store.append') as mock_store_append, \
             patch('app.app.common_sequence') as mock_common_sequence:
            
            # When: on_userを呼び出す
            await app.on_user("123456789012345678", "返信してください", "user789")
            
            # Then: common_sequenceが正しいパラメータで呼ばれる
            mock_common_sequence.assert_called_once_with(
                event_type="user_msg",
                channel="command-center",
                actor="user",
                payload_summary="返信してください",
                llm_kind="reply",
                llm_channel="123456789012345678"
            )

    @pytest.mark.asyncio
    async def test_on_user_truncates_long_payload_summary(self):
        """長いメッセージのpayload_summaryが適切に切り詰められること"""
        # Given: 長いユーザーメッセージ
        long_message = "これは非常に長いメッセージです。" * 10  # 80文字超過
        
        with patch('app.store.append') as mock_store_append, \
             patch('app.app.common_sequence') as mock_common_sequence:
            
            # When: on_userを呼び出す
            await app.on_user("123456789012345679", long_message, "user456")
            
            # Then: payload_summaryが80文字以内に切り詰められる
            call_args = mock_common_sequence.call_args
            payload_summary = call_args.kwargs['payload_summary']
            assert len(payload_summary) <= 80

    @pytest.mark.asyncio
    async def test_on_user_execution_order_store_before_common_sequence(self):
        """store.appendがcommon_sequenceより先に実行されること"""
        # Given: ユーザーメッセージ
        call_order = []
        
        def mock_store_append(*args):
            call_order.append("store_append")
            
        async def mock_common_sequence(*args, **kwargs):
            call_order.append("common_sequence")
        
        with patch('app.store.append', side_effect=mock_store_append), \
             patch('app.app.common_sequence', side_effect=mock_common_sequence):
            
            # When: on_userを呼び出す
            await app.on_user("123456789012345678", "順序テスト", "user123")
            
            # Then: store_appendがcommon_sequenceより先に実行される
            assert call_order == ["store_append", "common_sequence"]


class TestUserResponseFlowFailFast:
    """Fail-Fast原則テスト"""

    @pytest.mark.asyncio
    async def test_on_user_fails_fast_on_store_error(self):
        """store.appendエラー時に即座に失敗すること"""
        # Given: store.appendでエラーが発生
        with patch('app.store.append') as mock_store_append:
            mock_store_append.side_effect = Exception("Redis connection failed")
            
            # When & Then: 例外が発生する
            with pytest.raises(Exception, match="Redis connection failed"):
                await app.on_user("123456789012345678", "テスト", "user123")

    @pytest.mark.asyncio
    async def test_on_user_fails_fast_on_common_sequence_error(self):
        """common_sequenceエラー時に即座に失敗すること"""
        # Given: common_sequenceでエラーが発生
        with patch('app.store.append') as mock_store_append, \
             patch('app.app.common_sequence') as mock_common_sequence:
            
            mock_common_sequence.side_effect = Exception("LLM processing failed")
            
            # When & Then: 例外が発生する（SystemExitはcommon_sequence内で処理）
            with pytest.raises(Exception):
                await app.on_user("123456789012345678", "テスト", "user456")


class TestUserResponseFlowIntegration:
    """統合テスト"""

    @pytest.mark.asyncio
    async def test_user_response_flow_complete_sequence(self):
        """完全なユーザー応答フローが正しく実行されること"""
        # Given: 完全な実行環境
        with patch('app.store.append') as mock_store_append, \
             patch('app.app.common_sequence') as mock_common_sequence:
            
            # When: on_userを呼び出す
            await app.on_user("123456789012345680", "開発の進捗を教えて", "user999")
            
            # Then: 完全なフローが実行される
            # 1. チャンネルマッピング確認
            expected_channel = "development"
            
            # 2. ユーザーメッセージ格納確認
            mock_store_append.assert_called_once_with("user", expected_channel, "開発の進捗を教えて")
            
            # 3. common_sequence呼び出し確認
            mock_common_sequence.assert_called_once_with(
                event_type="user_msg",
                channel=expected_channel,
                actor="user",
                payload_summary="開発の進捗を教えて",
                llm_kind="reply",
                llm_channel="123456789012345680"
            )

    @pytest.mark.asyncio
    async def test_user_response_typing_immediate_after_message(self):
        """ユーザーメッセージ直後にTypingが即座に呼ばれること（体感速度）"""
        # Given: common_sequenceがTypingを即座に実行する環境
        typing_called = False
        
        async def mock_common_sequence(*args, **kwargs):
            nonlocal typing_called
            typing_called = True  # Typingが呼ばれたと仮定
        
        with patch('app.store.append'), \
             patch('app.app.common_sequence', side_effect=mock_common_sequence):
            
            # When: on_userを呼び出す
            await app.on_user("123456789012345678", "即応答テスト", "user123")
            
            # Then: Typingが呼ばれている（common_sequence内で）
            assert typing_called, "Typing should be called immediately via common_sequence"


class TestExistingValidation:
    """既存バリデーション確認テスト"""

    @pytest.mark.asyncio
    async def test_on_user_existing_validation_still_works(self):
        """既存のFail-Fastバリデーションが継続して動作すること"""
        # Given: 無効な入力（既存実装で検証済み）
        
        # When & Then: 空のchannelでValueError
        with pytest.raises(ValueError, match="Channel ID cannot be empty"):
            await app.on_user("", "テスト", "user123")
        
        # When & Then: 空のtextでValueError
        with pytest.raises(ValueError, match="Message text cannot be empty"):
            await app.on_user("123456789012345678", "", "user123")
        
        # When & Then: 空のuser_idでValueError  
        with pytest.raises(ValueError, match="User ID cannot be empty"):
            await app.on_user("123456789012345678", "テスト", "")