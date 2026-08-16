"""Where reels live, and which frame represents them.

Two features that are easy to believe are working without checking:

* **Persistence.** Reels are supposed to survive a sign-out. Nothing has ever
  deleted them on logout, which is the sort of property that holds right up
  until someone adds a cleanup call. Asserting it costs one test.
* **Thumbnail choice.** The old code took frame zero. A reel that fades in from
  black got a black thumbnail — a real frame from the video, useless as a
  preview, and the first thing anyone sees in the Queue. The sampler is only
  worth having if it actually prefers the informative frame, so that is what
  is tested rather than "a file appeared".

The scorer is tested on synthesised images rather than real video: it takes a
PIL image, so there is no reason to make these tests depend on ffmpeg being
installed on the runner.
"""

import os
import tempfile
from pathlib import Path

import pytest
from PIL import Image


# --------------------------------------------------------------------- store


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("REELS_FOLDER", str(tmp_path / "reels"))
    from backend.core.storage import get_media_store, reset_media_store

    reset_media_store()
    yield get_media_store()
    reset_media_store()


def test_reels_survive_a_sign_out(store, tmp_path):
    """Signing out must not touch the files.

    Reels are keyed by the database user id, which comes from LinkedIn's `sub`
    and is stable across sessions, so the same account lands back on the same
    folder.
    """
    reel = store.user_dir(7) / "clip.mp4"
    reel.write_bytes(b"video")

    # A sign-out clears the session token client-side and nothing more. There
    # is deliberately no server-side media teardown to call here — this test
    # exists so that stays deliberate.
    from backend.core.storage import get_media_store, reset_media_store

    reset_media_store()
    after = get_media_store()

    assert after.exists(7, "clip.mp4"), "a sign-out must not remove media"
    assert after.resolve(7, "clip.mp4").read_bytes() == b"video"


def test_resolve_refuses_to_leave_the_users_folder(store):
    store.user_dir(1)
    for attempt in ("../../etc/passwd", "../2/theirs.mp4", "/etc/passwd"):
        assert store.resolve(1, attempt) is None, attempt


def test_resolve_accepts_an_ordinary_name(store):
    (store.user_dir(1) / "a.mp4").write_bytes(b"x")
    resolved = store.resolve(1, "a.mp4")
    assert resolved is not None and resolved.is_file()


def test_one_users_media_is_invisible_to_another(store):
    (store.user_dir(1) / "mine.mp4").write_bytes(b"x")
    assert store.exists(1, "mine.mp4")
    assert not store.exists(2, "mine.mp4")


def test_list_files_is_newest_first_and_filtered(store):
    import time

    d = store.user_dir(3)
    (d / "old.mp4").write_bytes(b"x")
    time.sleep(0.01)
    (d / "new.mp4").write_bytes(b"x")
    (d / "thumb.jpg").write_bytes(b"x")

    names = [p.name for p in store.list_files(3, ("mp4",))]
    assert names == ["new.mp4", "old.mp4"], "jpg must be filtered out, newest first"


def test_the_store_follows_a_reconfigured_root(tmp_path, monkeypatch):
    """A cached store pinned to a stale folder is a 404 with no explanation."""
    from backend.core.storage import get_media_store, reset_media_store

    reset_media_store()
    monkeypatch.setenv("REELS_FOLDER", str(tmp_path / "first"))
    assert get_media_store().root == tmp_path / "first"

    monkeypatch.setenv("REELS_FOLDER", str(tmp_path / "second"))
    assert get_media_store().root == tmp_path / "second"
    reset_media_store()


def test_object_backend_fails_loudly_rather_than_silently_losing_media(
    tmp_path, monkeypatch
):
    """The stub must raise, not pretend to work.

    A half-implemented store that quietly returns None would look like an empty
    library rather than a missing implementation.
    """
    from backend.core.storage import ObjectMediaStore

    s = ObjectMediaStore(bucket="b", scratch=tmp_path)
    with pytest.raises(NotImplementedError) as e:
        s.exists(1, "a.mp4")
    assert "MEDIA_BACKEND=local" in str(e.value)


# ----------------------------------------------------------------- thumbnails


@pytest.fixture
def manager(tmp_path, monkeypatch):
    monkeypatch.setenv("REELS_FOLDER", str(tmp_path / "reels"))
    monkeypatch.setenv("UPLOAD_FOLDER", str(tmp_path / "uploads"))
    import backend.core.reel_manager as rm

    rm._reel_manager = None
    yield rm.get_reel_manager()
    rm._reel_manager = None


def solid(colour):
    return Image.new("RGB", (240, 300), colour)


def detailed():
    """A frame with content: bands plus noise, like a real shot."""
    img = Image.new("RGB", (240, 300))
    px = img.load()
    for y in range(300):
        for x in range(240):
            v = (x * 7 + y * 13) % 256
            px[x, y] = (v, (v * 3) % 256, (v * 5) % 256)
    return img


