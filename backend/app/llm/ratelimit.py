"""Process-wide cache of the most recent rate-limit state each OpenAI-compatible
provider reported in its response headers.

Groq and OpenRouter return `x-ratelimit-*` headers on every call with the REAL
remaining requests/tokens for the account — the ground truth that matches their
dashboards (and unlike our audit-log count, it also reflects calls made outside
this app and 413 retry attempts). The usage endpoint reads this to show an
authoritative "remaining" instead of an estimate.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

_LOCK = threading.Lock()
_STATE: dict[str, dict] = {}


def _to_int(value) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def record(provider: str, headers) -> None:
    """Capture the rate-limit headers from a provider response (best-effort)."""
    h = {k.lower(): v for k, v in dict(headers).items()}
    snap = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "limit_requests": _to_int(h.get("x-ratelimit-limit-requests") or h.get("x-ratelimit-limit")),
        "remaining_requests": _to_int(h.get("x-ratelimit-remaining-requests") or h.get("x-ratelimit-remaining")),
        "limit_tokens": _to_int(h.get("x-ratelimit-limit-tokens")),
        "remaining_tokens": _to_int(h.get("x-ratelimit-remaining-tokens")),
        "reset_requests": h.get("x-ratelimit-reset-requests") or h.get("x-ratelimit-reset"),
    }
    if snap["remaining_requests"] is None and snap["limit_requests"] is None and snap["remaining_tokens"] is None:
        return  # nothing useful in these headers
    with _LOCK:
        _STATE[provider] = snap


def get(provider: str) -> dict | None:
    with _LOCK:
        snap = _STATE.get(provider)
        return dict(snap) if snap else None
