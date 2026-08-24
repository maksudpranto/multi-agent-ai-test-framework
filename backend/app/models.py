from datetime import datetime, timezone
import enum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PipelineStage(str, enum.Enum):
    planning = "planning"  # Orchestrator planner decisions (agentic control)
    requirement_analysis = "requirement_analysis"
    test_generation = "test_generation"
    reviewer = "reviewer"
    consensus = "consensus"
    prioritization = "prioritization"
    coverage = "coverage"
    quality = "quality"


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ExperimentMode(str, enum.Enum):
    single_llm = "single_llm"
    multi_agent = "multi_agent"


class ExecutionStatus(str, enum.Enum):
    success = "success"
    failed = "failed"


class GeneratedBy(str, enum.Enum):
    generator = "generator"
    consensus = "consensus"
    manual = "manual"


class TestCaseStatus(str, enum.Enum):
    draft = "draft"
    reviewer_flagged = "reviewer_flagged"
    consensus_resolved = "consensus_resolved"
    manual_approved = "manual_approved"
    rejected = "rejected"


class DebateSpeaker(str, enum.Enum):
    reviewer = "reviewer"
    generator = "generator"
    consensus = "consensus"


class ManualAction(str, enum.Enum):
    approve = "approve"
    edit = "edit"
    reject = "reject"


class ModuleStatus(str, enum.Enum):
    active = "active"
    on_hold = "on_hold"
    completed = "completed"
    archived = "archived"


class Priority(str, enum.Enum):
    """Shared priority scale for modules and requirements."""

    high = "high"
    medium = "medium"
    low = "low"


class RequirementType(str, enum.Enum):
    """The source form a requirement was captured in (§5)."""

    user_story = "user_story"
    acceptance_criteria = "acceptance_criteria"
    brd = "brd"
    prd = "prd"
    srs = "srs"
    use_case = "use_case"
    feature_description = "feature_description"


