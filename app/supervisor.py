# Supervisor - LLMプロンプト制御
# Gemini 2.0 Flash を用いたLLM応答生成

import json
import asyncio
from typing import Dict, Any
from google import genai
from google.genai import types
from app.settings import settings


def build_prompt(
    kind: str,
    channel: str,
    task: str,
    context: str,
    limits: Dict[str, int],
    persona: Dict[str, str],
    report_config: Dict[str, Any],
) -> str:
    """LLMプロンプト構築"""
    # Fail-Fast: 必須パラメータ検証
    if not kind:
        raise ValueError("Kind cannot be empty")
    if kind not in ["reply", "auto", "report"]:
        raise ValueError(f"Invalid kind: {kind}. Must be reply, auto, or report")
    if not channel:
        raise ValueError("Channel cannot be empty")
    if not isinstance(limits, dict):
        raise ValueError("Limits must be a dictionary")
    if not isinstance(persona, dict):
        raise ValueError("Persona must be a dictionary")
    if not isinstance(report_config, dict):
        raise ValueError("Report config must be a dictionary")

    # チャンネル制限情報
    channel_limits = {
        "command-center": limits.get("cc", 100),
        "creation": limits.get("cr", 200),
        "development": limits.get("dev", 200),
        "lounge": limits.get("lo", 30),
    }

    # 基本プロンプト構築
    prompt = f"""あなたはDiscord Multi-Agent Systemの一部として動作します。

**入力情報:**
- Kind: {kind}
- Channel: {channel}
- Task: {task}
- Context: {context}
- Channel Limits: {channel_limits}
- Persona: {persona}
- Report Config: {report_config}

**重要指示:**
1. レスポンスは必ず厳密なJSON形式で返してください
2. JSON構造: {{"speaker": "spectra|lynq|paz", "text": "応答内容"}}
3. チャンネル文字数制限を厳守し、途中で切らずに完全な内容を提供してください
4. 制限: cc={channel_limits['command-center']}, cr={channel_limits['creation']}, \\
   dev={channel_limits['development']}, lo={channel_limits['lounge']}文字
5. speakerは必ずspectra、lynq、pazのいずれかを選択してください

現在のチャンネル「{channel}」の制限は{channel_limits.get(channel, 100)}文字です。
この制限内で完全な応答を提供してください。"""

    return prompt


async def generate(
    kind: str,
    channel: str,
    task: str,
    context: str,
    limits: Dict[str, int],
    persona: Dict[str, str],
    report_config: Dict[str, Any],
) -> Dict[str, str]:
    """LLM応答生成（Gemini 2.0 Flash）"""
    # Fail-Fast: APIキー検証
    if not settings.ai_service.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not configured")

    # Fail-Fast: 入力パラメータ検証
    if not kind or not channel:
        raise ValueError("Kind and channel are required")

    # プロンプト構築
    prompt = build_prompt(kind, channel, task, context, limits, persona, report_config)

    # Gemini クライアント初期化
    client = genai.Client(api_key=settings.ai_service.gemini_api_key)

    # JSON応答スキーマ定義
    response_schema = {
        "type": "object",
        "properties": {
            "speaker": {"type": "string", "enum": ["spectra", "lynq", "paz"]},
            "text": {"type": "string"},
        },
        "required": ["speaker", "text"],
    }

    try:
        # Gemini 2.0 Flash で生成（タイムアウト設定付き）
        loop = asyncio.get_event_loop()

        # 同期APIを非同期タスクとして実行
        generate_task = loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model="gemini-2.0-flash-001",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    max_output_tokens=1000,
                    temperature=0.7,
                ),
            ),
        )

        # タイムアウト設定でLLM呼び出し実行
        response = await asyncio.wait_for(
            generate_task, timeout=settings.ai_service.gemini_timeout_seconds
        )

        # Fail-Fast: レスポンス検証
        if not response or not hasattr(response, "text"):
            raise ValueError("Invalid response from Gemini API")
        if not response.text:
            raise ValueError("Empty response from Gemini API")

        # JSON解析
        try:
            result = json.loads(response.text)

            # Fail-Fast: JSON構造検証
            if not isinstance(result, dict):
                raise ValueError("Response is not a JSON object")
            if "speaker" not in result or "text" not in result:
                raise ValueError("Response missing required fields: speaker, text")
            if result["speaker"] not in ["spectra", "lynq", "paz"]:
                raise ValueError(f"Invalid speaker: {result['speaker']}")
            if not isinstance(result["text"], str):
                raise ValueError("Response text must be a string")

            # 6-2: kind=reportの場合の特別処理
            if kind == "report":
                # speaker強制: spectraに固定
                result["speaker"] = "spectra"
                # 文字数制限: 500文字以内に切り詰め
                if len(result["text"]) > 500:
                    result["text"] = result["text"][:500]

            return result
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parsing failed: {e}") from e

    except Exception as e:
        raise ValueError(f"LLM generation failed: {e}") from e
