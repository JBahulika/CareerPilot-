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
| LLM | Ollama (e.g. `qwen2.5:7b`) |
| Embeddings | `BAAI/bge-small-en-v1.5` (sentence-transformers) |
| Vector DB | ChromaDB |
| Storage | SQLite (SQLModel) |
| Resume parsing | PyMuPDF |
| PDF generation | WeasyPrint |
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

- `OLLAMA_MODEL` — local model tag (default `qwen2.5:7b`).
- `JOB_SOURCE` — `remotive` (default, no scraping) or `wellfound`.
- `TOP_N_JOBS` — number of jobs to tailor resumes for.
- `EMBEDDING_MODEL`, `CHROMA_PATH`, `DATABASE_URL`.

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

## Tests

```bash
pytest
```

## Autonomous daily scan

When `DAILY_SCAN_ENABLED=true` (default), the API starts a morning cron job that:

1. Runs the **full pipeline** for your latest profile (top 10 jobs with tailored PDFs)
2. Prioritizes jobs posted in the last 7 days (`RECENT_JOBS_DAYS`)
3. Writes a digest to `logs/notifications/` (or sends WhatsApp when configured)

Check status: `GET /scheduler/status` or the **Setup** page in Streamlit.

```env
DAILY_SCAN_ENABLED=true
DAILY_SCAN_HOUR=8
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
