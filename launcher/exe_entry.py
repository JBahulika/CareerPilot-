"""PyInstaller entry — double-click CareerPilot.exe in the repo folder."""

from __future__ import annotations

import sys


def _pause() -> None:
    if sys.platform.startswith("win"):
        try:
            input("\nPress Enter to close…")
        except EOFError:
            pass


def main() -> int:
    try:
        from launcher.bootstrap import main as boot

        code = boot()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}")
        _pause()
        return 1
    if code != 0:
        _pause()
    return int(code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
