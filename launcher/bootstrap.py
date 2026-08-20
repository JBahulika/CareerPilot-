"""First-run bootstrap for CareerPilot (venv + deps + .env).

Used by ``start_careerpilot.bat`` / ``CareerPilot.exe`` so a fresh GitHub
download can self-setup without manual terminal steps.

Honest limit: a tiny ``.exe`` cannot ship multi‑GB PyTorch + Ollama. Users need
**Python 3.10+** and **Ollama** installed once on the machine; this bootstrap
creates the venv, installs project deps, copies ``.env``, and starts the app.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path


def project_root() -> Path:
    # Frozen exe: live next to CareerPilot.exe (repo / release folder)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def venv_python(root: Path) -> Path:
    if sys.platform.startswith("win"):
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def find_system_python() -> str | None:
    """Locate a real CPython usable to create ``.venv`` (not a frozen exe)."""
    if not getattr(sys, "frozen", False) and sys.executable:
        # Prefer the interpreter that launched bootstrap (bat / python -m)
        ver = sys.version_info
        if ver.major == 3 and ver.minor >= 10:
            return sys.executable

    candidates: list[str] = []
    if sys.platform.startswith("win"):
        py_launcher = shutil.which("py")
        if py_launcher:
            for args in (["-3.12"], ["-3.11"], ["-3.10"], ["-3"]):
                try:
                    out = subprocess.check_output(
                        [py_launcher, *args, "-c", "import sys; print(sys.executable)"],
                        text=True,
                        stderr=subprocess.DEVNULL,
                        timeout=15,
                    ).strip()
                    if out and Path(out).is_file():
                        candidates.append(out)
                        break
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
                    continue
    for name in ("python3.12", "python3.11", "python3.10", "python3", "python"):
        found = shutil.which(name)
        if found:
            candidates.append(found)

    for cand in candidates:
        try:
            out = subprocess.check_output(
                [cand, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=15,
            ).strip()
            major_s, _, minor_s = out.partition(".")
            if int(major_s) == 3 and int(minor_s) >= 10:
                return cand
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError):
            continue
    return None


def open_url(url: str) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(url)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", url])
        else:
            subprocess.Popen(["xdg-open", url])
    except Exception:
        print(f"Open manually: {url}")


def ensure_venv(root: Path, base_python: str | None = None) -> Path:
    """Create ``.venv`` if missing; return path to venv python."""
    py = venv_python(root)
    if py.is_file():
        print(f"Virtualenv OK: {py}")
        return py

    creator = base_python or find_system_python()
    if not creator:
        print()
        print("ERROR: Python 3.10+ is required once to set up CareerPilot.")
        print("Install from https://www.python.org/downloads/ (Add to PATH), then re-run.")
        open_url("https://www.python.org/downloads/")
        raise RuntimeError("No Python 3.10+ found on PATH")

    print(f"Creating virtual environment (.venv) with {creator} — first run only…")
    # Prefer ``python -m venv`` so frozen CareerPilot.exe can still seed a real venv
    try:
        subprocess.check_call([creator, "-m", "venv", str(root / ".venv")], cwd=str(root))
    except subprocess.CalledProcessError:
        # Fallback: EnvBuilder only works when *this* process is real CPython
        if getattr(sys, "frozen", False):
            raise RuntimeError(
                f"Could not create .venv with {creator}. "
                "Reinstall Python 3.10+ with 'Add to PATH' checked."
            ) from None
        builder = venv.EnvBuilder(with_pip=True, clear=False, upgrade=False)
        builder.create(root / ".venv")

    if not py.is_file():
        raise RuntimeError(f"venv created but python missing at {py}")
    print(f"Virtualenv created: {py}")
    return py


def ensure_deps(venv_py: Path, root: Path) -> None:
    """pip install -r requirements.txt into the venv if imports fail."""
    req = root / "requirements.txt"
    marker = root / ".venv" / ".careerpilot_deps_ok"

    def _imports_ok() -> bool:
        code = "import fastapi, uvicorn, streamlit, httpx, sqlmodel"
        r = subprocess.run(
            [str(venv_py), "-c", code],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        return r.returncode == 0

    if marker.is_file() and _imports_ok():
        print("Dependencies OK.")
        return

    if not req.is_file():
        raise RuntimeError(
            f"Missing {req}. Put CareerPilot.exe next to the full project "
            "(or unzip the GitHub release / clone), then re-run."
        )

    print()
    print("Installing dependencies (first run can take several minutes)…")
    print("  This downloads packages including ML libs — please wait.")
    print()
    subprocess.check_call(
        [str(venv_py), "-m", "pip", "install", "--upgrade", "pip"],
        cwd=str(root),
    )
    subprocess.check_call(
        [str(venv_py), "-m", "pip", "install", "-r", str(req)],
        cwd=str(root),
    )
    if not _imports_ok():
        raise RuntimeError(
            "Dependencies installed but core imports still fail. "
            "Try: .venv\\Scripts\\python -m pip install -r requirements.txt"
        )
    marker.write_text("ok\n", encoding="utf-8")
    print("Dependencies installed.")


def ensure_env_file(root: Path) -> None:
    env_path = root / ".env"
    example = root / ".env.example"
    if env_path.is_file():
        return
    if example.is_file():
        print("Creating .env from .env.example")
        env_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        env_path.write_text("OLLAMA_MODEL=qwen2.5:7b\nAPI_PORT=8000\n", encoding="utf-8")
        print("Created minimal .env")


def run_bootstrap(base_python: str | None = None) -> Path:
    """Ensure venv + deps + .env. Returns venv python path."""
    root = project_root()
    os.chdir(root)
    print(f"Project: {root}")
    ensure_env_file(root)
    venv_py = ensure_venv(root, base_python=base_python)
    ensure_deps(venv_py, root)
    return venv_py


def main(argv: list[str] | None = None) -> int:
    """CLI: bootstrap then exec launcher.main (model picker by default).

    Pass ``--auto`` / ``--yes`` for non-interactive starts (CI / scripted).
    """
    argv = list(argv or sys.argv[1:])
    try:
        venv_py = run_bootstrap()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR during setup: {exc}")
        return 1

    # Re-launch main with the venv interpreter (never run FastAPI from the frozen exe).
    # Default: interactive model picker. Only skip prompts when caller passes --auto/--yes.
    cmd = [str(venv_py), "-m", "launcher.main", *argv]
    print("Launching CareerPilot…")
    return subprocess.call(cmd, cwd=str(project_root()))


if __name__ == "__main__":
    raise SystemExit(main())
