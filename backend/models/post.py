"""
Post model for Social Media Automation Agent
Stores information about reels and posts scheduled/posted
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Float, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.utils.timeutil import utcnow
from enum import Enum
from backend.utils.database import Base


class PostStatus(str, Enum):
    """Status of a post"""
    DRAFT = "draft"
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    POSTED = "posted"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PostPlatform(str, Enum):
    """Platform where post is published"""
    INSTAGRAM = "instagram"
    LINKEDIN = "linkedin"
    BOTH = "both"


class Post(Base):
    """Post/Reel model - stores information about scheduled and posted reels"""

    __tablename__ = "posts"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Foreign keys
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    media_file_id = Column(Integer, ForeignKey("media_files.id"), nullable=True)

    # Media information
    video_path = Column(String(500), nullable=False)  # Path to video file
    video_url = Column(String(500), nullable=True)  # Instagram/LinkedIn URL after posting
    thumbnail_path = Column(String(500), nullable=True)  # Thumbnail image path
    video_duration = Column(Float, nullable=True)  # Duration in seconds
    video_size = Column(Integer, nullable=True)  # File size in bytes

    # Content
    caption = Column(Text, nullable=True)  # Post caption/description
    hashtags = Column(String(500), nullable=True)  # Comma-separated hashtags
    ai_generated_caption = Column(Boolean, default=False)  # Was caption AI-generated?
    ai_generated_hashtags = Column(Boolean, default=False)  # Were hashtags AI-generated?

    # Scheduling
    status = Column(String(50), default=PostStatus.DRAFT, index=True)
    platform = Column(String(50), default=PostPlatform.INSTAGRAM)
    scheduled_time = Column(DateTime, nullable=True, index=True)
    posted_at = Column(DateTime, nullable=True)

    # Analytics
    instagram_post_id = Column(String(255), nullable=True)  # Instagram post ID
    linkedin_post_id = Column(String(255), nullable=True)  # LinkedIn post ID
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    engagement_rate = Column(Float, nullable=True)

    # Metadata
    # Attribute is `post_metadata` because `metadata` is reserved by the
    # SQLAlchemy Declarative API; the underlying column is still "metadata".
    post_metadata = Column("metadata", JSON, default={})  # Additional metadata
    error_message = Column(Text, nullable=True)  # Error details if posting failed
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # Job scheduling info
    job_id = Column(String(255), nullable=True, unique=True)  # APScheduler job ID

    # Timestamps
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    user = relationship("User", back_populates="posts")
    media_file = relationship("MediaFile", back_populates="posts")

    def __repr__(self):
        return f"<Post(id={self.id}, status={self.status}, platform={self.platform})>"

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "video_path": self.video_path,
            "thumbnail_path": self.thumbnail_path,
            "video_duration": self.video_duration,
            "job_id": self.job_id,
            "caption": self.caption,
            "hashtags": self.hashtags,
            "status": self.status,
            "platform": self.platform,
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
            "views": self.views,
            "likes": self.likes,
            "comments": self.comments,
            "shares": self.shares,
            "engagement_rate": self.engagement_rate,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def mark_as_posted(self, post_id: str, platform: str = "instagram"):
        """Mark post as successfully posted"""
        self.status = PostStatus.POSTED
        self.posted_at = utcnow()

        if platform == "instagram":
            self.instagram_post_id = post_id
        elif platform == "linkedin":
            self.linkedin_post_id = post_id

        self.updated_at = utcnow()

    def mark_as_failed(self, error_message: str):
        """Mark post as failed"""
        self.status = PostStatus.FAILED
        self.error_message = error_message
        self.retry_count += 1
        self.updated_at = utcnow()

    def mark_as_cancelled(self):
        """Mark post as cancelled"""
        self.status = PostStatus.CANCELLED
        self.updated_at = utcnow()

    def can_retry(self) -> bool:
        """Check if post can be retried"""
        return self.retry_count < self.max_retries and self.status == PostStatus.FAILED

    def update_analytics(self, views: int, likes: int, comments: int, shares: int):
        """Update post analytics"""
        self.views = views
        self.likes = likes
        self.comments = comments
        self.shares = shares

        # Calculate engagement rate
        total_engagement = likes + comments + shares
        if self.views > 0:
            self.engagement_rate = (total_engagement / self.views) * 100
        else:
            self.engagement_rate = 0

        self.updated_at = utcnow()
