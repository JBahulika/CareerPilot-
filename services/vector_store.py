"""ChromaDB wrapper for semantic job matching.

Job descriptions are embedded into a persistent Chroma collection so a profile
query can retrieve the most similar jobs by cosine distance.
"""

from __future__ import annotations

from functools import lru_cache

from core.config import settings
from core.logging import get_logger
from models.schemas import JobListing
from services.embeddings import embed_text, embed_texts

logger = get_logger(__name__)

_COLLECTION = "jobs"


@lru_cache(maxsize=1)
def _get_collection():
    import chromadb

    client = chromadb.PersistentClient(path=settings.chroma_path)
    return client.get_or_create_collection(
        name=_COLLECTION, metadata={"hnsw:space": "cosine"}
    )


def index_jobs(jobs: list[JobListing]) -> None:
    """Embed and upsert jobs keyed by their content hash."""
    if not jobs:
        return
    collection = _get_collection()
    ids = [j.content_hash for j in jobs]
    documents = [j.match_text() for j in jobs]
    embeddings = embed_texts(documents)
    metadatas = [{"company": j.company, "title": j.title} for j in jobs]
    collection.upsert(
        ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
    )
    logger.info(f"Indexed {len(jobs)} jobs into ChromaDB")


def rank_by_similarity(query_text: str, hashes: list[str]) -> dict[str, float]:
    """Return a {content_hash: similarity_score(0-1)} map for the given jobs.

    Cosine distance from Chroma is converted to a 0-1 similarity. Results are
    restricted to the requested candidate hashes.
    """
    if not hashes:
        return {}
    collection = _get_collection()
    query_embedding = embed_text(query_text)
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=collection.count() or len(hashes),
    )
    wanted = set(hashes)
    scores: dict[str, float] = {}
    ids = result.get("ids", [[]])[0]
    distances = result.get("distances", [[]])[0]
    for job_hash, distance in zip(ids, distances):
        if job_hash in wanted:
            scores[job_hash] = max(0.0, 1.0 - float(distance))
    return scores
