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

## [0.2.11] — 2026-08-05

### Fixed

- Missing skills no longer list sales/GTM process (solution selling, champion
  building, pre/post-sales activities). Concrete tech like SASE/SSE kept.
- Principal / Lead / Staff / Partner titles hard-capped for entry profiles;
  sales/solutions-engineer roles downranked for AI/ML IC profiles (e.g. SAARC
  Cloudflare-style matches).

### Changed

- Results caption clarifies missing skills = tools/stacks, not soft/sales fluff.

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.2.10] — 2026-08-05

### Added

- Smarter location matching: city aliases (Bangalore↔Bengaluru, Bombay↔Mumbai,
  Delhi↔New Delhi, …), multi-city prefs, and state/country inference so you can
  type a short city name. Scraper queries expand to `City, State, Country`.

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.2.9] — 2026-08-05

### Added

- **Logs** page (renamed from History): per-run breakdown of jobs requested /
  returned / kept per website, plus empty and error boards — for testing why
  Results may show only one source (e.g. weworkremotely).
- Pipeline `summary.scrape` stores Aggregate per-source report.

### Changed

- Removed sidebar caption “Local-first job discovery & resume tailoring.”

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.2.8] — 2026-08-05

### Fixed

- Matcher `missing_skills` no longer lists soft-skill fluff (English
  communication, reliability, self-organization, etc.). Prompt +
  `filter_missing_skills()` keep technical gaps only.
- Entry-level candidates: senior/lead roles hard-capped to ≤20 match score
  and Skip (prevents inflated LLM scores like ~74% on Senior roles).

### Changed

- Profile: experience is **min/max years only** (dropdown removed). Label like
  “0-1 years” is derived on save for LLM/storage.
- Run Pipeline: scrape control labeled **Max jobs to scrape (up to 2000)** with
  live ≈per-board caption; Results label **Missing technical skills**.
- Setup Enabled boards / health captions already reflect Playwright best-effort.

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.2.7] — 2026-08-05

### Changed

- **Max jobs to scrape** UI/API ceiling raised from **300 → 2000**
  (`SCRAPE_LIMIT_MAX` / `settings.scrape_limit_max`). Aggregate still splits
  across boards (`per_source = max(10, limit ÷ n)`); e.g. 1300 ≈ 100/board
  with 13 sources.

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.2.6] — 2026-08-05

### Changed

- Playwright scrapers (LinkedIn, Indeed, Naukri, Wellfound, Glassdoor) restored
  to the **pre–Phase 2** best-effort style: open URL → wait → parse cards.
  No captcha abort / health cooldown skip on those boards.
- All Playwright boards are **on by default** again in Aggregate.
- Profile allowlist still applies when set; leave Enabled boards empty for defaults.
- Captchas are still never solved.

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.2.5] — 2026-08-05

### Fixed

- Match step no longer crashes when Chroma returns NumPy arrays for `ids` /
  `embeddings` (`The truth value of an array with more than one element is
  ambiguous`). `vector_store` now converts those fields without boolean-
  evaluating ndarrays.

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

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
