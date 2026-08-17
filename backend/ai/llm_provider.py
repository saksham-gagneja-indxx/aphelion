"""Unified LLM provider interface: Claude (Anthropic), Gemini (Google), NVIDIA NIM.

This module abstracts away provider-specific APIs, allowing the application to
switch providers without changing business logic in captions.py or composer.py.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pathlib import Path
import json
import base64

from backend.utils.logger import get_logger
from backend.utils.config import get_settings, is_placeholder

logger = get_logger("social_media_automation.llm_provider")


class LLMError(Exception):
    """Base exception for LLM provider errors."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the provider is configured with valid API key."""
        pass

    @abstractmethod
    def unavailable_reason(self) -> Optional[str]:
        """Return user-facing reason why provider is unavailable, or None."""
        pass

    @abstractmethod
    def suggest_captions(
        self,
        brief: str,
        thumbnail: Optional[Path] = None,
        duration_seconds: Optional[float] = None,
    ) -> List[dict]:
        """Generate three caption suggestions. Returns list of {angle, text}."""
        pass

    @abstractmethod
    def run_composer_turn(
        self,
        messages: List[dict],
        draft: Optional[dict],
        reels: List[dict],
        tz_name: str,
        thumbnail: Optional[Path] = None,
    ) -> dict:
        """Run one composer turn. Returns {reply, draft, ready, actions}."""
        pass


class ClaudeProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(self):
        self.settings = get_settings()
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize Claude client."""
        try:
            import anthropic

            if not is_placeholder(self.settings.claude_api_key):
                self.client = anthropic.Anthropic(api_key=self.settings.claude_api_key)
        except ImportError:
            logger.warning("anthropic package not installed")

    def is_configured(self) -> bool:
        """Check if Claude is configured."""
        return self.client is not None and not is_placeholder(self.settings.claude_api_key)

    def unavailable_reason(self) -> Optional[str]:
        """Return reason Claude is unavailable."""
        if is_placeholder(self.settings.claude_api_key):
            return "Claude needs a real CLAUDE_API_KEY configured."
        if self.client is None:
            return "The anthropic package is not installed on the server."
        return None

    def suggest_captions(
        self,
        brief: str,
        thumbnail: Optional[Path] = None,
        duration_seconds: Optional[float] = None,
    ) -> List[dict]:
        """Generate three captions using Claude Haiku."""
        from backend.core.captions import (
            CaptionError,
            CAPTION_SCHEMA,
            SYSTEM as CAPTION_SYSTEM,
        )

        brief = (brief or "").strip()
        if not brief:
            raise CaptionError(
                "Describe the reel in a sentence first — captions are written from "
                "your brief, not from the video.",
                status=400,
            )

        try:
            import anthropic
        except ImportError:
            raise CaptionError(
                "The anthropic package is not installed on the server.", status=503
            )

        if not self.is_configured():
            reason = self.unavailable_reason()
            raise CaptionError(reason or "Claude is not available.", status=503)

        detail = f"Brief from the poster: {brief}"
        if duration_seconds:
            detail += f"\n\nThe reel is {duration_seconds:.0f} seconds long."

        content = []
        image = self._thumbnail_block(thumbnail)
        if image:
            content.append(image)
            detail += (
                "\n\nA thumbnail frame is attached. Treat it as a hint about setting "
                "and tone only."
            )
        content.append({"type": "text", "text": detail})

        try:
            response = self.client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=2048,
                system=CAPTION_SYSTEM,
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

    def run_composer_turn(
        self,
        messages: List[dict],
        draft: Optional[dict],
        reels: List[dict],
        tz_name: str,
        thumbnail: Optional[Path] = None,
    ) -> dict:
        """Run one composer turn using Claude Opus."""
        from backend.core.composer import (
            ComposerError,
            MODEL,
            EFFORT,
            SYSTEM as COMPOSER_SYSTEM,
            TOOLS,
            MAX_TOKENS,
            MAX_TURNS,
            MAX_MESSAGE_CHARS,
            MAX_TOOL_ROUNDS,
            empty_draft,
            _context_block,
            _apply_tool,
        )

        try:
            import anthropic
        except ImportError:
            raise ComposerError(
                "The anthropic package is not installed on the server.", status=503
            )

        if not self.is_configured():
            reason = self.unavailable_reason()
            raise ComposerError(reason or "Claude is not available.", status=503)

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

        draft = dict(draft or empty_draft())
        reel_names = [r.get("filename") for r in reels if r.get("filename")]

        convo: List[dict] = []
        for i, m in enumerate(messages):
            role = "assistant" if m.get("role") == "assistant" else "user"
            content = m.get("content") or ""
            if i == 0 and role == "user":
                content = f"{_context_block(reels, tz_name)}\n\n---\n\n{content}"
            convo.append({"role": role, "content": content})

        tool_notes: List[str] = []

        for _ in range(MAX_TOOL_ROUNDS):
            try:
                response = self.client.messages.create(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    system=COMPOSER_SYSTEM,
                    tools=TOOLS,
                    output_config={"effort": EFFORT},
                    messages=convo,
                )
            except anthropic.AuthenticationError:
                raise ComposerError("Anthropic rejected the API key.", status=502)
            except anthropic.RateLimitError:
                raise ComposerError("Rate limited by Anthropic. Try again shortly.", status=429)
            except anthropic.APIConnectionError:
                raise ComposerError("Could not reach Anthropic.", status=502)
            except anthropic.APIStatusError as e:
                logger.error(f"Anthropic {e.status_code}: {e.message}")
                raise ComposerError(f"Upstream error ({e.status_code}).", status=502)

            if response.stop_reason == "refusal":
                raise ComposerError("Claude declined to answer that.", status=422)

            text = "".join(b.text for b in response.content if b.type == "text").strip()
            tool_uses = [b for b in response.content if b.type == "tool_use"]

            if not tool_uses:
                return {
                    "reply": text,
                    "draft": draft,
                    "ready": bool(draft["reel_filename"] and draft["caption"] and draft["when"]),
                    "actions": tool_notes,
                }

            convo.append({"role": "assistant", "content": response.content})
            results = []
            for tu in tool_uses:
                outcome = _apply_tool(tu.name, tu.input or {}, draft, reel_names, tz_name)
                tool_notes.append(outcome)
                logger.info(f"composer tool {tu.name}: {outcome}")
                results.append(
                    {"type": "tool_result", "tool_use_id": tu.id, "content": outcome}
                )
            convo.append({"role": "user", "content": results})

        logger.warning("Composer hit the tool-round ceiling")
        return {
            "reply": (
                "I got partway there but kept going in circles. Here is what I have "
                "— tell me what to change."
            ),
            "draft": draft,
            "ready": bool(draft["reel_filename"] and draft["caption"] and draft["when"]),
            "actions": tool_notes,
        }

    @staticmethod
    def _thumbnail_block(thumbnail: Optional[Path]) -> Optional[dict]:
        """Convert thumbnail to base64 image block."""
        if thumbnail is None:
            return None
        try:
            if not thumbnail.is_file():
                return None
            data = thumbnail.read_bytes()
        except OSError as e:
            logger.warning(f"Could not read thumbnail {thumbnail}: {e}")
            return None

        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.standard_b64encode(data).decode("ascii"),
            },
        }


class GeminiProvider(LLMProvider):
    """Google Gemini API provider."""

    def __init__(self):
        self.settings = get_settings()
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize Gemini client."""
        try:
            import google.generativeai as genai

            if not is_placeholder(self.settings.gemini_api_key):
                genai.configure(api_key=self.settings.gemini_api_key)
                self.client = genai
        except ImportError:
            logger.warning("google-generativeai package not installed")

    def is_configured(self) -> bool:
        """Check if Gemini is configured."""
        return self.client is not None and not is_placeholder(self.settings.gemini_api_key)

    def unavailable_reason(self) -> Optional[str]:
        """Return reason Gemini is unavailable."""
        if is_placeholder(self.settings.gemini_api_key):
            return "Gemini needs a real GEMINI_API_KEY configured."
        if self.client is None:
            return "The google-generativeai package is not installed on the server."
        return None

    def suggest_captions(
        self,
        brief: str,
        thumbnail: Optional[Path] = None,
        duration_seconds: Optional[float] = None,
    ) -> List[dict]:
        """Generate three captions using Gemini."""
        from backend.core.captions import CaptionError

        brief = (brief or "").strip()
        if not brief:
            raise CaptionError(
                "Describe the reel in a sentence first — captions are written from "
                "your brief, not from the video.",
                status=400,
            )

        try:
            import google.generativeai as genai
        except ImportError:
            raise CaptionError(
                "The google-generativeai package is not installed on the server.", status=503
            )

        if not self.is_configured():
            reason = self.unavailable_reason()
            raise CaptionError(reason or "Gemini is not available.", status=503)

        system_prompt = """You write LinkedIn captions for short video posts (reels).

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

Return valid JSON with this structure:
{
  "captions": [
    {"angle": "string (2-3 words)", "text": "string (the caption)"},
    {"angle": "string", "text": "string"},
    {"angle": "string", "text": "string"}
  ]
}"""

        detail = f"Brief from the poster: {brief}"
        if duration_seconds:
            detail += f"\n\nThe reel is {duration_seconds:.0f} seconds long."

        content = []
        if thumbnail:
            try:
                if thumbnail.is_file():
                    image_data = thumbnail.read_bytes()
                    content.append(
                        {
                            "mime_type": "image/jpeg",
                            "data": base64.standard_b64encode(image_data).decode("ascii"),
                        }
                    )
                    detail += (
                        "\n\nA thumbnail frame is attached. Treat it as a hint about setting "
                        "and tone only."
                    )
            except (OSError, Exception) as e:
                logger.warning(f"Could not read thumbnail {thumbnail}: {e}")

        content.append(detail)

        try:
            model = self.client.GenerativeModel(
                self.settings.gemini_model,
                system_instruction=system_prompt,
            )
            response = model.generate_content(
                content,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=2048,
                    temperature=0.7,
                ),
            )

            text = response.text if hasattr(response, "text") else ""
        except Exception as e:
            logger.error(f"Gemini error: {str(e)}")
            if "quota" in str(e).lower():
                raise CaptionError(
                    "Gemini quota exceeded. Try again later.", status=429
                )
            elif "api_key" in str(e).lower() or "authentication" in str(e).lower():
                raise CaptionError("Gemini rejected the API key.", status=502)
            else:
                raise CaptionError(f"Caption generation failed ({str(e)[:50]}).", status=502)

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

    def run_composer_turn(
        self,
        messages: List[dict],
        draft: Optional[dict],
        reels: List[dict],
        tz_name: str,
        thumbnail: Optional[Path] = None,
    ) -> dict:
        """Run one composer turn using Gemini."""
        from backend.core.composer import (
            ComposerError,
            SYSTEM as COMPOSER_SYSTEM,
            MAX_TOKENS,
            MAX_TURNS,
            MAX_MESSAGE_CHARS,
            MAX_TOOL_ROUNDS,
            empty_draft,
            _context_block,
            _apply_tool,
            TOOLS,
        )

        try:
            import google.generativeai as genai
        except ImportError:
            raise ComposerError(
                "The google-generativeai package is not installed on the server.", status=503
            )

        if not self.is_configured():
            reason = self.unavailable_reason()
            raise ComposerError(reason or "Gemini is not available.", status=503)

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

        draft = dict(draft or empty_draft())
        reel_names = [r.get("filename") for r in reels if r.get("filename")]

        convo: List[dict] = []
        for i, m in enumerate(messages):
            role = "assistant" if m.get("role") == "assistant" else "user"
            content = m.get("content") or ""
            if i == 0 and role == "user":
                content = f"{_context_block(reels, tz_name)}\n\n---\n\n{content}"

            if role == "user":
                convo.append(genai.types.ContentDict(role="user", parts=[content]))
            else:
                convo.append(genai.types.ContentDict(role="model", parts=[content]))

        tool_notes: List[str] = []

        try:
            model = self.client.GenerativeModel(
                self.settings.gemini_model,
                system_instruction=COMPOSER_SYSTEM,
                tools=[self._convert_tools_to_gemini(TOOLS)],
            )

            for _ in range(MAX_TOOL_ROUNDS):
                try:
                    response = model.generate_content(
                        convo,
                        generation_config=genai.types.GenerationConfig(
                            max_output_tokens=MAX_TOKENS,
                            temperature=0.3,
                        ),
                    )
                except Exception as e:
                    logger.error(f"Gemini error: {str(e)}")
                    if "quota" in str(e).lower():
                        raise ComposerError("Rate limited by Gemini. Try again shortly.", status=429)
                    elif "api_key" in str(e).lower():
                        raise ComposerError("Gemini rejected the API key.", status=502)
                    else:
                        raise ComposerError(f"Upstream error ({str(e)[:50]}).", status=502)

                text = response.text if hasattr(response, "text") else ""
                tool_calls = self._extract_tool_calls(response)

                if not tool_calls:
                    return {
                        "reply": text,
                        "draft": draft,
                        "ready": bool(draft["reel_filename"] and draft["caption"] and draft["when"]),
                        "actions": tool_notes,
                    }

                convo.append(genai.types.ContentDict(role="model", parts=[text]))
                results = []
                for tool_name, tool_args in tool_calls:
                    outcome = _apply_tool(tool_name, tool_args, draft, reel_names, tz_name)
                    tool_notes.append(outcome)
                    logger.info(f"composer tool {tool_name}: {outcome}")
                    results.append(outcome)

                convo.append(genai.types.ContentDict(role="user", parts=results))

        except ComposerError:
            raise
        except Exception as e:
            logger.error(f"Composer error: {str(e)}")
            raise ComposerError(f"Unexpected error: {str(e)}", status=502)

        logger.warning("Composer hit the tool-round ceiling")
        return {
            "reply": (
                "I got partway there but kept going in circles. Here is what I have "
                "— tell me what to change."
            ),
            "draft": draft,
            "ready": bool(draft["reel_filename"] and draft["caption"] and draft["when"]),
            "actions": tool_notes,
        }

    @staticmethod
    def _strip_unsupported_schema_fields(schema: Any) -> Any:
        """Remove JSON Schema keywords Gemini's function-calling API rejects.

        Gemini's schema dialect is a subset of JSON Schema and errors out
        ("Unknown field for Schema: additionalProperties") on keywords Claude's
        tool schemas rely on. Strip them recursively rather than hand-writing a
        second schema per tool.
        """
        UNSUPPORTED = {"additionalProperties", "$schema"}
        if isinstance(schema, dict):
            return {
                k: GeminiProvider._strip_unsupported_schema_fields(v)
                for k, v in schema.items()
                if k not in UNSUPPORTED
            }
        if isinstance(schema, list):
            return [GeminiProvider._strip_unsupported_schema_fields(v) for v in schema]
        return schema

    @staticmethod
    def _convert_tools_to_gemini(tools: List[dict]) -> Dict[str, Any]:
        """Convert Claude tool format to Gemini tool format."""
        tool_defs = {}
        for tool in tools:
            name = tool["name"]
            tool_defs[name] = {
                "description": tool["description"],
                "parameters": GeminiProvider._strip_unsupported_schema_fields(
                    tool["input_schema"]
                ),
            }
        return {"function_declarations": [{"name": k, **v} for k, v in tool_defs.items()]}

    @staticmethod
    def _extract_tool_calls(response) -> List[tuple]:
        """Extract tool calls from Gemini response."""
        tool_calls = []
        if hasattr(response, "parts"):
            for part in response.parts:
                if hasattr(part, "function_call"):
                    func_call = part.function_call
                    name = func_call.name
                    args = dict(func_call.args) if func_call.args else {}
                    tool_calls.append((name, args))
        return tool_calls


