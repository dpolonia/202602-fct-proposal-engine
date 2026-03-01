"""
DOCX exporter for compliance reports.

Produces a color-coded Compliance Fulfilment Annex document.
"""

from __future__ import annotations

import logging
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from src.compliance.models import (
    ComplianceReport,
    ComplianceSeverity,
    ComplianceStatus,
)

logger = logging.getLogger(__name__)

# Color mapping for cell shading
_STATUS_COLORS = {
    # PASS → light green
    (ComplianceStatus.PASS, None): "C6EFCE",
    # FAIL + BLOCKER → red
    (ComplianceStatus.FAIL, ComplianceSeverity.BLOCKER): "FF6B6B",
    # FAIL + CRITICAL → orange
    (ComplianceStatus.FAIL, ComplianceSeverity.CRITICAL): "FFB366",
    # FAIL + MAJOR → yellow
    (ComplianceStatus.FAIL, ComplianceSeverity.MAJOR): "FFEB9C",
    # FAIL + MINOR → light grey
    (ComplianceStatus.FAIL, ComplianceSeverity.MINOR): "D9D9D9",
    # WARN → light amber
    (ComplianceStatus.WARN, None): "FFE0B2",
    # N/A → white
    (ComplianceStatus.NA, None): "FFFFFF",
    # SKIP → white
    (ComplianceStatus.SKIP, None): "F5F5F5",
}


def _get_color(status: ComplianceStatus, severity: ComplianceSeverity) -> str:
    """Get hex color for a finding's status/severity combination."""
    if status == ComplianceStatus.FAIL:
        return _STATUS_COLORS.get(
            (status, severity),
            _STATUS_COLORS[(ComplianceStatus.FAIL, ComplianceSeverity.MINOR)],
        )
    return _STATUS_COLORS.get(
        (status, None),
        "FFFFFF",
    )


def _shade_cell(cell, color_hex: str) -> None:
    """Apply background shading to a cell."""
    shading = cell._element.get_or_add_tcPr()
    shading_elem = shading.find(qn("w:shd"))
    if shading_elem is None:
        from docx.oxml import OxmlElement

        shading_elem = OxmlElement("w:shd")
        shading.append(shading_elem)
    shading_elem.set(qn("w:val"), "clear")
    shading_elem.set(qn("w:color"), "auto")
    shading_elem.set(qn("w:fill"), color_hex)


