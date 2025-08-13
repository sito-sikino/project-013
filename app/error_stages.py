"""エラー段階判定システム（12-1: 段階タグ）"""

from typing import Literal

# エラー段階の型定義
ErrorStage = Literal["settings", "slash", "plan", "typing", "send", "report", "memory"]


def determine_error_stage(exception: Exception, context: str = "general") -> ErrorStage:
    """例外とコンテキストからエラー段階を判定する
    
    AC要件に従い、error_stage ∈ {settings,slash,plan,typing,send,report,memory}の
    7段階のうち適切な段階を例外内容とコンテキストから推定します。
    
    Args:
        exception: 発生した例外
        context: エラー発生コンテキスト（"common_sequence", "slash_command", etc.）
        
    Returns:
        ErrorStage: 判定されたエラー段階
        
    Examples:
        >>> determine_error_stage(Exception("Redis connection failed"), "common_sequence")
        "memory"
        >>> determine_error_stage(Exception("Invalid channel"), "slash_command")
        "slash"
        >>> determine_error_stage(Exception("LLM generation failed"), "common_sequence")
        "plan"
    """
    error_message = str(exception).lower()
    
    # コンテキスト別の優先判定
    if context == "settings":
        return "settings"
    elif context == "slash_command":
        return "slash"  
    elif context == "report":
        return "report"
    
    # 例外メッセージ内容による判定（common_sequenceなど汎用コンテキスト）
    if any(keyword in error_message for keyword in ["redis", "store", "memory", "connection"]):
        return "memory"
    elif any(keyword in error_message for keyword in ["llm", "gemini", "generate", "ai", "model"]):
        return "plan"
    elif any(keyword in error_message for keyword in ["typing", "type"]):
        return "typing" 
    elif any(keyword in error_message for keyword in ["send", "discord", "message", "post"]):
        return "send"
    elif any(keyword in error_message for keyword in ["validation", "invalid", "parse", "format"]):
        # バリデーションエラーはコンテキストに応じて判定
        if context == "slash_command":
            return "slash"
        else:
            return "memory"  # データフォーマット問題として扱う
    
    # デフォルト: メモリ段階（データ・接続関連の問題として扱う）
    return "memory"


def get_all_error_stages() -> list[ErrorStage]:
    """すべてのエラー段階を取得する
    
    Returns:
        list[ErrorStage]: AC要件で定義された7つのエラー段階
    """
    return ["settings", "slash", "plan", "typing", "send", "report", "memory"]


def validate_error_stage(stage: str) -> ErrorStage:
    """エラー段階の妥当性を検証する
    
    Args:
        stage: 検証対象のエラー段階文字列
        
    Returns:
        ErrorStage: 検証済みエラー段階
        
    Raises:
        ValueError: 無効なエラー段階が指定された場合
    """
    valid_stages = get_all_error_stages()
    if stage not in valid_stages:
        raise ValueError(f"Invalid error_stage: {stage}. Must be one of {valid_stages}")
    return stage  # type: ignore