# %%
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_DIR = Path(__file__).resolve().parents[2]  # git repo


class BaseEnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="forbid",
    )
    # Env setup
    PYTHONPATH: str
    DJANGO_SETTINGS_MODULE: str
    APP_ENV: str

    # Tokens
    DISCORD_API_TOKEN: str
    DPS_REPORT_USERTOKEN: str
    DJANGO_SECRET_KEY: str

    # Setup
    CORE_MINIMUM_RAID: int
    CORE_MINIMUM_STRIKE: int
    CORE_MINIMUM_FRACTAL: int
    INCLUDE_NON_CORE_LOGS: bool
    MEAN_OR_MEDIAN: str
    MEDALS_TYPE: str
    RANK_BINS_PERCENTILE: list
    DPS_LOGS_DIR: Path
    EXTRA_LOGS_DIR: Path | None

    @classmethod
    def load(cls):
        return cls(_env_file=[PROJECT_DIR / ".env"])


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="allow",
    )

    # Django
    DEBUG: bool = False

    # Database
    DJANGO_DATABASE_ENGINE: str
    DJANGO_DATABASE_NAME: str
    DJANGO_DATABASE_USER: str | None = None
    DJANGO_DATABASE_PASSWORD: str | None = None
    DJANGO_DATABASE_HOST: str | None = None
    DJANGO_DATABASE_PORT: str | None = None

    # Webhooks
    WEBHOOK_BOT_CHANNEL_RAID: str
    WEBHOOK_BOT_CHANNEL_STRIKE: str
    WEBHOOK_BOT_CHANNEL_FRACTAL: str
    WEBHOOK_BOT_CHANNEL_RAID_CURRENT_WEEK: str
    WEBHOOK_BOT_CHANNEL_STRIKE_CURRENT_WEEK: str

    # Webhooks Leaderboard
    WEBHOOK_BOT_CHANNEL_LEADERBOARD: str
    CHANNEL_ID_LEADERBOARD: str
    WEBHOOK_BOT_THREAD_LEADERBOARD_RAIDS: str
    WEBHOOK_BOT_THREAD_LEADERBOARD_STRIKES: str
    WEBHOOK_BOT_THREAD_LEADERBOARD_FRACTALS: str

    # Webhooks Progression
    WEBHOOK_BOT_CHANNEL_PROGRESSION: str | None
    WEBHOOK_BOT_CHANNEL_CERUS_CM: str | None

    @classmethod
    def load(cls, app_env):
        return cls(_env_file=[PROJECT_DIR / f".env.{app_env.lower()}"])
