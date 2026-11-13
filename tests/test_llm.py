"""LLM layer without any real model or network."""

import pytest

from app import llm as llm_mod
from app.llm import FallbackLLM, LLMError, OllamaLLM
from tests.conftest import FakeLLM


def test_fallback_uses_second_when_first_fails():
    first, second = FakeLLM(LLMError("429")), FakeLLM('{"ok": true}')
    second.name = "backup"
    fb = FallbackLLM([first, second])
    assert fb.generate("s", "p") == '{"ok": true}'
    assert fb.last_used == "backup"


def test_fallback_raises_with_all_errors_when_everything_fails():
    fb = FallbackLLM([FakeLLM(LLMError("gemini down")), FakeLLM(LLMError("ollama down"))])
    with pytest.raises(LLMError, match="gemini down.*ollama down"):
        fb.generate("s", "p")


def test_no_llm_configured_is_an_error():
    with pytest.raises(LLMError, match="no LLM configured"):
        FallbackLLM([])


def test_ollama_sends_context_window(monkeypatch):
    """Regression test: without num_ctx, Ollama silently truncated long
    prompts to 2,048 tokens and dropped the system prompt."""
    captured = {}

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "{}"}}

    def fake_post(url, json, timeout):
        captured.update(json)
        return Resp()

    monkeypatch.setattr(llm_mod.httpx, "post", fake_post)
    OllamaLLM("http://ollama:11434", "m", num_ctx=16384).generate("system", "prompt")
    assert captured["options"]["num_ctx"] == 16384
    assert captured["format"] == "json"


def test_ollama_refuses_prompt_that_would_be_truncated(monkeypatch):
    def must_not_call(*a, **k):
        raise AssertionError("request should not be sent")

    monkeypatch.setattr(llm_mod.httpx, "post", must_not_call)
    with pytest.raises(LLMError, match="too long"):
        OllamaLLM("http://ollama:11434", "m", num_ctx=2048).generate("s", "word " * 5000)
