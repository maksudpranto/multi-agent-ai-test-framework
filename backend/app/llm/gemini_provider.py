from __future__ import annotations

import time

import httpx

from app.llm.base import LLMMessage, LLMProvider, LLMResponse


class GeminiProvider(LLMProvider):
    """Gemini backend using Google's REST API, with no SDK dependency."""

    name = "gemini"

    def __init__(self, api_key: str):
        self._api_key = api_key

    def complete(
        self,
        *,
        messages: list[LLMMessage],
        model: str,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        contents = [
            {
                "role": "model" if message.role == "assistant" else "user",
                "parts": [{"text": message.content}],
            }
            for message in messages
        ]
        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        start = time.monotonic()
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": self._api_key},
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        latency_ms = int((time.monotonic() - start) * 1000)

        candidates = data.get("candidates") or []
        candidate = candidates[0] if candidates else {}
        # Gemini "thinking" models (2.5/3.x flash) can return an empty content
        # block with finishReason=MAX_TOKENS when the token budget is spent on
        # internal reasoning, and a safety block yields no parts either. Parse
        # defensively so those cases surface as empty text (the JSON layer then
        # raises a clear ValueError) instead of a KeyError deep in the provider.
        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts)
        finish = candidate.get("finishReason")
        if not text and finish == "MAX_TOKENS":
            raise ValueError(
                "Gemini returned no text: output token budget exhausted "
                "(likely spent on model 'thinking'). Increase max_tokens."
            )
        if not text and finish in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT"}:
            raise ValueError(f"Gemini blocked the response (finishReason={finish}).")
        usage = data.get("usageMetadata", {})
        return LLMResponse(
            text=text,
            model=model,
            tokens_in=usage.get("promptTokenCount"),
            tokens_out=usage.get("candidatesTokenCount"),
            latency_ms=latency_ms,
            raw={"finish_reason": candidate.get("finishReason")},
        )
