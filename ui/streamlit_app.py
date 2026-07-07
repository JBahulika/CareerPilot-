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

st.set_page_config(page_title="CareerPilot AI", page_icon="🧭", layout="wide")


def api_get(path: str, **kwargs):
    return httpx.get(f"{API_BASE_URL}{path}", timeout=60, **kwargs)


def api_post(path: str, **kwargs):
    return httpx.post(f"{API_BASE_URL}{path}", timeout=600, **kwargs)


def api_put(path: str, **kwargs):
    return httpx.put(f"{API_BASE_URL}{path}", timeout=60, **kwargs)


EXPERIENCE_LEVEL_OPTIONS = [
    "Fresher",
    "0-1 years",
    "1-3 years",
    "3-5 years",
    "5+ years",
]

_EXPERIENCE_YEAR_DEFAULTS = {
    "Fresher": (0, 0),
    "0-1 years": (0, 1),
    "1-3 years": (1, 3),
    "3-5 years": (3, 5),
    "5+ years": (5, 15),
}


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

    current_level = profile.get("experience_level") or "Fresher"
    level_options = (
        [current_level, *EXPERIENCE_LEVEL_OPTIONS]
        if current_level not in EXPERIENCE_LEVEL_OPTIONS
        else EXPERIENCE_LEVEL_OPTIONS
    )
    selected_level = st.selectbox(
        "Experience level",
        level_options,
        index=level_options.index(current_level),
        help="Used for seniority filtering. Pick what best matches your resume.",
    )
    defaults = _EXPERIENCE_YEAR_DEFAULTS.get(selected_level, (0, 2))
    exp_col1, exp_col2 = st.columns(2)
    ymin = exp_col1.number_input(
        "Target years (min)",
        0,
        20,
        int(profile.get("target_years_min") if profile.get("target_years_min") is not None else defaults[0]),
    )
    ymax = exp_col2.number_input(
        "Target years (max)",
        0,
        20,
        int(profile.get("target_years_max") if profile.get("target_years_max") is not None else defaults[1]),
    )
    st.caption(
        f"**{selected_level}** → target **{ymin}–{ymax} years**. "
        "Jobs outside this band are dropped unless stretch is enabled."
    )

    preferred_loc = st.text_input(
        "Preferred job location",
        value=profile.get("preferred_location") or profile.get("location") or "",
        placeholder="e.g. Bangalore, Mumbai, Remote",
        help="City or region. Remote jobs are included when the checkbox below is on.",
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

    if st.button("Save profile", type="primary"):
        profile["experience_level"] = selected_level
        profile["target_years_min"] = int(ymin)
        profile["target_years_max"] = int(ymax)
        profile["preferred_location"] = preferred_loc.strip()
        profile["include_remote"] = include_remote
        profile["strict_experience"] = strict_experience
        profile["allow_stretch"] = allow_stretch
        profile["flex_years"] = int(flex_years)
        profile["exclude_internships"] = exclude_internships
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
    st.info(
        f"Using profile: **{profile.get('experience_level')}** "
        f"({profile.get('target_years_min', 0)}–{profile.get('target_years_max', 1)} yrs) · "
        f"roles: {', '.join(profile.get('preferred_roles', [])[:3]) or profile.get('role', '—')} · "
        f"location: **{loc}** · remote: **{remote}** · "
        f"strict: **{'on' if profile.get('strict_experience', True) else 'off'}** · "
        f"stretch: **{'on' if profile.get('allow_stretch') else 'off'}**"
    )

    try:
        sources_resp = api_get("/jobs/sources").json()
        source_options = [s["id"] for s in sources_resp.get("sources", [])]
        source_labels = {
            s["id"]: f"{s['name']} ({s['method']})" for s in sources_resp.get("sources", [])
        }
    except Exception:
        source_options = ["all", "remotive", "wellfound", "indeed", "naukri"]
        source_labels = {s: s for s in source_options}

    col1, col2, col3 = st.columns(3)
    top_n = col1.number_input("Top N to tailor", 1, 15, 10)
    source = col2.selectbox(
        "Job source",
        source_options,
        index=source_options.index("all") if "all" in source_options else 0,
        format_func=lambda x: source_labels.get(x, x),
    )
    scrape_limit = col3.number_input("Max jobs to scrape", 10, 300, 100, step=10)

    with st.expander("Override for this run only (optional)"):
        run_location = st.text_input(
            "Location override",
            value="",
            placeholder="Leave blank to use profile location",
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
            "include_remote": profile.get("include_remote", True),
            "recent_days": int(recent_days),
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
        st.info("No matches for this run yet.")
        return

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
            cols[0].write("**Matched:** " + ", ".join(m.get("matched_skills", [])) or "—")
            cols[1].write("**Missing:** " + ", ".join(m.get("missing_skills", [])) or "—")
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


def page_history() -> None:
    st.header("History")
    resp = api_get("/pipeline/runs")
    if resp.status_code != 200:
        st.error("Could not load history.")
        return
    runs = resp.json().get("runs", [])
    if not runs:
        st.info("No pipeline runs yet.")
        return
    st.dataframe(runs, use_container_width=True)


def main() -> None:
    st.sidebar.title("🧭 CareerPilot AI")
    page = st.sidebar.radio(
        "Navigate",
        ["Setup", "Profile", "Run Pipeline", "Results", "History"],
    )
    st.sidebar.caption("Local-first job discovery & resume tailoring.")
    st.sidebar.markdown(
        "**Quick start**\n"
        "1. Setup — check Ollama\n"
        "2. Profile — upload & save\n"
        "3. Run Pipeline\n"
        "4. Results — download PDFs"
    )

    {
        "Setup": page_setup,
        "Profile": page_profile,
        "Run Pipeline": page_run,
        "Results": page_results,
        "History": page_history,
    }[page]()


if __name__ == "__main__":
    main()
