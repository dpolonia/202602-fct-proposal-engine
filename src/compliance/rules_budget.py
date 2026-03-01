"""
Budget compliance rules — BG01-BG10.

Financial arithmetic checks using TYPOLOGY_RULES and BUDGET_RULES.
"""

from __future__ import annotations

from src.compliance.models import (
    ComplianceCategory,
    ComplianceFinding,
    ComplianceSeverity,
    ComplianceStatus,
)
from src.compliance.registry import RuleRegistry
from src.config.fct_constants import BUDGET_RULES, TYPOLOGY_RULES


def _get_typology_rules(proposal):
    """Get TypologyRules for the proposal's typology."""
    try:
        return TYPOLOGY_RULES[proposal.typology]
    except (KeyError, TypeError):
        return None


# --- BG01: Total budget within typology max ---


@RuleRegistry.register(
    rule_id="BG01",
    category=ComplianceCategory.BUDGET,
    severity=ComplianceSeverity.BLOCKER,
    description="Total budget must not exceed typology maximum",
)
def check_bg01(proposal, draft=None) -> ComplianceFinding:
    rules = _get_typology_rules(proposal)
    if rules is None:
        return ComplianceFinding(
            rule_id="BG01",
            category=ComplianceCategory.BUDGET,
            severity=ComplianceSeverity.BLOCKER,
            status=ComplianceStatus.SKIP,
            description="Budget check skipped — unknown typology",
        )
    if proposal.total_budget > rules.max_funding_eur:
        return ComplianceFinding(
            rule_id="BG01",
            category=ComplianceCategory.BUDGET,
            severity=ComplianceSeverity.BLOCKER,
            status=ComplianceStatus.FAIL,
            description="Total budget exceeds typology maximum",
            actual_value=f"EUR {proposal.total_budget:,.0f}",
            expected_value=f"<= EUR {rules.max_funding_eur:,}",
            field_path="total_budget",
            suggestion=f"Reduce to max EUR {rules.max_funding_eur:,}.",
        )
    return ComplianceFinding(
        rule_id="BG01",
        category=ComplianceCategory.BUDGET,
        severity=ComplianceSeverity.BLOCKER,
        status=ComplianceStatus.PASS,
        description="Total budget within typology maximum",
        actual_value=f"EUR {proposal.total_budget:,.0f}",
        expected_value=f"<= EUR {rules.max_funding_eur:,}",
    )


# --- BG02: Indirect costs = 25% of direct ---


@RuleRegistry.register(
    rule_id="BG02",
    category=ComplianceCategory.BUDGET,
    severity=ComplianceSeverity.CRITICAL,
    description="Indirect costs must be 25% of direct costs per task",
)
def check_bg02(proposal, draft=None) -> list[ComplianceFinding]:
    findings = []
    for t in proposal.tasks:
        expected_indirect = t.budget.direct_costs * BUDGET_RULES.indirect_costs_pct
        actual_indirect = t.budget.indirect_costs
        # Allow 1 EUR tolerance for rounding
        if abs(actual_indirect - expected_indirect) > 1.0:
            findings.append(
                ComplianceFinding(
                    rule_id="BG02",
                    category=ComplianceCategory.BUDGET,
                    severity=ComplianceSeverity.CRITICAL,
                    status=ComplianceStatus.FAIL,
                    description=f"Task T{t.number}: indirect costs mismatch",
                    actual_value=f"EUR {actual_indirect:,.2f}",
                    expected_value=f"EUR {expected_indirect:,.2f} "
                    f"(25% of {t.budget.direct_costs:,.2f})",
                    field_path=f"tasks[{t.number}].budget.indirect_costs",
                    suggestion="Indirect costs must be exactly 25% of direct costs.",
                )
            )
    return findings or [
        ComplianceFinding(
            rule_id="BG02",
            category=ComplianceCategory.BUDGET,
            severity=ComplianceSeverity.CRITICAL,
            status=ComplianceStatus.PASS,
            description="Indirect costs are 25% of direct costs for all tasks",
        )
    ]


# --- BG03: Task budgets sum ≈ total_budget ---


