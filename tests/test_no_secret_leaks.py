"""Guards against credentials leaking through API responses.

Written after /api/status was found returning the raw DATABASE_URL - which
embeds the database password. Any caller holding the API key could read it,
and it would end up in logs, screenshots, and pasted error reports.

These tests assert on the SHAPE of responses rather than on specific secrets,
so they keep working as configuration changes.
"""

import pytest

DB_PASSWORD = "sup3rs3cr3t-db-pw"
DB_URL = f"postgresql://postgres.abc:{DB_PASSWORD}@db.example.com:6543/postgres"
API_KEY = "leak-test-key"
LINKEDIN_SECRET = "WPL_AP1.super-secret-value"


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("API_ACCESS_KEY", API_KEY)
    monkeypatch.setenv("LINKEDIN_CLIENT_SECRET", LINKEDIN_SECRET)
    monkeypatch.setenv("SECRET_KEY", "signing-key-not-for-responses")
    # A real DSN shape, but pointed at a local file so no connection is made.
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/leak.db")

    import backend.utils.database as database

    database._db_instance = None

    from backend.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    yield app.test_client()

    database._db_instance = None


def _body(response) -> str:
    return response.get_data(as_text=True)


def test_status_reports_only_the_database_dialect(client):
    """The regression this file exists for.

    /api/status used to return the raw DATABASE_URL. A DSN always embeds the
    password as `user:password@host`, so asserting there is no "@" in the
    reported value is what actually pins the fix - it fails for any DSN,
    whatever the password happens to be.
    """
    response = client.get("/api/status", headers={"Authorization": f"Bearer {API_KEY}"})
    assert response.status_code == 200

    reported = response.get_json()["database"]
    assert "@" not in reported
    assert "://" not in reported
    assert reported in ("sqlite", "postgresql", "postgres", "unknown")


def test_status_does_not_leak_the_api_key(client):
    response = client.get("/api/status", headers={"Authorization": f"Bearer {API_KEY}"})
    assert API_KEY not in _body(response)


def test_status_does_not_leak_the_linkedin_secret(client):
    response = client.get("/api/status", headers={"Authorization": f"Bearer {API_KEY}"})
    body = _body(response)
    assert LINKEDIN_SECRET not in body
    # It may report WHETHER LinkedIn is configured - just not the value.
    assert "linkedin_configured" in body


def test_status_does_not_leak_the_signing_key(client):
    response = client.get("/api/status", headers={"Authorization": f"Bearer {API_KEY}"})
    assert "signing-key-not-for-responses" not in _body(response)


def test_health_leaks_nothing(client):
    """/health is PUBLIC - it must be the most conservative endpoint we have."""
    body = _body(client.get("/health"))
    for secret in (DB_PASSWORD, API_KEY, LINKEDIN_SECRET, "signing-key-not-for-responses"):
        assert secret not in body
    assert "@" not in body


def test_error_responses_do_not_echo_the_provided_key(client):
    """A rejected key must not be reflected back, or logs of 401s become a
    list of attempted credentials."""
    response = client.get(
        "/api/status", headers={"Authorization": "Bearer some-guessed-key"}
    )
    assert response.status_code == 401
    assert "some-guessed-key" not in _body(response)
