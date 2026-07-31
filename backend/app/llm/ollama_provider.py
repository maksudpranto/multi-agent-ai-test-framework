from __future__ import annotations

import time

import httpx

from app.llm.base import LLMMessage, LLMProvider, LLMResponse


class OllamaProvider(LLMProvider):
    """Local Ollama backend using its OpenAI-style chat endpoint."""

    name = "ollama"

    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    def complete(
        self,
        *,
        messages: list[LLMMessage],
        model: str,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        chat_messages = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.extend(
            {"role": message.role, "content": message.content} for message in messages
        )
        start = time.monotonic()
        response = httpx.post(
            f"{self._base_url}/api/chat",
            json={
                "model": model,
                "messages": chat_messages,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()
        latency_ms = int((time.monotonic() - start) * 1000)
        return LLMResponse(
            text=data["message"]["content"],
            model=data.get("model", model),
            tokens_in=data.get("prompt_eval_count"),
            tokens_out=data.get("eval_count"),
            latency_ms=latency_ms,
            raw={"done_reason": data.get("done_reason")},
        )
