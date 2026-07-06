"""CareerPilot AI — Streamlit dashboard.

A thin client over the FastAPI backend. Run the API first, then:

    streamlit run ui/streamlit_app.py
"""

from __future__ import annotations

import os
import time
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
        col1, col2 = st.columns(2)
        col1.metric("Name", profile.get("name") or "—")
        col2.metric("Role", profile.get("role") or "—")
        st.write("**Skills:** " + ", ".join(profile.get("skills", [])) or "—")
        st.write("**Preferred roles:** " + ", ".join(profile.get("preferred_roles", [])))
        with st.expander("Full parsed JSON"):
            st.json(profile)


def page_run() -> None:
    st.header("Run Pipeline")
    profile_id = st.session_state.get("profile_id")
    if not profile_id:
        st.info("Upload a resume on the Profile page first.")
        return

    col1, col2, col3 = st.columns(3)
    top_n = col1.number_input("Top N jobs", 1, 20, 5)
    source = col2.selectbox("Job source", ["remotive", "wellfound"])
    scrape_limit = col3.number_input("Scrape limit", 10, 300, 100, step=10)
    exclude_internships = st.checkbox("Exclude internships", value=False)

    if st.button("Run pipeline", type="primary"):
        resp = api_post(
            "/pipeline/run",
            json={
                "profile_id": profile_id,
                "top_n": int(top_n),
                "source": source,
                "scrape_limit": int(scrape_limit),
                "exclude_internships": exclude_internships,
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


def page_results() -> None:
    st.header("Results")
    run_id = st.session_state.get("run_id")
    run_id = st.number_input("Run ID", 1, value=int(run_id) if run_id else 1)

    if st.button("Load matches", type="primary") or run_id:
        resp = api_get(f"/jobs/matches/{int(run_id)}", params={"top_n": 20})
        if resp.status_code != 200:
            st.error("Could not load matches.")
            return
        matches = resp.json().get("matches", [])
        if not matches:
            st.info("No matches for this run yet.")
            return
        for m in matches:
            with st.container(border=True):
                head = f"{m['title']} — {m['company']}  ·  Match {m['match_score']}%"
                st.subheader(head)
                st.caption(f"{m['recommendation']} · {m.get('location') or 'Location N/A'}")
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
