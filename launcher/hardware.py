"""Hardware probes and model-size warnings for the CareerPilot launcher (Phase 10b)."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional


# Approximate parameter-size buckets used for soft warnings (not hard blocks).
_SIZE_PATTERNS = [
    (re.compile(r":?70b\b", re.I), 70),
    (re.compile(r":?72b\b", re.I), 72),
    (re.compile(r":?34b\b", re.I), 34),
    (re.compile(r":?33b\b", re.I), 33),
    (re.compile(r":?32b\b", re.I), 32),
    (re.compile(r":?27b\b", re.I), 27),
    (re.compile(r":?22b\b", re.I), 22),
    (re.compile(r":?14b\b", re.I), 14),
    (re.compile(r":?13b\b", re.I), 13),
    (re.compile(r":?9b\b", re.I), 9),
    (re.compile(r":?8b\b", re.I), 8),
    (re.compile(r":?7b\b", re.I), 7),
    (re.compile(r":?3b\b", re.I), 3),
    (re.compile(r":?1\.?5b\b", re.I), 2),
]


@dataclass
class HardwareInfo:
    ram_gb: Optional[float]
    gpu_name: Optional[str]
    gpu_vram_gb: Optional[float]
    notes: list[str]


def estimate_model_params_b(model_name: str) -> Optional[float]:
    """Best-effort billion-parameter estimate from an Ollama tag name."""
    name = (model_name or "").strip()
    if not name:
        return None
    for pattern, size in _SIZE_PATTERNS:
        if pattern.search(name):
            return float(size)
    return None


def probe_ram_gb() -> Optional[float]:
    """Return total RAM in GiB if detectable."""
    try:
        import psutil  # optional

        return round(psutil.virtual_memory().total / (1024**3), 1)
    except Exception:
        pass
    # Windows without psutil
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return round(stat.ullTotalPhys / (1024**3), 1)
    except Exception:
        pass
    return None


def probe_nvidia_gpu() -> tuple[Optional[str], Optional[float]]:
    """Return (gpu_name, vram_gb) from nvidia-smi when available."""
    if not shutil.which("nvidia-smi"):
        return None, None
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        )
        line = (out or "").strip().splitlines()[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2:
            name = parts[0]
            vram_mb = float(parts[1])
            return name, round(vram_mb / 1024.0, 1)
    except Exception:
        return None, None
    return None, None


def detect_hardware() -> HardwareInfo:
    notes: list[str] = []
    ram = probe_ram_gb()
    if ram is None:
        notes.append("Could not detect system RAM; warnings will be conservative.")
    gpu_name, vram = probe_nvidia_gpu()
    if gpu_name is None:
        notes.append("No NVIDIA GPU detected via nvidia-smi (CPU / other GPU mode).")
    return HardwareInfo(ram_gb=ram, gpu_name=gpu_name, gpu_vram_gb=vram, notes=notes)


def model_warning(
    model_name: str,
    hardware: HardwareInfo | None = None,
) -> Optional[str]:
    """Return a soft warning string if the model looks heavy for this machine.

    Never hard-blocks — caller should ask “Are you sure?”.
    """
    hw = hardware or detect_hardware()
    size = estimate_model_params_b(model_name)
    if size is None:
        return (
            f"Could not estimate size for '{model_name}'. "
            "Large models may be slow or fail on this machine."
        )

    ram = hw.ram_gb
    vram = hw.gpu_vram_gb

    # Rough guidance: prefer VRAM when NVIDIA present, else system RAM.
    if vram is not None:
        # Q4-ish rule of thumb: ~0.6–1.0 GB VRAM per B params
        if size >= 70 and vram < 40:
            return (
                f"'{model_name}' (~{size:.0f}B) usually needs a high-end GPU "
                f"(detected ~{vram} GB VRAM). Expect failure or extreme slowness."
            )
        if size >= 30 and vram < 20:
            return (
                f"'{model_name}' (~{size:.0f}B) is heavy for ~{vram} GB VRAM. "
                "Consider qwen2.5:7b or qwen2.5:14b instead."
            )
        if size >= 14 and vram < 8:
            return (
                f"'{model_name}' (~{size:.0f}B) may struggle on ~{vram} GB VRAM. "
                "qwen2.5:7b is the safer default."
            )
        return None

    # CPU / unknown GPU — use RAM
    if ram is not None:
        if size >= 30 and ram < 32:
            return (
                f"'{model_name}' (~{size:.0f}B) is very heavy for ~{ram} GB RAM "
                "without a strong GPU. Strongly prefer qwen2.5:7b."
            )
        if size >= 14 and ram < 16:
            return (
                f"'{model_name}' (~{size:.0f}B) may be slow or OOM on ~{ram} GB RAM. "
                "qwen2.5:7b is recommended."
            )
        if size >= 8 and ram < 8:
            return (
                f"'{model_name}' (~{size:.0f}B) is likely too large for ~{ram} GB RAM. "
                "Try a 3B–7B model."
            )
        return None

    if size >= 14:
        return (
            f"'{model_name}' (~{size:.0f}B) may be heavy; hardware could not be measured. "
            "qwen2.5:7b is the safe default."
        )
    return None


# Recommended presets shown in the launcher menu
RECOMMENDED_MODELS = [
    ("qwen2.5:7b", "Safe default — good quality on most PCs"),
    ("qwen2.5:3b", "Faster / lighter machines"),
    ("qwen2.5:14b", "Better quality — needs more RAM/VRAM"),
    ("llama3.1:8b", "Strong general alternative"),
]

DEFAULT_MODEL = "qwen2.5:7b"
