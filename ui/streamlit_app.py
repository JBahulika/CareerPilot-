"""CareerPilot AI — Streamlit dashboard.

A thin client over the FastAPI backend. Run the API first, then:

    streamlit run ui/streamlit_app.py
"""

from __future__ import annotations

import os
import time
from datetime import datetime

import httpx
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
# Keep in sync with core.config Settings.scrape_limit_max
SCRAPE_LIMIT_MAX = int(os.getenv("SCRAPE_LIMIT_MAX", "2000"))

st.set_page_config(page_title="CareerPilot AI", page_icon="🧭", layout="wide")


def api_get(path: str, **kwargs):
    return httpx.get(f"{API_BASE_URL}{path}", timeout=60, **kwargs)


def api_post(path: str, **kwargs):
    return httpx.post(f"{API_BASE_URL}{path}", timeout=600, **kwargs)


def api_put(path: str, **kwargs):
    return httpx.put(f"{API_BASE_URL}{path}", timeout=60, **kwargs)


def _label_from_years(ymin: int, ymax: int) -> str:
    lo, hi = int(ymin), int(ymax)
    if hi < lo:
        lo, hi = hi, lo
    if hi <= 0:
        return "Fresher"
    if lo == 0 and hi <= 1:
        return "0-1 years"
    if hi >= 15 and lo >= 5:
        return "5+ years"
    return f"{lo}-{hi} years"


def _years_from_legacy_level(level: str | None) -> tuple[int, int]:
    text = (level or "").strip().lower()
    if text in ("fresher", "fresh graduate", "new grad", "student") or "intern" in text:
        return 0, 0
    if "0-1" in text or "0 - 1" in text:
        return 0, 1
    if "1-3" in text:
        return 1, 3
    if "3-5" in text:
        return 3, 5
    if "5+" in text or text.startswith("5"):
        return 5, 15
    return 0, 1


def _api_reachable() -> bool:
    try:
        return api_get("/health").status_code == 200
    except Exception:
        return False


def _load_profile() -> dict | None:
    profile = st.session_state.get("profile")
    if profile is not None:
        return profile
    try:
        latest = api_get("/resume/latest")
        if latest.status_code == 200:
            data = latest.json()
            st.session_state["profile_id"] = data["profile_id"]
            st.session_state["profile"] = data["profile"]
            return data["profile"]
    except Exception:
        pass
    return None


def _save_profile(profile: dict) -> bool:
    profile_id = st.session_state.get("profile_id")
    if not profile_id:
        st.error("No profile to save.")
        return False
    resp = api_put(f"/resume/{profile_id}", json=profile)
    if resp.status_code != 200:
        st.error(resp.json().get("detail", "Could not save profile."))
        return False
    data = resp.json()
    st.session_state["profile_id"] = data["profile_id"]
    st.session_state["profile"] = data["profile"]
    return True


def _guide_whatsapp() -> None:
    st.markdown(
        """
**WhatsApp digests (Cloud API)**

1. Create/open an app at [Meta for Developers](https://developers.facebook.com/).
2. Add **WhatsApp** → get a temporary or permanent **Access token** and
   **Phone number ID**.
3. Put your recipient in E.164 form (e.g. `+91XXXXXXXXXX`).
4. Either:
   - Fill **Profile → Notifications** (number + token + phone ID), **or**
   - Set in `.env`: `NOTIFIER_BACKEND=whatsapp`, `WHATSAPP_ENABLED=true`,
     `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_RECIPIENT`.
5. Set digest delivery to `whatsapp` or `both`, then **Save profile**.

A local file under `logs/notifications/` is always written too.
CareerPilot never auto-applies.
        """
    )


def _guide_email() -> None:
    st.markdown(
        """
**Email digests (SMTP)**

1. Use any SMTP host (Gmail: enable 2FA → create an **App password**).
2. Either fill **Profile → Email SMTP**, **or** set in `.env`:
   - `NOTIFIER_BACKEND=email`
   - `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM`
   - `EMAIL_TO` (or set Digest email on Profile)
3. Typical Gmail: host `smtp.gmail.com`, port `587`, TLS on.
4. Set digest delivery to `email` or `both`, then **Save profile**.

Profile SMTP values override `.env` when filled in.
        """
    )


def _guide_drive() -> None:
    st.markdown(
        """
**Google Drive backup (optional)**

1. In [Google Cloud Console](https://console.cloud.google.com/), create a
   **service account** → Keys → download the **JSON** key.
2. Create a Drive folder; copy its **folder ID** from the URL
   (`…/folders/FOLDER_ID`).
3. Share that folder with the service-account email (**Editor**).
4. On **Profile**: upload the JSON → set folder ID → enable backup → **Save**.

Uploads are best-effort and do not block the pipeline. Never commit the JSON key.
        """
    )


def _guide_cookies() -> None:
    st.markdown(
        """
**Optional board cookies (advanced)**

1. Read risks in `docs/LEGAL.md` first — cookies can get **your** account limited.
2. In `.env` set `SCRAPE_COOKIES_ENABLED=true` (restart the API).
3. Put files under `data/cookies/` (gitignored), named by board id:
   - `linkedin.txt` / `indeed.json` / etc.
   - `.txt` = `name=value; …` or Netscape export
   - `.json` = Playwright cookie list
4. Details: `docs/examples/cookies.example.md`.
5. Setup shows which boards have files — **values are never shown**.

Does **not** solve captchas. Does **not** auto-apply. Prefer API sources when you can.
        """
    )


