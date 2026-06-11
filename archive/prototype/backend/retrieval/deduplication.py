from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from backend.retrieval.vector_store import RetrievedChunk


TOKEN_RE = re.compile(r"[a-zA-Z0-9+#.]+")


@dataclass
class DiversityResult:
    selected: list[RetrievedChunk]
    suppressed: list[dict[str, str | float]]


def token_set(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text or "") if len(token) > 1}


def token_overlap(left: str, right: str) -> float:
    left_tokens = token_set(left)
    right_tokens = token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def diversify_chunks(
    chunks: list[RetrievedChunk],
    limit: int = 3,
    max_per_source_label: int = 1,
    duplicate_threshold: float = 0.86,
    redundancy_threshold: float = 0.72,
) -> DiversityResult:
    selected: list[RetrievedChunk] = []
    suppressed: list[dict[str, str | float]] = []
    seen_chunk_ids: set[str] = set()
    source_counts: dict[str, int] = {}

    for chunk in chunks:
        if chunk.chunk_id in seen_chunk_ids:
            suppressed.append(_suppression(chunk, "duplicate_chunk_id", 1.0))
            continue
        seen_chunk_ids.add(chunk.chunk_id)

        source_count = source_counts.get(chunk.source_label, 0)
        if source_count >= max_per_source_label:
            suppressed.append(_suppression(chunk, "source_label_cap", 1.0))
            continue

        highest_overlap = max((token_overlap(chunk.text, item.text) for item in selected), default=0.0)
        if highest_overlap >= duplicate_threshold:
            suppressed.append(_suppression(chunk, "near_duplicate_text", highest_overlap))
            continue
        if highest_overlap >= redundancy_threshold and len(selected) >= 2:
            suppressed.append(_suppression(chunk, "redundant_evidence", highest_overlap))
            continue

        selected.append(chunk)
        source_counts[chunk.source_label] = source_count + 1
        if len(selected) >= limit:
            break

    return DiversityResult(selected=selected, suppressed=suppressed)


def dedupe_by_chunk_id(chunks: Iterable[RetrievedChunk]) -> list[RetrievedChunk]:
    seen: set[str] = set()
    ordered: list[RetrievedChunk] = []
    for chunk in chunks:
        if chunk.chunk_id in seen:
            continue
        seen.add(chunk.chunk_id)
        ordered.append(chunk)
    return ordered


def _suppression(chunk: RetrievedChunk, reason: str, overlap: float) -> dict[str, str | float]:
    return {
        "chunk_id": chunk.chunk_id,
        "source_label": chunk.source_label,
        "reason": reason,
        "overlap": round(overlap, 4),
    }
