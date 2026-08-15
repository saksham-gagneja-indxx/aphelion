"""Platform-agnostic publishing interface.

Everything above this layer - the scheduler, the API routes, the UI - talks to
`Publisher` and never to a platform SDK directly. That seam is what lets the
LinkedIn implementation ship today while Instagram waits on Meta App Review:
swapping platforms is a registry lookup, not a rewrite.

Design rules for implementations:

* Never raise for an expected failure. Return `PublishResult.failure(...)` so
  the scheduler can record a useful error on the post instead of a traceback.
* Set `retryable=True` only for genuinely transient conditions (5xx, timeouts,
  rate limits). A rejected video or a revoked token is not retryable, and
  retrying it just burns quota.
* `validate_media` must be cheap and must not perform network calls. It runs
  before upload so the user gets a fast, specific rejection rather than a
  failure five minutes into a transfer.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


@dataclass(frozen=True)
class PublishResult:
    """Outcome of a publish attempt.

    `platform_post_id` and `url` are only meaningful when `success` is True.
    """

    success: bool
    platform_post_id: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None
    retryable: bool = False

    @classmethod
    def ok(cls, platform_post_id: str, url: Optional[str] = None) -> "PublishResult":
        return cls(success=True, platform_post_id=platform_post_id, url=url)

    @classmethod
    def failure(cls, error: str, retryable: bool = False) -> "PublishResult":
        return cls(success=False, error=error, retryable=retryable)


class Publisher(ABC):
    """A destination that a reel can be published to."""

    #: Stable identifier stored on Post.platform. Must match PostPlatform values.
    platform: str = ""

    @abstractmethod
    def is_connected(self) -> bool:
        """True when this publisher holds usable credentials.

        Must not perform a network call - the scheduler checks this on every
        job fire, and the UI polls it.
        """

    @abstractmethod
    def validate_media(self, video_path: Path) -> Tuple[bool, str]:
        """Check a file against this platform's published limits.

        Returns (is_valid, error_message). Local checks only - no network.
        """

    @abstractmethod
    def publish(
        self,
        video_path: Path,
        caption: str = "",
        thumbnail_path: Optional[Path] = None,
    ) -> PublishResult:
        """Publish a video. Returns a result rather than raising on failure."""

    def delete(self, platform_post_id: str) -> Tuple[bool, str]:
        """Remove a published post from the platform.

        Returns (success, error_message). Needed for genuine retraction, and
        for verifying the publish path end-to-end without leaving test content
        on someone's public profile.

        Default: not supported. Implementations override where the platform
        allows it - reporting honestly is better than silently doing nothing
        and letting a caller believe the post is gone.
        """
        return False, f"{self.platform} does not support deleting posts via API"

    def connection_status(self) -> dict:
        """Describe connection state for /api/status and the Settings page."""
        return {"platform": self.platform, "connected": self.is_connected()}
