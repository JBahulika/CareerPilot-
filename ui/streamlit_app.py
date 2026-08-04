"""CareerPilot AI — Streamlit dashboard.

A thin client over the FastAPI backend. Run the API first, then:

    streamlit run ui/streamlit_app.py
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path

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

    st.subheader("Morning auto-update (9 AM)")
    st.markdown(
        "Each morning the pipeline scrapes **fresh jobs** (last 2 days), "
        "matches them to your profile, generates tailored resumes, and writes a "
        "digest to `logs/notifications/`. When WhatsApp is configured, the same "
        "digest is sent to your phone."
    )
    try:
        sched = api_get("/scheduler/status").json()
        if sched.get("running"):
            st.success(
                f"Next scan: **{sched.get('next_run') or 'scheduled'}** "
                f"(jobs from last {sched.get('recent_days', 2)} days)"
            )
        elif sched.get("enabled"):
            st.info("Daily scan enabled — restart the API to activate the scheduler.")
        else:
            st.warning("Daily scan disabled. Set `DAILY_SCAN_ENABLED=true` in `.env`.")

        col1, col2 = st.columns(2)
        col1.metric("Notifier", sched.get("notifier_backend", "local"))
        wa_status = "Ready" if sched.get("whatsapp_configured") else "Not configured"
        col2.metric("WhatsApp", wa_status)

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
        with st.spinner("Parsing resume locally..."):
            try:
                resp = api_post(
                    "/resume/upload",
                    files={"file": (uploaded.name, uploaded.getvalue(), "application/pdf")},
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"Upload failed: {exc}")
                return
        if resp.status_code != 200:
            st.error(resp.json().get("detail", "Parsing failed."))
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
        help="Only jobs at or above this score are tailored and included in digests. Default 60.",
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
        profile["enabled_sources"] = list(enabled_sources)
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
rank matches → generate tailored PDF resumes.

Settings come from your **Profile** (experience, location, strict/stretch rules).
        """
    )

    loc = profile.get("preferred_location") or profile.get("location") or "Any"
    remote = "yes" if profile.get("include_remote", True) else "no"
    saved_threshold = int(
        profile.get("min_match_score") if profile.get("min_match_score") is not None else 60
    )
    st.info(
        f"Using profile: **{profile.get('target_years_min', 0)}-"
        f"{profile.get('target_years_max', 1)} yrs** "
        f"({profile.get('experience_level') or '-'}) | "
        f"roles: {', '.join(profile.get('preferred_roles', [])[:3]) or profile.get('role', '—')} · "
        f"location: **{loc}** · remote: **{remote}** · "
        f"min match: **{saved_threshold}%** · "
        f"strict: **{'on' if profile.get('strict_experience', True) else 'off'}** · "
        f"stretch: **{'on' if profile.get('allow_stretch') else 'off'}**"
    )

    try:
        sources_resp = api_get("/jobs/sources").json()
        allowed = set(profile.get("enabled_sources") or [])
        raw_sources = sources_resp.get("sources", [])
        source_options = []
        for s in raw_sources:
            sid = s["id"]
            if sid == "all":
                source_options.append(sid)
                continue
            if allowed:
                if sid in allowed:
                    source_options.append(sid)
            elif s.get("enabled_by_default", True):
                source_options.append(sid)
        # Always allow explicit picks of any board (advanced)
        for s in raw_sources:
            if s["id"] not in source_options:
                source_options.append(s["id"])
        source_labels = {
            s["id"]: (
                f"{s['name']} ({s.get('method')}/{s.get('safety', '?')})"
                + ("" if s.get("enabled_by_default", True) else " [off by default]")
            )
            for s in raw_sources
        }
    except Exception:
        source_options = ["all", "remotive", "themuse", "weworkremotely"]
        source_labels = {s: s for s in source_options}

    col1, col2, col3 = st.columns(3)
    top_n = col1.number_input("Top N to tailor", 1, 15, 10)
    source = col2.selectbox(
        "Job source",
        source_options,
        index=source_options.index("all") if "all" in source_options else 0,
        format_func=lambda x: source_labels.get(x, x),
    )
    scrape_limit = col3.number_input(
        f"Max jobs to scrape (up to {SCRAPE_LIMIT_MAX})",
        min_value=10,
        max_value=SCRAPE_LIMIT_MAX,
        value=100,
        step=50,
        help=(
            f"Total cap after Aggregate (max {SCRAPE_LIMIT_MAX}). Split across "
            "enabled boards as max(10, limit / boards). "
            "Example: 1300 with 13 boards ~ 100 each."
        ),
    )
    if source == "all":
        enabled = profile.get("enabled_sources") or []
        n_boards = len(enabled) if enabled else 13
        per = max(10, int(scrape_limit) // max(n_boards, 1))
        warn = ""
        if int(scrape_limit) >= 800:
            warn = " High values with Playwright boards can be slow."
        st.caption(
            f"Aggregate ~ **{per}** jobs asked per board "
            f"({n_boards} boards"
            + (" from your allowlist" if enabled else " ~ default-on sources")
            + f").{warn}"
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
            "source": source,
            "scrape_limit": int(scrape_limit),
            "exclude_internships": profile.get("exclude_internships", False),
            "strict_experience": profile.get("strict_experience", True),
            "allow_stretch": profile.get("allow_stretch", False),
            "flex_years": profile.get("flex_years"),
            "include_remote": bool(run_include_remote),
            "recent_days": int(recent_days),
            "min_match_score": int(run_min_match),
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
    steps = {"scrape": 0.2, "filter": 0.4, "match": 0.6, "tailor": 0.85, "complete": 1.0}

    for _ in range(600):
        run = api_get(f"/pipeline/runs/{run_id}").json()
        step = run.get("current_step", "")
        progress.progress(steps.get(step, 0.05))
        status_box.info(
            f"Status: {run['status']} | step: {step or 'starting'} | "
            f"scraped {run['jobs_scraped']} | matched {run['jobs_matched']} | "
            f"pdfs {run['pdfs_generated']}"
        )
        if run["status"] in ("completed", "failed"):
            progress.progress(1.0)
            if run["status"] == "completed":
                st.success("Pipeline complete. See the Results page.")
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
    if summary:
        excl = summary.get("filter_exclusions") or {}
        excl_bits = [f"{k.replace('_', ' ')}: {v}" for k, v in sorted(excl.items()) if v]
        st.info(
            f"Min match **{summary.get('min_match_score', '—')}%** · "
            f"location **{summary.get('location') or 'Any'}** · "
            f"remote **{'on' if summary.get('include_remote', True) else 'off'}**"
            + (f" · exclusions — {'; '.join(excl_bits)}" if excl_bits else "")
        )

    page_size = st.selectbox("Jobs per page", [10, 15], index=0)
    if "results_page" not in st.session_state:
        st.session_state["results_page"] = 1

    nav1, nav2, nav3 = st.columns([1, 2, 1])
    if nav1.button("Previous", disabled=st.session_state["results_page"] <= 1):
        st.session_state["results_page"] = max(1, st.session_state["results_page"] - 1)
    if nav3.button("Next"):
        st.session_state["results_page"] += 1

    page = st.session_state["results_page"]
    resp = api_get(
        f"/jobs/matches/{int(run_id)}",
        params={"page": page, "page_size": page_size},
    )
    if resp.status_code != 200:
        st.error("Could not load matches.")
        return

    data = resp.json()
    matches = data.get("matches", [])
    total = data.get("total", 0)
    total_pages = data.get("total_pages", 1)

    if page > total_pages and total > 0:
        st.session_state["results_page"] = total_pages
        st.rerun()

    nav2.caption(f"Page {page} of {total_pages} · {total} jobs total")

    if not matches:
        st.info("No matches for this run yet (none passed filters and min match score).")
        return

    st.caption(
        "Missing technical skills = tools, stacks, protocols, certs - "
        "not soft skills or sales/process duties."
    )

    for m in matches:
        with st.container(border=True):
            head = f"{m['title']} — {m['company']}  ·  Match {m['match_score']}%"
            st.subheader(head)
            posted_label = _format_posted_ago(m.get("posted_at"))
            st.caption(
                f"{m['recommendation']} · {m.get('experience') or 'Level N/A'} · "
                f"{m.get('location') or 'Location N/A'} · source: {m.get('source', '—')}"
                + (f" · {posted_label}" if posted_label else "")
            )
            cols = st.columns(2)
            matched = ", ".join(m.get("matched_skills", [])) or "-"
            missing = ", ".join(m.get("missing_skills", [])) or "-"
            cols[0].write(f"**Matched skills:** {matched}")
            cols[1].write(f"**Missing technical skills:** {missing}")
            if m.get("reasons"):
                st.write("\n".join(f"- {r}" for r in m["reasons"]))
            if m.get("apply_url"):
                st.markdown(f"[Apply here]({m['apply_url']})")
            pdf_path = m.get("generated_pdf_path")
            if pdf_path and Path(pdf_path).exists():
                with open(pdf_path, "rb") as fh:
                    st.download_button(
                        "Download tailored resume",
                        data=fh.read(),
                        file_name=Path(pdf_path).name,
                        mime="application/pdf",
                        key=head,
                    )


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
                "pdfs": run.get("pdfs_generated"),
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

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Scraped", run.get("jobs_scraped") or 0)
    c2.metric("Matched", run.get("jobs_matched") or 0)
    c3.metric("PDFs", run.get("pdfs_generated") or 0)
    c4.metric("Min match %", summary.get("min_match_score") or "-")

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
        "1. Setup - check Ollama\n"
        "2. Profile - upload and save\n"
        "3. Run Pipeline\n"
        "4. Results - download PDFs"
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
