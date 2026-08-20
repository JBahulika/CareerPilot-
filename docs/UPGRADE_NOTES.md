# Upgrade notes

Human-oriented summary of what changed between versions. Keep this in sync with
[`CHANGELOG.md`](../CHANGELOG.md).

## Process

**Every phase ships on its own GitHub branch, then merges to `main`.** Do **not**
delete old phase branches — they back up that phase’s tip.

### Branch naming

| Phase | Branch |
|-------|--------|
| 0 | `phase-0-upgrade-notes` |
| 1 | `phase-1-match-threshold` |
| 2 | `phase-2-safe-scrape-client` |
| 3 | `phase-3-safe-sources` |
| 4 | `phase-4-digest-notifiers` |
| 5 | `phase-5-proxies-scan-windows` |
| 6 | `phase-6-optional-cookies` |
| 7 | `phase-7-model-pins-publish` |
| 8 | `phase-8-dedupe-notified` |
| 9 | `phase-9-skills-gap-cover-letter` |
| 10a | `phase-10a-still-hiring` |
| 10b | `phase-10b-launcher` |

Workflow:

1. `git checkout main && git pull`
2. `git checkout -b phase-N-…`
3. Implement the phase
4. Complete the **shipping checklist** below
5. Commit → `git push -u origin phase-N-…`
6. Merge into `main` and push `main` (leave the phase branch on GitHub)

### Shipping checklist (required every phase)

- [ ] **`CHANGELOG.md`** — version section + bullets
- [ ] **`docs/UPGRADE_NOTES.md`** — human summary + model pins if changed
- [ ] **`VERSION`** + FastAPI `version=` in `main.py`
- [ ] **`README.md`** — version line, new settings/UX, stack table if models change
- [ ] **`requirements.txt`** — add/pin new deps; if none, write
      `No dependency changes` in that version’s CHANGELOG
- [ ] **`.env.example`** — any new env knobs
- [ ] Tests for the phase behavior
- [ ] Push **phase branch** first, then update **`main`** (keep prior phase branches)

### Current phase backups on GitHub

