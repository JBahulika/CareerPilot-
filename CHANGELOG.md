# Changelog

All notable changes to CareerPilot are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/).

## Contribution rule

**Every phase PR and every merged upgrade must append an entry here** under the
correct version heading (or `[Unreleased]` until release). Also add a short
bullet in [`docs/UPGRADE_NOTES.md`](docs/UPGRADE_NOTES.md).

Do not ship feature work without a changelog line.

## [Unreleased]

### Planned (phased roadmap)

- Phase 2+: safe scrape layer, more API sources, WhatsApp/email digests, proxies,
  optional cookies, dedupe, skills-gap / cover-letter on user select — see
  `docs/UPGRADE_NOTES.md`.

## [0.2.1] — 2026-08-05

### Added

- User-settable `min_match_score` (0–100, default 60) on profile, config
  (`MIN_MATCH_SCORE`), API (`/pipeline/run`), and Streamlit Profile + per-run override.
- Filter exclusion counts (`location_mismatch`, `experience_mismatch`, etc.) stored
  on pipeline runs (`summary_json`) and shown in Results / History.
- Digest/notifier paths drop matches below the effective threshold.
- `services/threshold.py` helpers and unit tests.

### Changed

- `JobFilterAgent.run` returns `FilterResult` (jobs + exclusions) for transparency.
- Matcher applies min score before Top-N truncation.

## [0.2.0] — 2026-08-05

### Added

- Project version file (`VERSION`) and FastAPI app version `0.2.0`.
- `CHANGELOG.md` and `docs/UPGRADE_NOTES.md` for versioned upgrade history.
- `docs/LEGAL.md` — ToS / scraping stance (prefer APIs, no captcha circumvention,
  no auto-apply; not legal advice).
- `.gitignore` entries for cookies, proxy secret lists, and related local secrets.

### Matching upgrades (present in this workspace)

These matching-accuracy upgrades exist in the current tree (also tracked on
branch `contributor/local-matching-upgrades` for GitHub sync):

- Hybrid BM25 + vector shortlisting (`services/hybrid_search.py`).
- BGE cross-encoder reranker (`BAAI/bge-reranker-base`) with configurable weights.
- Default embedding model `BAAI/bge-base-en-v1.5` (stronger than small).
- Default local LLM `qwen2.5:7b` via Ollama.
- Richer resume schema / parser support and related matcher scoring knobs.

### Notes

- Upstream GitHub `main` may lag this workspace until the contributor branch
  (or equivalent) is merged. Prefer this changelog + `VERSION` as the source of
  truth for what the tree claims to be.

## [0.1.0] — prior

### Added

- Initial local-first multi-agent pipeline (parse → scrape → filter → match →
  tailor → PDF) with FastAPI, Streamlit, LangGraph, Ollama, ChromaDB, SQLite.
- Job source registry (Remotive, RemoteOK, Arbeitnow, Jobicy, Himalayas, plus
  scrape adapters).
- Daily morning scan scheduler and local / WhatsApp digest stubs.
