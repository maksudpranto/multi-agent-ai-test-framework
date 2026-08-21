from __future__ import annotations

import time

import httpx

from app.llm import ratelimit
from app.llm.base import LLMMessage, LLMProvider, LLMResponse

# Learned per-model completion-token ceiling. When a model/tier rejects a large
# max_tokens with 413, we remember the value that worked so later calls start
# there instead of burning a request on a guaranteed-413 first attempt.
_MODEL_TOKEN_CEILING: dict[str, int] = {}

# How many times to wait out a 429 before giving up, and the backoff cap. Free
# tiers rate-limit aggressively (per-minute request AND token budgets); a batch
# job like the experiment runner would otherwise fail most of its cells the
# moment it gets ahead of the quota.
_MAX_429_RETRIES = 6
_BACKOFF_CAP_SECONDS = 30.0


def _retry_after_seconds(headers) -> float | None:
    """Seconds to wait from a 429 response, preferring the provider's own hint
    (`retry-after`, or Groq/OpenRouter's `x-ratelimit-reset-*`)."""
    ra = headers.get("retry-after")
    if ra:
        try:
            return min(_BACKOFF_CAP_SECONDS, float(ra))
        except ValueError:
            pass
    for key in ("x-ratelimit-reset-requests", "x-ratelimit-reset-tokens"):
        val = headers.get(key)
        if not val:
            continue
        try:
            # These are often like "1.5s" or "2m59s"; parse the leading number.
            num = float("".join(c for c in val if (c.isdigit() or c == ".")) or "0")
            if num > 0:
                return min(_BACKOFF_CAP_SECONDS, num)
        except ValueError:
            continue
    return None


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
        # it). Start from the learned ceiling for this model (so we don't waste a
        # request on a guaranteed 413), then halve-and-retry if the tier still
        # rejects it — capable models keep the headroom, constrained ones heal.
        attempt_tokens = max_tokens
        ceiling = _MODEL_TOKEN_CEILING.get(model)
        if ceiling is not None:
            attempt_tokens = min(attempt_tokens, ceiling)
        rate_retries = 0
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
            # Rate-limited: wait out the window (provider hint or exponential
            # backoff) and retry, so a burst of calls paces itself instead of
            # failing. Bounded, so a genuinely exhausted quota still surfaces.
            if response.status_code == 429 and rate_retries < _MAX_429_RETRIES:
                rate_retries += 1
                wait = _retry_after_seconds(response.headers)
                if wait is None:
                    wait = min(_BACKOFF_CAP_SECONDS, 1.5 * (2 ** (rate_retries - 1)))
                time.sleep(wait)
                continue
            break
        # Remember what this model actually accepted, and capture the real
        # remaining quota the provider reported for the usage panel.
        _MODEL_TOKEN_CEILING[model] = attempt_tokens
        try:
            ratelimit.record(self.name, response.headers)
        except Exception:
            pass  # usage stats are best-effort, never block a completion
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
