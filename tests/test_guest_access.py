"""Guest accounts, and the limits that make them safe to offer publicly.

A guest is an ordinary account with an ordinary session - not a bypass - so the
interesting assertions are all about what it CANNOT reach. If any of these
stop holding, the guest button becomes a way for an anonymous visitor to
publish to somebody's LinkedIn or read the admin panel.
"""

import os
import tempfile

import pytest

API_KEY = "test-key-guest"


@pytest.fixture
def app(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    monkeypatch.setenv("API_ACCESS_KEY", API_KEY)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("ALLOW_GUEST_ACCESS", "true")

    import backend.utils.database as database

    database._db_instance = None

    from backend.app import create_app

    application = create_app()
    application.config["TESTING"] = True
    yield application

    database._db_instance = None
    for suffix in ("", "-wal", "-shm"):
        try:
            os.unlink(path + suffix)
        except OSError:
            pass


def _new_guest(app):
    with app.test_client() as client:
        res = client.post("/api/auth/guest")
    assert res.status_code == 201, res.get_data(as_text=True)
    body = res.get_json()
    return body["token"], body["user"]["id"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_a_guest_can_sign_in_and_use_the_app(app):
    token, user_id = _new_guest(app)

    with app.test_client() as client:
        res = client.get("/api/me", headers=_auth(token))

    assert res.status_code == 200
    assert res.get_json()["id"] == user_id


def test_each_guest_gets_its_own_account(app):
    """Sharing one row would show two visitors each other's uploads."""
    _, first = _new_guest(app)
    _, second = _new_guest(app)

    assert first != second


def test_a_guest_cannot_publish(app):
    """The limit that makes this safe to offer to anyone at all."""
    from backend.models.post import Post, PostStatus
    from backend.utils.database import get_session

    token, user_id = _new_guest(app)

    db = get_session()
    try:
        post = Post(
            user_id=user_id, video_path="/tmp/x.mp4", caption="nope",
            status=PostStatus.DRAFT,
        )
        db.add(post)
        db.commit()
        post_id = post.id
    finally:
        db.close()

    with app.test_client() as client:
        res = client.post(f"/api/posts/{post_id}/publish", headers=_auth(token))

    assert res.status_code == 403
    assert "guest" in res.get_json()["error"].lower()


def test_a_guest_cannot_retract_a_published_post(app):
    """The publish blueprint is guarded as a whole, not route by route."""
    from backend.models.post import Post, PostStatus
    from backend.utils.database import get_session

    token, user_id = _new_guest(app)

    db = get_session()
    try:
        post = Post(
            user_id=user_id, video_path="/tmp/x.mp4", caption="x",
            status=PostStatus.POSTED,
        )
        db.add(post)
        db.commit()
        post_id = post.id
    finally:
        db.close()

    with app.test_client() as client:
        res = client.delete(f"/api/posts/{post_id}/published", headers=_auth(token))

    assert res.status_code == 403


def test_a_guest_cannot_reach_the_admin_panel(app):
    token, _ = _new_guest(app)

    with app.test_client() as client:
        for path in ("/api/admin/users", "/api/admin/stats", "/api/admin/audit"):
            assert client.get(path, headers=_auth(token)).status_code == 403


def test_a_guest_promoted_to_admin_is_still_not_an_admin(app):
    """Belt and braces: the limit lives on the row, not on the role.

    A guest could end up with role='admin' through a bad migration, a seeded
    fixture, or a future admin screen. None of those should hand out the admin
    panel.
    """
    from backend.models.user import User
    from backend.utils.database import get_session

    token, user_id = _new_guest(app)

    db = get_session()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        user.role = User.ROLE_ADMIN
        db.commit()
        assert user.is_admin() is False
    finally:
        db.close()

    with app.test_client() as client:
        assert client.get("/api/admin/users", headers=_auth(token)).status_code == 403


def test_a_guest_cannot_read_another_accounts_data(app):
    """Ownership applies to guests exactly as to anyone else."""
    token_a, _ = _new_guest(app)
    _, id_b = _new_guest(app)

    with app.test_client() as client:
        res = client.get(f"/api/users/{id_b}/posts", headers=_auth(token_a))

    assert res.status_code == 403


def test_guest_access_can_be_switched_off(app, monkeypatch):
    monkeypatch.setenv("ALLOW_GUEST_ACCESS", "false")

    with app.test_client() as client:
        res = client.post("/api/auth/guest")
        assert res.status_code == 403

        status = client.get("/api/auth/guest/status")
        assert status.get_json()["enabled"] is False


def test_the_status_endpoint_says_whether_to_offer_the_option(app):
    with app.test_client() as client:
        res = client.get("/api/auth/guest/status")

    assert res.status_code == 200
    assert res.get_json()["enabled"] is True


def test_creating_a_guest_is_recorded_in_the_audit_log(app):
    from backend.models.audit import AuditLog
    from backend.utils.database import get_session

    _, user_id = _new_guest(app)

    db = get_session()
    try:
        event = (
            db.query(AuditLog)
            .filter(AuditLog.action == "user.guest_created")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert event is not None
        assert str(user_id) in event.target
    finally:
        db.close()
