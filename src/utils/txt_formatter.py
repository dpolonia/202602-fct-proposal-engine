"""
TXT formatters for proposals, reviews, and character reports.
Produces human-readable plain-text representations of pipeline outputs.
"""

from __future__ import annotations

from src.generators.models import ConsensusReport, ImprovementReport, Proposal


def proposal_to_txt(proposal: Proposal) -> str:
    """Format a full proposal as readable plain text with char counts."""
    from src.config.fct_constants import CHAR_LIMITS as CL

    lines: list[str] = []

    def _section(title: str, body: str, limit: int | None = None) -> None:
        if not body:
            return
        lines.append("=" * 72)
        if limit is not None:
            lines.append(f"{title}  [{len(body):,} / {limit:,} chars]")
        else:
            lines.append(title)
        lines.append("=" * 72)
        lines.append(body)
        lines.append("")

    # Header
    lines.append("=" * 72)
    lines.append(f"  {proposal.title_en}")
    lines.append(f"  Acronym: {proposal.acronym}  |  Typology: {proposal.typology.value}")
    lines.append(f"  Duration: {proposal.duration_months} months  |  "
                 f"Budget: EUR {proposal.total_budget:,.0f}")
    lines.append(f"  Keywords: {', '.join(proposal.keywords_en)}")
    lines.append("=" * 72)
    lines.append("")

    _section("ABSTRACT (EN)", proposal.abstract_en, CL.abstract_en)
    _section("ABSTRACT (PT)", proposal.abstract_pt, CL.abstract_pt)
    _section("STATE OF THE ART & OBJECTIVES",
             proposal.state_of_art_objectives, CL.state_of_art_objectives)
    _section("RESEARCH PLAN & METHODS",
             proposal.research_plan_methods, CL.research_plan_methods)
    _section("BIBLIOGRAPHIC REFERENCES",
             proposal.bibliographic_references, CL.bibliographic_references)

    # Tasks
    if proposal.tasks:
        lines.append("=" * 72)
        lines.append("TASKS")
        lines.append("=" * 72)
        for t in proposal.tasks:
            lines.append(f"\n  T{t.number}: {t.denomination}")
            lines.append(f"  Months {t.start_month}-"
                         f"{t.start_month + t.duration_months - 1}  |  "
                         f"{t.person_months} PM")
            lines.append(f"  [{len(t.description):,} / {CL.task_description:,} chars]")
            lines.append(f"  {t.description}")
            if t.cost_justification:
                lines.append(f"\n  Cost justification "
                             f"[{len(t.cost_justification):,} / {CL.cost_justification:,} chars]:")
                lines.append(f"  {t.cost_justification}")
        lines.append("")

    # Deliverables
    if proposal.deliverables:
        lines.append("=" * 72)
        lines.append("DELIVERABLES")
        lines.append("=" * 72)
        for d in proposal.deliverables:
            lines.append(f"  {d.code}: {d.title} (month {d.due_month})")
            lines.append(f"    {d.description}")
        lines.append("")

    # Milestones
    if proposal.milestones:
        lines.append("=" * 72)
        lines.append("MILESTONES")
        lines.append("=" * 72)
        for m in proposal.milestones:
            lines.append(f"  {m.code}: {m.denomination} (month {m.due_month})")
            lines.append(f"    {m.description}")
        lines.append("")

    _section("MANAGEMENT STRUCTURE", proposal.management_structure, CL.management_structure)
    _section("INSTITUTION DESCRIPTION", proposal.institution_description, CL.institution_description)
    _section("CAREER PROFILE", proposal.career_profile, CL.career_profile)
    _section("CONTRIBUTIONS - NEW IDEAS", proposal.contributions_new_ideas, CL.contributions_new_ideas)
    _section("CONTRIBUTIONS - TEAMS", proposal.contributions_teams, CL.contributions_teams)
    _section("CONTRIBUTIONS - SOCIETY", proposal.contributions_society, CL.contributions_society)
    _section("FURTHER DETAILS", proposal.further_details, CL.further_details)
    _section("TEAM CV SYNOPSIS", proposal.team_cv_synopsis, CL.team_cv_synopsis)
    _section("ETHICS JUSTIFICATION", proposal.ethics_justification, CL.ethics_justification)

    if proposal.why_timely_pex:
        _section("WHY TIMELY (PEX)", proposal.why_timely_pex, CL.why_timely_pex)

    return "\n".join(lines)


