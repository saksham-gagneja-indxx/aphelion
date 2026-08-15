"""Tests for sign-in, roles, and admin access control.

The properties under test are the ones that would be genuinely dangerous to get
wrong once a second person uses this tool: that a deactivated account really is
locked out, that a non-admin cannot reach admin endpoints, and that the system
cannot be locked into having no administrator.
"""

import os
import tempfile

import pytest

API_KEY = "test-key-identity"


@pytest.fixture
def app(monkeypatch):
    """App backed by a throwaway database, isolated per test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    monkeypatch.setenv("API_ACCESS_KEY", API_KEY)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")

    # The database handle is a module-level singleton; reset it so this test
    # gets its own engine rather than reusing one from an earlier test.
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


# ------------------------------------------------------------ session tokens


def test_session_token_roundtrip(app):
    from backend.utils.security import make_session_token, verify_session_token

    with app.app_context():
        assert verify_session_token(make_session_token(7)) == 7


def test_oauth_state_is_not_accepted_as_a_session_token(app):
    """Both are signed with the same key; the type claim keeps them distinct."""
    from backend.utils.security import make_oauth_state, verify_session_token

    with app.app_context():
        assert verify_session_token(make_oauth_state(1)) is None


def test_expired_session_token_is_rejected(app):
    from backend.utils.security import make_session_token, verify_session_token

    with app.app_context():
        assert verify_session_token(make_session_token(1, days=-1)) is None


def test_forged_session_token_is_rejected(app):
    from backend.utils.security import make_session_token, verify_session_token

    with app.app_context():
        token = make_session_token(1)
        body, _ = token.rsplit(".", 1)
        assert verify_session_token(f"{body}.forged") is None


# ------------------------------------------------------------------ /api/me


def test_me_requires_authentication(client):
    assert client.get("/api/me").status_code == 401


def test_me_returns_identity_without_tokens(app, client, db):
    user = make_user(db, email="me@example.com", full_name="Me")
    response = client.get("/api/me", headers=auth(session_for(app, user.id)))

    assert response.status_code == 200
    body = response.get_json()
    assert body["email"] == "me@example.com"
    assert body["role"] == "operator"
    # Credentials must never appear in an identity payload.
    assert "linkedin_access_token" not in body
    assert "linkedin_refresh_token" not in body


def test_machine_token_has_no_user_identity(client):
    """The API key authenticates a caller but is not a person."""
    assert client.get("/api/me", headers=auth(API_KEY)).status_code == 401


# --------------------------------------------------------- account lifecycle


def test_inactive_user_is_locked_out_immediately(app, client, db):
    """A signed token cannot be revoked, so is_active is what stops access."""
    user = make_user(db, email="pending@example.com", is_active=False)
    token = session_for(app, user.id)

    response = client.get("/api/me", headers=auth(token))

    assert response.status_code == 403
    assert "not active" in response.get_json()["error"].lower()


def test_deactivation_invalidates_an_already_issued_token(app, client, db):
    user = make_user(db, email="live@example.com", is_active=True)
    token = session_for(app, user.id)
    assert client.get("/api/me", headers=auth(token)).status_code == 200

    user.is_active = False
    db.commit()

    assert client.get("/api/me", headers=auth(token)).status_code == 403


def test_token_for_deleted_user_is_rejected(app, client, db):
    user = make_user(db, email="gone@example.com")
    token = session_for(app, user.id)
    db.delete(user)
    db.commit()

    assert client.get("/api/me", headers=auth(token)).status_code == 401


# ------------------------------------------------------------ admin access


def test_operator_cannot_reach_admin_endpoints(app, client, db):
    user = make_user(db, email="op@example.com", role="operator")
    token = session_for(app, user.id)

    for path in ("/api/admin/users", "/api/admin/audit", "/api/admin/stats"):
        assert client.get(path, headers=auth(token)).status_code == 403, path


def test_admin_can_list_users(app, client, db):
    admin = make_user(db, email="admin@example.com", role="admin")
    make_user(db, email="other@example.com", linkedin_sub="sub-other")

    response = client.get("/api/admin/users", headers=auth(session_for(app, admin.id)))

    assert response.status_code == 200
    assert response.get_json()["total"] == 2


def test_admin_endpoints_reject_anonymous_callers(client):
    assert client.get("/api/admin/users").status_code == 401


def test_machine_key_is_treated_as_admin(client):
    """The API key is already full-privilege; refusing it here protects nothing."""
    assert client.get("/api/admin/users", headers=auth(API_KEY)).status_code == 200


# --------------------------------------------------- lockout protection


def test_last_admin_cannot_be_demoted(app, client, db):
    admin = make_user(db, email="solo@example.com", role="admin")

    response = client.post(
        f"/api/admin/users/{admin.id}/role",
        json={"role": "operator"},
        headers=auth(session_for(app, admin.id)),
    )

    assert response.status_code == 409
    assert "last administrator" in response.get_json()["error"].lower()


def test_admin_can_be_demoted_when_another_exists(app, client, db):
    first = make_user(db, email="a@example.com", role="admin", linkedin_sub="sub-a")
    second = make_user(db, email="b@example.com", role="admin", linkedin_sub="sub-b")

    response = client.post(
        f"/api/admin/users/{second.id}/role",
        json={"role": "operator"},
        headers=auth(session_for(app, first.id)),
    )

    assert response.status_code == 200
    assert response.get_json()["role"] == "operator"


def test_admin_cannot_deactivate_themselves(app, client, db):
    admin = make_user(db, email="self@example.com", role="admin")

    response = client.post(
        f"/api/admin/users/{admin.id}/active",
        json={"is_active": False},
        headers=auth(session_for(app, admin.id)),
    )

    assert response.status_code == 409


def test_invalid_role_is_rejected(app, client, db):
    admin = make_user(db, email="admin2@example.com", role="admin")

    response = client.post(
        f"/api/admin/users/{admin.id}/role",
        json={"role": "superuser"},
        headers=auth(session_for(app, admin.id)),
    )

    assert response.status_code == 400


# ------------------------------------------------------- sign-up policy


def test_first_account_becomes_active_admin(app, db):
    """The system must be usable out of the box."""
    from backend.api.auth_routes import LOGIN_USER_ID, _resolve_user

    with app.app_context():
        user, created = _resolve_user(
            db, LOGIN_USER_ID, "sub-first", {"name": "First", "email": "f@x.com"}
        )
        db.commit()

    assert created and user.role == "admin" and user.is_active


def test_second_account_is_inactive_operator(app, db):
    """Otherwise anyone with a LinkedIn account could sign up and use the tool."""
    from backend.api.auth_routes import LOGIN_USER_ID, _resolve_user

    with app.app_context():
        _resolve_user(db, LOGIN_USER_ID, "sub-1", {"name": "A", "email": "a@x.com"})
        db.commit()
        second, created = _resolve_user(
            db, LOGIN_USER_ID, "sub-2", {"name": "B", "email": "b@x.com"}
        )
        db.commit()

    assert created and second.role == "operator" and not second.is_active


def test_allowlist_disables_first_user_bootstrap(app, db, monkeypatch):
    """With an allowlist set, an unlisted first account must NOT become admin."""
    monkeypatch.setenv("ADMIN_LINKEDIN_SUBS", "the-owner-sub")

    from backend.api.auth_routes import LOGIN_USER_ID, _resolve_user

    with app.app_context():
        user, created = _resolve_user(
            db, LOGIN_USER_ID, "some-stranger", {"name": "Stranger"}
        )
        db.commit()

    assert created
    assert user.role == "operator"
    assert not user.is_active


def test_allowlisted_identity_becomes_admin(app, db, monkeypatch):
    monkeypatch.setenv("ADMIN_LINKEDIN_SUBS", "the-owner-sub")

    from backend.api.auth_routes import LOGIN_USER_ID, _resolve_user

    with app.app_context():
        user, _ = _resolve_user(db, LOGIN_USER_ID, "the-owner-sub", {"name": "Owner"})
        db.commit()

    assert user.role == "admin" and user.is_active


def test_allowlist_restores_admin_after_tampering(app, db, monkeypatch):
    """Self-healing: a demoted or deactivated owner is restored on next login."""
    monkeypatch.setenv("ADMIN_LINKEDIN_SUBS", "the-owner-sub")

    from backend.api.auth_routes import LOGIN_USER_ID, _resolve_user

    with app.app_context():
        user, _ = _resolve_user(db, LOGIN_USER_ID, "the-owner-sub", {"name": "Owner"})
        db.commit()

        user.role = "operator"
        user.is_active = False
        db.commit()

        again, created = _resolve_user(
            db, LOGIN_USER_ID, "the-owner-sub", {"name": "Owner"}
        )
        db.commit()

    assert not created
    assert again.role == "admin" and again.is_active


def test_signups_can_be_closed_entirely(app, db, monkeypatch):
    monkeypatch.setenv("ADMIN_LINKEDIN_SUBS", "the-owner-sub")
    monkeypatch.setenv("ALLOW_NEW_SIGNUPS", "false")

    from backend.api.auth_routes import LOGIN_USER_ID, _resolve_user

    with app.app_context():
        user, created = _resolve_user(db, LOGIN_USER_ID, "outsider", {"name": "Nope"})

    assert user is None and not created


def test_returning_user_is_matched_not_duplicated(app, db):
    from backend.api.auth_routes import LOGIN_USER_ID, _resolve_user
    from backend.models.user import User

    with app.app_context():
        first, _ = _resolve_user(
            db, LOGIN_USER_ID, "sub-same", {"name": "A", "email": "a@x.com"}
        )
        db.commit()
        again, created = _resolve_user(
            db, LOGIN_USER_ID, "sub-same", {"name": "A", "email": "a@x.com"}
        )
        db.commit()

    assert not created
    assert again.id == first.id
    assert db.query(User).count() == 1
