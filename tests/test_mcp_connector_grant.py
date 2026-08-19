"""The website-mediated MCP connector authorization (no GitHub, no third-party
consent screen): the Worker sends the browser to the website, the website
authenticates them however it normally does, then /mcp/authorize-connector
mints a short-lived grant the Worker redeems via /mcp/verify-connector-grant
to finish its own OAuth handshake with Claude. See backend/utils/security.py's
make_mcp_connector_grant/verify_mcp_connector_grant.
"""

import os
import tempfile

import pytest

API_KEY = "test-key-connector-grant"


@pytest.fixture
def app(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    monkeypatch.setenv("API_ACCESS_KEY", API_KEY)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")
    monkeypatch.setenv("LINKEDIN_CLIENT_ID", "client-id")
    monkeypatch.setenv("LINKEDIN_CLIENT_SECRET", "client-secret")

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


def _make_active_user(db, role="admin", **kwargs):
    from backend.models.user import User

    user = User(is_active=True, role=role, **kwargs)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ------------------------------------------------------- authorize-connector


def test_authorize_connector_requires_a_signed_in_user(client):
    res = client.post("/api/mcp/authorize-connector", json={"worker_state": "abc"})
    assert res.status_code == 401


def test_authorize_connector_rejects_a_missing_worker_state(app):
    from backend.utils.database import get_session
    from backend.utils.security import make_session_token

    db = get_session()
    try:
        user = _make_active_user(db, linkedin_sub="sub-connector-1")
        token = make_session_token(user.id)
    finally:
        db.close()

    with app.test_client() as client:
        res = client.post(
            "/api/mcp/authorize-connector",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 400


def test_authorize_connector_mints_a_grant_redeemable_for_the_same_state(app):
    from backend.utils.database import get_session
    from backend.utils.security import make_session_token

    db = get_session()
    try:
        user = _make_active_user(db, linkedin_sub="sub-connector-2")
        token = make_session_token(user.id)
        user_id = user.id
    finally:
        db.close()

    with app.test_client() as client:
        res = client.post(
            "/api/mcp/authorize-connector",
            json={"worker_state": "worker-state-xyz"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        grant = res.get_json()["grant"]

        verify_res = client.post(
            "/api/mcp/verify-connector-grant",
            json={"grant": grant, "worker_state": "worker-state-xyz"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
    assert verify_res.status_code == 200
    body = verify_res.get_json()
    assert body["id"] == user_id
    assert body["role"] == "admin"


# --------------------------------------------------------- verify-connector-grant


def test_verify_connector_grant_refuses_a_non_admin_session(app):
    """Same require_admin guard as every other admin route: a machine
    caller (the Worker) or a human admin, not an ordinary signed-in user."""
    from backend.utils.database import get_session
    from backend.utils.security import make_session_token

    db = get_session()
    try:
        user = _make_active_user(db, linkedin_sub="sub-connector-3", role="operator")
        token = make_session_token(user.id)
    finally:
        db.close()

    with app.test_client() as client:
        res = client.post(
            "/api/mcp/verify-connector-grant",
            json={"grant": "whatever", "worker_state": "s"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 403


def test_verify_connector_grant_rejects_a_grant_bound_to_a_different_worker_state(app):
    from backend.utils.database import get_session
    from backend.utils.security import make_session_token

    db = get_session()
    try:
        user = _make_active_user(db, linkedin_sub="sub-connector-4")
        token = make_session_token(user.id)
    finally:
        db.close()

    with app.test_client() as client:
        grant = client.post(
            "/api/mcp/authorize-connector",
            json={"worker_state": "state-A"},
            headers={"Authorization": f"Bearer {token}"},
        ).get_json()["grant"]

        # Replaying it against a DIFFERENT connector attempt must fail closed.
        res = client.post(
            "/api/mcp/verify-connector-grant",
            json={"grant": grant, "worker_state": "state-B"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
    assert res.status_code == 401


def test_verify_connector_grant_rejects_a_forged_grant(app):
    with app.test_client() as client:
        res = client.post(
            "/api/mcp/verify-connector-grant",
            json={"grant": "not-a-real-grant", "worker_state": "s"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
    assert res.status_code == 401


def test_verify_connector_grant_rejects_an_inactive_account(app):
    """Deactivation must take effect even for a grant minted before it -
    an already-issued grant is short-lived, but should not be a loophole."""
    from backend.utils.database import get_session
    from backend.utils.security import make_mcp_connector_grant

    with app.app_context():
        db = get_session()
        try:
            user = _make_active_user(db, linkedin_sub="sub-connector-5")
            grant = make_mcp_connector_grant(user.id, "state-inactive")
            user.is_active = False
            db.commit()
        finally:
            db.close()

    with app.test_client() as client:
        res = client.post(
            "/api/mcp/verify-connector-grant",
            json={"grant": grant, "worker_state": "state-inactive"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
    assert res.status_code == 404


def test_a_grant_from_the_unit_helpers_round_trips(app):
    """Direct unit coverage of the signing helpers, independent of the routes."""
    with app.app_context():
        from backend.utils.security import make_mcp_connector_grant, verify_mcp_connector_grant

        grant = make_mcp_connector_grant(42, "some-state")
        assert verify_mcp_connector_grant(grant, "some-state") == 42
        assert verify_mcp_connector_grant(grant, "different-state") is None
        assert verify_mcp_connector_grant(None, "some-state") is None
        assert verify_mcp_connector_grant("garbage", "some-state") is None


# --------------------------------------------------------------- next redirect


class _Response:
    def __init__(self, payload, status=200):
        import json as _json

        self._payload = payload
        self.status_code = status
        self.text = _json.dumps(payload)

    def json(self):
        return self._payload


def test_linkedin_login_with_next_lands_the_callback_on_that_path(app):
    """The /mcp-authorize page needs LinkedIn sign-in to return to ITSELF,
    not the normal dashboard - see make_oauth_state's `next` and
    auth_routes.py's _redirect/_next_redirect."""
    from unittest.mock import patch

    with app.test_client() as client:
        start_res = client.get(
            "/api/auth/linkedin/login?next=%2Fmcp-authorize%3Fstate%3Dworker-abc"
        )
        assert start_res.status_code == 302
        from urllib.parse import urlparse, parse_qs

        state = parse_qs(urlparse(start_res.headers["Location"]).query)["state"][0]

        with patch(
            "backend.api.auth_routes.requests.post",
            return_value=_Response({"access_token": "at", "expires_in": 3600}),
        ), patch(
            "backend.api.auth_routes.requests.get",
            return_value=_Response(
                {"sub": "next-flow-sub", "name": "Next Flow", "email": "next@example.com"}
            ),
        ):
            callback_res = client.get(f"/api/auth/linkedin/callback?code=abc&state={state}")

    location = callback_res.headers["Location"]
    assert location.startswith("http://localhost:5173/mcp-authorize?state=worker-abc")
    assert "#token=" in location
    # Must NOT have fallen back to the normal dashboard redirect.
    assert "linkedin=connected" not in location
