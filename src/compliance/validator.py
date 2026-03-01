"""
Compliance validator orchestrator.

Runs all registered compliance rules against a proposal and produces
a ComplianceReport. Pure Python — no LLM calls.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from src.compliance.models import (
    ComplianceDelta,
    ComplianceFinding,
    ComplianceReport,
    ComplianceStatus,
)
from src.compliance.registry import RuleRegistry

logger = logging.getLogger(__name__)


class ComplianceValidator:
    """Orchestrates compliance validation across all registered rules."""

    def validate(
        self,
        proposal,
        draft=None,
        version: int = 1,
        previous_report: ComplianceReport | None = None,
        disabled_rules: list[str] | None = None,
        disabled_categories: list[str] | None = None,
    ) -> ComplianceReport:
        """Run all registered compliance rules and build a report.

        Args:
            proposal: Proposal to validate.
            draft: Optional DraftIdea for rules that need it.
            version: Proposal version number.
            previous_report: Previous report for delta computation.
            disabled_rules: Rule IDs to skip.
            disabled_categories: Category codes to skip entirely.

        Returns:
            ComplianceReport with all findings and aggregates.
        """
        disabled_rules = set(disabled_rules or [])
        disabled_categories = set(disabled_categories or [])

        typology_val = (
            proposal.typology.value
            if hasattr(proposal.typology, "value")
            else str(proposal.typology)
        )

        findings: list[ComplianceFinding] = []
        all_rules = RuleRegistry.get_all()

        logger.info(
            f"Compliance: validating v{version} against "
            f"{len(all_rules)} rules ({len(disabled_rules)} disabled)"
        )

        for rule_id, rule_def in sorted(all_rules.items()):
            # Skip if disabled by rule ID
            if rule_id in disabled_rules:
                findings.append(
                    ComplianceFinding(
                        rule_id=rule_id,
                        category=rule_def.category,
                        severity=rule_def.severity,
                        status=ComplianceStatus.SKIP,
                        description=rule_def.description,
                        notes="Disabled by configuration.",
                    )
                )
                continue

            # Skip if disabled by category
            if rule_def.category.value in disabled_categories:
                findings.append(
                    ComplianceFinding(
                        rule_id=rule_id,
                        category=rule_def.category,
                        severity=rule_def.severity,
                        status=ComplianceStatus.SKIP,
                        description=rule_def.description,
                        notes="Category disabled by configuration.",
                    )
                )
                continue

            # Skip if not applicable to this typology
            if typology_val not in rule_def.applicable_typologies:
                findings.append(
                    ComplianceFinding(
                        rule_id=rule_id,
                        category=rule_def.category,
                        severity=rule_def.severity,
                        status=ComplianceStatus.NA,
                        description=rule_def.description,
                        notes=f"Not applicable to {typology_val} typology.",
                    )
                )
                continue

            # Skip if not auto-checkable
            if not rule_def.auto_checkable:
                findings.append(
                    ComplianceFinding(
                        rule_id=rule_id,
                        category=rule_def.category,
                        severity=rule_def.severity,
                        status=ComplianceStatus.WARN,
                        description=rule_def.description,
                        notes="Requires manual/admin verification.",
                    )
                )
                continue

            # Skip if requires draft but no draft provided
            if rule_def.requires_draft and draft is None:
                findings.append(
                    ComplianceFinding(
                        rule_id=rule_id,
                        category=rule_def.category,
                        severity=rule_def.severity,
                        status=ComplianceStatus.WARN,
                        description=rule_def.description,
                        notes="Requires draft data (not provided).",
                    )
                )
                continue

            # Execute the check
            try:
                result = rule_def.check_fn(proposal, draft)
                if isinstance(result, list):
                    findings.extend(result)
                else:
                    findings.append(result)
            except Exception as e:
                logger.warning(f"Rule {rule_id} raised exception: {e}")
                findings.append(
                    ComplianceFinding(
                        rule_id=rule_id,
                        category=rule_def.category,
                        severity=rule_def.severity,
                        status=ComplianceStatus.SKIP,
                        description=rule_def.description,
                        notes=f"Rule execution error: {e}",
                    )
                )

        # Build report
        report = ComplianceReport(
            version=version,
            timestamp=datetime.now(UTC).isoformat(),
            typology=typology_val,
            findings=findings,
        )
        report.compute_aggregates()

        # Compute delta
        if previous_report is not None:
            report.delta = self._compute_delta(previous_report, report)

        logger.info(
            f"Compliance v{version}: {report.total} checks — "
            f"{report.passed} PASS, {report.failed} FAIL "
            f"({report.blocker_count} blockers, {report.critical_count} critical), "
            f"{report.warned} WARN, {report.na} N/A, {report.skipped} SKIP"
        )
        logger.info(f"  Recommendation: {report.recommendation.value}")

        return report

    @staticmethod
    def _compute_delta(
        prev: ComplianceReport,
        curr: ComplianceReport,
    ) -> ComplianceDelta:
        """Compute what changed between two compliance reports."""
        prev_failed = {f.rule_id for f in prev.findings if f.status == ComplianceStatus.FAIL}
        curr_failed = {f.rule_id for f in curr.findings if f.status == ComplianceStatus.FAIL}
        prev_passed = {f.rule_id for f in prev.findings if f.status == ComplianceStatus.PASS}

        resolved = sorted(prev_failed - curr_failed)
        persists = sorted(prev_failed & curr_failed)
        new_failures = sorted(curr_failed - prev_failed)
        # Regressions: was PASS before, now FAIL
        regressions = sorted(curr_failed & prev_passed)

        return ComplianceDelta(
            resolved=resolved,
            persists=persists,
            new_failures=new_failures,
            regressions=regressions,
        )
