"""スラッシュコマンドバリデーションテスト（8-1）- Red段階"""

import pytest
from unittest.mock import patch
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


class TestSlashValidationBasic:
    """基本的なSlashコマンドバリデーションテスト"""

    def test_parse_slash_command_function_exists(self):
        """parse_slash_command関数が定義されていること"""
        # Given: app.pyモジュール
        
        # When & Then: parse_slash_command関数が存在する
        assert hasattr(app, 'parse_slash_command'), "parse_slash_command function must be defined in app.py"
        assert callable(app.parse_slash_command), "parse_slash_command must be callable"

    def test_parse_slash_command_has_correct_signature(self):
        """parse_slash_command関数が正しいシグネチャを持つこと"""
        # Given: parse_slash_command関数
        
        # When: 関数シグネチャを確認
        import inspect
        sig = inspect.signature(app.parse_slash_command)
        
        # Then: 必要なパラメータを持つ
        required_params = ['channel', 'content']
        param_names = list(sig.parameters.keys())
        
        for param in required_params:
            assert param in param_names, f"parse_slash_command should have parameter: {param}"


class TestSlashValidationChannelValidation:
    """チャンネルバリデーションテスト"""

    def test_parse_slash_command_valid_channel_creation(self):
        """有効なchannel='creation'が受け入れられること"""
        # Given: 有効なチャンネル名
        
        # When: parse_slash_commandを呼び出す
        result = app.parse_slash_command(channel="creation", content="test content")
        
        # Then: 例外が発生しない
        assert result is not None
        assert result["channel"] == "creation"
        assert result["content"] == "test content"

    def test_parse_slash_command_valid_channel_development(self):
        """有効なchannel='development'が受け入れられること"""
        # Given: 有効なチャンネル名
        
        # When: parse_slash_commandを呼び出す
        result = app.parse_slash_command(channel="development", content="test content")
        
        # Then: 例外が発生しない
        assert result is not None
        assert result["channel"] == "development"
        assert result["content"] == "test content"

    def test_parse_slash_command_invalid_channel_command_center(self):
        """無効なchannel='command-center'が拒否されること"""
        # Given: 無効なチャンネル名
        
        # When & Then: 例外が発生する
        with pytest.raises(ValueError) as exc_info:
            app.parse_slash_command(channel="command-center", content="test")
        
        assert "Invalid channel" in str(exc_info.value)

    def test_parse_slash_command_invalid_channel_lounge(self):
        """無効なchannel='lounge'が拒否されること"""
        # Given: 無効なチャンネル名
        
        # When & Then: 例外が発生する
        with pytest.raises(ValueError) as exc_info:
            app.parse_slash_command(channel="lounge", content="test")
        
        assert "Invalid channel" in str(exc_info.value)

    def test_parse_slash_command_invalid_channel_random(self):
        """無効なchannel='random'が拒否されること"""
        # Given: 無効なチャンネル名
        
        # When & Then: 例外が発生する
        with pytest.raises(ValueError) as exc_info:
            app.parse_slash_command(channel="random", content="test")
        
        assert "Invalid channel" in str(exc_info.value)

    def test_parse_slash_command_empty_channel_string(self):
        """空文字列のchannelが拒否されること"""
        # Given: 空文字列チャンネル
        
        # When & Then: 例外が発生する
        with pytest.raises(ValueError) as exc_info:
            app.parse_slash_command(channel="", content="test")
        
        assert "Invalid channel" in str(exc_info.value)


class TestSlashValidationContentValidation:
    """コンテンツバリデーションテスト"""

    def test_parse_slash_command_valid_content_string(self):
        """有効なcontentが文字列として受け入れられること"""
        # Given: 有効な文字列コンテンツ
        
        # When: parse_slash_commandを呼び出す
        result = app.parse_slash_command(channel="creation", content="テストタスク内容")
        
        # Then: 例外が発生しない
        assert result is not None
        assert result["content"] == "テストタスク内容"

    def test_parse_slash_command_content_with_spaces(self):
        """スペースを含むcontentが受け入れられること"""
        # Given: スペースを含むコンテンツ
        
        # When: parse_slash_commandを呼び出す
        result = app.parse_slash_command(channel="development", content="複数 単語 の タスク")
        
        # Then: 例外が発生しない
        assert result is not None
        assert result["content"] == "複数 単語 の タスク"

    def test_parse_slash_command_content_non_string(self):
        """非文字列のcontentが拒否されること"""
        # Given: 非文字列コンテンツ
        
        # When & Then: 例外が発生する
        with pytest.raises(ValueError) as exc_info:
            app.parse_slash_command(channel="creation", content=123)
        
        assert "Content must be a string" in str(exc_info.value)

    def test_parse_slash_command_content_none_type(self):
        """None型のcontentは受け入れられること（オプショナル）"""
        # Given: None型コンテンツ
        
        # When: parse_slash_commandを呼び出す
        result = app.parse_slash_command(channel="creation", content=None)
        
        # Then: 例外が発生しない
        assert result is not None
        assert result["content"] is None

    def test_parse_slash_command_empty_content_string(self):
        """空文字列のcontentが拒否されること"""
        # Given: 空文字列コンテンツ
        
        # When & Then: 例外が発生する
        with pytest.raises(ValueError) as exc_info:
            app.parse_slash_command(channel="creation", content="")
        
        assert "Content cannot be empty string" in str(exc_info.value)


