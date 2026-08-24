"""Phone remote setup status for the Streamlit Setup page (no secrets)."""

from __future__ import annotations

import socket
from pathlib import Path

from core.config import PROJECT_ROOT, settings
from core.remote_auth import remote_api_enabled


def _lan_ipv4() -> list[str]:
    """Best-effort private LAN addresses for phone reachability URLs."""
    found: set[str] = set()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.3)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        if ip and not ip.startswith("127."):
            found.add(ip)
    except OSError:
        pass
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                found.add(ip)
    except OSError:
        pass

    def _rank(ip: str) -> tuple[int, str]:
        if ip.startswith("192.168."):
            return (0, ip)
        if ip.startswith("10."):
            return (1, ip)
        if ip.startswith("172."):
            return (2, ip)
        if ip.startswith("100."):  # Tailscale CGNAT
            return (3, ip)
        return (9, ip)

    return sorted(found, key=_rank)


def get_remote_setup_status() -> dict:
    """Public connectivity snapshot — never includes ``REMOTE_API_TOKEN``."""
    port = int(settings.api_port or 8000)
    token_on = remote_api_enabled()
    ui_on = bool(settings.remote_ui_enabled)
    ui_dir = Path(PROJECT_ROOT) / "remote_ui"
    ui_ready = ui_on and ui_dir.is_dir() and (ui_dir / "index.html").is_file()
    apk_path = Path(PROJECT_ROOT) / "CareerPilot-Remote-debug.apk"
    apk_built = apk_path.is_file()

    lan_ips = _lan_ipv4()
    phone_urls = [f"http://{ip}:{port}/m/" for ip in lan_ips[:4]]
    api_urls = [f"http://{ip}:{port}" for ip in lan_ips[:4]]
    local_m = f"http://127.0.0.1:{port}/m/"

    if token_on and ui_ready:
        readiness = "ready"
        readiness_detail = "Token set and mobile UI mounted — phones can connect."
    elif not token_on:
        readiness = "disabled"
        readiness_detail = (
            "Set REMOTE_API_TOKEN in .env and restart the API (uvicorn / start bat)."
        )
    elif not ui_ready:
        readiness = "ui_missing"
        readiness_detail = (
            "REMOTE_UI_ENABLED is off or remote_ui/ is missing — phone web UI unavailable."
        )
    else:
        readiness = "partial"
        readiness_detail = "Remote partially configured."

    return {
        "ok": readiness == "ready",
        "readiness": readiness,
        "readiness_detail": readiness_detail,
        "token_configured": token_on,
        "remote_ui_enabled": ui_on,
        "mobile_ui_ready": ui_ready,
        "mobile_ui_path": "/m/",
        "api_port": port,
        "api_base_url": (settings.api_base_url or f"http://localhost:{port}").rstrip(
            "/"
        ),
        "lan_ips": lan_ips,
        "phone_ui_urls": phone_urls,
        "phone_api_urls": api_urls,
        "local_ui_url": local_m,
        "apk_built": apk_built,
        "apk_path": str(apk_path.name) if apk_built else None,
        "auto_apply": False,
        "captcha_solving": False,
        "docs": "docs/REMOTE_ACCESS.md",
    }
