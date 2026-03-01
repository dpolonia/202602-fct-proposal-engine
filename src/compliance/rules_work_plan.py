"""
Work plan compliance rules — WP01-WP14.

Cross-reference checks for tasks, deliverables, milestones, and sections.
"""

from __future__ import annotations

from src.compliance.models import (
    ComplianceCategory,
    ComplianceFinding,
    ComplianceSeverity,
    ComplianceStatus,
)
from src.compliance.registry import RuleRegistry

# --- WP01: At least 1 task defined ---


@RuleRegistry.register(
    rule_id="WP01",
    category=ComplianceCategory.WORK_PLAN,
    severity=ComplianceSeverity.BLOCKER,
    description="At least 1 task must be defined",
)
def check_wp01(proposal, draft=None) -> ComplianceFinding:
    if not proposal.tasks:
        return ComplianceFinding(
            rule_id="WP01",
            category=ComplianceCategory.WORK_PLAN,
            severity=ComplianceSeverity.BLOCKER,
            status=ComplianceStatus.FAIL,
            description="At least 1 task must be defined",
            field_path="tasks",
            suggestion="Add at least one task to the work plan.",
        )
    return ComplianceFinding(
        rule_id="WP01",
        category=ComplianceCategory.WORK_PLAN,
        severity=ComplianceSeverity.BLOCKER,
        status=ComplianceStatus.PASS,
        description="At least 1 task must be defined",
        actual_value=f"{len(proposal.tasks)} tasks",
        field_path="tasks",
    )


# --- WP02: Tasks cover full duration (no month gaps) ---


@RuleRegistry.register(
    rule_id="WP02",
    category=ComplianceCategory.WORK_PLAN,
    severity=ComplianceSeverity.MAJOR,
    description="Tasks should cover the full project duration (no month gaps)",
)
def check_wp02(proposal, draft=None) -> ComplianceFinding:
    if not proposal.tasks:
        return ComplianceFinding(
            rule_id="WP02",
            category=ComplianceCategory.WORK_PLAN,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.SKIP,
            description="No tasks to check",
        )
    covered_months: set[int] = set()
    for t in proposal.tasks:
        end = t.start_month + t.duration_months - 1
        for m in range(t.start_month, end + 1):
            covered_months.add(m)
    all_months = set(range(1, proposal.duration_months + 1))
    gaps = sorted(all_months - covered_months)
    if gaps:
        return ComplianceFinding(
            rule_id="WP02",
            category=ComplianceCategory.WORK_PLAN,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.FAIL,
            description="Tasks should cover the full project duration",
            actual_value=f"Gaps at months: {gaps[:10]}{'...' if len(gaps) > 10 else ''}",
            expected_value=f"All months 1-{proposal.duration_months} covered",
            field_path="tasks",
            suggestion="Add tasks to cover the gap months.",
        )
    return ComplianceFinding(
        rule_id="WP02",
        category=ComplianceCategory.WORK_PLAN,
        severity=ComplianceSeverity.MAJOR,
        status=ComplianceStatus.PASS,
        description="Tasks cover the full project duration",
        field_path="tasks",
    )


# --- WP03: Each task fits within project duration ---


@RuleRegistry.register(
    rule_id="WP03",
    category=ComplianceCategory.WORK_PLAN,
    severity=ComplianceSeverity.CRITICAL,
    description="Each task must end within project duration",
)
def check_wp03(proposal, draft=None) -> list[ComplianceFinding]:
    findings = []
    for t in proposal.tasks:
        end_month = t.start_month + t.duration_months - 1
        if end_month > proposal.duration_months:
            findings.append(
                ComplianceFinding(
                    rule_id="WP03",
                    category=ComplianceCategory.WORK_PLAN,
                    severity=ComplianceSeverity.CRITICAL,
                    status=ComplianceStatus.FAIL,
                    description=f"Task T{t.number} ends at month {end_month}, "
                    f"beyond project duration ({proposal.duration_months})",
                    actual_value=f"end month {end_month}",
                    expected_value=f"<= {proposal.duration_months}",
                    field_path=f"tasks[{t.number}]",
                    suggestion="Shorten task or adjust start month.",
                )
            )
    return findings or [
        ComplianceFinding(
            rule_id="WP03",
            category=ComplianceCategory.WORK_PLAN,
            severity=ComplianceSeverity.CRITICAL,
            status=ComplianceStatus.PASS,
            description="All tasks fit within project duration",
        )
    ]


# --- WP04: Every deliverable references an existing task ---