class TestSlashValidationRequiredParameters:
    """必須パラメータバリデーションテスト"""

    def test_parse_slash_command_at_least_one_required_both_provided(self):
        """channel、content両方が提供された場合は受け入れられること"""
        # Given: 両方のパラメータが提供される
        
        # When: parse_slash_commandを呼び出す
        result = app.parse_slash_command(channel="creation", content="test content")
        
        # Then: 例外が発生しない
        assert result is not None
        assert result["channel"] == "creation"
        assert result["content"] == "test content"

    def test_parse_slash_command_at_least_one_required_channel_only(self):
        """channelのみが提供された場合は受け入れられること"""
        # Given: channelのみが提供される
        
        # When: parse_slash_commandを呼び出す
        result = app.parse_slash_command(channel="development", content=None)
        
        # Then: 例外が発生しない
        assert result is not None
        assert result["channel"] == "development"
        assert result["content"] is None

    def test_parse_slash_command_at_least_one_required_content_only(self):
        """contentのみが提供された場合は受け入れられること"""
        # Given: contentのみが提供される
        
        # When: parse_slash_commandを呼び出す
        result = app.parse_slash_command(channel=None, content="タスク内容のみ")
        
        # Then: 例外が発生しない
        assert result is not None
        assert result["channel"] is None
        assert result["content"] == "タスク内容のみ"

    def test_parse_slash_command_at_least_one_required_both_none(self):
        """channel、content両方がNoneの場合は拒否されること"""
        # Given: 両方のパラメータがNone
        
        # When & Then: 例外が発生する
        with pytest.raises(ValueError) as exc_info:
            app.parse_slash_command(channel=None, content=None)
        
        assert "At least one of channel or content must be provided" in str(exc_info.value)

    def test_parse_slash_command_at_least_one_required_both_empty_equivalent(self):
        """channelが無効、contentが空文字列の場合は拒否されること"""
        # Given: 両方とも実質的に無効
        
        # When & Then: 例外が発生する
        with pytest.raises(ValueError):
            app.parse_slash_command(channel="invalid", content="")


class TestSlashValidationFailFast:
    """Fail-Fast原則のテスト"""

    def test_parse_slash_command_fail_fast_no_fallback(self):
        """エラー時にフォールバック処理が無いこと"""
        # Given: 無効な入力
        
        # When & Then: 例外が発生し、フォールバック値は返されない
        with pytest.raises(ValueError):
            app.parse_slash_command(channel="invalid", content=123)
        
        # フォールバック処理があるならここで値が返ってしまう

    def test_parse_slash_command_immediate_error_on_invalid_channel(self):
        """無効なchannelで即座にエラーが発生すること"""
        # Given: 無効なチャンネル
        
        # When & Then: 即座に例外が発生する
        with pytest.raises(ValueError) as exc_info:
            app.parse_slash_command(channel="bad_channel", content="valid content")
        
        # チャンネル検証が最初に実行されることを確認
        assert "Invalid channel" in str(exc_info.value)

    def test_parse_slash_command_immediate_error_on_invalid_content(self):
        """無効なcontentで即座にエラーが発生すること"""
        # Given: 無効なコンテンツ
        
        # When & Then: 即座に例外が発生する
        with pytest.raises(ValueError) as exc_info:
            app.parse_slash_command(channel="creation", content=False)
        
        # コンテンツ検証が実行されることを確認
        assert "Content must be a string" in str(exc_info.value)


class TestSlashValidationReturnFormat:
    """戻り値フォーマットテスト"""

    def test_parse_slash_command_return_format_complete(self):
        """完全な戻り値フォーマットが正しいこと"""
        # Given: 完全な入力
        
        # When: parse_slash_commandを呼び出す
        result = app.parse_slash_command(channel="creation", content="test task")
        
        # Then: 期待される形式で戻り値が返される
        assert isinstance(result, dict)
        assert "channel" in result
        assert "content" in result
        assert result["channel"] == "creation"
        assert result["content"] == "test task"

    def test_parse_slash_command_return_format_channel_only(self):
        """チャンネルのみの戻り値フォーマットが正しいこと"""
        # Given: チャンネルのみの入力
        
        # When: parse_slash_commandを呼び出す
        result = app.parse_slash_command(channel="development", content=None)
        
        # Then: 期待される形式で戻り値が返される
        assert isinstance(result, dict)
        assert "channel" in result
        assert "content" in result
        assert result["channel"] == "development"
        assert result["content"] is None

    def test_parse_slash_command_return_format_content_only(self):
        """コンテンツのみの戻り値フォーマットが正しいこと"""
        # Given: コンテンツのみの入力
        
        # When: parse_slash_commandを呼び出す
        result = app.parse_slash_command(channel=None, content="task content only")
        
        # Then: 期待される形式で戻り値が返される
        assert isinstance(result, dict)
        assert "channel" in result
        assert "content" in result
        assert result["channel"] is None
        assert result["content"] == "task content only"