def _render_connect_guides() -> None:
    """In-app how-to for WhatsApp, email, Drive, and cookies."""
    st.subheader("How to connect")
    st.caption(
        "Click a tab for step-by-step setup. Full write-up also lives in the project README "
        "and `docs/LEGAL.md` (cookies)."
    )
    tabs = st.tabs(["WhatsApp", "Email", "Google Drive", "Board cookies"])
    with tabs[0]:
        _guide_whatsapp()
        st.info("Configure fields under **Profile → Notifications & cloud backup**.")
    with tabs[1]:
        _guide_email()
        st.info("Configure fields under **Profile → Notifications & cloud backup**.")
    with tabs[2]:
        _guide_drive()
        st.info("Upload credentials on **Profile → Google Drive backup**.")
    with tabs[3]:
        _guide_cookies()
        st.warning("Never commit files from `data/cookies/`.")


# --- Pages -------------------------------------------------------------------
def page_setup() -> None:
    st.header("Setup")
    st.write(f"API base URL: `{API_BASE_URL}`")

    if not _api_reachable():
        st.error(
            "Backend not reachable. Start it with "
            "`uvicorn main:app --reload` and refresh."
        )
        return
    st.success("Backend is running.")

    with st.expander("How to connect WhatsApp, email, Drive & cookies", expanded=False):
        _render_connect_guides()

    st.subheader("Morning auto-update")
    st.markdown(
        "CareerPilot **discovers** fresh jobs on a schedule, "
        "matches them to your profile, and sends a "
        "**digest** (local file always; WhatsApp / email when configured). "
        "**You choose what to apply to** — CareerPilot never auto-applies."
    )
    try:
        sched = api_get("/scheduler/status").json()
        if sched.get("running"):
            win = ""
            if sched.get("window_enabled"):
                win = (
                    f" · random window **{sched.get('window_start')}–"
                    f"{sched.get('window_end')}**"
                )
            quiet = ""
            if sched.get("quiet_hours_enabled"):
                quiet = (
                    f" · quiet **{sched.get('quiet_hours_start')}–"
                    f"{sched.get('quiet_hours_end')}**"
                    + (" (active now)" if sched.get("currently_quiet") else "")
                )
            st.success(
                f"Next scan: **{sched.get('next_run') or 'scheduled'}** "
                f"(jobs from last {sched.get('recent_days', 2)} days)"
                f"{win}{quiet}"
            )
        elif sched.get("enabled"):
            st.info("Daily scan enabled — restart the API to activate the scheduler.")
        else:
            st.warning("Daily scan disabled. Set `DAILY_SCAN_ENABLED=true` in `.env`.")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Notifier", sched.get("notifier_backend", "local"))
        col2.metric("Digest cap", sched.get("max_digest_jobs", 5))
        wa_status = "Ready" if sched.get("whatsapp_configured") else "Not configured"
        col3.metric("WhatsApp", wa_status)
        em_status = "Ready" if sched.get("email_configured") else "Not configured"
        col4.metric("Email", em_status)
        drive_on = "On" if sched.get("google_drive_enabled") else "Off"
        proxies = sched.get("proxies") or {}
        proxy_label = (
            f"On ({proxies.get('count', 0)})"
            if proxies.get("enabled") and proxies.get("configured")
            else ("Enabled, no URLs" if proxies.get("enabled") else "Off")
        )
        cookies = sched.get("cookies") or {}
        if cookies.get("enabled") and cookies.get("boards_active"):
            cookie_label = f"On ({', '.join(cookies.get('boards_active') or [])})"
        elif cookies.get("enabled"):
            cookie_label = "Enabled, no files"
        elif cookies.get("boards_with_files"):
            cookie_label = "Files present (feature off)"
        else:
            cookie_label = "Off"
        st.caption(
            "Set WhatsApp / email / Drive under **Profile → Notifications & cloud backup**. "
            "Open **How to connect…** above for step-by-step instructions. "
            f"Cap via `MAX_DIGEST_JOBS` (current {sched.get('max_digest_jobs', 5)}). "
            f"Google Drive backup: **{drive_on}**. "
            f"Proxies: **{proxy_label}**. "
            f"Board cookies: **{cookie_label}**. "
            "Scan window / quiet hours / proxies / cookies: configure in `.env`. "
            "Digests include title, company, location, score, reason, and apply link — "
            "only jobs ≥ your min match score and location prefs."
        )

        preview = sched.get("latest_notification_preview")
        if preview:
            st.subheader("Last notification preview")
            st.text(preview)
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Could not load scheduler status: {exc}")

    st.subheader("Job source health")
    st.caption(
        "Polite scrape client aborts on captcha/challenge pages "
        "(never solves them). Statuses: ok, rate_limited, captcha_blocked, disabled, error."
    )
    try:
        sources = api_get("/jobs/sources").json().get("sources", [])
        rows = [
            {
                "source": s.get("id"),
                "name": s.get("name"),
                "method": s.get("method"),
                "safety": s.get("safety"),
                "default_on": s.get("enabled_by_default"),
                "health": s.get("health"),
                "detail": s.get("health_detail") or s.get("notes") or "",
            }
            for s in sources
            if s.get("id") != "all"
        ]
        if rows:
            st.dataframe(rows, use_container_width=True)
        else:
            st.info("No sources listed.")
        try:
            health_resp = api_get("/jobs/sources/health").json()
            st.caption(
                f"Captcha/rate-limit cooldown: {health_resp.get('cooldown_seconds', 1800)}s"
            )
        except Exception:
            pass
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Could not load source health: {exc}")

    st.subheader("Local AI (Ollama)")
    try:
        status = api_get("/ollama/status").json()
        if status.get("ok"):
            st.success(status.get("message"))
        else:
            st.warning(status.get("message"))
            st.code(
                "ollama pull qwen2.5:7b\n"
                "# On Mac, open the Ollama app — no need to run ollama serve"
            )
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not check Ollama status: {exc}")