@RuleRegistry.register(
    rule_id="WP04",
    category=ComplianceCategory.WORK_PLAN,
    severity=ComplianceSeverity.MAJOR,
    description="Every deliverable must reference an existing task",
)
def check_wp04(proposal, draft=None) -> list[ComplianceFinding]:
    task_numbers = {t.number for t in proposal.tasks}
    findings = []
    for d in proposal.deliverables:
        bad_refs = [r for r in d.related_tasks if r not in task_numbers]
        if bad_refs:
            findings.append(
                ComplianceFinding(
                    rule_id="WP04",
                    category=ComplianceCategory.WORK_PLAN,
                    severity=ComplianceSeverity.MAJOR,
                    status=ComplianceStatus.FAIL,
                    description=f"Deliverable {d.code} references non-existent task(s): {bad_refs}",
                    field_path=f"deliverables[{d.code}].related_tasks",
                    suggestion="Fix task references.",
                )
            )
    return findings or [
        ComplianceFinding(
            rule_id="WP04",
            category=ComplianceCategory.WORK_PLAN,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.PASS,
            description="All deliverables reference existing tasks",
        )
    ]


# --- WP05: Every milestone references an existing task ---


@RuleRegistry.register(
    rule_id="WP05",
    category=ComplianceCategory.WORK_PLAN,
    severity=ComplianceSeverity.MAJOR,
    description="Every milestone must reference an existing task",
)
def check_wp05(proposal, draft=None) -> list[ComplianceFinding]:
    task_numbers = {t.number for t in proposal.tasks}
    findings = []
    for m in proposal.milestones:
        bad_refs = [r for r in m.related_tasks if r not in task_numbers]
        if bad_refs:
            findings.append(
                ComplianceFinding(
                    rule_id="WP05",
                    category=ComplianceCategory.WORK_PLAN,
                    severity=ComplianceSeverity.MAJOR,
                    status=ComplianceStatus.FAIL,
                    description=f"Milestone {m.code} references non-existent task(s): {bad_refs}",
                    field_path=f"milestones[{m.code}].related_tasks",
                    suggestion="Fix task references.",
                )
            )
    return findings or [
        ComplianceFinding(
            rule_id="WP05",
            category=ComplianceCategory.WORK_PLAN,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.PASS,
            description="All milestones reference existing tasks",
        )
    ]


# --- WP06: Deliverable due_month within duration ---


@RuleRegistry.register(
    rule_id="WP06",
    category=ComplianceCategory.WORK_PLAN,
    severity=ComplianceSeverity.CRITICAL,
    description="Deliverable due_month must be within project duration",
)
def check_wp06(proposal, draft=None) -> list[ComplianceFinding]:
    findings = []
    for d in proposal.deliverables:
        if d.due_month > proposal.duration_months:
            findings.append(
                ComplianceFinding(
                    rule_id="WP06",
                    category=ComplianceCategory.WORK_PLAN,
                    severity=ComplianceSeverity.CRITICAL,
                    status=ComplianceStatus.FAIL,
                    description=f"Deliverable {d.code} due at month {d.due_month}, "
                    f"beyond duration ({proposal.duration_months})",
                    actual_value=str(d.due_month),
                    expected_value=f"<= {proposal.duration_months}",
                    field_path=f"deliverables[{d.code}].due_month",
                )
            )
    return findings or [
        ComplianceFinding(
            rule_id="WP06",
            category=ComplianceCategory.WORK_PLAN,
            severity=ComplianceSeverity.CRITICAL,
            status=ComplianceStatus.PASS,
            description="All deliverable due dates within project duration",
        )
    ]


# --- WP07: Milestone due_month within duration ---


@RuleRegistry.register(
    rule_id="WP07",
    category=ComplianceCategory.WORK_PLAN,
    severity=ComplianceSeverity.CRITICAL,
    description="Milestone due_month must be within project duration",
)
def check_wp07(proposal, draft=None) -> list[ComplianceFinding]:
    findings = []
    for m in proposal.milestones:
        if m.due_month > proposal.duration_months:
            findings.append(
                ComplianceFinding(
                    rule_id="WP07",
                    category=ComplianceCategory.WORK_PLAN,
                    severity=ComplianceSeverity.CRITICAL,
                    status=ComplianceStatus.FAIL,
                    description=f"Milestone {m.code} due at month {m.due_month}, "
                    f"beyond duration ({proposal.duration_months})",
                    actual_value=str(m.due_month),
                    expected_value=f"<= {proposal.duration_months}",
                    field_path=f"milestones[{m.code}].due_month",
                )
            )
    return findings or [
        ComplianceFinding(
            rule_id="WP07",
            category=ComplianceCategory.WORK_PLAN,
            severity=ComplianceSeverity.CRITICAL,
            status=ComplianceStatus.PASS,
            description="All milestone due dates within project duration",
        )
    ]


# --- WP08: At least 1 deliverable and 1 milestone ---