class RequirementStatus(str, enum.Enum):
    draft = "draft"
    ready = "ready"
    in_progress = "in_progress"
    done = "done"
    archived = "archived"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    projects: Mapped[list["Project"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    owner: Mapped["User"] = relationship(back_populates="projects")
    modules: Mapped[list["Module"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    requirements: Mapped[list["Requirement"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Dataset(Base):
    """A named collection of user stories for a domain (e.g. Banking,
    Ecommerce, Healthcare). Experiments run over a dataset so results can be
    reported per domain rather than mixing everything together."""

    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    domain: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    requirements: Mapped[list["Requirement"]] = relationship(
        back_populates="dataset"
    )


class Module(Base):
    """A feature / functional area within a project (§4). Requirements are
    grouped under modules; a module carries its own status and priority."""

    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ModuleStatus] = mapped_column(
        Enum(ModuleStatus), default=ModuleStatus.active
    )
    priority: Mapped[Priority] = mapped_column(Enum(Priority), default=Priority.medium)
    order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    project: Mapped["Project"] = relationship(back_populates="modules")
    requirements: Mapped[list["Requirement"]] = relationship(
        back_populates="module"
    )


class Requirement(Base):
    """A requirement in any supported source form (§5): user story, acceptance
    criteria, BRD, PRD, SRS, use case, or feature description. `raw_text` holds
    the requirement content (typed or extracted from an uploaded document)."""

    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    module_id: Mapped[int | None] = mapped_column(
        ForeignKey("modules.id"), nullable=True, index=True
    )
    dataset_id: Mapped[int | None] = mapped_column(
        ForeignKey("datasets.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    raw_text: Mapped[str] = mapped_column(Text)
    req_type: Mapped[RequirementType] = mapped_column(
        Enum(RequirementType), default=RequirementType.user_story
    )
    priority: Mapped[Priority] = mapped_column(Enum(Priority), default=Priority.medium)
    status: Mapped[RequirementStatus] = mapped_column(
        Enum(RequirementStatus), default=RequirementStatus.draft
    )
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    project: Mapped["Project"] = relationship(back_populates="requirements")
    module: Mapped["Module | None"] = relationship(back_populates="requirements")
    dataset: Mapped["Dataset | None"] = relationship(
        back_populates="requirements"
    )
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(
        back_populates="requirement", cascade="all, delete-orphan"
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("requirements.id"), index=True
    )
    experiment_id: Mapped[int | None] = mapped_column(
        ForeignKey("experiments.id"), nullable=True, index=True
    )
    parent_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("pipeline_runs.id"), nullable=True
    )
    mode: Mapped[ExperimentMode] = mapped_column(
        Enum(ExperimentMode), default=ExperimentMode.multi_agent
    )
    # How the run's acceptance criteria were obtained: "requirement" (derived by
    # the Analyzer from a user story) or "acceptance_criteria" (supplied directly
    # by the user, skipping analysis). Lets a user generate from either input.
    input_mode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Which experiment arm produced this run, e.g. "single_llm", "full_pipeline",
    # "ablation_no_debate". Needed because full_pipeline and its ablations share
    # mode=multi_agent; this is the key the evaluation aggregation groups by.
    experiment_condition: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )
    current_stage: Mapped[PipelineStage | None] = mapped_column(
        Enum(PipelineStage), nullable=True
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), default=RunStatus.pending
    )
    # Which repetition of a repeated experiment this run belongs to (1-based).
    # LLM generation is not perfectly reproducible, so an experiment can be run
    # several times; each cell (item x condition) then has one run per repetition.
    repetition: Mapped[int] = mapped_column(Integer, default=1)
    # Fault-detection detail for an evaluation run: the harvested inputs and, per
    # seeded bug, whether this run's suite killed it and which input exposed it.
    # Persisted so the results drill-down can show the concrete bug/test/verdict
    # without re-running the (LLM-driven, non-deterministic) materializer.
    eval_detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    requirement: Mapped["Requirement"] = relationship(back_populates="pipeline_runs")


class AgentExecution(Base):
    __tablename__ = "agent_executions"

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_run_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_runs.id"), index=True
    )
    stage: Mapped[PipelineStage] = mapped_column(Enum(PipelineStage))
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    raw_input: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("prompt_templates.id"), nullable=True
    )
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus), default=ExecutionStatus.success
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AcceptanceCriterion(Base):
    __tablename__ = "acceptance_criteria"

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_run_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_runs.id"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    order: Mapped[int] = mapped_column(Integer, default=0)


class RequirementAnalysis(Base):
    __tablename__ = "requirement_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_run_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_runs.id"), index=True
    )
    actors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    preconditions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    main_flow: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    alt_flows: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ambiguities: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_run_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_runs.id"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_test_case_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_cases.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500))
    steps: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    expected_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Concrete mock/test data for the case: e.g.
    # {"valid": {...}, "invalid": {...}, "boundary": [...]} so a case is
    # executable, not just described. Shape is free-form per test type.
    test_data: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Assigned by the Prioritizer agent: severity (critical|major|minor) and a
    # numeric rank for ordering the suite by importance. Null until prioritised.
    severity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    traces_to: Mapped[int | None] = mapped_column(
        ForeignKey("acceptance_criteria.id"), nullable=True
    )
    generated_by: Mapped[GeneratedBy] = mapped_column(
        Enum(GeneratedBy), default=GeneratedBy.generator
    )
    status: Mapped[TestCaseStatus] = mapped_column(
        Enum(TestCaseStatus), default=TestCaseStatus.draft
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DebateTurn(Base):
    __tablename__ = "debate_turns"

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_run_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_runs.id"), index=True
    )
    test_case_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_cases.id"), nullable=True
    )
    round: Mapped[int] = mapped_column(Integer, default=1)
    speaker: Mapped[DebateSpeaker] = mapped_column(Enum(DebateSpeaker))
    content: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CoverageReport(Base):
    __tablename__ = "coverage_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_run_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_runs.id"), index=True
    )
    acceptance_criterion_id: Mapped[int] = mapped_column(
        ForeignKey("acceptance_criteria.id")
    )
    covered: Mapped[bool] = mapped_column(Boolean, default=False)
    covering_test_case_ids: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    gap_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class QualityReport(Base):
    __tablename__ = "quality_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_run_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_runs.id"), index=True
    )
    test_case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"))
    clarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    atomicity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    traceability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    duplicate_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ManualReview(Base):
    __tablename__ = "manual_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    test_case_id: Mapped[int] = mapped_column(
        ForeignKey("test_cases.id"), index=True
    )
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[ManualAction] = mapped_column(Enum(ManualAction))
    edited_content: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ExportLog(Base):
    __tablename__ = "export_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_run_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_runs.id"), index=True
    )
    format: Mapped[str] = mapped_column(String(20))
    test_case_version_ids: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ---------------------------------------------------------------------------
# Research-platform tables: prompts, experiments, configs, metrics.
# These make experiments a first-class, reproducible concept (single-LLM
# baseline vs multi-agent) rather than something bolted on for evaluation.
# ---------------------------------------------------------------------------


