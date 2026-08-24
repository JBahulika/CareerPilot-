"""CareerPilot one-click launcher (Phase 10b).

Preflight → model picker (with hardware warnings) → start Ollama / API / Streamlit.

Never auto-applies. Never solves captchas.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# Allow `python -m launcher.main` and frozen CareerPilot.exe
def _detect_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


_ROOT = _detect_root()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from launcher.env_file import read_env_key, upsert_env_key
from launcher.hardware import (
    DEFAULT_MODEL,
    RECOMMENDED_MODELS,
    detect_hardware,
    model_warning,
)
from launcher.preflight import list_ollama_models, run_preflight

STREAMLIT_PORT = 8501
API_PORT_DEFAULT = 8000
# Everyday start: if the user does not pick a model, keep last .env choice
MODEL_PICK_TIMEOUT_S = 10.0


def _print_banner() -> None:
    print()
    print("=" * 60)
    print("  CareerPilot launcher")
    print("  Local job discovery - you choose what to apply to")
    print("  (never auto-applies / never solves captchas)")
    print("=" * 60)
    print()


def _readline_with_timeout(
    prompt: str,
    timeout_s: float,
    *,
    default: str = "",
    timeout_message: str | None = None,
) -> str | None:
    """Read a line from stdin; on idle timeout return ``default``.

    Returns ``None`` on EOF. If the user starts typing before the timeout,
    wait for Enter with no further deadline. ``timeout_s <= 0`` waits forever
    (same as ``input``).
    """
    print(prompt, end="", flush=True)
    if timeout_s is None or float(timeout_s) <= 0:
        try:
            return sys.stdin.readline().rstrip("\r\n")
        except EOFError:
            return None

    timeout_s = float(timeout_s)

    if sys.platform == "win32":
        import msvcrt

        buf: list[str] = []
        deadline = time.time() + timeout_s
        timed_out = False
        while True:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\r", "\n"):
                    print()
                    return "".join(buf)
                if ch == "\x03":
                    raise KeyboardInterrupt
                if ch in ("\x08", "\x7f"):  # backspace
                    if buf:
                        buf.pop()
                        sys.stdout.write("\b \b")
                        sys.stdout.flush()
                    continue
                # Ignore special keys (arrows etc. come as \x00 / \xe0 + next)
                if ch in ("\x00", "\xe0"):
                    if msvcrt.kbhit():
                        msvcrt.getwch()
                    continue
                if ch.isprintable():
                    buf.append(ch)
                    sys.stdout.write(ch)
                    sys.stdout.flush()
                    # User engaged — no more auto-timeout
                    deadline = None
                continue
            if deadline is not None and time.time() >= deadline:
                timed_out = True
                break
            time.sleep(0.05)
        print()
        if timed_out:
            if timeout_message:
                print(timeout_message)
            return default
        return "".join(buf)

    # POSIX: select on stdin
    import select

    ready, _, _ = select.select([sys.stdin], [], [], timeout_s)
    if not ready:
        print()
        if timeout_message:
            print(timeout_message)
        return default
    try:
        line = sys.stdin.readline()
    except EOFError:
        return None
    if line == "":
        return None
    return line.rstrip("\r\n")


def _load_dotenv_values(root: Path) -> dict[str, str]:
    env_path = root / ".env"
    values: dict[str, str] = {}
    if not env_path.is_file():
        example = root / ".env.example"
        if example.is_file():
            print("No .env found — copying .env.example → .env")
            env_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def _resolve_python(root: Path) -> str:
    candidates = [
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    return sys.executable


def _open_default_browser(url: str) -> None:
    """Open URL in the user's default browser (reliable on Windows)."""
    print(f"Opening default browser: {url}")
    try:
        if sys.platform.startswith("win"):
            # Shell http(s) association -> default browser
            os.startfile(url)  # type: ignore[attr-defined]
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", url])
            return
        opener = shutil.which("xdg-open")
        if opener:
            subprocess.Popen([opener, url])
            return
        webbrowser.open(url)
    except Exception as exc:  # noqa: BLE001
        try:
            webbrowser.open(url)
        except Exception:
            print(f"Could not open browser automatically ({exc}).")
            print(f"Open this URL manually: {url}")


def _wait_http(url: str, timeout_s: float = 45.0) -> bool:
    import httpx

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=1.5)
            if r.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(0.6)
    return False


def _ensure_ollama(base_url: str) -> bool:
    import httpx

    tags = base_url.rstrip("/") + "/api/tags"
    try:
        if httpx.get(tags, timeout=2.0).status_code == 200:
            print("Ollama already running.")
            return True
    except Exception:
        pass

    if not shutil.which("ollama"):
        print("ERROR: Ollama CLI not found. Install from https://ollama.com")
        return False

    print("Starting Ollama (`ollama serve`)…")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(_ROOT),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: could not start ollama serve: {exc}")
        print("Open the Ollama desktop app, then re-run this launcher.")
        return False

    if _wait_http(tags, timeout_s=30):
        print("Ollama is up.")
        return True
    print("ERROR: Ollama did not become reachable. Open the Ollama app and retry.")
    return False


