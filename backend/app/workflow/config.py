from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings
from app.models import ExperimentConfig


@dataclass
class RunConfig:
    """Resolved configuration for one pipeline run. Built either from an
    ExperimentConfig row (research runs) or from defaults (ad-hoc runs), so the
    engine never reads settings or hardcodes values itself."""

    model: str
    temperature: float = 0.0
    # Headroom for "thinking" models (Gemini 2.5/3.x flash spend part of this
    # budget on internal reasoning before emitting the JSON answer).
    max_tokens: int = 8192
    reviewer_enabled: bool = True
    consensus_enabled: bool = True
    coverage_enabled: bool = True
    quality_enabled: bool = True
    max_debate_rounds: int = 3

    @classmethod
    def defaults(cls) -> "RunConfig":
        return cls(model=get_settings().effective_model)

    @classmethod
    def from_experiment_config(cls, cfg: ExperimentConfig) -> "RunConfig":
        return cls(
            model=cfg.llm_model,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            reviewer_enabled=cfg.reviewer_enabled,
            consensus_enabled=cfg.consensus_enabled,
            coverage_enabled=cfg.coverage_enabled,
            quality_enabled=cfg.quality_enabled,
            max_debate_rounds=cfg.max_debate_rounds,
        )
