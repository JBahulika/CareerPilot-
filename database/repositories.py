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
    """Insert jobs, skipping duplicates by content hash. Returns stored IDs."""
    stored_ids: list[int] = []
    with get_session() as session:
        for job in jobs:
            existing = session.exec(
                select(JobRow).where(JobRow.content_hash == job.content_hash)
            ).first()
            if existing is not None:
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
        scraped_at=row.scraped_at,
    )


# --- Matches ------------------------------------------------------------------
def save_matches(run_id: int, matches: list[MatchResult], job_ids: dict[str, int]) -> None:
    """Persist match results. ``job_ids`` maps content_hash -> stored job id."""
    with get_session() as session:
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
                recommendation=match.recommendation.value,
                generated_pdf_path=match.generated_pdf_path or "",
            )
            session.add(row)


def get_matches_for_run(run_id: int) -> list[dict]:
    with get_session() as session:
        rows = session.exec(
            select(MatchRow, JobRow)
            .join(JobRow, MatchRow.job_id == JobRow.id)
            .where(MatchRow.run_id == run_id)
            .order_by(MatchRow.match_score.desc())
        ).all()
        results = []
        for match_row, job_row in rows:
            results.append(
                {
                    "company": job_row.company,
                    "title": job_row.title,
                    "location": job_row.location,
                    "apply_url": job_row.apply_url,
                    "match_score": match_row.match_score,
                    "matched_skills": match_row.matched_skills_json,
                    "missing_skills": match_row.missing_skills_json,
                    "reasons": match_row.reasons_json,
                    "recommendation": match_row.recommendation,
                    "generated_pdf_path": match_row.generated_pdf_path,
                }
            )
        return results


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
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            }
            for row in rows
        ]
