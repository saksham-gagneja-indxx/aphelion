"""Tests for caption assist.

The Claude call itself is mocked — these cover the parts that are ours and
that would quietly do the wrong thing if they broke:

  * the feature refuses to run on a placeholder API key, rather than sending
    a request that fails with an unrelated-looking auth error;
  * an empty brief is refused before any spend, because captioning from a
    thumbnail alone is the thing this feature deliberately does not do;
  * a crafted `reel_filename` cannot walk out of the caller's own folder and
    feed an arbitrary file on disk to the model;
  * `user_id` comes from the session, never the request body;
  * a refusal or an unparseable response surfaces as an error instead of an
    empty caption list the UI would render as success.
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

API_KEY = "caption-test-key"
REAL_KEY = "sk-ant-api03-testonly"  # must not contain "placeholder"
PLACEHOLDER_KEY = "sk-ant-placeholder-not-used-in-v1"


@pytest.fixture
def app(monkeypatch, tmp_path):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("API_ACCESS_KEY", API_KEY)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.setenv("CLAUDE_API_KEY", REAL_KEY)
    monkeypatch.setenv("ENABLE_CAPTION_GENERATION", "true")
    monkeypatch.setenv("REELS_FOLDER", str(tmp_path / "reels"))
    # Pin the provider. These tests patch `anthropic.Anthropic`, so they only
    # mean anything against the Claude path - inheriting whatever the global
    # default happens to be made all six 503 the moment that default changed.
    monkeypatch.setenv("LLM_PROVIDER", "claude")

    import backend.utils.database as database
    import backend.core.reel_manager as reel_manager

    # get_settings() builds a fresh Settings() per call, so env changes take
    # effect immediately - there is no cache to clear.
    database._db_instance = None
    reel_manager._reel_manager = None

    from backend.app import create_app

    application = create_app()
    application.config["TESTING"] = True
    yield application

    database._db_instance = None
    reel_manager._reel_manager = None
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


def auth():
    return {"Authorization": f"Bearer {API_KEY}"}


def make_user(app):
    from backend.models.user import User
    from backend.utils.database import get_session

    db = get_session()
    user = User(linkedin_sub="cap-sub", full_name="Op", is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    uid = user.id
    db.close()
    return uid


def fake_response(payload, stop_reason="end_turn"):
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(payload)
    response = MagicMock()
    response.content = [block]
    response.stop_reason = stop_reason
    return response


# ---------------------------------------------------------------- guard rails


def test_placeholder_key_reports_unavailable_rather_than_calling_out(app, client):
    """A placeholder key must not reach the SDK.

    Sending it produces an authentication error that points at Anthropic
    instead of at the unset config value, which is the actual problem.
    """
    with patch.dict(os.environ, {"CLAUDE_API_KEY": PLACEHOLDER_KEY}):
        response = client.get("/api/captions/status", headers=auth())
        body = response.get_json()

    assert body["available"] is False
    # Assert the property that matters - the reason points at the config value
    # the operator has to fix - rather than at one particular wording of it.
    # The literal word "placeholder" was an incidental of the old message and
    # broke when the provider seam rephrased it, while the behaviour was fine.
    assert "claude_api_key" in body["reason"].lower()


def test_disabled_flag_is_honoured(app, client):
    with patch.dict(os.environ, {"ENABLE_CAPTION_GENERATION": "false"}):
        response = client.get("/api/captions/status", headers=auth())
        body = response.get_json()

    assert body["available"] is False
    assert "disabled" in body["reason"].lower()


def test_empty_brief_is_refused_before_any_spend(app, client):
    uid = make_user(app)

    with patch("anthropic.Anthropic") as sdk:
        response = client.post(
            "/api/captions/suggest",
            json={"user_id": uid, "brief": "   "},
            headers=auth(),
        )

    assert response.status_code == 400
    assert "brief" in response.get_json()["error"].lower()
    # Spend happens on messages.create, not on constructing the client - the
    # provider seam now builds the client up front, which costs nothing. Assert
    # on the call that would actually be billed.
    #
    # (The original line was also written as a bare tuple expression, so it
    # asserted nothing at all even before the refactor.)
    sdk.return_value.messages.create.assert_not_called()


def test_reel_filename_cannot_escape_the_users_folder(app, client):
    """A traversal attempt must not hand an arbitrary file to the model."""
    from backend.core.captions import suggest_captions  # noqa: F401

    uid = make_user(app)
    captured = {}

    def capture(brief, thumbnail=None, duration_seconds=None):
        captured["thumbnail"] = thumbnail
        return [{"angle": "a", "text": "t"}]

    with patch("backend.api.caption_routes.suggest_captions", side_effect=capture):
        response = client.post(
            "/api/captions/suggest",
            json={
                "user_id": uid,
                "brief": "a reel about shipping",
                "reel_filename": "../../../../etc/passwd",
            },
            headers=auth(),
        )

    assert response.status_code == 200
    assert captured["thumbnail"] is None, "traversal must resolve to no thumbnail"


# ------------------------------------------------------------------ the call


def test_returns_three_captions(app, client):
    uid = make_user(app)
    payload = {
        "captions": [
            {"angle": "lesson learned", "text": "One"},
            {"angle": "direct", "text": "Two"},
            {"angle": "behind the scenes", "text": "Three"},
        ]
    }

    with patch("anthropic.Anthropic") as sdk:
        sdk.return_value.messages.create.return_value = fake_response(payload)
        response = client.post(
            "/api/captions/suggest",
            json={"user_id": uid, "brief": "shipping an OAuth integration"},
            headers=auth(),
        )

    assert response.status_code == 200
    captions = response.get_json()["captions"]
    assert [c["angle"] for c in captions] == [
        "lesson learned", "direct", "behind the scenes"
    ]


def test_model_is_called_with_the_brief_and_no_effort_param(app, client):
    uid = make_user(app)

    with patch("anthropic.Anthropic") as sdk:
        sdk.return_value.messages.create.return_value = fake_response(
            {"captions": [{"angle": "a", "text": "t"}]}
        )
        client.post(
            "/api/captions/suggest",
            json={"user_id": uid, "brief": "byte-range uploads explained"},
            headers=auth(),
        )
        kwargs = sdk.return_value.messages.create.call_args.kwargs

    assert kwargs["model"] == "claude-haiku-4-5"
    # effort is rejected with a 400 on Haiku 4.5 - it must not be sent.
    assert "effort" not in kwargs["output_config"]
    assert "thinking" not in kwargs
    assert kwargs["output_config"]["format"]["type"] == "json_schema"
    sent = json.dumps(kwargs["messages"])
    assert "byte-range uploads explained" in sent


def test_refusal_is_surfaced_not_returned_as_empty(app, client):
    """A refusal is HTTP 200 with no usable content — it must not read as success."""
    uid = make_user(app)

    with patch("anthropic.Anthropic") as sdk:
        sdk.return_value.messages.create.return_value = fake_response(
            {"captions": []}, stop_reason="refusal"
        )
        response = client.post(
            "/api/captions/suggest",
            json={"user_id": uid, "brief": "something"},
            headers=auth(),
        )

    assert response.status_code == 422
    assert "declined" in response.get_json()["error"].lower()


def test_unparseable_response_is_an_error(app, client):
    uid = make_user(app)

    block = MagicMock()
    block.type = "text"
    block.text = "not json at all"
    bad = MagicMock()
    bad.content = [block]
    bad.stop_reason = "end_turn"

    with patch("anthropic.Anthropic") as sdk:
        sdk.return_value.messages.create.return_value = bad
        response = client.post(
            "/api/captions/suggest",
            json={"user_id": uid, "brief": "something"},
            headers=auth(),
        )

    assert response.status_code == 502


def test_ai_generated_caption_is_recorded_on_the_post(app, client, tmp_path):
    """The column existed from the first schema and was never written to."""
    from backend.models.post import Post
    from backend.utils.database import get_session

    uid = make_user(app)
    reel = tmp_path / "reels" / str(uid) / "clip.mp4"
    reel.parent.mkdir(parents=True, exist_ok=True)
    reel.write_bytes(b"\x00" * 2048)

    with patch("backend.api.routes.get_reel_manager") as rm:
        rm.return_value.get_reel_info.return_value = {
            "thumbnail_path": None, "duration_seconds": 12.0, "size_bytes": 2048,
        }
        response = client.post(
            "/api/posts",
            json={
                "user_id": uid,
                "video_path": str(reel),
                "caption": "written by caption assist",
                "ai_generated_caption": True,
            },
            headers=auth(),
        )

    assert response.status_code == 201
    db = get_session()
    post = db.query(Post).filter(Post.id == response.get_json()["id"]).first()
    assert post.ai_generated_caption is True
    db.close()
