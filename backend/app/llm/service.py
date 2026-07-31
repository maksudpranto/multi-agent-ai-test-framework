from __future__ import annotations

import json
import re
from functools import lru_cache

from app.config import get_settings
from app.llm.base import LLMMessage, LLMProvider, LLMResponse

_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", re.DOTALL)


class LLMService:
    """Facade the rest of the app uses. Wraps a provider and adds a
    structured-output helper so agents get parsed JSON back."""

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def complete(
        self,
        *,
        messages: list[LLMMessage],
        model: str,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        return self.provider.complete(
            messages=messages,
            model=model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def complete_json(
        self,
        *,
        prompt: str,
        model: str,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> tuple[dict | list, LLMResponse]:
        """Run a completion and parse a JSON object/array from the reply.

        Returns (parsed, raw_response). Raises ValueError if no JSON is found,
        so callers can log the raw output and retry.
        """
        response = self.complete(
            messages=[LLMMessage(role="user", content=prompt)],
            model=model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return extract_json(response.text), response


def extract_json(text: str) -> dict | list:
    """Best-effort JSON extraction: whole string, fenced block, or first
    balanced object/array in the text."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = _JSON_FENCE.search(text)
    if fenced:
        return json.loads(fenced.group(1))

    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue

    raise ValueError("No JSON object/array found in model output")


def _dev_mock_responder(messages, system) -> str:
    """Dev-only fallback used when no API key is configured, so the pipeline
    produces something realistic offline. Returns a plausible requirement
    analysis when the prompt is one; otherwise an empty JSON object."""
    text = " ".join(m.content for m in messages).lower()
    if "acceptance_criteria" in text and "main_flow" in text:
        return json.dumps(
            {
                "actors": ["End User", "Authentication Service"],
                "preconditions": ["The user has a registered account"],
                "main_flow": [
                    "User opens the login screen",
                    "User enters email and password",
                    "User submits the form",
                    "System validates credentials and grants access",
                ],
                "alt_flows": [
                    "Invalid credentials: system shows an error and denies access",
                    "Empty fields: system prompts for required input",
                ],
                "acceptance_criteria": [
                    {"id": "AC1", "text": "Valid credentials grant access to the dashboard"},
                    {"id": "AC2", "text": "Invalid credentials show an error and deny access"},
                    {"id": "AC3", "text": "Empty email or password is rejected with a prompt"},
                ],
                "ambiguities": [
                    "Account lockout policy after repeated failures is unspecified",
                    "Password complexity / reset flow is not described",
                ],
            }
        )
    return "{}"


def build_provider() -> LLMProvider:
    """Build the explicitly configured LLM provider.

    Mock is the default so development and tests work without an external API.
    """
    settings = get_settings()
    provider = settings.llm_provider.lower().strip()

    if provider == "mock":
        from app.llm.mock_provider import MockProvider

        return MockProvider(responder=_dev_mock_responder)

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(api_key=settings.anthropic_api_key)

    if provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        from app.llm.gemini_provider import GeminiProvider

        return GeminiProvider(api_key=settings.gemini_api_key)

    if provider == "ollama":
        from app.llm.ollama_provider import OllamaProvider

        return OllamaProvider(base_url=settings.ollama_base_url)

    raise ValueError(
        f"Unsupported LLM_PROVIDER={settings.llm_provider!r}. "
        "Choose mock, anthropic, gemini, or ollama."
    )


@lru_cache
def get_llm_service() -> LLMService:
    return LLMService(build_provider())
