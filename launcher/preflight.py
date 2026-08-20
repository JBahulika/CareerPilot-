"""Preflight checks for CareerPilot launcher (Phase 10b)."""

from __future__ import annotations

import importlib.util
import shutil
import socket
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx


@dataclass
class CheckResult:
    ok: bool
    title: str
    detail: str
    hint: str = ""


@dataclass
class PreflightReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.ok]


def _port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_python(min_major: int = 3, min_minor: int = 10) -> CheckResult:
    v = sys.version_info
    if (v.major, v.minor) < (min_major, min_minor):
        return CheckResult(
            False,
            "Python version",
            f"Found {v.major}.{v.minor}.{v.micro}",
            f"Install Python {min_major}.{min_minor}+ (64-bit) from https://www.python.org/",
        )
    return CheckResult(True, "Python version", f"{v.major}.{v.minor}.{v.micro}")


def check_project_root(root: Path) -> CheckResult:
    if not (root / "main.py").is_file() or not (root / "ui" / "streamlit_app.py").is_file():
        return CheckResult(
            False,
            "Project files",
            f"Could not find main.py / ui/streamlit_app.py under {root}",
            "Run the launcher from the CareerPilot repo root.",
        )
    return CheckResult(True, "Project files", str(root))


def check_venv_hint(root: Path) -> CheckResult:
    """Soft check — warn if no .venv, but don't fail (user may use global/cenv)."""
    venv = root / ".venv"
    if venv.is_dir():
        return CheckResult(True, "Virtualenv", f"Found {venv}")
    return CheckResult(
        True,
        "Virtualenv",
        "No .venv folder (ok if using another environment)",
        "Recommended: python -m venv .venv && .venv\\Scripts\\activate && pip install -r requirements.txt",
    )


def check_dependencies() -> CheckResult:
    missing = []
    for mod in ("fastapi", "uvicorn", "streamlit", "httpx", "sqlmodel"):
        if importlib.util.find_spec(mod) is None:
            missing.append(mod)
    if missing:
        return CheckResult(
            False,
            "Python packages",
            "Missing: " + ", ".join(missing),
            "Activate your venv and run: pip install -r requirements.txt",
        )
    return CheckResult(True, "Python packages", "Core imports OK")


def check_ollama_cli() -> CheckResult:
    path = shutil.which("ollama")
    if not path:
        return CheckResult(
            False,
            "Ollama CLI",
            "ollama not found on PATH",
            "Install from https://ollama.com and reopen this window (or add Ollama to PATH).",
        )
    return CheckResult(True, "Ollama CLI", path)


def check_ollama_api(base_url: str) -> CheckResult:
    url = (base_url or "http://localhost:11434").rstrip("/") + "/api/tags"
    try:
        resp = httpx.get(url, timeout=2.0)
        if resp.status_code == 200:
            return CheckResult(True, "Ollama API", f"Reachable at {base_url}")
        return CheckResult(
            False,
            "Ollama API",
            f"HTTP {resp.status_code} from {url}",
            "Start Ollama (open the Ollama app or run: ollama serve)",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            False,
            "Ollama API",
            f"Not reachable at {base_url} ({exc})",
            "Install/start Ollama: https://ollama.com — then retry. "
            "The launcher can try `ollama serve` for you.",
        )


def check_port(port: int, label: str, *, require_free: bool = True) -> CheckResult:
    in_use = _port_open("127.0.0.1", port)
    if require_free and in_use:
        return CheckResult(
            False,
            f"Port {port} ({label})",
            "Already in use",
            f"Stop the other app using port {port}, or change the port in `.env`.",
        )
    if not require_free and in_use:
        return CheckResult(True, f"Port {port} ({label})", "Already listening (will reuse)")
    return CheckResult(True, f"Port {port} ({label})", "Free")


def list_ollama_models(base_url: str) -> list[str]:
    url = (base_url or "http://localhost:11434").rstrip("/") + "/api/tags"
    try:
        resp = httpx.get(url, timeout=5.0)
        resp.raise_for_status()
        models = resp.json().get("models") or []
        names = []
        for m in models:
            name = m.get("name") or m.get("model")
            if name:
                names.append(str(name))
        return sorted(set(names))
    except Exception:
        return []


def parse_host_port(url: str, default_port: int) -> tuple[str, int]:
    parsed = urlparse(url if "://" in url else f"http://{url}")
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or default_port
    return host, port


def run_preflight(
    root: Path,
    *,
    ollama_base_url: str = "http://localhost:11434",
    api_port: int = 8000,
    streamlit_port: int = 8501,
    require_ollama_api: bool = False,
) -> PreflightReport:
    """Collect checks. ``require_ollama_api`` False allows starting serve later."""
    report = PreflightReport()
    report.checks.append(check_python())
    report.checks.append(check_project_root(root))
    report.checks.append(check_venv_hint(root))
    report.checks.append(check_dependencies())
    report.checks.append(check_ollama_cli())
    api_check = check_ollama_api(ollama_base_url)
    if require_ollama_api:
        report.checks.append(api_check)
    else:
        # Soft: record as OK with note if down — launcher will try serve
        if api_check.ok:
            report.checks.append(api_check)
        else:
            report.checks.append(
                CheckResult(
                    True,
                    "Ollama API",
                    api_check.detail + " (will try to start)",
                    api_check.hint,
                )
            )
    # If something already serves these ports, we may reuse — warn only for API start conflict
    report.checks.append(check_port(api_port, "FastAPI", require_free=False))
    report.checks.append(check_port(streamlit_port, "Streamlit", require_free=False))
    return report
