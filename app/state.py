# State Management - ステート管理
# Mode, Channel, Agent の型定義とステート操作

from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from app.settings import settings

# Type definitions (reuse from store.py for consistency)
Agent = Literal["spectra", "lynq", "paz", "user"]
Channel = Literal["command-center", "creation", "development", "lounge"]


class Mode(Enum):
    """システム動作モード"""
    STANDBY = "standby"        # 待機モード
    PROCESSING = "processing"  # 処理モード (日報生成時)
    ACTIVE = "active"         # アクティブモード
    FREE = "free"             # フリータイムモード


@dataclass
class Task:
    """タスク情報"""
    content: Optional[str] = None
    channel: Optional[Channel] = None


@dataclass
class State:
    """システム全体のステート"""
    mode: Mode
    active_channel: Channel
    task: Task


# Global state instance
_state: Optional[State] = None


def _parse_time_string(time_str: str) -> time:
    """時刻文字列 (HH:MM) を time オブジェクトに変換"""
    hour, minute = map(int, time_str.split(':'))
    return time(hour, minute)


def mode_from_time(now_jst: datetime) -> Mode:
    """JST時刻からモードを決定
    
    Args:
        now_jst: JST タイムゾーンの現在時刻
        
    Returns:
        Mode: 時刻に基づく動作モード
    """
    current_time = now_jst.time()
    
    # 設定から時刻を取得
    standby_start = _parse_time_string(settings.schedule.standby_start)  # 00:00
    processing_at = _parse_time_string(settings.schedule.processing_at)  # 06:00
    free_start = _parse_time_string(settings.schedule.free_start)        # 20:00
    
    # 06:00 PROCESSING タイムチェック (日報生成時)
    if current_time.hour == processing_at.hour and current_time.minute == processing_at.minute:
        return Mode.PROCESSING
    
    # FREE_START 以降（同日内）は FREE モード (20:00-23:59)
    if current_time >= free_start:
        return Mode.FREE
    
    # PROCESSING_AT 以降、FREE_START 未満は ACTIVE モード (06:00-19:59, 06:00除く)
    if current_time >= processing_at and current_time < free_start:
        return Mode.ACTIVE
    
    # 00:00-06:00 は STANDBY モード
    return Mode.STANDBY


def init_active_channel(mode: Mode) -> Channel:
    """モードに応じた初期アクティブチャンネルを決定
    
    Args:
        mode: システム動作モード
        
    Returns:
        Channel: 初期アクティブチャンネル
    """
    if mode == Mode.ACTIVE:
        return "command-center"
    elif mode == Mode.FREE:
        return "lounge"
    else:
        # STANDBY, PROCESSING の場合もデフォルトは command-center
        return "command-center"


def get_state() -> State:
    """現在のステートを取得"""
    global _state
    if _state is None:
        # 初期化: 現在時刻からモードを決定
        jst_tz = ZoneInfo("Asia/Tokyo")
        now_jst = datetime.now(jst_tz)
        current_mode = mode_from_time(now_jst)
        
        _state = State(
            mode=current_mode,
            active_channel=init_active_channel(current_mode),
            task=Task()
        )
    
    return _state


def set_active_channel(channel: Channel) -> None:
    """アクティブチャンネルを設定
    
    Args:
        channel: 設定するチャンネル
    """
    state = get_state()
    state.active_channel = channel


def update_task(content: Optional[str] = None, channel: Optional[Channel] = None) -> None:
    """タスク情報を更新
    
    Args:
        content: タスク内容 (省略時は既存値を保持)
        channel: タスクチャンネル (省略時は既存値を保持)
    """
    state = get_state()
    
    if content is not None:
        state.task.content = content
    
    if channel is not None:
        state.task.channel = channel


def update_mode(mode: Mode) -> None:
    """モードを更新 (スケジューラからの呼び出し用)
    
    Args:
        mode: 新しいモード
    """
    state = get_state()
    state.mode = mode
    
    # モード変更時にアクティブチャンネルも更新
    state.active_channel = init_active_channel(mode)


def get_current_mode() -> Mode:
    """現在のモードを取得"""
    return get_state().mode


def get_active_channel() -> Channel:
    """現在のアクティブチャンネルを取得"""
    return get_state().active_channel


