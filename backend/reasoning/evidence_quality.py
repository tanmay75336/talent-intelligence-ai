from __future__ import annotations

import re
from dataclasses import dataclass

from backend.models.evidence import EvidenceSnippet, SourceType


IMPLEMENTATION_TERMS = {
    "built",
    "developed",
    "implemented",
    "integrated",
    "designed",
    "architected",
    "optimized",
    "automated",
    "debugged",
    "refactored",
}

SHIP_OWNERSHIP_TERMS = {
    "shipped",
    "deployed",
    "launched",
    "owned",
    "led",
    "delivered",
    "production",
    "release",
}

ARCHITECTURE_TERMS = {
    "architecture",
    "orchestration",
    "pipeline",
    "workflow",
    "service",
    "services",
    "backend",
    "arbitration",
    "api",
    "apis",
    "database",
    "queue",
    "event",
    "realtime",
    "real-time",
    "synchronization",
    "retrieval",
    "embedding",
    "vector",
}

OPERATIONAL_TERMS = {
    "ci/cd",
    "monitoring",
    "observability",
    "reliability",
    "scaling",
    "scalable",
    "latency",
    "throughput",
    "load",
    "reconnect",
    "recovery",
    "fault",
    "rollback",
    "docker",
    "deployment",
    "kubernetes",
    "aws",
    "gcp",
    "azure",
    "vercel",
    "railway",
    "render",
}

VAGUE_TERMS = {
    "experienced",
    "familiar",
    "knowledge",
    "passionate",
    "strong",
    "good",
    "excellent",
    "various",
    "multiple",
    "responsible for",
}

MEASUREMENT_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?%|\b\d+\+?\s*(?:users?|requests?|ms|seconds?|secs?|apis?|services?|teams?|candidates?|resumes?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EvidenceQuality:
    label: str
    score: float
    reasons: tuple[str, ...]


def classify_evidence(text: str, source_type: SourceType | str = "summary") -> EvidenceQuality:
    lowered = (text or "").lower()
    source = source_type or "summary"
    reasons: list[str] = []
    score = 0.0

    if source in {"project", "experience"}:
        score += 0.20
        reasons.append("implementation_source")
    elif source == "skills":
        score -= 0.30
        reasons.append("skill_inventory")
    elif source == "summary":
        score -= 0.12
        reasons.append("summary_claim")

    implementation_hits = _hit_count(lowered, IMPLEMENTATION_TERMS)
    shipping_hits = _hit_count(lowered, SHIP_OWNERSHIP_TERMS)
    architecture_hits = _hit_count(lowered, ARCHITECTURE_TERMS)
    operational_hits = _hit_count(lowered, OPERATIONAL_TERMS)
    vague_hits = _hit_count(lowered, VAGUE_TERMS)

    if implementation_hits:
        score += min(0.28, implementation_hits * 0.08)
        reasons.append("implementation_detail")
    if shipping_hits:
        score += min(0.24, shipping_hits * 0.08)
        reasons.append("shipping_or_ownership")
    if architecture_hits:
        score += min(0.22, architecture_hits * 0.05)
        reasons.append("architecture_specificity")
    if operational_hits:
        score += min(0.24, operational_hits * 0.06)
        reasons.append("operational_specificity")
    if MEASUREMENT_PATTERN.search(lowered):
        score += 0.16
        reasons.append("measurable_outcome")
    if implementation_hits and architecture_hits >= 2 and operational_hits:
        score += 0.12
        reasons.append("implementation_operational_depth")

    if vague_hits and implementation_hits == 0 and architecture_hits <= 1:
        score -= min(0.20, vague_hits * 0.05)
        reasons.append("vague_claim")

    word_count = len(lowered.split())
    if word_count < 10:
        score -= 0.08
        reasons.append("thin_statement")
    elif word_count >= 22 and (implementation_hits or architecture_hits):
        score += 0.08
        reasons.append("contextual_detail")

    bounded = max(0.0, min(1.0, score))
    if bounded >= 0.55:
        label = "strong"
    elif bounded >= 0.34:
        label = "medium"
    else:
        label = "weak"

    return EvidenceQuality(label=label, score=round(bounded, 4), reasons=tuple(dict.fromkeys(reasons)))


def evidence_strength_from_quality(text: str, source_type: SourceType | str = "summary") -> str:
    quality = classify_evidence(text, source_type)
    if quality.label == "strong":
        return "high"
    if quality.label == "medium":
        return "medium"
    return "low"


def is_strong_evidence(snippet: EvidenceSnippet | dict) -> bool:
    if isinstance(snippet, dict):
        text = snippet.get("snippet", "")
        source_type = snippet.get("source_type", "summary")
        strength = snippet.get("evidence_strength")
    else:
        text = snippet.snippet
        source_type = snippet.source_type
        strength = snippet.evidence_strength

    return strength == "high" and classify_evidence(text, source_type).label == "strong"


def quality_weight(snippet: EvidenceSnippet | dict) -> float:
    if isinstance(snippet, dict):
        return classify_evidence(snippet.get("snippet", ""), snippet.get("source_type", "summary")).score
    return classify_evidence(snippet.snippet, snippet.source_type).score


def evidence_category(text: str) -> str | None:
    lowered = (text or "").lower()
    if any(term in lowered for term in {"realtime", "real-time", "synchronization", "websocket", "event"}):
        return "realtime systems"
    if any(term in lowered for term in {"docker", "kubernetes", "aws", "gcp", "azure", "vercel", "railway", "render", "ci/cd", "deployment"}):
        return "deployment ownership"
    if any(term in lowered for term in {"retrieval", "embedding", "vector", "llm", "rag", "semantic"}):
        return "AI retrieval implementation"
    if any(term in lowered for term in {"api", "fastapi", "service", "orchestration", "backend"}):
        return "backend implementation"
    if any(term in lowered for term in {"react", "next.js", "typescript", "dashboard", "ui"}):
        return "frontend product execution"
    if any(term in lowered for term in {"monitoring", "observability", "reliability", "recovery", "scaling", "latency"}):
        return "operational reliability"
    return None


def _hit_count(text: str, terms: set[str]) -> int:
    return sum(1 for term in terms if term in text)
