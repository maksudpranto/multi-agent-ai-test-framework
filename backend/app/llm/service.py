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
    """Dev-only fallback used when no API key is configured, so the FULL pipeline
    — requirement analysis, test generation, the reviewer<->consensus debate, and
    the single-LLM baseline — runs offline and free. Each branch keys off a unique
    marker in the seeded prompt and returns a schema-valid JSON reply.

    Reviewer/consensus/baseline are matched before test-generation because their
    prompts also embed the "acceptance criteria (database ids...)" phrase."""
    text = " ".join(m.content for m in messages).lower()

    # --- Reviewer: flag once on round 1, be satisfied from round 2 (so the
    # debate terminates by consensus rather than by hitting max rounds). ---
    if "you are a meticulous qa reviewer" in text:
        round_match = re.search(r"debate round:\s*(\d+)", text)
        round_no = int(round_match.group(1)) if round_match else 1
        if round_no >= 2:
            return json.dumps({"needs_revision": False, "findings": []})
        tail = text.split("current test cases", 1)[-1]
        tc_id = re.search(r'"id":\s*(\d+)', tail)
        ac_id = re.search(r'"acceptance_criterion_id":\s*(\d+)', tail)
        return json.dumps(
            {
                "needs_revision": True,
                "findings": [
                    {
                        "test_case_id": int(tc_id.group(1)) if tc_id else None,
                        "acceptance_criterion_id": int(ac_id.group(1)) if ac_id else None,
                        "issue_type": "weak_steps",
                        "severity": "medium",
                        "description": (
                            "Steps are too vague to execute unambiguously and no "
                            "negative path is covered."
                        ),
                        "suggestion": "Specify concrete input data and add an invalid-input case.",
                    }
                ],
            }
        )

    # --- Consensus: agree with the reviewer and revise the flagged case. ---
    if "you are the consensus agent" in text:
        ftail = text.split("reviewer findings", 1)[-1]
        tc_id = re.search(r'"test_case_id":\s*(\d+)', ftail)
        ac_id = re.search(r'"acceptance_criterion_id":\s*(\d+)', ftail)
        acid = int(ac_id.group(1)) if ac_id else 1
        return json.dumps(
            {
                "resolutions": [
                    {
                        "test_case_id": int(tc_id.group(1)) if tc_id else None,
                        "acceptance_criterion_id": acid,
                        "decision": "revise",
                        "rationale": (
                            "The reviewer is right that the steps were vague; tightening "
                            "them and adding explicit input data."
                        ),
                        "revised_test_case": {
                            "acceptance_criterion_id": acid,
                            "title": "Verify behaviour with explicit, unambiguous steps",
                            "steps": [
                                "Open the relevant feature",
                                "Enter the specified valid input values",
                                "Submit the form",
                                "Observe the resulting state",
                            ],
                            "expected_result": "The system produces the specified verifiable outcome",
                            "type": "functional",
                            "priority": "high",
                        },
                    }
                ]
            }
        )

    # --- Single-LLM baseline: story -> a couple of untraceable test cases. ---
    if "single-llm baseline" in text:
        return json.dumps(
            {
                "test_cases": [
                    {
                        "title": "Happy path works end to end",
                        "steps": [
                            "Open the feature described in the story",
                            "Provide valid input",
                            "Submit",
                        ],
                        "expected_result": "The primary action succeeds",
                        "type": "functional",
                        "priority": "high",
                    },
                    {
                        "title": "Invalid input is rejected",
                        "steps": ["Open the feature", "Provide invalid input", "Submit"],
                        "expected_result": "An error is shown and the action is denied",
                        "type": "negative",
                        "priority": "medium",
                    },
                ]
            }
        )

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
    if "acceptance criteria (database ids are authoritative)" in text:
        criteria = re.findall(r'"id"\s*:\s*(\d+).*?"text"\s*:\s*"([^"]+)"', text)
        return json.dumps(
            {
                "test_cases": [
                    {
                        "acceptance_criterion_id": int(criterion_id),
                        "title": f"Verify {criterion_text}",
                        "steps": [
                            "Open the relevant feature",
                            "Perform the action described by the acceptance criterion",
                        ],
                        "expected_result": criterion_text,
                        "type": "functional",
                        "priority": "medium",
                    }
                    for criterion_id, criterion_text in criteria
                ]
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