def test_a_black_frame_scores_worse_than_a_detailed_one(manager):
    """The exact case the sampler exists for: a fade-in from black."""
    from backend.core.reel_manager import ReelManager

    assert ReelManager.score_frame(detailed()) > ReelManager.score_frame(solid((0, 0, 0)))


def test_a_blown_out_white_frame_also_scores_badly(manager):
    from backend.core.reel_manager import ReelManager

    assert ReelManager.score_frame(detailed()) > ReelManager.score_frame(
        solid((255, 255, 255))
    )


def test_a_flat_mid_grey_card_loses_to_real_content(manager):
    """Brightness alone is not enough — a grey card is perfectly exposed."""
    from backend.core.reel_manager import ReelManager

    assert ReelManager.score_frame(detailed()) > ReelManager.score_frame(
        solid((128, 128, 128))
    )


def test_candidates_are_spread_and_avoid_both_edges(manager):
    ts = manager.candidate_timestamps(100.0)

    assert len(ts) == manager.THUMBNAIL_CANDIDATES
    assert ts == sorted(ts), "candidates must be in order"
    assert ts[0] >= 10.0, "the opening fade is skipped"
    assert ts[-1] <= 90.0, "the closing card is skipped"


def test_an_unknown_duration_degrades_to_a_single_frame(manager):
    """No ffprobe means no duration; guessing offsets would just fail to seek."""
    assert manager.candidate_timestamps(None) == [0.0]
    assert manager.candidate_timestamps(0) == [0.0]


def test_a_very_short_clip_still_yields_one_candidate(manager):
    ts = manager.candidate_timestamps(0.4)
    assert len(ts) >= 1
    assert all(0 <= t <= 0.4 for t in ts)


def test_the_best_scoring_candidate_is_the_one_kept(manager, tmp_path, monkeypatch):
    """End to end through _generate_thumbnail with ffmpeg stubbed out.

    Frame extraction is faked so this runs without ffmpeg: each requested
    timestamp writes a known image, and only the 3-second mark gets content.
    """
    video = tmp_path / "reel.mp4"
    video.write_bytes(b"x")

    monkeypatch.setattr(manager, "ffmpeg_available", True)
    monkeypatch.setattr(manager, "_get_video_duration", lambda p: 10.0)

    written = []

    def fake_extract(video_path, timestamp, out):
        written.append(timestamp)
        img = detailed() if abs(timestamp - 3.0) < 1.5 else solid((0, 0, 0))
        img.save(out, "JPEG")
        return True

    monkeypatch.setattr(manager, "_extract_frame", fake_extract)

    result = manager._generate_thumbnail(video)

    assert result == video.with_suffix(".jpg")
    assert result.exists()
    # The final call re-extracts the winner, and it must be the lit frame.
    assert abs(written[-1] - 3.0) < 1.5, f"kept {written[-1]}s, expected ~3s"
    assert not video.with_suffix(".cand.jpg").exists(), "scratch frame left behind"


def test_an_explicit_timestamp_skips_scoring_entirely(manager, tmp_path, monkeypatch):
    """The manual override: the user picked a frame, do not second-guess it."""
    video = tmp_path / "reel.mp4"
    video.write_bytes(b"x")

    monkeypatch.setattr(manager, "ffmpeg_available", True)
    calls = []

    def fake_extract(video_path, timestamp, out):
        calls.append(timestamp)
        solid((0, 0, 0)).save(out, "JPEG")
        return True

    monkeypatch.setattr(manager, "_extract_frame", fake_extract)

    manager.regenerate_thumbnail(video, timestamp=7.25)

    assert calls == [7.25], "an explicit timestamp must not trigger sampling"


def test_a_video_no_frame_can_be_read_from_falls_back_to_frame_zero(
    manager, tmp_path, monkeypatch
):
    """A broken sampler must never cost a thumbnail the old code would have got."""
    video = tmp_path / "reel.mp4"
    video.write_bytes(b"x")

    monkeypatch.setattr(manager, "ffmpeg_available", True)
    monkeypatch.setattr(manager, "_get_video_duration", lambda p: 10.0)

    attempts = []

    def flaky_extract(video_path, timestamp, out):
        attempts.append(timestamp)
        # Every sampled candidate fails; only the frame-zero fallback works.
        if timestamp == 0.0:
            solid((90, 90, 90)).save(out, "JPEG")
            return True
        return False

    monkeypatch.setattr(manager, "_extract_frame", flaky_extract)

    result = manager._generate_thumbnail(video)

    assert result is not None and result.exists()
    assert attempts[-1] == 0.0, "must fall back to frame zero"
