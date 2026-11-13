"""LLM clients. The answering code only depends on the LLM protocol, so tests
can use a fake LLM and Gemini can fall back to a local Ollama model."""

from __future__ import annotations

from typing import Protocol

import httpx


class LLMError(RuntimeError):
    """The model could not be reached or refused the request (rate limit,
    network, bad key). Distinct from 'the model answered with bad JSON'."""


class LLM(Protocol):
    name: str

    def generate(self, system: str, prompt: str) -> str:
        """Return the raw text of the model's reply (expected to be JSON)."""
        ...


class GeminiLLM:
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set")
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.name = f"gemini:{model}"

    def generate(self, system: str, prompt: str) -> str:
        from google.genai import types

        try:
            resp = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    # JSON mode: the model is constrained to emit valid JSON.
                    # We still validate it ourselves (see app/answer.py).
                    response_mime_type="application/json",
                    temperature=0.0,  # same question -> (nearly) same answer
                ),
            )
        except Exception as exc:  # SDK raises various types for 429/5xx/network
            raise LLMError(f"{self.name}: {exc}") from exc
        return resp.text or ""


class OllamaLLM:
    def __init__(self, url: str, model: str, timeout: float = 120.0):
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.name = f"ollama:{model}"

    def generate(self, system: str, prompt: str) -> str:
        try:
            resp = httpx.post(
                f"{self.url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": 0},
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMError(f"{self.name}: {exc}") from exc
        return resp.json()["message"]["content"]


class FallbackLLM:
    """Try each LLM in order; move to the next only if one *fails to respond*.
    A reply with bad JSON is not a failure here: that is handled (with a
    retry) by the answering code, against the same model."""

    def __init__(self, llms: list[LLM]):
        if not llms:
            raise LLMError("no LLM configured: set GEMINI_API_KEY or OLLAMA_URL")
        self.llms = llms
        self.name = " -> ".join(m.name for m in llms)
        self.last_used: str | None = None

    def generate(self, system: str, prompt: str) -> str:
        errors = []
        for llm in self.llms:
            try:
                out = llm.generate(system, prompt)
                self.last_used = llm.name
                return out
            except LLMError as exc:
                errors.append(str(exc))
        raise LLMError(" | ".join(errors))


def build_llm(settings) -> FallbackLLM:
    llms: list[LLM] = []
    if settings.gemini_api_key:
        llms.append(GeminiLLM(settings.gemini_api_key, settings.gemini_model))
    if settings.ollama_url:
        llms.append(OllamaLLM(settings.ollama_url, settings.ollama_model))
    return FallbackLLM(llms)
