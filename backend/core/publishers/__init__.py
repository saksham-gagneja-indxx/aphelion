"""Publisher registry.

`get_publisher(user, platform)` is the only way the rest of the app obtains a
publisher. Callers pass a platform string (matching PostPlatform) and receive
something that satisfies the `Publisher` interface - they never import a
platform module directly.
"""

from typing import Optional

from backend.core.publishers.base import Publisher, PublishResult
from backend.core.publishers.instagram import InstagramPublisher
from backend.core.publishers.linkedin import LinkedInPublisher
from backend.models.user import User
from backend.utils.config import get_settings

__all__ = [
    "Publisher",
    "PublishResult",
    "InstagramPublisher",
    "LinkedInPublisher",
    "get_publisher",
    "SUPPORTED_PLATFORMS",
]

SUPPORTED_PLATFORMS = ("linkedin", "instagram")


class UnknownPlatformError(ValueError):
    """Raised when a post names a platform we have no publisher for."""


def get_publisher(user: Optional[User], platform: str) -> Publisher:
    """Build a publisher for `platform`, wired to `user`'s stored credentials.

    A new instance is returned each call rather than being cached: tokens are
    refreshed on the User row, and a cached publisher would keep serving a
    stale access token after a reconnect.
    """
    key = (platform or "").strip().lower()

    if key == "linkedin":
        settings = get_settings()
        return LinkedInPublisher(
            access_token=getattr(user, "linkedin_access_token", None),
            person_urn=getattr(user, "linkedin_person_urn", None),
            api_version=settings.linkedin_api_version,
        )

    if key == "instagram":
        return InstagramPublisher()

    raise UnknownPlatformError(
        f"No publisher for platform '{platform}'. "
        f"Supported: {', '.join(SUPPORTED_PLATFORMS)}"
    )
