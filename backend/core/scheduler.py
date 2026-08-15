"""
Smart Scheduler - Manages scheduling and automated posting using APScheduler
Handles job persistence, queue management, and optimal time scheduling
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
import pytz

from backend.utils.logger import get_logger
from backend.utils.config import get_settings
from backend.utils.database import get_session
from backend.models.user import User
from backend.models.post import Post, PostStatus
from sqlalchemy.orm import Session

logger = get_logger("social_media_automation.scheduler")


class SmartScheduler:
    """Manages scheduled posts and automated posting"""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.settings = get_settings()
        self.queue_file = Path("data/schedule_queue.json")
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    def initialize(self):
        """Initialize the scheduler"""
        if self._initialized:
            return

        try:
            logger.info("🚀 Initializing Smart Scheduler")

            # Restore jobs from database
            self._restore_scheduled_jobs()

            # Start scheduler
            if not self.scheduler.running:
                self.scheduler.start()
                logger.info("✅ Scheduler started")

            self._initialized = True

        except Exception as e:
            logger.error(f"❌ Scheduler initialization failed: {str(e)}")
            raise

    def _restore_scheduled_jobs(self):
        """Re-arm scheduled posts after a restart, and account for the misses.

        APScheduler's job store is in memory, so the Post table is the only
        durable record of what is due - every process start has to rebuild the
        timers from it. Posts that came due while nothing was running are
        either still publishable (within the grace window) or too late, and
        the too-late ones are failed here. Leaving them `scheduled` is what
        made missed posts invisible: the Queue showed them as pending forever
        and no failure was ever recorded.
        """
        db = None
        try:
            db = get_session()
            scheduled_posts = db.query(Post).filter(
                Post.status == PostStatus.SCHEDULED
            ).all()

            logger.info(f"📋 Found {len(scheduled_posts)} scheduled posts to restore")

            grace = timedelta(seconds=self.settings.scheduler_misfire_grace_seconds)
            restored = 0
            expired = 0

            for post in scheduled_posts:
                if not post.scheduled_time or not post.job_id:
                    # schedule_post() writes status, scheduled_time and job_id
                    # in one commit, so this row cannot fire and cannot be
                    # explained. Surface it rather than skipping in silence.
                    logger.warning(
                        f"⚠️  Post {post.id} is scheduled but has no "
                        f"{'scheduled_time' if not post.scheduled_time else 'job_id'}"
                    )
                    continue

                tz = self._post_timezone(post)
                run_at = self._as_aware(post.scheduled_time, tz)
                late_by = datetime.now(tz) - run_at

                if late_by > grace:
                    post.mark_as_failed(
                        f"Missed its scheduled time by {self._humanise(late_by)}. "
                        f"The server was not running when it came due, and the "
                        f"post was past the {self._humanise(grace)} grace window "
                        f"by the time it started. Reschedule it to publish."
                    )
                    expired += 1
                    logger.warning(
                        f"⌛ Post {post.id} missed {run_at.isoformat()} by "
                        f"{self._humanise(late_by)} - marked failed"
                    )
                    continue

                if self._add_post_job(post, run_at=run_at):
                    restored += 1

            if expired:
                db.commit()

            logger.info(f"✅ Restored {restored} job(s), failed {expired} overdue post(s)")

        except Exception as e:
            logger.exception(f"Error restoring scheduled jobs: {str(e)}")
        finally:
            if db is not None:
                db.close()

    def _post_timezone(self, post: Post):
        """The timezone `post.scheduled_time` was written in."""
        name = None
        try:
            if post.user is not None:
                name = post.user.timezone
        except Exception:
            name = None
        try:
            return pytz.timezone(name or self.settings.timezone)
        except Exception:
            return pytz.timezone(self.settings.timezone)

    @staticmethod
    def _as_aware(dt: datetime, tz) -> datetime:
        """Attach a timezone to a stored `scheduled_time`.

        The column is a naive `DateTime`, and the write path localises the
        user's picked time before storing it, so Postgres keeps the local wall
        clock and drops the offset. A naive value therefore means local time in
        the user's zone - NOT UTC. Handing it to APScheduler unlocalised lets
        the scheduler read it in the container's zone instead, which publishes
        every restored post off by the offset (5h30m for Asia/Kolkata).
        """
        if dt.tzinfo is None:
            return tz.localize(dt)
        return dt.astimezone(tz)

    @staticmethod
    def _humanise(delta: timedelta) -> str:
        """'2h 15m' - for error messages a person has to read."""
        seconds = int(abs(delta).total_seconds())
        hours, seconds = divmod(seconds, 3600)
        minutes = seconds // 60
        if hours and minutes:
            return f"{hours}h {minutes}m"
        if hours:
            return f"{hours}h"
        return f"{minutes}m" 

    def schedule_post(
        self,
        user: User,
        post_id: int,
        scheduled_time: datetime,
        optimal: bool = False
    ) -> Optional[str]:
        """
        Schedule a post for posting at specific time

        Args:
            user: User database model
            post_id: Post database ID
            scheduled_time: When to post (datetime with timezone)
            optimal: Whether this is at optimal posting time

        Returns:
            str: Job ID or None if failed
        """
        try:
            db = get_session()

            # Get post
            post = db.query(Post).filter(Post.id == post_id).first()
            if not post:
                logger.error(f"❌ Post {post_id} not found")
                return None

            logger.info(f"📅 Scheduling post {post_id} for {scheduled_time}")

            # Create job ID
            job_id = f"post_{post_id}_{int(scheduled_time.timestamp())}"

            # Add job to scheduler
            trigger = DateTrigger(run_date=scheduled_time)

            self.scheduler.add_job(
                func=self._post_job_callback,
                trigger=trigger,
                id=job_id,
                args=[user.id, post_id],
                name=f"Post {post_id}",
                replace_existing=False,
                misfire_grace_time=self.settings.scheduler_misfire_grace_seconds,
            )

            # Update post in database
            post.status = PostStatus.SCHEDULED
            post.scheduled_time = scheduled_time
            post.job_id = job_id
            db.commit()

            logger.info(f"✅ Post scheduled with job ID: {job_id}")

            return job_id

        except Exception as e:
            logger.error(f"❌ Failed to schedule post: {str(e)}")
            return None
        finally:
            db.close()

    def schedule_at_optimal_time(
        self,
        user: User,
        post_id: int,
        analytics_engine
    ) -> Optional[str]:
        """
        Schedule post at optimal engagement time

        Args:
            user: User database model
            post_id: Post database ID
            analytics_engine: AnalyticsEngine instance

        Returns:
            str: Job ID or None if failed
        """
        try:
            # Get optimal time
            optimal_time_info = analytics_engine.get_next_optimal_posting_time()

            if not optimal_time_info:
                logger.warning("⚠️  No optimal time available, scheduling for now + 1 hour")
                scheduled_time = datetime.now(pytz.timezone(user.timezone)) + timedelta(hours=1)
            else:
                scheduled_time = datetime.fromisoformat(optimal_time_info["optimal_time"])
                logger.info(f"🎯 Optimal posting time: {scheduled_time}")

            return self.schedule_post(user, post_id, scheduled_time, optimal=True)

        except Exception as e:
            logger.error(f"❌ Error scheduling at optimal time: {str(e)}")
            return None

    def _post_job_callback(self, user_id: int, post_id: int):
        """Publish a scheduled post when its trigger fires.

        Runs on an APScheduler worker thread with no request context, so every
        failure has to be recorded on the Post row - there is nobody to return
        an error to. The post must never be left in `scheduled` after this
        returns, or the UI will show it as pending forever.

        Platform work is delegated to a Publisher; this method knows nothing
        about LinkedIn or Instagram beyond the string on the post.
        """
        db = None
        try:
            logger.info(f"🔔 Post job triggered: user_id={user_id}, post_id={post_id}")

            db = get_session()

            user = db.query(User).filter(User.id == user_id).first()
            post = db.query(Post).filter(Post.id == post_id).first()

            if not user or not post:
                logger.error(
                    f"User or post not found: user_id={user_id}, post_id={post_id}"
                )
                return

            # Imported here to avoid a circular import at module load.
            from backend.core.publishers import UnknownPlatformError, get_publisher

            platform = post.platform or "linkedin"
            try:
                publisher = get_publisher(user, platform)
            except UnknownPlatformError as e:
                post.mark_as_failed(str(e))
                db.commit()
                return

            if not publisher.is_connected():
                status = publisher.connection_status()
                reason = status.get("reason") or (
                    f"{platform} is not connected. Authorize it from Settings."
                )
                logger.error(f"❌ Cannot publish post {post_id}: {reason}")
                post.mark_as_failed(reason)
                db.commit()
                return

            logger.info(f"📤 Publishing post {post_id} to {platform}: {post.video_path}")
            result = publisher.publish(
                video_path=Path(post.video_path),
                caption=post.caption or "",
                thumbnail_path=Path(post.thumbnail_path) if post.thumbnail_path else None,
            )

            if result.success:
                post.mark_as_posted(result.platform_post_id, platform=platform)
                post.video_url = result.url
                db.commit()
                logger.info(f"✅ Post {post_id} published: {result.url}")
            else:
                post.mark_as_failed(result.error or "Publishing failed")
                db.commit()
                logger.error(f"❌ Post {post_id} failed: {result.error}")

        except Exception as e:
            # Last resort. A publisher returning a result is the normal path;
            # reaching here means something genuinely unexpected broke.
            logger.exception(f"❌ Unhandled error in post job {post_id}")
            try:
                if db is None:
                    db = get_session()
                post = db.query(Post).filter(Post.id == post_id).first()
                if post:
                    post.mark_as_failed(f"Unexpected error: {e}")
                    db.commit()
            except Exception:
                logger.exception(f"Could not record failure for post {post_id}")
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass

    def _add_post_job(self, post: Post, run_at: Optional[datetime] = None) -> bool:
        """Arm one post. `run_at` must be timezone-aware - see `_as_aware`."""
        try:
            if not post.scheduled_time or not post.job_id:
                return False

            if run_at is None:
                run_at = self._as_aware(post.scheduled_time, self._post_timezone(post))

            trigger = DateTrigger(run_date=run_at)

            self.scheduler.add_job(
                func=self._post_job_callback,
                trigger=trigger,
                id=post.job_id,
                args=[post.user_id, post.id],
                name=f"Post {post.id}",
                replace_existing=True,
                misfire_grace_time=self.settings.scheduler_misfire_grace_seconds,
            )

            logger.info(f"✅ Restored job {post.job_id} for {run_at.isoformat()}")
            return True

        except Exception as e:
            logger.warning(f"⚠️  Could not restore job {post.job_id}: {str(e)}")
            return False

    def cancel_post(self, post_id: int) -> bool:
        """
        Cancel a scheduled post

        Args:
            post_id: Post database ID

        Returns:
            bool: True if cancelled successfully
        """
        try:
            db = get_session()

            post = db.query(Post).filter(Post.id == post_id).first()
            if not post:
                logger.error(f"Post {post_id} not found")
                return False

            if not post.job_id:
                logger.warning(f"Post {post_id} has no job ID")
                return False

            # Remove job from scheduler
            try:
                self.scheduler.remove_job(post.job_id)
                logger.info(f"✅ Removed job: {post.job_id}")
            except Exception as e:
                logger.warning(f"⚠️  Job not in scheduler: {str(e)}")

            # Update post status
            post.mark_as_cancelled()
            db.commit()

            logger.info(f"✅ Post {post_id} cancelled")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to cancel post: {str(e)}")
            return False
        finally:
            db.close()

    def get_scheduled_posts(self, user_id: Optional[int] = None) -> List[Dict]:
        """
        Get all scheduled posts

        Args:
            user_id: Filter by user ID (optional)

        Returns:
            list: List of scheduled posts
        """
        try:
            db = get_session()

            query = db.query(Post).filter(Post.status == PostStatus.SCHEDULED)

            if user_id:
                query = query.filter(Post.user_id == user_id)

            posts = query.all()

            result = []
            for post in posts:
                result.append({
                    "id": post.id,
                    "user_id": post.user_id,
                    "caption": post.caption[:100] if post.caption else None,
                    "scheduled_time": post.scheduled_time.isoformat() if post.scheduled_time else None,
                    "job_id": post.job_id,
                    "platform": post.platform,
                })

            return result

        except Exception as e:
            logger.error(f"Error getting scheduled posts: {str(e)}")
            return []
        finally:
            db.close()

    def get_pending_posts(self, user_id: Optional[int] = None) -> List[Dict]:
        """
        Get all pending/queued posts

        Args:
            user_id: Filter by user ID (optional)

        Returns:
            list: List of pending posts
        """
        try:
            db = get_session()

            query = db.query(Post).filter(
                Post.status.in_([PostStatus.QUEUED, PostStatus.DRAFT])
            )

            if user_id:
                query = query.filter(Post.user_id == user_id)

            posts = query.all()

            result = []
            for post in posts:
                result.append({
                    "id": post.id,
                    "user_id": post.user_id,
                    "status": post.status,
                    "caption": post.caption[:100] if post.caption else None,
                    "created_at": post.created_at.isoformat(),
                })

            return result

        except Exception as e:
            logger.error(f"Error getting pending posts: {str(e)}")
            return []
        finally:
            db.close()

    def get_jobs_count(self) -> Dict:
        """Get count of scheduled jobs"""
        return {
            "total_jobs": len(self.scheduler.get_jobs()),
            "running": self.scheduler.running,
            "initialized": self._initialized,
        }

    def shutdown(self):
        """Shutdown the scheduler"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown()
                logger.info("✅ Scheduler shutdown")
        except Exception as e:
            logger.error(f"Error during scheduler shutdown: {str(e)}")


# Global scheduler instance
_scheduler_instance = None


def get_scheduler() -> SmartScheduler:
    """Get or create the global scheduler instance"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SmartScheduler()
        _scheduler_instance.initialize()

    return _scheduler_instance


def shutdown_scheduler():
    """Shutdown the global scheduler"""
    global _scheduler_instance
    if _scheduler_instance:
        _scheduler_instance.shutdown()
        _scheduler_instance = None