@RuleRegistry.register(
    rule_id="BG03",
    category=ComplianceCategory.BUDGET,
    severity=ComplianceSeverity.CRITICAL,
    description="Task budgets must sum to approximately total_budget (5% tolerance)",
)
def check_bg03(proposal, draft=None) -> ComplianceFinding:
    if not proposal.tasks or proposal.total_budget == 0:
        return ComplianceFinding(
            rule_id="BG03",
            category=ComplianceCategory.BUDGET,
            severity=ComplianceSeverity.CRITICAL,
            status=ComplianceStatus.SKIP,
            description="No tasks or zero budget — check skipped",
        )
    task_total = sum(t.budget.total for t in proposal.tasks)
    diff = abs(task_total - proposal.total_budget)
    threshold = proposal.total_budget * 0.05
    if diff > threshold:
        return ComplianceFinding(
            rule_id="BG03",
            category=ComplianceCategory.BUDGET,
            severity=ComplianceSeverity.CRITICAL,
            status=ComplianceStatus.FAIL,
            description="Task budgets do not sum to total budget (>5% diff)",
            actual_value=f"Tasks sum: EUR {task_total:,.0f}, "
            f"Total: EUR {proposal.total_budget:,.0f}",
            expected_value=f"Difference <= EUR {threshold:,.0f}",
            field_path="total_budget / tasks[*].budget",
            suggestion="Reconcile task budgets with total.",
        )
    return ComplianceFinding(
        rule_id="BG03",
        category=ComplianceCategory.BUDGET,
        severity=ComplianceSeverity.CRITICAL,
        status=ComplianceStatus.PASS,
        description="Task budgets sum to total budget (within 5%)",
        actual_value=f"Sum: EUR {task_total:,.0f}, Total: EUR {proposal.total_budget:,.0f}",
    )


# --- BG04: Budget justification per task ---


@RuleRegistry.register(
    rule_id="BG04",
    category=ComplianceCategory.BUDGET,
    severity=ComplianceSeverity.MAJOR,
    description="Tasks with budget > 0 must have cost justification",
)
def check_bg04(proposal, draft=None) -> list[ComplianceFinding]:
    findings = []
    for t in proposal.tasks:
        if t.budget.total > 0 and not t.cost_justification.strip():
            findings.append(
                ComplianceFinding(
                    rule_id="BG04",
                    category=ComplianceCategory.BUDGET,
                    severity=ComplianceSeverity.MAJOR,
                    status=ComplianceStatus.FAIL,
                    description=f"Task T{t.number} has budget but no cost justification",
                    actual_value=f"EUR {t.budget.total:,.0f} with empty justification",
                    field_path=f"tasks[{t.number}].cost_justification",
                    suggestion="Add cost justification for this task.",
                )
            )
    return findings or [
        ComplianceFinding(
            rule_id="BG04",
            category=ComplianceCategory.BUDGET,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.PASS,
            description="All funded tasks have cost justifications",
        )
    ]


# --- BG05: No negative budget line items ---


@RuleRegistry.register(
    rule_id="BG05",
    category=ComplianceCategory.BUDGET,
    severity=ComplianceSeverity.BLOCKER,
    description="No negative budget line items",
)
def check_bg05(proposal, draft=None) -> list[ComplianceFinding]:
    findings = []
    for t in proposal.tasks:
        budget = t.budget
        items = {
            "human_resources": budget.human_resources,
            "missions_travel": budget.missions_travel,
            "equipment": budget.equipment,
            "consumables": budget.consumables,
            "services": budget.services,
            "registrations_publications": budget.registrations_publications,
            "other": budget.other,
        }
        for name, value in items.items():
            if value < 0:
                findings.append(
                    ComplianceFinding(
                        rule_id="BG05",
                        category=ComplianceCategory.BUDGET,
                        severity=ComplianceSeverity.BLOCKER,
                        status=ComplianceStatus.FAIL,
                        description=f"Task T{t.number}: negative {name} = {value}",
                        actual_value=str(value),
                        expected_value=">= 0",
                        field_path=f"tasks[{t.number}].budget.{name}",
                    )
                )
    return findings or [
        ComplianceFinding(
            rule_id="BG05",
            category=ComplianceCategory.BUDGET,
            severity=ComplianceSeverity.BLOCKER,
            status=ComplianceStatus.PASS,
            description="No negative budget line items",
        )
    ]


# --- BG06: Total budget > 0 ---


@RuleRegistry.register(
    rule_id="BG06",
    category=ComplianceCategory.BUDGET,
    severity=ComplianceSeverity.BLOCKER,
    description="Total budget must be greater than zero",
)
def check_bg06(proposal, draft=None) -> ComplianceFinding:
    if proposal.total_budget <= 0:
        return ComplianceFinding(
            rule_id="BG06",
            category=ComplianceCategory.BUDGET,
            severity=ComplianceSeverity.BLOCKER,
            status=ComplianceStatus.FAIL,
            description="Total budget must be greater than zero",
            actual_value=f"EUR {proposal.total_budget:,.0f}",
            field_path="total_budget",
        )
    return ComplianceFinding(
        rule_id="BG06",
        category=ComplianceCategory.BUDGET,
        severity=ComplianceSeverity.BLOCKER,
        status=ComplianceStatus.PASS,
        description="Total budget is positive",
        actual_value=f"EUR {proposal.total_budget:,.0f}",
    )


# --- BG07-BG10: Heuristic checks ---


