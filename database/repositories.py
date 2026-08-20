"""Data-access helpers for profiles, jobs, matches, and pipeline runs.

Each function opens its own short-lived session so callers (agents, routes,
background tasks) never have to manage transactions directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import select

from database.models import JobRow, MatchRow, PipelineRunRow, UserProfileRow
from database.session import get_session
from models.schemas import JobListing, MatchResult, UserProfile


# --- Profiles -----------------------------------------------------------------
def save_profile(profile: UserProfile, resume_filename: str) -> int:
    with get_session() as session:
        row = UserProfileRow(
            name=profile.name,
            role=profile.role,
            resume_filename=resume_filename,
            profile_json=profile.model_dump(),
        )
        session.add(row)
        session.flush()
        return row.id


def get_profile(profile_id: int) -> Optional[UserProfile]:
    with get_session() as session:
        row = session.get(UserProfileRow, profile_id)
        if row is None:
            return None
        return UserProfile.model_validate(row.profile_json)


def get_latest_profile() -> Optional[tuple[int, UserProfile]]:
    with get_session() as session:
        row = session.exec(
            select(UserProfileRow).order_by(UserProfileRow.id.desc())
        ).first()
        if row is None:
            return None
        return row.id, UserProfile.model_validate(row.profile_json)


# --- Jobs ---------------------------------------------------------------------
def upsert_jobs(jobs: list[JobListing]) -> list[int]:
    """Insert jobs, refreshing metadata on duplicates. Returns stored IDs."""
    stored_ids: list[int] = []
    with get_session() as session:
        for job in jobs:
            existing = session.exec(
                select(JobRow).where(JobRow.content_hash == job.content_hash)
            ).first()
            if existing is not None:
                # Keep the earliest known post date (true listing age for UI/recency).
                incoming = job.posted_at or job.scraped_at
                if incoming is not None:
                    if existing.posted_at is None or incoming < existing.posted_at:
                        existing.posted_at = incoming
                if job.experience:
                    existing.experience = job.experience
                if job.apply_url:
                    existing.apply_url = job.apply_url
                if job.location:
                    existing.location = job.location
                if job.description and len(job.description) > len(existing.description or ""):
                    existing.description = job.description
                if job.skills:
                    existing.skills_json = job.skills
                existing.scraped_at = job.scraped_at or existing.scraped_at
                session.add(existing)
                stored_ids.append(existing.id)
                continue
            row = JobRow(
                source=job.source,
                company=job.company,
                title=job.title,
                description=job.description,
                location=job.location,
                salary=job.salary,
                experience=job.experience,
                apply_url=job.apply_url,
                skills_json=job.skills,
                content_hash=job.content_hash,
                posted_at=job.posted_at or job.scraped_at,
                scraped_at=job.scraped_at,
            )
            session.add(row)
            session.flush()
            stored_ids.append(row.id)
    return stored_ids


def get_job(job_id: int) -> Optional[JobListing]:
    with get_session() as session:
        row = session.get(JobRow, job_id)
        if row is None:
            return None
        return _row_to_job(row)


def _row_to_job(row: JobRow) -> JobListing:
    return JobListing(
        source=row.source,
        company=row.company,
        title=row.title,
        description=row.description,
        skills=row.skills_json or [],
        experience=row.experience,
        location=row.location,
        salary=row.salary,
        apply_url=row.apply_url,
        content_hash=row.content_hash,
        posted_at=row.posted_at or row.scraped_at,
        scraped_at=row.scraped_at,
    )


# --- Matches ------------------------------------------------------------------
def save_matches(run_id: int, matches: list[MatchResult], job_ids: dict[str, int]) -> None:
    """Persist match results. ``job_ids`` maps content_hash -> stored job id."""
    with get_session() as session:
        existing = session.exec(
            select(MatchRow).where(MatchRow.run_id == run_id)
        ).all()
        for row in existing:
            session.delete(row)
        for match in matches:
            job_id = job_ids.get(match.job.content_hash)
            if job_id is None:
                continue
            row = MatchRow(
                run_id=run_id,
                job_id=job_id,
                match_score=match.match_score,
                matched_skills_json=match.matched_skills,
                missing_skills_json=match.missing_skills,
                reasons_json=match.reasons,
                scores_json={
                    "embed_score": match.embed_score,
                    "skill_score": match.skill_score,
                    "rerank_score": match.rerank_score,
                    "llm_score": match.llm_score,
                    "seniority_compatible": match.seniority_compatible,
                },
                recommendation=match.recommendation.value,
                generated_pdf_path=match.generated_pdf_path or "",
            )
            session.add(row)


def get_match_detail(run_id: int, match_id: int) -> Optional[dict]:
    """Return one match + job for a run (Phase 9 assist + Phase 10a still-hiring)."""
    with get_session() as session:
        row = session.exec(
            select(MatchRow, JobRow)
            .join(JobRow, MatchRow.job_id == JobRow.id)
            .where(MatchRow.id == match_id, MatchRow.run_id == run_id)
        ).first()
        if row is None:
            return None
        match_row, job_row = row
        posted = job_row.posted_at
        detail = {
            "match_id": match_row.id,
            "job_id": job_row.id,
            "run_id": run_id,
            "content_hash": job_row.content_hash,
            "company": job_row.company,
            "title": job_row.title,
            "source": job_row.source,
            "location": job_row.location,
            "experience": job_row.experience,
            "description": job_row.description or "",
            "apply_url": job_row.apply_url,
            "posted_at": posted.isoformat() if posted else None,
            "match_score": match_row.match_score,
            "scores": match_row.scores_json or {},
            "matched_skills": match_row.matched_skills_json or [],
            "missing_skills": match_row.missing_skills_json or [],
            "reasons": match_row.reasons_json or [],
            "recommendation": match_row.recommendation,
        }
        from services.still_hiring import annotate_match_still_hiring

        return annotate_match_still_hiring(detail)


def get_matches_for_run(
    run_id: int,
    *,
    offset: int = 0,
    limit: Optional[int] = None,
    min_score: int | None = None,
) -> tuple[list[dict], int]:
    with get_session() as session:
        base_query = (
            select(MatchRow, JobRow)
            .join(JobRow, MatchRow.job_id == JobRow.id)
            .where(MatchRow.run_id == run_id)
            .order_by(MatchRow.match_score.desc())
        )
        rows = session.exec(base_query).all()
        if min_score is not None:
            floor = max(0, int(min_score))
            rows = [r for r in rows if r[0].match_score >= floor]

        results = []
        for match_row, job_row in rows:
            # Phase 10a: expose real posted_at only — never substitute scraped_at
            # (that would invent a "fresh" date for still-hiring).
            posted = job_row.posted_at
            results.append(
                {
                    "match_id": match_row.id,
                    "job_id": job_row.id,
                    "content_hash": job_row.content_hash,
                    "company": job_row.company,
                    "title": job_row.title,
                    "source": job_row.source,
                    "location": job_row.location,
                    "experience": job_row.experience,
                    "description": (job_row.description or "")[:2000],
                    "apply_url": job_row.apply_url,
                    "posted_at": posted.isoformat() if posted else None,
                    "match_score": match_row.match_score,
                    "scores": match_row.scores_json or {},
                    "matched_skills": match_row.matched_skills_json,
                    "missing_skills": match_row.missing_skills_json,
                    "reasons": match_row.reasons_json,
                    "recommendation": match_row.recommendation,
                    "generated_pdf_path": match_row.generated_pdf_path,
                }
            )
        from services.still_hiring import annotate_match_still_hiring, prefer_still_hiring

        results = prefer_still_hiring(
            [annotate_match_still_hiring(r) for r in results]
        )
        total = len(results)
        if offset:
            results = results[offset:]
        if limit is not None:
            results = results[:limit]
        return results, total


# --- Pipeline runs ------------------------------------------------------------
def create_run(profile_id: Optional[int]) -> int:
    with get_session() as session:
        row = PipelineRunRow(profile_id=profile_id, status="pending")
        session.add(row)
        session.flush()
        return row.id


def update_run(run_id: int, **fields) -> None:
    with get_session() as session:
        row = session.get(PipelineRunRow, run_id)
        if row is None:
            return
        for key, value in fields.items():
            setattr(row, key, value)
        session.add(row)


def finish_run(run_id: int, status: str, errors: list[str]) -> None:
    update_run(
        run_id,
        status=status,
        errors_json=errors,
        finished_at=datetime.utcnow(),
    )


def get_run(run_id: int) -> Optional[dict]:
    with get_session() as session:
        row = session.get(PipelineRunRow, run_id)
        if row is None:
            return None
        return {
            "id": row.id,
            "profile_id": row.profile_id,
            "status": row.status,
            "current_step": row.current_step,
            "jobs_scraped": row.jobs_scraped,
            "jobs_matched": row.jobs_matched,
            "pdfs_generated": row.pdfs_generated,
            "errors": row.errors_json or [],
            "summary": row.summary_json or {},
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        }


def list_runs(limit: int = 20) -> list[dict]:
    with get_session() as session:
        rows = session.exec(
            select(PipelineRunRow).order_by(PipelineRunRow.id.desc()).limit(limit)
        ).all()
        return [
            {
                "id": row.id,
                "status": row.status,
                "jobs_scraped": row.jobs_scraped,
                "jobs_matched": row.jobs_matched,
                "pdfs_generated": row.pdfs_generated,
                "summary": row.summary_json or {},
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            }
            for row in rows
        ]
