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
FREE_MODELS: list[dict] = [
    {
        "provider": "gemini",
        "model": "gemini-flash-latest",
        "label": "Gemini Flash (latest)",
        "note": "Google · balanced, thinking",
    },
    {
        "provider": "gemini",
        "model": "gemini-flash-lite-latest",
        "label": "Gemini Flash-Lite",
        "note": "Google · fastest, cheapest",
    },
    {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "label": "Llama 3.3 70B",
        "note": "Groq · very fast, strong",
    },
    {
        "provider": "groq",
        "model": "llama-3.1-8b-instant",
        "label": "Llama 3.1 8B",
        "note": "Groq · instant, lightweight",
    },
    {
        "provider": "openrouter",
        "model": "deepseek/deepseek-r1:free",
        "label": "DeepSeek R1",
        "note": "OpenRouter · reasoning model",
    },
    {
        "provider": "openrouter",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "label": "Llama 3.3 70B (OR)",
        "note": "OpenRouter · free tier",
    },
    {
        "provider": "openrouter",
        "model": "qwen/qwen-2.5-72b-instruct:free",
        "label": "Qwen 2.5 72B",
        "note": "OpenRouter · free tier",
    },
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
