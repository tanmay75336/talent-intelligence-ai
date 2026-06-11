from __future__ import annotations

import logging

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from backend.retrieval.chunking import RetrievalChunk
from backend.retrieval.vector_store import RetrievedChunk

logger = logging.getLogger(__name__)


class SparseRetriever:
    """Lightweight lexical retriever used to reinforce explicit JD must-haves."""

    def __init__(self):
        self._chunks_by_namespace: dict[str, list[RetrievalChunk]] = {}
        self._vectorizers: dict[str, TfidfVectorizer] = {}
        self._matrices: dict[str, object] = {}

    def upsert_chunks(self, namespace: str, chunks: list[RetrievalChunk]) -> None:
        if not chunks:
            return

        existing = {
            chunk.chunk_id: chunk
            for chunk in self._chunks_by_namespace.get(namespace, [])
        }
        for chunk in chunks:
            existing[chunk.chunk_id] = chunk
        self._rebuild(namespace, list(existing.values()))

    def delete_document_chunks(self, namespace: str, document_id: str) -> None:
        chunks = [
            chunk
            for chunk in self._chunks_by_namespace.get(namespace, [])
            if chunk.document_id != document_id
        ]
        self._rebuild(namespace, chunks)

    def query(
        self,
        namespace: str,
        query_texts: list[str],
        top_k: int = 5,
        where: dict[str, str | int | float] | None = None,
    ) -> list[RetrievedChunk]:
        cleaned_queries = [query.strip() for query in query_texts if query and query.strip()]
        chunks = self._chunks_by_namespace.get(namespace, [])
        vectorizer = self._vectorizers.get(namespace)
        matrix = self._matrices.get(namespace)
        if not cleaned_queries or not chunks or vectorizer is None or matrix is None:
            return []

        query_matrix = vectorizer.transform(cleaned_queries)
        scores = (matrix @ query_matrix.T).toarray().max(axis=1)
        if scores.ndim > 1:
            scores = scores.ravel()

        ranked_indices = np.argsort(scores)[::-1]
        results: list[RetrievedChunk] = []
        for index in ranked_indices:
            score = float(scores[index])
            if score <= 0:
                continue
            chunk = chunks[int(index)]
            if not _matches_where(chunk, where):
                continue
            metadata = {
                **chunk.metadata,
                "sparse_score": round(score, 4),
                "lexical_score": round(score, 4),
                "retrieval_mode": "sparse",
            }
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    chunk_type=chunk.chunk_type,
                    source_label=chunk.source_label,
                    text=chunk.text,
                    metadata=metadata,
                    retrieval_score=round(score, 4),
                )
            )
            if len(results) >= top_k:
                break
        return results

    def _rebuild(self, namespace: str, chunks: list[RetrievalChunk]) -> None:
        self._chunks_by_namespace[namespace] = chunks
        if not chunks:
            self._vectorizers.pop(namespace, None)
            self._matrices.pop(namespace, None)
            return

        vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
        )
        try:
            matrix = vectorizer.fit_transform([chunk.text for chunk in chunks])
        except ValueError as error:
            logger.warning("Sparse index unavailable for namespace %s: %s", namespace, error)
            self._vectorizers.pop(namespace, None)
            self._matrices.pop(namespace, None)
            return

        self._vectorizers[namespace] = vectorizer
        self._matrices[namespace] = matrix


def _matches_where(chunk: RetrievalChunk, where: dict[str, str | int | float] | None) -> bool:
    if not where:
        return True
    for key, expected in where.items():
        if key == "document_id":
            actual = chunk.document_id
        elif key == "chunk_type":
            actual = chunk.chunk_type
        else:
            actual = chunk.metadata.get(key)
        if actual != expected:
            return False
    return True
