"""Where reels live.

Reels already survive sign-out — nothing has ever deleted them on logout, and
they are keyed by the database user id, which is stable because it comes from
LinkedIn's `sub`. Signing out and back in lands on the same folder. There is a
test for that (`tests/test_storage.py`) so it stays true by accident no longer.

What this module adds is the **seam**. Today the files sit on local disk; on a
real host they belong in object storage. Routing every path decision through a
`MediaStore` means that migration is a new subclass and one setting, not a
rewrite of the upload, thumbnail, publish and delete paths.

The awkward constraint is ffmpeg and ffprobe: they take filesystem paths, not
byte streams. Rather than pretend otherwise, the interface is explicit about
it — `local_path()` is a context manager that yields a real path and, for a
remote backend, is where the download and cleanup would go. Every caller that
needs to hand a file to a subprocess goes through it, so a remote store has
exactly one place to implement rather than a dozen call sites to find.
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Optional

from backend.utils.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger("social_media_automation.storage")


class MediaStore(ABC):
    """The operations the app performs on a user's media.

    Deliberately small. Anything not on this list is either a local-disk
    implementation detail or belongs in ReelManager.
    """

    @abstractmethod
    def user_dir(self, user_id: int) -> Path:
        """Working directory for one user's reels, created if absent.

        For a remote store this is a local scratch directory — the place
        uploads land before they are shipped, not the source of truth.
        """

    @abstractmethod
    def resolve(self, user_id: int, filename: str) -> Optional[Path]:
        """Resolve `filename` inside the user's own space.

        Returns None when the name escapes that space. Path traversal is
        checked here, once, rather than at each of the four call sites that
        previously each rolled their own containment check.
        """

    @abstractmethod
    def exists(self, user_id: int, filename: str) -> bool:
        """Whether the named media is present."""

    @abstractmethod
    def list_files(self, user_id: int, suffixes: tuple[str, ...]) -> List[Path]:
        """Every file for a user whose suffix is in `suffixes`, newest first."""

    @abstractmethod
    def delete(self, path: Path) -> bool:
        """Remove one file. True if it went away (or was already gone)."""

    @contextmanager
    def local_path(self, path: Path) -> Iterator[Path]:
        """Yield a real filesystem path for `path`.

        The escape hatch for ffmpeg, ffprobe and the LinkedIn uploader, none of
        which take a stream. Local storage yields the path unchanged; a remote
        store downloads to a temporary file here and deletes it on exit.
        """
        yield path


class LocalMediaStore(MediaStore):
    """Files under `REELS_FOLDER/<user_id>/`.

    The only backend implemented today, and the correct one while the API runs
    on a developer machine.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def user_dir(self, user_id: int) -> Path:
        d = self.root / str(user_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def resolve(self, user_id: int, filename: str) -> Optional[Path]:
        if not filename:
            return None
        base = self.user_dir(user_id).resolve()
        try:
            candidate = (base / filename).resolve()
        except (OSError, ValueError):
            return None
        # `..`, an absolute path, or a symlink pointing outside all land here.
        if not candidate.is_relative_to(base):
            logger.warning(f"Rejected out-of-folder media name: {filename!r}")
            return None
        return candidate

    def exists(self, user_id: int, filename: str) -> bool:
        resolved = self.resolve(user_id, filename)
        return resolved is not None and resolved.is_file()

    def list_files(self, user_id: int, suffixes: tuple[str, ...]) -> List[Path]:
        d = self.root / str(user_id)
        if not d.is_dir():
            return []
        wanted = {s.lower().lstrip(".") for s in suffixes}
        files = [
            p for p in d.iterdir()
            if p.is_file() and p.suffix.lower().lstrip(".") in wanted
        ]
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files

    def delete(self, path: Path) -> bool:
        try:
            Path(path).unlink(missing_ok=True)
            return True
        except OSError as e:
            logger.error(f"Could not delete {path}: {e}")
            return False


class ObjectMediaStore(MediaStore):
    """Placeholder for S3 / R2 / GCS.

    Left unimplemented on purpose rather than half-written against an SDK
    nobody has chosen yet. What a real implementation owes each method is
    written on it, so the work is filling in bodies rather than rediscovering
    the shape.

    Switching over is: implement these five, add the SDK to requirements, and
    set `MEDIA_BACKEND=object`. Nothing above this class changes — `local_path`
    is the only place the difference leaks, and it is already a seam.
    """

    def __init__(self, bucket: str, scratch: Path):
        self.bucket = bucket
        self.scratch = Path(scratch)
        self.scratch.mkdir(parents=True, exist_ok=True)

    def _unimplemented(self, what: str):
        raise NotImplementedError(
            f"ObjectMediaStore.{what} is not implemented. Set MEDIA_BACKEND=local, "
            "or implement this class against your object store."
        )

    def user_dir(self, user_id: int) -> Path:
        # Scratch space for in-flight uploads; the bucket is the real home.
        d = self.scratch / str(user_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def resolve(self, user_id: int, filename: str) -> Optional[Path]:
        # Should map to an object key `<user_id>/<filename>` after the same
        # containment check LocalMediaStore performs.
        self._unimplemented("resolve")

    def exists(self, user_id: int, filename: str) -> bool:
        # HEAD the object.
        self._unimplemented("exists")

    def list_files(self, user_id: int, suffixes: tuple[str, ...]) -> List[Path]:
        # List the `<user_id>/` prefix, filter by suffix, sort by LastModified.
        self._unimplemented("list_files")

    def delete(self, path: Path) -> bool:
        self._unimplemented("delete")

    @contextmanager
    def local_path(self, path: Path) -> Iterator[Path]:
        # Download to self.scratch, yield it, remove it in a finally block.
        self._unimplemented("local_path")
        yield path  # pragma: no cover - unreachable, keeps the type honest


_store: Optional[MediaStore] = None


def get_media_store() -> MediaStore:
    """The configured store.

    Rebuilt when the configured root changes rather than cached forever. A
    plain singleton pinned whichever REELS_FOLDER happened to be set when the
    first request came in, which is invisible in production (the value never
    moves) and quietly wrong under test, where each case points at its own
    tmp_path. Constructing one is a `mkdir -p`, so re-checking is cheaper than
    the class of bug it prevents.
    """
    global _store
    settings = get_settings()
    backend = (getattr(settings, "media_backend", "local") or "local").lower()
    root = Path(settings.reels_folder)

    if isinstance(_store, LocalMediaStore) and backend == "local" and _store.root == root:
        return _store
    if isinstance(_store, ObjectMediaStore) and backend == "object":
        return _store

    if backend == "object":
        _store = ObjectMediaStore(
            bucket=getattr(settings, "media_bucket", "") or "",
            scratch=root / "_scratch",
        )
        logger.info(f"📦 Media store: object storage ({_store.bucket})")
    else:
        _store = LocalMediaStore(root)
        logger.info(f"📁 Media store: local disk ({root})")
    return _store


def reset_media_store() -> None:
    """Drop the cached store. For tests that repoint REELS_FOLDER."""
    global _store
    _store = None


def disk_usage_bytes(root: Path) -> int:
    """Total size of everything under `root`. For the storage readout."""
    total = 0
    try:
        for p in Path(root).rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    continue
    except OSError:
        pass
    return total


def free_space_bytes(root: Path) -> Optional[int]:
    """Free space on the volume holding `root`, or None if unavailable."""
    try:
        return shutil.disk_usage(Path(root)).free
    except OSError:
        return None
