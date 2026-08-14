"""Manual smoke test for the media upload pipeline.

Not a pytest test - run directly:
    .venv/Scripts/python.exe tests/manual_upload_check.py

Exercises: ffprobe duration read, validation (valid / corrupt / over-length),
disk write, and ffmpeg thumbnail generation. Useful as a fast check that the
media tooling is still wired up correctly after environment changes.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.reel_manager import get_reel_manager  # noqa: E402


def make_video(ffmpeg: str, dest: Path, duration: int, size: str = "1080x1920") -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg, "-f", "lavfi", "-i",
            f"testsrc=size={size}:rate=30:duration={duration}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", str(dest),
        ],
        capture_output=True, check=True,
    )
    return dest


def main() -> int:
    rm = get_reel_manager()
    print(f"ffprobe_available={rm.ffprobe_available}  ffmpeg_available={rm.ffmpeg_available}")
    if not (rm.ffprobe_available and rm.ffmpeg_available):
        print("FAIL: media tooling not resolved")
        return 1

    tmp = Path(os.environ.get("TEMP", "/tmp")) / "reelcheck"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    failures = []

    # 1. valid short reel
    good = make_video(rm.ffmpeg, tmp / "good.mp4", duration=8)
    dur = rm._get_video_duration(good)
    print(f"[1] duration read: {dur}")
    if dur is None or not (7.5 < dur < 8.5):
        failures.append("duration read wrong")

    ok, err = rm.validate_video(good)
    print(f"[2] validate valid 8s: ok={ok} err={err!r}")
    if not ok:
        failures.append("valid video rejected")

    # 2. corrupt file
    bad = tmp / "bad.mp4"
    bad.write_bytes(b"not a video at all")
    ok, err = rm.validate_video(bad)
    print(f"[3] validate corrupt: ok={ok} err={err!r}")
    if ok:
        failures.append("corrupt video accepted")

    # 3. over-length reel (>90s)
    long_v = make_video(rm.ffmpeg, tmp / "long.mp4", duration=95, size="320x568")
    ok, err = rm.validate_video(long_v)
    print(f"[4] validate 95s: ok={ok} err={err!r}")
    if ok:
        failures.append("over-length video accepted")

    # 4. full upload + thumbnail
    staged = tmp / "staged.mp4"
    shutil.copy2(good, staged)
    ok, dest, err = rm.upload_reel(staged, user_id=1, keep_original=False)
    print(f"[5] upload: ok={ok} dest={dest} err={err!r}")
    if not ok or dest is None:
        failures.append("upload failed")
    else:
        # Thumbnailing is backgrounded so uploads return fast - the response
        # legitimately reports has_thumbnail=False for a moment.
        immediately_present = dest.with_suffix(".jpg").exists()
        print(f"[6] thumbnail present immediately after upload: {immediately_present} (async, may be False)")

        thumb = rm.wait_for_thumbnail(dest, timeout=30)
        exists = thumb is not None and thumb.exists()
        size = thumb.stat().st_size if exists else 0
        print(f"[7] thumbnail after wait: exists={exists} bytes={size}")
        if not exists or size == 0:
            failures.append("thumbnail not generated")
        rm.delete_reel(dest)

    print()
    if failures:
        print("FAILURES: " + "; ".join(failures))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
