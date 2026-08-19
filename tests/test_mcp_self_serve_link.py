"""Self-serve GitHub<->backend account linking for the MCP connector.

Before this, a GitHub login with no mapped account was a dead end: the MCP
tool told the person to ask an admin to run `admin_cli set-github`. Now the
Worker can call POST /api/mcp/link-start to get a real LinkedIn sign-in URL
whose state carries that (already GitHub-verified) login signed into itself,
so the callback can set User.github_username automatically on success - see
backend/utils/security.py's make_oauth_state/verify_oauth_state and
auth_routes.py's mcp_link_start/linkedin_callback.
"""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

API_KEY = "test-key-linkstart"


@pytest.fixture
def app(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    monkeypatch.setenv("API_ACCESS_KEY", API_KEY)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("LINKEDIN_CLIENT_ID", "client-id")
    monkeypatch.setenv("LINKEDIN_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")

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


class _Response:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


# ------------------------------------------------------------- link-start


def test_link_start_requires_a_bearer_key(app):
    with app.test_client() as client:
        res = client.post("/api/mcp/link-start", json={"github_username": "octocat"})
    # Rejected by the blanket API-key gate before require_admin() is even
    # reached - this route isn't on the public-endpoints exception list.
    assert res.status_code == 401


def test_link_start_requires_a_github_username(app):
    with app.test_client() as client:
        res = client.post(
            "/api/mcp/link-start",
            json={},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
    assert res.status_code == 400


def test_link_start_returns_a_linkedin_url_carrying_the_login(app):
    from backend.utils.security import verify_oauth_state
    from urllib.parse import urlparse, parse_qs

    with app.test_client() as client:
        res = client.post(
            "/api/mcp/link-start",
            json={"github_username": "octocat"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
    assert res.status_code == 200
    url = res.get_json()["url"]
    assert url.startswith("https://www.linkedin.com/oauth/v2/authorization")

    state = parse_qs(urlparse(url).query)["state"][0]
    with app.app_context():
        user_id, error, link_github = verify_oauth_state(state)
    assert error == ""
    assert link_github == "octocat"


def test_link_start_503s_when_linkedin_is_not_configured(app, monkeypatch):
    monkeypatch.setenv("LINKEDIN_CLIENT_ID", "")
    monkeypatch.setenv("LINKEDIN_CLIENT_SECRET", "")
    with app.test_client() as client:
        res = client.post(
            "/api/mcp/link-start",
            json={"github_username": "octocat"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
    assert res.status_code == 503


# -------------------------------------------------------- callback linking

CLAIMS = {
    "sub": "linkedin-subject-self-serve",
    "name": "New Person",
    "email": "new@example.com",
}


def _authorize_url_for(app, github_username):
    with app.test_client() as client:
        res = client.post(
            "/api/mcp/link-start",
            json={"github_username": github_username},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
    from urllib.parse import urlparse, parse_qs

    return parse_qs(urlparse(res.get_json()["url"]).query)["state"][0]


def _run_callback(app, state, token_payload):
    with patch("backend.api.auth_routes.requests.post", return_value=_Response(token_payload)), \
         patch("backend.api.auth_routes.requests.get") as mock_get:
        mock_get.return_value = _Response(CLAIMS)
        with app.test_client() as client:
            return client.get(f"/api/auth/linkedin/callback?code=abc&state={state}")


def _id_token(claims):
    import base64

    def seg(obj):
        raw = json.dumps(obj).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    return f"{seg({'alg': 'RS256'})}.{seg(claims)}.sig"


def test_a_successful_signin_maps_the_github_login_automatically(app):
    from backend.models.user import User
    from backend.utils.database import get_session

    # A pre-existing account so the self-serve signup below isn't the
    # bootstrap "first user is free admin" case - that path is exercised
    # separately and would make the is_active assertion below meaningless.
    db = get_session()
    try:
        db.add(User(linkedin_sub="already-here", is_active=True, role="admin"))
        db.commit()
    finally:
        db.close()

    state = _authorize_url_for(app, "new-github-user")
    res = _run_callback(
        app, state, {"access_token": "at", "expires_in": 3600, "id_token": _id_token(CLAIMS)}
    )

    # Self-serve linking must not bypass approval - a second-or-later account
    # with no allowlist configured still lands pending, same as the web app.
    # The redirect target is the standalone /mcp-connected page, not the
    # normal dashboard landing - see _frontend_url's mcp flag.
    assert "/mcp-connected" in res.headers["Location"]
    assert "status=pending_approval" in res.headers["Location"]

    db = get_session()
    try:
        user = db.query(User).filter(User.linkedin_sub == CLAIMS["sub"]).first()
        assert user is not None
        # The mapping happens regardless of approval status - it's what lets
        # the *next* attempt (after an admin approves) resolve immediately.
        assert user.github_username == "new-github-user"
        assert user.is_active is False
    finally:
        db.close()


def test_linking_does_not_steal_a_login_already_mapped_to_someone_else(app):
    from backend.models.user import User
    from backend.utils.database import get_session

    db = get_session()
    try:
        existing = User(
            linkedin_sub="someone-else",
            github_username="claimed-login",
            is_active=True,
        )
        db.add(existing)
        db.commit()
    finally:
        db.close()

    state = _authorize_url_for(app, "claimed-login")
    _run_callback(
        app, state, {"access_token": "at", "expires_in": 3600, "id_token": _id_token(CLAIMS)}
    )

    db = get_session()
    try:
        new_user = db.query(User).filter(User.linkedin_sub == CLAIMS["sub"]).first()
        original_owner = db.query(User).filter(User.linkedin_sub == "someone-else").first()
        assert new_user is not None
        # The new account signed in fine, just without the disputed mapping.
        assert new_user.github_username != "claimed-login"
        # The original mapping is untouched.
        assert original_owner.github_username == "claimed-login"
    finally:
        db.close()


# ---------------------------------------------------- admin set-github route


def test_admin_can_clear_and_reset_a_github_mapping(app):
    """HTTP twin of `admin_cli set-github`/`unset-github` - lets an admin
    re-test the self-serve link flow against an already-mapped account
    without shell access to the database."""
    from backend.models.user import User
    from backend.utils.database import get_session

    db = get_session()
    try:
        user = User(linkedin_sub="sub-github-route", github_username="original-login", is_active=True)
        db.add(user)
        db.commit()
        user_id = user.id
    finally:
        db.close()

    with app.test_client() as client:
        res = client.post(
            f"/api/admin/users/{user_id}/github",
            json={"github_username": None},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
    assert res.status_code == 200
    assert res.get_json()["github_username"] is None

    db = get_session()
    try:
        assert db.query(User).filter(User.id == user_id).first().github_username is None
    finally:
        db.close()

    with app.test_client() as client:
        res = client.post(
            f"/api/admin/users/{user_id}/github",
            json={"github_username": "original-login"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
    assert res.status_code == 200
    assert res.get_json()["github_username"] == "original-login"


def test_admin_cannot_steal_a_github_login_via_the_route(app):
    from backend.models.user import User
    from backend.utils.database import get_session

    db = get_session()
    try:
        owner = User(linkedin_sub="sub-github-owner", github_username="taken", is_active=True)
        other = User(linkedin_sub="sub-github-other", is_active=True)
        db.add_all([owner, other])
        db.commit()
        other_id = other.id
    finally:
        db.close()

    with app.test_client() as client:
        res = client.post(
            f"/api/admin/users/{other_id}/github",
            json={"github_username": "taken"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
    assert res.status_code == 409


def test_a_plain_signin_state_leaves_github_username_untouched(app):
    """No link_github in the state (the ordinary web-app sign-in) must not
    touch github_username at all."""
    from backend.api.auth_routes import LOGIN_USER_ID
    from backend.models.user import User
    from backend.utils.database import get_session
    from backend.utils.security import make_oauth_state

    state = make_oauth_state(LOGIN_USER_ID)
    res = _run_callback(
        app, state, {"access_token": "at", "expires_in": 3600, "id_token": _id_token(CLAIMS)}
    )

    # A plain sign-in still lands on the normal dashboard redirect, not the
    # MCP standalone page - only a link_github-carrying state routes there.
    assert "/mcp-connected" not in res.headers["Location"]
    assert "linkedin=connected" in res.headers["Location"]

    db = get_session()
    try:
        user = db.query(User).filter(User.linkedin_sub == CLAIMS["sub"]).first()
        assert user is not None
        assert user.github_username is None
    finally:
        db.close()


def test_a_successful_mcp_signin_redirects_to_the_standalone_page(app):
    res = _run_callback(
        app,
        _authorize_url_for(app, "fresh-mcp-user"),
        {"access_token": "at", "expires_in": 3600, "id_token": _id_token(CLAIMS)},
    )
    # No pre-existing account, so this is the bootstrap first-user-is-admin
    # case - active immediately, landing on "connected" rather than pending.
    assert "/mcp-connected" in res.headers["Location"]
    assert "status=connected" in res.headers["Location"]
