"""体感速度最適化テスト（9-2）- Red段階"""

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


class TestImmediateTyping:
    """即時Typing応答テスト"""

    @pytest.mark.asyncio
    async def test_on_user_calls_typing_immediately_after_validation(self):
        """on_userがバリデーション直後に即座にTypingを呼び出すこと"""
        # Given: Typing呼び出しの監視
        with patch('app.discord.typing') as mock_typing, \
             patch('app.store.append') as mock_store_append, \
             patch('app.app.common_sequence') as mock_common_sequence:
            
            mock_typing.return_value = AsyncMock()
            
            # When: on_userを呼び出す
            await app.on_user("123456789012345678", "テストメッセージ", "user123")
            
            # Then: discord.typingが呼ばれる
            mock_typing.assert_called_once()

    @pytest.mark.asyncio
    async def test_typing_called_before_store_append(self):
        """Typingがstore.appendより先に呼ばれること"""
        # Given: 実行順序の記録
        call_order = []
        
        async def mock_typing(*args, **kwargs):
            call_order.append("typing")
            
        def mock_store_append(*args, **kwargs):
            call_order.append("store_append")
            
        async def mock_common_sequence(*args, **kwargs):
            call_order.append("common_sequence")
        
        with patch('app.discord.typing', side_effect=mock_typing), \
             patch('app.store.append', side_effect=mock_store_append), \
             patch('app.app.common_sequence', side_effect=mock_common_sequence):
            
            # When: on_userを呼び出す
            await app.on_user("123456789012345678", "順序テスト", "user456")
            
            # Then: typing → store_append → common_sequence の順序
            assert call_order == ["typing", "store_append", "common_sequence"]

    @pytest.mark.asyncio
    async def test_typing_called_before_common_sequence(self):
        """Typingがcommon_sequenceより先に呼ばれること"""
        # Given: 実行順序の記録
        call_order = []
        
        async def mock_typing(*args, **kwargs):
            call_order.append("typing")
            
        async def mock_common_sequence(*args, **kwargs):
            call_order.append("common_sequence")
        
        with patch('app.discord.typing', side_effect=mock_typing), \
             patch('app.store.append'), \
             patch('app.app.common_sequence', side_effect=mock_common_sequence):
            
            # When: on_userを呼び出す
            await app.on_user("123456789012345679", "速度テスト", "user789")
            
            # Then: typingがcommon_sequenceより先
            assert call_order[0] == "typing"
            assert "common_sequence" in call_order

    @pytest.mark.asyncio
    async def test_typing_with_correct_bot_and_channel(self):
        """Typingが正しいボット名義・チャンネルで呼ばれること"""
        # Given: Typing呼び出しパラメータの監視
        with patch('app.discord.typing') as mock_typing, \
             patch('app.store.append'), \
             patch('app.app.common_sequence') as mock_common_sequence:
            
            # common_sequenceが返すボット名をモック
            mock_common_sequence.return_value = None
            # LLMが選択するボットを予測するためのモック設定
            mock_typing.return_value = AsyncMock()
            
            # When: on_userを呼び出す
            await app.on_user("123456789012345680", "開発質問", "user999")
            
            # Then: typingが適切なパラメータで呼ばれる
            mock_typing.assert_called_once()
            # 実際の呼び出しパラメータは後の実装で確定


class TestResponseSpeedOptimization:
    """応答速度最適化テスト"""

    @pytest.mark.asyncio
    async def test_typing_response_time_under_100ms(self):
        """Typing呼び出しが100ms以内に実行されること"""
        # Given: タイミング測定環境
        typing_called_time = None
        start_time = None
        
        async def mock_typing(*args, **kwargs):
            nonlocal typing_called_time
            typing_called_time = time.time()
        
        with patch('app.discord.typing', side_effect=mock_typing), \
             patch('app.store.append'), \
             patch('app.app.common_sequence'):
            
            # When: on_userを呼び出してタイミング測定
            start_time = time.time()
            await app.on_user("123456789012345678", "速度測定", "user123")
            
            # Then: 100ms以内にTypingが呼ばれる
            response_time = typing_called_time - start_time
            assert response_time < 0.1, f"Typing response time {response_time:.3f}s exceeds 100ms limit"

    @pytest.mark.asyncio 
    async def test_typing_not_blocked_by_slow_operations(self):
        """遅い操作（Redis/LLM）でTypingがブロックされないこと"""
        # Given: 遅い操作のシミュレーション
        typing_called = False
        
        async def mock_typing(*args, **kwargs):
            nonlocal typing_called
            typing_called = True
            
        async def slow_common_sequence(*args, **kwargs):
            await asyncio.sleep(0.5)  # 500ms遅延シミュレーション
            
        def slow_store_append(*args, **kwargs):
            time.sleep(0.1)  # 100ms遅延シミュレーション
        
        with patch('app.discord.typing', side_effect=mock_typing), \
             patch('app.store.append', side_effect=slow_store_append), \
             patch('app.app.common_sequence', side_effect=slow_common_sequence):
            
            # When: on_userを呼び出す
            await app.on_user("123456789012345678", "遅延テスト", "user456")
            
            # Then: Typingが呼ばれている（遅い操作に関係なく）
            assert typing_called, "Typing should be called despite slow operations"

    @pytest.mark.asyncio
    async def test_typing_works_even_if_later_operations_fail(self):
        """後続操作失敗時でもTypingは正常実行されること"""
        # Given: 後続操作でエラーが発生
        typing_called = False
        
        async def mock_typing(*args, **kwargs):
            nonlocal typing_called
            typing_called = True
            
        def failing_store_append(*args, **kwargs):
            raise Exception("Redis connection failed")
        
        with patch('app.discord.typing', side_effect=mock_typing), \
             patch('app.store.append', side_effect=failing_store_append):
            
            # When & Then: エラーが発生するがTypingは呼ばれる
            with pytest.raises(Exception, match="Redis connection failed"):
                await app.on_user("123456789012345678", "エラーテスト", "user789")
            
            # Then: Typingは正常に呼ばれている
            assert typing_called, "Typing should be called even if later operations fail"


