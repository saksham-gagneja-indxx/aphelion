"""The conversational composer — Claude drives a reel to a publishable draft.

The shape of the thing
----------------------

You drop in a reel and say what it is, or you say nothing and Claude asks. It
writes the caption, proposes a time, and fills in a draft. Then a human presses
the button.

That last sentence is the design, not a limitation of it.

Why Claude cannot publish
-------------------------

There is no `publish` tool here and there should never be one. The model's
input includes text that other people can influence — a brief, a filename,
later a transcript — and the output goes out under a real person's name on
their professional profile. An autonomous publish tool turns "summarise this
reel" into "post whatever the reel's description tells you to post", and there
is no prompt that reliably fixes that.

So every tool on this loop is a **pure state edit**. Nothing here writes to the
database, calls LinkedIn, or schedules a job. The endpoint returns a draft; the
existing create/schedule/publish routes still require an authenticated human
request. Claude proposes, the human disposes, and "boom" is still one click.

Why the loop runs server-side
-----------------------------

The tools mutate a small JSON draft and nothing else, so there is no reason to
round-trip each one to the browser. The server runs the tool loop to
completion and returns the finished draft plus whatever Claude wants to say.
The client stays dumb: it holds the transcript and renders.

Statelessness is deliberate. The conversation lives in the client and is posted
back each turn, which matches how the rest of this app works — a signed session
token and no server-side session store — and avoids a conversations table whose
retention policy nobody has thought about.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import pytz

from backend.ai.llm_provider import get_provider
from backend.utils.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger("social_media_automation.composer")

MODEL = "claude-opus-5"
EFFORT = "low"
MAX_TOKENS = 2048
MAX_TOOL_ROUNDS = 4
MAX_TURNS = 40
MAX_MESSAGE_CHARS = 4000

SYSTEM = """You help someone turn a short video (a "reel") into a LinkedIn post.

Your job each turn is to move the draft closer to ready and then get out of the
way. The person is busy — that is the whole reason you exist. Prefer doing over
asking.

The draft has three parts: which reel, the caption, and when to post. Use the
tools to fill them in.

How to behave:

- **If you have enough to act, act.** Someone who says "post the OAuth one
  tomorrow morning" has told you the reel, the timing and the topic. Choose the
  reel, write the caption, set the time, and show them the result. Do not ask
  permission to do the thing they just asked for.
- **If something is genuinely missing, ask for exactly one thing.** One short
  question, not a form. The commonest gap is what the reel is actually about,
  because you cannot watch it.
- **Never invent specifics.** You cannot see the video. Do not state numbers,
  names, companies, results or dates that the person has not told you. If the
  brief is thin, write something correspondingly general. A caption that
  invents a metric publishes a false claim under their name.
- **Captions**: first person, plain, specific. No LinkedIn cliches, no
  engagement bait, no hashtag walls (two at most, and only if they are terms
  someone would actually follow). The first line has to earn the click —
  LinkedIn truncates around 140 characters. Under 1200 characters.
- **Timing**: if they ask for a specific time, use it. If they say "now", set
  it to now. If they have not said, and everything else is ready, propose a
  sensible weekday morning slot and say that you have — do not make them think
  about it.

You cannot publish anything, and you should not imply that you can. When the
draft is ready, say so plainly and tell them the button is theirs to press."""

TOOLS = [
    {
        "name": "choose_reel",
        "description": (
            "Select which already-uploaded reel this post is about. Use the exact "
            "filename from the list of available reels in the conversation. Call "
            "this as soon as it is clear which one they mean — including when "
            "they describe it rather than name it, and when there is only one."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Exact filename of one of the available reels.",
                }
            },
            "required": ["filename"],
            "additionalProperties": False,
        },
    },
    {
        "name": "set_caption",
        "description": (
            "Write or rewrite the post caption. Call this whenever you have "
            "enough to write something worth reading, rather than describing "
            "what you would write."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The caption itself."},
                "angle": {
                    "type": "string",
                    "description": "Two or three words for the approach taken, e.g. 'lesson learned'.",
                },
            },
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "set_schedule",
        "description": (
            "Propose when the post should go out. Either 'now', or a local "
            "datetime in the person's own timezone. This only fills in the "
            "draft — it does not schedule or publish anything."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "when": {
                    "type": "string",
                    "description": (
                        "'now', or a local datetime as YYYY-MM-DDTHH:MM in the "
                        "person's timezone. Never a past time."
                    ),
                }
            },
            "required": ["when"],
            "additionalProperties": False,
        },
    },
]


class ComposerError(Exception):
    """Something the caller should show the user verbatim."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status


