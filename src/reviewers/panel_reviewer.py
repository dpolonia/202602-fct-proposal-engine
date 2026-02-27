"""
Multi-Model AI Peer Reviewer.
Panel composition, personas, and models are fully user-configurable via config.yaml.
Consensus and revision LLMs are also independently configurable.
"""

from __future__ import annotations

import asyncio
import json
import logging

from src.config.fct_constants import CHAR_LIMITS, EVAL_CRITERIA
from src.config.settings import LLMProvider, ReviewerDef, cfg
from src.generators.models import (
    ConsensusReport, CriterionScore, Proposal, ReviewReport,
)
from src.utils.llm_client import BaseLLMClient, get_llm_client, get_llm_for_role

logger = logging.getLogger(__name__)


# =============================================================================
# Individual Reviewer
# =============================================================================

class AIReviewer:
    """One AI reviewer, configured from a ReviewerDef in config.yaml."""

    def __init__(self, definition: ReviewerDef):
        self.defn = definition
        try:
            self.llm = get_llm_client(provider=definition.provider, model=definition.model)
        except Exception as e:
            logger.warning(f"Skipping reviewer '{definition.id}': {e}")
            self.llm = None

    async def review(self, proposal: Proposal) -> ReviewReport | None:
        if not self.llm:
            return None

        prompt = self._build_prompt(proposal)
        system = self._build_system()

        try:
            resp = await self.llm.generate(prompt=prompt, system=system, max_tokens=6000, temperature=0.4)
            return self._parse(resp.text)
        except Exception as e:
            logger.error(f"Review failed ({self.defn.id}): {e}")
            return None

    def _build_system(self) -> str:
        persona = self.defn.persona or (
            f"You are an international peer reviewer specialising in {self.defn.perspective}."
        )
        return (
            f"{persona}\n\n"
            "You evaluate FCT PTDC 2025 proposals. Be specific, cite exact proposal sections, "
            "identify both strengths and weaknesses, and give actionable suggestions."
        )

    def _build_prompt(self, p: Proposal) -> str:
        tasks_txt = "\n".join(
            f"  T{t.number}: {t.denomination} ({t.duration_months}mo, {t.person_months}PM) "
            f"— {t.description[:200]}…"
            for t in p.tasks
        )
        deliverables_txt = "\n".join(
            f"  {d.code}: {d.title} (month {d.due_month})" for d in p.deliverables
        )
        return f"""Evaluate this FCT PTDC 2025 proposal.

=== PROPOSAL ===
TITLE: {p.title_en}
TYPOLOGY: {p.typology.value} | DURATION: {p.duration_months} mo | BUDGET: €{p.total_budget:,.0f}

--- ABSTRACT ---
{p.abstract_en}

--- STATE OF THE ART & OBJECTIVES ---
{p.state_of_art_objectives}

--- RESEARCH PLAN & METHODS ---
{p.research_plan_methods}

--- TASKS ---
{tasks_txt}

--- DELIVERABLES ---
{deliverables_txt}

--- MANAGEMENT ---
{p.management_structure}

--- PI CAREER PROFILE ---
{p.career_profile[:2000]}

--- TEAM CV SYNOPSIS ---
{p.team_cv_synopsis[:2000]}

--- ETHICS ---
{p.ethics_justification}

=== FCT EVALUATION CRITERIA ===
A (40%): Scientific merit (A1, 50%) + Innovation (A2, 50%)
B (30%): PI merit (B1, 60%) + Team (B2, 40%)
C (30%): Feasibility, deliverables, budget adequacy

Your focus: {', '.join(self.defn.focus_criteria)}

Return JSON:
{{
  "overall_score": <1-10>,
  "criterion_scores": [
    {{"criterion": "A", "sub_criterion": "A1", "score": <1-10>,
      "justification": "…", "strengths": ["…"], "weaknesses": ["…"], "suggestions": ["…"]}}
  ],
  "general_comments": "…",
  "major_revisions": ["…"],
  "minor_revisions": ["…"],
  "decision": "accept|minor_revision|major_revision|reject"
}}
JSON ONLY."""

    def _parse(self, text: str) -> ReviewReport:
        clean = text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1]
        if clean.endswith("```"):
            clean = clean.rsplit("```", 1)[0]
        clean = clean.strip()

        try:
            data = json.loads(clean)
        except json.JSONDecodeError:
            logger.warning(f"JSON parse failed for {self.defn.id}; using raw text")
            return ReviewReport(
                reviewer_id=self.defn.id, reviewer_model=self.defn.model,
                reviewer_provider=self.defn.provider.value, perspective=self.defn.perspective,
                overall_score=5.0, general_comments=text[:3000], decision="major_revision",
            )

        scores = [
            CriterionScore(
                criterion=cs.get("criterion", ""), sub_criterion=cs.get("sub_criterion", ""),
                score=float(cs.get("score", 5.0)), justification=cs.get("justification", ""),
                strengths=cs.get("strengths", []), weaknesses=cs.get("weaknesses", []),
                suggestions=cs.get("suggestions", []),
            )
            for cs in data.get("criterion_scores", [])
        ]

        return ReviewReport(
            reviewer_id=self.defn.id, reviewer_model=self.defn.model,
            reviewer_provider=self.defn.provider.value, perspective=self.defn.perspective,
            overall_score=float(data.get("overall_score", 5.0)),
            criterion_scores=scores,
            general_comments=data.get("general_comments", ""),
            major_revisions=data.get("major_revisions", []),
            minor_revisions=data.get("minor_revisions", []),
            decision=data.get("decision", "major_revision"),
        )


