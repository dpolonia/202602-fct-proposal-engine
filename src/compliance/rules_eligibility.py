"""
Eligibility compliance rules — E01-E11.

Auto-checkable rules use TYPOLOGY_RULES and PARTICIPATION_RULES.
Admin-only rules produce WARN status.
"""

from __future__ import annotations

from src.compliance.models import (
    ComplianceCategory,
    ComplianceFinding,
    ComplianceSeverity,
    ComplianceStatus,
)
from src.compliance.registry import RuleRegistry
from src.config.fct_constants import (
    PARTICIPATION_RULES,
    TYPOLOGY_RULES,
    ProjectType,
)


def _get_typology_rules(proposal):
    """Get TypologyRules for the proposal's typology."""
    try:
        return TYPOLOGY_RULES[proposal.typology]
    except (KeyError, TypeError):
        return None


# --- E01: Language and typology valid ---


@RuleRegistry.register(
    rule_id="E01",
    category=ComplianceCategory.ELIGIBILITY,
    severity=ComplianceSeverity.BLOCKER,
    description="Typology must be valid (SR&TD or PEX)",
)
def check_e01(proposal, draft=None) -> ComplianceFinding:
    valid_types = [t.value for t in ProjectType]
    typology_val = (
        proposal.typology.value if hasattr(proposal.typology, "value") else str(proposal.typology)
    )
    if typology_val not in valid_types:
        return ComplianceFinding(
            rule_id="E01",
            category=ComplianceCategory.ELIGIBILITY,
            severity=ComplianceSeverity.BLOCKER,
            status=ComplianceStatus.FAIL,
            description="Typology must be valid (SR&TD or PEX)",
            actual_value=typology_val,
            expected_value=f"One of {valid_types}",
            field_path="typology",
        )
    return ComplianceFinding(
        rule_id="E01",
        category=ComplianceCategory.ELIGIBILITY,
        severity=ComplianceSeverity.BLOCKER,
        status=ComplianceStatus.PASS,
        description="Typology must be valid (SR&TD or PEX)",
        actual_value=typology_val,
        expected_value=f"One of {valid_types}",
        field_path="typology",
    )


# --- E02-E06: Admin-only (WARN) ---

_ADMIN_ONLY_RULES = [
    (
        "E02",
        ComplianceSeverity.CRITICAL,
        "PI can only apply as PI in 1 application (admin verification required)",
    ),
    (
        "E03",
        ComplianceSeverity.CRITICAL,
        "PI participation limits: max 1 as member if PI (admin verification required)",
    ),
    (
        "E04",
        ComplianceSeverity.CRITICAL,
        "Team member participation limits: max 2 if not PI (admin verification required)",
    ),
    (
        "E05",
        ComplianceSeverity.BLOCKER,
        "PI must not have active sanctions (admin verification required)",
    ),
    (
        "E06",
        ComplianceSeverity.BLOCKER,
        "No duplicate funding for same research (admin verification required)",
    ),
]

for _rid, _sev, _desc in _ADMIN_ONLY_RULES:

    def _make_admin_check(rid=_rid, sev=_sev, desc=_desc):
        def check(proposal, draft=None):
            return ComplianceFinding(
                rule_id=rid,
                category=ComplianceCategory.ELIGIBILITY,
                severity=sev,
                status=ComplianceStatus.WARN,
                description=desc,
                notes="Cannot verify from proposal alone — requires admin check.",
            )

        return check

    RuleRegistry.register(
        rule_id=_rid,
        category=ComplianceCategory.ELIGIBILITY,
        severity=_sev,
        description=_desc,
        auto_checkable=False,
    )(_make_admin_check())


# --- E07: Duration within typology max ---


@RuleRegistry.register(
    rule_id="E07",
    category=ComplianceCategory.ELIGIBILITY,
    severity=ComplianceSeverity.BLOCKER,
    description="Duration must not exceed typology maximum",
)
def check_e07(proposal, draft=None) -> ComplianceFinding:
    rules = _get_typology_rules(proposal)
    if rules is None:
        return ComplianceFinding(
            rule_id="E07",
            category=ComplianceCategory.ELIGIBILITY,
            severity=ComplianceSeverity.BLOCKER,
            status=ComplianceStatus.SKIP,
            description="Duration check skipped — unknown typology",
        )
    if proposal.duration_months > rules.max_duration_months:
        return ComplianceFinding(
            rule_id="E07",
            category=ComplianceCategory.ELIGIBILITY,
            severity=ComplianceSeverity.BLOCKER,
            status=ComplianceStatus.FAIL,
            description="Duration must not exceed typology maximum",
            actual_value=f"{proposal.duration_months} months",
            expected_value=f"<= {rules.max_duration_months} months",
            field_path="duration_months",
            suggestion=f"Reduce duration to max {rules.max_duration_months} months.",
        )
    return ComplianceFinding(
        rule_id="E07",
        category=ComplianceCategory.ELIGIBILITY,
        severity=ComplianceSeverity.BLOCKER,
        status=ComplianceStatus.PASS,
        description="Duration must not exceed typology maximum",
        actual_value=f"{proposal.duration_months} months",
        expected_value=f"<= {rules.max_duration_months} months",
        field_path="duration_months",
    )


# --- E08: Budget within typology max ---


