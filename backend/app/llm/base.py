"""Provider-agnostic LLM interface.

Agents never talk to a vendor SDK directly — they go through `LLMService`,
which delegates to an `LLMProvider` and returns a uniform `LLMResponse`.
Swapping Claude for GPT/Gemini/Ollama later means adding a provider class,
not changing agents.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMMessage:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    text: str
    model: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: int | None = None
    raw: dict = field(default_factory=dict)


class LLMProvider(ABC):
    """A concrete backend (Anthropic, OpenAI, mock, …)."""

    name: str = "base"

    @abstractmethod
    def complete(
        self,
        *,
        messages: list[LLMMessage],
        model: str,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Run one completion and return a uniform response."""
        raise NotImplementedError