# =============================================================================
# Panel Orchestrator
# =============================================================================

class ReviewPanel:
    """
    Builds the reviewer roster from config.yaml, runs reviews in parallel,
    synthesises consensus using cfg.consensus LLM.
    """

    def __init__(self):
        defs = cfg.enabled_reviewers
        self.reviewers = [AIReviewer(d) for d in defs]
        self.consensus_llm = get_llm_for_role(cfg.consensus)
        logger.info(f"Panel initialised: {[d.id for d in defs]}")

    async def review(self, proposal: Proposal) -> ConsensusReport:
        logger.info(f"Running panel review ({len(self.reviewers)} reviewers)…")

        tasks = [r.review(proposal) for r in self.reviewers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        reviews: list[ReviewReport] = []
        for i, res in enumerate(results):
            if isinstance(res, ReviewReport) and res is not None:
                reviews.append(res)
                logger.info(f"  {res.reviewer_id}: score={res.overall_score:.1f} decision={res.decision}")
            elif isinstance(res, Exception):
                logger.warning(f"  Reviewer {i} failed: {res}")

        if not reviews:
            return ConsensusReport(panel_decision="error", panel_narrative="No reviews completed.")

        return await self._consensus(reviews, proposal)

    async def _consensus(self, reviews: list[ReviewReport], proposal: Proposal) -> ConsensusReport:
        all_scores: dict[str, list[float]] = {}
        all_strengths, all_weaknesses, all_revisions = [], [], []

        for r in reviews:
            for cs in r.criterion_scores:
                key = cs.sub_criterion or cs.criterion
                all_scores.setdefault(key, []).append(cs.score)
                all_strengths.extend(cs.strengths)
                all_weaknesses.extend(cs.weaknesses)
            all_revisions.extend(r.major_revisions)

        w = {k: sum(v) / len(v) for k, v in all_scores.items() if v}
        a = w.get("A1", 5) * 0.5 + w.get("A2", 5) * 0.5
        b = w.get("B1", 5) * 0.6 + w.get("B2", 5) * 0.4
        c = w.get("C", 5)
        score = a * 0.4 + b * 0.3 + c * 0.3

        reviews_txt = "\n\n".join(
            f"=== {r.reviewer_id} ({r.perspective}) — {r.overall_score}/10 ===\n"
            f"Decision: {r.decision}\n{r.general_comments[:500]}\n"
            f"Major: {'; '.join(r.major_revisions[:3])}"
            for r in reviews
        )
        narrative_resp = await self.consensus_llm.generate(
            f"""Synthesise {len(reviews)} reviews into a panel consensus for "{proposal.title_en}".

REVIEWS:
{reviews_txt}

SCORES: {json.dumps(w, indent=2)}
CONSENSUS: {score:.1f}/10

Write ~500 words: key strengths, critical weaknesses, top-5 priority revisions,
panel recommendation. Plain text.""",
            max_tokens=3000, temperature=0.3,
        )

        decisions = [r.decision for r in reviews]
        if score >= 8.0 and all(d in ("accept", "minor_revision") for d in decisions):
            decision = "accept"
        elif score >= 6.5:
            decision = "minor_revision"
        elif score >= 5.0:
            decision = "major_revision"
        else:
            decision = "reject"

        return ConsensusReport(
            individual_reviews=reviews,
            consensus_score=round(score, 1),
            weighted_scores={"A": round(a, 1), "B": round(b, 1), "C": round(c, 1)},
            key_strengths=list(dict.fromkeys(all_strengths))[:8],
            key_weaknesses=list(dict.fromkeys(all_weaknesses))[:8],
            priority_revisions=list(dict.fromkeys(all_revisions))[:10],
            panel_decision=decision,
            panel_narrative=narrative_resp.text.strip(),
        )


# =============================================================================
# Revision Engine
# =============================================================================

class RevisionEngine:
    """Applies review feedback to improve proposal. Uses cfg.revision LLM."""

    def __init__(self, llm: BaseLLMClient | None = None):
        self.llm = llm or get_llm_for_role(cfg.revision)

    async def revise(self, proposal: Proposal, consensus: ConsensusReport) -> Proposal:
        logger.info(f"Revising proposal (panel score: {consensus.consensus_score})…")
        revised = proposal.model_copy(deep=True)

        for section, limit in self._weak_sections(consensus):
            text = getattr(revised, section, "")
            if not text:
                continue
            feedback = self._feedback_for(section, consensus)
            if not feedback:
                continue

            resp = await self.llm.generate(
                f"""Revise the '{section}' section based on peer-review feedback.

CURRENT ({len(text)} chars, limit {limit}):
{text}

FEEDBACK:
{feedback}

Preserve strengths, fix weaknesses. Stay ≤{limit} chars. Plain text only. Return ONLY revised text.""",
                max_tokens=limit * 2, temperature=cfg.revision.temperature,
            )
            new = resp.text.strip()
            if len(new) > limit:
                new = new[:limit]
            setattr(revised, section, new)
            logger.info(f"  Revised '{section}': {len(new)}/{limit} chars")

        return revised

    def _weak_sections(self, consensus):
        sections = []
        for r in consensus.individual_reviews:
            for cs in r.criterion_scores:
                if cs.score < 7.0:
                    if cs.sub_criterion in ("A1", "A2"):
                        sections.append(("state_of_art_objectives", CHAR_LIMITS.state_of_art_objectives))
                        sections.append(("research_plan_methods", CHAR_LIMITS.research_plan_methods))
                    elif cs.sub_criterion == "B1":
                        sections.append(("career_profile", CHAR_LIMITS.career_profile))
                    elif cs.sub_criterion == "B2":
                        sections.append(("team_cv_synopsis", CHAR_LIMITS.team_cv_synopsis))
                    elif cs.criterion == "C":
                        sections.append(("management_structure", CHAR_LIMITS.management_structure))
        return list(dict.fromkeys(sections))

    def _feedback_for(self, section, consensus):
        mapping = {
            "state_of_art_objectives": ["A1", "A2", "A"],
            "research_plan_methods": ["A1", "C"],
            "career_profile": ["B1"], "contributions_new_ideas": ["B1"],
            "team_cv_synopsis": ["B2"], "management_structure": ["C"],
            "abstract_en": ["A1", "A2"],
        }
        relevant = mapping.get(section, [])
        parts = []
        for r in consensus.individual_reviews:
            for cs in r.criterion_scores:
                if cs.criterion in relevant or cs.sub_criterion in relevant:
                    if cs.weaknesses:
                        parts.append(f"[{r.reviewer_id}] Weaknesses: {'; '.join(cs.weaknesses)}")
                    if cs.suggestions:
                        parts.append(f"[{r.reviewer_id}] Suggestions: {'; '.join(cs.suggestions)}")
        for rev in consensus.priority_revisions[:5]:
            parts.append(f"[Panel] {rev}")
        return "\n".join(parts)