def review_to_txt(consensus: ConsensusReport) -> str:
    """Format a consensus review report as readable plain text."""
    lines: list[str] = []

    # Panel summary
    lines.append("=" * 72)
    lines.append("PANEL REVIEW SUMMARY")
    lines.append("=" * 72)
    lines.append(f"  Consensus Score: {consensus.consensus_score:.1f} / 10")
    lines.append(f"  Panel Decision:  {consensus.panel_decision}")
    lines.append("")

    # Weighted scores
    ws = consensus.weighted_scores
    if ws:
        lines.append("  Weighted Scores:")
        lines.append(f"    A (Scientific Merit & Innovation, 40%): {ws.get('A', 0):.1f}")
        lines.append(f"    B (PI & Team, 30%):                     {ws.get('B', 0):.1f}")
        lines.append(f"    C (Feasibility, 30%):                   {ws.get('C', 0):.1f}")
        lines.append("")

    # Key findings
    if consensus.key_strengths:
        lines.append("  Key Strengths:")
        for s in consensus.key_strengths:
            lines.append(f"    + {s}")
        lines.append("")

    if consensus.key_weaknesses:
        lines.append("  Key Weaknesses:")
        for w in consensus.key_weaknesses:
            lines.append(f"    - {w}")
        lines.append("")

    if consensus.priority_revisions:
        lines.append("  Priority Revisions:")
        for i, r in enumerate(consensus.priority_revisions, 1):
            lines.append(f"    {i}. {r}")
        lines.append("")

    # Panel narrative
    if consensus.panel_narrative:
        lines.append("-" * 72)
        lines.append("PANEL NARRATIVE")
        lines.append("-" * 72)
        lines.append(consensus.panel_narrative)
        lines.append("")

    # Individual reviewer reports
    for review in consensus.individual_reviews:
        lines.append("-" * 72)
        lines.append(f"REVIEWER: {review.reviewer_id} ({review.perspective})")
        lines.append(f"  Model: {review.reviewer_provider}/{review.reviewer_model}")
        lines.append(f"  Score: {review.overall_score:.1f} / 10  |  Decision: {review.decision}")
        lines.append("-" * 72)

        for cs in review.criterion_scores:
            label = cs.sub_criterion or cs.criterion
            lines.append(f"\n  {label}: {cs.score:.1f}/10")
            if cs.justification:
                lines.append(f"    {cs.justification}")
            if cs.strengths:
                for s in cs.strengths:
                    lines.append(f"    + {s}")
            if cs.weaknesses:
                for w in cs.weaknesses:
                    lines.append(f"    - {w}")
            if cs.suggestions:
                for sg in cs.suggestions:
                    lines.append(f"    > {sg}")

        if review.general_comments:
            lines.append(f"\n  General Comments:")
            lines.append(f"  {review.general_comments}")

        if review.major_revisions:
            lines.append(f"\n  Major Revisions:")
            for r in review.major_revisions:
                lines.append(f"    * {r}")

        if review.minor_revisions:
            lines.append(f"\n  Minor Revisions:")
            for r in review.minor_revisions:
                lines.append(f"    * {r}")

        lines.append("")

    return "\n".join(lines)


def char_report_to_txt(report: dict[str, dict[str, int]]) -> str:
    """Format a character count report as a plain-text table."""
    lines: list[str] = []

    # Header
    lines.append("=" * 72)
    lines.append("CHARACTER COUNT REPORT")
    lines.append("=" * 72)
    lines.append("")
    lines.append(f"  {'Section':<30s} {'Used':>7s} {'Limit':>7s} {'Left':>7s}  Status")
    lines.append(f"  {'-' * 30} {'-' * 7} {'-' * 7} {'-' * 7}  {'-' * 8}")

    all_ok = True
    for name, counts in report.items():
        actual = counts["actual"]
        limit = counts["limit"]
        remaining = counts["remaining"]
        status = "OK" if remaining >= 0 else "OVER"
        if remaining < 0:
            all_ok = False
        lines.append(
            f"  {name:<30s} {actual:>7,d} {limit:>7,d} {remaining:>7,d}  {status}"
        )

    lines.append("")
    lines.append(f"  Overall: {'ALL WITHIN LIMITS' if all_ok else 'SOME SECTIONS OVER LIMIT'}")
    lines.append("")

    return "\n".join(lines)


