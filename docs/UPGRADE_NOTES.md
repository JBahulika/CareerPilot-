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
- [`main`](https://github.com/JBahulika/CareerPilot-/tree/main) (latest merged work)

## Models pin (update when defaults change)

| Component | Current default (0.2.2) |
|-----------|-------------------------|
| Ollama LLM | `qwen2.5:7b` |
| Embeddings | `BAAI/bge-base-en-v1.5` |
| Reranker | `BAAI/bge-reranker-base` (enabled) |
| Min match score | `60` (user-settable) |

Source of truth for runtime knobs: `core/config.py` (mirrored in `.env.example`).

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
| 3 | More safe sources + allowlist; disable captcha-prone by default |
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
