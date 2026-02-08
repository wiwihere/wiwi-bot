# %%
"""Environment settings models for the bot.

Module provides two pydantic `BaseSettings` classes used to centralize
configuration loaded from `.env` files and the process environment.

- `BaseEnvSettings` holds global/shared values (loaded from `.env`).
- `EnvSettings` holds environment-specific values (loaded from `.env.prd` or `.env.dev`).

Secrets use `SecretStr` to avoid accidental exposure; call
`.get_secret_value()` where a plain string is required.
"""

from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_DIR = Path(__file__).resolve().parents[2]  # git repo


class BaseEnvSettings(BaseSettings):
    """Global/shared environment settings.

    Use `BaseEnvSettings.load()` to read values from `PROJECT_DIR/.env`.
    These settings include tokens, core feature flags and paths that are
    common across deployment environments.
    """

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="forbid",
    )
    # Env setup
    PYTHONPATH: str
    DJANGO_SETTINGS_MODULE: str
    APP_ENV: str

    # Tokens (secrets)
    DISCORD_API_TOKEN: SecretStr
    DPS_REPORT_USERTOKEN: SecretStr
    DJANGO_SECRET_KEY: SecretStr

    # Setup
    CORE_MINIMUM_RAID: int
    CORE_MINIMUM_STRIKE: int
    CORE_MINIMUM_FRACTAL: int
    INCLUDE_NON_CORE_LOGS: bool
    MEAN_OR_MEDIAN: str
    MEDALS_TYPE: str
    RANK_BINS_PERCENTILE: list[int]
    DPS_LOGS_DIR: Path
    EXTRA_LOGS_DIR: Path | None

    @classmethod
    def load(cls) -> "BaseEnvSettings":
        return cls(_env_file=[PROJECT_DIR / ".env"])

    @field_validator("EXTRA_LOGS_DIR", mode="before")
    def _parse_extra_logs_dir(cls, v):
        """Normalize `EXTRA_LOGS_DIR`: empty string or missing -> None.

        Convert a non-empty string to a `Path`.
        """
        if v in ("", None):
            return None
        return Path(v)


class EnvSettings(BaseSettings):
    """Per-environment settings.

    Use `EnvSettings.load(app_env)` to load `PROJECT_DIR/.env.<app_env>`.
    Extra unknown fields are allowed to make staged migrations easier.
    """

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="allow",
    )

    # Django
    DEBUG: bool = False
    LOGLEVEL: str = "INFO"  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL

    # Database
    DJANGO_DATABASE_ENGINE: str
    DJANGO_DATABASE_NAME: str
    DJANGO_DATABASE_USER: str | None = None
    DJANGO_DATABASE_PASSWORD: SecretStr | None = None
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
    def load(cls, app_env: str) -> "EnvSettings":
        return cls(_env_file=[PROJECT_DIR / f".env.{app_env.lower()}"])