def empty_draft() -> dict:
    return {"reel_filename": None, "caption": None, "angle": None, "when": None}


def _normalise_when(raw: str, tz_name: str) -> Optional[str]:
    """Validate a proposed time; return a canonical value or None.

    Returns 'now', or a naive local ISO string — the same shape the schedule
    endpoint already accepts from the date picker, so the handoff needs no
    translation. A past or unparseable time is rejected rather than passed on:
    the schedule endpoint would refuse it anyway, and refusing here means
    Claude is told about it while it can still fix it.
    """
    value = (raw or "").strip()
    if not value:
        return None
    if value.lower() in {"now", "immediately", "asap"}:
        return "now"

    try:
        tz = pytz.timezone(tz_name)
    except Exception:
        tz = pytz.timezone(get_settings().timezone)

    parsed = None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            parsed = datetime.strptime(value, fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(value).replace(tzinfo=None)
        except ValueError:
            return None

    if tz.localize(parsed) <= datetime.now(tz):
        return None
    return parsed.strftime("%Y-%m-%dT%H:%M")


def _apply_tool(name: str, args: dict, draft: dict, reels: List[str], tz_name: str) -> str:
    """Run one tool against the draft. Returns the result text for the model.

    Every branch is a dictionary write. Nothing here touches the database, the
    scheduler, or LinkedIn — see the module docstring for why that is a rule
    rather than a coincidence.
    """
    if name == "choose_reel":
        wanted = (args.get("filename") or "").strip()
        if wanted not in reels:
            # Handing back the real list beats a bare error: the next turn
            # usually picks correctly instead of guessing again.
            return (
                f"No reel named {wanted!r}. Available: "
                + (", ".join(reels) if reels else "(none uploaded yet)")
            )
        draft["reel_filename"] = wanted
        return f"Selected {wanted}."

    if name == "set_caption":
        text = (args.get("text") or "").strip()
        if not text:
            return "Caption was empty; nothing set."
        draft["caption"] = text[:3000]
        draft["angle"] = (args.get("angle") or "").strip() or None
        return f"Caption set ({len(draft['caption'])} characters)."

    if name == "set_schedule":
        when = _normalise_when(args.get("when", ""), tz_name)
        if when is None:
            return (
                "That time is in the past or could not be read. Use 'now', or "
                "YYYY-MM-DDTHH:MM in the future."
            )
        draft["when"] = when
        return "Will post immediately." if when == "now" else f"Scheduled for {when}."

    return f"Unknown tool {name!r}."


def _context_block(reels: List[dict], tz_name: str) -> str:
    """What Claude needs to know that is not in the conversation."""
    now = datetime.now(pytz.timezone(tz_name))
    lines = [
        f"Current local time: {now.strftime('%A %d %B %Y, %H:%M')} ({tz_name}).",
        "",
        "Reels already uploaded and available to post:",
    ]
    if not reels:
        lines.append(
            "  (none yet — they need to upload a video before there is anything "
            "to post; say so plainly)"
        )
    else:
        for r in reels[:25]:
            dur = r.get("duration_seconds")
            dur_text = f", {dur:.0f}s" if isinstance(dur, (int, float)) and dur else ""
            lines.append(f"  - {r.get('filename')}{dur_text}")
    return "\n".join(lines)


def run_turn(
    messages: List[dict],
    draft: Optional[dict],
    reels: List[dict],
    tz_name: str,
    thumbnail: Optional[Path] = None,
) -> dict:
    """One exchange. Returns {reply, draft, ready}.

    `messages` is the whole conversation so far, oldest first, each
    {role: 'user'|'assistant', content: str}.

    Delegates to the configured LLM provider (Claude or Gemini).
    """
    if not messages:
        raise ComposerError("Nothing to respond to.", status=400)
    if len(messages) > MAX_TURNS:
        raise ComposerError(
            "This conversation has gone on long enough that it is cheaper to "
            "start a fresh one. Post what you have, or begin again.",
            status=400,
        )
    for m in messages:
        if len(m.get("content") or "") > MAX_MESSAGE_CHARS:
            raise ComposerError("That message is too long.", status=400)

    provider = get_provider()
    reason = provider.unavailable_reason()
    if reason:
        raise ComposerError(reason, status=503)

    try:
        return provider.run_composer_turn(messages, draft, reels, tz_name, thumbnail)
    except ComposerError:
        raise
    except Exception as e:
        logger.error(f"Composer error: {str(e)}")
        raise ComposerError(
            f"Composer failed: {str(e)[:100]}", status=502
        )
