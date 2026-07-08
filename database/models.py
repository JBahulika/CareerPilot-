"""SQLModel tables for local persistence (SQLite).

Complex nested structures (parsed profiles, match reasons) are stored as JSON
columns to keep the schema simple for the MVP.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column
from sqlalchemy import JSON as SA_JSON
from sqlmodel import Field, SQLModel


class UserProfileRow(SQLModel, table=True):
    __tablename__ = "user_profiles"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = ""
    role: str = ""
    resume_filename: str = ""
    profile_json: dict = Field(default_factory=dict, sa_column=Column(SA_JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class JobRow(SQLModel, table=True):
    __tablename__ = "jobs"

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = ""
    company: str = ""
    title: str = ""
    description: str = ""
    location: str = ""
    salary: str = ""
    experience: str = ""
    apply_url: str = ""
    skills_json: list = Field(default_factory=list, sa_column=Column(SA_JSON))
    content_hash: str = Field(default="", index=True, unique=True)
    posted_at: Optional[datetime] = Field(default=None, index=True)
    scraped_at: datetime = Field(default_factory=datetime.utcnow)


class MatchRow(SQLModel, table=True):
    __tablename__ = "matches"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: Optional[int] = Field(default=None, index=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    match_score: int = 0
    matched_skills_json: list = Field(default_factory=list, sa_column=Column(SA_JSON))
    missing_skills_json: list = Field(default_factory=list, sa_column=Column(SA_JSON))
    reasons_json: list = Field(default_factory=list, sa_column=Column(SA_JSON))
    recommendation: str = ""
    generated_pdf_path: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PipelineRunRow(SQLModel, table=True):
    __tablename__ = "pipeline_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: Optional[int] = Field(default=None, index=True)
    status: str = "pending"
    current_step: str = ""
    jobs_scraped: int = 0
    jobs_matched: int = 0
    pdfs_generated: int = 0
    errors_json: list = Field(default_factory=list, sa_column=Column(SA_JSON))
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
