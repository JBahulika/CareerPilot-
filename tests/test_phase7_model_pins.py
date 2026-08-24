"""Phase 7 — model pins stay aligned with Settings defaults and VERSION."""

from __future__ import annotations

from core import model_pins
from core.config import Settings
from core.model_pins import pins_snapshot, read_version


def test_version_file_readable():
    ver = read_version()
    assert ver
    assert ver[0].isdigit()


def test_settings_defaults_match_pins():
    # Fresh Settings without relying on a polluted process .env for these fields:
    # construct with _env_file=None via model_validate empty + defaults.
    s = Settings(_env_file=None)
    assert s.ollama_model == model_pins.OLLAMA_MODEL
    assert s.embedding_model == model_pins.EMBEDDING_MODEL
    assert s.reranker_model == model_pins.RERANKER_MODEL
    assert s.reranker_enabled == model_pins.RERANKER_ENABLED
    assert s.min_match_score == model_pins.MIN_MATCH_SCORE
    assert s.scrape_limit_max == model_pins.SCRAPE_LIMIT_MAX
    assert s.max_digest_jobs == model_pins.MAX_DIGEST_JOBS
    assert s.recent_jobs_days == model_pins.RECENT_JOBS_DAYS
    assert s.still_hiring_days == model_pins.STILL_HIRING_DAYS
    assert s.score_weight_rerank == model_pins.SCORE_WEIGHT_RERANK


def test_pins_snapshot_shape():
    snap = pins_snapshot()
    assert snap["version"] == read_version()
    assert "qwen" in snap["models"]["ollama_model"]
    assert "bge" in snap["models"]["embedding_model"].lower()
    assert "github.com" in snap["github"]["repo"]
    assert "model_pins" in snap["github"]["docs"]


def test_launcher_default_matches_pin():
    from launcher.hardware import DEFAULT_MODEL

    assert DEFAULT_MODEL == model_pins.OLLAMA_MODEL


def test_env_example_mentions_pins():
    text = (model_pins.PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    assert f"OLLAMA_MODEL={model_pins.OLLAMA_MODEL}" in text
    assert f"EMBEDDING_MODEL={model_pins.EMBEDDING_MODEL}" in text
    assert f"RERANKER_MODEL={model_pins.RERANKER_MODEL}" in text


def test_model_pins_doc_exists():
    path = model_pins.PROJECT_ROOT / "docs" / "MODEL_PINS.md"
    assert path.is_file()
    body = path.read_text(encoding="utf-8")
    assert model_pins.OLLAMA_MODEL in body
    assert "Change checklist" in body
