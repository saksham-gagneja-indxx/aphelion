"""
Media file storage model.

Stores uploaded video and image files with metadata.
Files are encrypted at rest in storage and auto-cleaned up after 30 days.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from backend.utils.timeutil import utcnow
from backend.utils.database import Base


class MediaFile(Base):
    """Uploaded media file (video or image)."""

    __tablename__ = "media_files"

    id = Column(Integer, primary_key=True, index=True)

    # Ownership
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # File Info
    filename = Column(String(255), nullable=False)  # Original filename
    file_size_bytes = Column(Integer, nullable=False)
    media_type = Column(String(50), nullable=False)  # 'video' or 'image'
    mime_type = Column(String(100), nullable=False)  # 'video/mp4', 'image/jpeg'
    file_extension = Column(String(10), nullable=False)  # 'mp4', 'jpg'

    # Storage
    storage_path = Column(String(500), nullable=False)  # Full path: /user_{id}/{uuid}.mp4
    storage_url = Column(String(1000))  # Public URL if applicable
    storage_service = Column(String(50))  # 's3', 'local'

    # File Details
    duration_seconds = Column(Numeric(10, 2))  # For videos
    width = Column(Integer)  # Image/video width
    height = Column(Integer)  # Image/video height
    thumbnail_url = Column(String(1000))  # Generated thumbnail

    # Upload Status
    upload_completed_at = Column(DateTime, nullable=False)

    # Lifecycle
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime)
    expires_at = Column(DateTime, default=lambda: utcnow() + timedelta(days=30), index=True)

    # Timestamps
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", backref="media_files")
    posts = relationship("Post", back_populates="media_file")

    def __repr__(self):
        return f"<MediaFile(id={self.id}, filename={self.filename}, size={self.file_size_bytes})>"

    def is_video(self) -> bool:
        """Check if this is a video file."""
        return self.media_type == "video"

    def is_image(self) -> bool:
        """Check if this is an image file."""
        return self.media_type == "image"

    def is_expired(self) -> bool:
        """Check if file has expired and should be deleted."""
        if self.expires_at is None:
            return False
        return utcnow() >= self.expires_at

    def mark_deleted(self) -> None:
        """Mark file as deleted (soft delete)."""
        self.is_deleted = True
        self.deleted_at = utcnow()

    def extend_expiration(self, days: int = 30) -> None:
        """Extend file expiration by N days (when referenced by a post)."""
        self.expires_at = utcnow() + timedelta(days=days)
