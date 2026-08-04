"""Hybrid BM25 + vector retrieval for job shortlisting."""

from __future__ import annotations

import re

from core.config import settings
from core.logging import get_logger
from models.schemas import JobListing

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9+#.]+", re.IGNORECASE)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if len(t) > 1]


def _job_document(job: JobListing) -> str:
    return job.embedding_passage_text()


class _Bm25Index:
    """Minimal BM25 index for a single candidate pool (in-memory, per run)."""

    def __init__(self, documents: list[str]) -> None:
        self._documents = documents
        self._doc_tokens = [_tokenize(doc) for doc in documents]
        try:
            from rank_bm25 import BM25Okapi

            self._bm25 = BM25Okapi(self._doc_tokens)
            self._available = True
        except ImportError:
            logger.warning("rank_bm25 not installed; hybrid search uses vectors only")
            self._bm25 = None
            self._available = False

    def score(self, query: str) -> list[float]:
        if not self._available or not self._doc_tokens:
            return [0.0] * len(self._documents)
        query_tokens = _tokenize(query)
        if not query_tokens:
            return [0.0] * len(self._documents)
        return [float(s) for s in self._bm25.get_scores(query_tokens)]


def _normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    values = list(scores.values())
    lo = min(values)
    hi = max(values)
    if hi - lo < 1e-9:
        return {k: 0.5 for k in scores}
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}


def hybrid_similarity(
    query_text: str,
    jobs: list[JobListing],
    vector_scores: dict[str, float],
) -> dict[str, float]:
    """Blend normalized vector and BM25 scores for the given job pool."""
    if not jobs or not settings.hybrid_search_enabled:
        return vector_scores

    documents = [_job_document(job) for job in jobs]
    bm25 = _Bm25Index(documents)
    raw_bm25 = bm25.score(query_text)
    bm25_map = {job.content_hash: raw_bm25[i] for i, job in enumerate(jobs)}

    norm_vector = _normalize_scores(vector_scores)
    norm_bm25 = _normalize_scores(bm25_map)
    alpha = settings.hybrid_vector_weight

    blended: dict[str, float] = {}
    for job in jobs:
        h = job.content_hash
        v = norm_vector.get(h, 0.0)
        b = norm_bm25.get(h, 0.0)
        blended[h] = alpha * v + (1.0 - alpha) * b
    return blended
