"""Basic coverage for the Clerk sign-in bridge.

Not exhaustive - the point of these is to catch the two ways this feature
could go quietly wrong: accepting a token that was never actually signed by
Clerk, and losing a per-user LinkedIn secret to a bad round trip.
"""

import base64
import json
import os
import tempfile
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

API_KEY = "test-key-clerk"

# A throwaway RSA keypair standing in for Clerk's real signing key. Tokens
# signed with this must be rejected once verification checks against the
# REAL (mocked) JWKS below, which deliberately does not contain it.
_FORGED_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _fake_publishable_key(domain: str) -> str:
    encoded = base64.b64encode(f"{domain}$".encode()).decode()
    return f"pk_test_{encoded}"


# A REAL Clerk Frontend API domain with a REAL, live JWKS endpoint - not a
# made-up host. The forged-token test below has to fetch actual public keys
# and fail signature verification against them; pointing it at a domain whose
# JWKS 400s or 404s would make that test pass for the wrong reason (unreachable
# JWKS, not "signature didn't match") and prove nothing about the real defense.
PUBLISHABLE_KEY = _fake_publishable_key("noble-glowworm-144.clerk.accounts.dev")


@pytest.fixture
def app(monkeypatch, tmp_path):
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    monkeypatch.setenv("API_ACCESS_KEY", API_KEY)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("REELS_FOLDER", str(tmp_path / "reels"))
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_fake")
    monkeypatch.setenv("VITE_CLERK_PUBLISHABLE_KEY", PUBLISHABLE_KEY)

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


@pytest.fixture
def client(app):
    return app.test_client()


def _forged_token(sub="user_forged", issuer="https://noble-glowworm-144.clerk.accounts.dev"):
    """A structurally valid RS256 JWT, signed with a key Clerk never issued.

    Deliberately reuses the REAL kid this Clerk instance publishes, so
    verification is forced to load the genuine public key for that kid and
    attempt a real signature check - and fail specifically because the
    signature doesn't match, not because the kid was unrecognized. That's the
    strongest form of this test: an attacker would reuse a real kid too.
    """
    return jwt.encode(
        {"sub": sub, "iss": issuer},
        _FORGED_KEY,
        algorithm="RS256",
        headers={"kid": "ins_3I0JgxHZU22X4mUMDGbOR0Q7zci"},
    )


