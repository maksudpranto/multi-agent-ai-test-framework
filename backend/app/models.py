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
    requirement_analysis = "requirement_analysis"
    test_generation = "test_generation"
    reviewer = "reviewer"
    consensus = "consensus"
    coverage = "coverage"
    quality = "quality"


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


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
    user_stories: Mapped[list["UserStory"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class UserStory(Base):
    __tablename__ = "user_stories"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    raw_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    project: Mapped["Project"] = relationship(back_populates="user_stories")
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(
        back_populates="user_story", cascade="all, delete-orphan"
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_story_id: Mapped[int] = mapped_column(
        ForeignKey("user_stories.id"), index=True
    )
    parent_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("pipeline_runs.id"), nullable=True
    )
    current_stage: Mapped[PipelineStage | None] = mapped_column(
        Enum(PipelineStage), nullable=True
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), default=RunStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user_story: Mapped["UserStory"] = relationship(back_populates="pipeline_runs")


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
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
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
    type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(50), nullable=True)
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
