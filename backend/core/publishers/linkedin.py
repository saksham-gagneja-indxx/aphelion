"""LinkedIn publisher built on the official versioned REST API.

Flow (per Microsoft Learn, Videos API + Posts API):

  1. POST /rest/videos?action=initializeUpload  -> video URN + byte-range upload
     instructions + upload token
  2. PUT each byte range to its signed URL      -> collect the ETag per part
  3. POST /rest/videos?action=finalizeUpload    -> links the parts together
  4. GET  /rest/videos/{urn} until AVAILABLE    -> LinkedIn transcodes async
  5. POST /rest/posts                           -> the post; id is in x-restli-id

Notes that cost time if you get them wrong:

* Every call needs BOTH `LinkedIn-Version: YYYYMM` and
  `X-Restli-Protocol-Version: 2.0.0`. Omitting either yields opaque 400s.
* The part upload URLs are pre-signed and must NOT carry the Authorization
  header - they are plain PUTs to a CDN endpoint.
* Byte ranges come from the API. Do not assume a 4MB chunk size; a future
  version could partition differently and we would silently corrupt uploads.
* Part IDs sent to finalizeUpload are the ETag response headers with any
  surrounding quotes stripped.
* The created post's URN is returned in the `x-restli-id` response HEADER, not
  in the body.

Unlike Meta's Content Publishing API, LinkedIn accepts raw bytes - no publicly
reachable media URL and therefore no object storage is required.
"""

from pathlib import Path
from typing import List, Optional, Tuple

import requests
# Bound at import rather than reached through the module at raise-time. Aside
# from being a hair faster, it means `except` still works if `requests` is
# patched or partially initialised - otherwise the handler itself raises
# TypeError and the real failure is lost.
from requests import ConnectionError as RequestsConnectionError
from requests import RequestException, Timeout as RequestsTimeout

from backend.core.publishers.base import Publisher, PublishResult
from backend.utils.logger import get_logger

logger = get_logger("social_media_automation.publishers.linkedin")

API_ROOT = "https://api.linkedin.com/rest"

# Published limits for feed video. Source: Videos API "Video File Size
# Specifications". Checked locally so a bad file is rejected in milliseconds
# rather than after a multi-megabyte upload.
MIN_DURATION_SECONDS = 3
MAX_DURATION_SECONDS = 30 * 60
MIN_FILE_BYTES = 75 * 1024
MAX_FILE_BYTES = 500 * 1024 * 1024
ALLOWED_SUFFIXES = {".mp4"}

# Transcoding is asynchronous; publishing against a still-processing asset is
# rejected with MEDIA_ASSET_WAITING_UPLOAD.
PROCESSING_POLL_SECONDS = 3.0
PROCESSING_TIMEOUT_SECONDS = 300.0

