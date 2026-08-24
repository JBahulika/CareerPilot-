# Model pins (Phase 7)

**Single source of truth for default models and matching knobs.**

| Artifact | Role |
|----------|------|
| [`core/model_pins.py`](../core/model_pins.py) | Code constants (imported by `Settings` defaults) |
| This file | Human checklist |
| [`UPGRADE_NOTES.md`](UPGRADE_NOTES.md) Models pin table | Upgrade summary |
| [`.env.example`](../.env.example) | Env template mirroring pins |
| GitHub [`main`](https://github.com/JBahulika/CareerPilot-/tree/main) | Published tree |

Runtime `.env` may override pins. API: `GET /meta/pins` · Setup page shows pin vs live.

## Pinned stack (v0.10.0)

| Component | Pin |
|-----------|-----|
| Ollama LLM | `qwen2.5:7b` |
| Embeddings | `BAAI/bge-base-en-v1.5` |
| Reranker | `BAAI/bge-reranker-base` (enabled) |
| Min match score | `60` |
| Scrape limit max | `2000` |
| Digest cap | `5` |
| Recent jobs window | `3` days |
| Still-hiring window | `7` days |

### Matcher weights

| Knob | Pin |
|------|-----|
| Hybrid search | on (`0.65` vector weight) |
| Recall / rerank / LLM top-N | `50` / `20` / `8` |
| Score weights (embed / skill / rerank / llm) | `0.15` / `0.25` / `0.45` / `0.15` |

## Change checklist

When changing a pin, do **all** of the following in one PR:

1. Update `core/model_pins.py`
2. Update this file + `UPGRADE_NOTES.md` Models pin table
3. Mirror in `.env.example` if an env var changed
4. Bump `VERSION` + FastAPI `version` (via `read_version()`)
5. Append `CHANGELOG.md` + short `UPGRADE_NOTES` section
6. Run `pytest tests/test_phase7_model_pins.py`
7. Push branch `phase-7-…` then merge to `main` (keep the phase branch)

## Out of scope

- Captcha solvers, auto-apply, shipping multi‑GB models inside the repo
- Forcing users off a working local override (pins are defaults, not locks)
