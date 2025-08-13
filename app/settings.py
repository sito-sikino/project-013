# Settings Management - 設定一元管理
# Fail-Fast原則: 設定エラーは即座にプロセス終了

import os
import sys
from dataclasses import dataclass
from typing import Union
from dotenv import load_dotenv


def fail_fast(message: str) -> None:
    """設定エラー時の即座終了"""
    print(f"FATAL CONFIG ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def get_required_env(key: str) -> str:
    """必須環境変数の取得（欠落時は即座終了）"""
    value = os.getenv(key)
    if value is None:
        fail_fast(f"Required environment variable '{key}' is not set")
    return value


def get_required_int(key: str) -> int:
    """必須整数環境変数の取得（型変換失敗時は即座終了）"""
    value = get_required_env(key)
    try:
        return int(value)
    except ValueError:
        fail_fast(f"Environment variable '{key}' must be an integer, got: {value}")


def get_required_float(key: str) -> float:
    """必須浮動小数点環境変数の取得（型変換失敗時は即座終了）"""
    value = get_required_env(key)
    try:
        return float(value)
    except ValueError:
        fail_fast(f"Environment variable '{key}' must be a float, got: {value}")


def validate_probability(key: str, value: float) -> float:
    """確率値の範囲検証（0.0-1.0）"""
    if not 0.0 <= value <= 1.0:
        fail_fast(f"Environment variable '{key}' must be between 0.0 and 1.0, got: {value}")
    return value


def validate_time_format(key: str, value: str) -> str:
    """時刻フォーマット検証（HH:MM）"""
    try:
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError("Invalid format")
        hour, minute = int(parts[0]), int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Invalid time values")
        return value
    except ValueError:
        fail_fast(f"Environment variable '{key}' must be in HH:MM format, got: {value}")


@dataclass(frozen=True)
class EnvironmentConfig:
    """環境設定"""
    env: str
    timezone: str


@dataclass(frozen=True)
class DiscordConfig:
    """Discord設定"""
    spectra_token: str
    lynq_token: str
    paz_token: str
    chan_command_center: str
    chan_creation: str
    chan_development: str
    chan_lounge: str


@dataclass(frozen=True)
class RedisConfig:
    """Redis設定"""
    url: str


@dataclass(frozen=True)
class AIServiceConfig:
    """AI サービス設定"""
    gemini_api_key: str


@dataclass(frozen=True)
class TickConfig:
    """Tick設定"""
    interval_sec_dev: int
    prob_dev: float
    max_test_minutes: int
    interval_sec_prod: int
    prob_prod: float


@dataclass(frozen=True)
class ScheduleConfig:
    """スケジュール設定"""
    standby_start: str
    processing_at: str
    free_start: str


@dataclass(frozen=True)
class ChannelLimitsConfig:
    """チャンネル制限設定"""
    limit_cc: int
    limit_cr: int
    limit_dev: int
    limit_lo: int


@dataclass(frozen=True)
class LoggingConfig:
    """ログ設定"""
    log_file: str


@dataclass(frozen=True)
class Settings:
    """全設定の統合"""
    environment: EnvironmentConfig
    discord: DiscordConfig
    redis: RedisConfig
    ai_service: AIServiceConfig
    tick: TickConfig
    schedule: ScheduleConfig
    channel_limits: ChannelLimitsConfig
    logging: LoggingConfig


def load_settings() -> Settings:
    """設定の読み込みと検証（Fail-Fast）"""
    # .envファイルの読み込み
    load_dotenv()
    
    # 環境設定
    env = get_required_env("ENV")
    if env not in ["dev", "prod"]:
        fail_fast(f"ENV must be 'dev' or 'prod', got: {env}")
    
    # Discord設定
    discord_config = DiscordConfig(
        spectra_token=get_required_env("SPECTRA_TOKEN"),
        lynq_token=get_required_env("LYNQ_TOKEN"),
        paz_token=get_required_env("PAZ_TOKEN"),
        chan_command_center=get_required_env("CHAN_COMMAND_CENTER"),
        chan_creation=get_required_env("CHAN_CREATION"),
        chan_development=get_required_env("CHAN_DEVELOPMENT"),
        chan_lounge=get_required_env("CHAN_LOUNGE")
    )
    
    # Redis設定
    redis_config = RedisConfig(
        url=get_required_env("REDIS_URL")
    )
    
    # AIサービス設定
    ai_service_config = AIServiceConfig(
        gemini_api_key=get_required_env("GEMINI_API_KEY")
    )
    
    # Tick設定（確率値の範囲検証付き）
    prob_dev = validate_probability("TICK_PROB_DEV", get_required_float("TICK_PROB_DEV"))
    prob_prod = validate_probability("TICK_PROB_PROD", get_required_float("TICK_PROB_PROD"))
    
    tick_config = TickConfig(
        interval_sec_dev=get_required_int("TICK_INTERVAL_SEC_DEV"),
        prob_dev=prob_dev,
        max_test_minutes=get_required_int("MAX_TEST_MINUTES"),
        interval_sec_prod=get_required_int("TICK_INTERVAL_SEC_PROD"),
        prob_prod=prob_prod
    )
    
    # スケジュール設定（時刻フォーマット検証付き）
    schedule_config = ScheduleConfig(
        standby_start=validate_time_format("STANDBY_START", get_required_env("STANDBY_START")),
        processing_at=validate_time_format("PROCESSING_AT", get_required_env("PROCESSING_AT")),
        free_start=validate_time_format("FREE_START", get_required_env("FREE_START"))
    )
    
    # チャンネル制限設定
    channel_limits_config = ChannelLimitsConfig(
        limit_cc=get_required_int("LIMIT_CC"),
        limit_cr=get_required_int("LIMIT_CR"),
        limit_dev=get_required_int("LIMIT_DEV"),
        limit_lo=get_required_int("LIMIT_LO")
    )
    
    # ログ設定
    logging_config = LoggingConfig(
        log_file=get_required_env("LOG_FILE")
    )
    
    # 環境設定
    environment_config = EnvironmentConfig(
        env=env,
        timezone=get_required_env("TZ")
    )
    
    return Settings(
        environment=environment_config,
        discord=discord_config,
        redis=redis_config,
        ai_service=ai_service_config,
        tick=tick_config,
        schedule=schedule_config,
        channel_limits=channel_limits_config,
        logging=logging_config
    )


# グローバル設定インスタンス（初回読み込み時に検証）
settings = load_settings()