"""The experiment arms (conditions) the evaluation compares.

Each condition is one way of turning a requirement into a test suite. They share
the exact same agents and engine — a condition only differs in *which* stages run
(via RunConfig toggles) or whether the single-LLM baseline is used instead of the
multi-agent pipeline. Keeping them declarative here means the runner, the API,
and the dashboard all agree on the same set, and adding an arm is a one-line
change rather than a code fork.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models import ExperimentMode
from app.workflow.config import RunConfig


@dataclass(frozen=True)
class Condition:
    """One experiment arm. ``mode`` selects baseline vs multi-agent; the toggle
    fields are applied onto the base RunConfig to realise ablations."""

    key: str
    label: str
    description: str
    mode: ExperimentMode
    reviewer_enabled: bool = True
    consensus_enabled: bool = True
    coverage_enabled: bool = True
    quality_enabled: bool = True
    is_baseline: bool = False

    def apply(self, base: RunConfig) -> RunConfig:
        """Return a copy of ``base`` with this condition's toggles applied."""
        return RunConfig(
            model=base.model,
            temperature=base.temperature,
            max_tokens=base.max_tokens,
            reviewer_enabled=self.reviewer_enabled,
            consensus_enabled=self.consensus_enabled,
            coverage_enabled=self.coverage_enabled,
            quality_enabled=self.quality_enabled,
            max_debate_rounds=base.max_debate_rounds,
        )


CONDITIONS: dict[str, Condition] = {
    "single_llm": Condition(
        key="single_llm",
        label="Single-LLM baseline",
        description=(
            "One prompt turns the requirement straight into test cases — the "
            "control arm every other condition is measured against."
        ),
        mode=ExperimentMode.single_llm,
        is_baseline=True,
    ),
    "full_pipeline": Condition(
        key="full_pipeline",
        label="Full multi-agent pipeline",
        description=(
            "Analysis, generation, the Reviewer<->Consensus debate, coverage, "
            "quality, and prioritisation — the complete framework."
        ),
        mode=ExperimentMode.multi_agent,
        reviewer_enabled=True,
        consensus_enabled=True,
    ),
    "ablation_no_debate": Condition(
        key="ablation_no_debate",
        label="Multi-agent, no debate",
        description=(
            "The multi-agent pipeline with the Reviewer<->Consensus debate turned "
            "off, isolating how much the debate itself contributes."
        ),
        mode=ExperimentMode.multi_agent,
        reviewer_enabled=False,
        consensus_enabled=False,
    ),
}

# The MVP study: baseline vs full pipeline vs the no-debate ablation.
DEFAULT_CONDITIONS: list[str] = ["single_llm", "full_pipeline", "ablation_no_debate"]

# The arm every comparison is made against.
BASELINE_KEY = "single_llm"


def resolve_conditions(keys: list[str] | None) -> list[Condition]:
    """Validate and order a list of condition keys. Unknown keys are dropped;
    an empty/None list yields the default study. The baseline is always first so
    the runner and the stats agree on the reference arm."""
    keys = keys or DEFAULT_CONDITIONS
    chosen = [CONDITIONS[k] for k in keys if k in CONDITIONS]
    if not chosen:
        chosen = [CONDITIONS[k] for k in DEFAULT_CONDITIONS]
    chosen.sort(key=lambda c: (not c.is_baseline, c.key))
    return chosen
