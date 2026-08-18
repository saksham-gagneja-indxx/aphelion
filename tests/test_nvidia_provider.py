"""Tests for NvidiaNimProvider - specifically the model name sent to NVIDIA's
API, since that's the one thing every request depends on and the one thing
that broke silently in production with zero coverage: a well-intentioned
"auto-prefix with nvidia/" fix turned "meta/muse-glimmer-30b" into
"nvidia/meta/muse-glimmer-30b", which matches no real model and 404s on
every single call. NVIDIA NIM catalog ids are already fully namespaced
(meta/..., nvidia/..., mistralai/..., etc.) - never rewrite them.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def nvidia_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-genuinely-real-looking-test-key")
    monkeypatch.setenv("NVIDIA_MODEL", "meta/muse-glimmer-30b")
    monkeypatch.setenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-ant-placeholder-not-used-in-v1")
    monkeypatch.setenv("INSTAGRAM_USERNAME", "u")
    monkeypatch.setenv("INSTAGRAM_PASSWORD", "p")


def _fake_response(payload):
    """A response shaped like the OpenAI SDK's ChatCompletion."""
    choice = MagicMock()
    choice.message.content = payload
    choice.message.tool_calls = None
    response = MagicMock()
    response.choices = [choice]
    return response


class TestSuggestCaptionsModelName:
    def test_sends_the_configured_model_name_unmodified(self):
        """The regression this session actually shipped: a "helpful" prefix
        rewrote a valid, fully-namespaced NIM model id into one that matches
        nothing on NVIDIA's side. Every call 404'd upstream as a result."""
        from backend.ai.llm_provider import NvidiaNimProvider

        provider = NvidiaNimProvider()
        provider.client = MagicMock()
        provider.client.chat.completions.create.return_value = _fake_response(
            '{"captions": [{"angle": "a", "text": "one"}, '
            '{"angle": "b", "text": "two"}, {"angle": "c", "text": "three"}]}'
        )

        provider.suggest_captions(brief="a demo of the new feature")

        call_kwargs = provider.client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "meta/muse-glimmer-30b"

    def test_does_not_double_prefix_a_model_already_under_nvidia(self):
        """Some catalog models genuinely are namespaced under nvidia/ (e.g.
        nvidia/nemotron-4-340b-instruct) - the fix must not mangle those
        either, by turning back into a blanket rewrite in the other direction."""
        from backend.ai.llm_provider import NvidiaNimProvider

        with patch.dict(os.environ, {"NVIDIA_MODEL": "nvidia/nemotron-4-340b-instruct"}):
            provider = NvidiaNimProvider()
            provider.client = MagicMock()
            provider.client.chat.completions.create.return_value = _fake_response(
                '{"captions": [{"angle": "a", "text": "one"}, '
                '{"angle": "b", "text": "two"}, {"angle": "c", "text": "three"}]}'
            )

            provider.suggest_captions(brief="a demo of the new feature")

            call_kwargs = provider.client.chat.completions.create.call_args.kwargs
            assert call_kwargs["model"] == "nvidia/nemotron-4-340b-instruct"

    def test_composer_turn_uses_the_same_unmodified_model_name(self):
        """run_composer_turn never had the prefix bug, but pinning this too
        means the two code paths can't quietly drift apart again."""
        from backend.ai.llm_provider import NvidiaNimProvider

        provider = NvidiaNimProvider()
        provider.client = MagicMock()
        provider.client.chat.completions.create.return_value = _fake_response("hello")

        provider.run_composer_turn(
            messages=[{"role": "user", "content": "draft something"}],
            draft=None,
            reels=[],
            tz_name="Asia/Kolkata",
        )

        call_kwargs = provider.client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "meta/muse-glimmer-30b"
