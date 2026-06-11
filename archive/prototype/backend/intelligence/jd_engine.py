from __future__ import annotations

import re

from backend.models.evidence import EvidenceRef
from backend.models.job_intelligence import JobIntelligence
from backend.parsers.jd_analyzer import analyze_job_description
from backend.intelligence.normalization import split_into_sentences

ROLE_TITLE_PATTERN = re.compile(
    r"(?:hiring|looking for|seeking)\s+(?:an?\s+)?([A-Z][A-Za-z0-9\-/+ ]{2,60})",
    re.IGNORECASE,
)

STARTUP_TERMS = {
    "startup",
    "founding",
    "0 to 1",
    "zero to one",
    "fast-paced",
    "ambiguity",
    "wear many hats",
    "ownership",
}
ENTERPRISE_TERMS = {
    "cross-functional",
    "stakeholders",
    "process",
    "reliability",
    "scalability",
    "compliance",
    "enterprise",
    "documentation",
}
OWNERSHIP_TERMS = {"own", "ownership", "lead", "end-to-end", "autonomous", "independently", "responsible"}
COMMUNICATION_TERMS = {"communicate", "communication", "stakeholders", "collaborate", "present", "written", "verbal"}


def _extract_role_title(jd_text: str) -> str:
    match = ROLE_TITLE_PATTERN.search(jd_text or "")
    if match:
        return match.group(1).strip(" .")
    first_line = next((line.strip(" -•") for line in (jd_text or "").splitlines() if line.strip()), "")
    return first_line[:80] or "Target Role"


def _collect_evidence(jd_text: str, terms: set[str], prefix: str) -> list[EvidenceRef]:
    evidence = []
    for index, sentence in enumerate(split_into_sentences(jd_text)):
        lowered = sentence.lower()
        if any(term in lowered for term in terms):
            evidence.append(
                EvidenceRef(
                    evidence_id=f"{prefix}_{index}",
                    source_type="jd",
                    source_label="Job description",
                )
            )
    return evidence


def _score_expectation(jd_text: str, terms: set[str]) -> float:
    lowered = (jd_text or "").lower()
    hits = sum(1 for term in terms if term in lowered)
    return min(100.0, round(20.0 + (hits * 18.0), 2)) if hits else 35.0


def _infer_environment(jd_text: str) -> str:
    lowered = (jd_text or "").lower()
    startup_hits = sum(1 for term in STARTUP_TERMS if term in lowered)
    enterprise_hits = sum(1 for term in ENTERPRISE_TERMS if term in lowered)
    if startup_hits > enterprise_hits and startup_hits >= 1:
        return "startup"
    if enterprise_hits > startup_hits and enterprise_hits >= 1:
        return "enterprise"
    if startup_hits and enterprise_hits:
        return "hybrid"
    return "unknown"


def _confidence_for(value: str | float, evidence_count: int) -> str:
    if isinstance(value, str):
        return "High" if value not in {"unknown", ""} and evidence_count >= 1 else "Low"
    if evidence_count >= 2:
        return "High"
    if evidence_count == 1:
        return "Medium"
    return "Low"


def build_job_intelligence(jd_text: str) -> JobIntelligence:
    analysis = analyze_job_description(jd_text)
    ownership_evidence = _collect_evidence(jd_text, OWNERSHIP_TERMS, "jd_ownership")
    communication_evidence = _collect_evidence(jd_text, COMMUNICATION_TERMS, "jd_communication")
    startup_enterprise_evidence = _collect_evidence(jd_text, STARTUP_TERMS | ENTERPRISE_TERMS, "jd_environment")
    evidence = ownership_evidence + communication_evidence + startup_enterprise_evidence

    startup_vs_enterprise = _infer_environment(jd_text)
    ownership_expectation = _score_expectation(jd_text, OWNERSHIP_TERMS)
    communication_expectation = _score_expectation(jd_text, COMMUNICATION_TERMS)
    seniority = analysis.seniority_indicators[0] if analysis.seniority_indicators else "unknown"

    confidence = {
        "seniority": _confidence_for(seniority, len(analysis.seniority_indicators)),
        "startup_vs_enterprise": _confidence_for(startup_vs_enterprise, len(startup_enterprise_evidence)),
        "ownership_expectation": _confidence_for(ownership_expectation, len(ownership_evidence)),
        "communication_expectation": _confidence_for(communication_expectation, len(communication_evidence)),
    }

    return JobIntelligence(
        role_title=_extract_role_title(jd_text),
        explicit_skills=analysis.required_skills,
        preferred_skills=analysis.preferred_skills,
        responsibilities=analysis.responsibilities,
        domains=analysis.domain_keywords,
        seniority=seniority,
        startup_vs_enterprise=startup_vs_enterprise,
        ownership_expectation=ownership_expectation,
        communication_expectation=communication_expectation,
        evidence=evidence,
        confidence=confidence,
    )