class NvidiaNimProvider(LLMProvider):
    """NVIDIA NIM provider (OpenAI-compatible API), default model Meta Muse Glimmer 30B.

    NIM exposes an OpenAI-compatible chat completions endpoint, so this reuses
    the `openai` SDK pointed at NVIDIA's base URL rather than a bespoke client.
    """

    def __init__(self):
        self.settings = get_settings()
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize the OpenAI-compatible client against NVIDIA's endpoint."""
        try:
            import openai

            if not is_placeholder(self.settings.nvidia_api_key):
                self.client = openai.OpenAI(
                    api_key=self.settings.nvidia_api_key,
                    base_url=self.settings.nvidia_base_url,
                )
        except ImportError:
            logger.warning("openai package not installed")

    def is_configured(self) -> bool:
        """Check if NVIDIA NIM is configured."""
        return self.client is not None and not is_placeholder(self.settings.nvidia_api_key)

    def unavailable_reason(self) -> Optional[str]:
        """Return reason NVIDIA NIM is unavailable."""
        if is_placeholder(self.settings.nvidia_api_key):
            return "NVIDIA NIM needs a real NVIDIA_API_KEY configured."
        if self.client is None:
            return "The openai package is not installed on the server."
        return None

    def suggest_captions(
        self,
        brief: str,
        thumbnail: Optional[Path] = None,
        duration_seconds: Optional[float] = None,
    ) -> List[dict]:
        """Generate three captions using the NVIDIA-hosted model."""
        from backend.core.captions import CaptionError, SYSTEM as CAPTION_SYSTEM, CAPTION_SCHEMA

        brief = (brief or "").strip()
        if not brief:
            raise CaptionError(
                "Describe the reel in a sentence first — captions are written from "
                "your brief, not from the video.",
                status=400,
            )

        try:
            import openai
        except ImportError:
            raise CaptionError(
                "The openai package is not installed on the server.", status=503
            )

        if not self.is_configured():
            reason = self.unavailable_reason()
            raise CaptionError(reason or "NVIDIA NIM is not available.", status=503)

        detail = f"Brief from the poster: {brief}"
        if duration_seconds:
            detail += f"\n\nThe reel is {duration_seconds:.0f} seconds long."

        user_content: List[dict] = []
        image = self._thumbnail_block(thumbnail)
        if image:
            user_content.append(image)
            detail += (
                "\n\nA thumbnail frame is attached. Treat it as a hint about setting "
                "and tone only."
            )
        user_content.append({"type": "text", "text": detail})

        # Structured output is requested via a JSON schema response_format, the
        # same shape OpenAI-compatible APIs use. The system prompt also states
        # the schema in words as a fallback for models that ignore the field.
        schema_system = (
            CAPTION_SYSTEM
            + "\n\nRespond with a JSON object of exactly this shape: "
            + '{"captions": [{"angle": "...", "text": "..."}, ...]} with exactly three entries.'
        )

        # 30B model with a reasoning parser can spend a chunk of the token
        # budget on internal reasoning before it ever emits the JSON body, so
        # this needs real headroom - 2048 truncated the answer mid-string in
        # testing.
        CAPTION_MAX_TOKENS = 8192

        try:
            # Build model name with nvidia/ prefix if not already present
            model = self.settings.nvidia_model
            if not model.startswith("nvidia/"):
                model = f"nvidia/{model}"

            # Use reasoning for better caption quality on Nemotron
            extra_body = {}
            if "nemotron" in model.lower():
                extra_body = {
                    "chat_template_kwargs": {"enable_thinking": True},
                    "reasoning_budget": CAPTION_MAX_TOKENS // 2,
                }

            response = self.client.chat.completions.create(
                model=model,
                max_tokens=CAPTION_MAX_TOKENS,
                temperature=0.7,
                messages=[
                    {"role": "system", "content": schema_system},
                    {"role": "user", "content": user_content},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "captions", "schema": CAPTION_SCHEMA},
                },
                **({"extra_body": extra_body} if extra_body else {}),
            )
        except openai.AuthenticationError:
            raise CaptionError(
                "NVIDIA rejected the API key. Check NVIDIA_API_KEY.", status=502
            )
        except openai.RateLimitError:
            raise CaptionError(
                "NVIDIA NIM is rate limiting this account. Try again shortly.", status=429
            )
        except openai.APIConnectionError:
            raise CaptionError("Could not reach NVIDIA NIM. Try again shortly.", status=502)
        except openai.APIStatusError as e:
            logger.error(f"NVIDIA NIM returned {e.status_code}: {e.message}")
            # response_format with json_schema is not guaranteed on every
            # NIM-hosted model; a 4xx here likely means it was rejected, so
            # retry once without it and rely on the prompt instruction alone.
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    max_tokens=CAPTION_MAX_TOKENS,
                    temperature=0.7,
                    messages=[
                        {"role": "system", "content": schema_system},
                        {"role": "user", "content": user_content},
                    ],
                    **({"extra_body": extra_body} if extra_body else {}),
                )
            except Exception:
                raise CaptionError(
                    f"Caption generation failed upstream ({e.status_code}).", status=502
                )

        choice = response.choices[0]
        if choice.finish_reason == "length":
            logger.error(
                f"NVIDIA NIM truncated the caption response at {CAPTION_MAX_TOKENS} tokens"
            )
            raise CaptionError(
                "Caption generation ran out of room before finishing. Try a shorter brief.",
                status=502,
            )
        text = choice.message.content or ""
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

    def run_composer_turn(
        self,
        messages: List[dict],
        draft: Optional[dict],
        reels: List[dict],
        tz_name: str,
        thumbnail: Optional[Path] = None,
    ) -> dict:
        """Run one composer turn using the NVIDIA-hosted model's tool calling."""
        from backend.core.composer import (
            ComposerError,
            SYSTEM as COMPOSER_SYSTEM,
            MAX_TOKENS,
            MAX_TURNS,
            MAX_MESSAGE_CHARS,
            MAX_TOOL_ROUNDS,
            TOOLS,
            empty_draft,
            _context_block,
            _apply_tool,
        )

        try:
            import openai
        except ImportError:
            raise ComposerError(
                "The openai package is not installed on the server.", status=503
            )

        if not self.is_configured():
            reason = self.unavailable_reason()
            raise ComposerError(reason or "NVIDIA NIM is not available.", status=503)

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

        draft = dict(draft or empty_draft())
        reel_names = [r.get("filename") for r in reels if r.get("filename")]

        convo: List[dict] = [{"role": "system", "content": COMPOSER_SYSTEM}]
        for i, m in enumerate(messages):
            role = "assistant" if m.get("role") == "assistant" else "user"
            content = m.get("content") or ""
            if i == 0 and role == "user":
                content = f"{_context_block(reels, tz_name)}\n\n---\n\n{content}"
            convo.append({"role": role, "content": content})

        tools_oa = [self._convert_tool_to_openai(t) for t in TOOLS]
        tool_notes: List[str] = []

        for _ in range(MAX_TOOL_ROUNDS):
            try:
                response = self.client.chat.completions.create(
                    model=self.settings.nvidia_model,
                    max_tokens=MAX_TOKENS,
                    temperature=0.3,
                    messages=convo,
                    tools=tools_oa,
                )
            except openai.AuthenticationError:
                raise ComposerError("NVIDIA rejected the API key.", status=502)
            except openai.RateLimitError:
                raise ComposerError("Rate limited by NVIDIA NIM. Try again shortly.", status=429)
            except openai.APIConnectionError:
                raise ComposerError("Could not reach NVIDIA NIM.", status=502)
            except openai.APIStatusError as e:
                logger.error(f"NVIDIA NIM {e.status_code}: {e.message}")
                raise ComposerError(f"Upstream error ({e.status_code}).", status=502)

            choice = response.choices[0]
            msg = choice.message
            text = msg.content or ""
            tool_calls = msg.tool_calls or []

            if not tool_calls:
                return {
                    "reply": text,
                    "draft": draft,
                    "ready": bool(draft["reel_filename"] and draft["caption"] and draft["when"]),
                    "actions": tool_notes,
                }

            convo.append(
                {
                    "role": "assistant",
                    "content": text,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )
            for tc in tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except (ValueError, TypeError):
                    args = {}
                outcome = _apply_tool(tc.function.name, args, draft, reel_names, tz_name)
                tool_notes.append(outcome)
                logger.info(f"composer tool {tc.function.name}: {outcome}")
                convo.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": outcome}
                )

        logger.warning("Composer hit the tool-round ceiling")
        return {
            "reply": (
                "I got partway there but kept going in circles. Here is what I have "
                "— tell me what to change."
            ),
            "draft": draft,
            "ready": bool(draft["reel_filename"] and draft["caption"] and draft["when"]),
            "actions": tool_notes,
        }

    @staticmethod
    def _convert_tool_to_openai(tool: dict) -> dict:
        """Convert a Claude-shaped tool def to the OpenAI/NIM function-calling shape."""
        return {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }

    @staticmethod
    def _thumbnail_block(thumbnail: Optional[Path]) -> Optional[dict]:
        """Convert thumbnail to an OpenAI-style base64 image_url block."""
        if thumbnail is None:
            return None
        try:
            if not thumbnail.is_file():
                return None
            data = thumbnail.read_bytes()
        except OSError as e:
            logger.warning(f"Could not read thumbnail {thumbnail}: {e}")
            return None

        b64 = base64.standard_b64encode(data).decode("ascii")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        }


def get_provider() -> LLMProvider:
    """Get the configured LLM provider instance."""
    settings = get_settings()
    provider_name = (settings.llm_provider or "claude").lower().strip()

    if provider_name == "nvidia":
        return NvidiaNimProvider()
    elif provider_name == "gemini":
        return GeminiProvider()
    else:
        return ClaudeProvider()