class PromptTemplate(Base):
    """Versioned prompt text for a pipeline stage, stored as data (not code)
    so prompts can be iterated and every AgentExecution can be traced back to
    the exact prompt that produced it."""

    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    stage: Mapped[PipelineStage] = mapped_column(Enum(PipelineStage), index=True)
    version: Mapped[str] = mapped_column(String(50))
    template: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ExperimentConfig(Base):
    """A named, reusable configuration for a run: model, sampling params, and
    which stages are enabled. Keeps values out of the code so experiments are
    declarative and reproducible."""

    __tablename__ = "experiment_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    llm_model: Mapped[str] = mapped_column(String(100))
    temperature: Mapped[float] = mapped_column(Float, default=0.0)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)
    reviewer_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    consensus_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    coverage_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    quality_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    max_debate_rounds: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Experiment(Base):
    """A first-class experiment: run a dataset through the pipeline in a given
    mode (single-LLM baseline or multi-agent) with a fixed config. This is the
    unit the thesis compares."""

    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    dataset_id: Mapped[int | None] = mapped_column(
        ForeignKey("datasets.id"), nullable=True
    )
    config_id: Mapped[int | None] = mapped_column(
        ForeignKey("experiment_configs.id"), nullable=True
    )
    mode: Mapped[ExperimentMode] = mapped_column(Enum(ExperimentMode))
    # The experiment arms to run, e.g. ["single_llm", "full_pipeline",
    # "ablation_no_debate"]. `mode` is kept for back-compat / the legacy toggle;
    # `conditions` is the authoritative list the evaluation runner iterates over
    # (one PipelineRun per benchmark item x condition x repetition).
    conditions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # How many times to run the whole grid. >1 averages out LLM run-to-run
    # noise and yields a reported reproducibility spread (std across repetitions).
    repetitions: Mapped[int] = mapped_column(Integer, default=1)
    # "full" runs every benchmark program; "quick" runs a small representative
    # subset (corpus.QUICK_SLUGS) so a run is cheap/fast during iteration. The
    # thesis result uses "full"; "quick" is for development.
    scope: Mapped[str] = mapped_column(String(20), default="full")
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), default=RunStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ExperimentMetric(Base):
    """A precomputed metric value, either per pipeline run or aggregated for an
    experiment (pipeline_run_id NULL). Stored so the evaluation dashboard is a
    query, not a recomputation."""

    __tablename__ = "experiment_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("experiments.id"), index=True
    )
    pipeline_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("pipeline_runs.id"), nullable=True
    )
    metric_name: Mapped[str] = mapped_column(String(100), index=True)
    metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ---------------------------------------------------------------------------
# Benchmark tables: the executable micro-benchmark the fault-based evaluation
# runs against. Each item is a small program with a natural-language
# requirement (a real Requirement row, so the pipeline generates tests from it),
# a reference implementation that acts as the test oracle, and a set of seeded
# bug variants (mutants). "Mutation score" = fraction of mutants a generated
# suite's inputs kill (make diverge from the reference). This is what turns the
# app from a demo into a thesis: we RUN the tests against injected bugs.
# ---------------------------------------------------------------------------


class BenchmarkItem(Base):
    """One executable program in the benchmark corpus. Bound to a Requirement
    (so the pipeline generates tests from its NL description) and a Dataset (the
    'Benchmark Suite'). Holds the reference implementation (the oracle) plus the
    entrypoint and canonical inputs the fault-detection harness needs."""

    __tablename__ = "benchmark_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id"), index=True
    )
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("requirements.id"), index=True
    )
    slug: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(255))
    entrypoint: Mapped[str] = mapped_column(String(100))
    signature: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Positional-parameter descriptors [{name, type, note}], to help the
    # materializer produce well-typed argument lists for the entrypoint.
    params: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Deterministic fallback argument lists (list of positional-arg lists) used
    # when the LLM materializer produces unusable output. Guarantees the harness
    # always has valid inputs so a run never silently scores zero.
    canonical_inputs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    reference_code: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    requirement: Mapped["Requirement"] = relationship()
    mutants: Mapped[list["BenchmarkMutant"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class BenchmarkMutant(Base):
    """A single seeded bug: the reference implementation with one deliberate
    fault. The harness runs it on the harvested inputs; the mutant is 'killed'
    if its behaviour diverges from the reference on any input."""

    __tablename__ = "benchmark_mutants"

    id: Mapped[int] = mapped_column(primary_key=True)
    benchmark_item_id: Mapped[int] = mapped_column(
        ForeignKey("benchmark_items.id"), index=True
    )
    mutant_key: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The fault class this seeded bug represents (boundary / wrong_constant /
    # wrong_operator / missing_condition / control_flow), from the corpus'
    # FAULT_TYPES taxonomy. Lets the evaluation report fault detection by class.
    fault_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    code: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    item: Mapped["BenchmarkItem"] = relationship(back_populates="mutants")
