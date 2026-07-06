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

    # Embeddings
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    # Pipeline
    top_n_jobs: int = 5
    job_source: str = "remotive"  # "remotive" | "wellfound"

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
