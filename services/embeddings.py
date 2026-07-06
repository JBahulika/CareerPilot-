"""Local sentence-transformers embedding model.

The model is loaded lazily and cached so the first call pays the load cost and
subsequent calls are fast. Runs entirely on-device per the privacy NFR.
"""

from __future__ import annotations

from functools import lru_cache

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer

    logger.info(f"Loading embedding model: {settings.embedding_model}")
    return SentenceTransformer(settings.embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]
