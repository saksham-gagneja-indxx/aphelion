"""The operations console.

Two things matter here. It must be closed to everyone but an administrator -
it reports deployment internals and can delete files. And the orphan sweep must
never remove a file a post still refers to, because that is silent data loss
that only surfaces when a scheduled post fires days later.
"""

import os
import tempfile
from pathlib import Path

import pytest

API_KEY = "test-key-console"


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


def _make_user(role="admin", is_guest=False, sub=None):
    from backend.models.user import User
    from backend.utils.database import get_session

    db = get_session()
    try:
        user = User(
            linkedin_sub=sub or f"sub-{role}-{is_guest}",
            full_name=f"{role} user",
            email=f"{role}@test",
            role=role,
            is_active=True,
            is_guest=is_guest,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


def _auth(user):
    from backend.utils.security import make_session_token

    return {"Authorization": f"Bearer {make_session_token(user.id)}"}


def test_overview_is_refused_to_operators(app):
    operator = _make_user(role="operator")
    with app.test_client() as client:
        assert client.get("/api/console/overview", headers=_auth(operator)).status_code == 403


def test_overview_is_refused_to_guests(app):
    guest = _make_user(role="operator", is_guest=True)
    with app.test_client() as client:
        assert client.get("/api/console/overview", headers=_auth(guest)).status_code == 403


def test_overview_reports_the_running_system(app):
    admin = _make_user(role="admin")
    with app.test_client() as client:
        res = client.get("/api/console/overview", headers=_auth(admin))

    assert res.status_code == 200
    body = res.get_json()
    assert set(body) == {"runtime", "database", "scheduler", "storage", "features"}
    assert body["database"]["users"]["total"] >= 1
    assert "enabled" in body["scheduler"]


def test_overview_never_returns_the_database_url(app):
    """It carries the password; the backend name is the useful part."""
    admin = _make_user(role="admin")
    with app.test_client() as client:
        res = client.get("/api/console/overview", headers=_auth(admin))

    text = res.get_data(as_text=True)
    assert "sqlite:///" not in text
    assert res.get_json()["database"]["backend"] == "sqlite"


def test_purging_guests_removes_them_and_their_posts(app):
    from backend.models.post import Post, PostStatus
    from backend.models.user import User
    from backend.utils.database import get_session

    admin = _make_user(role="admin")
    guest = _make_user(role="operator", is_guest=True, sub="sub-guest-1")

    db = get_session()
    try:
        db.add(Post(user_id=guest.id, video_path="/tmp/g.mp4", caption="x",
                    status=PostStatus.DRAFT))
        db.commit()
    finally:
        db.close()

    with app.test_client() as client:
        res = client.delete("/api/console/guests", headers=_auth(admin))

    assert res.status_code == 200
    assert res.get_json()["deleted_accounts"] == 1
    assert res.get_json()["deleted_posts"] == 1

    db = get_session()
    try:
        assert db.query(User).filter(User.is_guest.is_(True)).count() == 0
        # The admin must survive a guest purge.
        assert db.query(User).filter(User.id == admin.id).first() is not None
    finally:
        db.close()


def _write_reel(user_id, name):
    from backend.core.reel_manager import get_reel_manager

    folder = get_reel_manager().reels_folder / str(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(b"video bytes")
    path.with_suffix(".jpg").write_bytes(b"thumb")
    return path


def test_a_referenced_reel_is_never_reported_as_an_orphan(app):
    """The assertion that keeps this from being a data-loss button."""
    from backend.models.post import Post, PostStatus
    from backend.utils.database import get_session

    admin = _make_user(role="admin")
    used = _write_reel(admin.id, "used.mp4")
    _write_reel(admin.id, "unused.mp4")

    db = get_session()
    try:
        db.add(Post(user_id=admin.id, video_path=str(used), caption="keep",
                    status=PostStatus.SCHEDULED))
        db.commit()
    finally:
        db.close()

    with app.test_client() as client:
        res = client.get("/api/console/storage/orphans", headers=_auth(admin))

    # Compared as exact filenames: "used.mp4" is a substring of "unused.mp4",
    # so a containment check here passes for the wrong reason.
    names = {Path(o["path"]).name for o in res.get_json()["orphans"]}
    assert "used.mp4" not in names
    assert "unused.mp4" in names


def test_deleting_orphans_leaves_referenced_files_alone(app):
    from backend.models.post import Post, PostStatus
    from backend.utils.database import get_session

    admin = _make_user(role="admin")
    used = _write_reel(admin.id, "used.mp4")
    unused = _write_reel(admin.id, "unused.mp4")

    db = get_session()
    try:
        db.add(Post(user_id=admin.id, video_path=str(used), caption="keep",
                    status=PostStatus.SCHEDULED))
        db.commit()
    finally:
        db.close()

    with app.test_client() as client:
        res = client.delete("/api/console/storage/orphans", headers=_auth(admin))

    assert res.status_code == 200
    assert res.get_json()["deleted"] == 1
    assert used.exists(), "a referenced reel must survive"
    assert not unused.exists()
    # The orphan's thumbnail goes with it; the kept one's stays.
    assert not unused.with_suffix(".jpg").exists()
    assert used.with_suffix(".jpg").exists()


def test_orphan_sweep_is_refused_to_operators(app):
    operator = _make_user(role="operator")
    with app.test_client() as client:
        assert client.delete(
            "/api/console/storage/orphans", headers=_auth(operator)
        ).status_code == 403


def test_console_actions_are_audited(app):
    from backend.models.audit import AuditLog
    from backend.utils.database import get_session

    admin = _make_user(role="admin")
    with app.test_client() as client:
        client.delete("/api/console/guests", headers=_auth(admin))

    db = get_session()
    try:
        assert (
            db.query(AuditLog).filter(AuditLog.action == "console.guests_purged").count()
            == 1
        )
    finally:
        db.close()
