# Redis Store - Redis全文脈ストレージ
# 当日全文脈をRedisに一元保存

import sys
from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal
from zoneinfo import ZoneInfo

import orjson
import redis

from app.logger import log_err, log_ok
from app.settings import settings


# Type definitions
Agent = Literal["spectra", "lynq", "paz", "user"]
Channel = Literal["command-center", "creation", "development", "lounge"]


@dataclass
class Record:
    """Redis ストレージのレコード構造"""
    agent: Agent
    channel: Channel
    timestamp: str  # ISO8601 JST format
    text: str


# Redis key constants
SESSION_ID = "discord_unified"
REDIS_KEY = f"session:{SESSION_ID}:messages"


def _get_jst_timestamp() -> str:
    """JST（Asia/Tokyo）タイムゾーンでのISO8601タイムスタンプを取得"""
    jst_tz = ZoneInfo("Asia/Tokyo")
    return datetime.now(jst_tz).isoformat()


def _get_redis_connection() -> redis.Redis:
    """Redis接続の取得（Fail-Fast）"""
    try:
        r = redis.from_url(settings.redis.url, decode_responses=True)
        # 接続テスト
        r.ping()
        return r
    except redis.ConnectionError as e:
        log_err("store", "system", "system", "Redis connection failed", "memory", str(e))
        print(f"FATAL REDIS ERROR: Unable to connect to Redis at {settings.redis.url}: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        log_err("store", "system", "system", "Redis connection error", "memory", str(e))
        print(f"FATAL REDIS ERROR: Unexpected error during Redis connection: {e}", file=sys.stderr)
        sys.exit(1)


def test_connection() -> bool:
    """Redis接続テスト（デバッグ用）"""
    try:
        r = _get_redis_connection()
        result = r.ping()
        log_ok("store", "system", "system", "Redis PING test")
        return result
    except SystemExit:
        # _get_redis_connection already handles the error logging and exit
        raise
    except Exception as e:
        log_err("store", "system", "system", "Redis ping test failed", "memory", str(e))
        return False


def read_all() -> List[Record]:
    """当日全文脈の読み取り
    
    Returns:
        List[Record]: 時系列順のメッセージリスト
    """
    try:
        r = _get_redis_connection()
        
        # Redis list から全メッセージを取得（時系列順）
        messages_json = r.lrange(REDIS_KEY, 0, -1)
        
        records = []
        for msg_json in messages_json:
            try:
                msg_data = orjson.loads(msg_json)
                record = Record(
                    agent=msg_data["agent"],
                    channel=msg_data["channel"],
                    timestamp=msg_data["timestamp"],
                    text=msg_data["text"]
                )
                records.append(record)
            except (orjson.JSONDecodeError, KeyError, TypeError) as e:
                log_err("store", "system", "system", f"Invalid message format: {msg_json[:80]}", "memory", str(e))
                # Skip malformed records but continue processing
                continue
        
        log_ok("store", "system", "system", f"Read {len(records)} messages from Redis")
        return records
        
    except SystemExit:
        # _get_redis_connection already handles the error logging and exit
        raise
    except Exception as e:
        log_err("store", "system", "system", "Failed to read messages from Redis", "memory", str(e))
        print(f"FATAL REDIS ERROR: Failed to read messages: {e}", file=sys.stderr)
        sys.exit(1)


def append(agent: Agent, channel: Channel, text: str) -> None:
    """新しいメッセージの追記
    
    Args:
        agent: エージェント名
        channel: チャンネル名
        text: メッセージ内容
    """
    try:
        r = _get_redis_connection()
        
        # レコード作成
        record = Record(
            agent=agent,
            channel=channel,
            timestamp=_get_jst_timestamp(),
            text=text
        )
        
        # JSON にシリアライズ
        record_json = orjson.dumps({
            "agent": record.agent,
            "channel": record.channel,
            "timestamp": record.timestamp,
            "text": record.text
        }).decode('utf-8')
        
        # Redis list に追記（右端＝最新）
        r.rpush(REDIS_KEY, record_json)
        
        log_ok("store", channel, agent, f"Appended message: {text[:80]}")
        
    except SystemExit:
        # _get_redis_connection already handles the error logging and exit
        raise
    except Exception as e:
        log_err("store", channel, agent, f"Failed to append message: {text[:80]}", "memory", str(e))
        print(f"FATAL REDIS ERROR: Failed to append message: {e}", file=sys.stderr)
        sys.exit(1)


def reset() -> None:
    """全メッセージのリセット（日報後の全削除）"""
    try:
        r = _get_redis_connection()
        
        # キーの存在確認と削除
        deleted_count = r.delete(REDIS_KEY)
        
        log_ok("store", "system", "system", f"Reset Redis store (deleted {deleted_count} keys)")
        
    except SystemExit:
        # _get_redis_connection already handles the error logging and exit
        raise
    except Exception as e:
        log_err("store", "system", "system", "Failed to reset Redis store", "memory", str(e))
        print(f"FATAL REDIS ERROR: Failed to reset store: {e}", file=sys.stderr)
        sys.exit(1)


def _test_store_cycle() -> bool:
    """ストアサイクルテスト（append → read_all → reset）
    
    Returns:
        bool: テスト成功時 True
    """
    try:
        # 1. 初期状態確認
        initial_messages = read_all()
        
        # 2. テストメッセージ追加
        test_message = "Test message for store cycle"
        append("user", "command-center", test_message)
        
        # 3. 読み取りテスト
        messages_after_append = read_all()
        
        # 4. 追加されたメッセージの確認
        if len(messages_after_append) != len(initial_messages) + 1:
            print(f"ERROR: Expected {len(initial_messages) + 1} messages, got {len(messages_after_append)}", file=sys.stderr)
            return False
            
        last_message = messages_after_append[-1]
        if (last_message.agent != "user" or 
            last_message.channel != "command-center" or 
            last_message.text != test_message):
            print(f"ERROR: Last message does not match expected values", file=sys.stderr)
            return False
        
        # 5. リセットテスト
        reset()
        
        # 6. リセット後の確認
        messages_after_reset = read_all()
        if len(messages_after_reset) != 0:
            print(f"ERROR: Expected 0 messages after reset, got {len(messages_after_reset)}", file=sys.stderr)
            return False
        
        log_ok("store", "system", "system", "Store cycle test completed successfully")
        return True
        
    except Exception as e:
        log_err("store", "system", "system", "Store cycle test failed", "memory", str(e))
        print(f"ERROR: Store cycle test failed: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    """直接実行時のテスト"""
    print("Testing Redis store system...")
    
    # 1. 接続テスト
    print("1. Testing Redis connection...")
    if test_connection():
        print("✓ Redis connection successful")
    else:
        print("✗ Redis connection failed")
        sys.exit(1)
    
    # 2. ストアサイクルテスト
    print("2. Testing store cycle (append → read → reset)...")
    if _test_store_cycle():
        print("✓ Store cycle test successful")
    else:
        print("✗ Store cycle test failed")
        sys.exit(1)
    
    print("All tests passed!")