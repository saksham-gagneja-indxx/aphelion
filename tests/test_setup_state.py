"""Setup progress reporting.

The step that matters here is 'publish'. Signing in successfully says nothing
about whether publishing will work: if the "Share on LinkedIn" product was
never added to the LinkedIn app, the member consents, the account connects, and
every post then fails on a missing w_member_social scope. Reading the granted
scope back off the token is what lets that be said during setup instead of
discovered when a scheduled post fires.
"""

import os
import tempfile
from datetime import timedelta

import pytest

from backend.utils.timeutil import utcnow

API_KEY = "test-key-setup"


@pytest.fixture
def app(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    monkeypatch.setenv("API_ACCESS_KEY", API_KEY)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("LINKEDIN_CLIENT_ID", "real-client-id")
    monkeypatch.setenv("LINKEDIN_CLIENT_SECRET", "real-client-secret")
    monkeypatch.setenv(
        "LINKEDIN_REDIRECT_URI", "http://localhost:5000/api/auth/linkedin/callback"
    )

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


def _make_user(**kwargs):
    from backend.models.user import User
    from backend.utils.database import get_session

    db = get_session()
    try:
        defaults = dict(
            linkedin_sub="sub-setup", full_name="Setup User", email="s@test",
            role="operator", is_active=True,
        )
        defaults.update(kwargs)
        user = User(**defaults)
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


def _state(app, user):
    from backend.utils.security import make_session_token

    with app.test_client() as client:
        res = client.get(
            "/api/setup/state",
            headers={"Authorization": f"Bearer {make_session_token(user.id)}"},
        )
    assert res.status_code == 200
    body = res.get_json()
    return {s["id"]: s for s in body["steps"]}, body


def _connected(**extra):
    return dict(
        linkedin_access_token="token",
        linkedin_person_urn="urn:li:person:abc",
        linkedin_token_expires_at=utcnow() + timedelta(days=30),
        **extra,
    )


def test_a_fresh_account_has_only_the_server_step_done(app):
    user = _make_user()
    steps, body = _state(app, user)

    assert steps["app"]["done"] is True  # credentials are set in this fixture
    assert steps["connect"]["done"] is False
    assert steps["publish"]["done"] is False
    assert body["complete"] is False


def test_connecting_without_the_publish_scope_is_reported_as_incomplete(app):
    """The whole point: connected but unable to post is a distinct state."""
    user = _make_user(**_connected(linkedin_scope="openid profile"))
    steps, body = _state(app, user)

    assert steps["connect"]["done"] is True
    assert steps["publish"]["done"] is False
    assert "w_member_social" in steps["publish"]["detail"]
    assert body["complete"] is False


def test_a_full_grant_completes_setup(app):
    user = _make_user(**_connected(linkedin_scope="openid profile w_member_social"))
    steps, body = _state(app, user)

    assert all(s["done"] for s in steps.values())
    assert body["complete"] is True


def test_a_comma_delimited_grant_from_linkedin_completes_setup(app):
    """LinkedIn's real token response has been observed to delimit scopes
    with commas rather than the OAuth-spec space - a single-element list
    like ["openid,profile,w_member_social"] must still be recognized as
    granting w_member_social, not silently fail the membership check."""
    user = _make_user(**_connected(linkedin_scope="openid,profile,w_member_social"))
    steps, body = _state(app, user)

    assert all(s["done"] for s in steps.values())
    assert body["complete"] is True


def test_an_expired_token_is_not_treated_as_able_to_publish(app):
    user = _make_user(
        linkedin_access_token="token",
        linkedin_person_urn="urn:li:person:abc",
        linkedin_token_expires_at=utcnow() - timedelta(days=1),
        linkedin_scope="openid profile w_member_social",
    )
    steps, _ = _state(app, user)

    assert steps["connect"]["done"] is False
    assert steps["publish"]["done"] is False


def test_a_grant_stored_before_scopes_were_recorded_is_assumed_capable(app):
    """Existing accounts have no scope recorded; calling them broken is worse."""
    user = _make_user(**_connected(linkedin_scope=None))
    steps, _ = _state(app, user)

    assert steps["publish"]["done"] is True


def test_scope_matching_is_by_token_not_substring(app):
    """A scope merely containing the string must not count as granting it."""
    user = _make_user(**_connected(linkedin_scope="openid w_member_social_readonly"))
    steps, _ = _state(app, user)

    assert steps["publish"]["done"] is False


def test_server_configuration_detail_is_withheld_from_non_admins(app, monkeypatch):
    monkeypatch.setenv("LINKEDIN_CLIENT_ID", "your_client_id")
    monkeypatch.setenv("LINKEDIN_CLIENT_SECRET", "your_secret")

    operator = _make_user(linkedin_sub="sub-op", email="op@test", role="operator")
    steps, _ = _state(app, operator)
    assert "LINKEDIN_CLIENT_ID" not in (steps["app"]["detail"] or "")

    admin = _make_user(linkedin_sub="sub-admin", email="ad@test", role="admin")
    steps, _ = _state(app, admin)
    assert "LINKEDIN_CLIENT_ID" in steps["app"]["detail"]


def test_setup_state_requires_a_signed_in_user(app):
    """The API key is a machine credential and has no setup to report."""
    with app.test_client() as client:
        res = client.get(
            "/api/setup/state", headers={"Authorization": f"Bearer {API_KEY}"}
        )
    assert res.status_code == 401
