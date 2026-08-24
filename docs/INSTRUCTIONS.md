# CareerPilot — user instructions

**Version:** see [`VERSION`](../VERSION) · **Changelog:** [`CHANGELOG.md`](../CHANGELOG.md)

This is the step-by-step guide for installing, running, and using CareerPilot.
The short overview lives in [`README.md`](../README.md). Legal guardrails:
[`LEGAL.md`](LEGAL.md).

CareerPilot is **local-first**: scraping, Ollama, and matching run on **your PC**.
It **never auto-applies** and **never solves captchas**.

---

## Contents

1. [What you need](#1-what-you-need)
2. [First-time setup](#2-first-time-setup)
3. [Everyday start](#3-everyday-start)
4. [Dashboard walkthrough](#4-dashboard-walkthrough)
5. [Phone remote (Android & iPhone)](#5-phone-remote-android--iphone)
6. [Job sources](#6-job-sources)
7. [Notifications & Google Drive](#7-notifications--google-drive)
8. [Morning auto-scan](#8-morning-auto-scan)
9. [Configuration (`.env`)](#9-configuration-env)
10. [Troubleshooting](#10-troubleshooting)
11. [More docs](#11-more-docs)

---

## 1. What you need

| Requirement | Notes |
|-------------|--------|
| **Python 3.10+** | [python.org](https://www.python.org/downloads/) — on Windows, check **Add python.exe to PATH** |
| **Ollama** | [ollama.com](https://ollama.com) — local LLM |
| **Disk / RAM** | A 7B model (e.g. `qwen2.5:7b`) is the usual sweet spot; larger models need more RAM/VRAM |
| **Network** | Job boards + (optional) phone on same Wi‑Fi or Tailscale |

Optional later:

- Android Studio / JDK 17 — only if you build the phone **APK**
- WhatsApp Cloud API / SMTP / Google Drive — only for digests & backup
- Free [Adzuna](https://developer.adzuna.com) keys — optional extra job API

---

## 2. First-time setup

### Windows (recommended)

1. Download or clone this repo (zip from GitHub is fine).
2. Install **Python 3.10+** and **Ollama** (once per PC).
3. Double-click **`setup_careerpilot.bat`**.
   - Creates `.venv`, installs dependencies, installs Playwright Chromium
   - Copies `.env.example` → `.env` if needed
   - Then starts the app (model picker → API + Streamlit)

If something fails, open a terminal in the project folder and read the error text.

### Mac / Linux

```bash
cd /path/to/CareerPilot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
ollama pull qwen2.5:7b   # or your preferred model
```

Then either:

```bash
python -m launcher.main
```

or two terminals:

```bash
# Terminal 1
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2
streamlit run ui/streamlit_app.py
```

Open the Streamlit URL (usually `http://localhost:8501`).

### Optional: Windows exe wrapper

After one successful setup, `build_careerpilot_exe.bat` can build `CareerPilot.exe`.
Keep the **exe next to the full project folder**. It still needs Python + Ollama on
the machine (it does not bundle the multi‑GB ML stack).

---

## 3. Everyday start

### Windows

Double-click **`start_careerpilot.bat`**.

1. Preflight checks Python / Ollama / packages.
2. **Model picker** — choose an Ollama model, **or wait 10 seconds** to keep the
   last model saved in `.env` (`OLLAMA_MODEL`). Start typing to cancel the timer.
3. API (port **8000**) and Streamlit (port **8501**) start; the browser opens.

No reinstall on daily start. If `.venv` is missing, the bat hands off to setup.

### Terminal (any OS)

```bash
python -m launcher.main          # interactive (10s → previous model)
python -m launcher.main --auto   # non-interactive, keep current model
python -m launcher.main --model qwen2.5:7b
```

---

## 4. Dashboard walkthrough

Streamlit pages (left sidebar):

| Page | What to do |
|------|------------|
| **Setup** | Confirm API + Ollama; **model pins**; **phone remote** status & instructions; morning scan; job-source health; WhatsApp/email/Drive/cookies guides |
| **Profile** | Upload resume PDF once; set experience, location, focus field, enabled job sources, notifications |
| **Run Pipeline** | Set scrape budget / top-N; run a scan now |
| **Results** | Browse scored matches; open apply links; optional skills gap / cover letter draft |
| **Logs** | Per-run scrape diagnostics (which boards returned jobs) |

Typical first session:

1. **Setup** — green “Backend is running” and Ollama OK.
2. **Profile** — upload PDF → parse → set location / experience → **Save**.
3. **Run Pipeline** — start a run; wait for completion.
4. **Results** — review matches; you apply yourself on each site.

---

## 5. Phone remote (Android & iPhone)

Full detail (API, Tailscale, tunnels): [`REMOTE_ACCESS.md`](REMOTE_ACCESS.md).

**Idea:** the phone only sends commands. Scraping and AI stay on the PC.

### On the PC (once)

1. Generate a token:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

2. Put it in `.env`:

```env
REMOTE_API_TOKEN=paste_token_here
REMOTE_UI_ENABLED=true
```

3. Restart CareerPilot (`start_careerpilot.bat` or restart uvicorn).
4. Open **Setup → Phone remote** — **Remote token** should say **Set**, **Status** **ready**.
5. Note the LAN URL shown there (example shape: `http://192.168.0.99:8000/m/`).
6. Allow inbound **TCP 8000** on the PC firewall if the phone cannot connect.

### Android

**Easiest — Chrome (no APK):**

1. Same Wi‑Fi as the PC (or Tailscale).
2. Open the `/m/` URL from Setup.
3. Paste the token → **Save & connect**.
4. Optional: Chrome ⋮ → **Add to Home screen**.

**Optional — APK:**

1. On a PC with Android Studio / SDK: run `build_remote_apk.bat` (or build `mobile_android/`).
2. Install `CareerPilot-Remote-debug.apk` on the phone (allow unknown apps if asked).
3. Server URL = `http://<pc-ip>:8000` (**no** `/m/`) + same token → **Save & connect**.

### iPhone / iPad

No free App Store IPA. Use **Safari**:

1. Same Wi‑Fi (or Tailscale / HTTPS tunnel).
2. Safari → open `http://<pc-ip>:8000/m/`.
3. **Share → Add to Home Screen**.
4. Open the icon → paste token → **Save & connect**.

### Browser on Mac or another PC

Open `http://127.0.0.1:8000/m/` on the host, or the LAN `/m/` URL from another device.

---

## 6. Job sources

Enable/disable boards under **Profile**. Default-on sources include Remotive, RemoteOK,
Arbeitnow, Jobicy, Himalayas, The Muse, We Work Remotely, Working Nomads, Wellfound,
Indeed, Naukri, LinkedIn, Glassdoor.

| Source | How it works |
|--------|----------------|
| **Indeed** | Public GraphQL search with pagination; Playwright fallback |
| **Naukri** | Captures the site’s own `jobapi` JSON (pages 1–3); DOM fallback |
| **LinkedIn / Glassdoor / Wellfound** | Best-effort Playwright (often blocked; never solves captchas) |
| **Adzuna** | Optional; off until you set keys and enable it |

### Optional Adzuna

1. Free keys: [developer.adzuna.com](https://developer.adzuna.com)
2. In `.env`:

```env
ADZUNA_APP_ID=...
ADZUNA_APP_KEY=...
# ADZUNA_COUNTRY=in   # optional; blank = infer from profile location
```

3. Profile → enable **Adzuna**.

### If Indeed/Naukri look empty vs the website

- Confirm Playwright Chromium is installed (`setup_careerpilot.bat` or `playwright install chromium`).
- Raise scrape limit on Run Pipeline.
- Loosen experience flex (1–2 years) — filters drop senior titles for junior profiles.
- Check **Setup → Job source health** and **Logs**.

---

## 7. Notifications & Google Drive

Digests are **human-in-the-loop**: CareerPilot notifies; **you** apply.

Configure in `.env` and/or **Profile → Notifications & cloud backup**.  
Step-by-step UI copy: **Setup → How to connect WhatsApp, email, Drive & cookies**.

### WhatsApp (Cloud API)

```env
NOTIFIER_BACKEND=whatsapp
WHATSAPP_ENABLED=true
WHATSAPP_TOKEN=...
WHATSAPP_PHONE_ID=...
WHATSAPP_RECIPIENT=+91XXXXXXXXXX
```

### Email (SMTP)

```env
NOTIFIER_BACKEND=email
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM=...
EMAIL_TO=...
```

Use `NOTIFIER_BACKEND=both` for WhatsApp + email. A local file under
`logs/notifications/` is **always** written when there is a digest.

### Google Drive backup (optional)

1. Google Cloud service account JSON key.
2. Profile → upload JSON + set folder ID.
3. Share that Drive folder with the service-account email (Editor).
4. Enable backup of digests / profile / run summaries.

### Board cookies (advanced, optional)

See [`examples/cookies.example.md`](examples/cookies.example.md) and [`LEGAL.md`](LEGAL.md).
Cookies are session secrets — never commit `data/cookies/`. They do **not** bypass
captchas or enable auto-apply.

---

## 8. Morning auto-scan

When the API is running and `DAILY_SCAN_ENABLED=true` (default):

1. Scrapes recent jobs (`DAILY_RECENT_JOBS_DAYS`, default 2).
2. Runs the pipeline with your saved Profile.
3. Sends a digest capped at `MAX_DIGEST_JOBS` (default 5), only jobs ≥ your min score.

Check **Setup → Morning auto-update** or `GET /scheduler/status`.

Optional: random scan window, quiet hours, proxies — see `.env.example` and
[`UPGRADE_NOTES.md`](UPGRADE_NOTES.md).

---

## 9. Configuration (`.env`)

Copy from [`.env.example`](../.env.example). Important knobs:

| Variable | Purpose |
|----------|---------|
| `OLLAMA_MODEL` | Local chat model (launcher updates this) |
| `API_PORT` / `API_BASE_URL` | Backend bind / Streamlit → API |
| `MIN_MATCH_SCORE` | Default match threshold (Profile can override) |
| `JOB_SOURCE` | `all` or a single source id |
| `SCRAPE_LIMIT_MAX` | Cap on aggregate scrape budget |
| `RECENT_JOBS_DAYS` / `DAILY_RECENT_JOBS_DAYS` | Recency windows |
| `REMOTE_API_TOKEN` | Enables phone remote (empty = off) |
| `REMOTE_UI_ENABLED` | Serve mobile UI at `/m/` |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | Optional Adzuna |
| `NOTIFIER_BACKEND` | `local` \| `whatsapp` \| `email` \| `both` |
| `TAILOR_RESUMES_ENABLED` | Resume PDF tailoring (default off) |

Pinned model defaults: [`MODEL_PINS.md`](MODEL_PINS.md) · `GET /meta/pins`.

---

## 10. Troubleshooting

| Problem | What to try |
|---------|-------------|
| Backend not reachable in Setup | Start via `start_careerpilot.bat` or `uvicorn main:app`; confirm port 8000 |
| Ollama not ready | Open the Ollama app; `ollama pull qwen2.5:7b` |
| Indeed/Naukri empty | Playwright Chromium; experience flex; Logs / source health |
| Phone cannot connect | Token set + restart; same Wi‑Fi; firewall TCP 8000; use LAN IP from Setup |
| Remote Status = disabled | Set `REMOTE_API_TOKEN` in `.env`, restart API, refresh Setup |
| Digests missing | Check Profile notifications; `logs/notifications/`; `NOTIFIER_BACKEND` |
| Heavy model warning | Pick a smaller tag (3B–7B) or wait for the 10s timeout to keep your last model |

---

## 11. More docs

| Doc | Topic |
|-----|--------|
| [`README.md`](../README.md) | Project overview, stack, roadmap |
| [`REMOTE_ACCESS.md`](REMOTE_ACCESS.md) | Phone remote deep dive (API, Tailscale, ngrok) |
| [`MODEL_PINS.md`](MODEL_PINS.md) | Changing default models |
| [`UPGRADE_NOTES.md`](UPGRADE_NOTES.md) | Version upgrades + phase shipping |
| [`LEGAL.md`](LEGAL.md) | Acceptable use |
| [`CHANGELOG.md`](../CHANGELOG.md) | What changed per version |
| [`mobile_android/README.md`](../mobile_android/README.md) | Building the Android APK |
