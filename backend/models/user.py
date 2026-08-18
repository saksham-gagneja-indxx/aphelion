"""
User model for Social Media Automation Agent
Stores Instagram and LinkedIn account information
"""

from typing import Optional

from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.utils.timeutil import utcnow
from backend.utils.database import Base


class User(Base):
    """User account model - stores Instagram and LinkedIn credentials"""

    __tablename__ = "users"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # ---- Identity -------------------------------------------------------
    # LinkedIn's OpenID Connect subject claim. This is the account's stable
    # identifier and the login key: users are found-or-created by it, so the
    # same person signing in twice never produces a duplicate record.
    # Nullable because legacy rows predate SSO; unique so it cannot collide.
    linkedin_sub = Column(String(255), unique=True, index=True, nullable=True)

    # Clerk's stable user id. The identity source for anyone who signed in
    # through Clerk rather than the legacy LinkedIn-as-login flow; the two are
    # independent columns so an account can in principle carry both (Clerk for
    # sign-in, LinkedIn purely for publish rights) without collision.
    clerk_id = Column(String(255), unique=True, index=True, nullable=True)

    # GitHub login, used by the MCP connector to map "who authenticated via
    # GitHub OAuth" to "which backend account they act as". Independent of
    # Clerk/LinkedIn sign-in - a person can use the web app via one identity
    # provider and the MCP connector via GitHub without those being linked.
    # Set via `python -m backend.admin_cli set-github <user> <login>`; there
    # is deliberately no self-service way to set this yet; an admin has to
    # vouch for the mapping since it decides which account a GitHub identity
    # can act as through the MCP server.
    github_username = Column(String(255), unique=True, index=True, nullable=True)

    full_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True, index=True)
    avatar_url = Column(String(1000), nullable=True)

    # "admin" or "operator". Admins can manage users and read the audit log.
    # Kept as a string rather than an enum column so adding a role later is a
    # code change, not a migration.
    role = Column(String(50), default="operator", nullable=False, index=True)
    last_seen_at = Column(DateTime, nullable=True)

    # Instagram credentials and info.
    # NULLABLE: users now sign up via LinkedIn and may never connect Instagram
    # at all. This was NOT NULL when the app assumed a single seeded user.
    instagram_username = Column(String(255), unique=True, index=True, nullable=True)
    instagram_session_id = Column(String(500), nullable=True)  # Session token for faster login
    instagram_user_id = Column(String(255), nullable=True)  # Instagram's internal user ID
    instagram_connected = Column(Boolean, default=False)

    # LinkedIn - OAuth 2.0 only, no password is ever stored.
    linkedin_email = Column(String(255), nullable=True)
    linkedin_session_id = Column(String(500), nullable=True)
    linkedin_connected = Column(Boolean, default=False)
    # Author URN used on every publish, e.g. "urn:li:person:abc123".
    linkedin_person_urn = Column(String(255), nullable=True)
    linkedin_access_token = Column(String(2000), nullable=True)
    linkedin_refresh_token = Column(String(2000), nullable=True)
    # Access tokens last ~60 days, refresh tokens ~365. Stored so the UI can
    # warn before expiry instead of discovering it when a scheduled post fires.
    linkedin_token_expires_at = Column(DateTime, nullable=True)
    # Scopes LinkedIn actually granted, space separated, as returned with the
    # token. Stored because sign-in succeeding says nothing about whether
    # publishing will: if the "Share on LinkedIn" product was never added to
    # the app, the member consents, signs in perfectly, and every publish then
    # fails on a missing w_member_social. This lets that be said up front
    # rather than discovered when a scheduled post fires.
    linkedin_scope = Column(String(500), nullable=True)

    # Per-user LinkedIn app credentials. Optional: when unset, the account
    # publishes through the operator's own app (LINKEDIN_CLIENT_ID/SECRET in
    # the server environment), same as before this column existed. Set, they
    # take over entirely for THIS account so each user can bring their own
    # LinkedIn developer app rather than sharing one.
    #
    # The secret is Fernet-encrypted (backend/utils/crypto.py) before it ever
    # reaches the database; the client id is not secret and is stored plain so
    # the setup UI can display it back without a decrypt round trip.
    linkedin_own_client_id = Column(String(255), nullable=True)
    linkedin_own_client_secret_encrypted = Column(String(1000), nullable=True)

    # A try-it-out account created without LinkedIn. Sandboxed rather than
    # privileged: its own data like any other account, but it can never publish
    # and can never be an administrator. See is_guest_account() for why those
    # two limits are enforced from this column rather than from the role.
    is_guest = Column(Boolean, default=False, nullable=True)

    # Account settings
    timezone = Column(String(50), default="Asia/Kolkata")
    account_name = Column(String(255), nullable=True)  # Display name
    is_active = Column(Boolean, default=True)

    # Preferences
    preferences = Column(JSON, default={
        "auto_analyze_engagement": True,
        "analysis_frequency_days": 7,
        "enable_caption_generation": True,
        "enable_hashtag_recommendations": True,
        "enable_comment_monitoring": False,
        "enable_auto_reply": False,
    })

    # Timestamps
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    last_login = Column(DateTime, nullable=True)
    instagram_connected_at = Column(DateTime, nullable=True)
    linkedin_connected_at = Column(DateTime, nullable=True)

    # Relationships
    posts = relationship("Post", back_populates="user", cascade="all, delete-orphan")
    analytics = relationship("Analytics", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, instagram={self.instagram_username})>"

    # ---- Roles ----------------------------------------------------------

    ROLE_ADMIN = "admin"
    ROLE_OPERATOR = "operator"
    VALID_ROLES = (ROLE_ADMIN, ROLE_OPERATOR)

    def is_admin(self) -> bool:
        # A guest is never an administrator, whatever the role column says.
        # Checked here rather than at each call site so that a guest promoted
        # by accident - by a bad migration, a seeded fixture, or a future admin
        # screen - still cannot reach anything.
        if self.is_guest:
            return False
        return self.role == self.ROLE_ADMIN

    def is_guest_account(self) -> bool:
        return bool(self.is_guest)

    def touch_last_seen(self):
        self.last_seen_at = utcnow()

    def to_identity(self) -> dict:
        """Shape returned by /api/me. Deliberately excludes tokens."""
        from backend.utils.config import linkedin_configured

        return {
            "id": self.id,
            "name": self.full_name,
            "email": self.email,
            "avatar_url": self.avatar_url,
            "role": self.role,
            "is_active": self.is_active,
            # The UI needs this to stop pushing a guest towards LinkedIn setup,
            # which is the one thing a guest has deliberately not done.
            "is_guest": bool(self.is_guest),
            "linkedin_connected": self.linkedin_token_valid(),
            "instagram_connected": bool(self.instagram_connected),
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "has_own_linkedin_app": self.has_own_linkedin_app(),
            # Whether ANY LinkedIn app is available to connect through - the
            # server's shared one, or this account's own. Distinct from
            # linkedin_connected: an operator can register the app (or an
            # admin can, once, for everyone) without any individual account
            # having clicked through the OAuth grant yet. The SPA uses this to
            # decide whether landing on Setup is actually necessary, or
            # whether there's nothing left to register and it should just go
            # straight to the app - see App.tsx's "/" redirect.
            "linkedin_app_configured": linkedin_configured() or self.has_own_linkedin_app(),
        }

    def to_admin_dict(self, post_count: int = 0) -> dict:
        """Shape returned by the admin user list. Still no tokens."""
        data = self.to_identity()
        data["post_count"] = post_count
        data["created_at"] = self.created_at.isoformat() if self.created_at else None
        return data

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "instagram_username": self.instagram_username,
            "full_name": self.full_name,
            "email": self.email,
            "role": self.role,
            "instagram_connected": self.instagram_connected,
            "linkedin_connected": self.linkedin_connected,
            "timezone": self.timezone,
            "account_name": self.account_name,
            "is_active": self.is_active,
            "preferences": self.preferences,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }

    def mark_instagram_connected(self, user_id: str, session_id: str):
        """Mark Instagram as successfully connected"""
        self.instagram_connected = True
        self.instagram_user_id = user_id
        self.instagram_session_id = session_id
        self.instagram_connected_at = utcnow()

    def mark_linkedin_connected(self, session_id: str):
        """Mark LinkedIn as successfully connected"""
        self.linkedin_connected = True
        self.linkedin_session_id = session_id
        self.linkedin_connected_at = utcnow()

    def store_linkedin_token(
        self,
        access_token: str,
        person_urn: str,
        expires_at=None,
        refresh_token: str = None,
        scope: str = None,
    ):
        """Record an OAuth grant from the LinkedIn callback."""
        self.linkedin_access_token = access_token
        self.linkedin_person_urn = person_urn
        self.linkedin_token_expires_at = expires_at
        if refresh_token:
            self.linkedin_refresh_token = refresh_token
        if scope is not None:
            self.linkedin_scope = scope
        self.linkedin_connected = True
        self.linkedin_connected_at = utcnow()
        self.updated_at = utcnow()

    def clear_linkedin_token(self):
        """Revoke locally - used when the member disconnects."""
        self.linkedin_access_token = None
        self.linkedin_refresh_token = None
        self.linkedin_person_urn = None
        self.linkedin_token_expires_at = None
        self.linkedin_connected = False
        self.updated_at = utcnow()

    def linkedin_token_valid(self) -> bool:
        """True when a token exists and has not passed its expiry."""
        if not (self.linkedin_access_token and self.linkedin_person_urn):
            return False
        if self.linkedin_token_expires_at is None:
            return True
        return self.linkedin_token_expires_at > utcnow()

    def can_publish_to_linkedin(self) -> bool:
        """True when the grant actually carries publishing rights.

        Unknown scope is treated as capable: grants stored before this column
        existed have none recorded, and reporting those accounts as unable to
        post would be wrong in the common case. A genuinely missing scope
        surfaces as a publish failure, which is the status quo for them.
        """
        if not self.linkedin_token_valid():
            return False
        if not self.linkedin_scope:
            return True
        return "w_member_social" in self.linkedin_scope.split()

    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = utcnow()

    def update_preferences(self, preferences: dict):
        """Update user preferences"""
        if self.preferences is None:
            self.preferences = {}
        self.preferences.update(preferences)
        self.updated_at = utcnow()

    # ---- Per-user LinkedIn app credentials ------------------------------

    def has_own_linkedin_app(self) -> bool:
        return bool(self.linkedin_own_client_id and self.linkedin_own_client_secret_encrypted)

    def set_own_linkedin_app(self, client_id: str, client_secret: str) -> None:
        from backend.utils.crypto import encrypt_secret

        self.linkedin_own_client_id = client_id
        self.linkedin_own_client_secret_encrypted = encrypt_secret(client_secret)
        self.updated_at = utcnow()

    def clear_own_linkedin_app(self) -> None:
        self.linkedin_own_client_id = None
        self.linkedin_own_client_secret_encrypted = None
        self.updated_at = utcnow()

    def effective_linkedin_client_id(self) -> Optional[str]:
        """This account's own app id if configured, else the server's."""
        if self.linkedin_own_client_id:
            return self.linkedin_own_client_id
        from backend.utils.config import get_settings

        return get_settings().linkedin_client_id

    def effective_linkedin_client_secret(self) -> Optional[str]:
        if self.linkedin_own_client_secret_encrypted:
            from backend.utils.crypto import decrypt_secret

            return decrypt_secret(self.linkedin_own_client_secret_encrypted)
        from backend.utils.config import get_settings

        return get_settings().linkedin_client_secret
