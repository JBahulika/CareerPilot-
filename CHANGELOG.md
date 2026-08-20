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

- Phase 7: model pins — see `docs/UPGRADE_NOTES.md`.

## [0.8.0] — 2026-08-20

### Added (Phase 10b)

- **One-click launcher**: `setup_careerpilot.bat` (first time: `.venv` + deps) and
  `start_careerpilot.bat` (everyday: model picker + start, no reinstall).
  Optional `CareerPilot.exe` via `build_careerpilot_exe.bat`.
- Hardware-aware soft warnings before heavy models (“Are you sure?”).
  Pass `--auto` / `--yes` only for non-interactive / CI runs.
- Persists `OLLAMA_MODEL` into `.env`. Opens Python/Ollama download pages when missing.
- Resume parse errors surface in the UI (timeouts / Ollama down) instead of a blank crash.

### Guardrails

- Never auto-applies; never solves captchas.

### Dependencies

- No dependency changes (`requirements.txt` unchanged; uses stdlib + existing `httpx`).

## [0.7.0] — 2026-08-20

### Added (Phase 10a)

- **Still-hiring heuristic**: label and prefer listings with a real `posted_at`
  inside `STILL_HIRING_DAYS` (default 7). Statuses: `likely` / `stale` / `unknown`.
- **Fail closed**: missing dates are never marked “still hiring”; scrape time is
  not used as a post date for this signal. Results show the label; digests and
  scrape sort can prefer likely jobs (`STILL_HIRING_PREFER`).
- Knobs: `STILL_HIRING_ENABLED`, `STILL_HIRING_DAYS`, `STILL_HIRING_PREFER`.

### Guardrails

- No auto-apply; no captcha bypass. Does not query employer ATS for live status.

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.6.0] — 2026-08-20

### Added (Phase 9)

- **Skills gap + cover letter (user-selected only)**: on Results, pick a job then
  optionally open skills gap or draft a cover letter via Ollama.
- API: `GET /jobs/matches/{run_id}/{match_id}/skills-gap`,
  `POST /jobs/matches/{run_id}/{match_id}/cover-letter`.
- Drafts are never auto-sent; CareerPilot never auto-applies.

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.5.0] — 2026-08-20

### Added (Phase 8)

- **Dedupe already-notified jobs**: digests persist sent listings in local DB
  (`notified_jobs`). The same job is not re-notified across runs unless the
  listing clearly refreshed (newer `posted_at` / fingerprint) or the match score
  jumps by `NOTIFY_RESEND_SCORE_DELTA` (default 10).
- Knobs: `NOTIFY_DEDUPE_ENABLED`, `NOTIFY_RESEND_SCORE_DELTA`.

### Guardrails

- Still never auto-applies.

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.4.1] — 2026-08-20

### Added

- **In-app setup guides**: Setup and Profile pages have a **How to connect**
  panel (tabs for WhatsApp, Email, Google Drive, board cookies) with step-by-step
  instructions pointing at Profile fields / `.env` / `docs/LEGAL.md`.

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.4.0] — 2026-08-20

### Added (Phase 6)

- **Optional board cookies** (`SCRAPE_COOKIES_*`): load per-board session cookies
  from gitignored `data/cookies/{source}.txt|.json` for HTTP + Playwright scrapers.
- **Stricter rate limits when cookies are used** (default): higher delays and
  concurrency 1 (`SCRAPE_COOKIES_STRICT`, `SCRAPE_COOKIE_*`).
- Setup / `/scheduler/status` shows which boards have cookie files (values never
  exposed). Example docs: `docs/examples/cookies.example.md`.

### Guardrails

- Still never solves captchas; still never auto-applies.
- Cookie risks documented in `docs/LEGAL.md` and README. Never commit cookie files.

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.3.0] — 2026-08-20

### Added (Phase 5)

- **Optional HTTP(S) proxies** for scrapers (`SCRAPE_PROXY_*`): single URL or
  `data/proxies/list.txt`, optional rotate; credentials never logged; Setup shows
  redacted status via `/scheduler/status`.
- **Random daily scan window** (`DAILY_SCAN_WINDOW_*`): when enabled, arms one
  scan at a random time between window start/end instead of a fixed clock time.
- **Quiet hours** (`QUIET_HOURS_*`): skip the daily scan when local time falls in
  the range (overnight wrap supported).
- **Stronger 429 backoff** (`SCRAPE_429_*`): honor `Retry-After`, exponential
  backoff with higher caps/retries.

### Guardrails

- Still never solves captchas; still never auto-applies.

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.2.23] — 2026-08-12

### Fixed

- Resume parse no longer fails when the LLM returns certifications as
  `{name, provider}` objects — they are coerced to strings.

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.2.22] — 2026-08-12

### Added

- **Manual-run digests**: Profile toggle “Also notify on manual Run Pipeline” plus
  a per-run override on Run Pipeline. Sends the same WhatsApp/email/local digest
  as the morning scan when enabled (threshold + location gated).

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.2.21] — 2026-08-12

### Added

- **Profile notifications UI**: digest backend, WhatsApp number + Cloud API fields,
  digest email + SMTP fields (override `.env` when set).
