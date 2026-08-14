"""
Reel Manager - Handles reel uploads, validation, and file management
Manages video files from various sources
"""

import os
import shutil
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Optional, Dict, Tuple
from werkzeug.utils import secure_filename
from PIL import Image
import subprocess
from datetime import datetime
from backend.utils.timeutil import utcnow
from backend.utils.logger import get_logger
from backend.utils.config import get_settings

logger = get_logger("social_media_automation.reel_manager")


class ReelManager:
    """Manages reel uploads and validation"""

    def __init__(self):
        self.settings = get_settings()
        self.upload_folder = Path(self.settings.upload_folder)
        self.reels_folder = Path(self.settings.reels_folder)
        self.allowed_extensions = set(self.settings.allowed_video_extensions)
        self.max_upload_size = self.settings.max_upload_size

        # Cache of ffprobe duration lookups, keyed by (path, mtime, size).
        self._duration_cache: Dict[Tuple[str, int, int], Optional[float]] = {}

        # Background workers for ffmpeg thumbnailing. Small pool on purpose:
        # ffmpeg is CPU-bound and this only ever serves one local user.
        self._thumbnail_pool = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="thumbnail"
        )
        self._thumbnail_jobs: Dict[str, "Future[Optional[Path]]"] = {}
        self._thumbnail_lock = threading.Lock()

        # Resolve media tooling once, up front, so a missing binary is a loud
        # startup warning rather than a confusing per-upload failure.
        self.ffmpeg = shutil.which(self.settings.ffmpeg_path) or self.settings.ffmpeg_path
        self.ffprobe = shutil.which(self.settings.ffprobe_path) or self.settings.ffprobe_path
        self.ffprobe_available = shutil.which(self.settings.ffprobe_path) is not None
        self.ffmpeg_available = shutil.which(self.settings.ffmpeg_path) is not None

        if not self.ffprobe_available:
            logger.warning(
                f"⚠️  ffprobe not found (looked for '{self.settings.ffprobe_path}'). "
                "Video duration/codec validation will be SKIPPED. "
                "Set FFPROBE_PATH in .env to an absolute path."
            )
        if not self.ffmpeg_available:
            logger.warning(
                f"⚠️  ffmpeg not found (looked for '{self.settings.ffmpeg_path}'). "
                "Thumbnail generation will be skipped. "
                "Set FFMPEG_PATH in .env to an absolute path."
            )

        # Create directories if they don't exist
        self.upload_folder.mkdir(parents=True, exist_ok=True)
        self.reels_folder.mkdir(parents=True, exist_ok=True)

        logger.info(f"📁 Reel Manager initialized")
        logger.debug(f"Upload folder: {self.upload_folder}")
        logger.debug(f"Reels folder: {self.reels_folder}")

    def _is_allowed_file(self, filename: str) -> bool:
        """Check if file extension is allowed"""
        return "." in filename and filename.rsplit(".", 1)[1].lower() in self.allowed_extensions

    def _get_file_size(self, filepath: Path) -> int:
        """Get file size in bytes"""
        return filepath.stat().st_size

    def validate_video(self, filepath: Path) -> Tuple[bool, str]:
        """
        Validate video file

        Args:
            filepath: Path to video file

        Returns:
            tuple: (is_valid, error_message)
        """
        try:
            # Check file exists
            if not filepath.exists():
                return False, "File does not exist"

            # Check file size
            file_size = self._get_file_size(filepath)
            if file_size > self.max_upload_size:
                return False, f"File size ({file_size / 1024 / 1024:.1f}MB) exceeds maximum ({self.max_upload_size / 1024 / 1024:.0f}MB)"

            # Check file extension
            if not self._is_allowed_file(filepath.name):
                return False, f"File type not allowed. Allowed: {', '.join(self.allowed_extensions)}"

            # Duration check requires ffprobe. If ffprobe isn't installed we
            # accept the file (degraded mode) rather than rejecting everything;
            # the missing binary is already surfaced as a startup warning.
            if not self.ffprobe_available:
                logger.warning(
                    f"⚠️  Skipping duration validation for {filepath.name} — ffprobe unavailable"
                )
                return True, ""

            duration = self._get_video_duration(filepath)
            if duration is None:
                return False, "Could not read video file (unreadable or not a valid video)"

            # Instagram reel max duration is 90 seconds
            if duration > 90:
                return False, f"Video duration ({duration:.1f}s) exceeds 90 second limit"

            return True, ""

        except Exception as e:
            logger.error(f"❌ Video validation error: {str(e)}")
            return False, str(e)

    def _get_video_duration(self, filepath: Path) -> Optional[float]:
        """Get video duration in seconds using ffprobe.

        Results are cached per (path, mtime, size): a given file's duration
        cannot change, and spawning ffprobe is expensive (~5s on Windows).
        list_user_reels() calls this once per reel, so without the cache the
        reels endpoint degrades linearly and times out on a modest library.

        Returns None only when the duration genuinely can't be determined.
        Callers must distinguish that from "ffprobe is unavailable" via
        self.ffprobe_available.
        """
        try:
            stat = filepath.stat()
            cache_key = (str(filepath), stat.st_mtime_ns, stat.st_size)
        except OSError:
            cache_key = None

        if cache_key is not None and cache_key in self._duration_cache:
            return self._duration_cache[cache_key]

        duration = self._probe_video_duration(filepath)

        # Cache negatives too - re-probing a corrupt file on every list request
        # is just as expensive as re-probing a valid one.
        if cache_key is not None:
            self._duration_cache[cache_key] = duration

        return duration

    def _prime_duration_cache(self, filepath: Path, duration: Optional[float]) -> None:
        """Record a known duration for a file without invoking ffprobe.

        Used after a validated upload is moved into place: the duration was
        already probed against the staging path, and re-probing under the new
        path would cost another full ffprobe spawn.
        """
        try:
            stat = filepath.stat()
        except OSError:
            return
        self._duration_cache[(str(filepath), stat.st_mtime_ns, stat.st_size)] = duration

    def _probe_video_duration(self, filepath: Path) -> Optional[float]:
        """Run ffprobe against a file. See _get_video_duration for caching."""
        try:
            result = subprocess.run(
                [
                    self.ffprobe,
                    "-v", "error",
                    "-show_entries", "format=duration",
                    # NOTE: 'nokey_wrappers' is not a valid ffprobe option.
                    # It used to be passed here and made ffprobe exit 1 on
                    # every file, which rejected all uploads.
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(filepath)
                ],
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode != 0:
                logger.error(
                    f"ffprobe failed (exit {result.returncode}) for {filepath.name}: "
                    f"{result.stderr.strip()}"
                )
                return None

            raw = result.stdout.strip()
            if not raw or raw == "N/A":
                logger.error(f"ffprobe reported no duration for {filepath.name}")
                return None

            return float(raw)

        except FileNotFoundError:
            logger.error(f"❌ ffprobe not found at '{self.ffprobe}'")
            return None
        except subprocess.TimeoutExpired:
            logger.error(f"ffprobe timed out reading {filepath.name}")
            return None
        except Exception as e:
            logger.error(f"Error getting video duration: {str(e)}")
            return None

    def upload_reel(
        self,
        source_file: Path,
        user_id: int,
        keep_original: bool = False
    ) -> Tuple[bool, Optional[Path], str]:
        """
        Upload a reel from source location

        Args:
            source_file: Path to source video file
            user_id: User ID for organization
            keep_original: Whether to keep original file

        Returns:
            tuple: (success, destination_path, error_message)
        """
        try:
            logger.info(f"📤 Uploading reel: {source_file.name}")

            # Validate video
            is_valid, error_msg = self.validate_video(source_file)
            if not is_valid:
                logger.error(f"❌ Video validation failed: {error_msg}")
                return False, None, error_msg

            # Cheap cache hit - validate_video just probed this file.
            source_duration = (
                self._get_video_duration(source_file) if self.ffprobe_available else None
            )

            # Create user-specific folder
            user_folder = self.reels_folder / str(user_id)
            user_folder.mkdir(parents=True, exist_ok=True)

            # Generate secure filename
            timestamp = utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{secure_filename(source_file.name)}"
            destination_path = user_folder / filename

            # Copy or move file
            if keep_original:
                shutil.copy2(source_file, destination_path)
                logger.info(f"✅ Reel copied: {destination_path}")
            else:
                shutil.move(str(source_file), destination_path)
                logger.info(f"✅ Reel moved: {destination_path}")

            # The moved file is byte-identical to the one just validated, so
            # carry its duration across rather than paying for another probe.
            self._prime_duration_cache(destination_path, source_duration)

            # Kick thumbnail generation onto a worker thread so the HTTP
            # response isn't blocked on ffmpeg (docs/ARCHITECTURE.md, "Media
            # Upload - Design Notes" #4). Callers see has_thumbnail=False until
            # it lands; wait_for_thumbnail() exists for tests and sync callers.
            self._submit_thumbnail(destination_path)

            return True, destination_path, ""

        except Exception as e:
            logger.error(f"❌ Reel upload failed: {str(e)}")
            return False, None, str(e)

    def _submit_thumbnail(self, video_path: Path) -> None:
        """Queue thumbnail generation on the background worker pool."""
        try:
            future = self._thumbnail_pool.submit(self._generate_thumbnail, video_path)
            with self._thumbnail_lock:
                self._thumbnail_jobs[str(video_path)] = future
        except RuntimeError:
            # Pool already shut down (interpreter exiting) - fall back to inline
            # generation rather than silently producing no thumbnail.
            logger.warning("⚠️  Thumbnail pool unavailable, generating inline")
            self._generate_thumbnail(video_path)

    def wait_for_thumbnail(self, video_path: Path, timeout: float = 30.0) -> Optional[Path]:
        """Block until a queued thumbnail finishes. Returns its path, or None.

        Only for tests and callers that genuinely need the thumbnail before
        continuing - the HTTP upload path deliberately does not wait.
        """
        with self._thumbnail_lock:
            future = self._thumbnail_jobs.get(str(video_path))

        if future is None:
            # Nothing queued: either already done or never submitted.
            existing = video_path.with_suffix(".jpg")
            return existing if existing.exists() else None

        try:
            return future.result(timeout=timeout)
        except Exception as e:
            logger.error(f"Thumbnail generation failed for {video_path.name}: {str(e)}")
            return None

    def _generate_thumbnail(self, video_path: Path, timestamp: float = 0.0) -> Optional[Path]:
        """
        Generate thumbnail from video using ffmpeg

        Args:
            video_path: Path to video file
            timestamp: Timestamp in seconds to capture (default: start of video)

        Returns:
            Path to generated thumbnail or None
        """
        try:
            thumbnail_path = video_path.with_suffix(".jpg")

            if not self.ffmpeg_available:
                logger.warning("⚠️  ffmpeg unavailable, skipping thumbnail generation")
                return None

            result = subprocess.run(
                [
                    self.ffmpeg,
                    "-i", str(video_path),
                    "-ss", str(timestamp),
                    "-vframes", "1",
                    "-vf", "scale=1080:1350",  # Instagram reel aspect ratio
                    "-y",  # Overwrite if exists
                    str(thumbnail_path)
                ],
                capture_output=True,
                timeout=10
            )

            if result.returncode == 0 and thumbnail_path.exists():
                logger.debug(f"Thumbnail generated: {thumbnail_path}")
                return thumbnail_path
            else:
                logger.warning(f"ffmpeg failed: {result.stderr.decode()}")
                return None

        except FileNotFoundError:
            logger.warning("⚠️  ffmpeg not found, skipping thumbnail generation")
            return None
        except Exception as e:
            logger.error(f"Failed to generate thumbnail: {str(e)}")
            return None

    def delete_reel(self, filepath: Path, delete_thumbnail: bool = True) -> bool:
        """
        Delete a reel file

        Args:
            filepath: Path to reel file
            delete_thumbnail: Whether to also delete thumbnail

        Returns:
            bool: True if deletion successful
        """
        try:
            if filepath.exists():
                filepath.unlink()
                logger.info(f"✅ Reel deleted: {filepath}")

                if delete_thumbnail:
                    thumbnail_path = filepath.with_suffix(".jpg")
                    if thumbnail_path.exists():
                        thumbnail_path.unlink()
                        logger.info(f"✅ Thumbnail deleted: {thumbnail_path}")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to delete reel: {str(e)}")
            return False

    def get_reel_info(self, filepath: Path) -> Optional[Dict]:
        """
        Get information about a reel

        Args:
            filepath: Path to reel file

        Returns:
            dict: Reel information or None
        """
        try:
            if not filepath.exists():
                return None

            file_size = self._get_file_size(filepath)
            duration = self._get_video_duration(filepath)
            thumbnail_path = filepath.with_suffix(".jpg")

            return {
                "filename": filepath.name,
                "path": str(filepath),
                "size_bytes": file_size,
                "size_mb": file_size / 1024 / 1024,
                "duration_seconds": duration,
                "has_thumbnail": thumbnail_path.exists(),
                "thumbnail_path": str(thumbnail_path) if thumbnail_path.exists() else None,
                "created_at": datetime.fromtimestamp(filepath.stat().st_ctime).isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting reel info: {str(e)}")
            return None

    def cleanup_old_reels(self, user_id: int, keep_recent: int = 50) -> int:
        """
        Clean up old reels for a user, keeping only the most recent

        Args:
            user_id: User ID
            keep_recent: Number of recent reels to keep

        Returns:
            int: Number of reels deleted
        """
        try:
            user_folder = self.reels_folder / str(user_id)
            if not user_folder.exists():
                return 0

            # Get all video files
            video_files = sorted(
                user_folder.glob("*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            # Keep only recent files
            deleted_count = 0
            for video_file in video_files[keep_recent:]:
                if self.delete_reel(video_file):
                    deleted_count += 1

            if deleted_count > 0:
                logger.info(f"🧹 Cleaned up {deleted_count} old reels for user {user_id}")

            return deleted_count

        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            return 0

    def list_user_reels(self, user_id: int) -> list:
        """
        List all reels for a user

        Args:
            user_id: User ID

        Returns:
            list: List of reel info dictionaries
        """
        try:
            user_folder = self.reels_folder / str(user_id)
            if not user_folder.exists():
                return []

            reels = []
            for video_file in sorted(
                user_folder.glob("*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            ):
                if self._is_allowed_file(video_file.name):
                    info = self.get_reel_info(video_file)
                    if info:
                        reels.append(info)

            return reels

        except Exception as e:
            logger.error(f"Error listing reels: {str(e)}")
            return []


# Global reel manager instance
_reel_manager = None


def get_reel_manager() -> ReelManager:
    """Get or create the global reel manager instance"""
    global _reel_manager
    if _reel_manager is None:
        _reel_manager = ReelManager()
    return _reel_manager
