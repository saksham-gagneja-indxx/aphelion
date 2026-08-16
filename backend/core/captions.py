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

from pathlib import Path
from typing import List, Optional

from backend.ai.llm_provider import get_provider
from backend.utils.config import get_settings, is_placeholder
from backend.utils.logger import get_logger

logger = get_logger("social_media_automation.captions")

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

    The feature flag must be on and the configured provider must have a real API key.
    """
    settings = get_settings()
    if not bool(settings.enable_caption_generation):
        return False

    provider = get_provider()
    return provider.is_configured()


def unavailable_reason() -> Optional[str]:
    """Why captions are off, phrased for the person who has to fix it."""
    settings = get_settings()
    if not settings.enable_caption_generation:
        return "Caption assist is disabled (ENABLE_CAPTION_GENERATION is false)."

    provider = get_provider()
    provider_reason = provider.unavailable_reason()
    if provider_reason:
        return provider_reason

    return None


def suggest_captions(
    brief: str,
    thumbnail: Optional[Path] = None,
    duration_seconds: Optional[float] = None,
) -> List[dict]:
    """Three caption options for one reel.

    Returns a list of {"angle": str, "text": str}. Raises CaptionError with a
    message fit to show the user.
    """
    settings = get_settings()
    if not settings.enable_caption_generation:
        raise CaptionError(
            "Caption assist is disabled (ENABLE_CAPTION_GENERATION is false).", status=503
        )

    provider = get_provider()
    reason = provider.unavailable_reason()
    if reason:
        raise CaptionError(reason, status=503)

    try:
        return provider.suggest_captions(brief, thumbnail, duration_seconds)
    except CaptionError:
        raise
    except Exception as e:
        logger.error(f"Caption generation error: {str(e)}")
        raise CaptionError(
            f"Caption generation failed: {str(e)[:100]}", status=502
        )
