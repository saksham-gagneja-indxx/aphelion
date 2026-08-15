"""Deleting reels and posts.

The interesting cases are the refusals, not the happy path: deleting a reel a
scheduled post still points at produces a failure at publish time, long after
the mistake and with no obvious cause, and the filename arrives from the client
so it can try to walk out of the user's own folder.
"""

import os
import tempfile
from pathlib import Path

import pytest

API_KEY = "test-key-deletion"


@pytest.fixture
def app(monkeypatch, tmp_path):
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    monkeypatch.setenv("API_ACCESS_KEY", API_KEY)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("REELS_FOLDER", str(tmp_path / "reels"))
    monkeypatch.setenv("UPLOAD_FOLDER", str(tmp_path / "uploads"))

    import backend.utils.database as database

    database._db_instance = None

    # The ReelManager singleton is reset by an autouse fixture in conftest —
    # an earlier attempt here named the attribute wrongly and did nothing.
    from backend.app import create_app

    application = create_app()
    application.config["TESTING"] = True
    yield application

    database._db_instance = None
    for suffix in ("", "-wal", "-shm"):
        try:
            os.unlink(db_path + suffix)
        except OSError:
            pass


@pytest.fixture
def users(app):
    from backend.models.user import User
    from backend.utils.database import get_session

    db = get_session()
    try:
        made = []
        for i, (sub, name) in enumerate([("sub-owner", "Owner"), ("sub-other", "Other")]):
            u = User(
                linkedin_sub=sub, full_name=name, email=f"{sub}@test",
                role="operator", is_active=True,
            )
            db.add(u)
            made.append(u)
        db.commit()
        for u in made:
            db.refresh(u)
            db.expunge(u)
        return made
    finally:
        db.close()


def _auth(user):
    from backend.utils.security import make_session_token

    return {"Authorization": f"Bearer {make_session_token(user.id)}"}


def _make_reel(user_id, name="clip.mp4") -> Path:
    from backend.core.reel_manager import get_reel_manager

    folder = get_reel_manager().reels_folder / str(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(b"not really a video")
    path.with_suffix(".jpg").write_bytes(b"thumb")
    return path


def test_deleting_a_reel_removes_the_file_and_its_thumbnail(app, users):
    owner = users[0]
    path = _make_reel(owner.id)

    with app.test_client() as client:
        res = client.delete(
            f"/api/users/{owner.id}/reels/{path.name}", headers=_auth(owner)
        )

    assert res.status_code == 200
    assert not path.exists()
    assert not path.with_suffix(".jpg").exists()


def test_another_user_cannot_delete_your_reel(app, users):
    owner, other = users
    path = _make_reel(owner.id)

    with app.test_client() as client:
        res = client.delete(
            f"/api/users/{owner.id}/reels/{path.name}", headers=_auth(other)
        )

    assert res.status_code == 403
    assert path.exists(), "the file must survive a refused request"


def test_a_reel_used_by_a_scheduled_post_is_not_deleted(app, users):
    """Otherwise the post fails at publish time with nothing to point at."""
    from backend.models.post import Post, PostStatus
    from backend.utils.database import get_session

    owner = users[0]
    path = _make_reel(owner.id)

    db = get_session()
    try:
        db.add(Post(
            user_id=owner.id, video_path=str(path), caption="later",
            status=PostStatus.SCHEDULED,
        ))
        db.commit()
    finally:
        db.close()

    with app.test_client() as client:
        res = client.delete(
            f"/api/users/{owner.id}/reels/{path.name}", headers=_auth(owner)
        )

    assert res.status_code == 409
    assert "scheduled post" in res.get_json()["error"]
    assert path.exists()


def test_an_already_published_post_does_not_block_deletion(app, users):
    """A posted reel has served its purpose; the file is just taking up space."""
    from backend.models.post import Post, PostStatus
    from backend.utils.database import get_session

    owner = users[0]
    path = _make_reel(owner.id)

    db = get_session()
    try:
        db.add(Post(
            user_id=owner.id, video_path=str(path), caption="done",
            status=PostStatus.POSTED,
        ))
        db.commit()
    finally:
        db.close()

    with app.test_client() as client:
        res = client.delete(
            f"/api/users/{owner.id}/reels/{path.name}", headers=_auth(owner)
        )

    assert res.status_code == 200
    assert not path.exists()


@pytest.mark.parametrize(
    "attack",
    [
        "../../../etc/passwd",
        "..%2f..%2fsecrets.env",
        "subdir/../../escape.mp4",
    ],
)
def test_a_crafted_filename_cannot_escape_the_users_folder(app, users, attack):
    owner = users[0]

    with app.test_client() as client:
        res = client.delete(
            f"/api/users/{owner.id}/reels/{attack}", headers=_auth(owner)
        )

    # Rejected outright, or simply not found - never a 200, and never a 500.
    assert res.status_code in (400, 404), res.status_code


def test_deleting_a_post_removes_the_row(app, users):
    from backend.models.post import Post, PostStatus
    from backend.utils.database import get_session

    owner = users[0]
    db = get_session()
    try:
        post = Post(
            user_id=owner.id, video_path="/tmp/x.mp4", caption="bye",
            status=PostStatus.DRAFT,
        )
        db.add(post)
        db.commit()
        post_id = post.id
    finally:
        db.close()

    with app.test_client() as client:
        res = client.delete(f"/api/posts/{post_id}/delete", headers=_auth(owner))

    assert res.status_code == 200

    db = get_session()
    try:
        assert db.query(Post).filter(Post.id == post_id).first() is None
    finally:
        db.close()


def test_another_user_cannot_delete_your_post(app, users):
    from backend.models.post import Post, PostStatus
    from backend.utils.database import get_session

    owner, other = users
    db = get_session()
    try:
        post = Post(
            user_id=owner.id, video_path="/tmp/x.mp4", caption="mine",
            status=PostStatus.DRAFT,
        )
        db.add(post)
        db.commit()
        post_id = post.id
    finally:
        db.close()

    with app.test_client() as client:
        res = client.delete(f"/api/posts/{post_id}/delete", headers=_auth(other))

    assert res.status_code == 403

    db = get_session()
    try:
        assert db.query(Post).filter(Post.id == post_id).first() is not None
    finally:
        db.close()
