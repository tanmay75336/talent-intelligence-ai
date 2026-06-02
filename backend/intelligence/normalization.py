from __future__ import annotations

import re
from typing import Iterable

from backend.models.evidence import EvidenceSnippet, EvidenceStrength, SourceType
from backend.reasoning.evidence_quality import evidence_strength_from_quality


HIGH_STRENGTH_TERMS = (
    "built",
    "developed",
    "implemented",
    "shipped",
    "deployed",
    "led",
    "architected",
    "owned",
    "launched",
)
MEDIUM_STRENGTH_TERMS = (
    "created",
    "designed",
    "worked on",
    "integrated",
    "improved",
    "optimized",
)
METRIC_PATTERN = re.compile(r"\b\d+(?:\.\d+)?%|\b\d+\+?\s*(?:users?|ms|secs?|seconds?|apis?|services?)\b", re.IGNORECASE)
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+|\n")


def clean_snippet(text: str, limit: int = 240) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def split_into_sentences(text: str) -> list[str]:
    return [clean_snippet(part, limit=320) for part in SENTENCE_SPLIT_PATTERN.split(text or "") if clean_snippet(part, limit=320)]


def infer_evidence_strength(text: str, source_type: SourceType | str = "summary") -> EvidenceStrength:
    return evidence_strength_from_quality(text, source_type)  # type: ignore[return-value]


def build_evidence_snippet(
    evidence_id: str,
    source_type: SourceType,
    source_label: str,
    snippet: str,
) -> EvidenceSnippet:
    return EvidenceSnippet(
        evidence_id=evidence_id,
        source_type=source_type,
        source_label=source_label,
        snippet=clean_snippet(snippet),
        evidence_strength=infer_evidence_strength(snippet, source_type),
    )


def average_score(values: Iterable[float], fallback: float = 0.0) -> float:
    values = list(values)
    if not values:
        return fallback
    return round(sum(values) / len(values), 2)
