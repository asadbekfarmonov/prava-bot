from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Deployment / runtime configuration.

    NOTE: legal exam rules (question count, timer, pass threshold) are *domain*
    configuration and live in ``app/domain/exam_config.py`` — never here.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="prava-bot", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    database_url: str = Field(
        default="postgresql+psycopg://prava:prava@localhost:5432/prava",
        alias="DATABASE_URL",
    )

    bot_token: str = Field(default="", alias="BOT_TOKEN")
    bot_username: str = Field(default="", alias="BOT_USERNAME")
    mini_app_url: str = Field(default="http://localhost:5173", alias="MINI_APP_URL")

    session_secret: str = Field(default="change-me", alias="SESSION_SECRET")
    telegram_init_data_max_age_seconds: int = Field(
        default=86400, alias="TELEGRAM_INIT_DATA_MAX_AGE_SECONDS"
    )
    admin_telegram_ids: str = Field(default="", alias="ADMIN_TELEGRAM_IDS")
    dev_auth_enabled: bool = Field(default=True, alias="DEV_AUTH_ENABLED")

    frontend_dev_url: str = Field(default="http://localhost:5173", alias="FRONTEND_DEV_URL")
    frontend_dist_dir: str = Field(default="frontend/dist", alias="FRONTEND_DIST_DIR")

    telegram_webhook_enabled: bool = Field(default=False, alias="TELEGRAM_WEBHOOK_ENABLED")
    telegram_webhook_secret: str = Field(default="", alias="TELEGRAM_WEBHOOK_SECRET")

    # Media storage adapter (Railway S3-compatible bucket). Not exercised in slice 1.
    media_bucket: str = Field(default="", alias="BUCKET")
    media_access_key_id: str = Field(default="", alias="ACCESS_KEY_ID")
    media_secret_access_key: str = Field(default="", alias="SECRET_ACCESS_KEY")
    media_region: str = Field(default="", alias="REGION")
    media_endpoint: str = Field(default="", alias="ENDPOINT")
    media_public_base_url: str = Field(default="", alias="MEDIA_PUBLIC_BASE_URL")
    media_presign_ttl_seconds: int = Field(default=300, alias="MEDIA_PRESIGN_TTL_SECONDS")

    # Media upload hardening caps (docs/spec/09 media-upload-security).
    max_image_bytes: int = Field(default=5 * 1024 * 1024, alias="MAX_IMAGE_BYTES")
    max_video_bytes: int = Field(default=25 * 1024 * 1024, alias="MAX_VIDEO_BYTES")
    max_video_duration_ms: int = Field(default=60_000, alias="MAX_VIDEO_DURATION_MS")
    max_image_pixels: int = Field(default=25_000_000, alias="MAX_IMAGE_PIXELS")
    max_image_dimension: int = Field(default=5_000, alias="MAX_IMAGE_DIMENSION")
    max_gif_frames: int = Field(default=300, alias="MAX_GIF_FRAMES")

    # Admin bootstrap + separation-of-duties (docs/spec/08).
    superadmin_telegram_ids: str = Field(default="", alias="SUPERADMIN_TELEGRAM_IDS")
    require_second_reviewer: bool = Field(default=False, alias="REQUIRE_SECOND_REVIEWER")

    auth_rate_limit_per_minute: int = Field(default=30, alias="AUTH_RATE_LIMIT_PER_MINUTE")
    write_rate_limit_per_minute: int = Field(default=180, alias="WRITE_RATE_LIMIT_PER_MINUTE")

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.app_env != "development":
            if self.session_secret == "change-me" or len(self.session_secret) < 32:
                raise ValueError(
                    "SESSION_SECRET must be a unique value with at least 32 characters outside development."
                )
            if self.app_debug:
                raise ValueError("APP_DEBUG must be false outside development.")
            if self.mini_app_url.startswith("http://"):
                raise ValueError("MINI_APP_URL must use https outside development.")
        if self.telegram_webhook_enabled:
            if not self.telegram_webhook_secret:
                raise ValueError(
                    "TELEGRAM_WEBHOOK_SECRET must be set when TELEGRAM_WEBHOOK_ENABLED is true."
                )
            if self.telegram_webhook_secret == self.session_secret:
                raise ValueError("TELEGRAM_WEBHOOK_SECRET must differ from SESSION_SECRET.")
        return self

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url.startswith("postgres://"):
            return self.database_url.replace("postgres://", "postgresql+psycopg://", 1)
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url

    @property
    def is_dev_auth_available(self) -> bool:
        return self.app_env == "development" and self.dev_auth_enabled

    @property
    def admin_ids(self) -> set[int]:
        ids: set[int] = set()
        for part in self.admin_telegram_ids.split(","):
            value = part.strip()
            if value:
                ids.add(int(value))
        return ids

    @property
    def superadmin_ids(self) -> set[int]:
        ids: set[int] = set()
        for part in self.superadmin_telegram_ids.split(","):
            value = part.strip()
            if value:
                ids.add(int(value))
        return ids

    @property
    def media_storage_configured(self) -> bool:
        """True when an S3-compatible bucket is configured; otherwise the in-memory
        fake is used (dev/test never hit the network)."""
        return bool(self.media_bucket and self.media_endpoint)

    @property
    def frontend_dist_path(self) -> Path:
        return Path(self.frontend_dist_dir).expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