# =============================================================================
# FCT-REVIEW-ITERATE v1 Markdown Formatters
# =============================================================================

def proposal_to_application_md(proposal: Proposal) -> str:
    """Full proposal in markdown format with all sections, task/deliverable/milestone tables."""
    from src.config.fct_constants import CHAR_LIMITS as CL

    lines: list[str] = []

    lines.append(f"# {proposal.title_en}")
    lines.append("")
    lines.append(f"**Acronym:** {proposal.acronym}  ")
    lines.append(f"**Typology:** {proposal.typology.value}  ")
    lines.append(f"**Duration:** {proposal.duration_months} months  ")
    lines.append(f"**Budget:** EUR {proposal.total_budget:,.0f}  ")
    lines.append(f"**Keywords (EN):** {', '.join(proposal.keywords_en)}  ")
    if proposal.keywords_pt:
        lines.append(f"**Keywords (PT):** {', '.join(proposal.keywords_pt)}  ")
    lines.append(f"**Scientific Domain:** {proposal.scientific_domain}  ")
    lines.append(f"**Scientific Area:** {proposal.scientific_area}  ")
    lines.append("")

    def _md_section(title: str, body: str, limit: int | None = None) -> None:
        if not body:
            return
        header = f"## {title}"
        if limit is not None:
            header += f" [{len(body):,}/{limit:,} chars]"
        lines.append(header)
        lines.append("")
        lines.append(body)
        lines.append("")

    _md_section("Abstract (EN)", proposal.abstract_en, CL.abstract_en)
    _md_section("Abstract (PT)", proposal.abstract_pt, CL.abstract_pt)
    _md_section("State of the Art & Objectives",
                proposal.state_of_art_objectives, CL.state_of_art_objectives)
    _md_section("Research Plan & Methods",
                proposal.research_plan_methods, CL.research_plan_methods)
    _md_section("Bibliographic References",
                proposal.bibliographic_references, CL.bibliographic_references)

    # Tasks table
    if proposal.tasks:
        lines.append("## Tasks")
        lines.append("")
        lines.append("| # | Task | Start | Duration | PM | Budget |")
        lines.append("|---|------|-------|----------|----|--------|")
        for t in proposal.tasks:
            end = t.start_month + t.duration_months - 1
            lines.append(
                f"| T{t.number} | {t.denomination} | M{t.start_month} | "
                f"M{t.start_month}-M{end} ({t.duration_months}mo) | "
                f"{t.person_months} | EUR {t.budget.total:,.0f} |"
            )
        lines.append("")

        for t in proposal.tasks:
            lines.append(f"### T{t.number}: {t.denomination}")
            lines.append("")
            lines.append(t.description)
            lines.append("")
            if t.cost_justification:
                lines.append(f"**Cost Justification:** {t.cost_justification}")
                lines.append("")

    # Deliverables table
    if proposal.deliverables:
        lines.append("## Deliverables")
        lines.append("")
        lines.append("| Code | Title | Type | Due | Tasks |")
        lines.append("|------|-------|------|-----|-------|")
        for d in proposal.deliverables:
            tasks_str = ", ".join(f"T{t}" for t in d.related_tasks)
            lines.append(
                f"| {d.code} | {d.title} | {d.type.value} | "
                f"M{d.due_month} | {tasks_str} |"
            )
        lines.append("")

    # Milestones table
    if proposal.milestones:
        lines.append("## Milestones")
        lines.append("")
        lines.append("| Code | Milestone | Due | Tasks |")
        lines.append("|------|-----------|-----|-------|")
        for m in proposal.milestones:
            tasks_str = ", ".join(f"T{t}" for t in m.related_tasks)
            lines.append(
                f"| {m.code} | {m.denomination} | M{m.due_month} | {tasks_str} |"
            )
        lines.append("")

    _md_section("Management Structure",
                proposal.management_structure, CL.management_structure)
    _md_section("Institution Description",
                proposal.institution_description, CL.institution_description)
    _md_section("Career Profile", proposal.career_profile, CL.career_profile)
    _md_section("Contributions - New Ideas",
                proposal.contributions_new_ideas, CL.contributions_new_ideas)
    _md_section("Contributions - Teams",
                proposal.contributions_teams, CL.contributions_teams)
    _md_section("Contributions - Society",
                proposal.contributions_society, CL.contributions_society)
    _md_section("Further Details", proposal.further_details, CL.further_details)
    _md_section("Team CV Synopsis", proposal.team_cv_synopsis, CL.team_cv_synopsis)
    _md_section("Ethics Justification",
                proposal.ethics_justification, CL.ethics_justification)

    if proposal.why_timely_pex:
        _md_section("Why Timely (PEX)", proposal.why_timely_pex, CL.why_timely_pex)

    if proposal.sdg_alignment:
        lines.append("## SDG Alignment")
        lines.append("")
        lines.append(", ".join(f"SDG {s}" for s in proposal.sdg_alignment))
        lines.append("")

    return "\n".join(lines)


