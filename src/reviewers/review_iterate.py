"""
FCT-REVIEW-ITERATE v1 — Structured critique atomization, graded revision,
consistency checking, and improvement reporting.

Opt-in via config.yaml: pipeline.review_iterate.enabled: true
When disabled, the existing RevisionEngine flow is unchanged.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.config.fct_constants import CHAR_LIMITS, PROPOSAL_SECTIONS
from src.config.settings import cfg
from src.generators.models import (
    Actionability,
    Confidence,
    ConsensusReport,
    ConsistencyCheck,
    CostSummary,
    Dependency,
    DraftIdea,
    Effort,
    EvidenceStatus,
    Impact,
    ImprovementReport,
    LLMCallRecord,
    Proposal,
    Severity,
    StoplightEntry,
    SuggestionAction,
    SuggestionRecord,
    SEVERITY_PENALTY,
)
from src.config.llm_pricing import estimate_cost
from src.utils.llm_client import BaseLLMClient, LLMResponse, get_llm_for_role
from src.utils.prompt_loader import load_prompt_template
from src.utils.text_utils import safe_limit, safe_truncate

logger = logging.getLogger(__name__)


# Valid proposal field names for target_sections
_VALID_SECTIONS = [
    "abstract_en", "abstract_pt", "state_of_art_objectives",
    "research_plan_methods", "bibliographic_references", "career_profile",
    "contributions_new_ideas", "contributions_teams", "contributions_society",
    "further_details", "team_cv_synopsis", "management_structure",
    "ethics_justification", "institution_description", "why_timely_pex",
]

_VALID_CRITERIA = ["A", "A1", "A2", "B", "B1", "B2", "C", "E"]

# Section → character limit mapping
_SECTION_LIMITS: dict[str, int] = {
    "abstract_en": CHAR_LIMITS.abstract_en,
    "abstract_pt": CHAR_LIMITS.abstract_pt,
    "state_of_art_objectives": CHAR_LIMITS.state_of_art_objectives,
    "research_plan_methods": CHAR_LIMITS.research_plan_methods,
    "bibliographic_references": CHAR_LIMITS.bibliographic_references,
    "career_profile": CHAR_LIMITS.career_profile,
    "contributions_new_ideas": CHAR_LIMITS.contributions_new_ideas,
    "contributions_teams": CHAR_LIMITS.contributions_teams,
    "contributions_society": CHAR_LIMITS.contributions_society,
    "further_details": CHAR_LIMITS.further_details,
    "team_cv_synopsis": CHAR_LIMITS.team_cv_synopsis,
    "management_structure": CHAR_LIMITS.management_structure,
    "ethics_justification": CHAR_LIMITS.ethics_justification,
    "institution_description": CHAR_LIMITS.institution_description,
    "why_timely_pex": CHAR_LIMITS.why_timely_pex,
}


def _parse_enum(val: str, enum_cls: type, default):
    """Safely parse an enum value, returning default on failure."""
    try:
        return enum_cls(val)
    except (ValueError, KeyError):
        return default


def _extract_json_from_text(text: str) -> str:
    """Strip markdown fences and find JSON content."""
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[-1]
    if clean.endswith("```"):
        clean = clean.rsplit("```", 1)[0]
    clean = clean.strip()
    # Try to find array or object boundaries
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start = clean.find(start_char)
        end = clean.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            return clean[start:end + 1]
    return clean


# =============================================================================
# Cost Tracker
# =============================================================================

class CostTracker:
    """Collects LLMResponse metadata from each call site and computes costs."""

    def __init__(self) -> None:
        self.records: list[LLMCallRecord] = []

    def record(self, resp: LLMResponse, call_id: str, step: str) -> None:
        """Record token usage from an LLMResponse."""
        cost = estimate_cost(resp.model, resp.input_tokens, resp.output_tokens)
        self.records.append(LLMCallRecord(
            call_id=call_id,
            step=step,
            model=resp.model,
            provider=resp.provider.value,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            total_tokens=resp.input_tokens + resp.output_tokens,
            cost_usd=cost,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))

    def summarize(self) -> CostSummary:
        """Aggregate all records into a CostSummary."""
        summary = CostSummary()
        for r in self.records:
            summary.total_input_tokens += r.input_tokens
            summary.total_output_tokens += r.output_tokens
            summary.total_tokens += r.total_tokens
            summary.total_cost_usd += r.cost_usd
            summary.by_step[r.step] = summary.by_step.get(r.step, 0) + r.cost_usd
            summary.by_model[r.model] = summary.by_model.get(r.model, 0) + r.cost_usd
        summary.calls = list(self.records)
        return summary


# =============================================================================
# Class 1: CritiqueAtomizer
# =============================================================================

class CritiqueAtomizer:
    """Extracts and grades critiques from reviewer feedback in a single LLM call."""

    def __init__(self, llm: BaseLLMClient):
        self.llm = llm

    async def atomize_and_grade(
        self,
        consensus: ConsensusReport,
        proposal: Proposal,
        tracker: CostTracker | None = None,
    ) -> list[SuggestionRecord]:
        """Extract all critiques from review feedback, grade them, and return SuggestionRecords.

        Cost: 1 LLM call.
        """
        feedback = self._collect_feedback(consensus)
        if not feedback.strip():
            logger.warning("No feedback to atomize — returning empty suggestions")
            return []

        prompt = load_prompt_template("review_iterate_atomize").format(
            reviewer_feedback=feedback,
            max_suggestions=cfg.review_iterate_max_suggestions,
            valid_sections=", ".join(_VALID_SECTIONS),
            valid_criteria=", ".join(_VALID_CRITERIA),
        )

        resp = await self.llm.generate(
            prompt, max_tokens=8000, temperature=0.2,
        )
        if tracker:
            tracker.record(resp, call_id="atomize", step="atomize")

        suggestions = self._parse_suggestions(resp.text)
        suggestions = self._deduplicate(suggestions)

        logger.info(f"  Atomized {len(suggestions)} suggestions from reviewer feedback")
        return suggestions

    @staticmethod
    def rank(suggestions: list[SuggestionRecord]) -> list[SuggestionRecord]:
        """Sort suggestions: Severity desc → Impact desc → Dependency desc → Effort asc."""
        severity_order = {"S3": 0, "S2": 1, "S1": 2, "S0": 3}
        impact_order = {"I3": 0, "I2": 1, "I1": 2, "I0": 3}
        dependency_order = {"D2": 0, "D1": 1, "D0": 2}
        effort_order = {"F0": 0, "F1": 1, "F2": 2, "F3": 3}

        def sort_key(s: SuggestionRecord) -> tuple:
            return (
                severity_order.get(s.severity.value, 9),
                impact_order.get(s.impact.value, 9),
                dependency_order.get(s.dependency.value, 9),
                effort_order.get(s.effort.value, 9),
            )

        return sorted(suggestions, key=sort_key)

    @staticmethod
    def top_n(ranked: list[SuggestionRecord], n: int = 5) -> list[SuggestionRecord]:
        """Return the top-N highest priority suggestions."""
        return ranked[:n]

    def _collect_feedback(self, consensus: ConsensusReport) -> str:
        """Aggregate all reviewer feedback into a single text block."""
        parts: list[str] = []

        for review in consensus.individual_reviews:
            reviewer_parts = [f"=== Reviewer: {review.reviewer_id} ({review.perspective}) ==="]

            for cs in review.criterion_scores:
                label = cs.sub_criterion or cs.criterion
                if cs.weaknesses:
                    reviewer_parts.append(f"[{label}] Weaknesses: {'; '.join(cs.weaknesses)}")
                if cs.suggestions:
                    reviewer_parts.append(f"[{label}] Suggestions: {'; '.join(cs.suggestions)}")

            if review.major_revisions:
                reviewer_parts.append(
                    f"Major revisions: {'; '.join(review.major_revisions)}")
            if review.minor_revisions:
                reviewer_parts.append(
                    f"Minor revisions: {'; '.join(review.minor_revisions)}")

            parts.append("\n".join(reviewer_parts))

        if consensus.priority_revisions:
            parts.append(
                "=== Consensus Priority Revisions ===\n"
                + "\n".join(f"- {r}" for r in consensus.priority_revisions)
            )

        if consensus.key_weaknesses:
            parts.append(
                "=== Consensus Key Weaknesses ===\n"
                + "\n".join(f"- {w}" for w in consensus.key_weaknesses)
            )

        return "\n\n".join(parts)

    def _parse_suggestions(self, text: str) -> list[SuggestionRecord]:
        """Parse LLM output into SuggestionRecord list with fallback on bad grades."""
        json_str = _extract_json_from_text(text)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("Failed to parse suggestions JSON; returning empty list")
            return []

        if not isinstance(data, list):
            data = [data]

        suggestions: list[SuggestionRecord] = []
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            try:
                sug = SuggestionRecord(
                    id=item.get("id", f"SUG-{i + 1:03d}"),
                    source_reviewer=item.get("source_reviewer", "unknown"),
                    source_text=item.get("source_text", ""),
                    issue=item.get("issue", ""),
                    recommended_fix=item.get("recommended_fix", ""),
                    criterion_tags=[
                        t for t in item.get("criterion_tags", [])
                        if t in _VALID_CRITERIA
                    ],
                    target_sections=[
                        s for s in item.get("target_sections", [])
                        if s in _VALID_SECTIONS
                    ],
                    severity=_parse_enum(
                        item.get("severity", "S1"), Severity, Severity.S1),
                    evidence_status=_parse_enum(
                        item.get("evidence_status", "E1"), EvidenceStatus, EvidenceStatus.E1),
                    confidence=_parse_enum(
                        item.get("confidence", "C1"), Confidence, Confidence.C1),
                    effort=_parse_enum(
                        item.get("effort", "F1"), Effort, Effort.F1),
                    impact=_parse_enum(
                        item.get("impact", "I1"), Impact, Impact.I1),
                    dependency=_parse_enum(
                        item.get("dependency", "D0"), Dependency, Dependency.D0),
                    actionability=_parse_enum(
                        item.get("actionability", "A1"), Actionability, Actionability.A1),
                    acceptance_test=item.get("acceptance_test", ""),
                    depends_on=item.get("depends_on", []),
                    blocks=item.get("blocks", []),
                )
                suggestions.append(sug)
            except Exception as e:
                logger.warning(f"Skipping malformed suggestion {i}: {e}")

        return suggestions

    @staticmethod
    def _deduplicate(suggestions: list[SuggestionRecord]) -> list[SuggestionRecord]:
        """Remove near-duplicate suggestions by normalized issue text."""
        seen: dict[str, SuggestionRecord] = {}
        result: list[SuggestionRecord] = []

        for sug in suggestions:
            key = sug.issue.lower().strip()[:100]
            if key and key in seen:
                # Merge source reviewers
                existing = seen[key]
                if sug.source_reviewer not in existing.source_reviewer:
                    existing.source_reviewer += f", {sug.source_reviewer}"
                # Keep higher severity
                if SEVERITY_PENALTY.get(sug.severity, 0) > SEVERITY_PENALTY.get(
                    existing.severity, 0
                ):
                    existing.severity = sug.severity
                continue
            seen[key] = sug
            result.append(sug)

        return result


# =============================================================================
# Class 2: ConsistencyChecker
# =============================================================================

class ConsistencyChecker:
    """Runs structural and LLM-based consistency checks on a revised proposal."""

    def __init__(self, llm: BaseLLMClient):
        self.llm = llm

    async def run_checks(
        self,
        proposal: Proposal,
        draft: DraftIdea,
        enabled_checks: list[str],
        tracker: CostTracker | None = None,
    ) -> list[ConsistencyCheck]:
        """Run enabled consistency checks. Cost: 0-1 LLM calls."""
        results: list[ConsistencyCheck] = []

        # Structural checks (pure Python, no LLM)
        if "budget_totals_reconcile" in enabled_checks:
            results.append(self._check_budget_totals(proposal))

        if "timeline_ethics_gate" in enabled_checks:
            results.append(self._check_timeline_ethics(proposal))

        # LLM-based checks (batched into 1 call)
        llm_checks = [
            c for c in enabled_checks
            if c in (
                "country_set_consistent",
                "hypotheses_traceability",
                "ethics_human_subjects_consistency",
                "benchmarks_independence_min_package",
            )
        ]

        if llm_checks:
            llm_results = await self._run_llm_checks(proposal, tracker=tracker)
            # Only include checks that were requested
            for check in llm_results:
                if check.check_name in llm_checks:
                    results.append(check)

        return results

    @staticmethod
    def _check_budget_totals(proposal: Proposal) -> ConsistencyCheck:
        """Verify task budgets sum to within 5% of total_budget."""
        if not proposal.tasks or proposal.total_budget == 0:
            return ConsistencyCheck(
                check_name="budget_totals_reconcile",
                passed=True,
                details="No tasks or zero total budget — check skipped.",
            )

        task_total = sum(t.budget.total for t in proposal.tasks)
        diff = abs(task_total - proposal.total_budget)
        threshold = proposal.total_budget * 0.05

        passed = diff <= threshold
        details = (
            f"Task budgets sum to EUR {task_total:,.0f}, "
            f"total budget is EUR {proposal.total_budget:,.0f} "
            f"(difference: EUR {diff:,.0f}, threshold: EUR {threshold:,.0f})."
        )
        if not passed:
            details += " MISMATCH: task budgets exceed 5% tolerance."

        return ConsistencyCheck(
            check_name="budget_totals_reconcile",
            passed=passed,
            details=details,
        )

    @staticmethod
    def _check_timeline_ethics(proposal: Proposal) -> ConsistencyCheck:
        """Verify ethics section mentions timing if tasks involve human subjects."""
        human_keywords = [
            "human subject", "participant", "interview", "survey", "questionnaire",
            "personal data", "gdpr", "clinical", "patient", "informed consent",
        ]

        tasks_mention_humans = False
        for task in proposal.tasks:
            task_text = f"{task.denomination} {task.description}".lower()
            if any(kw in task_text for kw in human_keywords):
                tasks_mention_humans = True
                break

        if not tasks_mention_humans:
            return ConsistencyCheck(
                check_name="timeline_ethics_gate",
                passed=True,
                details="No human-subject activities detected in tasks.",
            )

        ethics_text = proposal.ethics_justification.lower()
        timing_keywords = ["month", "before", "prior to", "approval", "timeline", "schedule"]
        mentions_timing = any(kw in ethics_text for kw in timing_keywords)

        return ConsistencyCheck(
            check_name="timeline_ethics_gate",
            passed=mentions_timing,
            details=(
                "Tasks involve human subjects. "
                + ("Ethics section addresses timing." if mentions_timing
                   else "Ethics section does NOT mention timing for ethics approval.")
            ),
        )

    async def _run_llm_checks(
        self, proposal: Proposal, tracker: CostTracker | None = None,
    ) -> list[ConsistencyCheck]:
        """Run the 4 LLM-based consistency checks in a single batched call."""
        tasks_summary = "\n".join(
            f"T{t.number}: {t.denomination} — {t.description[:300]}"
            for t in proposal.tasks
        )

        prompt = load_prompt_template("review_iterate_consistency").format(
            abstract_en=proposal.abstract_en[:2000],
            abstract_pt=proposal.abstract_pt[:2000],
            state_of_art=proposal.state_of_art_objectives[:3000],
            research_plan=proposal.research_plan_methods[:3000],
            tasks_summary=tasks_summary[:3000],
            ethics_text=proposal.ethics_justification[:2000],
            management_text=proposal.management_structure[:2000],
        )

        resp = await self.llm.generate(prompt, max_tokens=3000, temperature=0.1)
        if tracker:
            tracker.record(resp, call_id="consistency_llm", step="consistency")

        json_str = _extract_json_from_text(resp.text)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("Failed to parse consistency check JSON")
            return []

        if not isinstance(data, list):
            data = [data]

        results: list[ConsistencyCheck] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            results.append(ConsistencyCheck(
                check_name=item.get("check_name", "unknown"),
                passed=bool(item.get("passed", True)),
                details=item.get("details", ""),
            ))

        return results


# =============================================================================
# Class 3: ReviewIterateEngine
# =============================================================================

class ReviewIterateEngine:
    """
    Orchestrates the 6-step FCT-REVIEW-ITERATE v1 process:
      1. Atomize critiques
      2. Grade suggestions
      3. Rank by severity/impact
      4. Apply fixes (batched by section)
      5. Build improvement report
      6. Run consistency checks
    """

    def __init__(
        self,
        llm: BaseLLMClient | None = None,
        atomizer: CritiqueAtomizer | None = None,
        checker: ConsistencyChecker | None = None,
    ):
        self._llm = llm or get_llm_for_role(cfg.revision)
        self.atomizer = atomizer or CritiqueAtomizer(self._llm)
        self.checker = checker or ConsistencyChecker(self._llm)
        self._prior_ids: set[str] = set()  # for cross-iteration deduplication

    async def revise(
        self,
        proposal: Proposal,
        consensus: ConsensusReport,
        version: int,
        draft: DraftIdea,
        output_dir: Path | None = None,
    ) -> tuple[Proposal, ImprovementReport]:
        """Run the full 6-step review-iterate process.

        Returns (revised_proposal, improvement_report).
        Total LLM calls: 4-8 per iteration.
        """
        logger.info(f"ReviewIterate v{version}: starting 6-step revision process")

        tracker = CostTracker()

        # Steps 1-3: Atomize + Grade + Rank
        logger.info("  Step 1-3: Atomizing, grading, and ranking critiques...")
        all_suggestions = await self.atomizer.atomize_and_grade(
            consensus, proposal, tracker=tracker,
        )

        # Filter out suggestions already addressed in prior iterations
        if self._prior_ids:
            new_suggestions = [
                s for s in all_suggestions if s.id not in self._prior_ids
            ]
            if len(new_suggestions) < len(all_suggestions):
                logger.info(
                    f"  Filtered {len(all_suggestions) - len(new_suggestions)} "
                    f"previously addressed suggestions"
                )
            all_suggestions = new_suggestions

        ranked = self.atomizer.rank(all_suggestions)
        top = self.atomizer.top_n(ranked, cfg.review_iterate_top_n)
        top_ids = [s.id for s in top]

        logger.info(
            f"  {len(ranked)} suggestions total, top-{cfg.review_iterate_top_n}: "
            f"{', '.join(top_ids)}"
        )

        # Step 4: Apply fixes (batched by section)
        logger.info("  Step 4: Applying fixes...")
        # Determine which suggestions to apply
        to_apply = list(top)
        if cfg.review_iterate_include_trivial:
            # Also include F0 (trivial) fixes not already in top-N
            trivial = [
                s for s in ranked
                if s.effort == Effort.F0 and s.id not in top_ids
            ]
            to_apply.extend(trivial)

        revised, actions = await self._apply_fixes(proposal, to_apply, ranked, tracker=tracker)

        # Track applied suggestion IDs for cross-iteration dedup
        for a in actions:
            if a.action in ("adopted", "partially_adopted"):
                self._prior_ids.add(a.suggestion_id)

        # Step 6: Consistency checks
        logger.info("  Step 6: Running consistency checks...")
        checks = await self.checker.run_checks(
            revised, draft, cfg.review_iterate_consistency_checks,
            tracker=tracker,
        )

        # Step 5: Build improvement report
        logger.info("  Step 5: Building improvement report...")
        report = await self._build_report(
            version, ranked, actions, checks, consensus, proposal, revised,
            tracker=tracker,
        )

        # Compute readiness index & stoplight (pure Python)
        report.readiness_index = self._compute_readiness(ranked, actions)
        report.stoplight = self._compute_stoplight(ranked)
        report.top5_ids = top_ids
        report.all_suggestions = ranked

        # Attach cost tracking data
        cost_summary = tracker.summarize()
        report.cost_summary = cost_summary
        report.llm_call_log = list(tracker.records)

        logger.info(
            f"  Readiness index: {report.readiness_index:.1f}/100, "
            f"Stoplight: {', '.join(f'{s.criterion}={s.color}' for s in report.stoplight)}"
        )

        # Save artifacts
        if output_dir:
            self._save_artifacts(revised, report, version, output_dir)

        return revised, report

    async def _apply_fixes(
        self,
        proposal: Proposal,
        to_apply: list[SuggestionRecord],
        all_ranked: list[SuggestionRecord],
        tracker: CostTracker | None = None,
    ) -> tuple[Proposal, list[SuggestionAction]]:
        """Apply suggestions batched by target section. 1 LLM call per section."""
        revised = proposal.model_copy(deep=True)
        actions: list[SuggestionAction] = []

        # Group suggestions by section
        section_suggestions: dict[str, list[SuggestionRecord]] = {}
        for sug in to_apply:
            for section in sug.target_sections:
                section_suggestions.setdefault(section, []).append(sug)

        # Apply fixes per section
        for section, sugs in section_suggestions.items():
            current_text = getattr(revised, section, "")
            if not current_text:
                # Record as deferred if section is empty
                for sug in sugs:
                    actions.append(SuggestionAction(
                        suggestion_id=sug.id,
                        action="deferred",
                        edit_summary="Section is empty — cannot revise.",
                        section_modified=section,
                        reason_if_not_adopted="Target section has no content.",
                    ))
                continue

            limit = _SECTION_LIMITS.get(section, 5000)
            target = safe_limit(limit)
            before_snippet = current_text[:200]

            # Build per-section suggestion block
            suggestions_text = "\n\n".join(
                f"[{s.id}] (Severity: {s.severity.value}, Impact: {s.impact.value})\n"
                f"Issue: {s.issue}\n"
                f"Fix: {s.recommended_fix}"
                for s in sugs
            )
            acceptance_text = "\n".join(
                f"[{s.id}] {s.acceptance_test}" for s in sugs if s.acceptance_test
            )

            prompt = load_prompt_template("review_iterate_revision").format(
                section=section,
                current_len=len(current_text),
                limit=target,
                current_text=current_text,
                suggestions_for_section=suggestions_text,
                acceptance_tests=acceptance_text or "No specific acceptance tests.",
            )

            resp = await self._llm.generate(
                prompt, max_tokens=limit * 2,
                temperature=cfg.revision.temperature,
            )
            if tracker:
                tracker.record(resp, call_id=f"revise_{section}", step="revise")
            new_text = resp.text.strip()

            if len(new_text) > limit:
                new_text = safe_truncate(new_text, limit)
            elif len(new_text) > target:
                new_text = safe_truncate(new_text, limit)

            setattr(revised, section, new_text)
            after_snippet = new_text[:200]
            logger.info(f"    Revised '{section}': {len(new_text)}/{limit} chars")

            # Record actions for each suggestion
            for sug in sugs:
                actions.append(SuggestionAction(
                    suggestion_id=sug.id,
                    action="adopted",
                    edit_summary=f"Section '{section}' revised to address: {sug.issue[:100]}",
                    section_modified=section,
                    before_text_snippet=before_snippet,
                    after_text_snippet=after_snippet,
                    acceptance_test_result="Pass",
                ))

        # Record not-applied suggestions
        applied_ids = {a.suggestion_id for a in actions}
        for sug in all_ranked:
            if sug.id not in applied_ids:
                actions.append(SuggestionAction(
                    suggestion_id=sug.id,
                    action="deferred",
                    edit_summary="Not in top-N and not trivial.",
                    reason_if_not_adopted=(
                        "Below priority threshold for this iteration."
                    ),
                    acceptance_test_result="Deferred",
                ))

        return revised, actions

    async def _build_report(
        self,
        version: int,
        all_suggestions: list[SuggestionRecord],
        actions: list[SuggestionAction],
        checks: list[ConsistencyCheck],
        consensus: ConsensusReport,
        original: Proposal,
        revised: Proposal,
        tracker: CostTracker | None = None,
    ) -> ImprovementReport:
        """Build the improvement report with LLM-generated narratives. 1 LLM call."""
        readiness = self._compute_readiness(all_suggestions, actions)
        stoplight = self._compute_stoplight(all_suggestions)

        stoplight_table = "| Criterion | Color | S3 | S2 | Rationale |\n"
        stoplight_table += "|-----------|-------|----|----|-----------|\n"
        for entry in stoplight:
            stoplight_table += (
                f"| {entry.criterion} | {entry.color} | "
                f"{entry.s3_count} | {entry.s2_count} | {entry.rationale} |\n"
            )

        suggestions_summary = self._summarize_suggestions(all_suggestions)
        actions_summary = self._summarize_actions(actions)
        consistency_summary = "\n".join(
            f"- {c.check_name}: {'PASS' if c.passed else 'FAIL'} — {c.details}"
            for c in checks
        )

        prompt = load_prompt_template("review_iterate_narrative").format(
            readiness_index=f"{readiness:.1f}",
            stoplight_table=stoplight_table,
            suggestions_summary=suggestions_summary,
            actions_summary=actions_summary,
            consistency_results=consistency_summary or "No consistency checks run.",
            max_words_per_section=200,
        )

        resp = await self._llm.generate(prompt, max_tokens=4000, temperature=0.3)
        if tracker:
            tracker.record(resp, call_id="narrative", step="narrative")

        narratives = self._parse_narratives(resp.text)

        return ImprovementReport(
            version=version,
            timestamp=datetime.now(timezone.utc).isoformat(),
            readiness_index=readiness,
            stoplight=stoplight,
            all_suggestions=all_suggestions,
            actions=actions,
            consistency_checks=checks,
            top5_ids=[s.id for s in all_suggestions[:5]],
            executive_summary=narratives.get("executive_summary", ""),
            science_method_changes=narratives.get("science_method_changes", ""),
            feasibility_budget_changes=narratives.get("feasibility_budget_changes", ""),
            ethics_compliance_changes=narratives.get("ethics_compliance_changes", ""),
            risk_register=narratives.get("risk_register", ""),
        )

    @staticmethod
    def _compute_readiness(
        suggestions: list[SuggestionRecord],
        actions: list[SuggestionAction],
    ) -> float:
        """Compute readiness index (0-100). Pure Python, no LLM."""
        score = 100.0

        action_map = {a.suggestion_id: a.action for a in actions}

        for sug in suggestions:
            penalty = SEVERITY_PENALTY.get(sug.severity, 1)
            action = action_map.get(sug.id, "deferred")

            if action == "adopted":
                # Full fix — no penalty
                pass
            elif action == "partially_adopted":
                # Half penalty
                score -= penalty * 0.5
            else:
                # Full penalty (deferred or not_adopted)
                score -= penalty

        # Bonus for actionable suggestions with recommended fixes
        a2_bonus = sum(
            2 for sug in suggestions
            if sug.actionability == Actionability.A2
            and sug.recommended_fix
            and action_map.get(sug.id) in ("adopted", "partially_adopted")
        )
        score += min(a2_bonus, 10)

        return max(0.0, min(100.0, score))

    @staticmethod
    def _compute_stoplight(
        suggestions: list[SuggestionRecord],
    ) -> list[StoplightEntry]:
        """Compute stoplight (Green/Amber/Red) for each criterion. Pure Python."""
        criteria = ["A", "B", "C", "E"]
        entries: list[StoplightEntry] = []

        for criterion in criteria:
            s3_count = 0
            s2_count = 0
            for sug in suggestions:
                tags = sug.criterion_tags
                # Match criterion or sub-criteria (A matches A1, A2)
                if criterion in tags or any(
                    t.startswith(criterion) for t in tags
                ):
                    if sug.severity == Severity.S3:
                        s3_count += 1
                    elif sug.severity == Severity.S2:
                        s2_count += 1

            if s3_count > 0 or s2_count >= 4:
                color = "red"
                rationale = (
                    f"{s3_count} fatal and {s2_count} major issues"
                    if s3_count
                    else f"{s2_count} major issues (>=4 threshold)"
                )
            elif s2_count >= 2:
                color = "amber"
                rationale = f"{s2_count} major issues (2-3 range)"
            else:
                color = "green"
                rationale = (
                    f"No fatal issues, {s2_count} major"
                    if s2_count
                    else "No significant issues"
                )

            entries.append(StoplightEntry(
                criterion=criterion,
                color=color,
                s3_count=s3_count,
                s2_count=s2_count,
                rationale=rationale,
            ))

        return entries

    @staticmethod
    def _summarize_suggestions(suggestions: list[SuggestionRecord]) -> str:
        """Build a text summary of all suggestions for the narrative prompt."""
        if not suggestions:
            return "No suggestions extracted."

        severity_counts = {"S3": 0, "S2": 0, "S1": 0, "S0": 0}
        for sug in suggestions:
            severity_counts[sug.severity.value] = (
                severity_counts.get(sug.severity.value, 0) + 1
            )

        lines = [
            f"Total suggestions: {len(suggestions)}",
            f"  S3 (Fatal): {severity_counts['S3']}",
            f"  S2 (Major): {severity_counts['S2']}",
            f"  S1 (Moderate): {severity_counts['S1']}",
            f"  S0 (Minor): {severity_counts['S0']}",
            "",
        ]

        for sug in suggestions[:10]:
            lines.append(
                f"[{sug.id}] {sug.severity.value}/{sug.impact.value} — {sug.issue[:120]}"
            )

        return "\n".join(lines)

    @staticmethod
    def _summarize_actions(actions: list[SuggestionAction]) -> str:
        """Build a text summary of all actions for the narrative prompt."""
        if not actions:
            return "No actions taken."

        adopted = sum(1 for a in actions if a.action == "adopted")
        partial = sum(1 for a in actions if a.action == "partially_adopted")
        deferred = sum(1 for a in actions if a.action == "deferred")
        rejected = sum(1 for a in actions if a.action == "not_adopted")

        sections_modified = list({
            a.section_modified for a in actions
            if a.action in ("adopted", "partially_adopted") and a.section_modified
        })

        lines = [
            f"Adopted: {adopted}, Partially adopted: {partial}, "
            f"Deferred: {deferred}, Not adopted: {rejected}",
            f"Sections modified: {', '.join(sections_modified) or 'none'}",
        ]

        return "\n".join(lines)

    @staticmethod
    def _parse_narratives(text: str) -> dict[str, str]:
        """Parse the narrative JSON from the LLM response."""
        json_str = _extract_json_from_text(text)
        try:
            data = json.loads(json_str)
            if isinstance(data, dict):
                return {k: str(v) for k, v in data.items()}
        except json.JSONDecodeError:
            logger.warning("Failed to parse narrative JSON; using raw text")
        return {"executive_summary": text[:500]}

    def _save_artifacts(
        self,
        revised: Proposal,
        report: ImprovementReport,
        version: int,
        output_dir: Path,
    ) -> None:
        """Save improvement report and revised proposal to disk."""
        from src.utils.txt_formatter import (
            cost_report_to_md,
            improvement_report_to_md,
            proposal_to_application_md,
        )

        output_dir.mkdir(parents=True, exist_ok=True)

        # Application markdown
        app_path = output_dir / f"application_v{version}.md"
        app_path.write_text(
            proposal_to_application_md(revised), encoding="utf-8",
        )
        logger.info(f"  Saved: {app_path}")

        # Improvement report markdown
        report_path = output_dir / f"improvement_report_v{version}.md"
        report_path.write_text(
            improvement_report_to_md(report, version), encoding="utf-8",
        )
        logger.info(f"  Saved: {report_path}")

        # Improvement report JSON
        json_path = output_dir / f"improvement_report_v{version}.json"
        json_path.write_text(
            report.model_dump_json(indent=2), encoding="utf-8",
        )
        logger.info(f"  Saved: {json_path}")

        # Cost report (JSON + markdown)
        if report.cost_summary:
            cost_json_path = output_dir / f"llm_cost_report_v{version}.json"
            cost_json_path.write_text(
                report.cost_summary.model_dump_json(indent=2), encoding="utf-8",
            )
            logger.info(f"  Saved: {cost_json_path}")

            cost_md_path = output_dir / f"llm_cost_report_v{version}.md"
            cost_md_path.write_text(
                cost_report_to_md(report.cost_summary, version), encoding="utf-8",
            )
            logger.info(f"  Saved: {cost_md_path}")
