"""Workflow orchestration.

`WorkflowEngine` is an interface so a future LangGraph/CrewAI/AutoGen engine can
replace `DefaultWorkflowEngine` without touching agents or routes. The default
engine runs one stage at a time, logs an `AgentExecution` row for every attempt,
and lets each agent persist its own artifacts.

Beyond single stages it also runs:
- `run_debate`   — the bounded, bidirectional Reviewer <-> Consensus debate that
  is the multi-agent core: it loops rounds, terminates when the reviewer is
  satisfied or `max_debate_rounds` is hit, records a `DebateTurn` transcript,
  and versions `TestCase` rows produced by consensus.
- `run_baseline` — the single-LLM control arm (one prompt, story -> test cases).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import Agent, AgentContext, AgentResult
from app.llm import LLMService, get_llm_service
from app.models import (
    AgentExecution,
    DebateSpeaker,
    DebateTurn,
    ExecutionStatus,
    GeneratedBy,
    PipelineRun,
    PipelineStage,
    TestCase,
    TestCaseStatus,
)
from app.prompts.seed import get_active_prompt, get_prompt
from app.workflow.config import RunConfig


class WorkflowEngine(ABC):
    @abstractmethod
    def run_stage(
        self,
        db: Session,
        run: PipelineRun,
        stage: PipelineStage,
        inputs: dict[str, Any],
        config: RunConfig,
    ) -> AgentResult:
        raise NotImplementedError


class DefaultWorkflowEngine(WorkflowEngine):
    def __init__(self, llm_service: LLMService | None = None):
        self.llm = llm_service or get_llm_service()

    def _agent_for(self, stage: PipelineStage) -> Agent:
        # Imported here to avoid a circular import (agents import the engine's
        # config type). Extended per phase as new agents are added.
        if stage == PipelineStage.requirement_analysis:
            from app.agents.requirement_analysis import RequirementAnalysisAgent

            return RequirementAnalysisAgent(self.llm)
        if stage == PipelineStage.test_generation:
            from app.agents.test_generation import TestGenerationAgent

            return TestGenerationAgent(self.llm)
        if stage == PipelineStage.reviewer:
            from app.agents.reviewer import ReviewerAgent

            return ReviewerAgent(self.llm)
        if stage == PipelineStage.consensus:
            from app.agents.consensus import ConsensusAgent

            return ConsensusAgent(self.llm)
        raise NotImplementedError(f"No agent registered for stage {stage.value}")

    # -- low-level: run one agent and log an AgentExecution row ---------------
    def _run_agent_logged(
        self,
        db: Session,
        run: PipelineRun,
        stage: PipelineStage,
        inputs: dict[str, Any],
        config: RunConfig,
        *,
        agent: Agent | None = None,
        prompt_version: str | None = None,
    ) -> tuple[Agent, AgentResult]:
        """Resolve the prompt, run the agent, and write the audit row. Does NOT
        persist stage artifacts — the caller decides how (single stage vs debate)."""
        agent = agent or self._agent_for(stage)

        attempt_no = (
            db.query(AgentExecution)
            .filter(
                AgentExecution.pipeline_run_id == run.id,
                AgentExecution.stage == stage,
            )
            .count()
            + 1
        )

        prompt = (
            get_prompt(db, stage, prompt_version)
            if prompt_version
            else get_active_prompt(db, stage)
        )
        if prompt is None:
            raise RuntimeError(
                f"No prompt template seeded for stage {stage.value}"
                + (f" version {prompt_version}" if prompt_version else "")
            )

        ctx = AgentContext(
            inputs=inputs,
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            prompt_template=prompt.template,
            prompt_template_id=prompt.id,
            prompt_version=prompt.version,
        )
        result = agent.run(ctx)

        execution = AgentExecution(
            pipeline_run_id=run.id,
            stage=stage,
            attempt_no=attempt_no,
            raw_input=result.input or inputs,
            raw_output=result.output,
            reasoning=result.reasoning,
            model=result.metrics.get("model"),
            prompt_template_id=result.metrics.get("prompt_template_id"),
            prompt_version=result.metrics.get("prompt_version"),
            tokens_in=result.metrics.get("tokens_in"),
            tokens_out=result.metrics.get("tokens_out"),
            latency_ms=result.execution_time_ms,
            status=ExecutionStatus.success if result.success else ExecutionStatus.failed,
            error=result.error,
        )
        db.add(execution)
        db.flush()
        return agent, result

    def run_stage(
        self,
        db: Session,
        run: PipelineRun,
        stage: PipelineStage,
        inputs: dict[str, Any],
        config: RunConfig,
    ) -> AgentResult:
        agent, result = self._run_agent_logged(db, run, stage, inputs, config)
        # Stage-specific persistence (e.g. RequirementAnalysis rows).
        if result.success:
            agent.persist(db, run, result)
        db.commit()
        return result

    # -- single-LLM baseline (control arm) -----------------------------------
    def run_baseline(
        self, db: Session, run: PipelineRun, *, user_story: str, config: RunConfig
    ) -> AgentResult:
        from app.agents.single_llm_baseline import SingleLLMBaselineAgent

        agent = SingleLLMBaselineAgent(self.llm)
        agent, result = self._run_agent_logged(
            db,
            run,
            PipelineStage.test_generation,
            inputs={"user_story": user_story},
            config=config,
            agent=agent,
            prompt_version="baseline_v1",
        )
        if result.success:
            agent.persist(db, run, result)
        db.commit()
        return result

    # -- multi-agent debate: Reviewer <-> Consensus, bounded -----------------
    def _current_test_cases(self, db: Session, run: PipelineRun) -> list[TestCase]:
        """The live test cases for a run: the leaf of each version chain (a case
        no newer version supersedes), excluding rejected ones."""
        all_cases = list(
            db.scalars(
                select(TestCase)
                .where(TestCase.pipeline_run_id == run.id)
                .order_by(TestCase.id)
            )
        )
        superseded = {c.parent_test_case_id for c in all_cases if c.parent_test_case_id}
        return [
            c
            for c in all_cases
            if c.id not in superseded and c.status != TestCaseStatus.rejected
        ]

    @staticmethod
    def _tc_payload(cases: list[TestCase]) -> list[dict]:
        return [
            {
                "id": c.id,
                "acceptance_criterion_id": c.traces_to,
                "title": c.title,
                "steps": c.steps,
                "expected_result": c.expected_result,
                "type": c.type,
                "priority": c.priority,
            }
            for c in cases
        ]

    def _apply_resolutions(
        self, db: Session, run: PipelineRun, resolutions: list[dict]
    ) -> int:
        """Turn consensus decisions into versioned test cases. Returns the number
        of test cases created (revise + add). 'keep' is a rebuttal — recorded in
        the transcript, no row written."""
        created = 0
        for res in resolutions:
            decision = res.get("decision")
            revised = res.get("revised_test_case")
            if decision == "revise" and revised and res.get("test_case_id"):
                existing = db.get(TestCase, res["test_case_id"])
                if existing is None:
                    continue
                db.add(
                    TestCase(
                        pipeline_run_id=run.id,
                        version=existing.version + 1,
                        parent_test_case_id=existing.id,
                        title=revised["title"],
                        steps=revised["steps"],
                        expected_result=revised["expected_result"],
                        type=revised.get("type", "functional"),
                        priority=revised.get("priority", "medium"),
                        traces_to=existing.traces_to
                        or revised.get("acceptance_criterion_id"),
                        generated_by=GeneratedBy.consensus,
                        status=TestCaseStatus.consensus_resolved,
                    )
                )
                created += 1
            elif decision == "add" and revised:
                db.add(
                    TestCase(
                        pipeline_run_id=run.id,
                        version=1,
                        title=revised["title"],
                        steps=revised["steps"],
                        expected_result=revised["expected_result"],
                        type=revised.get("type", "functional"),
                        priority=revised.get("priority", "medium"),
                        traces_to=res.get("acceptance_criterion_id")
                        or revised.get("acceptance_criterion_id"),
                        generated_by=GeneratedBy.consensus,
                        status=TestCaseStatus.consensus_resolved,
                    )
                )
                created += 1
        db.flush()
        return created

    def run_debate(
        self,
        db: Session,
        run: PipelineRun,
        *,
        user_story: str,
        acceptance_criteria: list[dict],
        config: RunConfig,
    ) -> dict[str, Any]:
        """Bounded, bidirectional Reviewer <-> Consensus debate.

        Each round: the reviewer critiques the current test cases; if it is
        satisfied the loop stops (consensus reached); otherwise the consensus
        agent rebuts/revises/adds and the reviewer re-inspects next round. Every
        turn is persisted as a DebateTurn so the transcript is auditable.
        """
        rounds_used = 0
        consensus_reached = False
        revisions_made = 0
        total_findings = 0

        for round_no in range(1, config.max_debate_rounds + 1):
            rounds_used = round_no
            current = self._current_test_cases(db, run)
            if not current:
                break
            payload = self._tc_payload(current)

            # --- Reviewer turn ---
            _, review_result = self._run_agent_logged(
                db,
                run,
                PipelineStage.reviewer,
                inputs={
                    "round": round_no,
                    "user_story": user_story,
                    "acceptance_criteria": acceptance_criteria,
                    "test_cases": payload,
                },
                config=config,
            )
            if not review_result.success:
                db.commit()
                break

            review = review_result.output
            findings = review.get("findings", [])
            total_findings += len(findings)
            db.add(
                DebateTurn(
                    pipeline_run_id=run.id,
                    round=round_no,
                    speaker=DebateSpeaker.reviewer,
                    content=review,
                )
            )
            db.flush()

            # Autonomy: the reviewer's verdict — not the engine — ends the debate.
            if not review.get("needs_revision"):
                consensus_reached = True
                db.commit()
                break

            flagged = {f.get("test_case_id") for f in findings if f.get("test_case_id")}
            for case in current:
                if case.id in flagged:
                    case.status = TestCaseStatus.reviewer_flagged
            db.flush()

            # --- Consensus turn ---
            _, consensus_result = self._run_agent_logged(
                db,
                run,
                PipelineStage.consensus,
                inputs={
                    "round": round_no,
                    "user_story": user_story,
                    "acceptance_criteria": acceptance_criteria,
                    "test_cases": payload,
                    "findings": findings,
                },
                config=config,
            )
            if not consensus_result.success:
                db.commit()
                break

            consensus = consensus_result.output
            db.add(
                DebateTurn(
                    pipeline_run_id=run.id,
                    round=round_no,
                    speaker=DebateSpeaker.consensus,
                    content=consensus,
                )
            )
            db.flush()
            revisions_made += self._apply_resolutions(
                db, run, consensus.get("resolutions", [])
            )
            db.commit()

        run.current_stage = PipelineStage.consensus
        db.commit()
        return {
            "rounds_used": rounds_used,
            "consensus_reached": consensus_reached,
            "revisions_made": revisions_made,
            "total_findings": total_findings,
        }
