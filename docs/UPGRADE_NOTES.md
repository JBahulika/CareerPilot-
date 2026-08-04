# Upgrade notes

Human-oriented summary of what changed between versions. Keep this in sync with
[`CHANGELOG.md`](../CHANGELOG.md).

## Process

1. Implement a roadmap phase (or bugfix) on a branch.
2. Append bullets here under the target version (or **Unreleased**).
3. Mirror a Keep-a-Changelog entry in `CHANGELOG.md`.
4. Bump `VERSION` (and `main.py` FastAPI `version=`) when cutting a release.
5. Open / update the PR — **no merge without changelog + upgrade notes**.

## Models pin (update when defaults change)

| Component | Current default (0.2.0) |
|-----------|-------------------------|
| Ollama LLM | `qwen2.5:7b` |
| Embeddings | `BAAI/bge-base-en-v1.5` |
| Reranker | `BAAI/bge-reranker-base` (enabled) |

Source of truth for runtime knobs: `core/config.py` (mirrored in `.env.example`).

## [0.2.0] — Phase 0 guardrails

- Versioning: `VERSION` = `0.2.0`.
- Changelog discipline documented for all future phase PRs.
- Legal / ToS stance: prefer APIs; no captcha solving; no auto-apply
  (`docs/LEGAL.md`).
- Gitignore: cookies, proxy secret files, `.env`, local data dirs.
- Documented matching upgrades already in-tree (hybrid search, reranker, base
  embeddings, richer parser/schema).
- GitHub sync note: if `main` on
  [JBahulika/CareerPilot-](https://github.com/JBahulika/CareerPilot-) lacks
  hybrid/reranker files, merge or cherry-pick `contributor/local-matching-upgrades`
  (or re-apply from this workspace) before claiming GitHub is latest.

## Unreleased — phased roadmap (reference)

| Phase | Intent |
|-------|--------|
| 1 | User-settable match % threshold, location gating, filter reasons |
| 2 | Safe scrape HTTP client (headers, jitter, captcha abort, source health) |
| 3 | More safe sources + allowlist; disable captcha-prone by default |
| 4 | WhatsApp + email digests (human chooses applications; digest caps) |
| 5 | Proxies, random scan window, quiet hours, 429 backoff |
| 6 | Optional user cookies (advanced), stricter rate limits |
| 7 | Model pin checklist + publish GitHub as source of truth |
| 8 | Dedupe across runs (already notified) |
| 9 | Skills-gap + cover letter only after user selects a job |

## How to verify after upgrading

1. `cat VERSION` matches README / API version.
2. Setup page: API + Ollama healthy.
3. Upload resume → run pipeline (small Top N) → Results.
4. Confirm no secrets (`.env`, `data/cookies/`, proxy lists) are staged for commit.
