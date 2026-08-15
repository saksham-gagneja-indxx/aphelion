"""Tests for the administrative CLI.

The dotenv rewriting is what these mostly cover. That file is hand-maintained
and holds every credential the app has, so an edit that drops a comment, an
unrelated key, or the last line without a newline would be a genuinely
expensive mistake - and it is the kind of thing that only shows up later.
"""

import os
import tempfile
from pathlib import Path

import pytest

from backend.admin_cli import _set_env_key, main


@pytest.fixture
def env_file(tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        "# Header comment\n"
        "FLASK_ENV=development\n"
        "\n"
        "# ==== SECTION ====\n"
        "SECRET_KEY=original-secret\n"
        "ADMIN_LINKEDIN_SUBS=\n"
        "LAST_KEY=keep-me\n",
        encoding="utf-8",
    )
    return path


def test_replaces_an_existing_key_in_place(env_file):
    _set_env_key(env_file, "SECRET_KEY", "rotated")
    text = env_file.read_text(encoding="utf-8")

    assert "SECRET_KEY=rotated\n" in text
    assert "original-secret" not in text
    # The line is rewritten where it was, not appended.
    lines = text.splitlines()
    assert lines.index("SECRET_KEY=rotated") == 4


def test_preserves_comments_and_unrelated_keys(env_file):
    _set_env_key(env_file, "ADMIN_LINKEDIN_SUBS", "abc123")
    text = env_file.read_text(encoding="utf-8")

    assert "# Header comment" in text
    assert "# ==== SECTION ====" in text
    assert "FLASK_ENV=development" in text
    assert "LAST_KEY=keep-me" in text
    assert "SECRET_KEY=original-secret" in text


def test_appends_a_key_that_is_absent(env_file):
    _set_env_key(env_file, "BRAND_NEW_KEY", "value")
    assert env_file.read_text(encoding="utf-8").endswith("BRAND_NEW_KEY=value\n")


def test_rewrites_a_commented_out_key_rather_than_appending(env_file):
    """A commented key that is also appended below reads as two settings."""
    env_file.write_text("# ADMIN_LINKEDIN_SUBS=old\nOTHER=1\n", encoding="utf-8")
    _set_env_key(env_file, "ADMIN_LINKEDIN_SUBS", "new")

    text = env_file.read_text(encoding="utf-8")
    assert text.count("ADMIN_LINKEDIN_SUBS") == 1
    assert "ADMIN_LINKEDIN_SUBS=new" in text
    assert "# ADMIN_LINKEDIN_SUBS=old" not in text


def test_survives_a_file_with_no_trailing_newline(tmp_path):
    path = tmp_path / ".env"
    path.write_text("A=1\nB=2", encoding="utf-8")  # no final newline
    _set_env_key(path, "C", "3")

    # Without the guard this produces "B=2C=3" and silently destroys B.
    assert path.read_text(encoding="utf-8") == "A=1\nB=2\nC=3\n"


def test_key_match_is_anchored_not_a_substring(tmp_path):
    """SECRET_KEY must not be matched when setting KEY."""
    path = tmp_path / ".env"
    path.write_text("SECRET_KEY=untouched\nJWT_SECRET=also-untouched\n", encoding="utf-8")
    _set_env_key(path, "KEY", "mine")

    text = path.read_text(encoding="utf-8")
    assert "SECRET_KEY=untouched" in text
    assert "JWT_SECRET=also-untouched" in text
    assert "KEY=mine\n" in text


# ----------------------------------------------------------- command behaviour


@pytest.fixture
def db(monkeypatch):
    """A throwaway database with the CLI pointed at it."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")

    import backend.utils.database as database

    database._db_instance = None
    database.init_db()

    yield database

    database._db_instance = None
    try:
        os.unlink(path)
    except OSError:
        pass


def _make_user(db, **kwargs):
    from backend.models.user import User

    session = db.get_session()
    try:
        user = User(**kwargs)
        session.add(user)
        session.commit()
        session.refresh(user)
        session.expunge(user)
        return user
    finally:
        session.close()


def test_promote_makes_an_account_an_active_admin(db, capsys):
    from backend.models.user import User

    user = _make_user(
        db, linkedin_sub="sub-x", full_name="Ops", email="ops@test", role="operator",
        is_active=False,
    )

    assert main(["promote", str(user.id)]) == 0

    session = db.get_session()
    try:
        refreshed = session.query(User).filter(User.id == user.id).first()
        assert refreshed.role == User.ROLE_ADMIN
        assert refreshed.is_active is True
    finally:
        session.close()


def test_demote_refuses_to_remove_the_last_admin(db, capsys):
    """Otherwise the tool ends up with nobody able to administer it."""
    from backend.models.user import User

    admin = _make_user(
        db, linkedin_sub="sub-a", full_name="Only Admin", email="a@test",
        role="admin", is_active=True,
    )

    assert main(["demote", str(admin.id)]) == 1
    assert "last active administrator" in capsys.readouterr().err

    session = db.get_session()
    try:
        assert session.query(User).filter(User.id == admin.id).first().role == "admin"
    finally:
        session.close()


def test_pin_writes_admin_subs_to_the_env_file(db, env_file, monkeypatch, capsys):
    import backend.admin_cli as cli

    monkeypatch.setattr(cli, "ENV_PATH", env_file)
    _make_user(
        db, linkedin_sub="sub-admin-1", full_name="Boss", email="boss@test",
        role="admin", is_active=True,
    )
    _make_user(
        db, linkedin_sub="sub-operator", full_name="Not Boss", email="no@test",
        role="operator", is_active=True,
    )

    assert cli.main(["pin"]) == 0

    text = env_file.read_text(encoding="utf-8")
    assert "ADMIN_LINKEDIN_SUBS=sub-admin-1" in text
    # Pinning an operator would hand them the admin role on next sign-in.
    assert "sub-operator" not in text


def test_pin_skips_an_account_that_has_never_signed_in(db, env_file, monkeypatch, capsys):
    """Without a sub there is nothing to pin, and a blank entry would be wrong."""
    import backend.admin_cli as cli

    monkeypatch.setattr(cli, "ENV_PATH", env_file)
    _make_user(
        db, linkedin_sub=None, full_name="Seeded", email="seed@test",
        role="admin", is_active=True,
    )

    assert cli.main(["pin"]) == 1
    assert "ADMIN_LINKEDIN_SUBS=\n" in env_file.read_text(encoding="utf-8")


def test_destructive_commands_require_explicit_confirmation(db, env_file, monkeypatch):
    import backend.admin_cli as cli
    from backend.models.user import User

    monkeypatch.setattr(cli, "ENV_PATH", env_file)
    _make_user(db, linkedin_sub="s", full_name="X", email="x@test", role="admin",
               is_active=True)
    before = env_file.read_text(encoding="utf-8")

    assert cli.main(["reset-users"]) == 1
    assert cli.main(["sign-out-all"]) == 1

    session = db.get_session()
    try:
        assert session.query(User).count() == 1
    finally:
        session.close()
    assert env_file.read_text(encoding="utf-8") == before


def test_sign_out_all_rotates_the_signing_key(db, env_file, monkeypatch, capsys):
    """Rotating SECRET_KEY is what actually invalidates issued tokens."""
    import backend.admin_cli as cli

    monkeypatch.setattr(cli, "ENV_PATH", env_file)

    assert cli.main(["sign-out-all", "--yes"]) == 0

    text = env_file.read_text(encoding="utf-8")
    assert "SECRET_KEY=original-secret" not in text
    assert "SECRET_KEY=" in text
    assert Path(str(env_file) + ".bak").exists()
