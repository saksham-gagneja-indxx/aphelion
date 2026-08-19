"""Regression coverage for create_post's video_path resolution.

list_reels and draft_post (the MCP tools) only ever surface a reel's bare
filename, never its on-disk path - so a caller that echoes back exactly
what those tools showed it, as their descriptions instruct, could only ever
supply a bare filename. Before this was fixed, create_post required the
exact on-disk path and 400'd with "No reel found" on a bare filename,
which meant publish_reel/schedule_reel could never actually work for a
real MCP caller - only for tests or manual calls that happened to know the
storage layout.
"""

import os
import tempfile

import pytest

API_KEY = "test-key-create-post"


@pytest.fixture
def app(monkeypatch, tmp_path):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    monkeypatch.setenv("API_ACCESS_KEY", API_KEY)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("REELS_FOLDER", str(tmp_path / "reels"))
    monkeypatch.setenv("UPLOAD_FOLDER", str(tmp_path / "uploads"))

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
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    from backend.utils.database import get_session

    session = get_session()
    yield session
    session.close()


def auth():
    return {"Authorization": f"Bearer {API_KEY}"}


def make_user(db):
    from backend.models.user import User

    user = User(linkedin_sub="sub-create-post", full_name="Reel Owner", is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def put_reel_on_disk(app, user_id, filename, size=200 * 1024):
    from backend.utils.config import get_settings

    reel_dir = get_settings().reels_folder
    user_dir = os.path.join(reel_dir, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    full_path = os.path.join(user_dir, filename)
    with open(full_path, "wb") as f:
        f.write(b"\x00" * size)
    return full_path


def test_a_bare_filename_resolves_against_the_users_reel_directory(app, client, db):
    """Exactly what list_reels/draft_post hand a caller - and nothing more -
    must be enough to create a post."""
    user = make_user(db)
    put_reel_on_disk(app, user.id, "my_clip.mp4")

    response = client.post(
        "/api/posts",
        json={"user_id": user.id, "video_path": "my_clip.mp4", "caption": "hi"},
        headers=auth(),
    )

    assert response.status_code == 201
    body = response.get_json()
    # Stored as the real on-disk path, not the bare filename that was sent -
    # every downstream consumer (publish, schedule) expects a real path.
    assert body["video_path"].endswith(os.path.join(str(user.id), "my_clip.mp4"))


def test_a_full_path_still_works_as_before(app, client, db):
    user = make_user(db)
    full_path = put_reel_on_disk(app, user.id, "already_full_path.mp4")

    response = client.post(
        "/api/posts",
        json={"user_id": user.id, "video_path": full_path, "caption": "hi"},
        headers=auth(),
    )

    assert response.status_code == 201


def test_a_filename_that_does_not_exist_anywhere_still_400s(app, client, db):
    user = make_user(db)

    response = client.post(
        "/api/posts",
        json={"user_id": user.id, "video_path": "never_uploaded.mp4", "caption": "hi"},
        headers=auth(),
    )

    assert response.status_code == 400
    assert "No reel found" in response.get_json()["error"]


def test_a_bare_filename_does_not_resolve_against_another_users_directory(app, client, db):
    """The fallback must stay scoped to the requesting user's own directory -
    it must not let a filename guess reach across accounts."""
    from backend.models.user import User

    owner = make_user(db)
    other = User(linkedin_sub="sub-other", full_name="Someone Else", is_active=True)
    db.add(other)
    db.commit()
    db.refresh(other)

    put_reel_on_disk(app, owner.id, "shared_name.mp4")

    response = client.post(
        "/api/posts",
        json={"user_id": other.id, "video_path": "shared_name.mp4", "caption": "hi"},
        headers=auth(),
    )

    assert response.status_code == 400
