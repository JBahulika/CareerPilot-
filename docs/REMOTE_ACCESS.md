# Remote access (Phase 11)

Control CareerPilot from your phone: **trigger a pipeline**, **see status**,
**read digests**, **toggle daily scan / notify prefs**. Scraping, Ollama, and
matching always run on the **host PC or VPS** — the phone only sends commands.

**Never auto-applies. Never solves captchas.**

## Enable (host)

1. Generate a long random token (do not reuse passwords):

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

2. Put it in `.env`:

```env
REMOTE_API_TOKEN=your_long_random_token_here
REMOTE_UI_ENABLED=true
```

3. Restart uvicorn (`start_careerpilot.bat` or your process manager).

4. Note your reachability URL:

| Access | Example |
|--------|---------|
| Same Wi‑Fi (LAN) | `http://192.168.1.10:8000` |
| Tailscale | `http://100.x.x.x:8000` |
| HTTPS tunnel | `https://your-name.ngrok-free.app` |

---

## Install on your phone

### Android — APK (recommended)

1. On a PC with **Android Studio** (or JDK 17 + Android SDK):
   - Double-click **`build_remote_apk.bat`**, **or**
   - Open folder `mobile_android/` in Android Studio → **Build → Build Bundle(s) / APK(s) → Build APK(s)**
2. The debug APK is copied to the repo root as **`CareerPilot-Remote-debug.apk`**
   (also under `mobile_android/app/build/outputs/apk/debug/`).
3. Copy the APK to your phone (USB, Drive, etc.).
4. On Android: allow **Install unknown apps** for your file manager, then open the APK.
5. Open **CareerPilot Remote** → enter:
   - **Server URL** — e.g. `http://192.168.1.10:8000` (no `/m/` needed)
   - **Token** — same as `REMOTE_API_TOKEN`
6. Tap **Save & connect**.

The APK bundles the remote UI; it talks to your PC over the network. Processing stays on the host.

### iPhone — Safari (free; no App Store app)

Apple does not allow a free public IPA without a paid developer account. Use the Home Screen web app:

1. On the iPhone, open **Safari** (not Chrome).
2. Go to `http://<your-pc>:8000/m/` (LAN, Tailscale, or HTTPS tunnel).
3. Tap **Share** → **Add to Home Screen** → **Add**.
4. Open the new icon → paste your **token** (server URL is usually prefilled) → **Save & connect**.

---

## Browser (any phone, no install)

| Access | URL |
|--------|-----|
| LAN / Tailscale / tunnel | `http(s)://<host>:8000/m/` |

Paste the token once; it is stored in the browser / app.

## API (token required)

All routes under `/remote/*` need:

```http
Authorization: Bearer <REMOTE_API_TOKEN>
```

or header `X-Remote-Token: <token>`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/remote/ping` | Auth check |
| GET | `/remote/status` | Scheduler, profile, recent runs |
| POST | `/remote/pipeline/run` | Start pipeline on host |
| GET | `/remote/pipeline/runs` | List runs |
| GET | `/remote/pipeline/runs/{id}` | Run status |
| GET | `/remote/digests/latest` | Recent digest files |
| PATCH | `/remote/settings` | Toggle `daily_scan_enabled`, notifier knobs, `notify_on_manual_run` |

If `REMOTE_API_TOKEN` is empty, these endpoints return **503** (disabled).

### Setup dashboard (Streamlit)

On the host, open **Setup → Phone remote** for:

- Live connectivity (token set? mobile UI ready? APK built?)
- Detected LAN URLs for the phone
- Step-by-step **Android**, **iPhone / iPad**, and **browser** instructions

API for that panel (no secrets): `GET /meta/remote`.

Example:

```bash
curl -s -H "Authorization: Bearer $REMOTE_API_TOKEN" http://127.0.0.1:8000/remote/status
curl -s -X POST -H "Authorization: Bearer $REMOTE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"top_n\":10,\"scrape_limit\":80}" \
  http://127.0.0.1:8000/remote/pipeline/run
```

## LAN vs remote

| Mode | How | Notes |
|------|-----|--------|
| **LAN** | Phone on same Wi‑Fi | Fast; firewall must allow inbound **8000** on the PC |
| **Tailscale / ZeroTier** | Install on PC + phone; use the mesh IP | Preferred when away from home |
| **ngrok / Cloudflare Tunnel** | Point tunnel at `localhost:8000` | Use HTTPS; **always** keep `REMOTE_API_TOKEN` set |

### Do not

- Port-forward uvicorn to the public internet **without** a token
- Commit `.env` or share the token in chat/screenshots
- Expect the phone to run Ollama/scrapers — it cannot

## Security notes

- Streamlit (`:8501`) remains a local dashboard; Phase 11 remote surface is `/remote` + `/m` (+ Android APK)
- Treat the token like a password; rotate by changing `.env` and restarting
- Digests may contain job titles/links — prefer Tailscale over a public tunnel

## Building the APK (developers)

```text
build_remote_apk.bat          # syncs remote_ui → assets, then gradle assembleDebug
mobile_android/               # Android Studio project (WebView + bundled UI)
```

Requirements: **JDK 17+** and **Android SDK** (Android Studio is the easiest path).

## Out of scope

- Auto-apply, captcha solving
- Free App Store IPA for iPhone (use Safari Home Screen)
- Play Store listing (optional later; use sideloaded debug/release APK for now)