@RuleRegistry.register(
    rule_id="E08",
    category=ComplianceCategory.ELIGIBILITY,
    severity=ComplianceSeverity.BLOCKER,
    description="Total budget must not exceed typology maximum",
)
def check_e08(proposal, draft=None) -> ComplianceFinding:
    rules = _get_typology_rules(proposal)
    if rules is None:
        return ComplianceFinding(
            rule_id="E08",
            category=ComplianceCategory.ELIGIBILITY,
            severity=ComplianceSeverity.BLOCKER,
            status=ComplianceStatus.SKIP,
            description="Budget check skipped — unknown typology",
        )
    if proposal.total_budget > rules.max_funding_eur:
        return ComplianceFinding(
            rule_id="E08",
            category=ComplianceCategory.ELIGIBILITY,
            severity=ComplianceSeverity.BLOCKER,
            status=ComplianceStatus.FAIL,
            description="Total budget must not exceed typology maximum",
            actual_value=f"EUR {proposal.total_budget:,.0f}",
            expected_value=f"<= EUR {rules.max_funding_eur:,}",
            field_path="total_budget",
            suggestion=f"Reduce budget to max EUR {rules.max_funding_eur:,}.",
        )
    return ComplianceFinding(
        rule_id="E08",
        category=ComplianceCategory.ELIGIBILITY,
        severity=ComplianceSeverity.BLOCKER,
        status=ComplianceStatus.PASS,
        description="Total budget must not exceed typology maximum",
        actual_value=f"EUR {proposal.total_budget:,.0f}",
        expected_value=f"<= EUR {rules.max_funding_eur:,}",
        field_path="total_budget",
    )


# --- E09: Scientific domain non-empty ---


@RuleRegistry.register(
    rule_id="E09",
    category=ComplianceCategory.ELIGIBILITY,
    severity=ComplianceSeverity.CRITICAL,
    description="Scientific domain must be specified",
)
def check_e09(proposal, draft=None) -> ComplianceFinding:
    if not proposal.scientific_domain.strip():
        return ComplianceFinding(
            rule_id="E09",
            category=ComplianceCategory.ELIGIBILITY,
            severity=ComplianceSeverity.CRITICAL,
            status=ComplianceStatus.FAIL,
            description="Scientific domain must be specified",
            field_path="scientific_domain",
            suggestion="Add the FCT scientific domain classification.",
        )
    return ComplianceFinding(
        rule_id="E09",
        category=ComplianceCategory.ELIGIBILITY,
        severity=ComplianceSeverity.CRITICAL,
        status=ComplianceStatus.PASS,
        description="Scientific domain must be specified",
        actual_value=proposal.scientific_domain,
        field_path="scientific_domain",
    )


# --- E10: SDGs count ---


@RuleRegistry.register(
    rule_id="E10",
    category=ComplianceCategory.ELIGIBILITY,
    severity=ComplianceSeverity.MAJOR,
    description="SDG alignment: max 3 SDGs",
)
def check_e10(proposal, draft=None) -> ComplianceFinding:
    count = len(proposal.sdg_alignment)
    max_sdgs = PARTICIPATION_RULES.max_sdgs
    if count > max_sdgs:
        return ComplianceFinding(
            rule_id="E10",
            category=ComplianceCategory.ELIGIBILITY,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.FAIL,
            description="SDG alignment: max 3 SDGs",
            actual_value=str(count),
            expected_value=f"<= {max_sdgs}",
            field_path="sdg_alignment",
            suggestion=f"Reduce to max {max_sdgs} SDGs.",
        )
    return ComplianceFinding(
        rule_id="E10",
        category=ComplianceCategory.ELIGIBILITY,
        severity=ComplianceSeverity.MAJOR,
        status=ComplianceStatus.PASS,
        description="SDG alignment: max 3 SDGs",
        actual_value=str(count),
        expected_value=f"<= {max_sdgs}",
        field_path="sdg_alignment",
    )


# --- E11: Keywords EN/PT count match ---


@RuleRegistry.register(
    rule_id="E11",
    category=ComplianceCategory.ELIGIBILITY,
    severity=ComplianceSeverity.MINOR,
    description="Keywords EN and PT counts should match",
)
def check_e11(proposal, draft=None) -> ComplianceFinding:
    en_count = len(proposal.keywords_en)
    pt_count = len(proposal.keywords_pt)
    if en_count != pt_count and en_count > 0 and pt_count > 0:
        return ComplianceFinding(
            rule_id="E11",
            category=ComplianceCategory.ELIGIBILITY,
            severity=ComplianceSeverity.MINOR,
            status=ComplianceStatus.FAIL,
            description="Keywords EN and PT counts should match",
            actual_value=f"EN={en_count}, PT={pt_count}",
            expected_value="Same count for both",
            field_path="keywords_en / keywords_pt",
            suggestion="Ensure same number of keywords in EN and PT.",
        )
    return ComplianceFinding(
        rule_id="E11",
        category=ComplianceCategory.ELIGIBILITY,
        severity=ComplianceSeverity.MINOR,
        status=ComplianceStatus.PASS,
        description="Keywords EN and PT counts should match",
        actual_value=f"EN={en_count}, PT={pt_count}",
        field_path="keywords_en / keywords_pt",
    )
