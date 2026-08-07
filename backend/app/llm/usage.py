"""Usage stats derived from the AgentExecution audit log (one row per real LLM
call). Counts reflect calls made THROUGH THIS APP only — a key used elsewhere
won't be seen here. Free-tier caps are approximate and provider-published; only
the counts are exact.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.llm import catalog, ratelimit
from app.models import AgentExecution

# Approximate free-tier daily caps + when they reset. These drift; the UI labels
# them "approx" and links to each provider's live limits page.
PROVIDER_LIMITS = {
    "gemini": {
        "daily_limit": 250,
        "reset_tz": "America/Los_Angeles",
        "reset_label": "midnight Pacific (PT)",
        "note": "Flash tier (Flash-Lite ~1000/day). Estimate — Google exposes no live quota.",
    },
    "groq": {
        "daily_limit": 14400,
        "reset_tz": "UTC",
        "reset_label": "rolling + daily (UTC)",
        "note": "Real cap is tokens-per-minute (~6k TPM), not requests — pace, don't stop.",
    },
    "openrouter": {
        "daily_limit": 50,
        "reset_tz": "UTC",
        "reset_label": "midnight UTC",
        "note": "1000/day if you add $10 of credit.",
    },
}

PROVIDER_LABEL = {
    "gemini": "Google Gemini",
    "groq": "Groq",
    "openrouter": "OpenRouter",
    "anthropic": "Anthropic Claude",
    "ollama": "Ollama",
    "mock": "Mock (offline)",
    "unknown": "Other",
}


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _day_start_utc(tz_name: str) -> datetime:
    now = datetime.now(ZoneInfo(tz_name))
    return now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def _next_reset_utc(tz_name: str) -> datetime:
    now = datetime.now(ZoneInfo(tz_name))
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return nxt.astimezone(timezone.utc)


def compute_usage(db: Session, settings: Settings, session_since: str | None = None) -> dict:
    now_utc = datetime.now(timezone.utc)
    month_start = now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    session_dt = None
    if session_since:
        try:
            session_dt = _aware(datetime.fromisoformat(session_since.replace("Z", "+00:00")))
        except ValueError:
            session_dt = None

    rows = db.execute(select(AgentExecution.model, AgentExecution.created_at)).all()

    daystart_cache: dict[str, datetime] = {}

    def daystart(provider: str) -> datetime:
        tz = PROVIDER_LIMITS.get(provider, {}).get("reset_tz", "UTC")
        if tz not in daystart_cache:
            daystart_cache[tz] = _day_start_utc(tz)
        return daystart_cache[tz]

    agg: dict[str, dict[str, int]] = {}
    for model, created in rows:
        if not model:
            continue
        created = _aware(created)
        if created is None:
            continue
        provider = catalog.provider_for_model(model)
        counts = agg.setdefault(provider, {"today": 0, "month": 0, "session": 0})
        if created >= daystart(provider):
            counts["today"] += 1
        if created >= month_start:
            counts["month"] += 1
        if session_dt and created >= session_dt:
            counts["session"] += 1

    order = ["gemini", "groq", "openrouter"] + [
        p for p in agg if p not in ("gemini", "groq", "openrouter")
    ]
    seen: set[str] = set()
    providers: list[dict] = []
    for provider in order:
        if provider in seen:
            continue
        seen.add(provider)
        counts = agg.get(provider, {"today": 0, "month": 0, "session": 0})
        limits = PROVIDER_LIMITS.get(provider, {})
        daily = limits.get("daily_limit")
        # App-log estimate (our own successful calls vs the documented cap).
        remaining = max(0, daily - counts["today"]) if daily is not None else None
        reset_tz = limits.get("reset_tz")

        # If the provider reported real remaining in its response headers, that
        # is authoritative (matches its dashboard, counts external + retry
        # calls) — prefer it and mark the source accordingly.
        live = ratelimit.get(provider)
        source = "estimate"
        live_limit = None
        live_remaining = None
        if live and live.get("remaining_requests") is not None:
            live_remaining = live["remaining_requests"]
            live_limit = live.get("limit_requests") or daily
            remaining = live_remaining
            daily = live_limit or daily
            source = "provider"

        providers.append(
            {
                "provider": provider,
                "label": PROVIDER_LABEL.get(provider, provider),
                "ready": catalog.provider_ready(provider, settings),
                "today": counts["today"],
                "month": counts["month"],
                "session": counts["session"],
                "daily_limit": daily,
                "remaining_today": remaining,
                "source": source,
                "live_remaining_tokens": live.get("remaining_tokens") if live else None,
                "live_limit_tokens": live.get("limit_tokens") if live else None,
                "live_captured_at": live.get("captured_at") if live else None,
                "reset_label": limits.get("reset_label"),
                "next_reset_utc": _next_reset_utc(reset_tz).isoformat() if reset_tz else None,
                "note": limits.get("note"),
                "approx": source != "provider",
            }
        )

    return {
        "providers": providers,
        "counts_app_usage_only": True,
        "generated_at": now_utc.isoformat(),
    }
