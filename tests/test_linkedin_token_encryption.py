"""LinkedIn access/refresh tokens must never sit in the database as plaintext.

These carry real publish rights on a real member's LinkedIn account - more
sensitive than the per-user app client secret next to them, which was already
encrypted. store_linkedin_token()/clear_linkedin_token() and every other call
site keep using the plain `user.linkedin_access_token` attribute unchanged;
what changed is only what's behind it (see backend/models/user.py).
"""

import os
import tempfile

import pytest


@pytest.fixture
def app(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("API_ACCESS_KEY", "token-encryption-test-key")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")

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
def db(app):
    from backend.utils.database import get_session

    session = get_session()
    yield session
    session.close()


@pytest.fixture
def client(app):
    return app.test_client()


def test_access_and_refresh_tokens_are_encrypted_at_rest(db):
    from backend.models.user import User

    user = User(linkedin_sub="sub-enc-1", full_name="Enc Test", is_active=True)
    user.store_linkedin_token(
        access_token="real-access-token-value",
        person_urn="urn:li:person:enc1",
        refresh_token="real-refresh-token-value",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # The property still round-trips the plaintext transparently...
    assert user.linkedin_access_token == "real-access-token-value"
    assert user.linkedin_refresh_token == "real-refresh-token-value"

    # ...but what's actually on the row is ciphertext, not the plaintext, and
    # the legacy plaintext columns are empty.
    assert user.linkedin_access_token_encrypted is not None
    assert "real-access-token-value" not in user.linkedin_access_token_encrypted
    assert user.linkedin_refresh_token_encrypted is not None
    assert "real-refresh-token-value" not in user.linkedin_refresh_token_encrypted
    assert user._linkedin_access_token_legacy is None
    assert user._linkedin_refresh_token_legacy is None


def test_a_fresh_read_from_the_database_still_decrypts(db):
    from backend.models.user import User

    user = User(linkedin_sub="sub-enc-2", full_name="Enc Test 2", is_active=True)
    user.store_linkedin_token(access_token="tok-abc", person_urn="urn:li:person:enc2")
    db.add(user)
    db.commit()
    user_id = user.id
    db.expire_all()

    reloaded = db.query(User).filter(User.id == user_id).first()
    assert reloaded.linkedin_access_token == "tok-abc"


def test_clearing_the_token_blanks_both_encrypted_and_legacy_columns(db):
    from backend.models.user import User

    user = User(linkedin_sub="sub-enc-3", full_name="Enc Test 3", is_active=True)
    user.store_linkedin_token(access_token="tok-to-clear", person_urn="urn:li:person:enc3")
    db.add(user)
    db.commit()

    user.clear_linkedin_token()
    db.commit()

    assert user.linkedin_access_token is None
    assert user.linkedin_access_token_encrypted is None


def test_a_legacy_plaintext_row_still_reads_correctly_before_migration(db):
    """Simulates a row as it existed before this change - plaintext in the
    legacy column, nothing in the new encrypted one - to prove existing
    production rows aren't silently orphaned mid-rollout."""
    from backend.models.user import User

    user = User(linkedin_sub="sub-legacy-1", full_name="Legacy", is_active=True)
    db.add(user)
    db.commit()

    # Bypass the property - this is what a pre-migration row looks like.
    user._linkedin_access_token_legacy = "old-plaintext-token"
    db.commit()

    assert user.linkedin_access_token == "old-plaintext-token"
    assert user.linkedin_access_token_encrypted is None


def test_writing_through_the_property_self_heals_a_legacy_row(db):
    from backend.models.user import User

    user = User(linkedin_sub="sub-legacy-2", full_name="Legacy 2", is_active=True)
    user._linkedin_access_token_legacy = "old-plaintext-token"
    db.add(user)
    db.commit()

    # Any normal write path (re-sign-in, refresh) goes through the property.
    user.linkedin_access_token = "new-token"
    db.commit()

    assert user.linkedin_access_token == "new-token"
    assert user.linkedin_access_token_encrypted is not None
    assert user._linkedin_access_token_legacy is None


def test_admin_cli_migrates_every_legacy_row_immediately(db):
    from backend.admin_cli import cmd_encrypt_linkedin_tokens
    from backend.models.user import User

    migrated = User(linkedin_sub="sub-cli-1", full_name="CLI 1", is_active=True)
    migrated._linkedin_access_token_legacy = "cli-plaintext-access"
    migrated._linkedin_refresh_token_legacy = "cli-plaintext-refresh"

    already_encrypted = User(linkedin_sub="sub-cli-2", full_name="CLI 2", is_active=True)
    already_encrypted.linkedin_access_token = "already-fine"

    untouched = User(linkedin_sub="sub-cli-3", full_name="CLI 3", is_active=True)

    db.add_all([migrated, already_encrypted, untouched])
    db.commit()

    rc = cmd_encrypt_linkedin_tokens(argparse_namespace())
    assert rc == 0

    db.expire_all()
    reloaded = db.query(User).filter(User.linkedin_sub == "sub-cli-1").first()
    assert reloaded.linkedin_access_token == "cli-plaintext-access"
    assert reloaded.linkedin_refresh_token == "cli-plaintext-refresh"
    assert reloaded._linkedin_access_token_legacy is None
    assert reloaded._linkedin_refresh_token_legacy is None


def argparse_namespace():
    import argparse

    return argparse.Namespace()


def test_admin_route_requires_a_bearer_key(client, db):
    from backend.models.user import User

    user = User(linkedin_sub="sub-route-noauth", full_name="Route", is_active=True)
    user._linkedin_access_token_legacy = "plaintext"
    db.add(user)
    db.commit()

    res = client.post("/api/admin/encrypt-linkedin-tokens")
    assert res.status_code == 401


def test_admin_route_migrates_and_reports_a_count(client, db):
    from backend.models.user import User

    user = User(linkedin_sub="sub-route-1", full_name="Route 1", is_active=True)
    user._linkedin_access_token_legacy = "route-plaintext"
    db.add(user)
    db.commit()

    res = client.post(
        "/api/admin/encrypt-linkedin-tokens",
        headers={"Authorization": "Bearer token-encryption-test-key"},
    )
    assert res.status_code == 200
    assert res.get_json()["migrated"] == 1

    db.expire_all()
    reloaded = db.query(User).filter(User.linkedin_sub == "sub-route-1").first()
    assert reloaded.linkedin_access_token == "route-plaintext"
    assert reloaded._linkedin_access_token_legacy is None

    # Idempotent - a second call finds nothing left to do.
    res2 = client.post(
        "/api/admin/encrypt-linkedin-tokens",
        headers={"Authorization": "Bearer token-encryption-test-key"},
    )
    assert res2.get_json()["migrated"] == 0
