# CareerPilot AI

An autonomous, **local-first** AI assistant that discovers relevant jobs, scores
them against your resume, and generates ATS-friendly tailored resumes — all on
your machine. Built as a multi-agent pipeline (LangGraph) over a local LLM
(Ollama), with a FastAPI backend and a Streamlit dashboard.

Your resume never leaves your machine: parsing, matching, and generation all run
locally.

## Pipeline

```
Resume PDF -> Parse -> Scrape jobs -> Filter -> Semantic match -> Tailor resume -> PDF
```

Each stage is a LangGraph node sharing one typed pipeline state. See
[`agents/orchestrator.py`](agents/orchestrator.py).

## Tech stack

| Layer | Choice |
|-------|--------|
| Backend | FastAPI |
| Frontend | Streamlit |
| Agents | LangGraph |
| LLM | Ollama (e.g. `qwen2.5:14b`) |
| Embeddings | `BAAI/bge-small-en-v1.5` (sentence-transformers) |
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
ollama pull qwen2.5:14b
```

4. Copy the environment template and adjust if needed:

```bash
cp .env.example .env
```

## Run

Start the backend and the UI in two terminals:

```bash
# Terminal 1 — API
uvicorn main:app --reload

# Terminal 2 — Streamlit dashboard
streamlit run ui/streamlit_app.py
```

Then in the dashboard:

1. **Setup** — confirm the API and Ollama are ready.
2. **Profile** — upload your resume PDF; review the parsed profile.
3. **Run Pipeline** — pick a source and top-N, then run.
4. **Results** — browse ranked matches and download tailored resumes.
5. **History** — see past runs.

## Configuration

All settings live in `.env` (see [`.env.example`](.env.example)):

- `OLLAMA_MODEL` — local model tag (default `qwen2.5:14b`).
- `JOB_SOURCE` — `all` (default, aggregates every source below) or a single site id.
- `EXPERIENCE_FLEX_YEARS` — +/- years around your target range when matching jobs.
- `DEFAULT_INCLUDE_REMOTE` — include remote jobs when filtering by location (default `true`).
- `TOP_N_JOBS` — number of jobs to tailor resumes for.
- `EMBEDDING_MODEL`, `CHROMA_PATH`, `DATABASE_URL`.

### Job sources

CareerPilot scrapes these popular job boards (API where available, Playwright otherwise):

| Site | Method | Region |
|------|--------|--------|
| Remotive | API | Global |
| RemoteOK | API | Global |
| Arbeitnow | API | Global |
| Jobicy | API | Global |
| Himalayas | API | Global |
| Wellfound (AngelList) | Scrape | Global |
| Indeed | Scrape | Global |
| Naukri | Scrape | India |
| LinkedIn | Scrape | Global |
| Glassdoor | Scrape | Global |

Set `JOB_SOURCE=all` to query every source in one run, or pick a single id (e.g. `remotive`, `naukri`). Scraped sites may return fewer results when a board blocks automation.

### Experience matching

On **Profile**, set experience level and target year range once. These drive all filtering:

| Setting | What it does |
|---------|----------------|
| **Strict experience** | Blocks senior/lead roles for 0–1 year profiles (recommended) |
| **Stretch roles** | Allows jobs one tier above you (e.g. mid-level when junior). Off by default |
| **Year flexibility** | +/- years around your target range. Use 0–1 for tight matching |

Senior roles were slipping through because compatibility used loose OR logic and wide defaults. This is now **tier AND years** with tighter bands.

### Location

Set **preferred location** on Profile (city-level, e.g. Bangalore). Remote jobs included by default. Run Pipeline can override location or recency for a single run.

### Morning scan (9 AM)

When the API is running, a daily scan at **9:00 AM** scrapes jobs from the **last 2 days**, runs the pipeline, generates tailored PDFs, and writes a digest to `logs/notifications/`. WhatsApp delivery uses the same digest when configured.

```env
DAILY_SCAN_HOUR=9
DAILY_RECENT_JOBS_DAYS=2
RECENT_JOBS_DAYS=3
```

## Project layout

```
agents/       # parser, scraper, filter, matcher, resume tailor, pdf, orchestrator
api/routes/   # resume, jobs, pipeline endpoints
core/         # config (Pydantic Settings) + logging (Loguru)
database/     # SQLModel tables, session, repositories
models/       # Pydantic schemas shared across layers
prompts/      # versioned LLM prompt templates
services/     # embeddings, ChromaDB vector store, daily scheduler
ui/           # Streamlit dashboard
tests/        # unit + fixture-based tests
main.py       # FastAPI entry point
```

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
3. Generates tailored PDFs for top matches
4. Sends a digest to `logs/notifications/` or **WhatsApp** when configured

Check status: `GET /scheduler/status` or the **Setup** page in Streamlit.

```env
DAILY_SCAN_ENABLED=true
DAILY_SCAN_HOUR=9
DAILY_SCAN_MINUTE=0
NOTIFIER_BACKEND=local   # switch to whatsapp when ready
```

### WhatsApp (coming soon)

Set these when your Meta WhatsApp Cloud API credentials are ready:

```env
NOTIFIER_BACKEND=whatsapp
WHATSAPP_ENABLED=true
WHATSAPP_TOKEN=your_token
WHATSAPP_PHONE_ID=your_phone_id
WHATSAPP_RECIPIENT=+91XXXXXXXXXX
```

## Results pagination

The Results page shows **10 jobs per page** by default (up to 15). Use Previous/Next to browse all matches from a run.

API: `GET /jobs/matches/{run_id}?page=1&page_size=10`

## Roadmap (post-MVP)

- Additional job sources (Naukri, Indeed, LinkedIn, company pages)
- WhatsApp Cloud API delivery
- Auto-apply via browser automation
- Cover letter and interview-prep agents
- Multi-user SaaS dashboard
