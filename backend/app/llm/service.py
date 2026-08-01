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


def _extract_user_story(raw: str) -> str:
    """Pull the user-story text out of a formatted prompt so the mock can echo it
    back and produce story-specific (not hardcoded) output offline."""
    low = raw.lower()
    idx = low.find("user story:")
    seg = raw[idx + len("user story:") :] if idx != -1 else raw
    seg = seg.replace('"""', " ")
    for marker in ("return only", "acceptance criteria", "current test cases"):
        cut = seg.lower().find(marker)
        if cut != -1:
            seg = seg[:cut]
    return " ".join(seg.split()).strip()


def _story_labels(raw: str) -> tuple[str, str]:
    """(feature, subject): a short feature phrase and a longer subject line,
    both derived from the actual story so different stories differ."""
    story = _extract_user_story(raw)
    if not story:
        return "the feature", "the described behaviour"
    words = story.split()
    feature = " ".join(words[:8])
    subject = story if len(story) <= 90 else " ".join(words[:14]) + "…"
    return feature, subject


def _dev_mock_responder(messages, system) -> str:
    """Dev-only fallback used when no API key is configured, so the FULL pipeline
    — requirement analysis, test generation, the reviewer<->consensus debate, and
    the single-LLM baseline — runs offline and free. Each branch keys off a unique
    marker in the seeded prompt and returns a schema-valid JSON reply.

    It is a STUB: it echoes the story so output varies per story, but it does not
    reason. For genuine, domain-aware edge cases and mock data, set LLM_PROVIDER
    to a real free provider (ollama / gemini).

    Reviewer/consensus/baseline are matched before test-generation because their
    prompts also embed the "acceptance criteria (database ids...)" phrase."""
    raw = " ".join(m.content for m in messages)
    text = raw.lower()

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
                            "test_data": {
                                "valid": {"input": "explicit sample value"},
                                "invalid": {"input": "malformed value"},
                            },
                        },
                    }
                ]
            }
        )

    # --- Prioritizer: rank each current test case (annotation only). ---
    if "you are a test prioritization specialist" in text:
        tail = text.split("current test cases", 1)[-1]
        ids = [int(m) for m in re.findall(r'"id":\s*(\d+)', tail)]
        # Deterministic offline ranking: keep input order, high->low priority as
        # we go down. A real provider reasons about business impact.
        rankings = []
        for i, tc_id in enumerate(ids):
            priority = "high" if i < max(1, len(ids) // 3) else (
                "medium" if i < max(2, 2 * len(ids) // 3) else "low"
            )
            severity = "critical" if i == 0 else ("major" if priority != "low" else "minor")
            rankings.append(
                {
                    "test_case_id": tc_id,
                    "priority": priority,
                    "severity": severity,
                    "rank": i + 1,
                    "rationale": "Ranked by position in the reviewed suite (offline stub).",
                }
            )
        return json.dumps({"rankings": rankings})

    # --- Coverage analyst: judge adequacy per criterion. ---
    if "you are a test coverage analyst" in text:
        ids = [int(m) for m in re.findall(r'"acceptance_criterion_id":\s*(\d+)', text)]
        return json.dumps(
            {
                "assessments": [
                    {
                        "acceptance_criterion_id": cid,
                        "adequate": True,
                        "gap_notes": "Adequately covered by the mapped cases (offline stub).",
                    }
                    for cid in dict.fromkeys(ids)  # de-dup, keep order
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
                        "test_data": {"valid": {"input": "well-formed value"}},
                    },
                    {
                        "title": "Invalid input is rejected",
                        "steps": ["Open the feature", "Provide invalid input", "Submit"],
                        "expected_result": "An error is shown and the action is denied",
                        "type": "negative",
                        "priority": "medium",
                        "test_data": {"invalid": {"input": "bad value"}},
                    },
                ]
            }
        )

    if "acceptance_criteria" in text and "main_flow" in text:
        feature, subject = _story_labels(raw)
        return json.dumps(
            {
                "actors": ["End User", "System"],
                "preconditions": [f"The user can access {feature}"],
                "main_flow": [
                    f"User opens {feature}",
                    "User provides the required input",
                    "User submits the action",
                    "System processes the request and returns the result",
                ],
                "alt_flows": [
                    "Invalid input: the system shows an error and does not proceed",
                    "Missing required input: the system prompts for it",
                ],
                "acceptance_criteria": [
                    {"id": "AC1", "text": f"With valid input, {subject} succeeds"},
                    {"id": "AC2", "text": f"With invalid input, {feature} is rejected with a clear error"},
                    {"id": "AC3", "text": f"Required fields for {feature} cannot be empty"},
                ],
                "ambiguities": [
                    f"Boundary limits for {feature} are not specified",
                    "Authorization / permission rules are not described",
                ],
            }
        )
    if "acceptance criteria (database ids are authoritative)" in text:
        criteria = re.findall(r'"id"\s*:\s*(\d+).*?"text"\s*:\s*"([^"]+)"', text)
        cases = []
        for criterion_id, criterion_text in criteria:
            cid = int(criterion_id)
            # A small suite per criterion (functional + negative + boundary),
            # each with concrete mock data — so the offline path exercises the
            # rich schema. A real provider produces genuinely varied suites.
            cases.append(
                {
                    "acceptance_criterion_id": cid,
                    "title": f"Functional: {criterion_text}",
                    "steps": [
                        "Open the relevant feature",
                        "Enter the specified valid input",
                        "Submit the action",
                    ],
                    "expected_result": criterion_text,
                    "type": "functional",
                    "priority": "high",
                    "test_data": {"valid": {"input": "well-formed sample value"}},
                }
            )
            cases.append(
                {
                    "acceptance_criterion_id": cid,
                    "title": f"Negative: invalid input is rejected for AC{cid}",
                    "steps": [
                        "Open the relevant feature",
                        "Enter malformed / invalid input",
                        "Submit the action",
                    ],
                    "expected_result": "A clear validation error is shown and the action does not proceed",
                    "type": "negative",
                    "priority": "medium",
                    "test_data": {"invalid": {"input": "!!! not valid !!!"}},
                }
            )
            cases.append(
                {
                    "acceptance_criterion_id": cid,
                    "title": f"Boundary: edge values for AC{cid}",
                    "steps": [
                        "Open the relevant feature",
                        "Enter boundary values (empty, minimum, maximum)",
                        "Submit the action",
                    ],
                    "expected_result": "Each boundary value is handled correctly per the specification",
                    "type": "boundary",
                    "priority": "medium",
                    "test_data": {"boundary": ["", "min", "max", "max-length-string"]},
                }
            )
        return json.dumps({"test_cases": cases})
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
