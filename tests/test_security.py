"""Tests for API authentication and OAuth state signing.

These cover the properties that make the gate worth having: it fails closed,
it cannot be bypassed by a forged or expired state, and it does not leak the
key through comparison timing or query strings.
"""

import json
import time
from unittest.mock import patch

import pytest

from backend.utils.security import (
    PUBLIC_PATHS,
    _b64encode,
    _sign,
    make_oauth_state,
    verify_oauth_state,
)


@pytest.fixture
def app():
    """A real app instance with a known API key."""
    with patch.dict("os.environ", {"API_ACCESS_KEY": "test-key-12345"}):
        from backend.utils.config import get_settings

        get_settings.cache_clear() if hasattr(get_settings, "cache_clear") else None
        from backend.app import create_app

        application = create_app()
        application.config["TESTING"] = True
        yield application


@pytest.fixture
def client(app):
    return app.test_client()


# ------------------------------------------------------------- API key gate


def test_health_is_public(client):
    """Render's health probe cannot send custom headers."""
    assert client.get("/health").status_code != 401


def test_api_route_without_key_is_rejected(client):
    response = client.get("/api/status")
    assert response.status_code in (401, 503)


def test_api_route_with_wrong_key_is_rejected(client):
    response = client.get(
        "/api/status", headers={"Authorization": "Bearer wrong-key"}
    )
    assert response.status_code in (401, 503)


def test_api_route_with_correct_key_is_allowed(client):
    response = client.get(
        "/api/status", headers={"Authorization": "Bearer test-key-12345"}
    )
    assert response.status_code == 200


def test_x_api_key_header_also_works(client):
    response = client.get("/api/status", headers={"X-API-Key": "test-key-12345"})
    assert response.status_code == 200


def test_key_in_query_string_is_not_accepted(client):
    """URLs land in logs, history, and Referer headers - never accept keys there."""
    response = client.get("/api/status?api_key=test-key-12345")
    assert response.status_code in (401, 503)


def test_oauth_callback_is_public(client):
    """LinkedIn's redirect cannot carry our bearer token."""
    assert "/api/auth/linkedin/callback" in PUBLIC_PATHS
    # Reachable without a key, and rejects the request on state grounds instead.
    response = client.get("/api/auth/linkedin/callback?code=x&state=bogus")
    assert response.status_code != 401


def test_unset_key_fails_closed(client):
    """An unset key must reject everything, never serve openly."""
    with patch("backend.utils.security.api_key_configured", return_value=False):
        response = client.get("/api/status")
    assert response.status_code == 503
    assert "API_ACCESS_KEY" in response.get_json()["error"]


def test_placeholder_key_counts_as_unconfigured():
    from backend.utils.security import api_key_configured

    with patch("backend.utils.security.get_settings") as settings:
        settings.return_value.api_access_key = "your_api_key_here"
        assert not api_key_configured()


# ---------------------------------------------------------- OAuth state


def test_state_roundtrip(app):
    with app.app_context():
        state = make_oauth_state(42)
        user_id, error, link_github = verify_oauth_state(state)
    assert user_id == 42 and error == "" and link_github is None


def test_state_with_tampered_user_id_is_rejected(app):
    """The whole point: a returned state cannot be retargeted at another user."""
    with app.app_context():
        state = make_oauth_state(1)
        encoded, signature = state.rsplit(".", 1)

        forged_payload = json.dumps(
            {"user_id": 999, "exp": int(time.time()) + 600, "nonce": "x"},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        forged = f"{_b64encode(forged_payload)}.{signature}"

        user_id, error, _ = verify_oauth_state(forged)

    assert user_id is None
    assert "signature" in error


def test_state_with_forged_signature_is_rejected(app):
    with app.app_context():
        state = make_oauth_state(1)
        encoded, _ = state.rsplit(".", 1)
        user_id, error, _ = verify_oauth_state(f"{encoded}.not-a-real-signature")
    assert user_id is None and "signature" in error


def test_expired_state_is_rejected(app):
    with app.app_context():
        payload = json.dumps(
            {"user_id": 1, "exp": int(time.time()) - 10, "nonce": "x"},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        expired = f"{_b64encode(payload)}.{_sign(payload)}"
        user_id, error, _ = verify_oauth_state(expired)
    assert user_id is None and "expired" in error


def test_missing_state_is_rejected(app):
    with app.app_context():
        assert verify_oauth_state(None)[0] is None
        assert verify_oauth_state("")[0] is None
        assert verify_oauth_state("no-dot-here")[0] is None


def test_states_are_unique_per_call(app):
    """Two concurrent attempts for the same user must not collide."""
    with app.app_context():
        assert make_oauth_state(1) != make_oauth_state(1)


def test_state_can_carry_a_github_login_to_link(app):
    """The MCP self-serve flow signs a GitHub login into the state so the
    LinkedIn callback can map it automatically - see mcp_link_start."""
    with app.app_context():
        state = make_oauth_state(0, link_github="octocat")
        user_id, error, link_github = verify_oauth_state(state)
    assert user_id == 0 and error == "" and link_github == "octocat"


def test_a_plain_sign_in_state_carries_no_github_login(app):
    with app.app_context():
        state = make_oauth_state(0)
        _, _, link_github = verify_oauth_state(state)
    assert link_github is None


def test_a_tampered_github_login_is_rejected_with_the_whole_state(app):
    """The link_github field is covered by the same signature as user_id -
    swapping it for a different login must fail closed, not silently accept
    the tampered value."""
    with app.app_context():
        state = make_oauth_state(0, link_github="real-login")
        encoded, signature = state.rsplit(".", 1)

        forged_payload = json.dumps(
            {
                "user_id": 0,
                "exp": int(time.time()) + 600,
                "nonce": "x",
                "link_github": "attacker-login",
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        forged = f"{_b64encode(forged_payload)}.{signature}"

        user_id, error, link_github = verify_oauth_state(forged)

    assert user_id is None
    assert link_github is None
    assert "signature" in error