class ComplianceDocxExporter:
    """Exports compliance reports as color-coded DOCX documents."""

    @staticmethod
    def export(report: ComplianceReport, path: Path) -> None:
        """Export a compliance report as a DOCX Compliance Fulfilment Annex."""
        doc = ComplianceDocxExporter._setup_doc()

        # Title
        title_para = doc.add_paragraph()
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = title_para.add_run("Compliance Fulfilment Annex")
        run.bold = True
        run.font.size = Pt(18)
        run.font.color.rgb = RGBColor(0x1A, 0x3C, 0x6E)

        doc.add_paragraph("")

        # Header section
        ComplianceDocxExporter._add_header(doc, report)
        doc.add_paragraph("")

        # Summary stats
        ComplianceDocxExporter._add_summary(doc, report)
        doc.add_paragraph("")

        # Delta table (if v>1)
        if report.delta:
            ComplianceDocxExporter._add_delta(doc, report)
            doc.add_paragraph("")

        # Findings by category
        ComplianceDocxExporter._add_findings(doc, report)

        path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(path))
        logger.info(f"  Saved compliance annex: {path}")

    @staticmethod
    def _setup_doc() -> Document:
        """Create a new Document with A4 landscape for wide tables."""
        doc = Document()
        section = doc.sections[0]
        section.page_width = Cm(29.7)
        section.page_height = Cm(21.0)
        section.orientation = WD_ORIENT.LANDSCAPE
        section.top_margin = Cm(1.5)
        section.bottom_margin = Cm(1.5)
        section.left_margin = Cm(1.5)
        section.right_margin = Cm(1.5)

        style = doc.styles["Normal"]
        font = style.font
        font.name = "Arial"
        font.size = Pt(9)
        font.color.rgb = RGBColor(0x33, 0x33, 0x33)

        for level in range(1, 4):
            hs = doc.styles[f"Heading {level}"]
            hs.font.name = "Arial"
            hs.font.color.rgb = RGBColor(0x1A, 0x3C, 0x6E)

        return doc

    @staticmethod
    def _add_header(doc: Document, report: ComplianceReport) -> None:
        """Add header metadata."""
        doc.add_heading("Report Details", level=2)
        table = doc.add_table(rows=5, cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.LEFT

        rows = [
            ("Version", str(report.version)),
            ("Timestamp", report.timestamp[:19]),
            ("Typology", report.typology),
            ("Total Rules", str(report.total)),
            ("Recommendation", report.recommendation.value),
        ]
        for i, (label, value) in enumerate(rows):
            table.rows[i].cells[0].text = label
            table.rows[i].cells[1].text = value
            for cell in table.rows[i].cells:
                for p in cell.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(10)

    @staticmethod
    def _add_summary(doc: Document, report: ComplianceReport) -> None:
        """Add summary statistics."""
        doc.add_heading("Summary", level=2)
        table = doc.add_table(rows=1, cols=8)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        headers = [
            "Passed",
            "Failed",
            "Warned",
            "N/A",
            "Skipped",
            "Blockers",
            "Critical",
            "Major",
        ]
        values = [
            str(report.passed),
            str(report.failed),
            str(report.warned),
            str(report.na),
            str(report.skipped),
            str(report.blocker_count),
            str(report.critical_count),
            str(report.major_count),
        ]

        for i, h in enumerate(headers):
            cell = table.rows[0].cells[i]
            cell.text = h
            for p in cell.paragraphs:
                for r in p.runs:
                    r.bold = True
                    r.font.size = Pt(9)

        row = table.add_row()
        for i, v in enumerate(values):
            row.cells[i].text = v
            for p in row.cells[i].paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)

    @staticmethod
    def _add_delta(doc: Document, report: ComplianceReport) -> None:
        """Add delta section showing changes from previous version."""
        delta = report.delta
        doc.add_heading("Changes from Previous Version", level=2)

        items = [
            ("Resolved", delta.resolved),
            ("Persists", delta.persists),
            ("New Failures", delta.new_failures),
            ("Regressions", delta.regressions),
        ]
        for label, rule_ids in items:
            if rule_ids:
                doc.add_paragraph(
                    f"{label}: {', '.join(rule_ids)}",
                    style="List Bullet",
                )

    @staticmethod
    def _add_findings(doc: Document, report: ComplianceReport) -> None:
        """Add color-coded findings table grouped by category."""
        doc.add_heading("Detailed Findings", level=2)

        # Group findings by category
        by_category: dict[str, list] = {}
        for f in report.findings:
            cat = f.category.value
            by_category.setdefault(cat, []).append(f)

        for cat in sorted(by_category.keys()):
            cat_findings = by_category[cat]
            doc.add_heading(f"Category: {cat}", level=3)

            headers = [
                "Rule",
                "Status",
                "Severity",
                "Description",
                "Actual",
                "Expected",
                "Suggestion",
            ]
            table = doc.add_table(rows=1, cols=len(headers))
            table.alignment = WD_TABLE_ALIGNMENT.CENTER

            # Header row
            for i, h in enumerate(headers):
                cell = table.rows[0].cells[i]
                cell.text = h
                for p in cell.paragraphs:
                    for r in p.runs:
                        r.bold = True
                        r.font.size = Pt(8)

            # Data rows
            for finding in cat_findings:
                row = table.add_row()
                values = [
                    finding.rule_id,
                    finding.status.value,
                    finding.severity.name if finding.status == ComplianceStatus.FAIL else "",
                    finding.description[:80],
                    finding.actual_value[:40] if finding.actual_value else "",
                    finding.expected_value[:40] if finding.expected_value else "",
                    finding.suggestion[:60]
                    if finding.suggestion
                    else (finding.notes[:60] if finding.notes else ""),
                ]
                color = _get_color(finding.status, finding.severity)
                for i, v in enumerate(values):
                    cell = row.cells[i]
                    cell.text = str(v)
                    _shade_cell(cell, color)
                    for p in cell.paragraphs:
                        for r in p.runs:
                            r.font.size = Pt(8)

            doc.add_paragraph("")