def improvement_report_to_md(report: ImprovementReport, version: int) -> str:
    """Render the mandated 12-section improvement report as markdown."""
    lines: list[str] = []

    # 1. Executive Summary
    lines.append(f"# Improvement Report v{version}")
    lines.append("")
    lines.append("## 1. Executive Summary")
    lines.append("")
    lines.append(f"**Readiness Index:** {report.readiness_index:.1f}/100")
    lines.append("")

    if report.stoplight:
        lines.append("**Stoplight:**")
        lines.append("")
        lines.append("| Criterion | Status | S3 (Fatal) | S2 (Major) | Rationale |")
        lines.append("|-----------|--------|------------|------------|-----------|")
        for s in report.stoplight:
            emoji = {"green": "GREEN", "amber": "AMBER", "red": "RED"}.get(s.color, s.color)
            lines.append(
                f"| {s.criterion} | {emoji} | {s.s3_count} | {s.s2_count} | {s.rationale} |"
            )
        lines.append("")

    if report.executive_summary:
        lines.append(report.executive_summary)
        lines.append("")

    # 2. Version Metadata
    lines.append("## 2. Version Metadata")
    lines.append("")
    lines.append(f"- **Version:** {report.version}")
    lines.append(f"- **Timestamp:** {report.timestamp}")
    lines.append(f"- **Total Suggestions:** {len(report.all_suggestions)}")
    lines.append(f"- **Actions Taken:** {len(report.actions)}")
    lines.append(f"- **Top-5 IDs:** {', '.join(report.top5_ids)}")
    lines.append("")

    # 3. Actions Summary
    lines.append("## 3. Actions Summary")
    lines.append("")

    adopted = sum(1 for a in report.actions if a.action == "adopted")
    partial = sum(1 for a in report.actions if a.action == "partially_adopted")
    deferred = sum(1 for a in report.actions if a.action == "deferred")
    rejected = sum(1 for a in report.actions if a.action == "not_adopted")

    severity_counts = {"S3": 0, "S2": 0, "S1": 0, "S0": 0}
    for sug in report.all_suggestions:
        severity_counts[sug.severity.value] = (
            severity_counts.get(sug.severity.value, 0) + 1
        )

    lines.append(f"- **Adopted:** {adopted}")
    lines.append(f"- **Partially adopted:** {partial}")
    lines.append(f"- **Deferred:** {deferred}")
    lines.append(f"- **Not adopted:** {rejected}")
    lines.append(f"- **Severity breakdown:** "
                 f"S3={severity_counts['S3']}, S2={severity_counts['S2']}, "
                 f"S1={severity_counts['S1']}, S0={severity_counts['S0']}")
    lines.append("")

    # 4. Edits Executed
    lines.append("## 4. Edits Executed")
    lines.append("")
    sections_edited = list({
        a.section_modified for a in report.actions
        if a.action in ("adopted", "partially_adopted") and a.section_modified
    })
    lines.append(f"**Sections edited:** {', '.join(sections_edited) or 'none'}")
    lines.append("")

    # 5. Non-adoptions & Deferrals
    lines.append("## 5. Non-adoptions & Deferrals")
    lines.append("")
    non_adopted = [
        a for a in report.actions
        if a.action in ("deferred", "not_adopted")
    ]
    if non_adopted:
        lines.append("| SUG-ID | Action | Reason |")
        lines.append("|--------|--------|--------|")
        for a in non_adopted:
            reason = a.reason_if_not_adopted or a.edit_summary
            lines.append(f"| {a.suggestion_id} | {a.action} | {reason} |")
        lines.append("")
    else:
        lines.append("All suggestions were adopted or partially adopted.")
        lines.append("")

    # 6. High-level Change Log
    lines.append("## 6. Change Log")
    lines.append("")
    active_actions = [
        a for a in report.actions
        if a.action in ("adopted", "partially_adopted")
    ]
    if active_actions:
        lines.append("| SUG-ID | Section | Action | Before (chars) | After (chars) | Test |")
        lines.append("|--------|---------|--------|----------------|---------------|------|")
        for a in active_actions:
            before_len = len(a.before_text_snippet)
            after_len = len(a.after_text_snippet)
            lines.append(
                f"| {a.suggestion_id} | {a.section_modified} | "
                f"{a.action} | {before_len} | {after_len} | "
                f"{a.acceptance_test_result} |"
            )
        lines.append("")
    else:
        lines.append("No edits executed.")
        lines.append("")

    # 7. Traceability Matrix
    lines.append("## 7. Traceability Matrix")
    lines.append("")
    if report.all_suggestions:
        lines.append(
            "| ID | Reviewer | Severity | Criterion | Action | Section | Test Result |"
        )
        lines.append(
            "|----|----------|----------|-----------|--------|---------|-------------|"
        )
        action_map = {a.suggestion_id: a for a in report.actions}
        for sug in report.all_suggestions:
            act = action_map.get(sug.id)
            action_str = act.action if act else "n/a"
            section_str = act.section_modified if act else ""
            test_str = act.acceptance_test_result if act else "n/a"
            criteria = ", ".join(sug.criterion_tags)
            lines.append(
                f"| {sug.id} | {sug.source_reviewer} | {sug.severity.value} | "
                f"{criteria} | {action_str} | {section_str} | {test_str} |"
            )
        lines.append("")
    else:
        lines.append("No suggestions to trace.")
        lines.append("")

    # 8. Science/Method Changes
    lines.append("## 8. Science & Method Changes")
    lines.append("")
    lines.append(report.science_method_changes or "No changes in this category.")
    lines.append("")

    # 9. Feasibility/Budget Changes
    lines.append("## 9. Feasibility & Budget Changes")
    lines.append("")
    lines.append(report.feasibility_budget_changes or "No changes in this category.")
    lines.append("")

    # 10. Ethics/Compliance Changes
    lines.append("## 10. Ethics & Compliance Changes")
    lines.append("")
    lines.append(report.ethics_compliance_changes or "No changes in this category.")
    lines.append("")

    # 11. Consistency Check Results
    lines.append("## 11. Consistency Check Results")
    lines.append("")
    if report.consistency_checks:
        lines.append("| Check | Result | Details |")
        lines.append("|-------|--------|---------|")
        for c in report.consistency_checks:
            result = "PASS" if c.passed else "FAIL"
            auto = " (auto-fixed)" if c.auto_fixed else ""
            lines.append(f"| {c.check_name} | {result}{auto} | {c.details} |")
        lines.append("")
    else:
        lines.append("No consistency checks run.")
        lines.append("")

    # 12. Risk Register
    lines.append("## 12. Post-revision Risk Register")
    lines.append("")
    lines.append(report.risk_register or "No risk register generated.")
    lines.append("")

    return "\n".join(lines)