- [`phase-0-upgrade-notes`](https://github.com/JBahulika/CareerPilot-/tree/phase-0-upgrade-notes)
- [`phase-1-match-threshold`](https://github.com/JBahulika/CareerPilot-/tree/phase-1-match-threshold)
- [`phase-2-safe-scrape-client`](https://github.com/JBahulika/CareerPilot-/tree/phase-2-safe-scrape-client)
- [`phase-3-safe-sources`](https://github.com/JBahulika/CareerPilot-/tree/phase-3-safe-sources)
- [`phase-3b-enable-linkedin-indeed`](https://github.com/JBahulika/CareerPilot-/tree/phase-3b-enable-linkedin-indeed)
- [`phase-4-digest-notifiers`](https://github.com/JBahulika/CareerPilot-/tree/phase-4-digest-notifiers)
- [`phase-5-proxies-scan-windows`](https://github.com/JBahulika/CareerPilot-/tree/phase-5-proxies-scan-windows)
- [`phase-6-optional-cookies`](https://github.com/JBahulika/CareerPilot-/tree/phase-6-optional-cookies)
- [`phase-8-dedupe-notified`](https://github.com/JBahulika/CareerPilot-/tree/phase-8-dedupe-notified)
- [`phase-9-skills-gap-cover-letter`](https://github.com/JBahulika/CareerPilot-/tree/phase-9-skills-gap-cover-letter)
- [`phase-10a-still-hiring`](https://github.com/JBahulika/CareerPilot-/tree/phase-10a-still-hiring)
- [`phase-10b-launcher`](https://github.com/JBahulika/CareerPilot-/tree/phase-10b-launcher)
- [`main`](https://github.com/JBahulika/CareerPilot-/tree/main) (latest merged work)

## Models pin (update when defaults change)

| Component | Current default (0.8.0) |
|-----------|-------------------------|
| Ollama LLM | `qwen2.5:7b` |
| Embeddings | `BAAI/bge-base-en-v1.5` |
| Reranker | `BAAI/bge-reranker-base` (enabled) |
| Min match score | `60` (user-settable) |
| Scrape limit max | `2000` (`SCRAPE_LIMIT_MAX`) |
| Digest cap | `5` (`MAX_DIGEST_JOBS`) |
| Notifier backend | `local` (`NOTIFIER_BACKEND`) |
| Notify dedupe | on (`NOTIFY_DEDUPE_ENABLED`) |
| Resend score delta | `10` (`NOTIFY_RESEND_SCORE_DELTA`) |
| Still-hiring | on (`STILL_HIRING_ENABLED`), window 7 days |
| Scrape budgets | Even per board (same `requested`) |
| Proxies | off (`SCRAPE_PROXY_ENABLED=false`) |
| Scan window | off (fixed `DAILY_SCAN_HOUR`) |
| Quiet hours | off |
| 429 retries | `5` (`SCRAPE_429_MAX_RETRIES`) |
| Board cookies | off (`SCRAPE_COOKIES_ENABLED=false`) |
| Cookie strict limits | on when cookies used |
| Resume tailoring | off (`TAILOR_RESUMES_ENABLED=false`) |

Source of truth for runtime knobs: `core/config.py` (mirrored in `.env.example`).

## [0.8.0] — Phase 10b: one-click launcher

- GitHub / zip users:
  - **First time:** `setup_careerpilot.bat` (`.venv` + deps + `.env` + start).
  - **Everyday:** `start_careerpilot.bat` (model picker + stack; no pip).
- System one-time installs still required: **Python 3.10+** and **Ollama**.
- Preflight opens download pages when Python or Ollama is missing.
- Non-interactive: `python -m launcher.main --auto`. Optional `build_careerpilot_exe.bat`.
- Dependencies: no `requirements.txt` changes.

## [0.7.0] — Phase 10a: still-hiring (date-based)

- Prefer / label jobs with a real `posted_at` inside `STILL_HIRING_DAYS`.
- Statuses: `likely` | `stale` | `unknown`. **Never** invents “still hiring” when
  the post date is missing (fail closed; scrape time is not used as post date).
- Results badge, digest sort preference, scrape recency sort when prefer is on.
- Knobs: `STILL_HIRING_ENABLED`, `STILL_HIRING_DAYS`, `STILL_HIRING_PREFER`.
- Roadmap: former Phase 10 → **10a**; launcher planned as **10b**.
- Dependencies: no `requirements.txt` changes.

## [0.6.0] — Phase 9: skills gap + cover letter (selected job only)

- Results: select a match → **Show skills gap** or **Draft cover letter (Ollama)**.
- Endpoints require an explicit `match_id` for that run; nothing runs automatically.
- Cover letter is a local draft only — never emailed/WhatsApp’d; never auto-apply.
- Dependencies: no `requirements.txt` changes.

## [0.5.0] — Phase 8: dedupe already-notified digests

- Local table `notified_jobs` records jobs included in digests (per profile when known).
- Later digests skip the same `content_hash` / apply URL unless:
  - match score rises by ≥ `NOTIFY_RESEND_SCORE_DELTA`, or
  - listing `posted_at` is newer / fingerprint changed.
- Toggle with `NOTIFY_DEDUPE_ENABLED`. No auto-apply.
- Dependencies: no `requirements.txt` changes.

## [0.4.1] — In-app how-to for WhatsApp / email / Drive / cookies

- Setup + Profile: expandable **How to connect** tabs with step-by-step setup.
- No new env knobs; docs paths unchanged (`README`, `docs/LEGAL.md`, cookie example).
- Dependencies: no `requirements.txt` changes.

## [0.4.0] — Phase 6: optional board cookies + stricter limits

- Advanced users may place session cookies under `data/cookies/` (gitignored):
  `{board}.txt` (header or Netscape) or `{board}.json` (Playwright list).
- Enable with `SCRAPE_COOKIES_ENABLED=true`. Optional `SCRAPE_COOKIES_DIR`.
- When cookies are attached and `SCRAPE_COOKIES_STRICT=true` (default), scrapers
  use longer delays and concurrency 1 (`SCRAPE_COOKIE_MIN/MAX_DELAY_MS`,
  `SCRAPE_COOKIE_MAX_CONCURRENCY`).
- Applied to HTTP (`Cookie` header) and Playwright (browser context).
- Setup / status lists board ids with files — never cookie values.
- Risks: `docs/LEGAL.md`, README, `docs/examples/cookies.example.md`.
- Guardrails unchanged: no captcha solving, no auto-apply; never commit cookies.
- Dependencies: no `requirements.txt` changes.

## [0.3.0] — Phase 5: proxies, scan windows, quiet hours, 429 backoff

- Optional scraper proxies: `SCRAPE_PROXY_ENABLED` + `SCRAPE_PROXY_URL` and/or
  `data/proxies/list.txt` (or `SCRAPE_PROXY_FILE`). Rotate with
  `SCRAPE_PROXY_ROTATE`. Do not commit proxy credentials.
- Random scan window: set `DAILY_SCAN_WINDOW_ENABLED=true` and start/end hours;
  overrides fixed `DAILY_SCAN_HOUR`/`MINUTE`.
- Quiet hours: `QUIET_HOURS_ENABLED` skips the daily job during the local range
  (overnight wrap OK, e.g. 22→7).
- Stronger 429 handling: `SCRAPE_429_BASE_DELAY_MS` / `MAX_DELAY_MS` / `MAX_RETRIES`;
  honors `Retry-After`.
- Setup UI shows window / quiet / proxy status from `/scheduler/status`.
- Guardrails unchanged: no captcha solving, no auto-apply.
- Dependencies: no `requirements.txt` changes.

## [0.2.23] — Coerce certification objects on parse

- LLM `{name, provider}` certifications flatten to strings so Profile parse succeeds.
- Dependencies: no `requirements.txt` changes.

## [0.2.22] — Manual-run digests

- Profile + Run Pipeline: optional WhatsApp/email/local digest after manual scans.
- Dependencies: no `requirements.txt` changes.

## [0.2.21] — Profile WA/email + Google Drive backup

- Profile: configure digest WhatsApp/email/SMTP and optional Drive folder backup.
- Dependencies: `google-api-python-client`, `google-auth`.

## [0.2.20] — Browse filter-rejected scrapes

- Filter-rejected scrapes stay viewable under Results → Show low matches.
- Pagination / empty-state fixes when scored=0.
- Dependencies: no `requirements.txt` changes.

## [0.2.19] — Even budgets + low-match Results

- Same `requested` count per board; search uses skills and roles; default scrape 400.
- Results: optional view of scores ≥1%; digests still use min match threshold.
- Dependencies: no `requirements.txt` changes.

## [0.2.18] — Optional focus-field dropdown

- Profile (and optional Run override): narrow jobs to one field (AIML, Data Science, …)
  or leave **Any** for skill-first discovery.
- Dependencies: no `requirements.txt` changes.

## [0.2.17] — Skill-first job discovery

- Board search and keep-rules driven by resume skills; role title is secondary.
- Dependencies: no `requirements.txt` changes.

## [0.2.16] — Broader AIML scrape + adjacent roles

- Adjacent roles + skill matching so Data Analyst etc. surface for AIML resumes.
- API dump filters no longer require AI/ML title tokens only.
- Dependencies: no `requirements.txt` changes.

## [0.2.15] — Recency + experience filter fixes

- Relative post dates parsed; unknown dates fail closed under a day window.
- Stronger year-requirement parsing (`5+`, ranges); flex ±1 honored.
- Dependencies: no `requirements.txt` changes.

## [0.2.14] — Pause tailored resume PDFs

- Tailoring/PDF step skipped unless `TAILOR_RESUMES_ENABLED=true`.
- Results download button removed; pipeline is discover + match only for now.
- Dependencies: no `requirements.txt` changes.

## [0.2.13] — Smarter scrape budgets + multi-query search

- Aggregate allocates scrape_limit by source safety weight (API/RSS get more).
- Focused search queries (2–3) replace mega keyword strings; Remotive/Playwright
  fan out; keyword feeds match any query words.
- Cross-source URL/title dedupe + early relevance sort before cap truncate.
- Dependencies: no `requirements.txt` changes.

## [0.2.12] — Phase 4 human-in-the-loop digests

- Digests: title, company, location, score, reason, apply link; threshold +
  location gated; capped (`MAX_DIGEST_JOBS=5`).
- Backends: `local` | `whatsapp` | `email` | `both`; local file always written.
- SMTP email via env; WhatsApp Cloud API when configured.
- UI/README: discover + notify only — user applies manually (no auto-apply).
- Dependencies: no `requirements.txt` changes.

## [0.2.11] — Match honesty: sales fluff + role gates

- Filter drops solution selling / champion building / pre-post-sales duties.
- Entry profiles: Principal/Partner + sales/solutions-engineer roles → Skip/low score.
- Dependencies: no `requirements.txt` changes.

## [0.2.10] — City aliases + geo expansion

- Bangalore/Bengaluru, Bombay/Mumbai, Delhi/New Delhi, etc.
- Preference expands for scrape URLs; filter matches aliases + state context.
- Dependencies: no `requirements.txt` changes.

## [0.2.9] — Logs with per-source scrape diagnostics

- History → Logs; sidebar tagline removed.
- Each pipeline run records per-website scrape stats in `summary_json`.
- Dependencies: no `requirements.txt` changes.

## [0.2.8] — Cleaner missing skills + scrape UX

- Soft skills stripped from match Missing list; technical gaps only.
- Senior roles for fresher/0–1 hard-capped in matcher score.
- UI shows scrape max 2000 + per-board estimate.
- Profile experience: min/max years only (no discrete level dropdown).
- Dependencies: no `requirements.txt` changes.

## [0.2.7] — Higher scrape limit ceiling

- Run Pipeline / `/jobs/scrape` max raised 300 → 2000.
- Tip: set ~`100 × number of enabled boards` for ~100 asks per source.
- Dependencies: no `requirements.txt` changes.

## [0.2.6] — Restore best-effort Playwright scrapers

- LinkedIn / Indeed / Naukri / Wellfound / Glassdoor: pre–Phase 2 Playwright
  (no captcha abort; Aggregate always attempts enabled boards).
- All scrape boards default-on again.
- Still never solves captchas / never uses bypass kits.
- Dependencies: no `requirements.txt` changes.

## [0.2.5] — Fix match crash on Chroma NumPy arrays

- `services/vector_store.py`: safe conversion of Chroma `ids` / `embeddings`
  (no `value or []` on ndarrays).
- Symptom was pipeline failure at match with ambiguous array truth-value error.
- Dependencies: no `requirements.txt` changes.

## [0.2.4] — Enable LinkedIn + Indeed by default

- LinkedIn / Indeed: `enabled_by_default=True`, still `disabled_captcha` + captcha abort.
- Glassdoor remains off by default.
- Dependencies: no `requirements.txt` changes.

## [0.2.3] — Phase 3 safe sources + allowlist

- Added The Muse, We Work Remotely, Working Nomads.
- Captcha-prone boards off by default; profile allowlist for enabled boards.
- JobSpy skipped this phase.
- Dependencies: no `requirements.txt` changes.

## [0.2.2] — Phase 2 safe scrape client + source health

- Browser-like HTTP client with jitter, concurrency, retries; captcha → abort.
- Playwright scrapers share UA/headers + captcha abort.
- Setup / `GET /jobs/sources/health` for per-source status.
- Dependencies: no `requirements.txt` changes (`httpx` already present).

## [0.2.1] — Phase 1 match threshold + filter transparency

- Profile + Run Pipeline: set / override minimum match % (default 60).
- Location + include_remote gate filter eligibility; digests honor threshold.
- Results/History show compact exclusion reasons from the filter stage.
- Tests: `tests/test_threshold.py` (+ filter tests updated for `FilterResult`).
- Dependencies: no `requirements.txt` changes.

## [0.2.0] — Phase 0 guardrails

- Versioning: `VERSION` = `0.2.0`.
- Changelog discipline documented for all future phase PRs.
- Legal / ToS stance: prefer APIs; no captcha solving; no auto-apply
  (`docs/LEGAL.md`).
- Gitignore: cookies, proxy secret files, `.env`, local data dirs.
- Documented matching upgrades already in-tree (hybrid search, reranker, base
  embeddings, richer parser/schema).
- Dependencies: no `requirements.txt` changes (docs/guardrails only).

## Unreleased — phased roadmap (reference)

| Phase | Intent |
|-------|--------|
| 5 | ~~Proxies, random scan window, quiet hours, 429 backoff~~ — **0.3.0** |
| 6 | ~~Optional user cookies (advanced), stricter rate limits~~ — **0.4.0** |
| 7 | Model pin checklist + publish GitHub as source of truth |
| 8 | ~~Dedupe across runs (already notified)~~ — **0.5.0** |
| 9 | ~~Skills-gap + cover letter only after user selects a job~~ — **0.6.0** |
| 10a | ~~Still-hiring (fresh/dated listings; fail closed)~~ — **0.7.0** |
| 10b | ~~One-click launcher (Ollama + API + Streamlit, model picker)~~ — **0.8.0** |
| 7 | Model pin checklist + publish GitHub as source of truth |

## How to verify after upgrading

1. `cat VERSION` matches README / API version.
2. Setup page: API + Ollama healthy.
3. Upload resume → run pipeline (small Top N) → Results.
4. Confirm no secrets (`.env`, `data/cookies/`, proxy lists) are staged for commit.
5. `pip install -r requirements.txt` still succeeds after any dep edits.
