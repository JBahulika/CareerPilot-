# CareerPilot — run

**Once (first time only)**

```bash
cd /Users/bahulika/Documents/Projects_Stairway/P23_CAREERPILOT
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
ollama pull qwen2.5:14b
```

---

**Term 1 — Ollama** (skip if Ollama app is already running)

```bash
ollama serve
```

**Term 2 — API**

```bash
cd /Users/bahulika/Documents/Projects_Stairway/P23_CAREERPILOT
source .venv/bin/activate
uvicorn main:app --reload
```

**Term 3 — UI**

```bash
cd /Users/bahulika/Documents/Projects_Stairway/P23_CAREERPILOT
source .venv/bin/activate
streamlit run ui/streamlit_app.py
```

Open **http://localhost:8501** → Setup → Profile → Run Pipeline.

---

**Term 4 — auto-commit (optional)**

```bash
cd /Users/bahulika/Documents/Projects_Stairway/P23_CAREERPILOT
./scripts/start-gitwatch.sh --push
```

Commits + pushes on every save. Ctrl+C to stop.