@RuleRegistry.register(
    rule_id="WP08",
    category=ComplianceCategory.WORK_PLAN,
    severity=ComplianceSeverity.CRITICAL,
    description="At least 1 deliverable and 1 milestone required",
)
def check_wp08(proposal, draft=None) -> ComplianceFinding:
    has_d = len(proposal.deliverables) > 0
    has_m = len(proposal.milestones) > 0
    if not has_d or not has_m:
        missing = []
        if not has_d:
            missing.append("deliverables")
        if not has_m:
            missing.append("milestones")
        return ComplianceFinding(
            rule_id="WP08",
            category=ComplianceCategory.WORK_PLAN,
            severity=ComplianceSeverity.CRITICAL,
            status=ComplianceStatus.FAIL,
            description="At least 1 deliverable and 1 milestone required",
            actual_value=f"Missing: {', '.join(missing)}",
            suggestion=f"Add {' and '.join(missing)}.",
        )
    return ComplianceFinding(
        rule_id="WP08",
        category=ComplianceCategory.WORK_PLAN,
        severity=ComplianceSeverity.CRITICAL,
        status=ComplianceStatus.PASS,
        description="At least 1 deliverable and 1 milestone present",
        actual_value=f"{len(proposal.deliverables)} deliverables, "
        f"{len(proposal.milestones)} milestones",
    )


# --- WP09: Tasks have non-empty descriptions ---


@RuleRegistry.register(
    rule_id="WP09",
    category=ComplianceCategory.WORK_PLAN,
    severity=ComplianceSeverity.MAJOR,
    description="All tasks must have non-empty descriptions",
)
def check_wp09(proposal, draft=None) -> list[ComplianceFinding]:
    findings = []
    for t in proposal.tasks:
        if not t.description.strip():
            findings.append(
                ComplianceFinding(
                    rule_id="WP09",
                    category=ComplianceCategory.WORK_PLAN,
                    severity=ComplianceSeverity.MAJOR,
                    status=ComplianceStatus.FAIL,
                    description=f"Task T{t.number} has empty description",
                    field_path=f"tasks[{t.number}].description",
                    suggestion="Add a description for this task.",
                )
            )
    return findings or [
        ComplianceFinding(
            rule_id="WP09",
            category=ComplianceCategory.WORK_PLAN,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.PASS,
            description="All tasks have non-empty descriptions",
        )
    ]


# --- WP10: Person-months > 0 for each task ---


@RuleRegistry.register(
    rule_id="WP10",
    category=ComplianceCategory.WORK_PLAN,
    severity=ComplianceSeverity.MAJOR,
    description="Each task must have person-months > 0",
)
def check_wp10(proposal, draft=None) -> list[ComplianceFinding]:
    findings = []
    for t in proposal.tasks:
        if t.person_months <= 0:
            findings.append(
                ComplianceFinding(
                    rule_id="WP10",
                    category=ComplianceCategory.WORK_PLAN,
                    severity=ComplianceSeverity.MAJOR,
                    status=ComplianceStatus.FAIL,
                    description=f"Task T{t.number} has {t.person_months} person-months",
                    actual_value=str(t.person_months),
                    expected_value="> 0",
                    field_path=f"tasks[{t.number}].person_months",
                    suggestion="Assign person-months to this task.",
                )
            )
    return findings or [
        ComplianceFinding(
            rule_id="WP10",
            category=ComplianceCategory.WORK_PLAN,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.PASS,
            description="All tasks have person-months > 0",
        )
    ]


# --- WP11: Section text repetition check ---


def _jaccard_sentences(text_a: str, text_b: str) -> float:
    """Compute Jaccard similarity on sentence sets."""
    if not text_a.strip() or not text_b.strip():
        return 0.0
    sents_a = {s.strip().lower() for s in text_a.split(".") if s.strip()}
    sents_b = {s.strip().lower() for s in text_b.split(".") if s.strip()}
    if not sents_a or not sents_b:
        return 0.0
    intersection = sents_a & sents_b
    union = sents_a | sents_b
    return len(intersection) / len(union) if union else 0.0


