"""The conversational composer.

Claude is mocked throughout. What is under test is the harness around it, and
above all the boundary: **the model can fill in a draft and cannot publish**.

The first test in this file is the one that matters. A composer with a publish
tool would turn "summarise this reel" into "post whatever the reel description
tells you to post", on someone's real professional profile, and no amount of
prompt wording fixes that reliably. So the absence of the tool is asserted
directly rather than trusted to review.
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import pytz

API_KEY = "composer-test-key"
REAL_KEY = "sk-ant-api03-testonly"  # must not contain "placeholder"
TZ = "Asia/Kolkata"


# --------------------------------------------------------------- the boundary


def test_the_model_is_given_no_tool_that_can_publish():
    """The load-bearing assertion of this feature.

    If someone adds a publish/schedule-for-real tool later, this fails and they
    have to come and read why it is not allowed.
    """
    from backend.core.composer import TOOLS

    names = {t["name"] for t in TOOLS}
    assert names == {"choose_reel", "set_caption", "set_schedule"}

    forbidden = ("publish", "post", "send", "delete", "share")
    for tool in TOOLS:
        blob = json.dumps(tool).lower()
        for word in forbidden:
            assert f'"name": "{word}' not in blob, f"{tool['name']} looks like an action tool"


def test_applying_every_tool_touches_nothing_but_the_draft():
    """Tools are pure state edits — no database, no scheduler, no network."""
    from backend.core import composer

    draft = composer.empty_draft()
    future = (datetime.now(pytz.timezone(TZ)) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")

    composer._apply_tool("choose_reel", {"filename": "a.mp4"}, draft, ["a.mp4"], TZ)
    composer._apply_tool("set_caption", {"text": "hello", "angle": "direct"}, draft, [], TZ)
    composer._apply_tool("set_schedule", {"when": future}, draft, [], TZ)

    assert draft == {
        "reel_filename": "a.mp4",
        "caption": "hello",
        "angle": "direct",
        "when": future,
    }


# ------------------------------------------------------------- tool behaviour


def test_choosing_a_reel_the_user_does_not_own_is_refused_with_the_real_list():
    """Handing back the options beats a bare error — the next turn gets it right."""
    from backend.core import composer

    draft = composer.empty_draft()
    out = composer._apply_tool(
        "choose_reel", {"filename": "../../someone-elses.mp4"}, draft, ["mine.mp4"], TZ
    )

    assert draft["reel_filename"] is None
    assert "mine.mp4" in out


def test_a_past_time_is_rejected_rather_than_passed_on():
    """The schedule endpoint would refuse it anyway; refusing here lets Claude fix it."""
    from backend.core import composer

    draft = composer.empty_draft()
    past = (datetime.now(pytz.timezone(TZ)) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
    out = composer._apply_tool("set_schedule", {"when": past}, draft, [], TZ)

    assert draft["when"] is None
    assert "past" in out.lower()


def test_now_is_accepted_and_normalised():
    from backend.core import composer

    draft = composer.empty_draft()
    for phrasing in ("now", "NOW", "immediately", "asap"):
        draft = composer.empty_draft()
        composer._apply_tool("set_schedule", {"when": phrasing}, draft, [], TZ)
        assert draft["when"] == "now", phrasing


def test_unparseable_time_does_not_corrupt_the_draft():
    from backend.core import composer

    draft = composer.empty_draft()
    composer._apply_tool("set_schedule", {"when": "next tuesday-ish"}, draft, [], TZ)
    assert draft["when"] is None


def test_the_scheduled_shape_matches_what_the_schedule_endpoint_expects():
    """A naive local ISO string — the same thing the date picker produces.

    If these drift, the handoff from composer to schedule silently breaks.
    """
    from backend.core import composer

    draft = composer.empty_draft()
    future = (datetime.now(pytz.timezone(TZ)) + timedelta(days=2)).replace(microsecond=0)
    composer._apply_tool(
        "set_schedule", {"when": future.strftime("%Y-%m-%dT%H:%M")}, draft, [], TZ
    )
    # Parses with the same format the frontend datetime-local input emits.
    datetime.strptime(draft["when"], "%Y-%m-%dT%H:%M")


# ------------------------------------------------------------------- the loop


def reply(text="", tools=None, stop="end_turn"):
    blocks = []
    if text:
        b = MagicMock()
        b.type = "text"
        b.text = text
        blocks.append(b)
    for name, args in (tools or []):
        b = MagicMock()
        b.type = "tool_use"
        b.name = name
        b.input = args
        b.id = f"toolu_{name}"
        blocks.append(b)
    r = MagicMock()
    r.content = blocks
    r.stop_reason = stop
    return r


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("CLAUDE_API_KEY", REAL_KEY)
    monkeypatch.setenv("ENABLE_CAPTION_GENERATION", "true")
    # See the note in test_captions.py: these tests patch the Anthropic SDK, so
    # the provider has to be pinned rather than inherited from the default.
    monkeypatch.setenv("LLM_PROVIDER", "claude")


def test_a_turn_that_fills_everything_reports_ready(configured):
    from backend.core.composer import run_turn

    future = (datetime.now(pytz.timezone(TZ)) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")

    with patch("anthropic.Anthropic") as sdk:
        sdk.return_value.messages.create.side_effect = [
            reply(tools=[
                ("choose_reel", {"filename": "oauth.mp4"}),
                ("set_caption", {"text": "Shipped OAuth this week.", "angle": "direct"}),
                ("set_schedule", {"when": future}),
            ]),
            reply(text="Draft is ready — the button is yours."),
        ]
        out = run_turn(
            messages=[{"role": "user", "content": "post the oauth one tomorrow 9am"}],
            draft=None,
            reels=[{"filename": "oauth.mp4", "duration_seconds": 28}],
            tz_name=TZ,
        )

    assert out["ready"] is True
    assert out["draft"]["reel_filename"] == "oauth.mp4"
    assert out["draft"]["caption"].startswith("Shipped OAuth")
    assert "button is yours" in out["reply"]


def test_a_turn_that_only_asks_a_question_is_not_ready(configured):
    from backend.core.composer import run_turn

    with patch("anthropic.Anthropic") as sdk:
        sdk.return_value.messages.create.return_value = reply(
            text="What is the reel about?"
        )
        out = run_turn(
            messages=[{"role": "user", "content": "post something"}],
            draft=None,
            reels=[{"filename": "a.mp4"}],
            tz_name=TZ,
        )

    assert out["ready"] is False
    assert out["draft"]["caption"] is None
    assert "about" in out["reply"]


def test_available_reels_are_put_in_front_of_the_model(configured):
    """It cannot choose from a list it was never shown."""
    from backend.core.composer import run_turn

    with patch("anthropic.Anthropic") as sdk:
        sdk.return_value.messages.create.return_value = reply(text="ok")
        run_turn(
            messages=[{"role": "user", "content": "hi"}],
            draft=None,
            reels=[{"filename": "byte-range.mp4", "duration_seconds": 41}],
            tz_name=TZ,
        )
        sent = json.dumps(sdk.return_value.messages.create.call_args.kwargs["messages"])

    assert "byte-range.mp4" in sent
    assert "Asia/Kolkata" in sent, "the model needs the timezone to read 'tomorrow 9am'"


def test_a_runaway_tool_loop_is_cut_off_but_keeps_the_partial_draft(configured):
    from backend.core.composer import run_turn

    with patch("anthropic.Anthropic") as sdk:
        # Never stops calling tools.
        sdk.return_value.messages.create.return_value = reply(
            tools=[("set_caption", {"text": "again and again"})]
        )
        out = run_turn(
            messages=[{"role": "user", "content": "go"}],
            draft=None,
            reels=[{"filename": "a.mp4"}],
            tz_name=TZ,
        )

    assert out["draft"]["caption"] == "again and again", "partial work must survive"
    assert out["ready"] is False
    assert sdk.return_value.messages.create.call_count <= 4


def test_a_refusal_surfaces_as_an_error(configured):
    from backend.core.composer import ComposerError, run_turn

    with patch("anthropic.Anthropic") as sdk:
        sdk.return_value.messages.create.return_value = reply(text="", stop="refusal")
        with pytest.raises(ComposerError) as e:
            run_turn(
                messages=[{"role": "user", "content": "x"}],
                draft=None,
                reels=[],
                tz_name=TZ,
            )
    assert e.value.status == 422


def test_an_overlong_conversation_is_refused_before_any_spend(configured):
    from backend.core.composer import ComposerError, run_turn

    with patch("anthropic.Anthropic") as sdk:
        with pytest.raises(ComposerError) as e:
            run_turn(
                messages=[{"role": "user", "content": "x"}] * 100,
                draft=None,
                reels=[],
                tz_name=TZ,
            )
        sdk.assert_not_called()
    assert e.value.status == 400


def test_a_placeholder_key_stops_the_turn_before_the_sdk(monkeypatch):
    from backend.core.composer import ComposerError, run_turn

    monkeypatch.setenv("CLAUDE_API_KEY", "sk-ant-placeholder-not-used-in-v1")
    with patch("anthropic.Anthropic") as sdk:
        with pytest.raises(ComposerError) as e:
            run_turn(
                messages=[{"role": "user", "content": "x"}],
                draft=None,
                reels=[],
                tz_name=TZ,
            )
        sdk.assert_not_called()
    assert e.value.status == 503


# ------------------------------------------------------------------- the route


@pytest.fixture
def app(monkeypatch, tmp_path):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("API_ACCESS_KEY", API_KEY)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.setenv("CLAUDE_API_KEY", REAL_KEY)
    monkeypatch.setenv("ENABLE_CAPTION_GENERATION", "true")
    monkeypatch.setenv("REELS_FOLDER", str(tmp_path / "reels"))
    # See the note in test_captions.py: these patch the Anthropic SDK, so the
    # provider has to be pinned rather than inherited.
    monkeypatch.setenv("LLM_PROVIDER", "claude")

    import backend.core.reel_manager as reel_manager
    import backend.utils.database as database
    from backend.core.storage import reset_media_store

    database._db_instance = None
    reel_manager._reel_manager = None
    reset_media_store()

    from backend.app import create_app

    application = create_app()
    application.config["TESTING"] = True
    yield application

    database._db_instance = None
    reel_manager._reel_manager = None
    reset_media_store()
    try:
        os.unlink(path)
    except OSError:
        pass


def test_the_blueprint_exposes_no_publish_route(app):
    """Belt and braces on the boundary, from the routing table this time."""
    composer_rules = [
        str(r) for r in app.url_map.iter_rules() if "/api/composer" in str(r)
    ]
    assert composer_rules, "composer routes should be registered"
    for rule in composer_rules:
        assert "publish" not in rule and "post" not in rule.replace("composer", "")


def test_turn_requires_messages(app):
    client = app.test_client()
    res = client.post(
        "/api/composer/turn",
        json={"user_id": 1},
        headers={"Authorization": f"Bearer {API_KEY}"},
    )
    assert res.status_code == 400
