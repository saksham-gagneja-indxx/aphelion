"""Caption assist — three drafted LinkedIn captions for a reel.

What this is not: it does not watch the video. The server knows a filename, a
duration, a size and one thumbnail frame, and a single frame of a talking-head
reel is a person at a desk. Captioning from that alone produces confident,
generic filler, which is worse than nothing in a tool whose whole pitch is
professional publishing.

So the operator's one-line brief is the source of truth and the thumbnail is
supporting context only. The model is told, explicitly, not to invent
specifics the brief does not contain — a caption that states a number nobody
gave it is a caption that publishes a false claim under someone's name.

Real video understanding needs audio transcription. ffmpeg is already in the
image, but no transcription model is; that is a separate dependency, cost and
latency decision, not something to smuggle in here.
"""

import base64
import json
from pathlib import Path
from typing import List, Optional

from backend.utils.config import get_settings, is_placeholder
from backend.utils.logger import get_logger

logger = get_logger("social_media_automation.captions")

# Haiku 4.5, chosen for cost: roughly a fifth of Opus per suggestion, and a
# caption is short enough that the quality gap is acceptable. Note this model
# does NOT accept output_config.effort - passing it returns a 400 - and it has
# no adaptive thinking, so `thinking` is omitted entirely below.
MODEL = "claude-haiku-4-5"

# Three captions plus their angles fit comfortably; the cap is a backstop
# against a runaway response, not a length target.
MAX_TOKENS = 2048

SYSTEM = """You write LinkedIn captions for short video posts (reels).

You are given a one-line brief from the person posting, and sometimes a single
thumbnail frame from the video. Return three captions, each taking a different
angle on the same material.

Ground rules:

- The brief is the only source of fact. The thumbnail is weak evidence of
  setting and tone — never of content. Do not state numbers, names, company
  names, results, dates, or claims that the brief does not contain. If the
  brief is thin, write something correspondingly general rather than inventing
  detail to fill space.
- Write in the poster's voice as the brief suggests it: first person, plain,
  specific. No LinkedIn cliches — no "I'm humbled to announce", no "Let that
  sink in", no one-sentence-per-line cadence, no engagement bait.
- The first line has to earn the click; LinkedIn truncates around 140
  characters behind a "see more".
- No hashtag walls. At most two, only where they are genuinely the terms
  someone would follow, and only if the brief suggests a topic worth tagging.
- Emoji sparingly or not at all.
- Keep each caption under 1200 characters.

Give each caption a two- or three-word `angle` label describing its approach
(for example "lesson learned", "direct", "behind the scenes") so the poster can
tell them apart at a glance."""

# minItems/maxItems are not supported by structured outputs, so "exactly three"
# is asked for in the prompt and enforced below on the way out.
CAPTION_SCHEMA = {
    "type": "object",
    "properties": {
        "captions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "angle": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["angle", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["captions"],
    "additionalProperties": False,
}


class CaptionError(Exception):
    """Something went wrong that the caller should show the user verbatim."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status


def is_configured() -> bool:
    """True when captions can actually be generated.

    Both switches have to be on: the feature flag, and a real API key. The
    key defaults to a placeholder string in `.env.example` and `render.yaml`,
    which is not the same as being unset.
    """
    settings = get_settings()
    return bool(settings.enable_caption_generation) and not is_placeholder(
        settings.claude_api_key
    )


def unavailable_reason() -> Optional[str]:
    """Why captions are off, phrased for the person who has to fix it."""
    settings = get_settings()
    if not settings.enable_caption_generation:
        return "Caption assist is disabled (ENABLE_CAPTION_GENERATION is false)."
    if is_placeholder(settings.claude_api_key):
        return (
            "Caption assist needs an Anthropic API key. CLAUDE_API_KEY is still "
            "set to its placeholder value."
        )
    return None


def _thumbnail_block(thumbnail: Optional[Path]) -> Optional[dict]:
    """A base64 image block for the reel's thumbnail, if there is one."""
    if thumbnail is None:
        return None
    try:
        if not thumbnail.is_file():
            return None
        data = thumbnail.read_bytes()
    except OSError as e:
        logger.warning(f"Could not read thumbnail {thumbnail}: {e}")
        return None

    # Thumbnails are generated as JPEG by the reel manager.
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": base64.standard_b64encode(data).decode("ascii"),
        },
    }


def suggest_captions(
    brief: str,
    thumbnail: Optional[Path] = None,
    duration_seconds: Optional[float] = None,
) -> List[dict]:
    """Three caption options for one reel.

    Returns a list of {"angle": str, "text": str}. Raises CaptionError with a
    message fit to show the user.
    """
    brief = (brief or "").strip()
    if not brief:
        raise CaptionError(
            "Describe the reel in a sentence first — captions are written from "
            "your brief, not from the video.",
            status=400,
        )

    reason = unavailable_reason()
    if reason:
        raise CaptionError(reason, status=503)

    try:
        import anthropic
    except ImportError:
        raise CaptionError(
            "The anthropic package is not installed on the server.", status=503
        )

    settings = get_settings()
    # The env var is CLAUDE_API_KEY but the SDK looks for ANTHROPIC_API_KEY, so
    # the key is passed explicitly. Relying on the SDK's own lookup here fails
    # with an auth error that points nowhere near the real cause.
    client = anthropic.Anthropic(api_key=settings.claude_api_key)

    detail = f"Brief from the poster: {brief}"
    if duration_seconds:
        detail += f"\n\nThe reel is {duration_seconds:.0f} seconds long."

    content = []
    image = _thumbnail_block(thumbnail)
    if image:
        content.append(image)
        detail += (
            "\n\nA thumbnail frame is attached. Treat it as a hint about setting "
            "and tone only."
        )
    content.append({"type": "text", "text": detail})

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            # Format only. `effort` is not supported on Haiku 4.5 and returns
            # a 400, and omitting `thinking` means no thinking tokens - which
            # was the larger half of the per-request cost.
            output_config={
                "format": {"type": "json_schema", "schema": CAPTION_SCHEMA},
            },
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.AuthenticationError:
        raise CaptionError(
            "Anthropic rejected the API key. Check CLAUDE_API_KEY.", status=502
        )
    except anthropic.RateLimitError:
        raise CaptionError(
            "Anthropic is rate limiting this account. Try again shortly.", status=429
        )
    except anthropic.APIStatusError as e:
        logger.error(f"Anthropic returned {e.status_code}: {e.message}")
        raise CaptionError(
            f"Caption generation failed upstream ({e.status_code}).", status=502
        )
    except anthropic.APIConnectionError:
        raise CaptionError("Could not reach Anthropic. Try again shortly.", status=502)

    # A refusal is a successful HTTP call with no usable content, so this has
    # to be checked before touching response.content.
    if response.stop_reason == "refusal":
        raise CaptionError(
            "Claude declined to write a caption for this brief.", status=422
        )

    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        captions = json.loads(text)["captions"]
    except (ValueError, KeyError, TypeError):
        logger.error(f"Unparseable caption response: {text[:300]}")
        raise CaptionError("Caption generation returned an unusable response.")

    cleaned = [
        {"angle": str(c.get("angle", "")).strip(), "text": str(c.get("text", "")).strip()}
        for c in captions
        if isinstance(c, dict) and str(c.get("text", "")).strip()
    ]
    if not cleaned:
        raise CaptionError("Caption generation returned nothing usable.")

    return cleaned[:3]
