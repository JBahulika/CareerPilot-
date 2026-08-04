"""Shared Ollama helpers for all agents.

Centralizes model access, robust JSON parsing, and a status check so each agent
only has to define a system prompt and a schema. Adapted from the proven
pattern in the P19 agentic-RAG project.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import httpx
import ollama

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


def check_ollama_status(model: Optional[str] = None) -> tuple[bool, str]:
    """Return (ok, message). Verifies the server is up and the model is present."""
    model = model or settings.ollama_model
    try:
        resp = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=5.0)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        return False, (
            f"Ollama is not reachable at {settings.ollama_base_url}. "
            f"Start it with `ollama serve`. ({exc})"
        )

    available = [m.get("name", "") for m in resp.json().get("models", [])]
    # Model tags may be "qwen2.5:7b" or bare "qwen2.5"; match by prefix.
    if any(name == model or name.startswith(model.split(":")[0]) for name in available):
        return True, f"Ollama ready with model '{model}'."
    return False, (
        f"Model '{model}' not found. Pull it with `ollama pull {model}`. "
        f"Available: {', '.join(available) or 'none'}."
    )


def _extract_json(text: str) -> Any:
    """Best-effort extraction of a JSON object from an LLM response."""
    text = text.strip()

    # Strip markdown code fences.
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Grab the outermost object/array.
    match = re.search(r"[\{\[].*[\}\]]", text, re.DOTALL)
    if match:
        candidate = match.group(0)
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)  # trailing commas
        candidate = re.sub(r"[\x00-\x1f]", " ", candidate)  # control chars
        return json.loads(candidate)

    raise ValueError(f"No JSON found in LLM response: {text[:200]}")


def call_ollama(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    json_mode: bool = False,
    temperature: float = 0.3,
) -> str:
    """Call Ollama chat with one retry. Returns the raw text response."""
    model = model or settings.ollama_model
    client = ollama.Client(host=settings.ollama_base_url)
    options = {"temperature": temperature}
    fmt = "json" if json_mode else ""

    last_error: Optional[Exception] = None
    for attempt in range(2):
        try:
            response = client.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                format=fmt,
                options=options,
            )
            return response["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning(f"Ollama call failed (attempt {attempt + 1}/2): {exc}")

    raise RuntimeError(f"Ollama call failed after retries: {last_error}")


def call_ollama_json(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.2,
) -> Any:
    """Call Ollama in JSON mode and parse the result robustly."""
    raw = call_ollama(
        system_prompt,
        user_prompt,
        model=model,
        json_mode=True,
        temperature=temperature,
    )
    return _extract_json(raw)
