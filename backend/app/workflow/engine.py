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
    AcceptanceCriterion,
    AgentExecution,
    CoverageReport,
    DebateSpeaker,
    DebateTurn,
    ExecutionStatus,
    GeneratedBy,
    PipelineRun,
    PipelineStage,
    QualityReport,
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
        if stage == PipelineStage.prioritization:
            from app.agents.prioritizer import PrioritizerAgent

            return PrioritizerAgent(self.llm)
        if stage == PipelineStage.coverage:
            from app.agents.coverage import CoverageAgent

            return CoverageAgent(self.llm)
        if stage == PipelineStage.quality:
            from app.agents.quality import QualityAgent

            return QualityAgent(self.llm)
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

    # -- prioritization: rank the current suite ------------------------------
    def run_prioritization(
        self, db: Session, run: PipelineRun, *, user_story: str, config: RunConfig
    ) -> AgentResult:
        """Rank the run's current test cases by importance. Annotates cases in
        place (priority/severity/rank); creates no new versions."""
        current = self._current_test_cases(db, run)
        if not current:
            return AgentResult(
                stage=PipelineStage.prioritization,
                success=False,
                error="No test cases available to prioritize",
            )
        result = self.run_stage(
            db,
            run,
            PipelineStage.prioritization,
            inputs={"user_story": user_story, "test_cases": self._tc_payload(current)},
            config=config,
        )
        run.current_stage = PipelineStage.prioritization
        db.commit()
        return result

    # -- coverage / validation: traceability matrix + adequacy judgement -----
    def run_coverage(
        self, db: Session, run: PipelineRun, *, user_story: str, config: RunConfig
    ) -> dict[str, Any]:
        """Validate requirement coverage. Traceability (which criterion is hit by
        which case) is computed deterministically here — authoritative. The agent
        judges adequacy (superficial vs genuine). CoverageReport rows are then
        written merging the two."""
        criteria = list(
            db.scalars(
                select(AcceptanceCriterion)
                .where(AcceptanceCriterion.pipeline_run_id == run.id)
                .order_by(AcceptanceCriterion.order)
            )
        )
        current = self._current_test_cases(db, run)

        # Deterministic traceability matrix: criterion id -> covering case ids.
        covering: dict[int, list[int]] = {c.id: [] for c in criteria}
        for case in current:
            if case.traces_to in covering:
                covering[case.traces_to].append(case.id)

        by_id = {c.id: c for c in current}
        coverage_map = [
            {
                "acceptance_criterion_id": crit.id,
                "criterion_text": crit.text,
                "covering_test_case_ids": covering[crit.id],
                "mapped_cases": [
                    {"id": tc_id, "title": by_id[tc_id].title, "type": by_id[tc_id].type}
                    for tc_id in covering[crit.id]
                ],
            }
            for crit in criteria
        ]

        # Agent judges adequacy (logged as an AgentExecution). If it fails we
        # still record deterministic coverage, just without adequacy notes.
        assessments: dict[int, dict] = {}
        if criteria:
            _, result = self._run_agent_logged(
                db,
                run,
                PipelineStage.coverage,
                inputs={"user_story": user_story, "coverage_map": coverage_map},
                config=config,
            )
            if result.success:
                for a in result.output.get("assessments", []):
                    assessments[a.get("acceptance_criterion_id")] = a

        # Rewrite CoverageReport rows for this run.
        db.query(CoverageReport).filter(
            CoverageReport.pipeline_run_id == run.id
        ).delete()
        covered_count = 0
        adequate_count = 0
        for crit in criteria:
            ids = covering[crit.id]
            covered = bool(ids)
            covered_count += 1 if covered else 0
            assessment = assessments.get(crit.id, {})
            adequate = covered and assessment.get("adequate", True)
            adequate_count += 1 if adequate else 0
            if not covered:
                gap_notes = "No test case traces to this criterion."
            else:
                gap_notes = assessment.get("gap_notes") or "Adequately covered"
            db.add(
                CoverageReport(
                    pipeline_run_id=run.id,
                    acceptance_criterion_id=crit.id,
                    covered=covered,
                    covering_test_case_ids=ids,
                    gap_notes=gap_notes,
                )
            )

        run.current_stage = PipelineStage.coverage
        db.commit()
        total = len(criteria)
        return {
            "total": total,
            "covered_count": covered_count,
            "adequate_count": adequate_count,
            "coverage_pct": round(100.0 * covered_count / total, 1) if total else 0.0,
        }

    # -- quality: score each test case (clarity/atomicity/traceability) ------
    @staticmethod
    def _norm_title(title: str | None) -> str:
        return " ".join((title or "").lower().split())

    def run_quality(
        self, db: Session, run: PipelineRun, *, user_story: str, config: RunConfig
    ) -> dict[str, Any]:
        """Score the current suite's quality. The agent judges clarity /
        atomicity / traceability + duplicates; a deterministic near-duplicate
        pass (normalized title) complements the agent's duplicate flag. Writes
        QualityReport rows and returns an overall quality score + duplicate rate."""
        current = self._current_test_cases(db, run)
        if not current:
            return {"total": 0, "overall_score": 0.0, "duplicate_count": 0}

        payload = self._tc_payload(current)
        _, result = self._run_agent_logged(
            db,
            run,
            PipelineStage.quality,
            inputs={"user_story": user_story, "test_cases": payload},
            config=config,
        )
        scores = {}
        if result.success:
            for s in result.output.get("scores", []):
                scores[s.get("test_case_id")] = s

        # Deterministic near-duplicate detection: cases sharing a normalized
        # title (beyond the first occurrence) are flagged regardless of the LLM.
        seen_titles: dict[str, int] = {}
        det_duplicate: set[int] = set()
        for case in current:
            key = self._norm_title(case.title)
            if key in seen_titles:
                det_duplicate.add(case.id)
            else:
                seen_titles[key] = case.id

        db.query(QualityReport).filter(
            QualityReport.pipeline_run_id == run.id
        ).delete()

        clamp = lambda v: max(0.0, min(1.0, float(v or 0.0)))  # noqa: E731
        case_means = []
        duplicate_count = 0
        for case in current:
            s = scores.get(case.id, {})
            clarity = clamp(s.get("clarity"))
            atomicity = clamp(s.get("atomicity"))
            traceability = clamp(s.get("traceability"))
            duplicate = bool(s.get("duplicate")) or case.id in det_duplicate
            duplicate_count += 1 if duplicate else 0
            case_means.append((clarity + atomicity + traceability) / 3.0)
            db.add(
                QualityReport(
                    pipeline_run_id=run.id,
                    test_case_id=case.id,
                    clarity_score=clarity,
                    atomicity_score=atomicity,
                    traceability_score=traceability,
                    duplicate_flag=duplicate,
                    notes=s.get("notes") or ("Possible duplicate" if duplicate else None),
                )
            )

        run.current_stage = PipelineStage.quality
        db.commit()
        total = len(current)
        overall = round(sum(case_means) / total, 3) if total else 0.0
        return {
            "total": total,
            "overall_score": overall,
            "duplicate_count": duplicate_count,
            "duplicate_rate": round(duplicate_count / total, 3) if total else 0.0,
        }

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
                "test_data": c.test_data,
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
                        test_data=revised.get("test_data"),
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
                        test_data=revised.get("test_data"),
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

    # -- agentic orchestration: LLM planner + deterministic guardrails --------
    def _orch_criteria(self, db: Session, run: PipelineRun) -> list[AcceptanceCriterion]:
        return list(
            db.scalars(
                select(AcceptanceCriterion)
                .where(AcceptanceCriterion.pipeline_run_id == run.id)
                .order_by(AcceptanceCriterion.order)
            )
        )

    def _orch_state(self, db: Session, run: PipelineRun) -> dict[str, Any]:
        """Snapshot the run so the planner can reason about what remains."""
        criteria = self._orch_criteria(db, run)
        cases = self._current_test_cases(db, run)
        debated = (
            db.scalar(
                select(DebateTurn.id)
                .where(DebateTurn.pipeline_run_id == run.id)
                .limit(1)
            )
            is not None
        )
        cov = list(
            db.scalars(
                select(CoverageReport).where(CoverageReport.pipeline_run_id == run.id)
            )
        )
        qual = list(
            db.scalars(
                select(QualityReport).where(QualityReport.pipeline_run_id == run.id)
            )
        )
        covered = sum(1 for r in cov if r.covered)
        return {
            "has_criteria": bool(criteria),
            "n_criteria": len(criteria),
            "num_cases": len(cases),
            "debated": debated,
            "prioritized": any(c.rank is not None for c in cases),
            "coverage_done": bool(cov),
            "coverage_pct": round(100.0 * covered / len(cov), 1) if cov else 0.0,
            "quality_done": bool(qual),
        }

    @staticmethod
    def _orch_legal(state: dict[str, Any]) -> list[str]:
        """Guardrail: the legal next actions given the state. Enforces valid
        transitions (can't generate before criteria exist, etc.) and prevents
        loops (each stage offered until done, then removed)."""
        if not state["has_criteria"]:
            return ["analyze"]
        if state["num_cases"] == 0:
            return ["generate"]
        legal: list[str] = []
        if not state["debated"]:
            legal.append("debate")
        if not state["coverage_done"]:
            legal.append("coverage")
        if not state["quality_done"]:
            legal.append("quality")
        if not state["prioritized"]:
            legal.append("prioritize")
        legal.append("finish")
        return legal

    def _log_planner(
        self, db, run, step_no, state, legal, action, rationale, fallback, model=None
    ) -> None:
        db.add(
            AgentExecution(
                pipeline_run_id=run.id,
                stage=PipelineStage.planning,
                attempt_no=step_no,
                raw_input={"state": state, "legal_actions": legal},
                raw_output={
                    "action": action,
                    "rationale": rationale,
                    "planner_fallback": fallback,
                },
                reasoning=rationale,
                model=model,
                status=ExecutionStatus.success,
            )
        )
        db.flush()

    def _orch_dispatch(self, db, run, requirement, action, config) -> None:
        story = requirement.raw_text
        if action == "analyze":
            self.run_stage(
                db, run, PipelineStage.requirement_analysis,
                {"user_story": story}, config,
            )
        elif action == "generate":
            criteria = self._orch_criteria(db, run)
            self.run_stage(
                db, run, PipelineStage.test_generation,
                {
                    "user_story": story,
                    "acceptance_criteria": [
                        {"id": c.id, "text": c.text} for c in criteria
                    ],
                },
                config,
            )
        elif action == "debate":
            criteria = self._orch_criteria(db, run)
            self.run_debate(
                db, run, user_story=story,
                acceptance_criteria=[{"id": c.id, "text": c.text} for c in criteria],
                config=config,
            )
        elif action == "coverage":
            self.run_coverage(db, run, user_story=story, config=config)
        elif action == "quality":
            self.run_quality(db, run, user_story=story, config=config)
        elif action == "prioritize":
            self.run_prioritization(db, run, user_story=story, config=config)

    def run_orchestration(
        self, db: Session, run: PipelineRun, *, requirement, config: RunConfig, goal: dict | None = None
    ) -> dict[str, Any]:
        """The agentic control loop. An LLM planner picks the next specialist
        agent from live state each step; guardrails cap the step budget and the
        legal move set. Every decision is logged as an AgentExecution
        (stage=planning), so the run is an auditable trace of which agent acted
        and why — the framework's evidence of agency."""
        from app.agents.planner import PlannerAgent

        goal = goal or {"coverage_target": 100, "max_steps": 10}
        max_steps = int(goal.get("max_steps", 10))
        planner = PlannerAgent(self.llm)
        decisions: list[dict] = []

        for step_no in range(1, max_steps + 1):
            state = self._orch_state(db, run)
            legal = self._orch_legal(state)
            choice = planner.decide(
                goal=goal, state=state, legal_actions=legal, model=config.model
            )
            action = choice.get("action")
            fallback = action not in legal
            if fallback:
                action = legal[0]
            rationale = choice.get("rationale") or f"Selected '{action}'."
            self._log_planner(db, run, step_no, state, legal, action, rationale, fallback, model=config.model)
            decisions.append(
                {
                    "step": step_no,
                    "action": action,
                    "rationale": rationale,
                    "planner_fallback": fallback,
                }
            )
            if action == "finish":
                break
            self._orch_dispatch(db, run, requirement, action, config)

        db.commit()
        return {
            "decisions": decisions,
            "final_state": self._orch_state(db, run),
            "steps_used": len(decisions),
        }
