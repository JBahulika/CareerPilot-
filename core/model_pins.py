"""Pinned defaults — Phase 7 single source of truth for models & key knobs.

Change these deliberately in the same PR as:
  - ``docs/MODEL_PINS.md``
  - ``docs/UPGRADE_NOTES.md`` (Models pin table)
  - ``CHANGELOG.md``
  - ``.env.example`` (when env names/defaults change)

Runtime still allows ``.env`` overrides via ``core.config.Settings``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Public GitHub repo — canonical published tree
GITHUB_REPO_URL = "https://github.com/JBahulika/CareerPilot-"
GITHUB_MAIN_URL = f"{GITHUB_REPO_URL}/tree/main"
GITHUB_PHASE7_BRANCH = "phase-7-model-pins-publish"

# --- Model stack (local-first) ------------------------------------------------
OLLAMA_MODEL = "qwen2.5:7b"
OLLAMA_BASE_URL = "http://localhost:11434"
EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
RERANKER_MODEL = "BAAI/bge-reranker-base"
RERANKER_ENABLED = True

# --- Matcher knobs tied to the pin set ----------------------------------------
HYBRID_SEARCH_ENABLED = True
HYBRID_VECTOR_WEIGHT = 0.65
MATCHER_RECALL_TOP_N = 50
MATCHER_RERANK_TOP_N = 20
MATCHER_LLM_TOP_N = 8
SCORE_WEIGHT_EMBED = 0.15
SCORE_WEIGHT_SKILL = 0.25
SCORE_WEIGHT_RERANK = 0.45
SCORE_WEIGHT_LLM = 0.15

# --- Pipeline defaults often cited with the stack -----------------------------
MIN_MATCH_SCORE = 60
SCRAPE_LIMIT_MAX = 2000
MAX_DIGEST_JOBS = 5
RECENT_JOBS_DAYS = 3
STILL_HIRING_DAYS = 7


def read_version() -> str:
    """App version from the ``VERSION`` file (GitHub / releases SoT)."""
    path = PROJECT_ROOT / "VERSION"
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return "0.0.0"


def pins_snapshot() -> dict[str, Any]:
    """JSON-friendly snapshot for ``/meta/pins`` and Setup UI."""
    return {
        "version": read_version(),
        "github": {
            "repo": GITHUB_REPO_URL,
            "main": GITHUB_MAIN_URL,
            "docs": {
                "model_pins": f"{GITHUB_REPO_URL}/blob/main/docs/MODEL_PINS.md",
                "upgrade_notes": f"{GITHUB_REPO_URL}/blob/main/docs/UPGRADE_NOTES.md",
                "changelog": f"{GITHUB_REPO_URL}/blob/main/CHANGELOG.md",
            },
        },
        "models": {
            "ollama_model": OLLAMA_MODEL,
            "ollama_base_url": OLLAMA_BASE_URL,
            "embedding_model": EMBEDDING_MODEL,
            "reranker_model": RERANKER_MODEL,
            "reranker_enabled": RERANKER_ENABLED,
        },
        "matcher": {
            "hybrid_search_enabled": HYBRID_SEARCH_ENABLED,
            "hybrid_vector_weight": HYBRID_VECTOR_WEIGHT,
            "matcher_recall_top_n": MATCHER_RECALL_TOP_N,
            "matcher_rerank_top_n": MATCHER_RERANK_TOP_N,
            "matcher_llm_top_n": MATCHER_LLM_TOP_N,
            "score_weight_embed": SCORE_WEIGHT_EMBED,
            "score_weight_skill": SCORE_WEIGHT_SKILL,
            "score_weight_rerank": SCORE_WEIGHT_RERANK,
            "score_weight_llm": SCORE_WEIGHT_LLM,
        },
        "pipeline": {
            "min_match_score": MIN_MATCH_SCORE,
            "scrape_limit_max": SCRAPE_LIMIT_MAX,
            "max_digest_jobs": MAX_DIGEST_JOBS,
            "recent_jobs_days": RECENT_JOBS_DAYS,
            "still_hiring_days": STILL_HIRING_DAYS,
        },
        "notes": (
            "Pinned values are package defaults. "
            "A local `.env` may override them at runtime — Setup shows both."
        ),
    }