def _pick_model(base_url: str, current: str) -> str:
    hw = detect_hardware()
    print("Hardware (best-effort):")
    print(f"  RAM:  {hw.ram_gb or '?'} GB")
    if hw.gpu_name:
        print(f"  GPU:  {hw.gpu_name} (~{hw.gpu_vram_gb} GB VRAM)")
    else:
        print("  GPU:  not detected via nvidia-smi")
    for note in hw.notes:
        print(f"  note: {note}")
    print()

    installed = list_ollama_models(base_url)
    print("Installed Ollama models:")
    if installed:
        for name in installed:
            print(f"  - {name}")
    else:
        print("  (none listed — Ollama may be empty; you can still choose a preset to pull)")
    print()

    options: list[str] = []
    print("Choose a model:")
    idx = 1
    for name, desc in RECOMMENDED_MODELS:
        mark = " [current]" if name == current else ""
        print(f"  {idx}) {name}{mark} — {desc}")
        options.append(name)
        idx += 1
    for name in installed:
        if name in options:
            continue
        mark = " [current]" if name == current else ""
        print(f"  {idx}) {name}{mark}")
        options.append(name)
        idx += 1
    print(f"  {idx}) Keep current ({current or DEFAULT_MODEL})")
    keep_idx = idx
    idx += 1
    print(f"  {idx}) Type a custom model name")
    custom_idx = idx

    fallback = current or DEFAULT_MODEL
    print()
    print(
        f"No choice in {int(MODEL_PICK_TIMEOUT_S)}s → keep previous model "
        f"({fallback}). Start typing to cancel the timer."
    )

    while True:
        raw = _readline_with_timeout(
            "Enter number (or press Enter for previous): ",
            MODEL_PICK_TIMEOUT_S,
            default="",
            timeout_message=(
                f"Timed out — using previous model: {fallback}"
            ),
        )
        if raw is None:
            print("No interactive input — using previous/default model.")
            return fallback
        raw = raw.strip()
        if raw == "":
            return fallback
        if not raw.isdigit():
            print("Please enter a number.")
            continue
        choice = int(raw)
        if choice == keep_idx:
            return fallback
        if choice == custom_idx:
            custom = _readline_with_timeout(
                "Model name (e.g. qwen2.5:7b): ",
                MODEL_PICK_TIMEOUT_S,
                default="",
                timeout_message="Timed out — keeping previous model.",
            )
            if custom is None or not custom.strip():
                return fallback
            return custom.strip()
        if 1 <= choice <= len(options):
            return options[choice - 1]
        print("Invalid choice.")


def _confirm_model(model: str, *, previous: str = "") -> bool:
    warn = model_warning(model)
    if not warn:
        print(f"Selected model: {model}")
        return True
    print()
    print("WARNING:", warn)
    # Continuing with the same model you already use → default Yes on timeout
    same_as_previous = bool(previous) and model == previous
    default = "y" if same_as_previous else "n"
    hint = "Y/n" if same_as_previous else "y/N"
    ans = _readline_with_timeout(
        f"Continue with this model? [{hint}]: ",
        MODEL_PICK_TIMEOUT_S,
        default=default,
        timeout_message=(
            f"Timed out — {'continuing' if same_as_previous else 'aborting'} "
            f"({model})."
        ),
    )
    if ans is None:
        print("No interactive input — keeping safer default instead.")
        return same_as_previous
    return ans.strip().lower() in {"y", "yes"}


def _ensure_model_pulled(model: str) -> bool:
    if not shutil.which("ollama"):
        return False
    print(f"Ensuring model is available: {model}")
    try:
        # `ollama pull` is a no-op if already present
        proc = subprocess.run(
            ["ollama", "pull", model],
            cwd=str(_ROOT),
            check=False,
        )
        if proc.returncode != 0:
            print(
                f"WARNING: `ollama pull {model}` exited {proc.returncode}. "
                "Continuing — chat calls may fail until the model is pulled."
            )
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: could not pull model: {exc}")
        return False


