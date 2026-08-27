from __future__ import annotations

import time

from app.llm.base import LLMMessage, LLMProvider, LLMResponse


class AnthropicProvider(LLMProvider):
    """Claude backend via the official Anthropic SDK."""

    name = "anthropic"

    def __init__(self, api_key: str):
        # Imported lazily so the app (and tests using MockProvider) don't
        # require a configured key just to import this module.
        from anthropic import Anthropic

        self._client = Anthropic(api_key=api_key)

    def complete(
        self,
        *,
        messages: list[LLMMessage],
        model: str,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        start = time.monotonic()
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if system:
            kwargs["system"] = system

        # Use the raw response so we can read Anthropic's `anthropic-ratelimit-*`
        # headers and surface the live per-minute limits in the usage panel.
        raw = self._client.messages.with_raw_response.create(**kwargs)
        resp = raw.parse()
        latency_ms = int((time.monotonic() - start) * 1000)
        try:
            from app.llm import ratelimit

            ratelimit.record("anthropic", raw.headers)
        except Exception:
            pass  # rate-limit capture is best-effort, never fails a run

        text = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )
        return LLMResponse(
            text=text,
            model=model,
            tokens_in=resp.usage.input_tokens if resp.usage else None,
            tokens_out=resp.usage.output_tokens if resp.usage else None,
            latency_ms=latency_ms,
            raw={"stop_reason": resp.stop_reason},
        )
