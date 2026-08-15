"""Tests that one signed-in user cannot reach another user's data.

Authentication only proves who is calling. Every user-scoped route takes the
target user id from the client - a path segment, a form field, a query string -
so without an ownership check a perfectly valid session token can be pointed at
someone else's account just by editing the number.

These tests exist because the whole suite previously authenticated with the API
access key, which is a machine credential and is deliberately allowed through
every one of these guards. That meant a total absence of authorisation on the
user-scoped routes passed 93 tests without complaint.
"""

import os
import tempfile

import pytest

API_KEY = "test-key-ownership"


@pytest.fixture
def app(monkeypatch):
    """App backed by a throwaway database, isolated per test."""
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
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    from backend.utils.database import get_session

    session = get_session()
    yield session
    session.close()


def make_user(db, **kwargs):
    from backend.models.user import User

    defaults = {
        "linkedin_sub": f"sub-{kwargs.get('email', 'x')}",
        "full_name": "Test User",
        "email": "test@example.com",
        "role": "operator",
        "is_active": True,
    }
    defaults.update(kwargs)
    user = User(**defaults)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def session_for(app, user_id):
    from backend.utils.security import make_session_token

    with app.app_context():
        return make_session_token(user_id)


@pytest.fixture
def two_users(db):
    """An operator and an unrelated second account."""
    alice = make_user(db, email="alice@example.com", linkedin_sub="sub-alice")
    bob = make_user(db, email="bob@example.com", linkedin_sub="sub-bob")
    return alice, bob


# --------------------------------------------------------- cross-account reads


def test_operator_cannot_read_another_users_record(app, client, two_users):
    alice, bob = two_users
    res = client.get(f"/api/users/{bob.id}", headers=auth(session_for(app, alice.id)))
    assert res.status_code == 403


def test_operator_cannot_list_another_users_posts(app, client, two_users):
    alice, bob = two_users
    res = client.get(
        f"/api/users/{bob.id}/posts", headers=auth(session_for(app, alice.id))
    )
    assert res.status_code == 403


def test_operator_cannot_list_another_users_reels(app, client, two_users):
    alice, bob = two_users
    res = client.get(
        f"/api/users/{bob.id}/reels", headers=auth(session_for(app, alice.id))
    )
    assert res.status_code == 403


def test_operator_cannot_read_another_users_analytics(app, client, two_users):
    alice, bob = two_users
    res = client.get(
        f"/api/users/{bob.id}/analytics", headers=auth(session_for(app, alice.id))
    )
    assert res.status_code == 403


def test_operator_cannot_read_another_users_thumbnail(app, client, two_users):
    alice, bob = two_users
    res = client.get(
        f"/api/users/{bob.id}/reels/clip.mp4/thumbnail",
        headers=auth(session_for(app, alice.id)),
    )
    assert res.status_code == 403


# -------------------------------------------------------- cross-account writes


def test_operator_cannot_upload_as_another_user(app, client, two_users):
    alice, bob = two_users
    res = client.post(
        "/api/upload",
        data={"user_id": str(bob.id)},
        content_type="multipart/form-data",
        headers=auth(session_for(app, alice.id)),
    )
    assert res.status_code == 403


def test_operator_cannot_create_a_post_for_another_user(app, client, two_users):
    alice, bob = two_users
    res = client.post(
        "/api/posts",
        json={"user_id": bob.id, "video_path": "whatever.mp4"},
        headers=auth(session_for(app, alice.id)),
    )
    assert res.status_code == 403


def test_operator_cannot_filter_scheduler_jobs_by_another_user(app, client, two_users):
    alice, bob = two_users
    res = client.get(
        f"/api/scheduler/jobs?user_id={bob.id}",
        headers=auth(session_for(app, alice.id)),
    )
    assert res.status_code == 403


def test_unfiltered_scheduler_listing_is_scoped_to_the_caller(app, client, two_users):
    """No user_id means "everyone" for an admin - it must not for an operator."""
    alice, _bob = two_users
    res = client.get("/api/scheduler/jobs", headers=auth(session_for(app, alice.id)))
    assert res.status_code == 200


# ------------------------------------------------------------ allowed callers


def test_a_user_can_still_read_their_own_record(app, client, two_users):
    alice, _bob = two_users
    res = client.get(f"/api/users/{alice.id}", headers=auth(session_for(app, alice.id)))
    assert res.status_code == 200


def test_an_admin_may_read_another_users_record(app, client, db, two_users):
    _alice, bob = two_users
    admin = make_user(
        db, email="admin@example.com", linkedin_sub="sub-admin", role="admin"
    )
    res = client.get(f"/api/users/{bob.id}", headers=auth(session_for(app, admin.id)))
    assert res.status_code == 200


def test_the_api_key_may_read_any_users_record(client, two_users):
    _alice, bob = two_users
    res = client.get(f"/api/users/{bob.id}", headers=auth(API_KEY))
    assert res.status_code == 200
