"""Supervisor機能テスト（6-1）- Red段階"""

import pytest
from unittest.mock import MagicMock, patch
import os

# テスト用環境変数設定
os.environ.setdefault("GEMINI_TIMEOUT_SECONDS", "30")
os.environ.setdefault("GEMINI_API_KEY", "test_api_key")

from app.supervisor import build_prompt, generate


class TestSupervisorPrompt:
    """Supervisorプロンプト機能のテスト"""

    def test_build_prompt_includes_all_input_params(self):
        """プロンプト構築時に全ての入力パラメータが含まれること"""
        # Given: 全パラメータが設定された入力
        params = {
            "kind": "reply",
            "channel": "development",
            "task": "タスク実装",
            "context": "過去の会話文脈",
            "limits": {"dev": 200, "cc": 100},
            "persona": {"spectra": "システム担当", "lynq": "開発担当"},
            "report_config": {"max_length": 500},
        }

        # When: プロンプトを構築する
        prompt = build_prompt(**params)

        # Then: 全パラメータがプロンプトに含まれる
        assert "reply" in prompt
        assert "development" in prompt
        assert "タスク実装" in prompt
        assert "過去の会話文脈" in prompt
        assert "200" in prompt  # dev channel limit
        assert "100" in prompt  # cc channel limit

    def test_build_prompt_includes_channel_limits_warning(self):
        """プロンプトにチャンネル上限を途中で切らない指示が含まれること"""
        # Given: チャンネル制限情報
        params = {
            "kind": "auto",
            "channel": "creation",
            "task": "",
            "context": "",
            "limits": {"cr": 200, "dev": 200, "cc": 100, "lo": 30},
            "persona": {},
            "report_config": {},
        }

        # When: プロンプトを構築する
        prompt = build_prompt(**params)

        # Then: 上限を途中で切らない指示が含まれる
        assert (
            "途中で切らず" in prompt
            or "途中で切断" in prompt
            or "complete" in prompt.lower()
        )
        assert "200" in prompt  # creation channel limit確認

    def test_build_prompt_specifies_json_output_format(self):
        """プロンプトでJSON出力形式が指定されること"""
        # Given: 基本パラメータ
        params = {
            "kind": "report",
            "channel": "command-center",
            "task": "",
            "context": "",
            "limits": {"cc": 100},
            "persona": {"spectra": "リーダー"},
            "report_config": {"speaker": "spectra"},
        }

        # When: プロンプトを構築する
        prompt = build_prompt(**params)

        # Then: JSON形式の出力指示が含まれる
        assert "JSON" in prompt
        assert "speaker" in prompt
        assert "text" in prompt
        assert "spectra" in prompt or "lynq" in prompt or "paz" in prompt


