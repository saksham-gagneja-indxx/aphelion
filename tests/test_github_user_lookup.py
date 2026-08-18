"""Tests for /api/users/by-github/<username> - the MCP connector's identity
bridge between "who authenticated via GitHub" and "which backend account
they act as".
"""

import os
import tempfile

import pytest

API_KEY = "test-key-github-lookup"


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


def _machine_auth():
    return {"Authorization": f"Bearer {API_KEY}"}


def _make_user(app, **kwargs):
    from backend.models.user import User
    from backend.utils.database import get_session

    db = get_session()
    try:
        user = User(**kwargs)
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


class TestGithubLookup:
    def test_resolves_a_mapped_github_login(self, app, client):
        user = _make_user(
            app, full_name="Dev", email="dev@test", role="operator",
            is_active=True, github_username="octocat",
        )

        response = client.get("/api/users/by-github/octocat", headers=_machine_auth())

        assert response.status_code == 200
        body = response.get_json()
        assert body["id"] == user.id
        assert body["name"] == "Dev"

    def test_unmapped_login_is_404_not_a_crash(self, app, client):
        response = client.get(
            "/api/users/by-github/nobody-registered", headers=_machine_auth()
        )
        assert response.status_code == 404

    def test_inactive_account_is_refused(self, app, client):
        """Deactivating a user must take effect here too, not just on the web
        app - otherwise disabling someone's account leaves the MCP connector
        as a backdoor that still lets them act as it."""
        _make_user(
            app, full_name="Suspended", email="susp@test", role="operator",
            is_active=False, github_username="suspended-user",
        )

        response = client.get(
            "/api/users/by-github/suspended-user", headers=_machine_auth()
        )
        assert response.status_code == 404

    def test_requires_authentication(self, client):
        response = client.get("/api/users/by-github/octocat")
        assert response.status_code == 401

    def test_a_human_session_cannot_use_this_lookup(self, app, client):
        """This resolves OTHER people's GitHub logins to account ids - an
        ordinary signed-in operator has no business calling it, only an
        admin or a machine caller should."""
        from backend.utils.security import make_session_token

        target = _make_user(
            app, full_name="Target", email="target@test", role="operator",
            is_active=True, github_username="octocat",
        )
        caller = _make_user(
            app, full_name="Caller", email="caller@test", role="operator",
            is_active=True,
        )
        token = make_session_token(caller.id)

        response = client.get(
            "/api/users/by-github/octocat",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert target.id  # sanity: fixture actually created

    def test_response_never_includes_the_github_login_itself(self, app, client):
        """Not a secret, but there is no reason to echo the caller's own
        query back - keep the response shape minimal."""
        _make_user(
            app, full_name="Dev", email="dev@test", role="operator",
            is_active=True, github_username="octocat",
        )

        response = client.get("/api/users/by-github/octocat", headers=_machine_auth())
        assert "github_username" not in response.get_json()
