"""Sign-in reads identity from the id_token rather than calling userinfo.

The token endpoint (www.linkedin.com) and the userinfo endpoint
(api.linkedin.com) are different hosts, so sign-in used to require BOTH to be
reachable. On a network that filters api.linkedin.com by SNI - which is real,
and is what prompted this - the token exchange succeeds and sign-in then dies
with:

    SSLError(1, '[SSL: WRONG_VERSION_NUMBER] wrong version number')

Since the `openid` scope is requested, the token response already carries an
id_token with the same claims userinfo would return, so the second call is
avoidable.
"""

import base64
import json
import os
import tempfile
from unittest.mock import patch

import pytest

API_KEY = "test-key-idtoken"


def _make_id_token(claims: dict) -> str:
    """A JWT-shaped string. Only the payload segment is ever read."""

    def seg(obj):
        raw = json.dumps(obj).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    return f"{seg({'alg': 'RS256'})}.{seg(claims)}.fake-signature"


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


CLAIMS = {
    "sub": "linkedin-subject-123",
    "name": "Real Person",
    "email": "real@example.com",
    "picture": "https://media.example/photo.jpg",
}


def _callback(app, token_payload, userinfo_side_effect=None):
    """Drive the OAuth callback with a valid signed state."""
    from backend.api.auth_routes import LOGIN_USER_ID
    from backend.utils.security import make_oauth_state

    state = make_oauth_state(LOGIN_USER_ID)

    with patch("backend.api.auth_routes.requests.post", return_value=_Response(token_payload)), \
         patch("backend.api.auth_routes.requests.get") as mock_get:
        if userinfo_side_effect is not None:
            mock_get.side_effect = userinfo_side_effect
        else:
            mock_get.return_value = _Response({**CLAIMS, "sub": "from-userinfo"})

        with app.test_client() as client:
            res = client.get(f"/api/auth/linkedin/callback?code=abc&state={state}")
        return res, mock_get


def test_identity_comes_from_the_id_token_without_calling_userinfo(app):
    from backend.models.user import User
    from backend.utils.database import get_session

    res, mock_get = _callback(
        app,
        {"access_token": "at", "expires_in": 3600, "id_token": _make_id_token(CLAIMS)},
    )

    assert res.status_code == 302
    assert "linkedin=connected" in res.headers["Location"]
    # The whole point: api.linkedin.com is never contacted.
    assert mock_get.call_count == 0

    db = get_session()
    try:
        user = db.query(User).filter(User.linkedin_sub == "linkedin-subject-123").first()
        assert user is not None
        assert user.full_name == "Real Person"
        assert user.email == "real@example.com"
    finally:
        db.close()


def test_sign_in_survives_userinfo_being_unreachable(app):
    """The exact failure this addresses: api.linkedin.com blocked by SNI."""
    import requests

    res, mock_get = _callback(
        app,
        {"access_token": "at", "expires_in": 3600, "id_token": _make_id_token(CLAIMS)},
        userinfo_side_effect=requests.exceptions.SSLError(
            "[SSL: WRONG_VERSION_NUMBER] wrong version number"
        ),
    )

    assert "linkedin=connected" in res.headers["Location"]
    assert mock_get.call_count == 0


def test_falls_back_to_userinfo_when_there_is_no_id_token(app):
    """Nothing regresses for a token response without one."""
    res, mock_get = _callback(app, {"access_token": "at", "expires_in": 3600})

    assert "linkedin=connected" in res.headers["Location"]
    assert mock_get.call_count == 1


@pytest.mark.parametrize(
    "bad",
    [
        "not-a-jwt",
        "only.two",
        "aaa.!!!not-base64!!!.ccc",
        "aaa." + base64.urlsafe_b64encode(b"not json").decode().rstrip("=") + ".ccc",
        "aaa." + base64.urlsafe_b64encode(b'{"no":"subject"}').decode().rstrip("=") + ".c",
    ],
)
def test_a_malformed_id_token_falls_back_rather_than_failing(app, bad):
    """Garbage must not sign anyone in, and must not 500 either."""
    res, mock_get = _callback(app, {"access_token": "at", "expires_in": 3600, "id_token": bad})

    assert res.status_code == 302
    assert mock_get.call_count == 1, "should have fallen back to userinfo"


def test_claims_helper_ignores_a_token_without_a_subject():
    """A token that decodes but identifies nobody is not usable."""
    from backend.api.auth_routes import _claims_from_id_token

    assert _claims_from_id_token(_make_id_token({"name": "No Subject"})) == {}
    assert _claims_from_id_token(None) == {}
    assert _claims_from_id_token("") == {}
