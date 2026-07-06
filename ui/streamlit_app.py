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


def _api_reachable() -> bool:
    try:
        return api_get("/health").status_code == 200
    except Exception:
        return False


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

    st.subheader("Daily auto-update")
    try:
        sched = api_get("/scheduler/status").json()
        if sched.get("running"):
            st.success(
                f"Morning scan enabled — next run: {sched.get('next_run') or 'scheduled'}"
            )
        elif sched.get("enabled"):
            st.info("Daily scan is enabled but scheduler is not running. Restart the API.")
        else:
            st.warning("Daily scan disabled. Set DAILY_SCAN_ENABLED=true in .env")

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
            st.code("ollama serve\nollama pull " + status.get("model", "qwen2.5:7b"))
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not check Ollama status: {exc}")


def page_profile() -> None:
    st.header("Profile")
    st.caption("Upload your master resume (PDF). It is parsed locally and never leaves your machine.")

    uploaded = st.file_uploader("Master resume (PDF)", type=["pdf"])
    if uploaded is not None and st.button("Parse resume", type="primary"):
        with st.spinner("Parsing resume with the local LLM..."):
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
        st.success(f"Parsed profile (id {data['profile_id']}).")

    profile = st.session_state.get("profile")
    if profile is None:
        try:
            latest = api_get("/resume/latest")
            if latest.status_code == 200:
                data = latest.json()
                st.session_state["profile_id"] = data["profile_id"]
                st.session_state["profile"] = data["profile"]
                profile = data["profile"]
        except Exception:
            pass

    if profile:
        st.subheader("Parsed profile")
        col1, col2, col3 = st.columns(3)
        col1.metric("Name", profile.get("name") or "—")
        col2.metric("Role", profile.get("role") or "—")
        col3.metric("Experience", profile.get("experience_level") or "—")

        current_level = profile.get("experience_level") or "Fresher"
        if current_level not in EXPERIENCE_LEVEL_OPTIONS:
            EXPERIENCE_LEVEL_OPTIONS_WITH_CURRENT = [current_level, *EXPERIENCE_LEVEL_OPTIONS]
        else:
            EXPERIENCE_LEVEL_OPTIONS_WITH_CURRENT = EXPERIENCE_LEVEL_OPTIONS

        selected_level = st.selectbox(
            "Experience level (edit if the parser got it wrong)",
            EXPERIENCE_LEVEL_OPTIONS_WITH_CURRENT,
            index=EXPERIENCE_LEVEL_OPTIONS_WITH_CURRENT.index(current_level),
        )
        if selected_level != current_level and st.button("Save experience level"):
            profile["experience_level"] = selected_level
            profile_id = st.session_state.get("profile_id")
            resp = api_put(f"/resume/{profile_id}", json=profile)
            if resp.status_code == 200:
                data = resp.json()
                st.session_state["profile_id"] = data["profile_id"]
                st.session_state["profile"] = data["profile"]
                st.success(f"Updated experience level to '{selected_level}'.")
            else:
                st.error(resp.json().get("detail", "Could not save profile."))

        st.write("**Skills:** " + ", ".join(profile.get("skills", [])) or "—")
        st.write("**Preferred roles:** " + ", ".join(profile.get("preferred_roles", [])))

        st.subheader("Location preferences")
        default_loc = profile.get("preferred_location") or profile.get("location") or ""
        preferred_loc = st.text_input(
            "Preferred location",
            value=default_loc,
            placeholder="e.g. Bangalore, Remote, New York",
        )
        include_remote_profile = st.checkbox(
            "Include remote jobs",
            value=profile.get("include_remote", True),
        )
        if st.button("Save location preferences"):
            profile["preferred_location"] = preferred_loc.strip()
            profile["include_remote"] = include_remote_profile
            profile_id = st.session_state.get("profile_id")
            resp = api_put(f"/resume/{profile_id}", json=profile)
            if resp.status_code == 200:
                data = resp.json()
                st.session_state["profile_id"] = data["profile_id"]
                st.session_state["profile"] = data["profile"]
                st.success("Saved location preferences.")
            else:
                st.error(resp.json().get("detail", "Could not save profile."))

        st.subheader("Experience range (flexible matching)")
        exp_col1, exp_col2, exp_col3 = st.columns(3)
        ymin = exp_col1.number_input(
            "Min years target",
            0,
            20,
            int(profile.get("target_years_min") or 0),
        )
        ymax = exp_col2.number_input(
            "Max years target",
            0,
            20,
            int(profile.get("target_years_max") or 2),
        )
        st.caption(
            "Jobs within this range (plus flexibility below) will be included. "
            "Set 0–2 for entry level, 2–5 for mid, etc."
        )
        if st.button("Save experience range"):
            profile["target_years_min"] = int(ymin)
            profile["target_years_max"] = int(ymax)
            profile_id = st.session_state.get("profile_id")
            resp = api_put(f"/resume/{profile_id}", json=profile)
            if resp.status_code == 200:
                data = resp.json()
                st.session_state["profile_id"] = data["profile_id"]
                st.session_state["profile"] = data["profile"]
                st.success(f"Saved target range {ymin}-{ymax} years.")
            else:
                st.error(resp.json().get("detail", "Could not save profile."))

        with st.expander("Full parsed JSON"):
            st.json(profile)


