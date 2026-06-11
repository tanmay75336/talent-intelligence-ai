from __future__ import annotations

import os
from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection

from backend.retrieval.chunking import RetrievalChunk
from backend.retrieval.embeddings import embed_texts
from backend.retrieval.vector_store import RetrievedChunk, VectorStore


class ChromaVectorStore(VectorStore):
    def __init__(self, persist_directory: str | None = None):
        directory = persist_directory or os.getenv(
            "CHROMA_PERSIST_DIR",
            str(Path(__file__).resolve().parent.parent / ".chroma"),
        )
        self.client = chromadb.PersistentClient(path=directory)

    def _collection(self, namespace: str) -> Collection:
        return self.client.get_or_create_collection(name=namespace, metadata={"hnsw:space": "cosine"})

    def upsert_chunks(self, namespace: str, chunks: list[RetrievalChunk]) -> None:
        if not chunks:
            return
        collection = self._collection(namespace)
        embeddings = embed_texts([chunk.text for chunk in chunks])
        if len(embeddings) != len(chunks):
            raise ValueError("Embedding count does not match chunk count.")
        collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            embeddings=embeddings,
            metadatas=[
                {
                    "document_id": chunk.document_id,
                    "chunk_type": chunk.chunk_type,
                    "source_label": chunk.source_label,
                    **{key: value for key, value in chunk.metadata.items() if isinstance(value, (str, int, float, bool))},
                }
                for chunk in chunks
            ],
        )

    def query(
        self,
        namespace: str,
        query_texts: list[str],
        top_k: int = 5,
        where: dict[str, str | int | float] | None = None,
    ) -> list[RetrievedChunk]:
        if not query_texts:
            return []
        collection = self._collection(namespace)
        result = collection.query(
            query_embeddings=embed_texts(query_texts),
            n_results=top_k,
            where=where,
        )
        chunks: list[RetrievedChunk] = []
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        for chunk_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
            retrieval_score = round(max(0.0, 1.0 - float(distance)), 4)
            chunks.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    document_id=str(metadata.get("document_id", "")),
                    chunk_type=str(metadata.get("chunk_type", "")),
                    source_label=str(metadata.get("source_label", "")),
                    text=document,
                    metadata=dict(metadata),
                    retrieval_score=retrieval_score,
                )
            )
        return chunks

    def delete_document_chunks(self, namespace: str, document_id: str) -> None:
        collection = self._collection(namespace)
        collection.delete(where={"document_id": document_id})