class TestSupervisorGenerate:
    """Supervisor生成機能のテスト"""

    @pytest.mark.asyncio
    async def test_generate_returns_valid_json_structure(self):
        """generate関数が正しいJSON構造を返すこと"""
        # Given: モックされたGemini APIレスポンス（正常JSON）
        mock_response = MagicMock()
        mock_response.text = '{"speaker": "spectra", "text": "テスト応答"}'

        # When: generate関数を呼び出す
        with patch("google.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            result = await generate(
                kind="reply",
                channel="development",
                task="実装",
                context="文脈",
                limits={"dev": 200},
                persona={"spectra": "担当"},
                report_config={},
            )

        # Then: 正しい構造のJSONが返る
        assert result["speaker"] in ["spectra", "lynq", "paz"]
        assert "text" in result
        assert isinstance(result["text"], str)

    @pytest.mark.asyncio
    async def test_generate_raises_exception_on_invalid_json(self):
        """generate関数がJSONパース失敗時に例外を発生すること"""
        # Given: モックされたGemini APIレスポンス（不正JSON）
        mock_response = MagicMock()
        mock_response.text = "invalid json response"

        # When & Then: 不正JSONで例外が発生する
        with patch("google.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            with pytest.raises(ValueError, match="JSON parsing failed"):
                await generate(
                    kind="auto",
                    channel="lounge",
                    task="",
                    context="",
                    limits={"lo": 30},
                    persona={},
                    report_config={},
                )

    @pytest.mark.asyncio
    async def test_generate_uses_gemini_2_flash_model(self):
        """generate関数がGemini 2.0 Flashモデルを使用すること"""
        # Given: モックされたGemini APIレスポンス
        mock_response = MagicMock()
        mock_response.text = '{"speaker": "lynq", "text": "応答"}'

        # When: generate関数を呼び出す
        with patch("google.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            await generate(
                kind="reply",
                channel="creation",
                task="",
                context="",
                limits={"cr": 200},
                persona={},
                report_config={},
            )

        # Then: 正しいモデルが指定される
        call_args = mock_client.models.generate_content.call_args
        assert "gemini-2" in str(call_args)  # Gemini 2.x系モデル確認

    @pytest.mark.asyncio
    async def test_generate_configures_json_response_mode(self):
        """generate関数がJSON応答モードを設定すること"""
        # Given: モックされたGemini APIレスポンス
        mock_response = MagicMock()
        mock_response.text = '{"speaker": "paz", "text": "実装完了"}'

        # When: generate関数を呼び出す
        with patch("google.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            await generate(
                kind="report",
                channel="command-center",
                task="日報",
                context="",
                limits={"cc": 100},
                persona={"spectra": "リーダー"},
                report_config={"max_length": 500},
            )

        # Then: JSONレスポンス設定が正しく指定される
        call_args = mock_client.models.generate_content.call_args
        config = call_args.kwargs.get("config")
        assert config is not None
        assert config.response_mime_type == "application/json"


class TestSupervisorGenerateKinds:
    """Supervisor生成機能のkind別テスト（6-2）"""

    @pytest.mark.asyncio
    async def test_generate_reply_kind_returns_appropriate_response(self):
        """kind=replyで適切な応答が生成されること"""
        # Given: モックされたGemini APIレスポンス（reply用）
        mock_response = MagicMock()
        mock_response.text = '{"speaker": "lynq", "text": "ユーザーへの返答です"}'

        # When: kind=replyでgenerate関数を呼び出す
        with patch("google.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            result = await generate(
                kind="reply",
                channel="development", 
                task="ユーザー質問への応答",
                context="過去の会話",
                limits={"dev": 200},
                persona={"lynq": "開発担当"},
                report_config={},
            )

        # Then: reply用の応答が返る
        assert result["speaker"] in ["spectra", "lynq", "paz"]
        assert "text" in result
        assert len(result["text"]) > 0

    @pytest.mark.asyncio 
    async def test_generate_auto_kind_returns_proactive_response(self):
        """kind=autoで自発的な応答が生成されること"""
        # Given: モックされたGemini APIレスポンス（auto用）
        mock_response = MagicMock()
        mock_response.text = '{"speaker": "paz", "text": "自発的な発言内容です"}'

        # When: kind=autoでgenerate関数を呼び出す
        with patch("google.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            result = await generate(
                kind="auto",
                channel="lounge",
                task="",
                context="チャンネルの雰囲気",
                limits={"lo": 30},
                persona={"paz": "エンターテイナー"},
                report_config={},
            )

        # Then: auto用の応答が返る
        assert result["speaker"] in ["spectra", "lynq", "paz"]
        assert "text" in result
        assert len(result["text"]) > 0

    @pytest.mark.asyncio
    async def test_generate_report_kind_forces_spectra_speaker(self):
        """kind=reportでspeaker='spectra'が強制されること"""
        # Given: モックされたGemini APIレスポンス（report用、初期speaker無視）
        mock_response = MagicMock()
        mock_response.text = '{"speaker": "lynq", "text": "日報内容です"}'

        # When: kind=reportでgenerate関数を呼び出す
        with patch("google.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            result = await generate(
                kind="report",
                channel="command-center",
                task="日報作成",
                context="本日の活動内容",
                limits={"cc": 100},
                persona={"spectra": "リーダー"},
                report_config={"max_length": 500},
            )

        # Then: speakerが強制的にspectraになる
        assert result["speaker"] == "spectra"
        assert "text" in result

    @pytest.mark.asyncio
    async def test_generate_report_kind_enforces_500_char_limit(self):
        """kind=reportで500文字制限が適用されること"""
        # Given: モックされたGemini APIレスポンス（長い文章）
        long_text = "長い文章です。" * 100  # 500文字超過
        mock_response = MagicMock()
        mock_response.text = f'{{"speaker": "spectra", "text": "{long_text}"}}'

        # When: kind=reportでgenerate関数を呼び出す
        with patch("google.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            result = await generate(
                kind="report",
                channel="command-center",
                task="日報作成",
                context="本日の活動内容",
                limits={"cc": 100},
                persona={"spectra": "リーダー"},
                report_config={"max_length": 500},
            )

        # Then: 500文字以内に制限される
        assert len(result["text"]) <= 500
        assert result["speaker"] == "spectra"

    @pytest.mark.asyncio
    async def test_generate_applies_timeout_setting(self):
        """generate関数でタイムアウト設定が適用されること"""
        # Given: タイムアウトが発生するモック
        with patch("google.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            # 意図的にタイムアウト例外を発生させる
            mock_client.models.generate_content.side_effect = TimeoutError("Request timeout")

            # When & Then: タイムアウト例外が適切に処理される
            with pytest.raises(ValueError, match="LLM generation failed"):
                await generate(
                    kind="reply",
                    channel="development",
                    task="応答",
                    context="文脈",
                    limits={"dev": 200},
                    persona={},
                    report_config={},
                )

    @pytest.mark.asyncio  
    async def test_generate_no_retry_on_failure(self):
        """generate関数でリトライが行われないこと"""
        # Given: 失敗するAPI呼び出し
        with patch("google.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.models.generate_content.side_effect = Exception("API Error")

            # When & Then: 1回の失敗で即座に例外が発生（リトライなし）
            with pytest.raises(ValueError, match="LLM generation failed"):
                await generate(
                    kind="auto",
                    channel="lounge", 
                    task="",
                    context="",
                    limits={"lo": 30},
                    persona={},
                    report_config={},
                )

        # Then: API呼び出しが1回だけ実行された（リトライなし）
        assert mock_client.models.generate_content.call_count == 1