# Transient conditions worth a retry. 429 included: the scheduler backs off
# rather than dropping the post.
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class LinkedInPublisher(Publisher):
    """Publishes a video to an authenticated member's LinkedIn feed.

    Requires the `w_member_social` scope, which is self-serve via the
    "Share on LinkedIn" product - no partner review.
    """

    platform = "linkedin"

    def __init__(
        self,
        access_token: Optional[str],
        person_urn: Optional[str],
        api_version: str,
        timeout: float = 60.0,
        sleep=None,
    ):
        """
        Args:
            access_token: OAuth 2.0 bearer token for the member.
            person_urn: Author URN, e.g. "urn:li:person:abc123".
            api_version: LinkedIn-Version header value in YYYYMM form.
            timeout: Per-request timeout in seconds.
            sleep: Injectable sleep, so tests don't wait on real polling.
        """
        self.access_token = access_token
        self.person_urn = person_urn
        self.api_version = api_version
        self.timeout = timeout
        if sleep is None:
            import time

            sleep = time.sleep
        self._sleep = sleep

    # ------------------------------------------------------------------ auth

    def is_connected(self) -> bool:
        return bool(self.access_token and self.person_urn)

    def _headers(self, extra: Optional[dict] = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": self.api_version,
        }
        if extra:
            headers.update(extra)
        return headers

    # ------------------------------------------------------------ validation

    def validate_media(self, video_path: Path) -> Tuple[bool, str]:
        if not video_path.exists():
            return False, "File does not exist"

        if video_path.suffix.lower() not in ALLOWED_SUFFIXES:
            return False, (
                f"LinkedIn video must be MP4 (got '{video_path.suffix}')"
            )

        size = video_path.stat().st_size
        if size < MIN_FILE_BYTES:
            return False, f"File is too small ({size} bytes); LinkedIn requires at least 75KB"
        if size > MAX_FILE_BYTES:
            return False, (
                f"File is {size / 1024 / 1024:.1f}MB; LinkedIn's limit is 500MB"
            )

        # Duration comes from ReelManager's ffprobe cache, so this stays cheap.
        # If ffprobe is unavailable the duration is unknown - accept the file
        # and let LinkedIn arbitrate rather than blocking on a missing binary.
        duration = self._probe_duration(video_path)
        if duration is not None:
            if duration < MIN_DURATION_SECONDS:
                return False, (
                    f"Video is {duration:.1f}s; LinkedIn requires at least 3 seconds"
                )
            if duration > MAX_DURATION_SECONDS:
                return False, (
                    f"Video is {duration / 60:.1f} minutes; LinkedIn's limit is 30 minutes"
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

    # --------------------------------------------------------------- publish

    def publish(
        self,
        video_path: Path,
        caption: str = "",
        thumbnail_path: Optional[Path] = None,
    ) -> PublishResult:
        if not self.is_connected():
            return PublishResult.failure(
                "LinkedIn is not connected. Authorize the app from Settings first."
            )

        is_valid, error = self.validate_media(video_path)
        if not is_valid:
            return PublishResult.failure(error)

        try:
            video_urn, instructions, upload_token = self._initialize_upload(video_path)
            part_ids = self._upload_parts(video_path, instructions)
            self._finalize_upload(video_urn, upload_token, part_ids)

            ready, status_error = self._await_processing(video_urn)
            if not ready:
                return PublishResult.failure(status_error)

            return self._create_post(video_urn, caption, video_path.stem)

        except RequestsTimeout:
            return PublishResult.failure(
                "LinkedIn request timed out", retryable=True
            )
        except RequestsConnectionError as e:
            return PublishResult.failure(
                f"Could not reach LinkedIn: {e}", retryable=True
            )
        except _LinkedInApiError as e:
            return PublishResult.failure(str(e), retryable=e.retryable)
        except RequestException as e:
            # Any other transport-level failure; treat as transient.
            return PublishResult.failure(f"LinkedIn request failed: {e}", retryable=True)
        except Exception as e:
            logger.exception("Unexpected LinkedIn publish failure")
            return PublishResult.failure(f"Unexpected error: {e}")

    # ----------------------------------------------------------- upload steps

    def _initialize_upload(self, video_path: Path) -> Tuple[str, List[dict], str]:
        size = video_path.stat().st_size
        response = requests.post(
            f"{API_ROOT}/videos?action=initializeUpload",
            headers=self._headers({"Content-Type": "application/json"}),
            json={
                "initializeUploadRequest": {
                    "owner": self.person_urn,
                    "fileSizeBytes": size,
                    "uploadCaptions": False,
                    "uploadThumbnail": False,
                }
            },
            timeout=self.timeout,
        )
        payload = _require_json(response, "initialize video upload")
        value = payload.get("value") or {}

        video_urn = value.get("video")
        instructions = value.get("uploadInstructions") or []
        if not video_urn or not instructions:
            raise _LinkedInApiError(
                "LinkedIn did not return upload instructions for this video"
            )

        logger.info(
            f"LinkedIn upload initialized: {video_urn} in {len(instructions)} part(s)"
        )
        # uploadToken is absent for single-part uploads; finalize wants "".
        return video_urn, instructions, value.get("uploadToken", "") or ""

    def _upload_parts(self, video_path: Path, instructions: List[dict]) -> List[str]:
        """PUT each byte range and return the ETag of every part, in order."""
        part_ids: List[str] = []

        with video_path.open("rb") as handle:
            for index, instruction in enumerate(instructions, start=1):
                first = int(instruction["firstByte"])
                last = int(instruction["lastByte"])
                handle.seek(first)
                chunk = handle.read(last - first + 1)

                # Pre-signed URL: sending our bearer token here is rejected.
                response = requests.put(
                    instruction["uploadUrl"],
                    data=chunk,
                    headers={"Content-Type": "application/octet-stream"},
                    timeout=self.timeout,
                )
                if response.status_code >= 400:
                    raise _LinkedInApiError(
                        f"Upload of part {index}/{len(instructions)} failed "
                        f"(HTTP {response.status_code})",
                        retryable=response.status_code in RETRYABLE_STATUS,
                    )

                etag = response.headers.get("etag") or response.headers.get("ETag")
                if not etag:
                    raise _LinkedInApiError(
                        f"LinkedIn did not return an ETag for part {index}; "
                        "cannot finalize the upload"
                    )
                part_ids.append(etag.strip('"'))
                logger.debug(f"Uploaded part {index}/{len(instructions)}")

        return part_ids

    def _finalize_upload(
        self, video_urn: str, upload_token: str, part_ids: List[str]
    ) -> None:
        response = requests.post(
            f"{API_ROOT}/videos?action=finalizeUpload",
            headers=self._headers({"Content-Type": "application/json"}),
            json={
                "finalizeUploadRequest": {
                    "video": video_urn,
                    "uploadToken": upload_token,
                    "uploadedPartIds": part_ids,
                }
            },
            timeout=self.timeout,
        )
        _require_ok(response, "finalize video upload")
        logger.info(f"LinkedIn upload finalized: {video_urn}")

    def _await_processing(self, video_urn: str) -> Tuple[bool, str]:
        """Poll until the asset is AVAILABLE. Returns (ready, error_message)."""
        from urllib.parse import quote

        waited = 0.0
        while waited < PROCESSING_TIMEOUT_SECONDS:
            response = requests.get(
                f"{API_ROOT}/videos/{quote(video_urn, safe='')}",
                headers=self._headers(),
                timeout=self.timeout,
            )
            payload = _require_json(response, "check video status")
            status = payload.get("status")

            if status == "AVAILABLE":
                return True, ""
            if status == "PROCESSING_FAILED":
                reason = payload.get("processingFailureReason") or "unknown reason"
                return False, f"LinkedIn could not process the video: {reason}"

            self._sleep(PROCESSING_POLL_SECONDS)
            waited += PROCESSING_POLL_SECONDS

        return False, (
            f"LinkedIn was still processing the video after "
            f"{PROCESSING_TIMEOUT_SECONDS / 60:.0f} minutes"
        )

    def _create_post(
        self, video_urn: str, caption: str, title: str
    ) -> PublishResult:
        response = requests.post(
            f"{API_ROOT}/posts",
            headers=self._headers({"Content-Type": "application/json"}),
            json={
                "author": self.person_urn,
                "commentary": caption or "",
                "visibility": "PUBLIC",
                "distribution": {
                    "feedDistribution": "MAIN_FEED",
                    "targetEntities": [],
                    "thirdPartyDistributionChannels": [],
                },
                "content": {"media": {"title": title[:200], "id": video_urn}},
                "lifecycleState": "PUBLISHED",
                "isReshareDisabledByAuthor": False,
            },
            timeout=self.timeout,
        )
        _require_ok(response, "create post")

        # Documented to arrive as a response header, not in the body.
        post_urn = response.headers.get("x-restli-id") or response.headers.get(
            "X-RestLi-Id"
        )
        if not post_urn:
            return PublishResult.failure(
                "LinkedIn accepted the post but returned no post id"
            )

        logger.info(f"✅ Published to LinkedIn: {post_urn}")
        return PublishResult.ok(
            platform_post_id=post_urn,
            url=f"https://www.linkedin.com/feed/update/{post_urn}/",
        )


class _LinkedInApiError(Exception):
    """A LinkedIn API call failed in a way we can describe to the user."""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def _require_ok(response: requests.Response, action: str) -> None:
    """Raise a descriptive error unless the response is a success."""
    if response.status_code < 400:
        return

    detail = ""
    try:
        body = response.json()
        detail = body.get("message") or body.get("code") or ""
    except ValueError:
        detail = (response.text or "").strip()[:200]

    raise _LinkedInApiError(
        f"LinkedIn rejected the request to {action} "
        f"(HTTP {response.status_code}){f': {detail}' if detail else ''}",
        retryable=response.status_code in RETRYABLE_STATUS,
    )


def _require_json(response: requests.Response, action: str) -> dict:
    _require_ok(response, action)
    try:
        return response.json()
    except ValueError:
        raise _LinkedInApiError(f"LinkedIn returned a non-JSON response to {action}")
