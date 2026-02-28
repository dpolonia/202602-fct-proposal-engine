"""
End-to-end pipeline: DraftIdea → Generate → Review → Revise → Final.
Reads iterations, stop_on_accept, output formats from config.yaml.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from src.config.settings import cfg
from src.generators.models import ConsensusReport, DraftIdea, Proposal
from src.generators.proposal_generator import ProposalGenerator
from src.reviewers.panel_reviewer import ReviewPanel, RevisionEngine

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(
        self,
        generator: ProposalGenerator | None = None,
        panel: ReviewPanel | None = None,
        reviser: RevisionEngine | None = None,
    ):
        self.generator = generator or ProposalGenerator()
        self.panel = panel or ReviewPanel()
        self.reviser = reviser or RevisionEngine()

    async def run(
        self,
        draft: DraftIdea,
        iterations: int | None = None,
        output_dir: Path | None = None,
    ) -> dict:
        iters = iterations if iterations is not None else cfg.iterations
        out = output_dir or Path(cfg.output_dir) / datetime.now().strftime("%Y%m%d_%H%M%S")
        out.mkdir(parents=True, exist_ok=True)

        history: list[dict] = []
        consensus: ConsensusReport | None = None
        proposal: Proposal | None = None

        try:
            # --- Generate ---
            logger.info("=" * 60)
            logger.info("STEP 1: Generating initial proposal…")
            logger.info("=" * 60)
            proposal = await self.generator.generate(draft)
            if cfg.save_intermediates:
                self._save(proposal, out / "v0_proposal.json")

            for it in range(iters):
                logger.info("=" * 60)
                logger.info(f"ITERATION {it + 1}/{iters}")
                logger.info("=" * 60)

                # --- Review ---
                consensus = await self.panel.review(proposal)
                if cfg.save_intermediates:
                    self._save_review(consensus, out / f"v{it}_review.json")

                history.append({
                    "iteration": it,
                    "score": consensus.consensus_score,
                    "decision": consensus.panel_decision,
                    "weighted_scores": consensus.weighted_scores,
                })
                logger.info(
                    f"  Score: {consensus.consensus_score}/10  Decision: {consensus.panel_decision}"
                )

                # --- Early stop ---
                if cfg.stop_on_accept and consensus.panel_decision == "accept":
                    logger.info("Panel accepted — stopping early.")
                    break

                # --- Revise ---
                if it < iters - 1 or consensus.panel_decision in ("major_revision", "reject"):
                    proposal = await self.reviser.revise(proposal, consensus)
                    if cfg.save_intermediates:
                        self._save(proposal, out / f"v{it + 1}_proposal.json")

        except Exception:
            logger.exception("Pipeline failed — saving intermediate state")
            if proposal is not None:
                self._save(proposal, out / "partial_proposal.json")
            if consensus is not None:
                self._save_review(consensus, out / "partial_review.json")
            raise

        # --- Final outputs ---
        if cfg.out_json:
            self._save(proposal, out / "final_proposal.json")
        if cfg.out_char_report:
            (out / "char_report.json").write_text(json.dumps(proposal.char_count_report(), indent=2))
        if cfg.out_markdown:
            self._save_markdown(proposal, consensus, out / "proposal_summary.md")

        logger.info("=" * 60)
        logger.info(f"DONE — output: {out}")
        logger.info("=" * 60)

        return {
            "proposal": proposal,
            "final_review": consensus,
            "history": history,
            "output_dir": str(out),
        }

    # --- helpers ---------------------------------------------------------------

    def _save(self, proposal: Proposal, path: Path):
        path.write_text(proposal.model_dump_json(indent=2), encoding="utf-8")
        logger.info(f"  Saved: {path}")

    def _save_review(self, consensus: ConsensusReport, path: Path):
        path.write_text(consensus.model_dump_json(indent=2), encoding="utf-8")
        logger.info(f"  Saved: {path}")

    def _save_markdown(self, proposal: Proposal, consensus: ConsensusReport | None, path: Path):
        lines = [
            f"# {proposal.title_en}",
            f"**Acronym:** {proposal.acronym}  ",
            f"**Typology:** {proposal.typology.value}  ",
            f"**Duration:** {proposal.duration_months} months  ",
            f"**Budget:** €{proposal.total_budget:,.0f}\n",
            "## Abstract (EN)", proposal.abstract_en, "",
            "## State of the Art & Objectives", proposal.state_of_art_objectives, "",
            "## Research Plan & Methods", proposal.research_plan_methods, "",
            "## Tasks",
        ]
        for t in proposal.tasks:
            lines.append(f"**T{t.number}: {t.denomination}** (months {t.start_month}–"
                         f"{t.start_month + t.duration_months - 1}, {t.person_months} PM)")
            lines.append(t.description[:500])
            lines.append("")
        lines += ["## Management Structure", proposal.management_structure, ""]

        if consensus and cfg.include_review_narrative:
            lines += [
                "---",
                f"## Panel Review (Score: {consensus.consensus_score}/10 — {consensus.panel_decision})",
                consensus.panel_narrative,
            ]

        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"  Saved: {path}")


# --- Convenience for CLI / API -------------------------------------------------

async def run_pipeline(draft_path: str, output_dir: str | None = None,
                       iterations: int | None = None) -> dict:
    import yaml

    path = Path(draft_path)
    if path.suffix in (".yaml", ".yml"):
        with open(path) as f:
            data = yaml.safe_load(f)
    else:
        with open(path) as f:
            data = json.loads(f.read())

    draft = DraftIdea(**data)
    return await Pipeline().run(draft, iterations=iterations,
                                output_dir=Path(output_dir) if output_dir else None)
