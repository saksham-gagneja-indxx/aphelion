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
    """S3-backed store.

    The bucket is the source of truth, keyed by `<user_id>/<filename>`.
    `self.scratch` is only where in-flight uploads and ffmpeg/ffprobe
    downloads land — never treated as the real copy.
    """

    def __init__(self, bucket: str, scratch: Path):
        import boto3  # local import: only paid for when MEDIA_BACKEND=object

        self.bucket = bucket
        self.scratch = Path(scratch)
        self.scratch.mkdir(parents=True, exist_ok=True)
        self._s3 = boto3.client("s3")

    def _key(self, user_id: int, filename: str) -> Optional[str]:
        # Same containment check as LocalMediaStore, applied to the object key.
        if not filename or "/" in filename or "\\" in filename or filename in (".", ".."):
            return None
        if ".." in Path(filename).parts:
            return None
        return f"{user_id}/{filename}"

    def user_dir(self, user_id: int) -> Path:
        d = self.scratch / str(user_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def resolve(self, user_id: int, filename: str) -> Optional[Path]:
        key = self._key(user_id, filename)
        if key is None:
            logger.warning(f"Rejected out-of-folder media name: {filename!r}")
            return None
        # Not a real filesystem path — a stand-in that carries the object key
        # through the rest of the call chain (mirrored by scratch layout).
        return self.user_dir(user_id) / filename

    def exists(self, user_id: int, filename: str) -> bool:
        key = self._key(user_id, filename)
        if key is None:
            return False
        try:
            self._s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def list_files(self, user_id: int, suffixes: tuple[str, ...]) -> List[Path]:
        wanted = {s.lower().lstrip(".") for s in suffixes}
        prefix = f"{user_id}/"
        objects = []
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                name = key[len(prefix):]
                if "/" in name:
                    continue
                suffix = Path(name).suffix.lower().lstrip(".")
                if suffix in wanted:
                    objects.append((obj["LastModified"], name))
        objects.sort(key=lambda t: t[0], reverse=True)
        return [self.user_dir(user_id) / name for _, name in objects]

    def delete(self, path: Path) -> bool:
        user_id, filename = path.parent.name, path.name
        key = self._key(int(user_id), filename)
        if key is None:
            return False
        try:
            self._s3.delete_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as e:
            logger.error(f"Could not delete s3://{self.bucket}/{key}: {e}")
            return False

    def upload(self, user_id: int, filename: str, local_file: Path) -> None:
        """Push a scratch file up to the bucket. Called after writing to `user_dir`."""
        key = self._key(user_id, filename)
        if key is None:
            raise ValueError(f"Refusing to upload out-of-folder name: {filename!r}")
        self._s3.upload_file(str(local_file), self.bucket, key)

    @contextmanager
    def local_path(self, path: Path) -> Iterator[Path]:
        user_id, filename = path.parent.name, path.name
        key = self._key(int(user_id), filename)
        if key is None:
            raise ValueError(f"Refusing to resolve out-of-folder name: {filename!r}")
        dest = self.user_dir(int(user_id)) / filename
        if not dest.exists():
            self._s3.download_file(self.bucket, key, str(dest))
        try:
            yield dest
        finally:
            dest.unlink(missing_ok=True)


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
