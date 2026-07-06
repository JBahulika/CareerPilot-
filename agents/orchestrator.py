"""Pipeline Orchestrator (PRD Section 10).

Wires the agents into a LangGraph state machine:

    scrape -> filter -> match -> tailor+pdf -> complete

The graph shares one typed ``PipelineState``. Each node updates the persisted
``pipeline_runs`` row so the API/UI can report live progress. Errors in a node
are recorded and, where safe, the pipeline continues.
"""

from __future__ import annotations

from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

from agents.filter_agent import JobFilterAgent
from agents.matcher_agent import SemanticMatcherAgent
from agents.pdf_agent import PDFGeneratorAgent
from agents.resume_agent import ResumeTailorAgent
from agents.scraper_agent import JobScraperAgent
from core.config import settings
from core.logging import get_logger
from database.repositories import (
    finish_run,
    save_matches,
    update_run,
    upsert_jobs,
)
from models.schemas import JobListing, MatchResult, RunStatus, UserProfile

logger = get_logger(__name__)


class PipelineState(TypedDict, total=False):
    run_id: int
    profile: UserProfile
    top_n: int
    source: Optional[str]
    scrape_limit: int
    exclude_internships: bool
    strict_experience: bool
    allow_stretch: bool
    flex_years: Optional[int]
    jobs: list[JobListing]
    filtered_jobs: list[JobListing]
    matches: list[MatchResult]
    generated_pdfs: list[str]
    errors: list[str]
    current_step: str


_scraper = JobScraperAgent()
_filter = JobFilterAgent()
_matcher = SemanticMatcherAgent()
_tailor = ResumeTailorAgent()
_pdf = PDFGeneratorAgent()


def _scrape_node(state: PipelineState) -> PipelineState:
    update_run(state["run_id"], status=RunStatus.RUNNING.value, current_step="scrape")
    try:
        jobs = _scraper.run(
            state["profile"],
            limit=state.get("scrape_limit", 100),
            source_name=state.get("source"),
            allow_stretch=state.get("allow_stretch", False),
            flex_years=state.get("flex_years"),
        )
        upsert_jobs(jobs)
        update_run(state["run_id"], jobs_scraped=len(jobs))
        return {"jobs": jobs, "current_step": "scrape"}
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Scrape failed: {exc}")
        return {"jobs": [], "errors": state.get("errors", []) + [f"scrape: {exc}"]}


def _filter_node(state: PipelineState) -> PipelineState:
    update_run(state["run_id"], current_step="filter")
    try:
        filtered = _filter.run(
            state.get("jobs", []),
            state["profile"],
            exclude_internships=state.get("exclude_internships", False),
            strict_experience=state.get("strict_experience", True),
            allow_stretch=state.get("allow_stretch", False),
            flex_years=state.get("flex_years"),
        )
        return {"filtered_jobs": filtered, "current_step": "filter"}
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Filter failed: {exc}")
        return {
            "filtered_jobs": state.get("jobs", []),
            "errors": state.get("errors", []) + [f"filter: {exc}"],
        }


def _match_node(state: PipelineState) -> PipelineState:
    update_run(state["run_id"], current_step="match")
    try:
        matches = _matcher.run(
            state["profile"],
            state.get("filtered_jobs", []),
            top_n=state.get("top_n", settings.top_n_jobs),
            strict_experience=state.get("strict_experience", True),
            allow_stretch=state.get("allow_stretch", False),
            flex_years=state.get("flex_years"),
        )
        update_run(state["run_id"], jobs_matched=len(matches))
        return {"matches": matches, "current_step": "match"}
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Match failed: {exc}")
        return {"matches": [], "errors": state.get("errors", []) + [f"match: {exc}"]}


def _tailor_node(state: PipelineState) -> PipelineState:
    update_run(state["run_id"], current_step="tailor")
    profile = state["profile"]
    matches = state.get("matches", [])
    pdfs: list[str] = []
    errors = list(state.get("errors", []))

    for match in matches:
        try:
            tailored = _tailor.run(profile, match.job)
            pdf_path = _pdf.run(tailored, match.job)
            match.generated_pdf_path = pdf_path
            pdfs.append(pdf_path)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Tailoring failed for '{match.job.title}': {exc}")
            errors.append(f"tailor[{match.job.title}]: {exc}")

    update_run(state["run_id"], pdfs_generated=len(pdfs))
    return {"generated_pdfs": pdfs, "matches": matches, "errors": errors}


def _persist_node(state: PipelineState) -> PipelineState:
    matches = state.get("matches", [])
    # Map content hash -> stored job id so matches link correctly.
    stored_ids = upsert_jobs([m.job for m in matches])
    job_ids = {
        m.job.content_hash: stored_ids[i] for i, m in enumerate(matches)
    }
    save_matches(state["run_id"], matches, job_ids)

    errors = state.get("errors", [])
    status = RunStatus.COMPLETED.value if matches else RunStatus.FAILED.value
    finish_run(state["run_id"], status=status, errors=errors)
    return {"current_step": "complete"}


def _build_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("scrape", _scrape_node)
    graph.add_node("filter", _filter_node)
    graph.add_node("match", _match_node)
    graph.add_node("tailor", _tailor_node)
    graph.add_node("persist", _persist_node)

    graph.set_entry_point("scrape")
    graph.add_edge("scrape", "filter")
    graph.add_edge("filter", "match")
    graph.add_edge("match", "tailor")
    graph.add_edge("tailor", "persist")
    graph.add_edge("persist", END)
    return graph.compile()


_PIPELINE = _build_graph()


def run_pipeline(
    run_id: int,
    profile: UserProfile,
    top_n: int | None = None,
    source: Optional[str] = None,
    scrape_limit: int = 100,
    exclude_internships: bool = False,
    strict_experience: bool = True,
    allow_stretch: bool = False,
    flex_years: Optional[int] = None,
) -> None:
    """Execute the full pipeline. Intended to run as a background task."""
    logger.info(f"Pipeline run {run_id} starting")
    initial: PipelineState = {
        "run_id": run_id,
        "profile": profile,
        "top_n": top_n or settings.top_n_jobs,
        "source": source,
        "scrape_limit": scrape_limit,
        "exclude_internships": exclude_internships,
        "strict_experience": strict_experience,
        "allow_stretch": allow_stretch,
        "flex_years": flex_years,
        "errors": [],
    }
    try:
        _PIPELINE.invoke(initial)
        logger.info(f"Pipeline run {run_id} finished")
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Pipeline run {run_id} crashed: {exc}")
        finish_run(run_id, status=RunStatus.FAILED.value, errors=[str(exc)])
