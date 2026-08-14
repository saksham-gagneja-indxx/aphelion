"""
Analytics Engine - Analyzes engagement patterns and determines optimal posting times
Processes Instagram engagement data and provides recommendations
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from backend.utils.timeutil import utcnow
from statistics import mean, stdev
import pytz
from backend.utils.logger import get_logger
from backend.utils.config import get_settings
from backend.models.user import User
from backend.models.analytics import Analytics
from backend.models.post import Post
from sqlalchemy.orm import Session
from sqlalchemy import and_

logger = get_logger("social_media_automation.analytics")


class AnalyticsEngine:
    """Analyzes engagement data and provides optimization recommendations"""

    def __init__(self, user: User, db_session: Session):
        """
        Initialize Analytics Engine

        Args:
            user: User database model instance
            db_session: SQLAlchemy database session
        """
        self.user = user
        self.db_session = db_session
        self.settings = get_settings()

    def analyze_engagement(
        self,
        engagement_data: Dict,
        platform: str = "instagram"
    ) -> Optional[Analytics]:
        """
        Analyze engagement data and save analytics to database

        Args:
            engagement_data: Raw engagement data from agent
            platform: Platform name (instagram, linkedin)

        Returns:
            Analytics model instance or None
        """
        try:
            logger.info(f"📊 Analyzing engagement data for {platform}")

            # Create or get analytics record
            analytics = self.db_session.query(Analytics).filter(
                and_(
                    Analytics.user_id == self.user.id,
                    Analytics.platform == platform
                )
            ).first()

            if not analytics:
                analytics = Analytics(
                    user_id=self.user.id,
                    platform=platform
                )
                self.db_session.add(analytics)

            # Process engagement data
            analysis_dict = self._process_engagement_data(engagement_data)

            # Update analytics record
            analytics.update_analysis(analysis_dict)

            self.db_session.commit()

            logger.info(f"✅ Engagement analysis saved")
            logger.debug(f"Best hours: {analytics.best_posting_hours}")

            return analytics

        except Exception as e:
            logger.error(f"❌ Engagement analysis failed: {str(e)}")
            self.db_session.rollback()
            return None

    def _process_engagement_data(self, engagement_data: Dict) -> Dict:
        """
        Process raw engagement data into actionable insights

        Args:
            engagement_data: Raw engagement data from agent

        Returns:
            dict: Processed analysis data
        """
        try:
            # Extract hourly and daily data
            hourly_avg = engagement_data.get("hourly_average", {})
            daily_avg = engagement_data.get("daily_average", {})

            # Convert hour strings to integers and sort
            hourly_sorted = {}
            for hour_str, metrics in hourly_avg.items():
                hour_int = int(hour_str)
                engagement = metrics.get("avg_likes", 0) + metrics.get("avg_comments", 0)
                hourly_sorted[hour_int] = engagement

            # Get best hours (top 6)
            best_hours = sorted(
                hourly_sorted.items(),
                key=lambda x: x[1],
                reverse=True
            )[:6]
            best_hours_list = [h[0] for h in best_hours]

            # Get best days
            best_days_list = []
            daily_sorted = {}
            for day_str, metrics in daily_avg.items():
                engagement = metrics.get("avg_likes", 0) + metrics.get("avg_comments", 0)
                daily_sorted[day_str] = engagement

            for day_str, _ in sorted(
                daily_sorted.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]:
                day_map = {
                    "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
                    "Friday": 4, "Saturday": 5, "Sunday": 6
                }
                if day_str in day_map:
                    best_days_list.append(day_map[day_str])

            # Find peak engagement hour
            peak_hour = max(hourly_sorted.items(), key=lambda x: x[1])[0] if hourly_sorted else None

            # Calculate average metrics
            all_engagements = list(hourly_sorted.values())
            avg_engagement = mean(all_engagements) if all_engagements else 0

            analysis_dict = {
                "best_posting_hours": best_hours_list,
                "best_posting_days": best_days_list,
                "peak_engagement_hour": peak_hour,
                "hourly_analytics": hourly_avg,
                "daily_analytics": daily_avg,
                "weekly_analytics": {},
                "total_posts_analyzed": engagement_data.get("posts_analyzed", 0),
                "average_likes": engagement_data.get("average_likes", 0),
                "average_comments": engagement_data.get("average_comments", 0),
                "average_shares": engagement_data.get("average_shares", 0),
                "average_engagement_rate": avg_engagement,
                "trending_hashtags": [],
                "trending_content_themes": [],
                "posting_frequency_optimal": 7,  # Default: one post per week
            }

            return analysis_dict

        except Exception as e:
            logger.error(f"Error processing engagement data: {str(e)}")
            return {}

    def get_next_optimal_posting_time(self) -> Optional[Dict]:
        """
        Calculate the next optimal time to post based on analytics

        Returns:
            dict: Next optimal posting time information
        """
        try:
            # Get latest analytics
            analytics = self.db_session.query(Analytics).filter(
                Analytics.user_id == self.user.id
            ).order_by(Analytics.updated_at.desc()).first()

            if not analytics or not analytics.best_posting_hours:
                logger.warning("⚠️  No analytics data available")
                return None

            logger.info("🕐 Calculating next optimal posting time")

            # Get current time in user's timezone
            tz = pytz.timezone(self.user.timezone)
            now_local = datetime.now(tz)

            # Best hours and days
            best_hours = analytics.best_posting_hours[:3]  # Top 3 hours
            best_days = analytics.best_posting_days or [now_local.weekday()]  # Top days

            # Find next optimal time
            next_time = None
            min_wait = float('inf')

            for days_offset in range(0, 8):  # Look ahead up to 8 days
                check_date = now_local + timedelta(days=days_offset)

                # Check if this day is optimal
                if check_date.weekday() not in best_days and days_offset > 0:
                    continue

                # Check optimal hours for this day
                for hour in best_hours:
                    target_time = check_date.replace(hour=hour, minute=0, second=0, microsecond=0)

                    # Make sure time is in future
                    if target_time > now_local:
                        wait_hours = (target_time - now_local).total_seconds() / 3600
                        if wait_hours < min_wait:
                            min_wait = wait_hours
                            next_time = target_time

            if next_time is None:
                logger.warning("⚠️  Could not calculate next optimal time")
                return None

            wait_hours = (next_time - now_local).total_seconds() / 3600

            result = {
                "optimal_time": next_time.isoformat(),
                "optimal_hour": next_time.hour,
                "optimal_day": next_time.strftime("%A"),
                "wait_hours": round(wait_hours, 1),
                "wait_minutes": round(wait_hours * 60, 0),
                "confidence": self._calculate_confidence(analytics),
                "best_hours": best_hours,
                "best_days": best_days,
            }

            logger.info(f"✅ Next optimal posting time: {next_time.strftime('%Y-%m-%d %H:%M %Z')}")
            return result

        except Exception as e:
            logger.error(f"❌ Error calculating next optimal time: {str(e)}")
            return None

    def _calculate_confidence(self, analytics: Analytics) -> float:
        """
        Calculate confidence score for recommendations (0-100)

        Args:
            analytics: Analytics model instance

        Returns:
            float: Confidence score
        """
        try:
            score = 50  # Base score

            # Add points for more data
            if analytics.total_posts_analyzed >= 20:
                score += 30
            elif analytics.total_posts_analyzed >= 10:
                score += 15
            elif analytics.total_posts_analyzed >= 5:
                score += 7

            # Add points if recently updated
            if analytics.last_calculated_at:
                days_old = (utcnow() - analytics.last_calculated_at).days
                if days_old <= 7:
                    score += 10
                elif days_old <= 30:
                    score += 5

            return min(score, 100)

        except Exception as e:
            logger.debug(f"Error calculating confidence: {str(e)}")
            return 50

    def get_analytics_summary(self) -> Optional[Dict]:
        """Get summary of current analytics"""
        try:
            analytics = self.db_session.query(Analytics).filter(
                Analytics.user_id == self.user.id
            ).order_by(Analytics.updated_at.desc()).first()

            if not analytics:
                return None

            return {
                "total_posts_analyzed": analytics.total_posts_analyzed,
                "average_likes": analytics.average_likes,
                "average_comments": analytics.average_comments,
                "best_posting_hours": analytics.best_posting_hours,
                "best_posting_days": analytics.best_posting_days,
                "peak_engagement_hour": analytics.peak_engagement_hour,
                "confidence": self._calculate_confidence(analytics),
                "last_updated": analytics.last_calculated_at.isoformat() if analytics.last_calculated_at else None,
            }

        except Exception as e:
            logger.error(f"Error getting analytics summary: {str(e)}")
            return None


def get_analytics_engine(user: User, db_session: Session) -> AnalyticsEngine:
    """Create analytics engine for a user"""
    return AnalyticsEngine(user, db_session)
