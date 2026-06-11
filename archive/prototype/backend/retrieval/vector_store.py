from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.retrieval.chunking import RetrievalChunk


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    chunk_type: str
    source_label: str
    text: str
    metadata: dict[str, str | int | float]
    retrieval_score: float


class VectorStore(Protocol):
    def upsert_chunks(self, namespace: str, chunks: list[RetrievalChunk]) -> None: ...

    def query(
        self,
        namespace: str,
        query_texts: list[str],
        top_k: int = 5,
        where: dict[str, str | int | float] | None = None,
    ) -> list[RetrievedChunk]: ...

    def delete_document_chunks(self, namespace: str, document_id: str) -> None: ...
