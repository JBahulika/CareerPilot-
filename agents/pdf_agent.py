"""PDF Generator Agent.

Renders a ``TailoredResume`` into an ATS-friendly PDF: single column, standard
fonts, no tables or images. Uses WeasyPrint (HTML -> PDF).
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from core.config import settings
from core.logging import get_logger
from models.schemas import JobListing, TailoredResume

logger = get_logger(__name__)

_STYLE = """
@page { size: A4; margin: 1.6cm; }
body { font-family: 'Helvetica', 'Arial', sans-serif; font-size: 10.5pt;
       color: #1a1a1a; line-height: 1.4; }
h1 { font-size: 18pt; margin: 0 0 2px 0; }
.contact { font-size: 9.5pt; color: #444; margin-bottom: 10px; }
h2 { font-size: 11.5pt; text-transform: uppercase; letter-spacing: 0.5px;
     border-bottom: 1px solid #999; padding-bottom: 2px; margin: 14px 0 6px 0; }
.item-title { font-weight: bold; }
.item-sub { color: #555; font-size: 9.5pt; }
p { margin: 2px 0; }
ul { margin: 2px 0 6px 0; padding-left: 18px; }
.skills { line-height: 1.6; }
"""


def _esc(text: str) -> str:
    return html.escape(text or "")


def _safe_filename(company: str, role: str) -> str:
    base = f"Resume_{company}_{role}".strip("_")
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", base)
    return re.sub(r"_+", "_", base).strip("_")[:80] or "Resume"


class PDFGeneratorAgent:
    def run(self, resume: TailoredResume, job: JobListing) -> str:
        from weasyprint import HTML

        filename = _safe_filename(job.company, job.title) + ".pdf"
        out_path = Path(settings.generated_resumes_dir) / filename

        HTML(string=self._render_html(resume)).write_pdf(str(out_path))
        logger.info(f"Generated resume PDF: {out_path}")
        return str(out_path)

    def _render_html(self, r: TailoredResume) -> str:
        sections: list[str] = []

        if r.summary:
            sections.append(f"<h2>Summary</h2><p>{_esc(r.summary)}</p>")

        if r.skills:
            sections.append(
                "<h2>Skills</h2>"
                f"<p class='skills'>{_esc(', '.join(r.skills))}</p>"
            )

        if r.experience:
            items = []
            for exp in r.experience:
                sub = " | ".join(x for x in (exp.company, exp.duration) if x)
                items.append(
                    f"<p class='item-title'>{_esc(exp.title)}</p>"
                    f"<p class='item-sub'>{_esc(sub)}</p>"
                    f"<p>{_esc(exp.description)}</p>"
                )
            sections.append("<h2>Experience</h2>" + "".join(items))

        if r.projects:
            items = []
            for proj in r.projects:
                tech = f" ({_esc(', '.join(proj.tech_stack))})" if proj.tech_stack else ""
                items.append(
                    f"<p class='item-title'>{_esc(proj.name)}{tech}</p>"
                    f"<p>{_esc(proj.description)}</p>"
                )
            sections.append("<h2>Projects</h2>" + "".join(items))

        if r.education:
            items = []
            for edu in r.education:
                sub = " | ".join(x for x in (edu.institution, edu.year) if x)
                items.append(
                    f"<p class='item-title'>{_esc(edu.degree)}</p>"
                    f"<p class='item-sub'>{_esc(sub)}</p>"
                )
            sections.append("<h2>Education</h2>" + "".join(items))

        if r.certifications:
            lis = "".join(f"<li>{_esc(c)}</li>" for c in r.certifications)
            sections.append(f"<h2>Certifications</h2><ul>{lis}</ul>")

        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<style>{_STYLE}</style></head><body>"
            f"<h1>{_esc(r.name)}</h1>"
            f"<p class='contact'>{_esc(r.contact)}</p>"
            f"{''.join(sections)}"
            "</body></html>"
        )
