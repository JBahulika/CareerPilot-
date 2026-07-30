# CareerPilot AI

**Local-first multi-agent system for job discovery and resume tailoring.**

CareerPilot scrapes live job listings, filters them by experience and skills, ranks matches with semantic embeddings, and generates ATS-friendly tailored resumes as PDFs — entirely on the user’s machine. Resumes never leave the device; parsing, matching, and generation all run locally through Ollama.

Built as a portfolio project demonstrating agent orchestration, local LLM integration, retrieval/ranking, and a full-stack Python application.

---

## What it does

1. **Parse** a master resume PDF into a structured profile  
2. **Scrape** jobs from multiple boards (API + browser automation)  
3. **Filter** by experience tier, skills, location, and recency  
4. **Rank** candidates with embeddings (BGE + ChromaDB)  
5. **Tailor** the resume per job via a local LLM, with truthfulness guardrails  
6. **Export** ATS-friendly single-column PDFs  

Optional **daily 9 AM scan** re-runs the pipeline on fresh postings and writes a digest (local file or WhatsApp when configured).

```
Resume PDF → Parse → Scrape → Filter → Semantic match → Tailor → PDF
```

Orchestration is a LangGraph state machine (`agents/orchestrator.py`) with live progress reported to the API and Streamlit UI.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI |
| Frontend | Streamlit |
| Agent orchestration | LangGraph |
| Local LLM | Ollama (`qwen2.5:14b`) |
| Embeddings | `BAAI/bge-small-en-v1.5` (sentence-transformers) |
| Vector store | ChromaDB |
| Database | SQLite + SQLModel |
| PDF parse / generate | PyMuPDF |
| Job sources | Remotive, RemoteOK, Arbeitnow, Jobicy, Himalayas (API); Wellfound, Indeed, Naukri, LinkedIn, Glassdoor (Playwright) |
| Logging | Loguru |

---

## Architecture highlights

- **Multi-agent pipeline** — dedicated agents for scraping, filtering, matching, tailoring, and PDF generation, coordinated by a shared typed state graph  
- **Privacy by design** — local LLM, local embeddings, local SQLite/Chroma; no cloud resume upload  
- **Experience-aware matching** — strict seniority tiers, optional stretch roles, and configurable year flexibility  
- **Truthfulness guardrails** — tailored resumes may only rephrase facts present in the source profile  
- **Aggregated job sources** — one run can query all boards or a single source  
- **Background daily scan** — APScheduler cron for morning digests  

---

## Quick start

**Prerequisites:** Python 3.11+, [Ollama](https://ollama.com), and (for scrape sources) Playwright Chromium.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # optional; needed for scrape-based boards
cp .env.example .env

ollama pull qwen2.5:14b       # Ollama app or `ollama serve` must be running
```

```bash
# Terminal 1 — API
uvicorn main:app --reload

# Terminal 2 — dashboard
streamlit run ui/streamlit_app.py
```

Open **http://localhost:8501** → Setup → Profile (upload resume) → Run Pipeline → Results.

---

## Configuration

Settings are loaded from `.env` (see `.env.example`):

| Variable | Purpose |
|----------|---------|
| `OLLAMA_MODEL` | Local model tag (default `qwen2.5:14b`) |
| `JOB_SOURCE` | `all` or a single source id (`remotive`, `naukri`, …) |
| `TOP_N_JOBS` | How many matches get tailored resumes |
| `RECENT_JOBS_DAYS` / `DAILY_RECENT_JOBS_DAYS` | Recency windows for manual vs morning runs |
| `EXPERIENCE_FLEX_YEARS` | ± years around the profile’s target range |
| `DAILY_SCAN_ENABLED` | Morning pipeline cron (default on) |
| `NOTIFIER_BACKEND` | `local` or `whatsapp` |

Profile preferences (experience level, fields, location, strict/stretch rules) are set once in the UI and reused by every run and the daily scan.

---

## Project structure

```
agents/          # Scraper, filter, matcher, tailor, PDF, orchestrator, job sources
api/routes/      # Resume, jobs, pipeline HTTP endpoints
core/            # Settings (Pydantic) and logging
database/        # SQLModel models, session, repositories
models/          # Shared Pydantic schemas
prompts/         # Versioned LLM prompt templates
services/        # Embeddings, vector store, scoring, scheduler, notifier
ui/              # Streamlit dashboard
tests/           # Unit and fixture-based tests
main.py          # FastAPI entry point
```

---

## Tests

```bash
pytest
```

---

## Demo flow (for reviewers)

1. Confirm API + Ollama healthy on the **Setup** page  
2. Upload a resume on **Profile**; set experience, fields, and location  
3. **Run Pipeline** with Top N (3–5 is enough for a quick demo; each tailored PDF uses a local LLM call)  
4. Open **Results** to view match scores, reasons, apply links, and download PDFs  
5. **History** lists past runs with scrape / match / PDF counts  

---

## Roadmap

- WhatsApp Cloud API digest delivery  
- Cover-letter and interview-prep agents  
- Selective auto-apply automation  
- Multi-user / hosted variant (optional; core remains local-first)
