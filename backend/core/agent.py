"""
Instagram Agent - Core Instagram interaction module
Handles authentication, posting, and engagement tracking
"""

# instagrapi is an OPTIONAL dependency and is not installed in deployed
# environments. It is a reverse-engineered client that logs in with a username
# and password, which violates Instagram's Terms of Service - publishing now
# goes through backend/core/publishers/ instead, and InstagramPublisher is
# disabled pending Meta App Review.
#
# This module is kept only because routes.py still exposes the legacy Instagram
# endpoints. The import is guarded so the app boots without instagrapi present;
# the endpoints then fail with a clear message rather than an ImportError at
# startup that would take the whole service down.
try:
    from instagrapi import Client

    INSTAGRAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only in deployed envs
    Client = None
    INSTAGRAPI_AVAILABLE = False

from typing import Optional, List, Dict
import json
from datetime import datetime, timedelta
from backend.utils.timeutil import utcnow
from pathlib import Path
from backend.utils.logger import get_logger
from backend.utils.config import get_settings
from backend.models.user import User
from backend.models.post import Post
from sqlalchemy.orm import Session

logger = get_logger("social_media_automation.agent")


class InstagramAgent:
    """Main Instagram agent for handling all Instagram operations"""

    def __init__(self, user: User, db_session: Session):
        """
        Initialize Instagram Agent

        Args:
            user: User database model instance
            db_session: SQLAlchemy database session
        """
        self.user = user
        self.db_session = db_session
        self.client = None
        self.settings = get_settings()
        self._session_file = Path("data/instagram_sessions") / f"{user.instagram_username}.json"
        self._ensure_session_dir()

    def _ensure_session_dir(self):
        """Create session directory if it doesn't exist"""
        self._session_file.parent.mkdir(parents=True, exist_ok=True)

    def authenticate(self, username: str, password: str) -> bool:
        """
        Authenticate with Instagram using username and password

        Args:
            username: Instagram username
            password: Instagram password

        Returns:
            bool: True if authentication successful
        """
        if not INSTAGRAPI_AVAILABLE:
            logger.error(
                "Instagram authentication is unavailable: instagrapi is not "
                "installed. Instagram publishing is disabled pending Meta App "
                "Review - use LinkedIn instead."
            )
            return False

        try:
            logger.info(f"🔐 Attempting Instagram authentication for: {username}")

            # Initialize client
            self.client = Client()

            # Try to load existing session first
            if self._load_session():
                logger.info("✅ Loaded existing Instagram session")
                return True

            # Otherwise, perform new login
            self.client.login(username, password)
            logger.info("✅ Successfully logged in to Instagram")

            # Save session
            self._save_session()

            # Update user model
            self.user.mark_instagram_connected(
                user_id=str(self.client.user_id),
                session_id=self.client.sessionid
            )
            self.db_session.commit()

            return True

        except Exception as e:
            logger.error(f"❌ Instagram authentication failed: {str(e)}")
            return False

    def _save_session(self) -> bool:
        """Save Instagram session to file"""
        try:
            session_data = {
                "sessionid": self.client.sessionid,
                "user_id": self.client.user_id,
                "username": self.client.username,
                "saved_at": utcnow().isoformat()
            }

            with open(self._session_file, "w") as f:
                json.dump(session_data, f)

            logger.debug(f"Session saved: {self._session_file}")
            return True

        except Exception as e:
            logger.warning(f"⚠️  Could not save session: {str(e)}")
            return False

    def _load_session(self) -> bool:
        """Load Instagram session from file"""
        try:
            if not self._session_file.exists():
                return False

            with open(self._session_file, "r") as f:
                session_data = json.load(f)

            # TODO: Implement session restoration
            # This is a placeholder - actual session restoration depends on instagrapi version
            logger.info("Session file found, but restoration not yet implemented")
            return False

        except Exception as e:
            logger.warning(f"⚠️  Could not load session: {str(e)}")
            return False

    def is_connected(self) -> bool:
        """Check if agent is connected to Instagram"""
        return self.client is not None and self.user.instagram_connected

    def post_reel(
        self,
        video_path: str,
        caption: str = "",
        thumbnail_path: Optional[str] = None,
        post_id: Optional[int] = None
    ) -> Optional[Dict]:
        """
        Post a reel to Instagram

        Args:
            video_path: Path to video file
            caption: Caption for the reel
            thumbnail_path: Path to custom thumbnail
            post_id: Database post ID for tracking

        Returns:
            dict: Posted media info or None if failed
        """
        try:
            if not self.is_connected():
                logger.error("❌ Not connected to Instagram")
                return None

            logger.info(f"📤 Posting reel: {Path(video_path).name}")

            # Post reel
            media = self.client.clip_upload(
                video_path,
                caption=caption,
                thumbnail=thumbnail_path
            )

            logger.info(f"✅ Reel posted successfully: {media.pk}")

            # Update database if post_id provided
            if post_id:
                post = self.db_session.query(Post).filter(Post.id == post_id).first()
                if post:
                    post.mark_as_posted(str(media.pk), platform="instagram")
                    self.db_session.commit()

            return {
                "post_id": media.pk,
                "url": f"https://instagram.com/p/{media.code}/",
                "posted_at": utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"❌ Failed to post reel: {str(e)}")
            if post_id:
                post = self.db_session.query(Post).filter(Post.id == post_id).first()
                if post:
                    post.mark_as_failed(str(e))
                    self.db_session.commit()
            return None

    def get_recent_posts(self, limit: int = 30) -> List[Dict]:
        """
        Get recent posts from Instagram user

        Args:
            limit: Number of posts to fetch (max 30)

        Returns:
            list: List of post data
        """
        try:
            if not self.is_connected():
                logger.error("❌ Not connected to Instagram")
                return []

            logger.info(f"📊 Fetching recent posts (limit: {limit})")

            # Get user info first
            user = self.client.user_info(self.client.user_id)
            posts = self.client.user_medias(self.client.user_id, amount=limit)

            posts_data = []
            for post in posts:
                posts_data.append({
                    "id": post.pk,
                    "caption": post.caption,
                    "likes": post.like_count,
                    "comments": post.comment_count,
                    "posted_at": post.taken_at.isoformat() if post.taken_at else None,
                    "engagement": post.like_count + post.comment_count
                })

            logger.info(f"✅ Fetched {len(posts_data)} posts")
            return posts_data

        except Exception as e:
            logger.error(f"❌ Failed to fetch recent posts: {str(e)}")
            return []

    def get_engagement_data(self, limit: int = 30) -> Dict:
        """
        Fetch and analyze engagement data from recent posts

        Args:
            limit: Number of recent posts to analyze

        Returns:
            dict: Engagement analysis data
        """
        try:
            if not self.is_connected():
                logger.error("❌ Not connected to Instagram")
                return {}

            logger.info(f"📈 Analyzing engagement data from last {limit} posts")

            posts = self.get_recent_posts(limit)

            if not posts:
                logger.warning("⚠️  No posts found for analysis")
                return {}

            # Calculate hourly engagement
            hourly_data = {}
            daily_data = {}

            for post in posts:
                posted_at = datetime.fromisoformat(post["posted_at"])
                hour = posted_at.hour
                day = posted_at.strftime("%A")

                # Hourly aggregation
                if hour not in hourly_data:
                    hourly_data[hour] = {"likes": [], "comments": [], "count": 0}

                hourly_data[hour]["likes"].append(post["likes"])
                hourly_data[hour]["comments"].append(post["comments"])
                hourly_data[hour]["count"] += 1

                # Daily aggregation
                if day not in daily_data:
                    daily_data[day] = {"likes": [], "comments": [], "count": 0}

                daily_data[day]["likes"].append(post["likes"])
                daily_data[day]["comments"].append(post["comments"])
                daily_data[day]["count"] += 1

            # Calculate averages
            hourly_avg = {}
            for hour, data in hourly_data.items():
                hourly_avg[hour] = {
                    "avg_likes": sum(data["likes"]) / len(data["likes"]),
                    "avg_comments": sum(data["comments"]) / len(data["comments"]),
                    "post_count": data["count"]
                }

            daily_avg = {}
            for day, data in daily_data.items():
                daily_avg[day] = {
                    "avg_likes": sum(data["likes"]) / len(data["likes"]),
                    "avg_comments": sum(data["comments"]) / len(data["comments"]),
                    "post_count": data["count"]
                }

            # Find best hours and days
            best_hours = sorted(
                hourly_avg.items(),
                key=lambda x: x[1]["avg_likes"] + x[1]["avg_comments"],
                reverse=True
            )[:6]

            best_days = sorted(
                daily_avg.items(),
                key=lambda x: x[1]["avg_likes"] + x[1]["avg_comments"],
                reverse=True
            )[:3]

            engagement_data = {
                "posts_analyzed": len(posts),
                "hourly_average": hourly_avg,
                "daily_average": daily_avg,
                "best_hours": [h[0] for h in best_hours],
                "best_days": [d[0] for d in best_days],
                "average_likes": sum(p["likes"] for p in posts) / len(posts),
                "average_comments": sum(p["comments"] for p in posts) / len(posts),
                "analysis_date": utcnow().isoformat()
            }

            logger.info(f"✅ Engagement analysis complete")
            logger.debug(f"Best hours for posting: {engagement_data['best_hours']}")

            return engagement_data

        except Exception as e:
            logger.error(f"❌ Failed to analyze engagement data: {str(e)}")
            return {}

    def get_followers_count(self) -> Optional[int]:
        """Get current follower count"""
        try:
            if not self.is_connected():
                return None

            user = self.client.user_info(self.client.user_id)
            return user.follower_count

        except Exception as e:
            logger.error(f"❌ Failed to get follower count: {str(e)}")
            return None

    def get_status(self) -> Dict:
        """Get current agent status"""
        return {
            "connected": self.is_connected(),
            "username": self.user.instagram_username,
            "user_id": self.user.instagram_user_id,
            "connected_since": self.user.instagram_connected_at.isoformat() if self.user.instagram_connected_at else None,
            "last_login": self.user.last_login.isoformat() if self.user.last_login else None,
        }

    def disconnect(self):
        """Disconnect from Instagram"""
        try:
            if self.client:
                self.client.logout()
                logger.info("✅ Disconnected from Instagram")
        except Exception as e:
            logger.warning(f"⚠️  Error during disconnect: {str(e)}")
        finally:
            self.client = None


# Global agent instance manager
_agent_instances = {}


def get_agent(user: User, db_session: Session) -> InstagramAgent:
    """Get or create an Instagram agent for a user"""
    if user.id not in _agent_instances:
        _agent_instances[user.id] = InstagramAgent(user, db_session)

    return _agent_instances[user.id]


def clear_agent(user_id: int):
    """Clear agent instance for a user"""
    if user_id in _agent_instances:
        _agent_instances[user_id].disconnect()
        del _agent_instances[user_id]
        logger.info(f"Cleared agent for user {user_id}")
