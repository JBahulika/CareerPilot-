"""Application configuration via Pydantic Settings.

All runtime knobs are read from environment variables (or a local ``.env``
file). Keeping them here means every agent, service, and route imports from a
single source of truth.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from core.model_pins import (
    EMBEDDING_MODEL,
    HYBRID_SEARCH_ENABLED,
    HYBRID_VECTOR_WEIGHT,
    MATCHER_LLM_TOP_N,
    MATCHER_RECALL_TOP_N,
    MATCHER_RERANK_TOP_N,
    MAX_DIGEST_JOBS,
    MIN_MATCH_SCORE,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    RECENT_JOBS_DAYS,
    RERANKER_ENABLED,
    RERANKER_MODEL,
    SCORE_WEIGHT_EMBED,
    SCORE_WEIGHT_LLM,
    SCORE_WEIGHT_RERANK,
    SCORE_WEIGHT_SKILL,
    SCRAPE_LIMIT_MAX,
    STILL_HIRING_DAYS,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Ollama (local LLM) — defaults from core.model_pins (Phase 7)
    ollama_base_url: str = OLLAMA_BASE_URL
    ollama_model: str = OLLAMA_MODEL

    # Embeddings & matching accuracy
    embedding_model: str = EMBEDDING_MODEL
    reranker_model: str = RERANKER_MODEL
    reranker_enabled: bool = RERANKER_ENABLED
    hybrid_search_enabled: bool = HYBRID_SEARCH_ENABLED
    hybrid_vector_weight: float = HYBRID_VECTOR_WEIGHT
    matcher_recall_top_n: int = MATCHER_RECALL_TOP_N
    matcher_rerank_top_n: int = MATCHER_RERANK_TOP_N
    matcher_llm_top_n: int = MATCHER_LLM_TOP_N
    score_weight_embed: float = SCORE_WEIGHT_EMBED
    score_weight_skill: float = SCORE_WEIGHT_SKILL
    score_weight_rerank: float = SCORE_WEIGHT_RERANK
    score_weight_llm: float = SCORE_WEIGHT_LLM

    # Pipeline
    top_n_jobs: int = 10
    tailor_resumes_enabled: bool = False  # resume PDF tailoring paused for now
    min_match_score: int = MIN_MATCH_SCORE  # 0–100; profile/run can override
    job_source: str = "all"  # "all" | remotive | wellfound | indeed | ...
    display_page_size: int = 10
    max_page_size: int = 15
    recent_jobs_days: int = RECENT_JOBS_DAYS
    experience_flex_years: int = 1
    daily_recent_jobs_days: int = 2
    default_include_remote: bool = True
    # Phase 10a — still-hiring heuristic (date-based; never invent when unknown)
    still_hiring_enabled: bool = True
    still_hiring_days: int = STILL_HIRING_DAYS  # posted within N days → "likely still hiring"
    still_hiring_prefer: bool = True  # sort/prefer likely over stale/unknown
    # Aggregate splits this across enabled boards (per_source = max(10, limit // n))
    scrape_limit_max: int = SCRAPE_LIMIT_MAX

    # Safe scrape HTTP (Phase 2) — polite delays; never solve captchas
    scrape_min_delay_ms: int = 400
    scrape_max_delay_ms: int = 1200
    scrape_max_concurrency: int = 2
    scrape_max_retries: int = 2
    scrape_health_cooldown_seconds: int = 1800
    # Phase 5 — proxies + stronger 429 backoff
    scrape_proxy_enabled: bool = False
    scrape_proxy_url: str = ""  # e.g. http://user:pass@host:8080
    scrape_proxy_file: str = ""  # default: data/proxies/list.txt
    scrape_proxy_rotate: bool = True
    scrape_429_base_delay_ms: int = 2000
    scrape_429_max_delay_ms: int = 60000
    scrape_429_max_retries: int = 5
    # Phase 6 — optional board cookies (advanced; stricter limits when used)
    scrape_cookies_enabled: bool = False
    scrape_cookies_dir: str = ""  # default: data/cookies/
    scrape_cookies_strict: bool = True  # slower + concurrency 1 when cookies used
    scrape_cookie_min_delay_ms: int = 1500
    scrape_cookie_max_delay_ms: int = 4000
    scrape_cookie_max_concurrency: int = 1

    # Daily scan (9 AM — fresh jobs + digest; resume PDFs optional)
    daily_scan_enabled: bool = True
    daily_scan_hour: int = 9
    daily_scan_minute: int = 0
    # Phase 5 — random scan window (overrides fixed hour/minute when enabled)
    daily_scan_window_enabled: bool = False
    daily_scan_window_start_hour: int = 8
    daily_scan_window_start_minute: int = 0
    daily_scan_window_end_hour: int = 11
    daily_scan_window_end_minute: int = 0
    # Phase 5 — quiet hours (skip daily scan if triggered during this local window)
    quiet_hours_enabled: bool = False
    quiet_hours_start_hour: int = 22
    quiet_hours_start_minute: int = 0
    quiet_hours_end_hour: int = 7
    quiet_hours_end_minute: int = 0

    # Notifications (Phase 4) — human-in-the-loop digests; no auto-apply
    notifier_backend: str = "local"  # local | whatsapp | email | both
    max_digest_jobs: int = MAX_DIGEST_JOBS  # sort by score desc, then truncate
    # Phase 8 — skip jobs already sent in digests unless refresh / score jump
    notify_dedupe_enabled: bool = True
    notify_resend_score_delta: int = 10  # re-notify if score rises by this many points
    whatsapp_enabled: bool = False
    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""
    whatsapp_recipient: str = ""
    # SMTP email (stdlib smtplib)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    email_to: str = ""
    # Google Drive backup (optional)
    google_drive_folder_id: str = ""
    google_drive_credentials_path: str = ""  # default: data/secrets/gdrive_service_account.json

    # Storage
    database_url: str = "sqlite:///data/careerpilot.db"
    chroma_path: str = "data/chroma"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_base_url: str = "http://localhost:8000"
    # Phase 11 — phone remote (empty = remote API disabled)
    remote_api_token: str = ""
    remote_ui_enabled: bool = True

    # Optional Adzuna Jobs API (https://developer.adzuna.com — free app id/key)
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    adzuna_country: str = ""  # blank = infer from profile (in/us/gb/…)

    # Local directories (privacy: resumes never leave the machine)
    resumes_dir: Path = PROJECT_ROOT / "resumes"
    jobs_dir: Path = PROJECT_ROOT / "jobs"
    generated_resumes_dir: Path = PROJECT_ROOT / "generated_resumes"
    logs_dir: Path = PROJECT_ROOT / "logs"

    def ensure_directories(self) -> None:
        """Create the local working directories if they do not exist."""
        for directory in (
            self.resumes_dir,
            self.jobs_dir,
            self.generated_resumes_dir,
            self.logs_dir,
            self.logs_dir / "notifications",
            PROJECT_ROOT / "data",
            PROJECT_ROOT / "data" / "secrets",
            PROJECT_ROOT / "data" / "proxies",
            PROJECT_ROOT / "data" / "cookies",
            PROJECT_ROOT / self.chroma_path,
        ):
            Path(directory).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings


settings = get_settings()
