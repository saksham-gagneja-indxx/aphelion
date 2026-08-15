"""
Configuration management for Social Media Automation Agent
Uses environment variables and pydantic for validation
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # ============ FLASK SETTINGS ============
    flask_env: str = Field(default="development", alias="FLASK_ENV")
    flask_port: int = Field(default=5000, alias="FLASK_PORT")
    secret_key: str = Field(default="dev-secret-key-change-in-production", alias="SECRET_KEY")
    debug: bool = Field(default=True, alias="DEBUG")

    # ============ DATABASE SETTINGS ============
    database_url: str = Field(
        default="sqlite:///data/automation.db",
        alias="DATABASE_URL"
    )
    db_echo: bool = Field(default=False, alias="DB_ECHO")

    # ============ CLAUDE API SETTINGS ============
    claude_api_key: str = Field(alias="CLAUDE_API_KEY")
    claude_model: str = Field(default="claude-3-5-sonnet-20241022", alias="CLAUDE_MODEL")

    # ============ INSTAGRAM SETTINGS ============
    instagram_username: str = Field(alias="INSTAGRAM_USERNAME")
    instagram_password: str = Field(alias="INSTAGRAM_PASSWORD")

    # ============ LINKEDIN SETTINGS ============
    # OAuth 2.0 only. There is deliberately no LINKEDIN_PASSWORD: publishing
    # uses the `w_member_social` scope obtained via the member's own consent,
    # and password-based automation violates LinkedIn's User Agreement.
    linkedin_client_id: Optional[str] = Field(default=None, alias="LINKEDIN_CLIENT_ID")
    linkedin_client_secret: Optional[str] = Field(
        default=None, alias="LINKEDIN_CLIENT_SECRET"
    )
    linkedin_redirect_uri: str = Field(
        default="http://localhost:5000/api/auth/linkedin/callback",
        alias="LINKEDIN_REDIRECT_URI",
    )
    # LinkedIn-Version header, YYYYMM. Versions sunset on a rolling schedule,
    # so this is configurable rather than hardcoded at a call site.
    linkedin_api_version: str = Field(default="202607", alias="LINKEDIN_API_VERSION")

    # ============ FRONTEND ============
    # Where the OAuth callback sends the browser once the token is stored.
    # Configurable because it differs per environment: the Vite dev server
    # locally, the deployed SPA in production.
    frontend_url: str = Field(default="http://localhost:5173", alias="FRONTEND_URL")

    # ============ TIMEZONE SETTINGS ============
    timezone: str = Field(default="Asia/Kolkata", alias="TIMEZONE")

    # ============ FILE UPLOAD SETTINGS ============
    upload_folder: str = Field(default="data/uploads", alias="UPLOAD_FOLDER")
    reels_folder: str = Field(default="data/reels", alias="REELS_FOLDER")
    max_upload_size: int = Field(default=500 * 1024 * 1024, alias="MAX_UPLOAD_SIZE")  # 500MB
    allowed_video_extensions: list = Field(
        default=["mp4", "mov", "avi", "mkv", "webm"],
        alias="ALLOWED_VIDEO_EXTENSIONS"
    )

    # ============ MEDIA TOOLING ============
    # Set these if ffmpeg/ffprobe are not on PATH (common on Windows right
    # after a winget install, until the shell is restarted).
    ffmpeg_path: str = Field(default="ffmpeg", alias="FFMPEG_PATH")
    ffprobe_path: str = Field(default="ffprobe", alias="FFPROBE_PATH")

    # ============ SCHEDULER SETTINGS ============
    scheduler_enabled: bool = Field(default=True, alias="SCHEDULER_ENABLED")
    scheduler_check_interval: int = Field(default=60, alias="SCHEDULER_CHECK_INTERVAL")  # seconds
    scheduler_max_workers: int = Field(default=4, alias="SCHEDULER_MAX_WORKERS")

    # ============ AI SETTINGS ============
    enable_caption_generation: bool = Field(default=True, alias="ENABLE_CAPTION_GENERATION")
    enable_hashtag_recommendations: bool = Field(default=True, alias="ENABLE_HASHTAG_RECOMMENDATIONS")
    enable_comment_monitoring: bool = Field(default=True, alias="ENABLE_COMMENT_MONITORING")
    enable_auto_reply: bool = Field(default=False, alias="ENABLE_AUTO_REPLY")

    # ============ LOGGING SETTINGS ============
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: str = Field(default="data/logs/app.log", alias="LOG_FILE")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        alias="LOG_FORMAT"
    )

    # ============ JWT SETTINGS (Future Security) ============
    jwt_secret: str = Field(default="jwt-secret-key", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expiration_hours: int = Field(default=24, alias="JWT_EXPIRATION_HOURS")

    # SettingsConfigDict rather than a nested `class Config`, which pydantic
    # deprecated in v2 and removes in v3.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Tolerate keys in .env that this model doesn't define (e.g. deferred
        # Phase 2/3 settings). Without this, pydantic-settings v2 raises
        # extra_forbidden and the app refuses to boot.
        extra="ignore",
    )


def get_settings() -> Settings:
    """Get application settings instance (singleton pattern)"""
    return Settings()


def is_placeholder(value: Optional[str]) -> bool:
    """True if a setting is unset or still holding an example placeholder."""
    if not value:
        return True
    lowered = value.lower()
    return lowered.startswith("your_") or "placeholder" in lowered


def instagram_configured() -> bool:
    """True only when real (non-placeholder) Instagram credentials are present."""
    settings = get_settings()
    return not (
        is_placeholder(settings.instagram_username)
        or is_placeholder(settings.instagram_password)
    )


def linkedin_configured() -> bool:
    """True when the LinkedIn OAuth app is configured.

    This reports whether *the app* can start an OAuth flow - not whether any
    member has authorized it. Per-user connection state lives on the User row.
    """
    settings = get_settings()
    return not (
        is_placeholder(settings.linkedin_client_id)
        or is_placeholder(settings.linkedin_client_secret)
    )


def validate_settings() -> bool:
    """Validate configuration required for the app to boot.

    Credentials are deliberately NOT boot-blocking. Instagram auth is only
    needed when actually posting, and the 24h plan builds/tests the upload
    pipeline before real credentials are supplied (docs/TIMELINE.md hour 18-21).
    Missing credentials degrade the relevant feature and are surfaced via
    /api/status, rather than preventing the server from starting.
    """
    try:
        settings = get_settings()

        if not instagram_configured():
            print(
                "⚠️  Instagram credentials not configured — upload/scheduling "
                "will work, but posting will fail until they are set in .env"
            )

        if is_placeholder(settings.claude_api_key):
            print("⚠️  CLAUDE_API_KEY not configured — AI features are out of scope for v1")

        print("✅ Configuration loaded")
        return True
    except Exception as e:
        print(f"❌ Settings validation error: {str(e)}")
        return False


if __name__ == "__main__":
    settings = get_settings()
    validate_settings()
    print("\n📋 Current Settings:")
    print(f"  Flask: {settings.flask_env} on port {settings.flask_port}")
    print(f"  Database: {settings.database_url}")
    print(f"  Timezone: {settings.timezone}")
    print(f"  Instagram: {settings.instagram_username}")
    print(f"  Claude Model: {settings.claude_model}")
