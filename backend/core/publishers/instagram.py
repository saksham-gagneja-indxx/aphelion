"""Instagram publisher - scaffolded, deliberately not enabled.

Meta's Content Publishing API is the only compliant way to publish to an
Instagram account we do not own. It is not wired up yet because it is blocked
on things that cannot be completed in a sprint:

  * App Review for `instagram_business_basic` + `instagram_business_content_publish`
    (2-4 weeks, separate submission per permission)
  * An Instagram **Business** account - Creator accounts cannot publish via API
  * Publicly reachable HTTPS media URLs: Meta *pulls* the file from a URL we
    host, so `data/reels/` on local disk is not sufficient. This needs object
    storage and is a real architecture change, tracked separately.

The previous `instagrapi` path is intentionally NOT reachable from here.
It logs in with a username and password, which violates Instagram's Terms of
Service and risks suspension of the account being posted to. That is an
unacceptable risk for client accounts, so this publisher fails loudly and
explains why rather than silently falling back to it.

`validate_media` is fully implemented against Instagram's published Reels
limits, so the upload pipeline can already reject unsuitable files today.
"""

from pathlib import Path
from typing import Optional, Tuple

from backend.core.publishers.base import Publisher, PublishResult
from backend.utils.logger import get_logger

logger = get_logger("social_media_automation.publishers.instagram")

# Instagram Reels limits, enforced locally so the Upload page can reject files
# before anything is scheduled.
MIN_DURATION_SECONDS = 3
MAX_DURATION_SECONDS = 90
MAX_FILE_BYTES = 500 * 1024 * 1024
ALLOWED_SUFFIXES = {".mp4", ".mov"}

_NOT_ENABLED_MESSAGE = (
    "Instagram publishing is not enabled yet. It requires Meta App Review "
    "(instagram_business_content_publish), an Instagram Business account, and "
    "media hosted at a public HTTPS URL. Use LinkedIn until that is approved."
)


class InstagramPublisher(Publisher):
    """Placeholder that reports honestly instead of failing at post time."""

    platform = "instagram"

    def is_connected(self) -> bool:
        # Never claim a connection we cannot honour. The Settings page and the
        # scheduler both key off this, and reporting True here would let posts
        # be scheduled that are guaranteed to fail hours later.
        return False

    def validate_media(self, video_path: Path) -> Tuple[bool, str]:
        if not video_path.exists():
            return False, "File does not exist"

        if video_path.suffix.lower() not in ALLOWED_SUFFIXES:
            return False, (
                f"Instagram reels must be MP4 or MOV (got '{video_path.suffix}')"
            )

        size = video_path.stat().st_size
        if size > MAX_FILE_BYTES:
            return False, (
                f"File is {size / 1024 / 1024:.1f}MB; Instagram's limit is 500MB"
            )

        duration = self._probe_duration(video_path)
        if duration is not None:
            if duration < MIN_DURATION_SECONDS:
                return False, (
                    f"Video is {duration:.1f}s; Instagram reels must be at least 3 seconds"
                )
            if duration > MAX_DURATION_SECONDS:
                return False, (
                    f"Video is {duration:.1f}s; Instagram reels are capped at 90 seconds"
                )

        return True, ""

    def _probe_duration(self, video_path: Path) -> Optional[float]:
        try:
            from backend.core.reel_manager import get_reel_manager

            info = get_reel_manager().get_reel_info(video_path)
            return info.get("duration_seconds") if info else None
        except Exception as e:  # pragma: no cover - diagnostics only
            logger.debug(f"Could not determine duration for {video_path.name}: {e}")
            return None

    def publish(
        self,
        video_path: Path,
        caption: str = "",
        thumbnail_path: Optional[Path] = None,
    ) -> PublishResult:
        logger.warning("Instagram publish attempted while the platform is disabled")
        # Not retryable: retrying cannot change the outcome until App Review
        # completes, and a retry loop would just fill the log with noise.
        return PublishResult.failure(_NOT_ENABLED_MESSAGE, retryable=False)

    def connection_status(self) -> dict:
        return {
            "platform": self.platform,
            "connected": False,
            "reason": _NOT_ENABLED_MESSAGE,
        }
