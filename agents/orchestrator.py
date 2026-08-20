"""Pipeline Orchestrator (PRD Section 10).

Wires the agents into a LangGraph state machine:

    scrape -> filter -> match -> [optional tailor+pdf] -> complete

Resume PDF tailoring is controlled by ``TAILOR_RESUMES_ENABLED`` (default off).

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
from services.location import effective_location
from services.threshold import effective_min_match_score

logger = get_logger(__name__)


def _resolve_profile(state: PipelineState) -> UserProfile:
    """Apply run-time location overrides to a copy of the profile."""
    profile = state["profile"]
    if state.get("location"):
        profile = profile.model_copy(update={"preferred_location": state["location"]})
    if state.get("include_remote") is not None:
        profile = profile.model_copy(update={"include_remote": state["include_remote"]})
    return profile


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
    recent_days: Optional[int]
    location: Optional[str]
    include_remote: Optional[bool]
    min_match_score: Optional[int]
    jobs: list[JobListing]
    filtered_jobs: list[JobListing]
    filter_rejected: list  # list[tuple[JobListing, str]]
    matches: list[MatchResult]
    generated_pdfs: list[str]
    errors: list[str]
    current_step: str
    run_summary: dict


_scraper = JobScraperAgent()
_filter = JobFilterAgent()
_matcher = SemanticMatcherAgent()
_tailor = ResumeTailorAgent()
_pdf = PDFGeneratorAgent()


def _scrape_node(state: PipelineState) -> PipelineState:
    update_run(state["run_id"], status=RunStatus.RUNNING.value, current_step="scrape")
    profile = _resolve_profile(state)
    summary = dict(state.get("run_summary") or {})
    try:
        jobs = _scraper.run(
            profile,
            limit=state.get("scrape_limit", 100),
            source_name=state.get("source"),
            allow_stretch=state.get("allow_stretch", False),
            flex_years=state.get("flex_years"),
            recent_days=state.get("recent_days"),
        )
        upsert_jobs(jobs)
        scrape_report = dict(getattr(_scraper, "last_scrape_report", None) or {})
        summary["scrape"] = scrape_report
        update_run(
            state["run_id"],
            jobs_scraped=len(jobs),
            summary_json=summary,
        )
        return {
            "jobs": jobs,
            "current_step": "scrape",
            "run_summary": summary,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Scrape failed: {exc}")
        summary["scrape"] = {
            "mode": state.get("source") or "all",
            "per_source": [],
            "sources_error": ["scrape"],
            "detail": str(exc)[:300],
        }
        update_run(state["run_id"], summary_json=summary)
        return {
            "jobs": [],
            "errors": state.get("errors", []) + [f"scrape: {exc}"],
            "run_summary": summary,
        }


def _filter_node(state: PipelineState) -> PipelineState:
    update_run(state["run_id"], current_step="filter")
    profile = _resolve_profile(state)
    summary = dict(state.get("run_summary") or {})
    try:
        result = _filter.run(
            state.get("jobs", []),
            profile,
            exclude_internships=state.get("exclude_internships", False),
            strict_experience=state.get("strict_experience", True),
            allow_stretch=state.get("allow_stretch", False),
            flex_years=state.get("flex_years"),
            recent_days=state.get("recent_days"),
        )
        summary["filter_exclusions"] = result.exclusions
        summary["jobs_after_filter"] = len(result.jobs)
        summary["jobs_filter_rejected"] = len(result.rejected)
        summary["location"] = effective_location(profile) or ""
        summary["include_remote"] = bool(profile.include_remote)
        update_run(state["run_id"], summary_json=summary)
        return {
            "filtered_jobs": result.jobs,
            "filter_rejected": result.rejected,
            "current_step": "filter",
            "run_summary": summary,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Filter failed: {exc}")
        return {
            "filtered_jobs": state.get("jobs", []),
            "errors": state.get("errors", []) + [f"filter: {exc}"],
        }


def _match_node(state: PipelineState) -> PipelineState:
    update_run(state["run_id"], current_step="match")
    profile = _resolve_profile(state)
    threshold = effective_min_match_score(profile, state.get("min_match_score"))
    summary = dict(state.get("run_summary") or {})
    try:
        from services.browse_matches import merge_browse_matches

        matches = _matcher.run(
            profile,
            state.get("filtered_jobs", []),
            top_n=state.get("top_n", settings.top_n_jobs),
            strict_experience=state.get("strict_experience", True),
            allow_stretch=state.get("allow_stretch", False),
            flex_years=state.get("flex_years"),
            min_match_score=threshold,
        )
        stats = dict(getattr(_matcher, "last_match_stats", None) or {})
        above = int(stats.get("above_threshold", 0))
        # Keep filter-rejected / unscored scrapes visible under low-match toggle
        matches = merge_browse_matches(
            matches,
            state.get("jobs", []) or [],
            state.get("filter_rejected", []) or [],
            profile,
            threshold=threshold,
        )
        above = sum(1 for m in matches if m.match_score >= threshold)
        summary["min_match_score"] = threshold
        summary["jobs_matched"] = above
        summary["jobs_viewable"] = len(matches)
        summary["jobs_low_match"] = max(0, len(matches) - above)
        update_run(
            state["run_id"],
            jobs_matched=above,
            summary_json=summary,
        )
        return {
            "matches": matches,
            "current_step": "match",
            "run_summary": summary,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Match failed: {exc}")
        return {"matches": [], "errors": state.get("errors", []) + [f"match: {exc}"]}


def _tailor_node(state: PipelineState) -> PipelineState:
    """Optional resume PDF tailoring. Disabled by default (``TAILOR_RESUMES_ENABLED``)."""
    matches = state.get("matches", [])
    if not settings.tailor_resumes_enabled:
        logger.info("Resume tailoring skipped (TAILOR_RESUMES_ENABLED=false)")
        update_run(state["run_id"], current_step="tailor", pdfs_generated=0)
        return {"generated_pdfs": [], "matches": matches}

    update_run(state["run_id"], current_step="tailor")
    profile = state["profile"]
    threshold = effective_min_match_score(profile, state.get("min_match_score"))
    pdfs: list[str] = []
    errors = list(state.get("errors", []))
    # Only tailor strong matches (not optional low-match browse rows)
    to_tailor = [m for m in matches if m.match_score >= threshold][
        : state.get("top_n", settings.top_n_jobs)
    ]

    for match in to_tailor:
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

    errors = list(state.get("errors", []))
    summary = dict(state.get("run_summary") or {})
    profile = state.get("profile")
    # Best-effort Drive backup of run summary (does not block completion)
    if profile is not None:
        try:
            from services.google_drive import maybe_backup_run_summary

            maybe_backup_run_summary(profile, state["run_id"], summary)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Drive run backup skipped: {exc}")

    # Manual-run digest (before finish so UI can see digest_sent)
    if summary.get("send_digest") and profile is not None:
        try:
            from database.repositories import get_matches_for_run
            from services.notifier import get_notifier

            threshold = int(summary.get("min_match_score") or 60)
            fetch_limit = max(settings.top_n_jobs, settings.max_digest_jobs * 3, 30)
            match_rows, _ = get_matches_for_run(
                state["run_id"], offset=0, limit=fetch_limit, min_score=threshold
            )
            profile_id = None
            try:
                from database.repositories import get_run

                run_meta = get_run(state["run_id"])
                if run_meta:
                    profile_id = run_meta.get("profile_id")
            except Exception:  # noqa: BLE001
                profile_id = None
            sent = get_notifier(profile=profile).send_job_digest(
                profile,
                match_rows,
                state["run_id"],
                profile_id=profile_id,
            )
            summary["digest_sent"] = bool(sent)
            logger.info(f"Run {state['run_id']} digest notified={sent}")
        except Exception as exc:  # noqa: BLE001
            summary["digest_sent"] = False
            logger.warning(f"Run {state['run_id']} digest failed: {exc}")

    if summary:
        update_run(state["run_id"], summary_json=summary)
    status = RunStatus.COMPLETED.value if matches else RunStatus.FAILED.value
    finish_run(state["run_id"], status=status, errors=errors)
    return {"current_step": "complete", "run_summary": summary}


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
    location: Optional[str] = None,
    include_remote: Optional[bool] = None,
    recent_days: Optional[int] = None,
    min_match_score: Optional[int] = None,
    send_digest: bool = False,
) -> None:
    """Execute the full pipeline. Intended to run as a background task.

    When ``send_digest`` is True, sends a WhatsApp/email/local digest after the
    run (same format as the morning scan). Daily scan usually sets this False
    and notifies itself after fetching matches.
    """
    logger.info(f"Pipeline run {run_id} starting")
    threshold = effective_min_match_score(profile, min_match_score)
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
        "recent_days": recent_days,
        "location": location,
        "include_remote": include_remote,
        "min_match_score": threshold,
        "run_summary": {
            "min_match_score": threshold,
            "location": effective_location(
                profile.model_copy(
                    update={
                        **({"preferred_location": location} if location else {}),
                        **(
                            {"include_remote": include_remote}
                            if include_remote is not None
                            else {}
                        ),
                    }
                )
                if (location or include_remote is not None)
                else profile
            )
            or "",
            "include_remote": (
                include_remote
                if include_remote is not None
                else profile.include_remote
            ),
            "send_digest": bool(send_digest),
        },
        "errors": [],
    }
    try:
        _PIPELINE.invoke(initial)
        logger.info(f"Pipeline run {run_id} finished")
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Pipeline run {run_id} crashed: {exc}")
        finish_run(run_id, status=RunStatus.FAILED.value, errors=[str(exc)])
