from __future__ import annotations

from dataclasses import replace

from backend.retrieval.vector_store import RetrievedChunk


def reciprocal_rank_fusion(
    rankings: dict[str, list[RetrievedChunk]],
    k: int = 60,
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    scores: dict[str, float] = {}
    selected: dict[str, RetrievedChunk] = {}
    metadata_by_chunk: dict[str, dict[str, str | int | float]] = {}

    for ranking_name, chunks in rankings.items():
        seen: set[str] = set()
        for rank, chunk in enumerate(chunks, start=1):
            if chunk.chunk_id in seen:
                continue
            seen.add(chunk.chunk_id)
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + (1.0 / (k + rank))
            selected.setdefault(chunk.chunk_id, chunk)
            metadata = metadata_by_chunk.setdefault(chunk.chunk_id, dict(chunk.metadata))
            metadata[f"{ranking_name}_rank"] = rank
            metadata[f"{ranking_name}_score"] = round(chunk.retrieval_score, 4)

    if not scores:
        return []

    max_score = max(scores.values()) or 1.0
    fused: list[RetrievedChunk] = []
    for chunk_id, rrf_score in sorted(scores.items(), key=lambda item: item[1], reverse=True):
        chunk = selected[chunk_id]
        metadata = metadata_by_chunk.get(chunk_id, dict(chunk.metadata))
        metadata["rrf_score"] = round(rrf_score, 6)
        metadata["fused_score"] = round(rrf_score / max_score, 4)
        fused.append(
            replace(
                chunk,
                metadata=metadata,
                retrieval_score=round(rrf_score / max_score, 4),
            )
        )
        if top_k and len(fused) >= top_k:
            break

    return fused