def page_run() -> None:
    st.header("Run Pipeline")
    profile_id = st.session_state.get("profile_id")
    if not profile_id:
        st.info("Upload a resume on the Profile page first.")
        return

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
    top_n = col1.number_input("Top N jobs", 1, 15, 10)
    source = col2.selectbox(
        "Job source",
        source_options,
        index=source_options.index("all") if "all" in source_options else 0,
        format_func=lambda x: source_labels.get(x, x),
    )
    scrape_limit = col3.number_input("Scrape limit", 10, 300, 100, step=10)

    profile = st.session_state.get("profile") or {}
    default_run_loc = profile.get("preferred_location") or profile.get("location") or ""
    loc_col1, loc_col2 = st.columns(2)
    run_location = loc_col1.text_input(
        "Location (override for this run)",
        value=default_run_loc,
        placeholder="Leave as-is to use profile location",
    )
    include_remote = loc_col2.checkbox(
        "Include remote jobs",
        value=profile.get("include_remote", True),
    )

    exclude_internships = st.checkbox("Exclude internships", value=False)
    strict_experience = st.checkbox("Strict experience matching", value=True)
    allow_stretch = st.checkbox("Include stretch roles", value=True)
    flex_years = st.slider("Experience flexibility (+/- years)", 0, 5, 2)

    with st.expander("Supported job boards"):
        for sid in source_options:
            if sid == "all":
                continue
            st.write(f"- **{source_labels.get(sid, sid)}**")

    if st.button("Run pipeline", type="primary"):
        resp = api_post(
            "/pipeline/run",
            json={
                "profile_id": profile_id,
                "top_n": int(top_n),
                "source": source,
                "scrape_limit": int(scrape_limit),
                "exclude_internships": exclude_internships,
                "strict_experience": strict_experience,
                "allow_stretch": allow_stretch,
                "flex_years": int(flex_years),
            },
        )
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

    for _ in range(600):  # up to ~10 minutes
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
            cols[0].write("**Matched:** " + ", ".join(m.get("matched_skills", [])))
            cols[1].write("**Missing:** " + ", ".join(m.get("missing_skills", [])))
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


# --- App shell ---------------------------------------------------------------
def main() -> None:
    st.sidebar.title("🧭 CareerPilot AI")
    page = st.sidebar.radio(
        "Navigate",
        ["Setup", "Profile", "Run Pipeline", "Results", "History"],
    )
    st.sidebar.caption("Local-first autonomous job application assistant.")

    {
        "Setup": page_setup,
        "Profile": page_profile,
        "Run Pipeline": page_run,
        "Results": page_results,
        "History": page_history,
    }[page]()


if __name__ == "__main__":
    main()
