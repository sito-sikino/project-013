"""自発投稿テスト（10-2）- Red段階"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
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
from io import StringIO
import sys


class TestOnTickImplementation:
    """on_tick関数実装テスト"""

    @pytest.mark.asyncio
    async def test_on_tick_function_not_stub(self):
        """on_tick関数がスタブではなく実装されていること"""
        # Given: on_tick関数
        
        # When: on_tickを実行してコンソール出力をキャプチャ
        captured_output = StringIO()
        sys.stdout = captured_output
        
        try:
            # モックして実際の処理を回避
            with patch('app.state.get_active_channel', return_value='command-center'), \
                 patch('app.app.common_sequence') as mock_common_sequence:
                
                await app.on_tick()
                
        finally:
            sys.stdout = sys.__stdout__
        
        output = captured_output.getvalue()
        
        # Then: "TODO"や"本格実装"メッセージが出力されない（実装済み）
        assert "TODO" not in output, "on_tick should be fully implemented, not a TODO stub"
        assert "本格実装" not in output, "on_tick should be fully implemented"

    @pytest.mark.asyncio
    async def test_on_tick_is_async_function(self):
        """on_tick関数が非同期関数であること"""
        # Given: on_tick関数
        
        # When & Then: 非同期関数である
        import inspect
        assert inspect.iscoroutinefunction(app.on_tick), "on_tick must be an async function"

    @pytest.mark.asyncio
    async def test_on_tick_has_no_parameters(self):
        """on_tick関数がパラメータを持たないこと"""
        # Given: on_tick関数
        
        # When: 関数シグネチャを確認
        import inspect
        sig = inspect.signature(app.on_tick)
        
        # Then: パラメータがない
        assert len(sig.parameters) == 0, "on_tick should have no parameters"


class TestActiveChannelIntegration:
    """アクティブチャンネル統合テスト"""

    @pytest.mark.asyncio
    async def test_on_tick_uses_active_channel_from_state(self):
        """on_tick関数がstate.get_active_channel()を使用すること"""
        # Given: 特定のアクティブチャンネル
        with patch('app.state.get_active_channel', return_value='creation') as mock_get_channel, \
             patch('app.app.common_sequence') as mock_common_sequence:
            
            # When: on_tickを実行
            await app.on_tick()
            
            # Then: state.get_active_channelが呼ばれる
            mock_get_channel.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_tick_handles_different_active_channels(self):
        """on_tick関数が異なるアクティブチャンネルを適切に処理すること"""
        # Given: 異なるアクティブチャンネルのテスト
        test_channels = ['command-center', 'creation', 'development', 'lounge']
        
        for channel in test_channels:
            with patch('app.state.get_active_channel', return_value=channel), \
                 patch('app.app.common_sequence') as mock_common_sequence:
                
                # When: on_tickを実行
                await app.on_tick()
                
                # Then: common_sequenceが正しいチャンネルで呼ばれる
                assert mock_common_sequence.call_count == 1
                call_args = mock_common_sequence.call_args
                assert call_args.kwargs['channel'] == channel


class TestCommonSequenceIntegration:
    """共通シーケンス統合テスト"""

    @pytest.mark.asyncio
    async def test_on_tick_calls_common_sequence(self):
        """on_tick関数がcommon_sequenceを呼び出すこと"""
        # Given: アクティブチャンネル設定
        with patch('app.state.get_active_channel', return_value='command-center'), \
             patch('app.app.common_sequence') as mock_common_sequence:
            
            # When: on_tickを実行
            await app.on_tick()
            
            # Then: common_sequenceが呼ばれる
            mock_common_sequence.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_tick_common_sequence_with_correct_parameters(self):
        """on_tick関数がcommon_sequenceを正しいパラメータで呼び出すこと"""
        # Given: アクティブチャンネル設定
        with patch('app.state.get_active_channel', return_value='development'), \
             patch('app.app.common_sequence') as mock_common_sequence:
            
            # When: on_tickを実行
            await app.on_tick()
            
            # Then: common_sequenceが正しいパラメータで呼ばれる
            mock_common_sequence.assert_called_once()
            call_args = mock_common_sequence.call_args
            
            # 必須パラメータの確認
            assert call_args.kwargs['event_type'] == 'auto_tick'
            assert call_args.kwargs['channel'] == 'development'
            assert call_args.kwargs['actor'] == 'system'
            assert call_args.kwargs['llm_kind'] == 'auto'
            assert 'payload_summary' in call_args.kwargs
            assert 'llm_channel' in call_args.kwargs

    @pytest.mark.asyncio
    async def test_on_tick_payload_summary_format(self):
        """on_tick関数のpayload_summaryが適切な形式であること"""
        # Given: アクティブチャンネル設定
        with patch('app.state.get_active_channel', return_value='creation'), \
             patch('app.app.common_sequence') as mock_common_sequence:
            
            # When: on_tickを実行
            await app.on_tick()
            
            # Then: payload_summaryが適切な形式
            call_args = mock_common_sequence.call_args
            payload_summary = call_args.kwargs['payload_summary']
            
            # "auto_tick:チャンネル名" 形式
            assert payload_summary.startswith('auto_tick:')
            assert 'creation' in payload_summary


class TestChannelIdMapping:
    """チャンネルIDマッピングテスト"""

    def test_get_channel_id_from_name_function_exists(self):
        """get_channel_id_from_name関数が定義されていること"""
        # Given: app.pyモジュール
        
        # When & Then: get_channel_id_from_name関数が存在する
        assert hasattr(app, 'get_channel_id_from_name'), "get_channel_id_from_name function must be defined in app.py"
        assert callable(app.get_channel_id_from_name), "get_channel_id_from_name must be callable"

    def test_channel_id_mapping_command_center(self):
        """command-centerのチャンネルIDマッピングが正しいこと"""
        # Given: command-center論理チャンネル名
        
        # When: get_channel_id_from_nameを呼び出す
        result = app.get_channel_id_from_name('command-center')
        
        # Then: 正しいDiscord IDが返される
        assert result == "123456789012345678"

    def test_channel_id_mapping_all_channels(self):
        """全チャンネルのIDマッピングが正しいこと"""
        # Given: 全論理チャンネル名
        expected_mappings = {
            'command-center': '123456789012345678',
            'creation': '123456789012345679',
            'development': '123456789012345680',
            'lounge': '123456789012345681'
        }
        
        for channel_name, expected_id in expected_mappings.items():
            # When: get_channel_id_from_nameを呼び出す
            result = app.get_channel_id_from_name(channel_name)
            
            # Then: 正しいDiscord IDが返される
            assert result == expected_id, f"Channel {channel_name} should map to {expected_id}, got {result}"

    def test_channel_id_mapping_unknown_channel(self):
        """未知のチャンネル名でデフォルトIDが返されること"""
        # Given: 未知のチャンネル名
        unknown_channel = 'unknown_channel'
        
        # When: get_channel_id_from_nameを呼び出す
        result = app.get_channel_id_from_name(unknown_channel)
        
        # Then: デフォルト（command-center）IDが返される
        assert result == "123456789012345678", "Unknown channel should default to command-center ID"

    @pytest.mark.asyncio
    async def test_on_tick_uses_channel_id_mapping(self):
        """on_tick関数がチャンネルIDマッピングを使用すること"""
        # Given: アクティブチャンネル設定
        with patch('app.state.get_active_channel', return_value='lounge'), \
             patch('app.app.common_sequence') as mock_common_sequence:
            
            # When: on_tickを実行
            await app.on_tick()
            
            # Then: common_sequenceのllm_channelが正しいDiscord ID
            call_args = mock_common_sequence.call_args
            llm_channel = call_args.kwargs['llm_channel']
            assert llm_channel == "123456789012345681", f"Expected lounge ID, got {llm_channel}"


class TestBotSelection:
    """ボット選択テスト"""

    @pytest.mark.asyncio
    async def test_on_tick_uses_bot_selection_for_typing(self):
        """on_tick関数でボット選択が適切に行われること"""
        # Given: common_sequenceでボット選択が行われる環境
        
        # Then: common_sequenceが呼ばれればボット選択も実行される
        # （ボット選択はcommon_sequence内のLLMで実行されるため、直接テストは困難）
        # 代わりに、正しいllm_kindが渡されることを確認
        
        with patch('app.state.get_active_channel', return_value='creation'), \
             patch('app.app.common_sequence') as mock_common_sequence:
            
            # When: on_tickを実行
            await app.on_tick()
            
            # Then: llm_kind="auto"でボット選択が委譲される
            call_args = mock_common_sequence.call_args
            assert call_args.kwargs['llm_kind'] == 'auto', "Should use 'auto' llm_kind for autonomous posting"


class TestTickSchedulerIntegration:
    """TickScheduler統合テスト"""

    @pytest.mark.asyncio
    async def test_tick_scheduler_calls_on_tick_function(self):
        """TickSchedulerがon_tick関数を正しく呼び出すこと"""
        # Given: TickSchedulerとEventQueue
        with patch('app.app.on_tick') as mock_on_tick:
            
            # When: EventQueueにTICKイベントを手動追加
            await app.event_queue.enqueue(app.EventPriority.TICK, app.on_tick)
            
            # Then: on_tickが呼ばれる（EventQueue経由）
            # 実際にはEventQueueの処理を待つ必要があるため、統合テストで確認

    @pytest.mark.asyncio 
    async def test_on_tick_integrates_with_existing_priority_system(self):
        """on_tick関数が既存の優先度システムと統合されること"""
        # Given: 優先度システムの確認
        
        # When & Then: TICK優先度が最低であることを確認
        assert app.EventPriority.TICK.value > app.EventPriority.USER.value
        assert app.EventPriority.TICK.value > app.EventPriority.SLASH.value
        
        # TICKは最低優先度（3）
        assert app.EventPriority.TICK.value == 3


class TestErrorHandling:
    """エラーハンドリングテスト"""

    @pytest.mark.asyncio
    async def test_on_tick_handles_state_error(self):
        """on_tick関数でstate取得エラーが適切に処理されること"""
        # Given: state.get_active_channelでエラーが発生
        with patch('app.state.get_active_channel', side_effect=Exception("State error")):
            
            # When & Then: エラーが伝播される（Fail-Fast）
            with pytest.raises(Exception, match="State error"):
                await app.on_tick()

    @pytest.mark.asyncio
    async def test_on_tick_handles_common_sequence_error(self):
        """on_tick関数でcommon_sequenceエラーが適切に処理されること"""
        # Given: common_sequenceでエラーが発生
        with patch('app.state.get_active_channel', return_value='command-center'), \
             patch('app.app.common_sequence', side_effect=Exception("Common sequence error")):
            
            # When & Then: エラーが伝播される（Fail-Fast）
            with pytest.raises(Exception, match="Common sequence error"):
                await app.on_tick()


class TestLlmKindAndContext:
    """LLM種別・文脈テスト"""

    @pytest.mark.asyncio
    async def test_on_tick_uses_auto_llm_kind(self):
        """on_tick関数でllm_kind='auto'が使用されること"""
        # Given: アクティブチャンネル設定
        with patch('app.state.get_active_channel', return_value='command-center'), \
             patch('app.app.common_sequence') as mock_common_sequence:
            
            # When: on_tickを実行
            await app.on_tick()
            
            # Then: llm_kind='auto'が使用される
            call_args = mock_common_sequence.call_args
            assert call_args.kwargs['llm_kind'] == 'auto', "Should use 'auto' for autonomous posting"

    @pytest.mark.asyncio
    async def test_on_tick_actor_is_system(self):
        """on_tick関数でactor='system'が使用されること"""
        # Given: アクティブチャンネル設定
        with patch('app.state.get_active_channel', return_value='development'), \
             patch('app.app.common_sequence') as mock_common_sequence:
            
            # When: on_tickを実行
            await app.on_tick()
            
            # Then: actor='system'が使用される
            call_args = mock_common_sequence.call_args
            assert call_args.kwargs['actor'] == 'system', "Should use 'system' as actor for autonomous posting"

    @pytest.mark.asyncio
    async def test_on_tick_event_type_is_auto_tick(self):
        """on_tick関数でevent_type='auto_tick'が使用されること"""
        # Given: アクティブチャンネル設定
        with patch('app.state.get_active_channel', return_value='lounge'), \
             patch('app.app.common_sequence') as mock_common_sequence:
            
            # When: on_tickを実行
            await app.on_tick()
            
            # Then: event_type='auto_tick'が使用される
            call_args = mock_common_sequence.call_args
            assert call_args.kwargs['event_type'] == 'auto_tick', "Should use 'auto_tick' as event type"


class TestE2EConsistency:
    """E2E一貫性テスト"""

    @pytest.mark.asyncio
    async def test_on_tick_e2e_consistency(self):
        """on_tick関数のE2E一貫性確認"""
        # Given: 完全な実行環境
        with patch('app.state.get_active_channel', return_value='creation') as mock_get_channel, \
             patch('app.app.common_sequence') as mock_common_sequence:
            
            # When: on_tickを実行
            await app.on_tick()
            
            # Then: 一貫した実行フローが実行される
            
            # 1. State取得
            mock_get_channel.assert_called_once()
            
            # 2. Common sequence呼び出し
            mock_common_sequence.assert_called_once()
            
            # 3. パラメータの一貫性確認
            call_args = mock_common_sequence.call_args
            
            # active_channel='creation'が一貫して使用される
            assert call_args.kwargs['channel'] == 'creation'
            assert call_args.kwargs['llm_channel'] == '123456789012345679'  # creation ID
            
            # 自発投稿用パラメータが一貫している
            assert call_args.kwargs['event_type'] == 'auto_tick'
            assert call_args.kwargs['actor'] == 'system'
            assert call_args.kwargs['llm_kind'] == 'auto'
            assert 'auto_tick:creation' == call_args.kwargs['payload_summary']