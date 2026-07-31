from __future__ import annotations

import time
from collections.abc import Callable

from app.llm.base import LLMMessage, LLMProvider, LLMResponse


class MockProvider(LLMProvider):
    """Offline provider for tests and no-key development.

    Either returns a fixed string, or calls a supplied function with the
    messages/system so a test can synthesize a realistic structured response.
    """

    name = "mock"

    def __init__(
        self,
        *,
        response: str | None = None,
        responder: Callable[[list[LLMMessage], str | None], str] | None = None,
    ):
        if response is None and responder is None:
            response = "{}"
        self._response = response
        self._responder = responder

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
        text = (
            self._responder(messages, system)
            if self._responder is not None
            else self._response
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        # Rough token estimate so downstream logging/metrics have values.
        joined = (system or "") + "".join(m.content for m in messages)
        return LLMResponse(
            text=text,
            model=f"mock:{model}",
            tokens_in=len(joined) // 4,
            tokens_out=len(text) // 4,
            latency_ms=latency_ms,
            raw={"mock": True},
        )
