# Logger - JSONL形式ログ出力
# 一元ログ: ts,event_type,channel,actor,payload_summary,result,error_stage,error_detail

import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import orjson
from zoneinfo import ZoneInfo

from app.settings import settings


# スレッドセーフなファイル書き込み用のロック
_log_lock = threading.Lock()


def _ensure_log_directory() -> None:
    """ログディレクトリの存在確認と作成"""
    log_path = Path(settings.logging.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)


def _get_jst_timestamp() -> str:
    """JST（Asia/Tokyo）タイムゾーンでのISO8601タイムスタンプを取得"""
    jst_tz = ZoneInfo("Asia/Tokyo")
    return datetime.now(jst_tz).isoformat()


def _truncate_payload_summary(payload_summary: str, max_length: int = 80) -> str:
    """ペイロードサマリーを指定文字数で切り詰め"""
    if len(payload_summary) <= max_length:
        return payload_summary
    return payload_summary[:max_length - 3] + "..."


def _write_log_entry(
    event_type: str,
    channel: str,
    actor: str,
    payload_summary: str,
    result: str,
    error_stage: Optional[str] = None,
    error_detail: Optional[str] = None
) -> None:
    """ログエントリをJSONL形式でファイルに書き込み"""
    log_entry = {
        "ts": _get_jst_timestamp(),
        "event_type": event_type,
        "channel": channel,
        "actor": actor,
        "payload_summary": _truncate_payload_summary(payload_summary),
        "result": result,
        "error_stage": error_stage,
        "error_detail": error_detail
    }
    
    try:
        # ディレクトリの存在確認
        _ensure_log_directory()
        
        # JSONエンコード（orjsonを使用）
        json_line = orjson.dumps(log_entry).decode('utf-8')
        
        # スレッドセーフなファイル書き込み
        with _log_lock:
            with open(settings.logging.log_file, 'a', encoding='utf-8') as f:
                f.write(json_line + '\n')
                
    except Exception as e:
        # ログ出力エラーはアプリケーションをクラッシュさせない
        # ただし、エラーを標準エラー出力に出力してデバッグ可能にする
        import sys
        print(f"LOGGER ERROR: Failed to write log entry: {e}", file=sys.stderr)


def log_ok(event_type: str, channel: str, actor: str, payload_summary: str) -> None:
    """成功ログの記録
    
    Args:
        event_type: イベントタイプ（slash|user_msg|auto_tick|report）
        channel: チャンネル（command-center|creation|development|lounge）
        actor: アクター（user|spectra|lynq|paz|system）
        payload_summary: ペイロード要約（先頭80字程度）
    """
    _write_log_entry(
        event_type=event_type,
        channel=channel,
        actor=actor,
        payload_summary=payload_summary,
        result="ok"
    )


def log_err(
    event_type: str,
    channel: str,
    actor: str,
    payload_summary: str,
    error_stage: str,
    error_detail: str
) -> None:
    """エラーログの記録
    
    Args:
        event_type: イベントタイプ（slash|user_msg|auto_tick|report）
        channel: チャンネル（command-center|creation|development|lounge）
        actor: アクター（user|spectra|lynq|paz|system）
        payload_summary: ペイロード要約（先頭80字程度）
        error_stage: エラー段階（settings|slash|plan|typing|send|report|memory）
        error_detail: エラー詳細（例外要約など）
    """
    _write_log_entry(
        event_type=event_type,
        channel=channel,
        actor=actor,
        payload_summary=payload_summary,
        result="error",
        error_stage=error_stage,
        error_detail=error_detail
    )