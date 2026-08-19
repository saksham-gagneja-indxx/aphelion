"""An account created via Clerk (or anything else that isn't the plain
LinkedIn sign-in path) has no linkedin_sub until it connects LinkedIn. The
reconnect flow used to store a fresh token without ever recording the
member's `sub` claim - fixed in _resolve_user, and repaired here for any
account that reconnected before that fix via
POST /api/admin/users/<id>/backfill-linkedin-sub.
"""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

API_KEY = "test-key-sub-backfill"


@pytest.fixture
def app(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    monkeypatch.setenv("API_ACCESS_KEY", API_KEY)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")

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


@pytest.fixture
def client(app):
    return app.test_client()


class _Response:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def _make_user(db, **kwargs):
    from backend.models.user import User

    user = User(is_active=True, role="admin", **kwargs)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_backfill_requires_admin(client):
    res = client.post("/api/admin/users/1/backfill-linkedin-sub")
    assert res.status_code == 401


def test_backfill_is_a_noop_when_sub_already_set(app):
    from backend.utils.database import get_session

    db = get_session()
    try:
        user = _make_user(db, clerk_id="clerk-1", linkedin_sub="already-set")
        user_id = user.id
    finally:
        db.close()

    with app.test_client() as client:
        res = client.post(
            f"/api/admin/users/{user_id}/backfill-linkedin-sub",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
    assert res.status_code == 200
    body = res.get_json()
    assert body["changed"] is False
    assert body["linkedin_sub"] == "already-set"


def test_backfill_refuses_without_a_stored_access_token(app):
    from backend.utils.database import get_session

    db = get_session()
    try:
        user = _make_user(db, clerk_id="clerk-2")
        user_id = user.id
    finally:
        db.close()

    with app.test_client() as client:
        res = client.post(
            f"/api/admin/users/{user_id}/backfill-linkedin-sub",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
    assert res.status_code == 409


def test_backfill_fetches_the_sub_from_linkedin_and_stores_it(app):
    from backend.utils.database import get_session

    db = get_session()
    try:
        user = _make_user(db, clerk_id="clerk-3")
        user.linkedin_access_token = "stored-access-token"
        db.commit()
        user_id = user.id
    finally:
        db.close()

    with patch(
        "backend.api.admin_routes.requests.get",
        return_value=_Response({"sub": "fetched-sub-123"}),
    ):
        with app.test_client() as client:
            res = client.post(
                f"/api/admin/users/{user_id}/backfill-linkedin-sub",
                headers={"Authorization": f"Bearer {API_KEY}"},
            )
    assert res.status_code == 200
    body = res.get_json()
    assert body["changed"] is True
    assert body["linkedin_sub"] == "fetched-sub-123"

    db = get_session()
    try:
        from backend.models.user import User

        reloaded = db.query(User).filter(User.id == user_id).first()
        assert reloaded.linkedin_sub == "fetched-sub-123"
    finally:
        db.close()


def test_backfill_refuses_to_steal_a_sub_mapped_to_someone_else(app):
    from backend.utils.database import get_session

    db = get_session()
    try:
        owner = _make_user(db, clerk_id="clerk-owner", linkedin_sub="taken-sub")
        other = _make_user(db, clerk_id="clerk-other")
        other.linkedin_access_token = "stored-access-token"
        db.commit()
        other_id = other.id
    finally:
        db.close()

    with patch(
        "backend.api.admin_routes.requests.get",
        return_value=_Response({"sub": "taken-sub"}),
    ):
        with app.test_client() as client:
            res = client.post(
                f"/api/admin/users/{other_id}/backfill-linkedin-sub",
                headers={"Authorization": f"Bearer {API_KEY}"},
            )
    assert res.status_code == 409


def test_backfill_surfaces_a_dead_token_rather_than_guessing(app):
    from backend.utils.database import get_session

    db = get_session()
    try:
        user = _make_user(db, clerk_id="clerk-4")
        user.linkedin_access_token = "revoked-token"
        db.commit()
        user_id = user.id
    finally:
        db.close()

    with patch(
        "backend.api.admin_routes.requests.get",
        return_value=_Response({"error": "invalid_token"}, status=401),
    ):
        with app.test_client() as client:
            res = client.post(
                f"/api/admin/users/{user_id}/backfill-linkedin-sub",
                headers={"Authorization": f"Bearer {API_KEY}"},
            )
    assert res.status_code == 502


# ------------------------------------------------- reconnect self-heal path


def test_reconnecting_backfills_a_missing_linkedin_sub(app):
    """The actual fix in _resolve_user: a normal reconnect for an account
    that has no linkedin_sub yet now records one, instead of leaving the
    account stuck forever on whatever identity path created it."""
    from backend.api.auth_routes import _resolve_user
    from backend.utils.database import get_session

    db = get_session()
    try:
        user = _make_user(db, clerk_id="clerk-5")
        user_id = user.id

        resolved, created = _resolve_user(db, user_id, "new-sub-456", {"name": "Someone"})
        assert created is False
        assert resolved.id == user_id
        assert resolved.linkedin_sub == "new-sub-456"
    finally:
        db.close()


def test_reconnecting_does_not_overwrite_an_existing_linkedin_sub(app):
    from backend.api.auth_routes import _resolve_user
    from backend.utils.database import get_session

    db = get_session()
    try:
        user = _make_user(db, linkedin_sub="original-sub")
        user_id = user.id

        resolved, _ = _resolve_user(db, user_id, "different-sub", {"name": "Someone"})
        assert resolved.linkedin_sub == "original-sub"
    finally:
        db.close()


def test_reconnecting_does_not_steal_a_sub_mapped_to_a_different_account(app):
    from backend.api.auth_routes import _resolve_user
    from backend.models.user import User
    from backend.utils.database import get_session

    db = get_session()
    try:
        owner = _make_user(db, linkedin_sub="shared-sub")
        reconnecting = _make_user(db, clerk_id="clerk-6")
        reconnecting_id = reconnecting.id

        resolved, _ = _resolve_user(db, reconnecting_id, "shared-sub", {"name": "Someone"})
        assert resolved.linkedin_sub is None

        untouched = db.query(User).filter(User.id == owner.id).first()
        assert untouched.linkedin_sub == "shared-sub"
    finally:
        db.close()
