# CareerPilot AI

**Version [`0.10.0`](VERSION)** · **[Instructions (start here)](docs/INSTRUCTIONS.md)** · [Changelog](CHANGELOG.md) · [Upgrade notes](docs/UPGRADE_NOTES.md) · [Remote access](docs/REMOTE_ACCESS.md) · [Model pins](docs/MODEL_PINS.md) · [Legal](docs/LEGAL.md)

Local-first AI job discovery: scrape → filter → score against your resume on **your
machine** (Ollama + LangGraph). FastAPI backend, Streamlit dashboard, optional
phone remote control.

Your resume never leaves your PC. CareerPilot **never auto-applies** and **never
solves captchas**. (Resume PDF tailoring is off by default; set
`TAILOR_RESUMES_ENABLED=true` to re-enable.)

---

## Quick start

### Windows (easiest)

1. Install [Python 3.10+](https://www.python.org/downloads/) (add to PATH) and [Ollama](https://ollama.com).
2. **First time:** double-click **`setup_careerpilot.bat`**.
3. **Every day:** double-click **`start_careerpilot.bat`**.
   - Model picker appears; **wait 10 seconds** to keep your last model, or pick a number.
4. Open Streamlit (usually `http://localhost:8501`) → **Setup** → **Profile** → **Run Pipeline**.

### Mac / Linux

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
ollama pull qwen2.5:7b
python -m launcher.main
```

Or run API + UI manually:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000   # terminal 1
streamlit run ui/streamlit_app.py                        # terminal 2
```

**Full step-by-step** (phone remote, notifications, job sources, troubleshooting):
→ **[`docs/INSTRUCTIONS.md`](docs/INSTRUCTIONS.md)**

---

## What you can do

| Feature | Where |
|---------|--------|
| Upload resume, set location / experience / sources | **Profile** |
| Run a job scan now | **Run Pipeline** |
| Browse scored matches + apply links | **Results** |
| Morning digest (you apply manually) | Scheduler + WhatsApp / email / local file |
| Control from phone (Android / iPhone) | **Setup → Phone remote** · [`docs/REMOTE_ACCESS.md`](docs/REMOTE_ACCESS.md) |
| Skills gap / cover letter draft | **Results** (per selected job) |
| Check board health / Ollama / remote status | **Setup** |

---

## Pipeline

```
Resume PDF → Parse → Scrape jobs → Filter → Semantic match
(optional: tailor resume → PDF when TAILOR_RESUMES_ENABLED=true)
```

Orchestration: [`agents/orchestrator.py`](agents/orchestrator.py).

---

## Tech stack

| Layer | Choice |
|-------|--------|
| Backend | FastAPI |
| Dashboard | Streamlit |
| Phone UI | PWA at `/m/` + optional Android APK (`mobile_android/`) |
| Agents | LangGraph |
| LLM | Ollama (pinned default `qwen2.5:7b` — see [`docs/MODEL_PINS.md`](docs/MODEL_PINS.md)) |
| Embeddings | `BAAI/bge-base-en-v1.5` |
| Reranker | `BAAI/bge-reranker-base` (on by default) |
| Vector DB | ChromaDB |
| Storage | SQLite (SQLModel) |
| Job boards | Public APIs/RSS + Indeed GraphQL + Naukri capture + Playwright (best-effort) |
| Logging | Loguru |

---

## Job sources (summary)

Prefer public APIs. Scraped boards are best-effort; captcha pages abort (never solved).

| Source | Method | Default |
|--------|--------|---------|
| Remotive, RemoteOK, Arbeitnow, Jobicy, Himalayas, The Muse, Working Nomads | API | on |
| We Work Remotely, Jobspresso | RSS | on |
| Freelancer.com | Public projects API | on |
| Upwork, Guru, PeoplePerHour, Internshala, Truelancer, Workana, freelancermap, WorknHire | Playwright | on |
| Fiverr, Toptal, Malt, Twago, Contra, Arc.dev, Turing, Lemon.io, Braintrust, Gun.io, Codementor, OnlineJobs.ph, Outsourcely, Authentic Jobs, 99designs, crowdSPRING, Dribbble, FlexJobs, Sribulancer, Andela, Revelo, A.Team | Playwright | off (enable in Profile) |
| Adzuna | API (needs free keys) | off |
| Indeed | GraphQL pagination (+ Playwright fallback) | on |
| Naukri | jobapi capture pages 1–3 (+ DOM fallback) | on |
| LinkedIn, Glassdoor, Wellfound | Playwright | on |

Enable boards on **Profile**. Details and Adzuna setup: [`docs/INSTRUCTIONS.md`](docs/INSTRUCTIONS.md#6-job-sources).

---

## Configuration

Copy [`.env.example`](.env.example) → `.env`. Highlights:

| Knob | Purpose |
|------|---------|
| `OLLAMA_MODEL` | Local model (launcher updates this) |
| `MIN_MATCH_SCORE` | Default match % (Profile can override) |
| `JOB_SOURCE` | `all` or one source id |
| `REMOTE_API_TOKEN` | Phone remote (empty = disabled) |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | Optional Adzuna |
| `NOTIFIER_BACKEND` | `local` \| `whatsapp` \| `email` \| `both` |
| `DAILY_SCAN_*` / `MAX_DIGEST_JOBS` | Morning digest |

Full list and how-tos: [`docs/INSTRUCTIONS.md`](docs/INSTRUCTIONS.md#9-configuration-env).

---

## Phone remote (short)

1. Set `REMOTE_API_TOKEN` in `.env` → restart.
2. **Setup → Phone remote** shows connectivity + LAN URLs.
3. **Android:** Chrome → `/m/` URL, or build APK with `build_remote_apk.bat`.
4. **iPhone:** Safari → `/m/` → Share → Add to Home Screen.

Deep dive: [`docs/REMOTE_ACCESS.md`](docs/REMOTE_ACCESS.md).

---

## Project layout

```
agents/           # parse, scrape, filter, match, tailor, orchestrator
api/routes/       # resume, jobs, pipeline, remote
core/             # config, logging, model_pins, remote_auth
database/         # SQLModel
docs/             # INSTRUCTIONS, REMOTE_ACCESS, MODEL_PINS, LEGAL, UPGRADE_NOTES
launcher/         # setup + everyday start (Windows bats call these)
mobile_android/   # optional WebView APK project
remote_ui/        # phone PWA served at /m/
services/         # embeddings, scheduler, digests, remote helpers
ui/               # Streamlit
tests/
main.py
setup_careerpilot.bat / start_careerpilot.bat
VERSION / CHANGELOG.md / .env.example
```

---

## Tests

```bash
pytest
```

---

## Acceptable use

See [`docs/LEGAL.md`](docs/LEGAL.md). Prefer APIs; do not solve captchas or
circumvent access controls; no auto-apply. Not legal advice.

---

## Changelog & shipping rule

Every phase ships on a **dedicated GitHub branch** (e.g. `phase-11-mobile-remote`),
then merges to `main`. **Keep prior phase branches** on GitHub as backups.

Each phase **must** update:

| Artifact | What |
|----------|------|
| [`CHANGELOG.md`](CHANGELOG.md) | Version section + bullets |
| [`docs/UPGRADE_NOTES.md`](docs/UPGRADE_NOTES.md) | Human summary + checklist |
| [`VERSION`](VERSION) | Semver when cutting the release |
| [`README.md`](README.md) + [`docs/INSTRUCTIONS.md`](docs/INSTRUCTIONS.md) | Version, UX, setup |
| [`requirements.txt`](requirements.txt) | Deps — or note “unchanged” in CHANGELOG |
| [`.env.example`](.env.example) | New env knobs |

---

## Roadmap

Tracked in [`docs/UPGRADE_NOTES.md`](docs/UPGRADE_NOTES.md).

1. ~~Match threshold + location gating~~
2. ~~Safe scrape HTTP (no captcha bypass)~~
3. ~~Safe job sources + allowlist~~
4. ~~WhatsApp / email digests~~ — **0.2.12**
5. ~~Proxies, scan windows, quiet hours~~ — **0.3.0**
6. ~~Optional cookies~~ — **0.4.0**
7. ~~Model pins + GitHub source of truth~~ — **0.9.0**
8. ~~Digest dedupe~~ — **0.5.0**
9. ~~Skills gap + cover letter~~ — **0.6.0**
10a. ~~Still-hiring labels~~ — **0.7.0**
10b. ~~One-click launcher~~ — **0.8.0**
11. ~~Phone remote (token API + PWA + Android APK)~~ — **0.10.0**

**Out of scope:** captcha solvers, access-control circumvention, auto-apply.

### Phase knobs (pointer)

Optional env tables for proxies, cookies, still-hiring, digest dedupe, and the
launcher live in older README history / [`.env.example`](.env.example). Prefer
[`docs/INSTRUCTIONS.md`](docs/INSTRUCTIONS.md) and [`docs/UPGRADE_NOTES.md`](docs/UPGRADE_NOTES.md)
for current how-to and upgrade checklists.

| Phase | Doc / entry |
|-------|-------------|
| 7 Model pins | [`docs/MODEL_PINS.md`](docs/MODEL_PINS.md) · `GET /meta/pins` |
| 10b Launcher | `setup_careerpilot.bat` / `start_careerpilot.bat` · 10s model timeout |
| 11 Phone remote | [`docs/REMOTE_ACCESS.md`](docs/REMOTE_ACCESS.md) · Setup UI · `GET /meta/remote` |

### Results pagination

Results default to **10** jobs per page (max 15). API:
`GET /jobs/matches/{run_id}?page=1&page_size=10`

### Git auto-commit (optional)

```bash
brew install gitwatch
./scripts/setup-git-hooks.sh
./scripts/start-gitwatch.sh          # local commits
./scripts/start-gitwatch.sh --push   # commit + push
```
