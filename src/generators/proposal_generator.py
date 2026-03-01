"""
ProposalGenerator: DraftIdea → complete FCT Proposal.
LLM provider/model read from cfg.generator; Scopus from cfg.scopus_*.
"""

from __future__ import annotations

import json
import logging

from src.config.fct_constants import CHAR_LIMITS, TYPOLOGY_RULES, ProjectType
from src.config.settings import cfg
from src.generators.models import (
    Deliverable,
    DraftIdea,
    Milestone,
    Proposal,
    ProposalTask,
)
from src.scrapers.scopus_client import ScopusArticle, ScopusScraper
from src.utils.json_utils import extract_json
from src.utils.llm_client import BaseLLMClient, get_llm_for_role
from src.utils.prompt_loader import get_prompt, load_prompt_template
from src.utils.sanitize import scrub_pii_for_llm
from src.utils.text_utils import safe_limit, safe_truncate

logger = logging.getLogger(__name__)


class ProposalGenerator:
    def __init__(self, llm: BaseLLMClient | None = None, scopus: ScopusScraper | None = None):
        self.llm = llm or get_llm_for_role(cfg.generator)
        self.scopus = scopus or ScopusScraper()

    async def generate(self, draft: DraftIdea) -> Proposal:
        """Transform a DraftIdea into a complete FCT PTDC proposal.

        Generates literature review, tasks, and budget.
        """
        logger.info(f"Generating proposal: {draft.title}")

        # Apply config.yaml defaults to draft where the draft is empty
        if not draft.typology:
            draft.typology = ProjectType(cfg.typology)
        if not draft.principal_contractor:
            draft.principal_contractor = cfg.principal_contractor
        if not draft.research_units and cfg.default_research_units:
            draft.research_units = cfg.default_research_units

        rules = TYPOLOGY_RULES[draft.typology]
        duration = draft.duration_months or rules.max_duration_months

        # 1. Literature
        articles = []
        if self.scopus.is_available:
            articles = await self.scopus.search_for_proposal(
                topic=draft.research_topic[:200],
                keywords=draft.keywords_en,
            )
        lit_ctx = self._lit_context(articles)

        # 2. Build proposal shell
        proposal = Proposal(
            title_en=draft.title,
            title_pt=draft.title_pt or draft.title,
            acronym=draft.acronym,
            typology=draft.typology,
            keywords_en=draft.keywords_en[:4],
            keywords_pt=draft.keywords_pt[:4],
            scientific_domain=draft.scientific_domain,
            scientific_area=draft.scientific_area,
            scientific_subarea=draft.scientific_subarea,
            duration_months=duration,
        )

        # PII-scrubbed copy for LLM prompts (names/emails replaced with role labels)
        safe_draft = self._scrub_draft_for_llm(draft)

        # 3. Generate sections sequentially
        for section, limit, need_lit in [
            ("abstract_en", CHAR_LIMITS.abstract_en, True),
            ("abstract_pt", CHAR_LIMITS.abstract_pt, False),
            ("state_of_art_objectives", CHAR_LIMITS.state_of_art_objectives, True),
            ("research_plan_methods", CHAR_LIMITS.research_plan_methods, True),
            ("institution_description", CHAR_LIMITS.institution_description, False),
            ("management_structure", CHAR_LIMITS.management_structure, False),
            ("ethics_justification", CHAR_LIMITS.ethics_justification, False),
        ]:
            ctx = lit_ctx if need_lit else ""
            text = await self._gen(
                section,
                safe_draft,
                ctx,
                proposal,
                limit,
            )
            setattr(proposal, section, text)

        proposal.bibliographic_references = self._fmt_refs(articles)

        # PI / Team (only if draft provides context)
        if draft.pi_career_summary:
            for sec, lim in [
                ("career_profile", CHAR_LIMITS.career_profile),
                ("contributions_new_ideas", CHAR_LIMITS.contributions_new_ideas),
                ("contributions_teams", CHAR_LIMITS.contributions_teams),
                ("contributions_society", CHAR_LIMITS.contributions_society),
            ]:
                setattr(proposal, sec, await self._gen(sec, safe_draft, "", proposal, lim))

        if draft.team_members:
            proposal.team_cv_synopsis = await self._gen(
                "team_cv_synopsis", safe_draft, "", proposal, CHAR_LIMITS.team_cv_synopsis
            )

        # Tasks, deliverables, milestones
        proposal.tasks = await self._gen_tasks(safe_draft, proposal, duration)
        proposal.deliverables = await self._gen_deliverables(proposal)
        proposal.milestones = await self._gen_milestones(proposal)
        proposal.sdg_alignment = draft.sdg_alignment[:3]
        proposal.total_budget = self._est_budget(proposal)

        logger.info(f"Proposal complete. Budget: €{proposal.total_budget:,.0f}")
        return proposal

    # --- helpers ---------------------------------------------------------------

    @staticmethod
    def _scrub_draft_for_llm(draft: DraftIdea) -> DraftIdea:
        """Return a copy of *draft* with contact PII (emails, phones, NIF) removed.

        Names are PRESERVED because the generator needs them to write natural
        prose (e.g. "Prof. Silva has led...").  Only the reviewer pathway
        anonymises identities (see panel_reviewer.py).
        """
        d = draft.model_copy(deep=True)
        if d.pi:
            d.pi.email = ""
        for tm in d.team_members:
            tm.email = ""
        for tm in d.hirings_planned:
            tm.email = ""
        d.pi_career_summary = scrub_pii_for_llm(d.pi_career_summary)
        d.research_topic = scrub_pii_for_llm(d.research_topic)
        d.methodology_notes = scrub_pii_for_llm(d.methodology_notes)
        d.budget_notes = scrub_pii_for_llm(d.budget_notes)
        d.ethical_considerations = scrub_pii_for_llm(d.ethical_considerations)
        return d

    async def _gen(
        self,
        section: str,
        draft: DraftIdea,
        lit: str,
        proposal: Proposal,
        limit: int,
    ) -> str:
        target = safe_limit(limit)
        prompt = self._prompt(section, draft, lit, proposal, target)
        system = get_prompt("system", "generator")
        resp = await self.llm.generate(
            prompt, system=system, max_tokens=limit * 2, temperature=cfg.generator.temperature
        )
        text = resp.text.strip()
        if len(text) > limit:
            text = await self._trim(text, limit, section)
        # Ensure text doesn't end mid-sentence even when under the hard limit
        if len(text) > target:
            text = safe_truncate(text, limit)
        logger.info(f"  {section}: {len(text)}/{limit} chars")
        return text

    async def _trim(self, text: str, limit: int, section: str) -> str:
        target = safe_limit(limit)
        prompt = (
            f"Condense this '{section}' section to "
            f"\u2264{target} chars, keeping key arguments.\n\n{text}"
        )
        resp = await self.llm.generate(
            prompt,
            max_tokens=limit,
            temperature=0.1,
        )
        r = resp.text.strip()
        return safe_truncate(r, limit) if len(r) > limit else r

    async def _gen_tasks(
        self,
        draft: DraftIdea,
        proposal: Proposal,
        duration: int,
    ) -> list[ProposalTask]:
        prompt = load_prompt_template("proposal_tasks").format(
            topic=safe_truncate(draft.research_topic, 500),
            research_questions="; ".join(draft.research_questions),
            duration=duration,
            typology=draft.typology.value,
            sota_excerpt=safe_truncate(proposal.state_of_art_objectives, 1500),
            plan_excerpt=safe_truncate(proposal.research_plan_methods, 2000),
            method_notes=safe_truncate(draft.methodology_notes, 500),
            task_desc_limit=CHAR_LIMITS.task_description,
            cost_just_limit=CHAR_LIMITS.cost_justification,
        )
        resp = await self.llm.generate_json(prompt, max_tokens=8000)
        try:
            data = json.loads(extract_json(resp.text))
            return [
                ProposalTask(
                    number=t.get("number", i + 1),
                    denomination=t.get("denomination", f"Task {i + 1}")[:150],
                    description=safe_truncate(
                        t.get("description", ""), CHAR_LIMITS.task_description
                    ),
                    expected_results=t.get("expected_results", ""),
                    person_months=t.get("person_months", 3.0),
                    start_month=t.get("start_month", 1),
                    duration_months=t.get("duration_months", 6),
                    cost_justification=safe_truncate(
                        t.get("cost_justification", ""), CHAR_LIMITS.cost_justification
                    ),
                )
                for i, t in enumerate(data)
            ]
        except Exception as e:
            logger.error(f"Task parse error: {e}")
            return self._fallback_tasks(duration)

    async def _gen_deliverables(self, proposal: Proposal) -> list[Deliverable]:
        summary = "\n".join(
            f"T{t.number}: {t.denomination} "
            f"(m{t.start_month}\u2013{t.start_month + t.duration_months - 1})"
            for t in proposal.tasks
        )
        prompt = load_prompt_template("proposal_deliverables").format(
            tasks_summary=summary,
            deliv_desc_limit=CHAR_LIMITS.deliverable_description,
        )
        resp = await self.llm.generate_json(prompt, max_tokens=4000)
        try:
            data = json.loads(extract_json(resp.text))
            return [
                Deliverable(
                    code=d.get("code", f"D{i + 1}"),
                    title=d.get("title", ""),
                    description=safe_truncate(
                        d.get("description", ""),
                        CHAR_LIMITS.deliverable_description,
                    ),
                    related_tasks=d.get("related_tasks", []),
                    due_month=d.get("due_month", 0),
                )
                for i, d in enumerate(data)
            ]
        except Exception:
            return []

    async def _gen_milestones(self, proposal: Proposal) -> list[Milestone]:
        summary = "\n".join(f"T{t.number}: {t.denomination}" for t in proposal.tasks)
        prompt = load_prompt_template("proposal_milestones").format(
            tasks_summary=summary,
            duration=proposal.duration_months,
            milestone_desc_limit=CHAR_LIMITS.milestone_description,
        )
        resp = await self.llm.generate_json(prompt, max_tokens=2000)
        try:
            data = json.loads(extract_json(resp.text))
            return [
                Milestone(
                    code=m.get("code", f"M{i + 1}"),
                    denomination=m.get("denomination", ""),
                    description=safe_truncate(
                        m.get("description", ""),
                        CHAR_LIMITS.milestone_description,
                    ),
                    related_tasks=m.get("related_tasks", []),
                    due_month=m.get("due_month", 0),
                )
                for i, m in enumerate(data)
            ]
        except Exception:
            return []

    def _prompt(
        self,
        section: str,
        draft: DraftIdea,
        lit: str,
        proposal: Proposal,
        limit: int,
    ) -> str:
        base = load_prompt_template("proposal_system").format(
            section=section,
            title=draft.title,
            typology=draft.typology.value,
            topic=draft.research_topic[:800],
            research_questions="; ".join(draft.research_questions),
            limit=limit,
        )
        if lit:
            base += f"\n{lit}\n"
        section_prompts = {
            "state_of_art_objectives": {},
            "research_plan_methods": {
                "sota_excerpt": proposal.state_of_art_objectives[:1500],
            },
            "abstract_pt": {
                "abstract_en": proposal.abstract_en[:2500],
            },
            "institution_description": {
                "principal_contractor": draft.principal_contractor,
                "research_units": ", ".join(draft.research_units),
            },
            "career_profile": {
                "pi_career_summary": draft.pi_career_summary[:1500],
            },
            "management_structure": {
                "tasks_list": ", ".join(f"T{t.number}" for t in proposal.tasks),
            },
        }
        if section in section_prompts:
            tpl = load_prompt_template(f"section_{section}")
            base += tpl.format(**section_prompts[section])
        return base

    def _lit_context(self, articles: list[ScopusArticle]) -> str:
        if not articles:
            return ""
        lines = [
            f"- {a.authors} ({a.year}): {a.title}. {a.journal}. [Cited: {a.citation_count}]"
            for a in articles[:15]
        ]
        abstracts = [
            f"({a.authors}, {a.year}): {a.abstract[:300]}\u2026" for a in articles[:5] if a.abstract
        ]
        return "LITERATURE:\n" + "\n".join(lines) + "\n\nABSTRACTS:\n" + "\n".join(abstracts)

    def _fmt_refs(self, articles: list[ScopusArticle]) -> str:
        if not articles:
            return ""
        refs = "\n".join(f"[{i}] {a.apa_reference}" for i, a in enumerate(articles[:30], 1))
        return refs[: CHAR_LIMITS.bibliographic_references]

    def _est_budget(self, proposal: Proposal) -> float:
        direct = sum(t.budget.direct_costs for t in proposal.tasks)
        if direct == 0:
            return TYPOLOGY_RULES[proposal.typology].max_funding_eur * 0.8
        return direct * 1.25

    def _fallback_tasks(self, dur: int) -> list[ProposalTask]:
        return [
            ProposalTask(
                number=1,
                denomination="Literature Review & Framework",
                description="SLR and framework.",
                person_months=4,
                start_month=1,
                duration_months=6,
            ),
            ProposalTask(
                number=2,
                denomination="Data Collection",
                description="Primary data collection.",
                person_months=8,
                start_month=4,
                duration_months=12,
            ),
            ProposalTask(
                number=3,
                denomination="Analysis & Results",
                description="Analysis and interpretation.",
                person_months=6,
                start_month=13,
                duration_months=12,
            ),
            ProposalTask(
                number=4,
                denomination="Dissemination & Management",
                description="Publications, coordination.",
                person_months=4,
                start_month=1,
                duration_months=dur,
            ),
        ]