- **Optional Google Drive backup**: upload service-account JSON, set folder ID;
  digests / profile snapshots / run summaries upload in the background without
  blocking the pipeline.

### Dependencies

- Added `google-api-python-client`, `google-auth` (Drive backup).

## [0.2.20] — 2026-08-07

### Fixed

- Scrapes that fail location/role/experience filters are still saved as **browse
  low-matches** (score ≥1%, below digest threshold) so Results is not empty when
  boards return a handful of jobs.
- Results pagination no longer sticks on “Page 2 of 1” with 0 jobs; clearer empty
  state showing scrape/filter counts.

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.2.19] — 2026-08-07

### Changed

- **Even scrape budgets**: every board gets the same `requested` share of
  `scrape_limit` (no longer API-weighted 3× vs Playwright).
- Board search blends **skills + roles** (and skill+role combos), not skills alone.
- Run Pipeline default scrape cap raised to **400**.

### Added

- Results toggle **Show low matches too (score ≥ 1%)** — scrapes scored ≥1% are
  persisted; digests still use your min match threshold.

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.2.18] — 2026-08-07

### Added

- **Optional focus-field dropdown** on Profile (and Run Pipeline override): choose
  AI/ML, Data Science, Data Analytics, Data Engineering, Backend, etc. When set,
  scrape queries and relevance keep listings in that field. Leave as **Any** for
  skill-first matching across adjacent roles.

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.2.17] — 2026-08-07

### Changed

- **Skill-first discovery**: board search queries are driven by resume skills
  (individual skills + skill blend); preferred role is only a secondary query.
- Dump/API keep-rules and `role_relevant` prioritize skill overlap over AIML
  title matching — Data Analyst / similar roles surface when skills match.

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.2.16] — 2026-08-07

### Changed

- Broader scrape queries for AIML profiles: adjacent roles (Data Analyst /
  Scientist / Engineer, NLP, Python Developer, …) plus a skill-blend query.
- Dump/API boards match on **skills or adjacent roles**, not only AI/ML title
  tokens — fixes empty Remotive/RemoteOK/WWR vs LinkedIn+Arbeitnow dominance.
- `role_relevant` accepts adjacent titles and skill overlap (≥1).
- Jobicy uses skill tags (e.g. python) instead of truncated `AI`.
- Playwright boards run up to 3 focused queries.

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.2.15] — 2026-08-07

### Fixed

- Recency: parse relative dates (`5 months ago`, `2 weeks ago`); do **not** invent
  `posted_at=now` for undated listings; drop unknown/stale dates when a day
  window is set (fail closed). Filter stage re-applies the run’s `recent_days`.
- Experience: parse `5+ years`, `3-5 years`, and similar phrases; entry profiles
  with flex ±1 no longer keep jobs that require far more years.
- Job upsert refreshes metadata and keeps the earliest known post date.

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.2.14] — 2026-08-07

### Changed

- Resume PDF tailoring **paused** by default (`TAILOR_RESUMES_ENABLED=false`).
  Pipeline still scrapes → filters → matches; tailor/PDF step is a no-op.
- Results UI no longer shows “Download tailored resume”; Run Pipeline copy
  updated (“Top N matches to keep”).

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.2.13] — 2026-08-07

### Added

- Weighted Aggregate scrape budgets: API/RSS boards get a larger share of
  `scrape_limit` than Playwright boards (`agents/job_sources/budget.py`).
- Focused multi-query search (`search_queries`): 2–3 short role queries instead
  of one mega keyword bag; juniors get a separate “junior …” query.
- Cross-source identity dedupe (apply URL or company+title) in Aggregate.
- Early skill/role relevance sort before truncating to the scrape cap.
- Remotive + Playwright boards fan out across focused queries (Playwright max 2).
- Tests: `tests/test_scrape_budget.py`; updated `tests/test_scraper_search.py`.

### Changed

- Run Pipeline caption explains weighted budgets (not flat limit÷boards).

### Dependencies

- No dependency changes (`requirements.txt` unchanged).

## [0.2.12] — 2026-08-07

### Added

- Human-in-the-loop digests with **cap** (`MAX_DIGEST_JOBS`, default 5): sort by
  match score desc, then truncate.
- Digest lines: title, company, location, score, short reason, apply link —
  only ≥ min match score and location-eligible (`services/digest.py`).
- Email notifier via SMTP (`SMTP_*`, `EMAIL_TO`).
- `NOTIFIER_BACKEND`: `local` | `whatsapp` | `email` | `both`.
- Local digest file under `logs/notifications/` always written when notifying
  (audit / fallback).
- Setup UI shows digest cap + WhatsApp/email config status; README clarifies
  discover + notify only (no auto-apply).
- Tests: `tests/test_digest.py`, `tests/test_email_notifier.py`, expanded
  notifier/WhatsApp formatter tests (mocked — no real sends).

### Changed

- Daily scheduler relies on notifier prep/cap instead of a separate pre-filter.
- Digest footer states CareerPilot never auto-applies.

### Dependencies

- No dependency changes (`requirements.txt` unchanged; SMTP via stdlib).

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
