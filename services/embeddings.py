"""Local sentence-transformers embedding and cross-encoder reranking.

Bi-encoders embed profile/job text separately for fast retrieval. Cross-encoders
jointly score (profile, job) pairs for precision reranking. BGE models use
query/passage prefixes for best accuracy.
"""

from __future__ import annotations

from functools import lru_cache

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
_BGE_PASSAGE_PREFIX = "Represent this sentence for retrieving relevant jobs: "


def _uses_bge_prefixes(model_name: str) -> bool:
    name = (model_name or "").lower()
    return "bge" in name or "e5" in name


def format_query_text(text: str) -> str:
    if _uses_bge_prefixes(settings.embedding_model):
        return f"{_BGE_QUERY_PREFIX}{text}"
    return text


def format_passage_text(text: str) -> str:
    if _uses_bge_prefixes(settings.embedding_model):
        return f"{_BGE_PASSAGE_PREFIX}{text}"
    return text


@lru_cache(maxsize=1)
def _get_bi_encoder():
    from sentence_transformers import SentenceTransformer

    logger.info(f"Loading embedding model: {settings.embedding_model}")
    return SentenceTransformer(settings.embedding_model)


@lru_cache(maxsize=1)
def _get_cross_encoder():
    if not settings.reranker_enabled:
        return None
    from sentence_transformers import CrossEncoder

    logger.info(f"Loading reranker model: {settings.reranker_model}")
    return CrossEncoder(settings.reranker_model)


def embed_texts(texts: list[str], *, as_passages: bool = True) -> list[list[float]]:
    if not texts:
        return []
    formatter = format_passage_text if as_passages else format_query_text
    formatted = [formatter(t) for t in texts]
    model = _get_bi_encoder()
    vectors = model.encode(formatted, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]


def embed_query(text: str) -> list[float]:
    return embed_texts([text], as_passages=False)[0]


def embed_passages(texts: list[str]) -> list[list[float]]:
    return embed_texts(texts, as_passages=True)


def embed_text(text: str) -> list[float]:
    """Backward-compatible alias — treats input as a passage."""
    return embed_passages([text])[0]


def rerank_pairs(query_text: str, passages: list[str]) -> list[float]:
    """Return raw cross-encoder scores for (query, passage) pairs."""
    if not passages:
        return []
    reranker = _get_cross_encoder()
    if reranker is None:
        return [0.0] * len(passages)
    pairs = [[query_text, passage] for passage in passages]
    scores = reranker.predict(pairs)
    return [float(s) for s in scores]


def normalize_rerank_scores(scores: list[float]) -> list[float]:
    """Map cross-encoder logits to 0–1 within a batch."""
    if not scores:
        return []
    lo = min(scores)
    hi = max(scores)
    if hi - lo < 1e-6:
        return [0.5] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]
