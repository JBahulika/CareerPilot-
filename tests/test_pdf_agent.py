"""Tests for PDF generation."""

from __future__ import annotations

from pathlib import Path

from agents.pdf_agent import PDFGeneratorAgent
from models.schemas import JobListing, TailoredResume


def test_generates_pdf_without_weasyprint(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "agents.pdf_agent.settings.generated_resumes_dir",
        tmp_path,
    )
    resume = TailoredResume(
        name="Jane Doe",
        contact="jane@example.com",
        summary="Software engineer with Python experience.",
        skills=["Python", "FastAPI"],
    )
    job = JobListing(company="Acme", title="Backend Engineer")
    path = PDFGeneratorAgent().run(resume, job)
    assert Path(path).exists()
    assert Path(path).stat().st_size > 0
