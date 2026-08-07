from __future__ import annotations

import time

import httpx

from app.llm.base import LLMMessage, LLMProvider, LLMResponse


class OpenAICompatibleProvider(LLMProvider):
    """One provider for every host that speaks the OpenAI /chat/completions API.

    Groq, OpenRouter, Cerebras, Together, DeepSeek, local vLLM, … all share this
    shape, so a single class (base_url + key + optional headers) unlocks all of
    them — no per-vendor SDK. Instantiate with the right base_url per service."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        name: str = "openai_compatible",
        extra_headers: dict[str, str] | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.name = name
        self._extra_headers = extra_headers or {}

    def complete(
        self,
        *,
        messages: list[LLMMessage],
        model: str,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        chat: list[dict] = []
        if system:
            chat.append({"role": "system", "content": system})
        chat.extend({"role": m.role, "content": m.content} for m in messages)

        payload = {
            "model": model,
            "messages": chat,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            **self._extra_headers,
        }

        start = time.monotonic()
        # Free tiers cap per-request/per-minute tokens differently per model
        # (e.g. Groq's 8B tier rejects an 8192 budget with 413 while 70B accepts
        # it). Request the full budget, then halve-and-retry on 413 so capable
        # models keep the headroom and constrained ones self-heal.
        attempt_tokens = max_tokens
        while True:
            payload["max_tokens"] = attempt_tokens
            response = httpx.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120.0,
            )
            if response.status_code == 413 and attempt_tokens > 2048:
                attempt_tokens = max(2048, attempt_tokens // 2)
                continue
            break
        response.raise_for_status()
        data = response.json()
        latency_ms = int((time.monotonic() - start) * 1000)

        choices = data.get("choices") or []
        choice = choices[0] if choices else {}
        message = choice.get("message") or {}
        text = message.get("content") or ""
        finish = choice.get("finish_reason")
        if not text and finish == "length":
            raise ValueError(
                "Model returned no text: output token budget exhausted "
                "(likely spent on reasoning). Increase max_tokens."
            )
        usage = data.get("usage") or {}
        return LLMResponse(
            text=text,
            model=data.get("model", model),
            tokens_in=usage.get("prompt_tokens"),
            tokens_out=usage.get("completion_tokens"),
            latency_ms=latency_ms,
            raw={"finish_reason": finish},
        )