def _start_stack(root: Path, python: str, api_port: int, streamlit_port: int) -> list[subprocess.Popen]:
    procs: list[subprocess.Popen] = []
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")

    # Reuse if already up
    api_url = f"http://127.0.0.1:{api_port}/health"
    st_url = f"http://127.0.0.1:{streamlit_port}"

    import httpx

    api_up = False
    try:
        api_up = httpx.get(api_url, timeout=1.5).status_code == 200
    except Exception:
        api_up = False

    if api_up:
        print(f"FastAPI already running on :{api_port}")
    else:
        print(f"Starting FastAPI on :{api_port} …")
        procs.append(
            subprocess.Popen(
                [
                    python,
                    "-m",
                    "uvicorn",
                    "main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(api_port),
                ],
                cwd=str(root),
                env=env,
            )
        )
        if not _wait_http(api_url, timeout_s=60):
            print("ERROR: API did not become healthy. Check the uvicorn window/logs.")
        else:
            print("API is healthy.")

    st_up = False
    try:
        st_up = httpx.get(st_url, timeout=1.5).status_code < 500
    except Exception:
        st_up = False

    if st_up:
        print(f"Streamlit already running on :{streamlit_port}")
    else:
        print(f"Starting Streamlit on :{streamlit_port} …")
        procs.append(
            subprocess.Popen(
                [
                    python,
                    "-m",
                    "streamlit",
                    "run",
                    "ui/streamlit_app.py",
                    "--server.port",
                    str(streamlit_port),
                    "--server.headless",
                    "true",
                ],
                cwd=str(root),
                env=env,
            )
        )
        if not _wait_http(st_url, timeout_s=60):
            print("ERROR: Streamlit did not start. Check logs above.")
        else:
            print("Streamlit is up.")

    return procs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CareerPilot one-click launcher")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Non-interactive: keep current/default model, skip confirmations",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Fully automatic (same as --yes): no prompts, open browser",
    )
    parser.add_argument("--model", default="", help="Force OLLAMA_MODEL")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--skip-pull", action="store_true")
    args = parser.parse_args(argv)
    if args.auto:
        args.yes = True

    root = _ROOT
    _print_banner()
    env_vals = _load_dotenv_values(root)
    ollama_base = env_vals.get("OLLAMA_BASE_URL") or os.getenv(
        "OLLAMA_BASE_URL", "http://localhost:11434"
    )
    api_port = int(env_vals.get("API_PORT") or API_PORT_DEFAULT)
    current_model = (
        args.model
        or env_vals.get("OLLAMA_MODEL")
        or os.getenv("OLLAMA_MODEL")
        or DEFAULT_MODEL
    )

    print("Running preflight checks…")
    report = run_preflight(
        root,
        ollama_base_url=ollama_base,
        api_port=api_port,
        streamlit_port=STREAMLIT_PORT,
        require_ollama_api=False,
    )
    for c in report.checks:
        mark = "OK " if c.ok else "FAIL"
        print(f"  [{mark}] {c.title}: {c.detail}")
        if c.hint and not c.ok:
            print(f"         -> {c.hint}")

    pw_fail = next((c for c in report.checks if c.title == "Playwright browsers" and not c.ok), None)
    if pw_fail:
        print()
        print("Playwright Chromium missing — installing (needed for Indeed/Naukri)…")
        try:
            from launcher.bootstrap import ensure_playwright_browsers

            ensure_playwright_browsers(Path(_resolve_python(root)))
            print("  Playwright Chromium installed.")
        except Exception as exc:  # noqa: BLE001
            print(f"  WARNING: could not install Chromium ({exc})")
            print("  Indeed/Naukri/LinkedIn scrapes will show as errors until you run:")
            print("    .venv\\Scripts\\python -m playwright install chromium")

    hard_fails = [
        c
        for c in report.checks
        if not c.ok
        and c.title in {"Python version", "Project files", "Python packages", "Ollama CLI"}
    ]
    if hard_fails:
        print()
        print("Preflight failed. Fix the items above, then re-run.")
        for c in hard_fails:
            if c.title == "Ollama CLI":
                print("Opening https://ollama.com so you can install Ollama…")
                _open_default_browser("https://ollama.com")
            if c.title == "Python version":
                print("Opening https://www.python.org/downloads/ …")
                _open_default_browser("https://www.python.org/downloads/")
        return 1

    if not _ensure_ollama(ollama_base):
        print("Opening https://ollama.com …")
        _open_default_browser("https://ollama.com")
        return 1

    if args.yes:
        model = current_model
        print(f"Using model: {model}")
    else:
        model = _pick_model(ollama_base, current_model)
        if not _confirm_model(model, previous=current_model):
            print("Aborted. Choose a smaller model next time (qwen2.5:7b recommended).")
            return 1

    env_path = root / ".env"
    upsert_env_key(env_path, "OLLAMA_MODEL", model)
    print(f"Saved OLLAMA_MODEL={model} to {env_path.name}")

    if not args.skip_pull:
        _ensure_model_pulled(model)

    python = _resolve_python(root)
    print(f"Using Python: {python}")
    procs = _start_stack(root, python, api_port, STREAMLIT_PORT)

    st_url = f"http://localhost:{STREAMLIT_PORT}"
    if not args.no_browser:
        # Small delay so the page is ready when the tab loads
        time.sleep(1.0)
        _open_default_browser(st_url)
    else:
        print(f"Browser launch skipped. Open manually: {st_url}")

    print()
    print("CareerPilot is starting.")
    print(f"  UI:  {st_url}")
    print(f"  API: http://localhost:{api_port}/docs")
    print("Leave this window open. Press Ctrl+C to stop launched processes.")
    print()

    try:
        while True:
            alive = [p for p in procs if p.poll() is None]
            if procs and not alive:
                print("Child processes exited.")
                break
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nStopping…")
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
