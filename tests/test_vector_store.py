"""Regression tests for Chroma/NumPy handling in vector_store."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np

from services import vector_store


def test_as_list_handles_numpy_without_truthiness_error():
    arr = np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32)
    out = vector_store._as_list(arr)
    assert len(out) == 2 and len(out[0]) == 2
    assert abs(out[0][0] - 0.1) < 1e-5
    assert vector_store._as_list(None) == []
    assert vector_store._as_list([]) == []
    assert vector_store._as_list(["a", "b"]) == ["a", "b"]


def test_rank_by_similarity_accepts_numpy_chroma_embeddings(monkeypatch):
    """Chroma often returns embeddings as ndarray; must not use `or []`."""
    hashes = ["hash-a", "hash-b"]
    emb = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=np.float32,
    )
    fake_collection = MagicMock()
    fake_collection.get.return_value = {
        "ids": np.array(hashes),
        "embeddings": emb,
    }
    monkeypatch.setattr(vector_store, "_get_collection", lambda: fake_collection)
    monkeypatch.setattr(
        vector_store,
        "embed_query",
        lambda _text: [1.0, 0.0, 0.0],
    )

    scores = vector_store.rank_by_similarity("python ml engineer", hashes)

    assert set(scores.keys()) == set(hashes)
    assert scores["hash-a"] > scores["hash-b"]
    assert 0.0 <= scores["hash-a"] <= 1.0


def test_index_jobs_skips_when_ids_are_numpy(monkeypatch):
    job = MagicMock()
    job.content_hash = "already-there"
    job.embedding_passage_text.return_value = "doc"
    job.company = "Acme"
    job.title = "ML Eng"
    job.source = "test"

    fake_collection = MagicMock()
    fake_collection.get.return_value = {"ids": np.array(["already-there"])}
    monkeypatch.setattr(vector_store, "_get_collection", lambda: fake_collection)

    vector_store.index_jobs([job])
    fake_collection.upsert.assert_not_called()
