"""
LinkedIn OAuth credential storage model.

Stores encrypted LinkedIn OAuth tokens and account information.
Tokens are encrypted at rest using Fernet symmetric encryption.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.utils.timeutil import utcnow
from backend.utils.database import Base


class LinkedInCredential(Base):
    """Encrypted LinkedIn OAuth token storage (one-to-one with User)."""

    __tablename__ = "linkedin_credentials"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)

    # LinkedIn OAuth Token (ENCRYPTED with Fernet AES-128)
    access_token_encrypted = Column(String(2000), nullable=False)
    refresh_token_encrypted = Column(String(2000), nullable=False)

    # LinkedIn Account Info (public, not encrypted)
    linkedin_person_urn = Column(String(255), nullable=True)  # e.g., "urn:li:person:ABC123"
    linkedin_account_name = Column(String(255), nullable=True)  # Display name
    linkedin_profile_url = Column(String(500), nullable=True)  # Profile URL

    # Token Lifecycle
    token_expires_at = Column(DateTime, nullable=True)
    last_refreshed_at = Column(DateTime, nullable=True)
    refresh_count = Column(Integer, default=0)

    # Status
    is_connected = Column(Boolean, default=True, index=True)
    connection_verified_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationship
    user = relationship("User", back_populates="linkedin_credential")

    def __repr__(self):
        return f"<LinkedInCredential(user_id={self.user_id}, is_connected={self.is_connected})>"

    def is_token_expired(self) -> bool:
        """Check if token has expired."""
        if self.token_expires_at is None:
            return False
        return utcnow() >= self.token_expires_at

    def should_refresh(self) -> bool:
        """Check if token should be refreshed (within 1 hour of expiration)."""
        if self.token_expires_at is None:
            return False
        from datetime import timedelta
        refresh_threshold = self.token_expires_at - timedelta(hours=1)
        return utcnow() >= refresh_threshold

    def mark_refreshed(self, expires_at: datetime) -> None:
        """Mark token as refreshed with new expiration time."""
        self.token_expires_at = expires_at
        self.last_refreshed_at = utcnow()
        self.refresh_count += 1
        self.updated_at = utcnow()

    def mark_verified(self) -> None:
        """Mark connection as verified."""
        self.is_connected = True
        self.connection_verified_at = utcnow()
        self.updated_at = utcnow()

    def disconnect(self) -> None:
        """Mark connection as disconnected."""
        self.is_connected = False
        self.updated_at = utcnow()
