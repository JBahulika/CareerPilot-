"""Per-source scrape budgets for Aggregate.

By default each active board gets an even share of ``scrape_limit`` so
``requested`` is the same across sources. Optional weighted mode remains
available for callers that prefer API-heavy allocation.
"""

from __future__ import annotations

from agents.job_sources.registry import POPULAR_JOB_SITES

# Relative weights by safety tag (see registry POPULAR_JOB_SITES).
_SAFETY_WEIGHT: dict[str, float] = {
    "api": 3.0,
    "scrape_safe": 2.0,
    "scrape_risky": 1.0,
    "disabled_captcha": 1.0,
}

_DEFAULT_WEIGHT = 1.5
_MIN_PER_SOURCE = 8


def _meta_by_id() -> dict[str, dict]:
    return {str(s["id"]): s for s in POPULAR_JOB_SITES}


def source_weight(source_id: str) -> float:
    meta = _meta_by_id().get(source_id, {})
    safety = str(meta.get("safety") or meta.get("method") or "")
    return _SAFETY_WEIGHT.get(safety, _DEFAULT_WEIGHT)


def allocate_scrape_budgets(
    source_ids: list[str],
    total_limit: int,
    *,
    min_per_source: int = _MIN_PER_SOURCE,
    weighted: bool = False,
) -> dict[str, int]:
    """Split ``total_limit`` across sources.

    Default (``weighted=False``): even shares so every board gets the same
    ``requested`` count (remainder distributed round-robin).

    When ``weighted=True``: API/RSS boards get a larger share than Playwright.
    """
    ids = [sid for sid in source_ids if sid]
    if not ids:
        return {}
    total_limit = max(0, int(total_limit))
    n = len(ids)
    if total_limit == 0:
        return {sid: 0 for sid in ids}

    if not weighted:
        base = total_limit // n
        rem = total_limit - base * n
        budgets = {sid: base for sid in ids}
        for sid in ids:
            if rem <= 0:
                break
            budgets[sid] += 1
            rem -= 1
        # Ensure non-zero when total allows
        if base == 0 and total_limit > 0:
            for i, sid in enumerate(ids):
                if i < total_limit:
                    budgets[sid] = 1
        return budgets

    # Weighted path (optional)
    if min_per_source * n > total_limit:
        base = max(1, total_limit // n)
        budgets = {sid: base for sid in ids}
        rem = total_limit - base * n
        for sid in ids:
            if rem <= 0:
                break
            budgets[sid] += 1
            rem -= 1
        return budgets

    weights = {sid: source_weight(sid) for sid in ids}
    weight_sum = sum(weights.values()) or float(n)

    raw = {sid: total_limit * (weights[sid] / weight_sum) for sid in ids}
    budgets = {sid: max(min_per_source, int(raw[sid])) for sid in ids}

    def _trim_order() -> list[str]:
        return sorted(ids, key=lambda s: (weights[s], s))

    def _grow_order() -> list[str]:
        return sorted(ids, key=lambda s: (-weights[s], s))

    current = sum(budgets.values())
    while current > total_limit:
        progressed = False
        for sid in _trim_order():
            if budgets[sid] > min_per_source:
                budgets[sid] -= 1
                current -= 1
                progressed = True
                if current <= total_limit:
                    break
        if not progressed:
            break
    while current < total_limit:
        for sid in _grow_order():
            budgets[sid] += 1
            current += 1
            if current >= total_limit:
                break

    return budgets