@RuleRegistry.register(
    rule_id="BG07",
    category=ComplianceCategory.BUDGET,
    severity=ComplianceSeverity.MAJOR,
    description="Subcontracting should not dominate the budget",
)
def check_bg07(proposal, draft=None) -> ComplianceFinding:
    if not proposal.tasks or proposal.total_budget == 0:
        return ComplianceFinding(
            rule_id="BG07",
            category=ComplianceCategory.BUDGET,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.SKIP,
            description="No budget data",
        )
    services_total = sum(t.budget.services for t in proposal.tasks)
    ratio = services_total / proposal.total_budget if proposal.total_budget else 0
    if ratio > 0.50:
        return ComplianceFinding(
            rule_id="BG07",
            category=ComplianceCategory.BUDGET,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.FAIL,
            description=f"Services/subcontracting is {ratio:.0%} of total budget",
            actual_value=f"{ratio:.0%}",
            expected_value="<= 50%",
            suggestion="Review services budget — may flag excessive outsourcing.",
        )
    return ComplianceFinding(
        rule_id="BG07",
        category=ComplianceCategory.BUDGET,
        severity=ComplianceSeverity.MAJOR,
        status=ComplianceStatus.PASS,
        description="Services budget is reasonable",
        actual_value=f"{ratio:.0%}",
    )


@RuleRegistry.register(
    rule_id="BG08",
    category=ComplianceCategory.BUDGET,
    severity=ComplianceSeverity.MINOR,
    description="Human resources should be the largest budget component",
    auto_checkable=True,
)
def check_bg08(proposal, draft=None) -> ComplianceFinding:
    if not proposal.tasks:
        return ComplianceFinding(
            rule_id="BG08",
            category=ComplianceCategory.BUDGET,
            severity=ComplianceSeverity.MINOR,
            status=ComplianceStatus.SKIP,
            description="No tasks",
        )
    hr_total = sum(t.budget.human_resources for t in proposal.tasks)
    direct_total = sum(t.budget.direct_costs for t in proposal.tasks)
    if direct_total > 0 and hr_total / direct_total < 0.30:
        return ComplianceFinding(
            rule_id="BG08",
            category=ComplianceCategory.BUDGET,
            severity=ComplianceSeverity.MINOR,
            status=ComplianceStatus.WARN,
            description="Human resources < 30% of direct costs — unusual",
            actual_value=f"{hr_total / direct_total:.0%}",
            notes="Low HR allocation may raise reviewer questions.",
        )
    return ComplianceFinding(
        rule_id="BG08",
        category=ComplianceCategory.BUDGET,
        severity=ComplianceSeverity.MINOR,
        status=ComplianceStatus.PASS,
        description="Human resources allocation looks adequate",
    )


@RuleRegistry.register(
    rule_id="BG09",
    category=ComplianceCategory.BUDGET,
    severity=ComplianceSeverity.MINOR,
    description="Equipment budget should be justified",
    auto_checkable=True,
)
def check_bg09(proposal, draft=None) -> ComplianceFinding:
    if not proposal.tasks:
        return ComplianceFinding(
            rule_id="BG09",
            category=ComplianceCategory.BUDGET,
            severity=ComplianceSeverity.MINOR,
            status=ComplianceStatus.SKIP,
            description="No tasks",
        )
    equip_total = sum(t.budget.equipment for t in proposal.tasks)
    if proposal.total_budget > 0 and equip_total / proposal.total_budget > 0.40:
        return ComplianceFinding(
            rule_id="BG09",
            category=ComplianceCategory.BUDGET,
            severity=ComplianceSeverity.MINOR,
            status=ComplianceStatus.WARN,
            description=f"Equipment is {equip_total / proposal.total_budget:.0%} "
            "of total — may need strong justification",
            notes="High equipment share may raise questions in review.",
        )
    return ComplianceFinding(
        rule_id="BG09",
        category=ComplianceCategory.BUDGET,
        severity=ComplianceSeverity.MINOR,
        status=ComplianceStatus.PASS,
        description="Equipment budget proportion is reasonable",
    )


@RuleRegistry.register(
    rule_id="BG10",
    category=ComplianceCategory.BUDGET,
    severity=ComplianceSeverity.MINOR,
    description="Travel budget should be proportionate",
    auto_checkable=True,
)
def check_bg10(proposal, draft=None) -> ComplianceFinding:
    if not proposal.tasks:
        return ComplianceFinding(
            rule_id="BG10",
            category=ComplianceCategory.BUDGET,
            severity=ComplianceSeverity.MINOR,
            status=ComplianceStatus.SKIP,
            description="No tasks",
        )
    travel_total = sum(t.budget.missions_travel for t in proposal.tasks)
    if proposal.total_budget > 0 and travel_total / proposal.total_budget > 0.30:
        return ComplianceFinding(
            rule_id="BG10",
            category=ComplianceCategory.BUDGET,
            severity=ComplianceSeverity.MINOR,
            status=ComplianceStatus.WARN,
            description=f"Travel is {travel_total / proposal.total_budget:.0%} "
            "of total — may need justification",
            notes="High travel share may raise questions.",
        )
    return ComplianceFinding(
        rule_id="BG10",
        category=ComplianceCategory.BUDGET,
        severity=ComplianceSeverity.MINOR,
        status=ComplianceStatus.PASS,
        description="Travel budget proportion is reasonable",
    )