class TestClerkVerification:
    def test_a_forged_token_is_rejected(self, client):
        """The one property that has to hold: a token nobody at Clerk signed
        must not produce a session, no matter how plausible its claims look."""
        response = client.post(
            "/api/auth/clerk/verify", json={"token": _forged_token()}
        )
        assert response.status_code == 401
        assert "token" not in response.get_json()

    def test_missing_token_is_a_400_not_a_500(self, client):
        response = client.post("/api/auth/clerk/verify", json={})
        assert response.status_code == 400

    def test_unconfigured_server_reports_503_not_a_crash(self, monkeypatch, app):
        monkeypatch.setenv("CLERK_SECRET_KEY", "")
        with app.test_client() as c:
            response = c.post(
                "/api/auth/clerk/verify", json={"token": _forged_token()}
            )
        assert response.status_code == 503

    def test_a_verified_token_creates_a_working_session(self, client):
        """The happy path, with Clerk itself mocked out: a token that DOES
        verify results in a real, usable app session token.

        The very first account on an empty database bootstraps to admin (same
        rule as the LinkedIn path) - see test_second_account_is_a_plain_operator
        for the case that actually exercises the "operator" default.
        """
        with patch(
            "backend.utils.clerk_auth.verify_session_token", return_value="user_abc123"
        ), patch(
            "backend.utils.clerk_auth.fetch_user_profile",
            return_value={
                "email": "person@example.com",
                "name": "Test Person",
                "avatar_url": None,
                "public_metadata": {},
            },
        ):
            response = client.post(
                "/api/auth/clerk/verify", json={"token": "irrelevant-mocked"}
            )

        assert response.status_code == 200
        body = response.get_json()
        assert body["user"]["email"] == "person@example.com"
        assert body["user"]["role"] == "admin"

        # The minted token must actually authenticate, exactly like a
        # LinkedIn-issued one - that's the whole point of reusing
        # make_session_token instead of inventing a second scheme.
        me = client.get("/api/me", headers={"Authorization": f"Bearer {body['token']}"})
        assert me.status_code == 200
        assert me.get_json()["email"] == "person@example.com"

    def test_second_account_is_a_plain_operator(self, client):
        """Bootstrap only ever promotes the FIRST account on an empty
        database - anyone signing up after that is an ordinary operator."""
        with patch(
            "backend.utils.clerk_auth.verify_session_token", return_value="user_first"
        ), patch(
            "backend.utils.clerk_auth.fetch_user_profile",
            return_value={
                "email": "first@example.com", "name": "First",
                "avatar_url": None, "public_metadata": {},
            },
        ):
            client.post("/api/auth/clerk/verify", json={"token": "t"})

        with patch(
            "backend.utils.clerk_auth.verify_session_token", return_value="user_second"
        ), patch(
            "backend.utils.clerk_auth.fetch_user_profile",
            return_value={
                "email": "second@example.com", "name": "Second",
                "avatar_url": None, "public_metadata": {},
            },
        ):
            response = client.post("/api/auth/clerk/verify", json={"token": "t"})

        assert response.get_json()["user"]["role"] == "operator"

    def test_admin_allowlisted_email_becomes_admin(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_CLERK_EMAILS", "boss@example.com")

        with patch(
            "backend.utils.clerk_auth.verify_session_token", return_value="user_boss"
        ), patch(
            "backend.utils.clerk_auth.fetch_user_profile",
            return_value={
                "email": "boss@example.com",
                "name": "Boss",
                "avatar_url": None,
                "public_metadata": {},
            },
        ):
            response = client.post(
                "/api/auth/clerk/verify", json={"token": "irrelevant-mocked"}
            )

        assert response.get_json()["user"]["role"] == "admin"

    def test_signing_in_twice_reuses_the_same_account(self, client):
        """Keyed on clerk_id, not created fresh every time."""
        with patch(
            "backend.utils.clerk_auth.verify_session_token", return_value="user_repeat"
        ), patch(
            "backend.utils.clerk_auth.fetch_user_profile",
            return_value={
                "email": "repeat@example.com",
                "name": "Repeat",
                "avatar_url": None,
                "public_metadata": {},
            },
        ):
            first = client.post("/api/auth/clerk/verify", json={"token": "t1"})
            second = client.post("/api/auth/clerk/verify", json={"token": "t2"})

        assert first.get_json()["user"]["id"] == second.get_json()["user"]["id"]


class TestLinkedInCredentials:
    def _sign_in(self, client):
        with patch(
            "backend.utils.clerk_auth.verify_session_token", return_value="user_creds"
        ), patch(
            "backend.utils.clerk_auth.fetch_user_profile",
            return_value={
                "email": "creds@example.com",
                "name": "Creds",
                "avatar_url": None,
                "public_metadata": {},
            },
        ):
            response = client.post("/api/auth/clerk/verify", json={"token": "t"})
        return response.get_json()["token"]

    def test_saving_then_reading_status_round_trips(self, client):
        token = self._sign_in(client)
        headers = {"Authorization": f"Bearer {token}"}

        save = client.post(
            "/api/integrations/linkedin/credentials",
            json={"client_id": "abc123", "client_secret": "shh-secret"},
            headers=headers,
        )
        assert save.status_code == 200

        status = client.get(
            "/api/integrations/linkedin/credentials/status", headers=headers
        )
        body = status.get_json()
        assert body["configured"] is True
        assert body["client_id"] == "abc123"
        # The secret itself must never come back over the wire.
        assert "client_secret" not in body
        assert "shh-secret" not in status.get_data(as_text=True)

    def test_clearing_credentials_falls_back_cleanly(self, client):
        token = self._sign_in(client)
        headers = {"Authorization": f"Bearer {token}"}

        client.post(
            "/api/integrations/linkedin/credentials",
            json={"client_id": "abc123", "client_secret": "shh-secret"},
            headers=headers,
        )
        cleared = client.delete("/api/integrations/linkedin/credentials", headers=headers)
        assert cleared.status_code == 200
        assert cleared.get_json()["configured"] is False

    def test_unauthenticated_caller_is_refused(self, client):
        response = client.get("/api/integrations/linkedin/credentials/status")
        assert response.status_code == 401


class TestCryptoRoundTrip:
    def test_encrypt_then_decrypt_recovers_the_original(self):
        from backend.utils.crypto import decrypt_secret, encrypt_secret

        secret = "super-secret-linkedin-client-secret"
        ciphertext = encrypt_secret(secret)

        assert ciphertext != secret
        assert decrypt_secret(ciphertext) == secret

    def test_garbage_ciphertext_raises_rather_than_returning_nonsense(self):
        from backend.utils.crypto import decrypt_secret

        with pytest.raises(ValueError):
            decrypt_secret("not-actually-encrypted")