def get_task() -> Task:
    """現在のタスク情報を取得"""
    return get_state().task


def get_current_jst_time() -> datetime:
    """現在のJST時間を取得"""
    jst_tz = ZoneInfo("Asia/Tokyo")
    return datetime.now(jst_tz)


# Test functions for development
def _test_time_modes() -> bool:
    """時刻ベースのモード判定テスト"""
    jst_tz = ZoneInfo("Asia/Tokyo")
    
    # Test cases for different times
    # Schedule: STANDBY_START=00:00, PROCESSING_AT=06:00, FREE_START=20:00
    test_cases = [
        (datetime(2025, 8, 13, 0, 0, tzinfo=jst_tz), Mode.STANDBY),    # 00:00 - STANDBY (00:00-05:59)
        (datetime(2025, 8, 13, 5, 30, tzinfo=jst_tz), Mode.STANDBY),   # 05:30 - STANDBY (00:00-05:59)
        (datetime(2025, 8, 13, 6, 0, tzinfo=jst_tz), Mode.PROCESSING), # 06:00 - PROCESSING (exactly 06:00)
        (datetime(2025, 8, 13, 6, 1, tzinfo=jst_tz), Mode.ACTIVE),     # 06:01 - ACTIVE (06:01-19:59)
        (datetime(2025, 8, 13, 8, 0, tzinfo=jst_tz), Mode.ACTIVE),     # 08:00 - ACTIVE
        (datetime(2025, 8, 13, 19, 59, tzinfo=jst_tz), Mode.ACTIVE),   # 19:59 - ACTIVE (last minute of ACTIVE)
        (datetime(2025, 8, 13, 20, 0, tzinfo=jst_tz), Mode.FREE),      # 20:00 - FREE (FREE_START)
        (datetime(2025, 8, 13, 23, 0, tzinfo=jst_tz), Mode.FREE),      # 23:00 - FREE
        (datetime(2025, 8, 13, 23, 59, tzinfo=jst_tz), Mode.FREE),     # 23:59 - FREE (before next day)
    ]
    
    for test_time, expected_mode in test_cases:
        actual_mode = mode_from_time(test_time)
        if actual_mode != expected_mode:
            print(f"ERROR: Time {test_time.time()} expected {expected_mode}, got {actual_mode}")
            return False
    
    print("✓ Time-based mode detection tests passed")
    return True


def _test_channel_initialization() -> bool:
    """チャンネル初期化テスト"""
    test_cases = [
        (Mode.ACTIVE, "command-center"),
        (Mode.FREE, "lounge"),
        (Mode.STANDBY, "command-center"),
        (Mode.PROCESSING, "command-center"),
    ]
    
    for mode, expected_channel in test_cases:
        actual_channel = init_active_channel(mode)
        if actual_channel != expected_channel:
            print(f"ERROR: Mode {mode} expected {expected_channel}, got {actual_channel}")
            return False
    
    print("✓ Channel initialization tests passed")
    return True


if __name__ == "__main__":
    """直接実行時のテスト"""
    print("Testing state management system...")
    
    # 1. 時刻ベースモード判定テスト
    print("1. Testing time-based mode detection...")
    if not _test_time_modes():
        exit(1)
    
    # 2. チャンネル初期化テスト
    print("2. Testing channel initialization...")
    if not _test_channel_initialization():
        exit(1)
    
    # 3. ステート操作テスト
    print("3. Testing state operations...")
    
    # 初期ステート取得
    initial_state = get_state()
    print(f"Initial state - Mode: {initial_state.mode}, Channel: {initial_state.active_channel}")
    
    # チャンネル変更テスト
    set_active_channel("development")
    assert get_active_channel() == "development"
    print("✓ Channel setting test passed")
    
    # タスク更新テスト
    update_task(content="Test task", channel="creation")
    task = get_task()
    assert task.content == "Test task"
    assert task.channel == "creation"
    print("✓ Task update test passed")
    
    # 部分更新テスト
    update_task(content="Updated content")
    task = get_task()
    assert task.content == "Updated content"
    assert task.channel == "creation"  # 前の値を保持
    print("✓ Partial task update test passed")
    
    print("All state management tests passed!")