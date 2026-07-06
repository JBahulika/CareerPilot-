"""PDF Generator Agent.

Renders a ``TailoredResume`` into an ATS-friendly PDF: single column, standard
fonts, no tables or images. Uses PyMuPDF (no native GTK/Pango deps).
"""

from __future__ import annotations

import re
from pathlib import Path

import fitz  # PyMuPDF

from core.config import settings
from core.logging import get_logger
from models.schemas import JobListing, TailoredResume

logger = get_logger(__name__)

_PAGE_WIDTH = 595  # A4 width in points
_PAGE_HEIGHT = 842
_MARGIN = 45
_CONTENT_WIDTH = _PAGE_WIDTH - 2 * _MARGIN


def _safe_filename(company: str, role: str) -> str:
    base = f"Resume_{company}_{role}".strip("_")
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", base)
    return re.sub(r"_+", "_", base).strip("_")[:80] or "Resume"


class PDFGeneratorAgent:
    def run(self, resume: TailoredResume, job: JobListing) -> str:
        filename = _safe_filename(job.company, job.title) + ".pdf"
        out_path = Path(settings.generated_resumes_dir) / filename

        doc = fitz.open()
        page = doc.new_page(width=_PAGE_WIDTH, height=_PAGE_HEIGHT)
        writer = _PageWriter(page)

        writer.heading(resume.name, size=18)
        if resume.contact:
            writer.paragraph(resume.contact, size=9.5, color=(0.27, 0.27, 0.27))
            writer.gap(6)

        if resume.summary:
            writer.section("Summary")
            writer.paragraph(resume.summary)

        if resume.skills:
            writer.section("Skills")
            writer.paragraph(", ".join(resume.skills))

        if resume.experience:
            writer.section("Experience")
            for exp in resume.experience:
                writer.item_title(exp.title)
                sub = " | ".join(x for x in (exp.company, exp.duration) if x)
                if sub:
                    writer.item_sub(sub)
                if exp.description:
                    writer.paragraph(exp.description)

        if resume.projects:
            writer.section("Projects")
            for proj in resume.projects:
                title = proj.name
                if proj.tech_stack:
                    title = f"{title} ({', '.join(proj.tech_stack)})"
                writer.item_title(title)
                if proj.description:
                    writer.paragraph(proj.description)

        if resume.education:
            writer.section("Education")
            for edu in resume.education:
                writer.item_title(edu.degree)
                sub = " | ".join(x for x in (edu.institution, edu.year) if x)
                if sub:
                    writer.item_sub(sub)

        if resume.certifications:
            writer.section("Certifications")
            for cert in resume.certifications:
                writer.bullet(cert)

        doc.save(str(out_path))
        doc.close()
        logger.info(f"Generated resume PDF: {out_path}")
        return str(out_path)


class _PageWriter:
    def __init__(self, page: fitz.Page) -> None:
        self._page = page
        self._y = _MARGIN

    def _ensure_space(self, height: float) -> None:
        if self._y + height <= _PAGE_HEIGHT - _MARGIN:
            return
        self._page = self._page.parent.new_page(width=_PAGE_WIDTH, height=_PAGE_HEIGHT)
        self._y = _MARGIN

    def gap(self, points: float) -> None:
        self._y += points

    def heading(self, text: str, *, size: float = 11.5) -> None:
        self._ensure_space(size + 4)
        self._page.insert_text(
            (_MARGIN, self._y + size),
            text,
            fontsize=size,
            fontname="helv",
            color=(0.1, 0.1, 0.1),
        )
        self._y += size + 4

    def section(self, title: str) -> None:
        self.gap(10)
        self._ensure_space(20)
        self._page.insert_text(
            (_MARGIN, self._y + 11.5),
            title.upper(),
            fontsize=11.5,
            fontname="hebo",
            color=(0.1, 0.1, 0.1),
        )
        line_y = self._y + 14
        self._page.draw_line(
            fitz.Point(_MARGIN, line_y),
            fitz.Point(_PAGE_WIDTH - _MARGIN, line_y),
            color=(0.6, 0.6, 0.6),
            width=0.5,
        )
        self._y = line_y + 8

    def paragraph(self, text: str, *, size: float = 10.5, color=(0.1, 0.1, 0.1)) -> None:
        if not text:
            return
        rect = fitz.Rect(_MARGIN, self._y, _MARGIN + _CONTENT_WIDTH, _PAGE_HEIGHT - _MARGIN)
        used = self._page.insert_textbox(
            rect,
            text,
            fontsize=size,
            fontname="helv",
            color=color,
            align=fitz.TEXT_ALIGN_LEFT,
        )
        if used < 0:
            self._ensure_space(14)
            rect = fitz.Rect(_MARGIN, self._y, _MARGIN + _CONTENT_WIDTH, _PAGE_HEIGHT - _MARGIN)
            used = self._page.insert_textbox(
                rect,
                text,
                fontsize=size,
                fontname="helv",
                color=color,
                align=fitz.TEXT_ALIGN_LEFT,
            )
        self._y += max(used, 14) + 2

    def item_title(self, text: str) -> None:
        self.gap(4)
        self._ensure_space(12)
        self._page.insert_text(
            (_MARGIN, self._y + 10.5),
            text,
            fontsize=10.5,
            fontname="hebo",
            color=(0.1, 0.1, 0.1),
        )
        self._y += 12

    def item_sub(self, text: str) -> None:
        self.paragraph(text, size=9.5, color=(0.33, 0.33, 0.33))

    def bullet(self, text: str) -> None:
        self.paragraph(f"• {text}", size=10.5)
