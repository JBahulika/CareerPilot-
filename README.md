# CareerPilot AI

**Version [`0.8.0`](VERSION)** · [Changelog](CHANGELOG.md) · [Upgrade notes](docs/UPGRADE_NOTES.md) · [Legal stance](docs/LEGAL.md)

An autonomous, **local-first** AI assistant that discovers relevant jobs and scores
them against your resume — all on your machine. Built as a multi-agent pipeline
(LangGraph) over a local LLM (Ollama), with a FastAPI backend and a Streamlit
dashboard.

Your resume never leaves your machine: parsing and matching run locally.
(Tailored resume PDF generation is paused by default; set
`TAILOR_RESUMES_ENABLED=true` to turn it back on.)

## Changelog rule-

Every phase ships on a **dedicated GitHub branch** (e.g. `phase-2-…`), then
merges to `main`. **Keep prior phase branches** on GitHub as backups — do not
delete them after merge.

Each phase **must** update:-

| Artifact | What to update |
|----------|----------------|
| [`CHANGELOG.md`](CHANGELOG.md) | Version section + bullets |
| [`docs/UPGRADE_NOTES.md`](docs/UPGRADE_NOTES.md) | Human summary + checklist |
| [`VERSION`](VERSION) + `main.py` | Semver bump when cutting the phase release |
| [`README.md`](README.md) | Version line, settings, UX, stack/models |
| [`requirements.txt`](requirements.txt) | New/changed deps — or note “no dependency changes” in CHANGELOG |
| [`.env.example`](.env.example) | New env knobs |

See the full shipping checklist in [`docs/UPGRADE_NOTES.md`](docs/UPGRADE_NOTES.md).

## Pipeline

```
Resume PDF -> Parse -> Scrape jobs -> Filter -> Semantic match
(optional: Tailor resume -> PDF when ``TAILOR_RESUMES_ENABLED=true``)
```

Each stage is a LangGraph node sharing one typed pipeline state. See
[`agents/orchestrator.py`](agents/orchestrator.py).

## Tech stack

| Layer | Choice |
|-------|--------|
| Backend | FastAPI |
| Frontend | Streamlit |
| Agents | LangGraph |
| LLM | Ollama (e.g. `qwen2.5:7b`) |
| Embeddings | `BAAI/bge-base-en-v1.5` (sentence-transformers) |
| Reranker | `BAAI/bge-reranker-base` (optional, enabled by default) |
| Vector DB | ChromaDB |
| Storage | SQLite (SQLModel) |
| Resume parsing | PyMuPDF |
| PDF generation | PyMuPDF |
| Scraping | Remotive API (default), Wellfound (Playwright) |
| Logging | Loguru |

## Setup

1. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Install the Playwright browser (only needed for the Wellfound source):

```bash
playwright install chromium
```

