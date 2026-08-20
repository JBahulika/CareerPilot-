"""Phase 10b — launcher hardware / env helpers (no process starts)."""

from __future__ import annotations

from launcher.bootstrap import ensure_env_file, project_root, venv_python
from launcher.env_file import read_env_key, upsert_env_key
from launcher.hardware import (
    HardwareInfo,
    estimate_model_params_b,
    model_warning,
)


def test_estimate_model_params():
    assert estimate_model_params_b("qwen2.5:7b") == 7
    assert estimate_model_params_b("qwen2.5:14b") == 14
    assert estimate_model_params_b("llama3.1:8b") == 8
    assert estimate_model_params_b("mystery") is None


def test_model_warning_heavy_on_small_ram():
    hw = HardwareInfo(ram_gb=8.0, gpu_name=None, gpu_vram_gb=None, notes=[])
    warn = model_warning("qwen2.5:14b", hw)
    assert warn is not None
    assert "7b" in warn.lower() or "ram" in warn.lower()


def test_model_warning_ok_for_7b_on_16gb():
    hw = HardwareInfo(ram_gb=16.0, gpu_name=None, gpu_vram_gb=None, notes=[])
    assert model_warning("qwen2.5:7b", hw) is None


def test_model_warning_vram_path():
    hw = HardwareInfo(
        ram_gb=32.0, gpu_name="RTX 3060", gpu_vram_gb=6.0, notes=[]
    )
    warn = model_warning("qwen2.5:14b", hw)
    assert warn is not None


def test_upsert_env_key(tmp_path):
    path = tmp_path / ".env"
    path.write_text("FOO=1\nOLLAMA_MODEL=old\nBAR=2\n", encoding="utf-8")
    upsert_env_key(path, "OLLAMA_MODEL", "qwen2.5:7b")
    text = path.read_text(encoding="utf-8")
    assert "OLLAMA_MODEL=qwen2.5:7b" in text
    assert "FOO=1" in text
    assert text.count("OLLAMA_MODEL=") == 1
    assert read_env_key(path, "OLLAMA_MODEL") == "qwen2.5:7b"


def test_project_root_is_repo():
    root = project_root()
    assert (root / "requirements.txt").is_file()
    assert (root / "launcher" / "bootstrap.py").is_file()


def test_venv_python_path(tmp_path):
    p = venv_python(tmp_path)
    assert p.name in {"python.exe", "python"}
    assert ".venv" in p.parts


def test_ensure_env_file_from_example(tmp_path):
    (tmp_path / ".env.example").write_text("OLLAMA_MODEL=qwen2.5:7b\n", encoding="utf-8")
    ensure_env_file(tmp_path)
    assert (tmp_path / ".env").is_file()
    assert "OLLAMA_MODEL" in (tmp_path / ".env").read_text(encoding="utf-8")
