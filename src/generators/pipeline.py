"""
End-to-end pipeline: DraftIdea → Generate → Review → Revise → Final.
Reads iterations, stop_on_accept, output formats from config.yaml.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from src.config.settings import cfg
from src.generators.docx_exporter import DocxExporter
from src.generators.draft_updater import DraftUpdater
from src.generators.models import ConsensusReport, DraftIdea, Proposal
from src.generators.proposal_generator import ProposalGenerator
from src.reviewers.panel_reviewer import ReviewPanel, RevisionEngine
from src.utils.txt_formatter import char_report_to_txt, proposal_to_txt, review_to_txt

if TYPE_CHECKING:
    from src.reviewers.review_iterate import ReviewIterateEngine

# Lazy imports for compliance (avoid circular / heavy import on startup)
_compliance_loaded = False

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(
        self,
        generator: ProposalGenerator | None = None,
        panel: ReviewPanel | None = None,
        reviser: RevisionEngine | None = None,
        review_iterate_engine: ReviewIterateEngine | None = None,
    ):
        self.generator = generator or ProposalGenerator()
        self.panel = panel or ReviewPanel()
        self.reviser = reviser or RevisionEngine()
        self.review_iterate: ReviewIterateEngine | None = review_iterate_engine

    @staticmethod
    def _setup_output_dirs(base: Path) -> dict[str, Path]:
        """Create organised subdirectories and return a mapping of dir names to paths.

        Structure:
            base/
            ├── proposals/      v1-vN .json+.txt, final_proposal .json+.txt+.docx
            ├── reviews/        v1-vN .json+.txt, final_review.docx
            ├── drafts/         original_draft.yaml, draft_pre_vN.yaml, diffs, change logs
            ├── improvements/   application_vN.md, improvement_report_vN.md (review-iterate)
            └── summary/        proposal_summary .md+.docx, char_report .json+.txt
        """
        dirs = {
            "proposals": base / "proposals",
            "reviews": base / "reviews",
            "drafts": base / "drafts",
            "improvements": base / "improvements",
            "summary": base / "summary",
            "compliance": base / "compliance",
        }
        for d in dirs.values():
            d.mkdir(parents=True, exist_ok=True)
        return dirs

    async def run(
        self,
        draft: DraftIdea,
        iterations: int | None = None,
        output_dir: Path | None = None,
        draft_path: Path | None = None,
    ) -> dict:
        """Run the full generate-review-revise pipeline for the given draft idea."""
        iters = iterations if iterations is not None else cfg.iterations
        out = output_dir or Path(cfg.output_dir) / datetime.now().strftime("%Y%m%d_%H%M%S")
        out.mkdir(parents=True, exist_ok=True)
        dirs = self._setup_output_dirs(out)

        history: list[dict] = []
        draft_changes_history: list[dict] = []
        improvement_reports: list = []
        compliance_reports: list = []
        consensus: ConsensusReport | None = None
        proposal: Proposal | None = None
        draft_updater = DraftUpdater()

        # Compliance setup (lazy)
        compliance_validator = None
        if cfg.compliance_enabled:
            from src.compliance import ComplianceValidator

            compliance_validator = ComplianceValidator()

        try:
            # --- Generate ---
            logger.info("=" * 60)
            logger.info("STEP 1: Generating initial proposal…")
            logger.info("=" * 60)
            proposal = await self.generator.generate(draft)
            if cfg.save_intermediates:
                self._save(proposal, dirs["proposals"] / "v1_proposal.json")
                self._save_proposal_txt(proposal, dirs["proposals"] / "v1_proposal.txt")

            # --- Compliance check A: after v1, before review ---
            prev_compliance = None
            if compliance_validator and cfg.compliance_run_before_review:
                logger.info("=" * 60)
                logger.info("COMPLIANCE CHECK: v1 proposal")
                logger.info("=" * 60)
                compliance_report = compliance_validator.validate(
                    proposal,
                    draft,
                    version=1,
                    disabled_rules=cfg.compliance_disabled_rules,
                    disabled_categories=cfg.compliance_disabled_categories,
                )
                compliance_reports.append(compliance_report)
                prev_compliance = compliance_report
                self._save_compliance(compliance_report, dirs["compliance"], 1)

            for it in range(iters):
                version = it + 1  # 1-based version of current proposal
                logger.info("=" * 60)
                logger.info(f"ITERATION {version}/{iters}")
                logger.info("=" * 60)

                # --- Review (blind: draft names used to anonymise) ---
                consensus = await self.panel.review(proposal, draft=draft)
                if cfg.save_intermediates:
                    self._save_review(consensus, dirs["reviews"] / f"v{version}_review.json")
                    self._save_review_txt(consensus, dirs["reviews"] / f"v{version}_review.txt")

                history.append(
                    {
                        "iteration": version,
                        "score": consensus.consensus_score,
                        "decision": consensus.panel_decision,
                        "weighted_scores": consensus.weighted_scores,
                    }
                )
                logger.info(
                    f"  Score: {consensus.consensus_score}/10  Decision: {consensus.panel_decision}"
                )

                # --- Early stop ---
                if cfg.stop_on_accept and consensus.panel_decision == "accept":
                    logger.info("Panel accepted — stopping early.")
                    break

                # --- Update draft from review feedback ---
                will_revise = it < iters - 1 or consensus.panel_decision in (
                    "major_revision",
                    "reject",
                )
                if will_revise:
                    old_draft = draft.model_copy(deep=True)
                    DraftUpdater.save_backup(draft, version, dirs["drafts"], draft_path)
                    draft, changes = await draft_updater.update_draft(
                        draft,
                        consensus,
                        version,
                        dirs["drafts"],
                    )
                    DraftUpdater.save_diff(old_draft, draft, version, dirs["drafts"])
                    DraftUpdater.save_changes_log(changes, version, dirs["drafts"])
                    draft_changes_history.append(
                        {
                            "from_version": version,
                            "to_version": version + 1,
                            "changes": changes,
                        }
                    )

                    # --- Revise proposal ---
                    # Determine compliance report to feed into review-iterate
                    _compliance_for_ri = (
                        prev_compliance
                        if (
                            cfg.compliance_enabled
                            and cfg.compliance_feed_to_review_iterate
                            and prev_compliance
                        )
                        else None
                    )
                    if cfg.review_iterate_enabled:
                        if self.review_iterate is None:
                            from src.reviewers.review_iterate import ReviewIterateEngine

                            self.review_iterate = ReviewIterateEngine()
                        proposal, improvement_report = await self.review_iterate.revise(
                            proposal,
                            consensus,
                            version=version,
                            draft=draft,
                            output_dir=dirs["improvements"],
                            compliance_report=_compliance_for_ri,
                        )
                        improvement_reports.append(improvement_report)
                        # Enrich history entry
                        history[-1]["readiness_index"] = improvement_report.readiness_index
                        history[-1]["stoplight"] = [
                            {"criterion": s.criterion, "color": s.color}
                            for s in improvement_report.stoplight
                        ]
                    else:
                        proposal = await self.reviser.revise(proposal, consensus)

                    # --- Compliance check B: after revision ---
                    if compliance_validator and cfg.compliance_run_after_revision:
                        logger.info(f"  Compliance check: v{version + 1} proposal")
                        compliance_report = compliance_validator.validate(
                            proposal,
                            draft,
                            version=version + 1,
                            previous_report=prev_compliance,
                            disabled_rules=cfg.compliance_disabled_rules,
                            disabled_categories=cfg.compliance_disabled_categories,
                        )
                        compliance_reports.append(compliance_report)
                        prev_compliance = compliance_report
                        self._save_compliance(compliance_report, dirs["compliance"], version + 1)
                        # Enrich history entry with compliance stats
                        history[-1]["compliance"] = {
                            "blockers": compliance_report.blocker_count,
                            "critical": compliance_report.critical_count,
                            "failed": compliance_report.failed,
                            "recommendation": compliance_report.recommendation.value,
                        }

                    if cfg.save_intermediates:
                        self._save(
                            proposal,
                            dirs["proposals"] / f"v{version + 1}_proposal.json",
                        )
                        self._save_proposal_txt(
                            proposal,
                            dirs["proposals"] / f"v{version + 1}_proposal.txt",
                        )

        except Exception:
            logger.exception("Pipeline failed — saving intermediate state")
            if proposal is not None:
                self._save(proposal, dirs["proposals"] / "partial_proposal.json")
            if consensus is not None:
                self._save_review(consensus, dirs["reviews"] / "partial_review.json")
            raise

        # --- Final outputs ---
        if cfg.out_json:
            self._save(proposal, dirs["proposals"] / "final_proposal.json")
            self._save_proposal_txt(proposal, dirs["proposals"] / "final_proposal.txt")
        if cfg.out_char_report:
            report = proposal.char_count_report()
            (dirs["summary"] / "char_report.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            (dirs["summary"] / "char_report.txt").write_text(
                char_report_to_txt(report), encoding="utf-8"
            )
            logger.info(f"  Saved: {dirs['summary'] / 'char_report.json'}")
            logger.info(f"  Saved: {dirs['summary'] / 'char_report.txt'}")
        if cfg.out_markdown:
            self._save_markdown(proposal, consensus, dirs["summary"] / "proposal_summary.md")
        if cfg.out_docx:
            DocxExporter.export_final_proposal(proposal, dirs["proposals"] / "final_proposal.docx")
            DocxExporter.export_proposal_summary(
                proposal, consensus, history, dirs["summary"] / "proposal_summary.docx"
            )
            DocxExporter.export_final_review(
                consensus, history, draft_changes_history, dirs["reviews"] / "final_review.docx"
            )

        # --- Final compliance outputs ---
        if cfg.compliance_enabled and compliance_reports:
            from src.compliance.docx_exporter import ComplianceDocxExporter
            from src.compliance.formatters import (
                compliance_to_json_improvements,
                compliance_to_md,
            )

            final_cr = compliance_reports[-1]
            if cfg.out_docx:
                ComplianceDocxExporter.export(
                    final_cr,
                    dirs["compliance"] / "compliance_annex.docx",
                )
            if cfg.out_markdown:
                (dirs["compliance"] / "compliance_report.md").write_text(
                    compliance_to_md(final_cr), encoding="utf-8"
                )
            if cfg.out_json:
                (dirs["compliance"] / "compliance_improvements.json").write_text(
                    compliance_to_json_improvements(final_cr), encoding="utf-8"
                )
            logger.info(
                f"  Compliance: {final_cr.failed} failures "
                f"({final_cr.blocker_count} blockers) — "
                f"{final_cr.recommendation.value}"
            )

        logger.info("=" * 60)
        logger.info(f"DONE — output: {out}")
        logger.info("=" * 60)

        return {
            "proposal": proposal,
            "final_review": consensus,
            "history": history,
            "draft_changes": draft_changes_history,
            "improvement_reports": improvement_reports,
            "compliance_reports": compliance_reports,
            "output_dir": str(out),
        }

    # --- helpers ---------------------------------------------------------------

    def _save(self, proposal: Proposal, path: Path):
        path.write_text(proposal.model_dump_json(indent=2), encoding="utf-8")
        logger.info(f"  Saved: {path}")

    def _save_review(self, consensus: ConsensusReport, path: Path):
        path.write_text(consensus.model_dump_json(indent=2), encoding="utf-8")
        logger.info(f"  Saved: {path}")

    def _save_proposal_txt(self, proposal: Proposal, path: Path):
        path.write_text(proposal_to_txt(proposal), encoding="utf-8")
        logger.info(f"  Saved: {path}")

    def _save_review_txt(self, consensus: ConsensusReport, path: Path):
        path.write_text(review_to_txt(consensus), encoding="utf-8")
        logger.info(f"  Saved: {path}")

    def _save_compliance(self, report, compliance_dir: Path, version: int):
        """Save compliance report JSON and markdown."""
        compliance_dir.mkdir(parents=True, exist_ok=True)
        json_path = compliance_dir / f"v{version}_compliance.json"
        json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        logger.info(f"  Saved: {json_path}")

    def _save_markdown(
        self,
        proposal: Proposal,
        consensus: ConsensusReport | None,
        path: Path,
    ):
        lines = [
            f"# {proposal.title_en}",
            f"**Acronym:** {proposal.acronym}  ",
            f"**Typology:** {proposal.typology.value}  ",
            f"**Duration:** {proposal.duration_months} months  ",
            f"**Budget:** \u20ac{proposal.total_budget:,.0f}\n",
            "## Abstract (EN)",
            proposal.abstract_en,
            "",
            "## State of the Art & Objectives",
            proposal.state_of_art_objectives,
            "",
            "## Research Plan & Methods",
            proposal.research_plan_methods,
            "",
            "## Tasks",
        ]
        for t in proposal.tasks:
            lines.append(
                f"**T{t.number}: {t.denomination}** "
                f"(months {t.start_month}\u2013"
                f"{t.start_month + t.duration_months - 1}, {t.person_months} PM)"
            )
            lines.append(t.description[:500])
            lines.append("")
        lines += ["## Management Structure", proposal.management_structure, ""]

        if consensus and cfg.include_review_narrative:
            lines += [
                "---",
                f"## Panel Review (Score: {consensus.consensus_score}/10 "
                f"\u2014 {consensus.panel_decision})",
                consensus.panel_narrative,
            ]

        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"  Saved: {path}")


# --- Convenience for CLI / API -------------------------------------------------


async def run_pipeline(
    draft_path: str, output_dir: str | None = None, iterations: int | None = None
) -> dict:
    import yaml

    path = Path(draft_path)
    if path.suffix in (".yaml", ".yml"):
        with open(path) as f:
            data = yaml.safe_load(f)
    else:
        with open(path) as f:
            data = json.loads(f.read())

    draft = DraftIdea(**data)
    return await Pipeline().run(
        draft,
        iterations=iterations,
        output_dir=Path(output_dir) if output_dir else None,
        draft_path=path,
    )