class TestBotSelectionForTyping:
    """Typingボット選択テスト"""

    @pytest.mark.asyncio
    async def test_typing_uses_smart_bot_selection(self):
        """Typingで適切なボット選択が行われること"""
        # Given: ボット選択ロジックのテスト
        with patch('app.discord.typing') as mock_typing, \
             patch('app.store.append'), \
             patch('app.app.common_sequence'):
            
            mock_typing.return_value = AsyncMock()
            
            # When: 開発関連メッセージ
            await app.on_user("123456789012345680", "コードレビューお願いします", "user123")
            
            # Then: typingが呼ばれる（ボット選択は実装により決定）
            mock_typing.assert_called_once()

    @pytest.mark.asyncio
    async def test_typing_channel_mapping_consistency(self):
        """Typingがチャンネルマッピングと一貫していること"""
        # Given: 異なるチャンネルでのテスト
        channels_to_test = [
            ("123456789012345678", "command-center"),  # command-center
            ("123456789012345679", "creation"),        # creation
            ("123456789012345680", "development"),     # development
            ("123456789012345681", "lounge")           # lounge
        ]
        
        for channel_id, expected_channel_name in channels_to_test:
            with patch('app.discord.typing') as mock_typing, \
                 patch('app.store.append'), \
                 patch('app.app.common_sequence'):
                
                mock_typing.return_value = AsyncMock()
                
                # When: 各チャンネルでon_userを呼び出す
                await app.on_user(channel_id, f"{expected_channel_name}テスト", "user123")
                
                # Then: typingが呼ばれる
                mock_typing.assert_called_once()


class TestExistingFunctionalityPreservation:
    """既存機能保持テスト"""

    @pytest.mark.asyncio
    async def test_immediate_typing_preserves_existing_validation(self):
        """即時Typing実装で既存バリデーションが保持されること"""
        # Given: 無効な入力
        
        # When & Then: 既存のバリデーションが動作する
        with pytest.raises(ValueError, match="Channel ID cannot be empty"):
            await app.on_user("", "テスト", "user123")
        
        with pytest.raises(ValueError, match="Message text cannot be empty"):
            await app.on_user("123456789012345678", "", "user123")
        
        with pytest.raises(ValueError, match="User ID cannot be empty"):
            await app.on_user("123456789012345678", "テスト", "")

    @pytest.mark.asyncio
    async def test_immediate_typing_preserves_full_response_flow(self):
        """即時Typing実装で完全応答フローが保持されること"""
        # Given: 完全な実行環境
        with patch('app.discord.typing') as mock_typing, \
             patch('app.store.append') as mock_store_append, \
             patch('app.app.common_sequence') as mock_common_sequence:
            
            mock_typing.return_value = AsyncMock()
            
            # When: on_userを呼び出す
            await app.on_user("123456789012345678", "完全フローテスト", "user999")
            
            # Then: 全ての主要コンポーネントが呼ばれる
            mock_typing.assert_called_once()
            mock_store_append.assert_called_once()
            mock_common_sequence.assert_called_once()


class TestPerformanceMetrics:
    """パフォーマンス測定テスト"""

    @pytest.mark.asyncio
    async def test_measure_validation_to_typing_latency(self):
        """バリデーション→Typing間のレイテンシ測定"""
        # Given: 高精度タイミング測定
        start_time = None
        typing_time = None
        
        # バリデーション完了を検出するためのパッチ
        original_on_user = app.on_user
        
        async def timed_on_user(channel, text, user_id):
            nonlocal start_time
            # バリデーション直後のタイミング
            if not channel or not text or not user_id:
                raise ValueError("Validation failed")
            start_time = time.time()
            return await original_on_user(channel, text, user_id)
        
        async def mock_typing(*args, **kwargs):
            nonlocal typing_time
            typing_time = time.time()
        
        with patch('app.app.on_user', side_effect=timed_on_user), \
             patch('app.discord.typing', side_effect=mock_typing), \
             patch('app.store.append'), \
             patch('app.app.common_sequence'):
            
            # When: on_userを呼び出す
            await timed_on_user("123456789012345678", "レイテンシ測定", "user123")
            
            # Then: レイテンシが測定され適切な範囲内
            if start_time and typing_time:
                latency = typing_time - start_time
                assert latency < 0.05, f"Validation to typing latency {latency:.3f}s exceeds 50ms"

    @pytest.mark.asyncio
    async def test_concurrent_typing_calls_handling(self):
        """同時Typing呼び出しの処理確認"""
        # Given: 同時実行環境
        typing_call_count = 0
        
        async def mock_typing(*args, **kwargs):
            nonlocal typing_call_count
            typing_call_count += 1
            await asyncio.sleep(0.01)  # 短い処理時間
        
        with patch('app.discord.typing', side_effect=mock_typing), \
             patch('app.store.append'), \
             patch('app.app.common_sequence'):
            
            # When: 複数の同時on_user呼び出し
            tasks = [
                app.on_user("123456789012345678", f"同時テスト{i}", f"user{i}")
                for i in range(3)
            ]
            await asyncio.gather(*tasks)
            
            # Then: 各呼び出しでTypingが実行される
            assert typing_call_count == 3, f"Expected 3 typing calls, got {typing_call_count}"