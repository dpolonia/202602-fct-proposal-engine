"""
Compliance report formatters.

Converts ComplianceReport to Markdown, JSON improvement list,
and SuggestionRecord list for review-iterate consumption.
"""

from __future__ import annotations

import json

from src.compliance.models import (
    ComplianceFinding,
    ComplianceReport,
    ComplianceSeverity,
    ComplianceStatus,
)
from src.generators.models import (
    Actionability,
    Confidence,
    Dependency,
    Effort,
    EvidenceStatus,
    Impact,
    Severity,
    SuggestionRecord,
)

# Severity mapping: ComplianceSeverity → review-iterate Severity
_SEVERITY_MAP = {
    ComplianceSeverity.BLOCKER: Severity.S3,
    ComplianceSeverity.CRITICAL: Severity.S2,
    ComplianceSeverity.MAJOR: Severity.S1,
    ComplianceSeverity.MINOR: Severity.S0,
}

# Effort mapping: compliance rules are generally small fixes
_EFFORT_MAP = {
    ComplianceSeverity.BLOCKER: Effort.F2,
    ComplianceSeverity.CRITICAL: Effort.F1,
    ComplianceSeverity.MAJOR: Effort.F1,
    ComplianceSeverity.MINOR: Effort.F0,
}


def compliance_to_md(report: ComplianceReport) -> str:
    """Convert a ComplianceReport to a Markdown summary."""
    lines = [
        f"# Compliance Report — v{report.version}",
        f"**Timestamp:** {report.timestamp[:19]}",
        f"**Typology:** {report.typology}",
        f"**Recommendation:** {report.recommendation.value}",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Total checks | {report.total} |",
        f"| Passed | {report.passed} |",
        f"| Failed | {report.failed} |",
        f"| Warned | {report.warned} |",
        f"| N/A | {report.na} |",
        f"| Skipped | {report.skipped} |",
        "",
        "### Severity Breakdown (FAIL only)",
        "",
        "| Severity | Count |",
        "|----------|-------|",
        f"| BLOCKER | {report.blocker_count} |",
        f"| CRITICAL | {report.critical_count} |",
        f"| MAJOR | {report.major_count} |",
        f"| MINOR | {report.minor_count} |",
        "",
    ]

    # Delta section
    if report.delta:
        d = report.delta
        lines += [
            "## Delta (vs previous version)",
            "",
            f"- **Resolved:** {', '.join(d.resolved) or 'none'}",
            f"- **Persists:** {', '.join(d.persists) or 'none'}",
            f"- **New failures:** {', '.join(d.new_failures) or 'none'}",
            f"- **Regressions:** {', '.join(d.regressions) or 'none'}",
            "",
        ]

    # Findings grouped by category
    by_cat: dict[str, list[ComplianceFinding]] = {}
    for f in report.findings:
        by_cat.setdefault(f.category.value, []).append(f)

    lines.append("## Findings by Category")
    lines.append("")

    for cat in sorted(by_cat.keys()):
        findings = by_cat[cat]
        lines.append(f"### {cat}")
        lines.append("")
        lines.append("| Rule | Status | Severity | Description | Notes |")
        lines.append("|------|--------|----------|-------------|-------|")
        for f in findings:
            sev = f.severity.name if f.status == ComplianceStatus.FAIL else ""
            notes = f.suggestion or f.notes or ""
            lines.append(
                f"| {f.rule_id} | {f.status.value} | {sev} | {f.description[:60]} | {notes[:50]} |"
            )
        lines.append("")

    return "\n".join(lines)


def compliance_to_json_improvements(report: ComplianceReport) -> str:
    """Convert FAIL/WARN findings to a JSON list for improvement consumption."""
    items = []
    for f in report.findings:
        if f.status not in (ComplianceStatus.FAIL, ComplianceStatus.WARN):
            continue
        items.append(
            {
                "rule_id": f.rule_id,
                "category": f.category.value,
                "severity": f.severity.name,
                "status": f.status.value,
                "description": f.description,
                "actual_value": f.actual_value,
                "expected_value": f.expected_value,
                "field_path": f.field_path,
                "suggestion": f.suggestion,
            }
        )

    # Sort by severity (BLOCKER first)
    items.sort(
        key=lambda x: {
            "BLOCKER": 0,
            "CRITICAL": 1,
            "MAJOR": 2,
            "MINOR": 3,
        }.get(x["severity"], 9)
    )

    return json.dumps(items, indent=2)


def compliance_to_suggestions(
    report: ComplianceReport,
) -> list[SuggestionRecord]:
    """Convert compliance FAIL findings to SuggestionRecords.

    These can be prepended to the review-iterate suggestion list
    to give compliance fixes priority.
    """
    suggestions = []
    counter = 0

    for f in report.findings:
        if f.status != ComplianceStatus.FAIL:
            continue

        counter += 1
        sev = _SEVERITY_MAP.get(f.severity, Severity.S1)
        eff = _EFFORT_MAP.get(f.severity, Effort.F1)

        # Determine target sections from field_path
        target_sections = []
        if f.field_path:
            # Extract the base field name
            base = f.field_path.split("[")[0].split("/")[0].strip()
            if base and base not in ("tasks", "deliverables", "milestones"):
                target_sections.append(base)

        suggestions.append(
            SuggestionRecord(
                id=f"COMP-{counter:03d}",
                source_reviewer="compliance_validator",
                source_text=f"[{f.rule_id}] {f.description}",
                issue=f.description,
                recommended_fix=f.suggestion or f"Fix {f.rule_id}: {f.description}",
                criterion_tags=_map_category_to_criteria(f.category.value),
                target_sections=target_sections,
                severity=sev,
                evidence_status=EvidenceStatus.E2,
                confidence=Confidence.C2,
                effort=eff,
                impact=Impact.I2 if sev in (Severity.S3, Severity.S2) else Impact.I1,
                dependency=Dependency.D0,
                actionability=Actionability.A2 if f.suggestion else Actionability.A1,
                acceptance_test=f"Rule {f.rule_id} passes after fix.",
            )
        )

    return suggestions


def _map_category_to_criteria(category: str) -> list[str]:
    """Map compliance category to FCT evaluation criteria tags."""
    mapping = {
        "E": ["E"],
        "CL": ["E"],
        "WP": ["C"],
        "BG": ["C"],
        "UA": ["E"],
        "ET": ["E"],
        "EV": ["A", "B", "C"],
    }
    return mapping.get(category, [])
