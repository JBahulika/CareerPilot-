# Changelog

All notable changes to CareerPilot are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/).

## Contribution rule

**Every phase PR and every merged upgrade must append an entry here** under the
correct version heading (or `[Unreleased]` until release). Also add a short
bullet in [`docs/UPGRADE_NOTES.md`](docs/UPGRADE_NOTES.md).

Ship each phase on its own branch (`phase-N-…`), merge to `main`, and **keep the
phase branch** on GitHub as a backup. Update `README.md` and `requirements.txt`
every phase (or explicitly note “no dependency changes”).

Do not ship feature work without a changelog line.

## [Unreleased]

### Planned (phased roadmap)

- Phase 4+: WhatsApp/email digests, proxies, optional cookies, dedupe,
  skills-gap / cover-letter — see `docs/UPGRADE_NOTES.md`.

## [0.2.4] — 2026-08-05

### Changed

- **LinkedIn** and **Indeed** are default-on again (best-effort Playwright scrape).
- Safety remains `disabled_captcha`: Phase 2 still aborts on challenge pages
  (`captcha_blocked`) — captchas are never solved.
- Glassdoor stays off by default.

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.2.3] — 2026-08-05

### Added

- Source safety tags: `api` | `scrape_safe` | `scrape_risky` | `disabled_captcha`.
- New safe sources: **The Muse** (API), **We Work Remotely** (RSS), **Working Nomads** (API).
- Profile `enabled_sources` allowlist (empty = safe defaults). Aggregate respects it.
- Setup table shows method, safety, default_on, and health.

### Changed

- Indeed / LinkedIn / Glassdoor tagged `disabled_captcha` and **off by default**.
- Wellfound / Naukri tagged `scrape_risky` and **off by default**.

### Notes

- JobSpy not integrated (would need allowlist + Phase 2 client + captcha abort);
  skipped for this phase.

### Dependencies

- No dependency changes (`requirements.txt` unchanged; RSS via stdlib).

## [0.2.2] — 2026-08-05

### Added

- Shared safe scrape HTTP client (`services/scrape_http.py`): browser-like headers,
  jitter delays, concurrency limit, retries on 429/5xx.
- Captcha/challenge detection aborts the source (`captcha_blocked`) — never solved.
- Source health registry + `GET /jobs/sources/health`; Setup page health table.
- Config: `SCRAPE_MIN_DELAY_MS`, `SCRAPE_MAX_DELAY_MS`, `SCRAPE_MAX_CONCURRENCY`,
  `SCRAPE_MAX_RETRIES`, `SCRAPE_HEALTH_COOLDOWN_SECONDS`.
- Unit tests in `tests/test_scrape_http.py`.

### Changed

- API job sources use the shared client instead of bare `requests`.
- Playwright scrapers use browser UA/headers, jitter, and captcha abort.
- Aggregate skips sources temporarily blocked by captcha/rate-limit cooldown.

### Dependencies

- No dependency changes (`httpx` already required).

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

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

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

- Matching upgrades from `contributor/local-matching-upgrades` are on `main`.
- Phase backups: keep `phase-0-upgrade-notes` / `phase-1-match-threshold` branches.

### Dependencies

- No dependency changes for Phase 0 docs/guardrails (`requirements.txt` unchanged).

## [0.1.0] — prior

### Added

- Initial local-first multi-agent pipeline (parse → scrape → filter → match →
  tailor → PDF) with FastAPI, Streamlit, LangGraph, Ollama, ChromaDB, SQLite.
- Job source registry (Remotive, RemoteOK, Arbeitnow, Jobicy, Himalayas, plus
  scrape adapters).
- Daily morning scan scheduler and local / WhatsApp digest stubs.
