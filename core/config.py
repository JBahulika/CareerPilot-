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
    min_match_score: int = 60  # 0–100; profile/run can override
    job_source: str = "all"  # "all" | remotive | wellfound | indeed | ...
    display_page_size: int = 10
    max_page_size: int = 15
    recent_jobs_days: int = 3
    experience_flex_years: int = 1
    daily_recent_jobs_days: int = 2
    default_include_remote: bool = True

    # Daily scan (9 AM — fresh jobs + tailored resumes for WhatsApp digest)
    daily_scan_enabled: bool = True
    daily_scan_hour: int = 9
    daily_scan_minute: int = 0

    # Notifications
    notifier_backend: str = "local"  # "local" | "whatsapp"
    whatsapp_enabled: bool = False
    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""
    whatsapp_recipient: str = ""

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
            PROJECT_ROOT / self.chroma_path,
        ):
            Path(directory).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings


settings = get_settings()
