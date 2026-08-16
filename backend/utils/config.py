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

    # ============ LLM API SETTINGS ============
    # Supported providers: "claude" (Anthropic), "gemini" (Google)
    llm_provider: str = Field(default="gemini", alias="LLM_PROVIDER")

    # Claude (Anthropic) settings
    claude_api_key: str = Field(default="sk-ant-placeholder", alias="CLAUDE_API_KEY")
    claude_model: str = Field(default="claude-3-5-sonnet-20241022", alias="CLAUDE_MODEL")

    # Gemini (Google) settings
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")

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

    # ============ ADMIN ALLOWLIST ============
    # Comma-separated LinkedIn OIDC subject claims (`sub`) permitted to hold
    # the admin role. When set, this is the ONLY way to become an admin:
    # the "first account becomes admin" bootstrap is disabled entirely.
    #
    # Pinned to `sub` rather than email because LinkedIn does not always return
    # an email (it needs the `email` scope, which we do not request), and an
    # email can be changed by its owner. `sub` is stable and unforgeable.
    admin_linkedin_subs: str = Field(default="", alias="ADMIN_LINKEDIN_SUBS")

    # When false, accounts that are not on the admin allowlist cannot sign up
    # at all. Use to close the tool completely once the intended users exist.
    allow_new_signups: bool = Field(default=True, alias="ALLOW_NEW_SIGNUPS")

    # ============ GUEST ACCESS ============
    # Lets a visitor try the tool without a LinkedIn account. A guest is a real,
    # ordinary account - not a bypass of anything - created on request and
    # sandboxed: its own data, no publishing, never an administrator.
    #
    # Turn it off to require LinkedIn for everyone.
    allow_guest_access: bool = Field(default=True, alias="ALLOW_GUEST_ACCESS")

    # ============ API AUTHENTICATION ============
    # Bearer token required on every /api/* route. There is no default and no
    # "disabled" mode: if this is unset the app refuses API requests rather
    # than serving them openly. See backend/utils/security.py.
    api_access_key: Optional[str] = Field(default=None, alias="API_ACCESS_KEY")

    # Origins allowed to call the API from a browser. Comma-separated.
    # Never "*" - that lets any site a user visits drive this API with their
    # credentials attached.
    cors_origins: str = Field(
        default="http://localhost:5173", alias="CORS_ORIGINS"
    )

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
    # Where reels actually live. "local" is disk under reels_folder; "object"
    # selects ObjectMediaStore, which is a documented stub until someone picks
    # an SDK. See backend/core/storage.py.
    media_backend: str = Field(default="local", alias="MEDIA_BACKEND")
    media_bucket: str = Field(default="", alias="MEDIA_BUCKET")
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
    # How late a post may be published after its scheduled time. The process
    # is not always up when a post comes due - a deploy, a crash, or a free
    # instance sleeping through the moment - so recovery has to tolerate some
    # lateness. Past this window the post is failed with a reason rather than
    # published at the wrong time of day or dropped in silence.
    scheduler_misfire_grace_seconds: int = Field(
        default=3600, alias="SCHEDULER_MISFIRE_GRACE_SECONDS"
    )
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


def admin_subs() -> set:
    """LinkedIn `sub` values allowed to hold the admin role."""
    raw = get_settings().admin_linkedin_subs or ""
    return {s.strip() for s in raw.split(",") if s.strip()}


def is_admin_sub(subject: str) -> bool:
    """True when this LinkedIn identity is on the admin allowlist."""
    return bool(subject) and subject in admin_subs()


def admin_allowlist_enabled() -> bool:
    """True when an explicit allowlist is configured.

    While this is empty the system falls back to bootstrap behaviour: the first
    account to sign in becomes an admin so the tool is usable at all. That is
    convenient but weak - anyone reaching the public login endpoint on an empty
    database would claim it. Setting the allowlist closes that permanently.
    """
    return len(admin_subs()) > 0


def guest_access_enabled() -> bool:
    """True when visitors may create a guest account."""
    return bool(get_settings().allow_guest_access)


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

    Platform credentials are deliberately NOT boot-blocking. They are only
    needed when actually publishing, so a missing or unconfigured platform
    degrades that one feature and is surfaced through /api/status, rather than
    preventing the server from starting at all.

    API_ACCESS_KEY is the exception and is checked separately: without it every
    /api/* request is refused with 503. See docs/ARCHITECTURE.md, "Failing
    closed".
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
