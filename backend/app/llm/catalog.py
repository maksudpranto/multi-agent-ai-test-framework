"""Curated catalog of free models the UI offers for per-run selection.

This is the single source of truth: the /meta/models endpoint annotates each
entry with whether its provider is configured (key present), and the pipeline
routes validate an incoming {provider, model} selection against it.
"""
from __future__ import annotations

from app.config import Settings

# label      — shown in the UI dropdown
# provider   — which backend/key it runs on
# model      — the exact model id sent to the provider
# note       — short hint (speed / character), shown as a sublabel
# NOTE: provider catalogs change over time — model ids get retired. Keep this in
# sync with what the keys can actually call (Groq retired the Llama-3.x ids that
# used to live here, which made every run 404). Gemini Flash-Lite is listed first
# because it reliably returns the strict JSON our agents need; the Groq gpt-oss
# and OpenRouter models are reasoning/`:free` models that can be flakier.
FREE_MODELS: list[dict] = [
    {
        "provider": "gemini",
        "model": "gemini-flash-lite-latest",
        "label": "Gemini Flash-Lite",
        "note": "Google · fast, reliable (recommended)",
    },
    {
        "provider": "gemini",
        "model": "gemini-flash-latest",
        "label": "Gemini Flash (latest)",
        "note": "Google · balanced, thinking",
    },
    {
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "label": "GPT-OSS 120B",
        "note": "Groq · very fast, strong (reasoning)",
    },
    {
        "provider": "groq",
        "model": "openai/gpt-oss-20b",
        "label": "GPT-OSS 20B",
        "note": "Groq · instant, lightweight (reasoning)",
    },
    # OpenRouter's ':free' catalog changes often — verify before relying on these.
    {
        "provider": "openrouter",
        "model": "openai/gpt-oss-20b:free",
        "label": "GPT-OSS 20B (OpenRouter)",
        "note": "OpenRouter · OpenAI open model",
    },
    {
        "provider": "openrouter",
        "model": "nvidia/nemotron-nano-9b-v2:free",
        "label": "Nemotron Nano 9B",
        "note": "OpenRouter · fast, lightweight",
    },
    # Claude (Anthropic) — PAID. Hidden from the picker for now (the API account
    # needs prepaid credits). To re-enable, uncomment these two entries:
    # {"provider": "anthropic", "model": "claude-sonnet-4-5",
    #  "label": "Claude Sonnet 4.5", "note": "Anthropic · paid · strong general model", "paid": True},
    # {"provider": "anthropic", "model": "claude-haiku-4-5-20251001",
    #  "label": "Claude Haiku 4.5", "note": "Anthropic · paid · fast & lower-cost", "paid": True},
]


def provider_ready(provider: str, settings: Settings) -> bool:
    """True when the provider can actually be used (its key/host is configured)."""
    provider = provider.lower().strip()
    if provider == "gemini":
        return bool(settings.gemini_api_key)
    if provider == "groq":
        return bool(settings.groq_api_key)
    if provider == "openrouter":
        return bool(settings.openrouter_api_key)
    if provider == "anthropic":
        return bool(settings.anthropic_api_key)
    if provider in ("ollama", "mock"):
        return True
    return False


def find(provider: str, model: str) -> dict | None:
    provider = (provider or "").lower().strip()
    for entry in FREE_MODELS:
        if entry["provider"] == provider and entry["model"] == model:
            return entry
    return None


def annotated(settings: Settings) -> list[dict]:
    """Catalog entries + a `ready` flag, for the UI to enable/disable options."""
    return [{**entry, "ready": provider_ready(entry["provider"], settings)} for entry in FREE_MODELS]


_MODEL_TO_PROVIDER = {e["model"]: e["provider"] for e in FREE_MODELS}


def provider_for_model(model: str | None) -> str:
    """Best-effort provider name for a recorded model id (used by usage stats).

    Prefers the exact catalog match, then falls back to id conventions:
    OpenRouter ids carry a 'org/model' slash; Gemini/Claude have clear prefixes;
    bare Llama ids come from Groq."""
    if not model:
        return "unknown"
    if model in _MODEL_TO_PROVIDER:
        return _MODEL_TO_PROVIDER[model]
    m = model.lower()
    if "/" in model:
        return "openrouter"
    if m.startswith("gemini"):
        return "gemini"
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith("mock"):
        return "mock"
    if "llama" in m or "versatile" in m or "instant" in m or "qwen" in m:
        return "groq"
    return "unknown"
