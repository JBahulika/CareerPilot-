"""Application configuration via Pydantic Settings.

All runtime knobs are read from environment variables (or a local ``.env``
file). Keeping them here means every agent, service, and route imports from a
single source of truth.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Ollama (local LLM)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"

    # Embeddings & matching accuracy
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    reranker_model: str = "BAAI/bge-reranker-base"
    reranker_enabled: bool = True
    hybrid_search_enabled: bool = True
    hybrid_vector_weight: float = 0.65
    matcher_recall_top_n: int = 50
    matcher_rerank_top_n: int = 20
    matcher_llm_top_n: int = 8
    score_weight_embed: float = 0.15
    score_weight_skill: float = 0.25
    score_weight_rerank: float = 0.45
    score_weight_llm: float = 0.15

    # Pipeline
    top_n_jobs: int = 10
    tailor_resumes_enabled: bool = False  # resume PDF tailoring paused for now
    min_match_score: int = 60  # 0–100; profile/run can override
    job_source: str = "all"  # "all" | remotive | wellfound | indeed | ...
    display_page_size: int = 10
    max_page_size: int = 15
    recent_jobs_days: int = 3
    experience_flex_years: int = 1
    daily_recent_jobs_days: int = 2
    default_include_remote: bool = True
    # Phase 10a — still-hiring heuristic (date-based; never invent when unknown)
    still_hiring_enabled: bool = True
    still_hiring_days: int = 7  # posted within N days → "likely still hiring"
    still_hiring_prefer: bool = True  # sort/prefer likely over stale/unknown
    # Aggregate splits this across enabled boards (per_source = max(10, limit // n))
    scrape_limit_max: int = 2000

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
    max_digest_jobs: int = 5  # sort by score desc, then truncate
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