def page_profile() -> None:
    st.header("Profile")
    st.caption("Upload your resume once. Set experience, roles, location, and matching rules here.")

    uploaded = st.file_uploader("Master resume (PDF)", type=["pdf"])
    if uploaded is not None and st.button("Parse resume", type="primary"):
        with st.spinner(
            "Parsing resume locally (Ollama)… this can take 1–3 minutes. "
            "Keep this tab and the CareerPilot console window open."
        ):
            try:
                resp = api_post(
                    "/resume/upload",
                    files={"file": (uploaded.name, uploaded.getvalue(), "application/pdf")},
                )
            except httpx.TimeoutException:
                st.error(
                    "Parse timed out. Is Ollama running with your model pulled? "
                    "Try again, or pick a smaller model (qwen2.5:7b) from the launcher."
                )
                return
            except httpx.HTTPError as exc:
                st.error(
                    f"Could not reach the API ({exc}). "
                    "Leave the CareerPilot console window open and confirm "
                    "http://localhost:8000/docs loads."
                )
                return
            except Exception as exc:  # noqa: BLE001
                st.error(f"Upload failed: {exc}")
                return
        if resp.status_code != 200:
            detail = "Parsing failed."
            try:
                body = resp.json()
                detail = body.get("detail", detail)
                if isinstance(detail, list):
                    detail = "; ".join(str(x) for x in detail)
            except Exception:
                detail = (resp.text or detail)[:500]
            st.error(detail)
            return
        data = resp.json()
        st.session_state["profile_id"] = data["profile_id"]
        st.session_state["profile"] = data["profile"]
        st.success(f"Parsed profile (id {data['profile_id']}). Review and save below.")
        st.rerun()

    profile = _load_profile()
    if not profile:
        st.info("Upload a resume PDF to get started.")
        return

    st.subheader("Parsed summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("Name", profile.get("name") or "—")
    col2.metric("Role", profile.get("role") or "—")
    col3.metric("Location", profile.get("preferred_location") or profile.get("location") or "—")

    st.write("**Skills:** " + (", ".join(profile.get("skills", [])) or "—"))
    st.write("**Preferred roles:** " + (", ".join(profile.get("preferred_roles", [])) or "—"))
    try:
        from models.schemas import UserProfile as _UP
        from services.skills import focus_field_label

        st.write(
            "**Focus field:** "
            + focus_field_label(_UP.model_validate(profile))
        )
    except Exception:  # noqa: BLE001
        pass

    st.divider()
    st.subheader("Your search preferences")
    st.caption("Everything below is saved once and reused by Run Pipeline and the morning scan.")

    saved_ymin = profile.get("target_years_min")
    saved_ymax = profile.get("target_years_max")
    if saved_ymin is None and saved_ymax is None:
        saved_ymin, saved_ymax = _years_from_legacy_level(profile.get("experience_level"))

    exp_col1, exp_col2 = st.columns(2)
    ymin = exp_col1.number_input(
        "Experience years (min)",
        0,
        20,
        int(saved_ymin if saved_ymin is not None else 0),
        help="Lowest years of experience you want jobs to target.",
    )
    ymax = exp_col2.number_input(
        "Experience years (max)",
        0,
        20,
        int(saved_ymax if saved_ymax is not None else max(int(ymin), 1)),
        help="Highest years of experience you will consider.",
    )
    if int(ymax) < int(ymin):
        st.warning("Max years is below min - they will be swapped on save.")
        ymin, ymax = int(ymax), int(ymin)
    level_label = _label_from_years(int(ymin), int(ymax))
    st.caption(
        f"Target band **{int(ymin)}-{int(ymax)} years** "
        f'(saved as "{level_label}"). '
        "Jobs outside this band are dropped unless stretch is enabled."
    )

    preferred_loc = st.text_input(
        "Preferred job location",
        value=profile.get("preferred_location") or profile.get("location") or "",
        placeholder="e.g. Bangalore, Mumbai, Delhi (aliases OK)",
        help=(
            "Short city names are enough. Bangalore/Bengaluru, Bombay/Mumbai, "
            "Delhi/New Delhi; state/country are inferred. "
            "Comma-separate multiple cities."
        ),
    )
    include_remote = st.checkbox(
        "Include remote jobs",
        value=profile.get("include_remote", True),
    )

    from services.skills import focus_field_options, normalize_focus_field

    field_opts = focus_field_options()
    field_ids = [o["id"] for o in field_opts]
    field_labels = {o["id"]: o["label"] for o in field_opts}
    saved_focus = normalize_focus_field(profile.get("focus_field") or "") or "any"
    if saved_focus not in field_ids:
        saved_focus = "any"
    focus_field = st.selectbox(
        "Focus field (optional)",
        field_ids,
        index=field_ids.index(saved_focus),
        format_func=lambda x: field_labels.get(x, x),
        help=(
            "Narrow listings to one career field (e.g. AI/ML or Data Science). "
            "Leave as Any to keep skill-first matching across adjacent roles."
        ),
    )

    st.markdown("**Matching rules**")
    strict_experience = st.checkbox(
        "Strict experience matching",
        value=profile.get("strict_experience", True),
        help="When on, senior/lead roles are blocked for entry-level profiles (recommended).",
    )
    allow_stretch = st.checkbox(
        "Include stretch roles",
        value=profile.get("allow_stretch", False),
        help="Allow jobs slightly above your tier (e.g. mid-level when you are junior). Off by default.",
    )
    flex_years = st.slider(
        "Year flexibility (+/-)",
        0,
        3,
        int(profile.get("flex_years") if profile.get("flex_years") is not None else 1),
        help="How many years beyond your target range to still consider. Use 0–1 for tight matching.",
    )
    exclude_internships = st.checkbox(
        "Exclude internships",
        value=profile.get("exclude_internships", False),
    )
    min_match_score = st.slider(
        "Minimum match score (%)",
        0,
        100,
        int(profile.get("min_match_score") if profile.get("min_match_score") is not None else 60),
        help="Only jobs at or above this score are kept in Results and digests. Default 60.",
    )

    st.markdown("**Job sources (allowlist)**")
    st.caption(
        "Empty selection uses safe defaults (API/RSS). Captcha-prone boards stay off "
        "unless you explicitly enable them."
    )
    try:
        all_sources = [
            s
            for s in api_get("/jobs/sources").json().get("sources", [])
            if s.get("id") != "all"
        ]
    except Exception:
        all_sources = []
    source_ids = [s["id"] for s in all_sources]
    labels = {
        s["id"]: (
            f"{s.get('name')} [{s.get('safety', s.get('method'))}]"
            + ("" if s.get("enabled_by_default", True) else " — off by default")
        )
        for s in all_sources
    }
    saved = profile.get("enabled_sources") or []
    default_sel = [sid for sid in saved if sid in source_ids]
    enabled_sources = st.multiselect(
        "Enabled boards",
        source_ids,
        default=default_sel,
        format_func=lambda x: labels.get(x, x),
        help="Leave empty to use built-in defaults (API + Playwright boards).",
    )

    st.markdown("**Notifications & cloud backup**")
    st.caption(
        "Set how digests reach you. API secrets can live here (local DB) or in `.env`. "
        "CareerPilot never auto-applies."
    )
    with st.expander("View setup instructions (WhatsApp / email / Drive / cookies)"):
        _render_connect_guides()

    backend_opts = ["local", "whatsapp", "email", "both"]
    saved_backend = (profile.get("notifier_backend") or "local").strip().lower()
    if saved_backend not in backend_opts:
        saved_backend = "local"
    notifier_backend = st.selectbox(
        "Digest delivery",
        backend_opts,
        index=backend_opts.index(saved_backend),
        help="local = file under logs/notifications/. whatsapp/email/both also write that file.",
    )
    notify_on_manual_run = st.checkbox(
        "Also notify on manual Run Pipeline",
        value=bool(profile.get("notify_on_manual_run")),
        help=(
            "When on, clicking Run Pipeline sends the same digest (WhatsApp/email/local) "
            "as the morning scan. Morning scan always notifies when configured."
        ),
    )
    notify_whatsapp = st.text_input(
        "WhatsApp number (E.164)",
        value=profile.get("notify_whatsapp") or "",
        placeholder="+91XXXXXXXXXX",
    )
    notify_email = st.text_input(
        "Digest email",
        value=profile.get("notify_email") or profile.get("email") or "",
        placeholder="you@example.com",
    )
    with st.expander("WhatsApp Cloud API (token + phone ID)"):
        st.caption(
            "From Meta Developer → WhatsApp → API Setup. Leave blank to use `.env`. "
            "Need steps? Open **View setup instructions** above → WhatsApp tab."
        )
        whatsapp_token = st.text_input(
            "WhatsApp token",
            value=profile.get("whatsapp_token") or "",
            type="password",
        )
        whatsapp_phone_id = st.text_input(
            "WhatsApp phone number ID",
            value=profile.get("whatsapp_phone_id") or "",
        )
    with st.expander("Email SMTP (Gmail app password works)"):
        st.caption(
            "Leave blank to use `.env` SMTP_*. Profile values override when set. "
            "Need steps? Open **View setup instructions** above → Email tab."
        )
        smtp_host = st.text_input(
            "SMTP host",
            value=profile.get("smtp_host") or "",
            placeholder="smtp.gmail.com",
        )
        smtp_port = st.number_input(
            "SMTP port",
            1,
            65535,
            int(profile.get("smtp_port") or 587),
        )
        smtp_user = st.text_input(
            "SMTP user",
            value=profile.get("smtp_user") or "",
        )
        smtp_password = st.text_input(
            "SMTP password / app password",
            value=profile.get("smtp_password") or "",
            type="password",
        )
        smtp_from = st.text_input(
            "From address",
            value=profile.get("smtp_from") or "",
            placeholder="you@example.com",
        )

    st.markdown("**Google Drive backup (optional)**")
    st.caption(
        "Upload a service-account JSON, share a Drive folder with that email, "
        "then enable backup. Digests and run summaries upload in the background "
        "while the pipeline keeps running. "
        "Need steps? Open **View setup instructions** above → Google Drive tab."
    )
    google_drive_enabled = st.checkbox(
        "Backup digests / profile / run summaries to Google Drive",
        value=bool(profile.get("google_drive_enabled")),
    )
    google_drive_folder_id = st.text_input(
        "Google Drive folder ID",
        value=profile.get("google_drive_folder_id") or "",
        placeholder="Folder ID from the Drive URL",
        help="Open the folder in Drive; copy the ID from the URL after /folders/.",
    )
    drive_file = st.file_uploader(
        "Service account JSON",
        type=["json"],
        help="Google Cloud → IAM → Service account → Keys → JSON",
    )
    if drive_file is not None and st.button("Save Drive credentials"):
        try:
            resp = api_post(
                "/resume/drive/credentials",
                files={"file": (drive_file.name, drive_file.getvalue(), "application/json")},
            )
            if resp.status_code == 200:
                data = resp.json()
                st.success(
                    f"Saved. Share your folder with **{data.get('client_email')}** (Editor)."
                )
            else:
                st.error(resp.json().get("detail", "Could not save credentials."))
        except Exception as exc:  # noqa: BLE001
            st.error(f"Upload failed: {exc}")

    if st.button("Save profile", type="primary"):
        profile["experience_level"] = _label_from_years(int(ymin), int(ymax))
        profile["target_years_min"] = int(ymin)
        profile["target_years_max"] = int(ymax)
        profile["preferred_location"] = preferred_loc.strip()
        profile["include_remote"] = include_remote
        profile["strict_experience"] = strict_experience
        profile["allow_stretch"] = allow_stretch
        profile["flex_years"] = int(flex_years)
        profile["exclude_internships"] = exclude_internships
        profile["min_match_score"] = int(min_match_score)
        profile["focus_field"] = "" if focus_field == "any" else focus_field
        profile["enabled_sources"] = list(enabled_sources)
        profile["notifier_backend"] = notifier_backend
        profile["notify_on_manual_run"] = bool(notify_on_manual_run)
        profile["notify_whatsapp"] = notify_whatsapp.strip()
        profile["notify_email"] = notify_email.strip()
        profile["whatsapp_token"] = whatsapp_token.strip()
        profile["whatsapp_phone_id"] = whatsapp_phone_id.strip()
        profile["smtp_host"] = smtp_host.strip()
        profile["smtp_port"] = int(smtp_port) if smtp_host.strip() else None
        profile["smtp_user"] = smtp_user.strip()
        profile["smtp_password"] = smtp_password
        profile["smtp_from"] = smtp_from.strip()
        profile["google_drive_enabled"] = bool(google_drive_enabled)
        profile["google_drive_folder_id"] = google_drive_folder_id.strip()
        if _save_profile(profile):
            st.success("Profile saved. Ready to run the pipeline.")


def page_run() -> None:
    st.header("Run Pipeline")
    profile_id = st.session_state.get("profile_id")
    profile = _load_profile()
    if not profile_id or not profile:
        st.info("Upload and save your profile first.")
        return

    st.markdown(
        """
**What this does:** scrape latest jobs → filter by your experience & skills →
rank matches. (Tailored resume PDFs are paused for now.)

Settings come from your **Profile** (experience, location, strict/stretch rules).
        """
    )

    loc = profile.get("preferred_location") or profile.get("location") or "Any"
    remote = "yes" if profile.get("include_remote", True) else "no"
    saved_threshold = int(
        profile.get("min_match_score") if profile.get("min_match_score") is not None else 60
    )
    enabled = profile.get("enabled_sources") or []
    if enabled:
        boards_label = ", ".join(enabled[:6]) + ("…" if len(enabled) > 6 else "")
    else:
        boards_label = "defaults (all default-on boards)"
    from models.schemas import UserProfile as _UP
    from services.skills import focus_field_label, focus_field_options, normalize_focus_field

    focus_label = focus_field_label(_UP.model_validate(profile))
    st.info(
        f"Using profile: **{profile.get('target_years_min', 0)}-"
        f"{profile.get('target_years_max', 1)} yrs** "
        f"({profile.get('experience_level') or '-'}) | "
        f"roles: {', '.join(profile.get('preferred_roles', [])[:3]) or profile.get('role', '—')} · "
        f"focus: **{focus_label}** · "
        f"location: **{loc}** · remote: **{remote}** · "
        f"min match: **{saved_threshold}%** · "
        f"boards: **{boards_label}** · "
        f"strict: **{'on' if profile.get('strict_experience', True) else 'off'}** · "
        f"stretch: **{'on' if profile.get('allow_stretch') else 'off'}**"
    )
    st.caption(
        "Change which boards run under **Profile → Enabled boards** "
        "(shown once there). This page always scrapes your allowlist."
    )

    col1, col2 = st.columns(2)
    top_n = col1.number_input("Top N matches to keep", 1, 15, 10)
    scrape_limit = col2.number_input(
        f"Max jobs to scrape (up to {SCRAPE_LIMIT_MAX})",
        min_value=10,
        max_value=SCRAPE_LIMIT_MAX,
        value=min(400, SCRAPE_LIMIT_MAX),
        step=50,
        help=(
            f"Total Aggregate cap (max {SCRAPE_LIMIT_MAX}). Budget is split evenly "
            "across enabled boards (same requested count per source)."
        ),
    )
    n_boards = len(enabled) if enabled else 13
    per_even = max(1, int(scrape_limit) // max(n_boards, 1))
    warn = ""
    if int(scrape_limit) >= 800:
        warn = " High values with Playwright boards can be slow."
    st.caption(
        f"Even budgets across **{n_boards}** boards"
        + (" (your allowlist)" if enabled else " (default-on)")
        + f" — about **{per_even}** requested per board."
        f"{warn}"
    )

    send_digest = st.checkbox(
        "Send digest after this run (WhatsApp / email / local)",
        value=bool(profile.get("notify_on_manual_run")),
        help=(
            "Uses Profile digest delivery (local/whatsapp/email/both). "
            "Default follows Profile → “Also notify on manual Run Pipeline”."
        ),
    )

    with st.expander("Override for this run only (optional)"):
        run_location = st.text_input(
            "Location override",
            value="",
            placeholder="Leave blank to use profile location",
        )
        run_include_remote = st.checkbox(
            "Include remote (this run)",
            value=profile.get("include_remote", True),
        )
        field_opts = focus_field_options()
        field_ids = [o["id"] for o in field_opts]
        field_labels = {o["id"]: o["label"] for o in field_opts}
        saved_focus = normalize_focus_field(profile.get("focus_field") or "") or "any"
        if saved_focus not in field_ids:
            saved_focus = "any"
        run_focus = st.selectbox(
            "Focus field (this run)",
            field_ids,
            index=field_ids.index(saved_focus),
            format_func=lambda x: field_labels.get(x, x),
            help="Override Profile focus for this run only. Any = skill-first.",
        )
        run_min_match = st.slider(
            "Min match score for this run (%)",
            0,
            100,
            saved_threshold,
            help="Only keep matches at or above this %. Does not change saved Profile threshold unless you save it there.",
        )
        recent_days = st.slider(
            "Only jobs posted in last N days",
            1,
            14,
            3,
            help="Lower = fresher listings. Morning scan uses 2 days.",
        )

    if st.button("Run pipeline", type="primary"):
        payload = {
            "profile_id": profile_id,
            "top_n": int(top_n),
            "source": "all",
            "scrape_limit": int(scrape_limit),
            "exclude_internships": profile.get("exclude_internships", False),
            "strict_experience": profile.get("strict_experience", True),
            "allow_stretch": profile.get("allow_stretch", False),
            "flex_years": profile.get("flex_years"),
            "include_remote": bool(run_include_remote),
            "recent_days": int(recent_days),
            "min_match_score": int(run_min_match),
            "focus_field": "" if run_focus == "any" else run_focus,
            "send_digest": bool(send_digest),
        }
        if run_location.strip():
            payload["location"] = run_location.strip()
        resp = api_post("/pipeline/run", json=payload)
        if resp.status_code != 200:
            st.error(resp.json().get("detail", "Could not start pipeline."))
            return
        run_id = resp.json()["run_id"]
        st.session_state["run_id"] = run_id
        _poll_run(run_id)


def _poll_run(run_id: int) -> None:
    progress = st.progress(0.0)
    status_box = st.empty()
    steps = {"scrape": 0.2, "filter": 0.4, "match": 0.7, "tailor": 0.85, "complete": 1.0}

    for _ in range(600):
        run = api_get(f"/pipeline/runs/{run_id}").json()
        step = run.get("current_step", "")
        progress.progress(steps.get(step, 0.05))
        status_box.info(
            f"Status: {run['status']} | step: {step or 'starting'} | "
            f"scraped {run['jobs_scraped']} | matched {run['jobs_matched']}"
        )
        if run["status"] in ("completed", "failed"):
            progress.progress(1.0)
            if run["status"] == "completed":
                st.success("Pipeline complete. See the Results page.")
                summary = run.get("summary") or {}
                if summary.get("digest_sent"):
                    st.info(
                        "Digest sent (WhatsApp / email / local per your Profile settings)."
                    )
                elif summary.get("send_digest"):
                    st.caption(
                        "Digest was requested but nothing qualified "
                        "(check min match score / location, or Logs)."
                    )
            else:
                st.error("Pipeline failed.")
            summary = run.get("summary") or {}
            if summary:
                excl = summary.get("filter_exclusions") or {}
                excl_bits = [
                    f"{k.replace('_', ' ')}: {v}" for k, v in sorted(excl.items()) if v
                ]
                st.caption(
                    f"Threshold ≥ {summary.get('min_match_score', '—')}% · "
                    f"location: {summary.get('location') or 'Any'} · "
                    f"remote: {'yes' if summary.get('include_remote', True) else 'no'}"
                    + (f" · filtered out — {'; '.join(excl_bits)}" if excl_bits else "")
                )
            if run.get("errors"):
                st.warning("\n".join(run["errors"]))
            return
        time.sleep(1.0)
    st.warning("Timed out waiting for the pipeline.")


def _format_posted_ago(iso_value: str | None) -> str:
    if not iso_value:
        return ""
    try:
        posted = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
        if posted.tzinfo:
            posted = posted.replace(tzinfo=None)
        days = (datetime.utcnow() - posted).days
        if days <= 0:
            return "Posted today"
        if days == 1:
            return "Posted 1 day ago"
        return f"Posted {days} days ago"
    except ValueError:
        return ""


def page_results() -> None:
    st.header("Results")
    run_id = st.session_state.get("run_id")
    run_id = st.number_input("Run ID", 1, value=int(run_id) if run_id else 1)

    run_meta = {}
    try:
        run_meta = api_get(f"/pipeline/runs/{int(run_id)}").json()
    except Exception:
        run_meta = {}
    summary = run_meta.get("summary") or {}
    threshold = int(summary.get("min_match_score") or 60)
    if summary:
        excl = summary.get("filter_exclusions") or {}
        excl_bits = [f"{k.replace('_', ' ')}: {v}" for k, v in sorted(excl.items()) if v]
        low_n = summary.get("jobs_low_match")
        view_n = summary.get("jobs_viewable")
        extra = ""
        if view_n is not None:
            extra = f" · scored **{view_n}**"
            if low_n:
                extra += f" ({low_n} below threshold)"
        st.info(
            f"Min match **{threshold}%** · "
            f"location **{summary.get('location') or 'Any'}** · "
            f"remote **{'on' if summary.get('include_remote', True) else 'off'}**"
            + extra
            + (f" · exclusions — {'; '.join(excl_bits)}" if excl_bits else "")
        )

    show_low = st.checkbox(
        "Show low matches too (score ≥ 1%)",
        value=False,
        help=(
            "When off, only jobs at/above your min match score are listed. "
            "Turn on to browse every scored scrape with at least 1% relevance "
            "(includes jobs that failed location/role/experience filters)."
        ),
    )
    min_score = 1 if show_low else threshold

    page_size = st.selectbox("Jobs per page", [10, 15], index=0)
    if "results_page" not in st.session_state:
        st.session_state["results_page"] = 1
    # Reset page when toggling low matches or changing run
    toggle_key = f"low:{show_low}:{int(run_id)}"
    if st.session_state.get("_results_toggle") != toggle_key:
        st.session_state["_results_toggle"] = toggle_key
        st.session_state["results_page"] = 1

    page = max(1, int(st.session_state["results_page"]))
    resp = api_get(
        f"/jobs/matches/{int(run_id)}",
        params={"page": page, "page_size": page_size, "min_score": min_score},
    )
    if resp.status_code != 200:
        st.error("Could not load matches.")
        return

    data = resp.json()
    matches = data.get("matches", [])
    total = data.get("total", 0)
    total_pages = max(1, int(data.get("total_pages") or 1))

    if total == 0:
        st.session_state["results_page"] = 1
        page = 1
    elif page > total_pages:
        st.session_state["results_page"] = total_pages
        st.rerun()

    nav1, nav2, nav3 = st.columns([1, 2, 1])
    if nav1.button("Previous", disabled=page <= 1):
        st.session_state["results_page"] = max(1, page - 1)
        st.rerun()
    if nav3.button("Next", disabled=page >= total_pages or total == 0):
        st.session_state["results_page"] = page + 1
        st.rerun()

    mode = "all scored (≥1%)" if show_low else f"strong (≥{threshold}%)"
    nav2.caption(f"Page {page} of {total_pages} · {total} jobs · {mode}")

    scraped_n = run_meta.get("jobs_scraped")
    after_filter = summary.get("jobs_after_filter")
    if not matches:
        bits = []
        if scraped_n is not None:
            bits.append(f"scraped {scraped_n}")
        if after_filter is not None:
            bits.append(f"after filter {after_filter}")
        excl = summary.get("filter_exclusions") or {}
        excl_bits = [f"{k.replace('_', ' ')}: {v}" for k, v in sorted(excl.items()) if v]
        hint = (
            "Turn on **Show low matches** — scrapes that failed location/role/"
            "experience gates are kept there."
            if not show_low
            else "Re-run the pipeline after updating CareerPilot; older runs "
            "did not persist filter-rejected scrapes."
        )
        st.info(
            "No matches for this filter"
            + (f" ({', '.join(bits)})" if bits else "")
            + ". "
            + hint
            + (f" Exclusions: {'; '.join(excl_bits)}." if excl_bits else "")
        )
        return

    st.caption(
        "Missing technical skills = tools, stacks, protocols, certs - "
        "not soft skills or sales/process duties. "
        "**Likely still hiring** only appears when a real post date is within "
        f"your still-hiring window — undated listings are never claimed as still open."
    )
    st.markdown("**Select a job for skills gap / cover letter** (optional — you choose)")
    labels = []
    id_by_label = {}
    for m in matches:
        mid = m.get("match_id")
        if mid is None:
            continue
        label = (
            f"#{mid} · {m.get('title', '?')} — {m.get('company', '?')} "
            f"({int(m.get('match_score') or 0)}%)"
        )
        labels.append(label)
        id_by_label[label] = int(mid)

    selected_match_id = None
    if labels:
        choice = st.selectbox(
            "Selected job",
            ["— none —"] + labels,
            help="Skills gap and cover letter only run after you pick a job. Never auto-applies.",
        )
        if choice != "— none —":
            selected_match_id = id_by_label[choice]
            c_gap, c_cover = st.columns(2)
            if c_gap.button("Show skills gap", type="secondary"):
                try:
                    gap = api_get(
                        f"/jobs/matches/{int(run_id)}/{selected_match_id}/skills-gap"
                    ).json()
                    st.session_state["skills_gap"] = gap
                    st.session_state.pop("cover_letter", None)
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Skills gap failed: {exc}")
            if c_cover.button("Draft cover letter (Ollama)", type="secondary"):
                with st.spinner("Drafting cover letter locally via Ollama…"):
                    try:
                        letter = api_post(
                            f"/jobs/matches/{int(run_id)}/{selected_match_id}/cover-letter"
                        ).json()
                        st.session_state["cover_letter"] = letter
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Cover letter failed: {exc}")
            gap = st.session_state.get("skills_gap")
            if gap and gap.get("match_id") == selected_match_id:
                st.subheader("Skills gap")
                st.write(
                    f"**Matched ({gap.get('overlap_count', 0)}):** "
                    + (", ".join(gap.get("matched_skills") or []) or "—")
                )
                st.write(
                    f"**Missing ({gap.get('gap_count', 0)}):** "
                    + (", ".join(gap.get("missing_skills") or []) or "—")
                )
                for tip in gap.get("tips") or []:
                    st.caption(f"• {tip}")
                st.caption("Draft tools only — CareerPilot never auto-applies.")
            letter = st.session_state.get("cover_letter")
            if letter and letter.get("match_id") == selected_match_id:
                st.subheader("Cover letter draft")
                st.info(letter.get("disclaimer") or "Draft only — review before sending.")
                st.text_area(
                    "Draft",
                    value=letter.get("draft") or "",
                    height=280,
                    label_visibility="collapsed",
                )
    else:
        st.caption(
            "This run has no match_id fields (older data). Re-run the pipeline to enable "
            "skills gap / cover letter."
        )

    for m in matches:
        with st.container(border=True):
            score = int(m.get("match_score") or 0)
            weak = score < threshold
            head = f"{m['title']} — {m['company']}  ·  Match {score}%"
            if weak:
                head += "  ·  low match"
            st.subheader(head)
            posted_label = _format_posted_ago(m.get("posted_at"))
            sh = m.get("still_hiring")
            sh_label = m.get("still_hiring_label") or ""
            if sh == "likely":
                sh_bit = f" · **{sh_label}**"
            elif sh == "unknown":
                sh_bit = " · Date unknown (not marked still hiring)"
            elif sh == "stale":
                sh_bit = f" · {sh_label}"
            else:
                sh_bit = ""
            st.caption(
                f"{m['recommendation']} · {m.get('experience') or 'Level N/A'} · "
                f"{m.get('location') or 'Location N/A'} · source: {m.get('source', '—')}"
                + (f" · {posted_label}" if posted_label else "")
                + sh_bit
            )
            cols = st.columns(2)
            matched = ", ".join(m.get("matched_skills", [])) or "-"
            missing = ", ".join(m.get("missing_skills", [])) or "-"
            cols[0].write(f"**Matched skills:** {matched}")
            cols[1].write(f"**Missing technical skills:** {missing}")
            if m.get("reasons"):
                st.write("\n".join(f"- {r}" for r in m["reasons"]))
            apply_url = (m.get("apply_url") or "").strip()
            if not apply_url:
                from urllib.parse import quote_plus

                q = quote_plus(
                    f"{m.get('title', '')} {m.get('company', '')} job apply".strip()
                )
                apply_url = f"https://www.google.com/search?q={q}"
            st.markdown(f"[Apply here]({apply_url})")


def page_logs() -> None:
    st.header("Logs")
    st.caption(
        "Per-run scrape diagnostics: jobs per website, empty boards, and access errors. "
        "Use this to see why Results may show only one source (e.g. weworkremotely)."
    )
    resp = api_get("/pipeline/runs")
    if resp.status_code != 200:
        st.error("Could not load logs.")
        return
    runs = resp.json().get("runs", [])
    if not runs:
        st.info("No pipeline runs yet.")
        return

    display_rows = []
    for run in runs:
        summary = run.get("summary") or {}
        scrape = summary.get("scrape") or {}
        excl = summary.get("filter_exclusions") or {}
        excl_bits = [f"{k}:{v}" for k, v in sorted(excl.items()) if v]
        errors = scrape.get("sources_error") or []
        empty = scrape.get("sources_empty") or []
        display_rows.append(
            {
                "id": run.get("id"),
                "status": run.get("status"),
                "scraped": run.get("jobs_scraped"),
                "matched": run.get("jobs_matched"),
                "min_%": summary.get("min_match_score"),
                "sources_ok": ", ".join(scrape.get("sources_with_jobs") or []) or "-",
                "sources_empty": len(empty),
                "sources_error": len(errors),
                "location": summary.get("location") or "",
                "exclusions": "; ".join(excl_bits) if excl_bits else "",
                "started_at": run.get("started_at"),
                "finished_at": run.get("finished_at"),
            }
        )
    st.dataframe(display_rows, use_container_width=True)

    st.subheader("Run detail")
    run_ids = [r.get("id") for r in runs if r.get("id") is not None]
    selected = st.selectbox(
        "Inspect run",
        run_ids,
        format_func=lambda i: f"Run #{i}",
    )
    run = next((r for r in runs if r.get("id") == selected), None)
    if not run:
        return

    summary = run.get("summary") or {}
    scrape = summary.get("scrape") or {}
    per = scrape.get("per_source") or []

    c1, c2, c3 = st.columns(3)
    c1.metric("Scraped", run.get("jobs_scraped") or 0)
    c2.metric("Matched", run.get("jobs_matched") or 0)
    c3.metric("Min match %", summary.get("min_match_score") or "-")

    if scrape.get("sources_error"):
        st.error(
            "Could not access / scrape failed: " + ", ".join(scrape["sources_error"])
        )
    if scrape.get("sources_empty"):
        st.warning(
            "Returned 0 jobs (blocked, no listings, or filtered out at source): "
            + ", ".join(scrape["sources_empty"])
        )
    if scrape.get("sources_skipped"):
        st.info(
            "Skipped (not in allowlist/defaults): "
            + ", ".join(scrape["sources_skipped"])
        )
    if scrape.get("sources_with_jobs"):
        st.success(
            "Sources that contributed jobs: "
            + ", ".join(scrape["sources_with_jobs"])
        )

    if per:
        st.markdown("**Per-website scrape**")
        st.dataframe(
            [
                {
                    "source": row.get("id"),
                    "status": row.get("status"),
                    "requested": row.get("requested"),
                    "returned": row.get("returned"),
                    "kept_after_recency": row.get("kept_after_recency"),
                    "detail": row.get("detail") or "",
                    "sample_titles": "; ".join(row.get("sample_titles") or []),
                }
                for row in per
            ],
            use_container_width=True,
        )
    else:
        st.info(
            "No per-source breakdown for this run (older runs before Logs upgrade). "
            "Re-run the pipeline to capture website-level stats."
        )

    excl = summary.get("filter_exclusions") or {}
    if excl:
        st.markdown("**Filter exclusions**")
        st.json(excl)

    if run.get("errors"):
        st.markdown("**Run errors**")
        st.warning("\n".join(run["errors"]))


def main() -> None:
    st.sidebar.title("CareerPilot AI")
    page = st.sidebar.radio(
        "Navigate",
        ["Setup", "Profile", "Run Pipeline", "Results", "Logs"],
    )
    st.sidebar.markdown(
        "**Quick start**\n"
        "1. Setup - check Ollama + **How to connect**\n"
        "2. Profile - upload, notifications, save\n"
        "3. Run Pipeline\n"
        "4. Results - matches + apply links"
    )

    {
        "Setup": page_setup,
        "Profile": page_profile,
        "Run Pipeline": page_run,
        "Results": page_results,
        "Logs": page_logs,
    }[page]()


if __name__ == "__main__":
    main()
