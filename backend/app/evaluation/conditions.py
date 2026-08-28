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
    execution_grounded: bool = False
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
            execution_grounded=self.execution_grounded,
        )


CONDITIONS: dict[str, Condition] = {
    "single_llm": Condition(
        key="single_llm",
        label="Single AI",
        description=(
            "One AI writes the whole test suite from a single prompt — the "
            "baseline every other approach is measured against."
        ),
        mode=ExperimentMode.single_llm,
        is_baseline=True,
    ),
    "full_pipeline": Condition(
        key="full_pipeline",
        label="Agent team",
        description=(
            "A team of AI agents that hand off in turn and review and fix each "
            "other's tests before finishing — the complete framework."
        ),
        mode=ExperimentMode.multi_agent,
        reviewer_enabled=True,
        consensus_enabled=True,
    ),
    "ablation_no_debate": Condition(
        key="ablation_no_debate",
        label="Agent team, no self-review",
        description=(
            "The same agent team, but with the self-review step switched off — "
            "the step where one agent critiques the tests and another fixes them. "
            "This isolates how much that self-review adds."
        ),
        mode=ExperimentMode.multi_agent,
        reviewer_enabled=False,
        consensus_enabled=False,
    ),
    "grounded_debate": Condition(
        key="grounded_debate",
        label="Agent team, execution-grounded",
        description=(
            "The agent team, but the reviewer is shown how the tests actually "
            "behave when the inputs are run against a correct reference — so its "
            "critique is based on real execution evidence, not the model's guess. "
            "The seeded bugs are never shown, so nothing is leaked."
        ),
        mode=ExperimentMode.multi_agent,
        reviewer_enabled=True,
        consensus_enabled=True,
        execution_grounded=True,
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
