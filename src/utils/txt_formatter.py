"""
TXT formatters for proposals, reviews, and character reports.
Produces human-readable plain-text representations of pipeline outputs.
"""

from __future__ import annotations

from src.generators.models import ConsensusReport, Proposal


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
