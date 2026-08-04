"""ChromaDB wrapper for semantic job matching.

Job descriptions are embedded into a persistent Chroma collection keyed by
content hash. Similarity is computed only within the requested candidate pool
(not the entire collection) for accuracy and performance.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from core.config import settings
from core.logging import get_logger
from models.schemas import JobListing
from services.embeddings import embed_passages, embed_query

logger = get_logger(__name__)

_COLLECTION = "jobs"


@lru_cache(maxsize=1)
def _get_collection():
    import chromadb

    client = chromadb.PersistentClient(path=settings.chroma_path)
    return client.get_or_create_collection(
        name=_COLLECTION, metadata={"hnsw:space": "cosine"}
    )


def _cosine_similarity(query: list[float], vectors: list[list[float]]) -> list[float]:
    q = np.array(query, dtype=np.float32)
    mat = np.array(vectors, dtype=np.float32)
    if mat.size == 0:
        return []
    dots = mat @ q
    return [max(0.0, min(1.0, float(d))) for d in dots]


def index_jobs(jobs: list[JobListing]) -> None:
    """Embed and upsert jobs keyed by content hash (skips already-indexed ids)."""
    if not jobs:
        return
    collection = _get_collection()
    ids = [j.content_hash for j in jobs]
    existing: set[str] = set()
    try:
        got = collection.get(ids=ids, include=[])
        existing = set(got.get("ids") or [])
    except Exception:  # noqa: BLE001
        existing = set()

    to_index = [j for j in jobs if j.content_hash not in existing]
    if not to_index:
        return

    documents = [j.embedding_passage_text() for j in to_index]
    embeddings = embed_passages(documents)
    metadatas = [
        {"company": j.company, "title": j.title, "source": j.source}
        for j in to_index
    ]
    collection.upsert(
        ids=[j.content_hash for j in to_index],
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )
    logger.info(f"Indexed {len(to_index)} new jobs into ChromaDB ({len(existing)} cached)")


def rank_by_similarity(query_text: str, hashes: list[str]) -> dict[str, float]:
    """Return {content_hash: similarity 0-1} restricted to the given job hashes."""
    if not hashes:
        return {}

    collection = _get_collection()
    query_embedding = embed_query(query_text)

    try:
        result = collection.get(ids=hashes, include=["embeddings"])
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Chroma get failed, returning empty scores: {exc}")
        return {}

    ids = result.get("ids") or []
    embeddings = result.get("embeddings") or []
    if not ids or embeddings is None or len(embeddings) == 0:
        return {}

    sims = _cosine_similarity(query_embedding, embeddings)
    return {job_id: sim for job_id, sim in zip(ids, sims)}
