"""Read/write OLLAMA_MODEL (and related) in the project ``.env`` file."""

from __future__ import annotations

from pathlib import Path


def upsert_env_key(env_path: Path, key: str, value: str) -> None:
    """Set ``key=value`` in a dotenv file, preserving other lines."""
    key = key.strip()
    value = value.strip()
    lines: list[str] = []
    if env_path.is_file():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    prefix = f"{key}="
    found = False
    out: list[str] = []
    for line in lines:
        if line.strip().startswith(prefix) or line.strip().startswith(f"#{prefix}"):
            if not found:
                out.append(f"{key}={value}")
                found = True
            # drop duplicate keys
            continue
        out.append(line)
    if not found:
        if out and out[-1].strip():
            out.append("")
        out.append(f"{key}={value}")
    env_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(out).rstrip() + "\n"
    env_path.write_text(text, encoding="utf-8")


def read_env_key(env_path: Path, key: str, default: str = "") -> str:
    if not env_path.is_file():
        return default
    prefix = f"{key}="
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped.startswith(prefix):
            continue
        return stripped[len(prefix) :].strip().strip('"').strip("'")
    return default
