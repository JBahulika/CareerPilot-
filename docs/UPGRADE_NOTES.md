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
- [`main`](https://github.com/JBahulika/CareerPilot-/tree/main) (latest merged work)

## Models pin (update when defaults change)

| Component | Current default (0.2.11) |
|-----------|-------------------------|
| Ollama LLM | `qwen2.5:7b` |
| Embeddings | `BAAI/bge-base-en-v1.5` |
| Reranker | `BAAI/bge-reranker-base` (enabled) |
| Min match score | `60` (user-settable) |
| Scrape limit max | `2000` (`SCRAPE_LIMIT_MAX`) |

Source of truth for runtime knobs: `core/config.py` (mirrored in `.env.example`).

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
| 4 | WhatsApp + email digests (human chooses applications; digest caps) |
| 5 | Proxies, random scan window, quiet hours, 429 backoff |
| 6 | Optional user cookies (advanced), stricter rate limits |
| 7 | Model pin checklist + publish GitHub as source of truth |
| 8 | Dedupe across runs (already notified) |
| 9 | Skills-gap + cover letter only after user selects a job |

## How to verify after upgrading

1. `cat VERSION` matches README / API version.
2. Setup page: API + Ollama healthy.
3. Upload resume → run pipeline (small Top N) → Results.
4. Confirm no secrets (`.env`, `data/cookies/`, proxy lists) are staged for commit.
5. `pip install -r requirements.txt` still succeeds after any dep edits.
