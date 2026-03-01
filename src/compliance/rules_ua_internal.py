"""
UA internal rules — UA01-UA13.

Most are admin-only (WARN). A few are auto-checkable.
"""

from __future__ import annotations

from src.compliance.models import (
    ComplianceCategory,
    ComplianceFinding,
    ComplianceSeverity,
    ComplianceStatus,
)
from src.compliance.registry import RuleRegistry
from src.config.fct_constants import BUDGET_RULES

# --- Admin-only rules (WARN) ---

_ADMIN_RULES = [
    (
        "UA01",
        ComplianceSeverity.CRITICAL,
        "PI must have a valid employment contract with UA (admin verification)",
    ),
    (
        "UA02",
        ComplianceSeverity.CRITICAL,
        "PI contract must cover the full project duration (admin verification)",
    ),
    (
        "UA04",
        ComplianceSeverity.MAJOR,
        "Internal approval form must be submitted (admin verification)",
    ),
    (
        "UA05",
        ComplianceSeverity.MAJOR,
        "Department director approval obtained (admin verification)",
    ),
    (
        "UA06",
        ComplianceSeverity.MAJOR,
        "Research unit coordinator approval obtained (admin verification)",
    ),
    (
        "UA07",
        ComplianceSeverity.CRITICAL,
        "Submitted before UA internal deadline (admin verification)",
    ),
    (
        "UA08",
        ComplianceSeverity.MAJOR,
        "Research unit endorsement letter obtained (admin verification)",
    ),
    (
        "UA09",
        ComplianceSeverity.MAJOR,
        "Institutional commitment declaration prepared (admin verification)",
    ),
    (
        "UA10",
        ComplianceSeverity.MINOR,
        "Institution name matches official UA designation (manual check)",
    ),
    ("UA11", ComplianceSeverity.MINOR, "PI CIENCIAVITAE profile is current (manual check)"),
    (
        "UA12",
        ComplianceSeverity.MINOR,
        "Foreign researcher budget in correct heading (manual check)",
    ),
]

for _rid, _sev, _desc in _ADMIN_RULES:

    def _make_check(rid=_rid, sev=_sev, desc=_desc):
        def check(proposal, draft=None):
            return ComplianceFinding(
                rule_id=rid,
                category=ComplianceCategory.UA_INTERNAL,
                severity=sev,
                status=ComplianceStatus.WARN,
                description=desc,
                notes="Cannot verify from proposal alone — requires admin check.",
            )

        return check

    RuleRegistry.register(
        rule_id=_rid,
        category=ComplianceCategory.UA_INTERNAL,
        severity=_sev,
        description=_desc,
        auto_checkable=False,
    )(_make_check())


# --- UA03: Budget >= UA minimum ---


@RuleRegistry.register(
    rule_id="UA03",
    category=ComplianceCategory.UA_INTERNAL,
    severity=ComplianceSeverity.MAJOR,
    description=f"Budget must be >= EUR {BUDGET_RULES.ua_minimum_budget_eur:,} (UA internal rule)",
)
def check_ua03(proposal, draft=None) -> ComplianceFinding:
    min_budget = BUDGET_RULES.ua_minimum_budget_eur
    if proposal.total_budget < min_budget and proposal.total_budget > 0:
        return ComplianceFinding(
            rule_id="UA03",
            category=ComplianceCategory.UA_INTERNAL,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.FAIL,
            description=f"Budget below UA minimum (EUR {min_budget:,})",
            actual_value=f"EUR {proposal.total_budget:,.0f}",
            expected_value=f">= EUR {min_budget:,}",
            field_path="total_budget",
            suggestion=f"Increase budget to at least EUR {min_budget:,}.",
        )
    return ComplianceFinding(
        rule_id="UA03",
        category=ComplianceCategory.UA_INTERNAL,
        severity=ComplianceSeverity.MAJOR,
        status=ComplianceStatus.PASS,
        description="Budget meets UA minimum requirement",
        actual_value=f"EUR {proposal.total_budget:,.0f}",
        expected_value=f">= EUR {min_budget:,}",
    )


# --- UA13: Project start date >= 2027-01-01 ---


@RuleRegistry.register(
    rule_id="UA13",
    category=ComplianceCategory.UA_INTERNAL,
    severity=ComplianceSeverity.MAJOR,
    description="Project start date must be >= 2027-01-01",
)
def check_ua13(proposal, draft=None) -> ComplianceFinding:
    if not proposal.start_date:
        return ComplianceFinding(
            rule_id="UA13",
            category=ComplianceCategory.UA_INTERNAL,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.WARN,
            description="No start date specified",
            notes="Start date should be set to 2027-01-01 or later.",
        )
    if proposal.start_date < "2027-01-01":
        return ComplianceFinding(
            rule_id="UA13",
            category=ComplianceCategory.UA_INTERNAL,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.FAIL,
            description="Start date is before 2027-01-01",
            actual_value=proposal.start_date,
            expected_value=">= 2027-01-01",
            field_path="start_date",
            suggestion="Set start date to 2027-01-01 or later.",
        )
    return ComplianceFinding(
        rule_id="UA13",
        category=ComplianceCategory.UA_INTERNAL,
        severity=ComplianceSeverity.MAJOR,
        status=ComplianceStatus.PASS,
        description="Start date is 2027-01-01 or later",
        actual_value=proposal.start_date,
    )
