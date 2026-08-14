"""
Analytics model for Social Media Automation Agent
Stores engagement analytics and optimal posting time calculations
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.utils.timeutil import utcnow
from backend.utils.database import Base


class Analytics(Base):
    """Analytics model - stores engagement data and posting time analysis"""

    __tablename__ = "analytics"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Foreign key
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Analysis metadata
    analysis_type = Column(String(50), default="hourly")  # hourly, daily, weekly
    platform = Column(String(50), default="instagram")  # instagram, linkedin
    analysis_date = Column(DateTime, default=utcnow, nullable=False)

    # Engagement metrics by time
    best_posting_hours = Column(JSON, default=[])  # Top 5-6 hours for posting
    best_posting_days = Column(JSON, default=[])  # Best days of week (0-6, 0=Monday)

    # Hourly breakdown
    hourly_analytics = Column(JSON, default={})  # {hour: {avg_likes, avg_comments, count}}

    # Daily breakdown
    daily_analytics = Column(JSON, default={})  # {day: {avg_likes, avg_comments, count}}

    # Weekly breakdown
    weekly_analytics = Column(JSON, default={})  # {week: {avg_likes, avg_comments, count}}

    # Summary metrics
    total_posts_analyzed = Column(Integer, default=0)
    average_likes = Column(Float, nullable=True)
    average_comments = Column(Float, nullable=True)
    average_shares = Column(Float, nullable=True)
    average_engagement_rate = Column(Float, nullable=True)

    # Trend information
    trending_hashtags = Column(JSON, default=[])  # Top performing hashtags
    trending_content_themes = Column(JSON, default=[])  # Content themes that perform well
    posting_frequency_optimal = Column(Integer, nullable=True)  # Posts per week recommendation

    # Time-based analytics
    peak_engagement_hour = Column(Integer, nullable=True)  # 0-23
    peak_engagement_day = Column(Integer, nullable=True)  # 0-6, 0=Monday
    slowest_hour = Column(Integer, nullable=True)
    slowest_day = Column(Integer, nullable=True)

    # Growth metrics
    follower_growth_rate = Column(Float, nullable=True)  # Followers gained/week
    engagement_growth_rate = Column(Float, nullable=True)  # Engagement trend

    # Metadata
    data_source = Column(String(100), default="instagram_api")
    last_analysis_posts_count = Column(Integer, default=0)  # Number of posts analyzed

    # Timestamps
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    last_calculated_at = Column(DateTime, nullable=True)

    # Relationship
    user = relationship("User", back_populates="analytics")

    def __repr__(self):
        return f"<Analytics(id={self.id}, user_id={self.user_id}, platform={self.platform})>"

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "platform": self.platform,
            "analysis_type": self.analysis_type,
            "best_posting_hours": self.best_posting_hours,
            "best_posting_days": self.best_posting_days,
            "average_likes": self.average_likes,
            "average_comments": self.average_comments,
            "average_engagement_rate": self.average_engagement_rate,
            "total_posts_analyzed": self.total_posts_analyzed,
            "peak_engagement_hour": self.peak_engagement_hour,
            "peak_engagement_day": self.peak_engagement_day,
            "trending_hashtags": self.trending_hashtags,
            "follower_growth_rate": self.follower_growth_rate,
            "engagement_growth_rate": self.engagement_growth_rate,
            "last_calculated_at": self.last_calculated_at.isoformat() if self.last_calculated_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def update_analysis(self, analysis_data: dict):
        """Update analytics with new analysis data"""
        self.best_posting_hours = analysis_data.get("best_posting_hours", [])
        self.best_posting_days = analysis_data.get("best_posting_days", [])
        self.hourly_analytics = analysis_data.get("hourly_analytics", {})
        self.daily_analytics = analysis_data.get("daily_analytics", {})
        self.weekly_analytics = analysis_data.get("weekly_analytics", {})
        self.total_posts_analyzed = analysis_data.get("total_posts_analyzed", 0)
        self.average_likes = analysis_data.get("average_likes")
        self.average_comments = analysis_data.get("average_comments")
        self.average_shares = analysis_data.get("average_shares")
        self.average_engagement_rate = analysis_data.get("average_engagement_rate")
        self.peak_engagement_hour = analysis_data.get("peak_engagement_hour")
        self.peak_engagement_day = analysis_data.get("peak_engagement_day")
        self.trending_hashtags = analysis_data.get("trending_hashtags", [])
        self.trending_content_themes = analysis_data.get("trending_content_themes", [])
        self.posting_frequency_optimal = analysis_data.get("posting_frequency_optimal")
        self.follower_growth_rate = analysis_data.get("follower_growth_rate")
        self.engagement_growth_rate = analysis_data.get("engagement_growth_rate")
        self.last_calculated_at = utcnow()
        self.updated_at = utcnow()

    def get_next_optimal_time(self) -> dict:
        """Get the next optimal time to post based on analysis"""
        if not self.best_posting_hours or not self.best_posting_days:
            return {"hour": 12, "day": 0, "confidence": 0}

        return {
            "hours": self.best_posting_hours[:3],  # Top 3 hours
            "days": self.best_posting_days[:2],  # Top 2 days
            "peak_hour": self.peak_engagement_hour,
            "peak_day": self.peak_engagement_day,
        }