3. Install and start [Ollama](https://ollama.com), then pull a model:

```bash
ollama serve          # in one terminal
ollama pull qwen2.5:7b
```

4. Copy the environment template and adjust if needed:

```bash
cp .env.example .env
```

## Run

### One-click (Windows) — GitHub download

1. Download / clone this repo (or a Release zip that includes the project files).
2. **Once on the PC** (system installs, not per-project):
   - [Python 3.10+](https://www.python.org/downloads/) — check **Add python.exe to PATH**
   - [Ollama](https://ollama.com)
3. **First time only:** double-click **`setup_careerpilot.bat`**
   (creates `.venv`, installs deps, copies `.env`, then starts).
4. **Every day after that:** double-click **`start_careerpilot.bat`**
   (model picker → start API + Streamlit → open browser). No reinstall.

If you skip setup and run `start_careerpilot.bat` with no `.venv`, it will
hand off to setup automatically.

```bash
# Same paths from a terminal
python -m launcher.bootstrap   # first-time setup + start
python -m launcher.main        # everyday start (model picker)

# Non-interactive (CI / scripts)
python -m launcher.main --auto
```

Optional: run `build_careerpilot_exe.bat` after one successful setup to produce
`CareerPilot.exe` in the repo root. Ship the **exe next to the full project**
(or zip the folder). The exe is a bootstrapper — it still needs Python + Ollama
on the machine (bundling torch + models would be multi‑GB).

### Manual (two terminals)

```bash
# Terminal 1 — API
uvicorn main:app --reload

# Terminal 2 — Streamlit dashboard
streamlit run ui/streamlit_app.py
```

Then in the dashboard:

1. **Setup** — confirm the API and Ollama are ready.
2. **Profile** — upload your resume PDF; review the parsed profile; optionally set a **focus field** (e.g. AI/ML or Data Science).
3. **Run Pipeline** — pick top-N and scrape budget, then run (optional focus/location overrides).
4. **Results** — browse ranked matches and open apply links.
5. **Logs** — per-run scrape diagnostics (jobs per website, empty/failed boards).

## Configuration

All settings live in `.env` (see [`.env.example`](.env.example)):

- `OLLAMA_MODEL` — local model tag (default `qwen2.5:7b`).
- `MIN_MATCH_SCORE` — default minimum match % (0–100, default `60`); Profile can override.
- `MAX_DIGEST_JOBS` — max jobs in a digest (default `5`); highest scores first.
- `NOTIFIER_BACKEND` — `local` | `whatsapp` | `email` | `both` (local file always written).
- `SCRAPE_MIN_DELAY_MS` / `SCRAPE_MAX_DELAY_MS` — jitter between scrape/API requests.
- `SCRAPE_MAX_CONCURRENCY` / `SCRAPE_MAX_RETRIES` — polite concurrency and backoff.
- `JOB_SOURCE` — `all` (default, aggregates every source below) or a single site id.
- `EXPERIENCE_FLEX_YEARS` — +/- years around your target range when matching jobs.
- `DEFAULT_INCLUDE_REMOTE` — include remote jobs when filtering by location (default `true`).
- `TOP_N_JOBS` — number of top matches to keep after scoring.
- `TAILOR_RESUMES_ENABLED` — resume PDF tailoring (default `false`; paused for now).
- `EMBEDDING_MODEL`, `CHROMA_PATH`, `DATABASE_URL`.

### Job sources

CareerPilot prefers public API/RSS sources. LinkedIn/Indeed are default-on best-effort scrapes (abort on captcha; never solve). Glassdoor stays off by default:

| Site | Method | Region | Safety | Default |
|------|--------|--------|--------|---------|
| Remotive | API | Global | api | on |
| RemoteOK | API | Global | api | on |
| Arbeitnow | API | Global | api | on |
| Jobicy | API | Global | api | on |
| Himalayas | API | Global | api | on |
| The Muse | API | Global | api | on |
| We Work Remotely | RSS | Global | api | on |
| Working Nomads | API | Global | api | on |
| Wellfound (AngelList) | Scrape | Global | scrape_risky | off |
| Naukri | Scrape | India | scrape_risky | off |
| Indeed | Scrape | Global | disabled_captcha | on |
| LinkedIn | Scrape | Global | disabled_captcha | on |
| Glassdoor | Scrape | Global | disabled_captcha | off |

Set `JOB_SOURCE=all` to query every source in one run, or pick a single id (e.g. `remotive`, `naukri`). Scraped sites may return fewer results when a board blocks automation. Challenge/captcha pages are **aborted** (`captcha_blocked`) — CareerPilot never solves captchas. Check **Setup → Job source health** or `GET /jobs/sources/health`.

### Experience matching

On **Profile**, set experience level and target year range once. These drive all filtering:

| Setting | What it does |
|---------|----------------|
| **Strict experience** | Blocks senior/lead roles for 0–1 year profiles (recommended) |
| **Stretch roles** | Allows jobs one tier above you (e.g. mid-level when junior). Off by default |
| **Year flexibility** | +/- years around your target range. Use 0–1 for tight matching |

Senior roles were slipping through because compatibility used loose OR logic and wide defaults. This is now **tier AND years** with tighter bands.

### Location

Set **preferred location** on Profile (city-level, e.g. Bangalore). Remote jobs included by default. Optionally set a **focus field** (AI/ML, Data Science, …) to narrow listings; leave as Any for skill-first across adjacent roles. Run Pipeline can override location, focus, or recency for a single run.

### Morning scan (9 AM)

When the API is running, a daily scan at **9:00 AM** scrapes jobs from the **last 2 days**, runs the pipeline, and sends a **human-in-the-loop digest** (capped, threshold + location gated). CareerPilot **discovers and notifies** — **you apply manually** (no auto-apply). Tailored resume PDFs are paused by default.

```env
DAILY_SCAN_HOUR=9
DAILY_RECENT_JOBS_DAYS=2
RECENT_JOBS_DAYS=3
MAX_DIGEST_JOBS=5
NOTIFIER_BACKEND=local   # local | whatsapp | email | both
```

## Project layout

```
agents/       # parser, scraper, filter, matcher, resume tailor, pdf, orchestrator
api/routes/   # resume, jobs, pipeline endpoints
core/         # config (Pydantic Settings) + logging (Loguru)
database/     # SQLModel tables, session, repositories
docs/         # LEGAL, UPGRADE_NOTES, phase docs
models/       # Pydantic schemas shared across layers
prompts/      # versioned LLM prompt templates
services/     # embeddings, hybrid search, ChromaDB, daily scheduler
ui/           # Streamlit dashboard
tests/        # unit + fixture-based tests
main.py       # FastAPI entry point
VERSION       # release version (Keep in sync with CHANGELOG)
CHANGELOG.md  # Keep a Changelog history
```

## Acceptable use

See [`docs/LEGAL.md`](docs/LEGAL.md). Short version: prefer APIs; do not solve
captchas or circumvent access controls; CareerPilot does **not** auto-apply —
you choose applications. Not legal advice.

## Git auto-commit (gitwatch)

Optional: auto-commit on save while developing.

```bash
brew install gitwatch          # once
./scripts/setup-git-hooks.sh # strips Cursor co-author from commits
./scripts/start-gitwatch.sh  # watch + commit locally
./scripts/start-gitwatch.sh --push  # commit + push to origin
```

Commit messages list changed files (via `scripts/gitwatch-commit-msg.sh`).

## Tests

```bash
pytest
```

## Autonomous daily scan

When `DAILY_SCAN_ENABLED=true` (default), the API runs a **9 AM** cron job that:

1. Scrapes jobs posted in the last **2 days** (`DAILY_RECENT_JOBS_DAYS`)
2. Runs the full pipeline using your saved Profile preferences
3. Sends a digest (title, company, location, score, reason, apply link) capped at
   `MAX_DIGEST_JOBS` (default 5), only for jobs ≥ `MIN_MATCH_SCORE` and location-eligible

**CareerPilot discovers + notifies. You choose applications and apply manually.**
There is no auto-apply.

Check status: `GET /scheduler/status` or the **Setup** page in Streamlit.

```env
DAILY_SCAN_ENABLED=true
DAILY_SCAN_HOUR=9
DAILY_SCAN_MINUTE=0
MAX_DIGEST_JOBS=5
NOTIFIER_BACKEND=local   # local | whatsapp | email | both
```

A local file under `logs/notifications/` is **always** written when there is a
digest (audit / fallback), even if WhatsApp or email is selected.

### WhatsApp (Cloud API)

```env
NOTIFIER_BACKEND=whatsapp
WHATSAPP_ENABLED=true
WHATSAPP_TOKEN=your_token
WHATSAPP_PHONE_ID=your_phone_id
WHATSAPP_RECIPIENT=+91XXXXXXXXXX
```

### Email (SMTP)

```env
NOTIFIER_BACKEND=email
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=you@example.com
SMTP_PASSWORD=app-password
SMTP_FROM=you@example.com
SMTP_USE_TLS=true
EMAIL_TO=you@example.com
```

Use `NOTIFIER_BACKEND=both` to send WhatsApp and email (local file still written).

You can also set these on **Profile → Notifications & cloud backup** (recipients,
SMTP, WhatsApp token). Profile values override `.env` when filled in.

**In the UI:** Setup and Profile both have a **How to connect** expander with
tabs for WhatsApp, Email, Google Drive, and board cookies.

### Google Drive backup (optional)

1. Create a Google Cloud service account and download its JSON key.
2. On Profile, upload the JSON and set a Drive **folder ID**.
3. Share that folder with the service-account email (Editor).
4. Enable **Backup digests / profile / run summaries**.

Uploads are best-effort and do not block the pipeline.

## Results pagination

The Results page shows **10 jobs per page** by default (up to 15). Use Previous/Next to browse all matches from a run. Turn on **Show low matches too** to include every scored scrape at ≥1% (digests still respect your min match score).

API: `GET /jobs/matches/{run_id}?page=1&page_size=10`

## Roadmap (phased)

Tracked in [`docs/UPGRADE_NOTES.md`](docs/UPGRADE_NOTES.md). High level:

1. ~~User-settable match threshold + location gating~~
2. ~~Safe scrape HTTP layer (no captcha bypass)~~
3. ~~More safe job sources + allowlist~~
4. ~~WhatsApp / email digests (human-in-the-loop; no auto-apply)~~ — **0.2.12**
5. ~~Proxies, random scan windows, quiet hours, stronger 429 backoff~~ — **0.3.0**
6. ~~Optional user cookies (advanced) + stricter limits~~ — **0.4.0**
7. Model pins + GitHub as source of truth
8. ~~Dedupe already-notified digests~~ — **0.5.0**
9. ~~Skills-gap + cover letter only after user selects a job~~ — **0.6.0**
10a. ~~Still-hiring labels / prefer fresh dated listings~~ — **0.7.0**
10b. ~~One-click launcher (Ollama + API + Streamlit)~~ — **0.8.0**
7. Model pins + GitHub as source of truth

**Out of scope:** captcha solvers, access-control circumvention, auto-apply.

### Phase 5 settings (optional)

| Knob | Purpose |
|------|---------|
| `SCRAPE_PROXY_ENABLED` / `SCRAPE_PROXY_URL` / `SCRAPE_PROXY_FILE` | Route scrape HTTP via proxy(ies); list file default `data/proxies/list.txt` |
| `DAILY_SCAN_WINDOW_ENABLED` + start/end | Randomize daily scan time inside a window |
| `QUIET_HOURS_*` | Skip daily scan during local quiet range |
| `SCRAPE_429_*` | Stronger rate-limit backoff (honors `Retry-After`) |

Setup → Morning auto-update shows next scan, window/quiet status, and proxy on/off.

### Phase 6 — optional cookies (advanced)

| Knob | Purpose |
|------|---------|
| `SCRAPE_COOKIES_ENABLED` | Load cookies from `data/cookies/{board}.txt\|.json` |
| `SCRAPE_COOKIES_DIR` | Override cookies directory |
| `SCRAPE_COOKIES_STRICT` | When true, cookie-authenticated scrapes use slower delays + concurrency 1 |
| `SCRAPE_COOKIE_MIN/MAX_DELAY_MS` | Delays used under strict cookie mode |
| `SCRAPE_COOKIE_MAX_CONCURRENCY` | Cap concurrent cookie-authenticated HTTP requests |

**Risks:** cookies are session secrets; misuse can ban **your** account. Prefer APIs.
Never commit `data/cookies/`. See [`docs/LEGAL.md`](docs/LEGAL.md) and
[`docs/examples/cookies.example.md`](docs/examples/cookies.example.md).
Cookies do **not** bypass captchas and do **not** enable auto-apply.

### Phase 8 — digest dedupe

| Knob | Purpose |
|------|---------|
| `NOTIFY_DEDUPE_ENABLED` | Skip jobs already sent in a prior digest (default on) |
| `NOTIFY_RESEND_SCORE_DELTA` | Re-notify if score rises by this many points (default 10) |

Also re-notifies when the listing looks refreshed (newer post date / changed fingerprint).
Still human-in-the-loop — no auto-apply.

### Phase 9 — skills gap & cover letter

On **Results**, select one job, then:

- **Show skills gap** — matched vs missing technical skills for that listing
- **Draft cover letter (Ollama)** — local text draft only

Nothing is emailed or applied automatically. You copy/edit and apply yourself.

### Phase 10a — still hiring

| Knob | Purpose |
|------|---------|
| `STILL_HIRING_ENABLED` | Annotate / prefer dated fresh listings (default on) |
| `STILL_HIRING_DAYS` | Window for “Likely still hiring” (default 7) |
| `STILL_HIRING_PREFER` | Sort likely ahead of stale/unknown in Results & digests |

Only real `posted_at` counts — undated jobs show **Date unknown** and are never
claimed as still open. Recency scrape filters still fail closed on missing dates.

### Phase 10b — launcher

| Entry | Purpose |
|-------|---------|
| `setup_careerpilot.bat` | **First time only** — venv + deps + start |
| `start_careerpilot.bat` | Everyday start — model picker (no pip) |
| `python -m launcher.main --auto` | Non-interactive (no model prompt) |
| `build_careerpilot_exe.bat` | Optional: build `CareerPilot.exe` |
| `--yes` / `--model` / `--skip-pull` | Non-interactive flags |

Persists `OLLAMA_MODEL` to `.env`. Soft-warns on heavy models vs detected RAM/GPU.