@RuleRegistry.register(
    rule_id="WP11",
    category=ComplianceCategory.WORK_PLAN,
    severity=ComplianceSeverity.MAJOR,
    description="No excessive text repetition across major proposal sections",
)
def check_wp11(proposal, draft=None) -> list[ComplianceFinding]:
    sections = {
        "abstract_en": proposal.abstract_en,
        "state_of_art_objectives": proposal.state_of_art_objectives,
        "research_plan_methods": proposal.research_plan_methods,
    }
    findings = []
    checked = set()
    for name_a, text_a in sections.items():
        for name_b, text_b in sections.items():
            if name_a >= name_b:
                continue
            pair = (name_a, name_b)
            if pair in checked:
                continue
            checked.add(pair)
            similarity = _jaccard_sentences(text_a, text_b)
            if similarity > 0.40:
                findings.append(
                    ComplianceFinding(
                        rule_id="WP11",
                        category=ComplianceCategory.WORK_PLAN,
                        severity=ComplianceSeverity.MAJOR,
                        status=ComplianceStatus.FAIL,
                        description=f"High text overlap ({similarity:.0%}) between "
                        f"{name_a} and {name_b}",
                        actual_value=f"{similarity:.0%}",
                        expected_value="<= 40%",
                        field_path=f"{name_a} / {name_b}",
                        suggestion="Differentiate the content between these sections.",
                    )
                )
    return findings or [
        ComplianceFinding(
            rule_id="WP11",
            category=ComplianceCategory.WORK_PLAN,
            severity=ComplianceSeverity.MAJOR,
            status=ComplianceStatus.PASS,
            description="No excessive text repetition across sections",
        )
    ]


# --- WP12: Final deliverable near project end ---


@RuleRegistry.register(
    rule_id="WP12",
    category=ComplianceCategory.WORK_PLAN,
    severity=ComplianceSeverity.MINOR,
    description="A deliverable should be due near the project end",
)
def check_wp12(proposal, draft=None) -> ComplianceFinding:
    if not proposal.deliverables:
        return ComplianceFinding(
            rule_id="WP12",
            category=ComplianceCategory.WORK_PLAN,
            severity=ComplianceSeverity.MINOR,
            status=ComplianceStatus.SKIP,
            description="No deliverables",
        )
    max_due = max(d.due_month for d in proposal.deliverables)
    # "Near end" means within last 3 months
    threshold = max(1, proposal.duration_months - 3)
    if max_due < threshold:
        return ComplianceFinding(
            rule_id="WP12",
            category=ComplianceCategory.WORK_PLAN,
            severity=ComplianceSeverity.MINOR,
            status=ComplianceStatus.FAIL,
            description="No deliverable due near project end",
            actual_value=f"Latest deliverable at month {max_due}",
            expected_value=f">= month {threshold}",
            suggestion="Add a final deliverable near project end.",
        )
    return ComplianceFinding(
        rule_id="WP12",
        category=ComplianceCategory.WORK_PLAN,
        severity=ComplianceSeverity.MINOR,
        status=ComplianceStatus.PASS,
        description="Final deliverable near project end",
        actual_value=f"Latest at month {max_due}",
    )


# --- WP13: Abstract EN non-empty ---


@RuleRegistry.register(
    rule_id="WP13",
    category=ComplianceCategory.WORK_PLAN,
    severity=ComplianceSeverity.BLOCKER,
    description="Abstract (EN) must not be empty",
)
def check_wp13(proposal, draft=None) -> ComplianceFinding:
    if not proposal.abstract_en.strip():
        return ComplianceFinding(
            rule_id="WP13",
            category=ComplianceCategory.WORK_PLAN,
            severity=ComplianceSeverity.BLOCKER,
            status=ComplianceStatus.FAIL,
            description="Abstract (EN) must not be empty",
            field_path="abstract_en",
            suggestion="Write the English abstract.",
        )
    return ComplianceFinding(
        rule_id="WP13",
        category=ComplianceCategory.WORK_PLAN,
        severity=ComplianceSeverity.BLOCKER,
        status=ComplianceStatus.PASS,
        description="Abstract (EN) is present",
        actual_value=f"{len(proposal.abstract_en)} chars",
        field_path="abstract_en",
    )


# --- WP14: State of Art non-empty ---


@RuleRegistry.register(
    rule_id="WP14",
    category=ComplianceCategory.WORK_PLAN,
    severity=ComplianceSeverity.BLOCKER,
    description="State of art & objectives must not be empty",
)
def check_wp14(proposal, draft=None) -> ComplianceFinding:
    if not proposal.state_of_art_objectives.strip():
        return ComplianceFinding(
            rule_id="WP14",
            category=ComplianceCategory.WORK_PLAN,
            severity=ComplianceSeverity.BLOCKER,
            status=ComplianceStatus.FAIL,
            description="State of art & objectives must not be empty",
            field_path="state_of_art_objectives",
            suggestion="Write the state of art and objectives section.",
        )
    return ComplianceFinding(
        rule_id="WP14",
        category=ComplianceCategory.WORK_PLAN,
        severity=ComplianceSeverity.BLOCKER,
        status=ComplianceStatus.PASS,
        description="State of art & objectives is present",
        actual_value=f"{len(proposal.state_of_art_objectives)} chars",
        field_path="state_of_art_objectives",
    )
