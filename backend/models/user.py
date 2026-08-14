"""
User model for Social Media Automation Agent
Stores Instagram and LinkedIn account information
"""

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

    # Instagram credentials and info
    instagram_username = Column(String(255), unique=True, index=True, nullable=False)
    instagram_session_id = Column(String(500), nullable=True)  # Session token for faster login
    instagram_user_id = Column(String(255), nullable=True)  # Instagram's internal user ID
    instagram_connected = Column(Boolean, default=False)

    # LinkedIn credentials and info (Phase 3)
    linkedin_email = Column(String(255), nullable=True)
    linkedin_session_id = Column(String(500), nullable=True)
    linkedin_connected = Column(Boolean, default=False)

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

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "instagram_username": self.instagram_username,
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

    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = utcnow()

    def update_preferences(self, preferences: dict):
        """Update user preferences"""
        if self.preferences is None:
            self.preferences = {}
        self.preferences.update(preferences)
        self.updated_at = utcnow()
