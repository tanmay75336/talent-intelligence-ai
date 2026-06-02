from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from backend.models.candidate_profile import CandidateProfile
from backend.utils.skill_taxonomy import normalize_whitespace


AI_INFRA_TERMS = {
    "retrieval",
    "rag",
    "search ranking",
    "ranking",
    "recommendation",
    "recommender",
    "embedding",
    "embeddings",
    "vector database",
    "vector search",
    "semantic search",
    "faiss",
    "pinecone",
    "weaviate",
    "qdrant",
    "milvus",
    "elasticsearch",
    "opensearch",
    "ml platform",
    "model serving",
    "inference",
}

WEAK_AI_TERMS = {
    "ai",
    "llm",
    "llms",
    "openai",
    "langchain",
    "generative ai",
    "machine learning",
    "ml",
    "nlp",
}

OWNERSHIP_TERMS = {
    "built",
    "created",
    "designed",
    "implemented",
    "developed",
    "architected",
    "deployed",
    "scaled",
    "optimized",
    "owned",
    "shipped",
    "launched",
}

TECH_CONTEXT_TERMS = {
    "ai",
    "ml",
    "search",
    "ranking",
    "retrieval",
    "backend",
    "platform",
    "pipeline",
    "inference",
    "model",
    "embedding",
    "vector",
    "recommendation",
}

PRODUCTION_TERMS = {
    "production",
    "deployed",
    "shipped",
    "users",
    "scale",
    "scaled",
    "latency",
    "monitoring",
    "observability",
    "pipeline",
    "pipelines",
    "inference",
}

STARTUP_TERMS = {
    "startup",
    "founding",
    "0-1",
    "zero to one",
    "end-to-end",
    "end to end",
    "ownership",
    "owned",
    "system design",
}

MANAGEMENT_ONLY_TERMS = {
    "managed",
    "coordinated",
    "supervised",
    "stakeholder",
    "roadmap",
    "strategy",
    "hiring",
    "performance review",
}

RESEARCH_TERMS = {"research", "paper", "papers", "publication", "published", "phd", "thesis"}
FRAMEWORK_ONLY_TERMS = {"langchain", "openai", "prompt engineering", "chatgpt"}
AI_SKILL_TERMS = WEAK_AI_TERMS | AI_INFRA_TERMS | FRAMEWORK_ONLY_TERMS

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass(frozen=True)
class EvidenceCalibration:
    adjustment: float
    ai_infra_hits: list[str] = field(default_factory=list)
    career_ai_infra_hits: list[str] = field(default_factory=list)
    production_hits: list[str] = field(default_factory=list)
    ownership_hits: list[str] = field(default_factory=list)
    startup_hits: list[str] = field(default_factory=list)
    trap_flags: list[str] = field(default_factory=list)
    behavioral_tie_breaker: float = 0.0
    best_evidence: str = ""
    promoted_reasons: list[str] = field(default_factory=list)
    demoted_reasons: list[str] = field(default_factory=list)


def calibrate_candidate_evidence(profile: CandidateProfile) -> EvidenceCalibration:
    career_text = normalize_whitespace(" ".join(str(item.get("description") or "") for item in profile.career_history))
    summary_text = normalize_whitespace(profile.summary or "")
    skill_text = normalize_whitespace(" ".join(str(skill.get("name") or "") for skill in profile.skill_records))
    certification_text = normalize_whitespace(" ".join(profile.certifications))
    combined_text = normalize_whitespace(" ".join([summary_text, career_text, skill_text, certification_text]))
    career_lower = career_text.lower()
    summary_lower = summary_text.lower()
    skill_lower = skill_text.lower()
    combined_lower = combined_text.lower()
    skill_summary_lower = skill_lower + " " + summary_lower

    career_ai_hits = _term_hits_lower(career_lower, AI_INFRA_TERMS)
    all_ai_hits = _term_hits_lower(combined_lower, AI_INFRA_TERMS)
    weak_ai_hits = _term_hits_lower(skill_summary_lower, WEAK_AI_TERMS | FRAMEWORK_ONLY_TERMS)
    production_hits = _term_hits_lower(career_lower, PRODUCTION_TERMS)
    ownership_hits = _ownership_hits_near_context(career_text)
    startup_hits = _term_hits_lower(combined_lower, STARTUP_TERMS)
    trap_flags = _detect_traps(
        profile,
        career_lower,
        skill_summary_lower,
        career_ai_hits,
        weak_ai_hits,
        production_hits,
        ownership_hits,
    )
    behavioral_tie_breaker = _behavioral_tie_breaker(profile.redrob_signals)

    adjustment = 0.0
    promoted_reasons: list[str] = []
    demoted_reasons: list[str] = []

    if career_ai_hits:
        delta = min(0.030, 0.010 + (len(career_ai_hits) * 0.004))
        adjustment += delta
        promoted_reasons.append("career evidence proves AI infrastructure work")
    elif all_ai_hits:
        adjustment += 0.006
        promoted_reasons.append("AI infrastructure appears outside career history")

    if production_hits and ownership_hits:
        adjustment += min(0.024, 0.008 + (len(production_hits) * 0.003) + (len(ownership_hits) * 0.002))
        promoted_reasons.append("production ownership is backed by work history")

    if 5.0 <= profile.years_of_experience <= 9.0 and ownership_hits:
        adjustment += 0.010
        promoted_reasons.append("experience range matches senior founding engineer target")
    elif profile.years_of_experience >= 15.0:
        adjustment -= 0.010
        demoted_reasons.append("very high experience is not treated as automatic fit")

    if startup_hits and ownership_hits:
        adjustment += 0.006
        promoted_reasons.append("builder/startup ownership language is present")

    if behavioral_tie_breaker > 0 and (career_ai_hits or production_hits):
        adjustment += behavioral_tie_breaker
        promoted_reasons.append("positive RedRob platform signals used as close-candidate tie breaker")

    trap_penalty = {
        "framework_only_ai_profile": 0.022,
        "keyword_stuffing": 0.030,
        "research_only_mismatch": 0.020,
        "hands_off_senior": 0.024,
    }
    for flag in trap_flags:
        penalty = trap_penalty.get(flag, 0.0)
        adjustment -= penalty
        if penalty:
            demoted_reasons.append(flag.replace("_", " "))

    adjustment = round(max(-0.060, min(0.080, adjustment)), 6)
    return EvidenceCalibration(
        adjustment=adjustment,
        ai_infra_hits=all_ai_hits,
        career_ai_infra_hits=career_ai_hits,
        production_hits=production_hits,
        ownership_hits=ownership_hits,
        startup_hits=startup_hits,
        trap_flags=trap_flags,
        behavioral_tie_breaker=round(behavioral_tie_breaker, 6),
        best_evidence="",
        promoted_reasons=promoted_reasons,
        demoted_reasons=demoted_reasons,
    )


def best_evidence_for_calibration(profile: CandidateProfile, calibration: EvidenceCalibration) -> str:
    career_text = normalize_whitespace(" ".join(str(item.get("description") or "") for item in profile.career_history))
    return _best_evidence_sentence(
        career_text,
        calibration.career_ai_infra_hits,
        calibration.production_hits,
        calibration.ownership_hits,
    )


def _detect_traps(
    profile: CandidateProfile,
    career_lower: str,
    skill_summary_lower: str,
    career_ai_hits: list[str],
    weak_ai_hits: list[str],
    production_hits: list[str],
    ownership_hits: list[str],
) -> list[str]:
    flags: list[str] = []
    ai_skill_count = 0
    low_support_ai_skill_count = 0
    for skill in profile.skill_records:
        skill_name = str(skill.get("name") or "").lower()
        if any(term in skill_name for term in AI_SKILL_TERMS):
            ai_skill_count += 1
            if _float(skill.get("duration_months")) <= 12 and _float(skill.get("endorsements")) <= 3:
                low_support_ai_skill_count += 1
    career_summary_lower = career_lower + " " + str(profile.summary or "").lower()
    framework_hits = _term_hits_lower(skill_summary_lower, FRAMEWORK_ONLY_TERMS)
    research_hits = _term_hits_lower(career_summary_lower, RESEARCH_TERMS)
    management_hits = _term_hits_lower(career_summary_lower, MANAGEMENT_ONLY_TERMS)

    if framework_hits and not career_ai_hits and not production_hits:
        flags.append("framework_only_ai_profile")
    if ai_skill_count >= 6 and low_support_ai_skill_count >= 4 and not career_ai_hits:
        flags.append("keyword_stuffing")
    if research_hits and not production_hits and len(ownership_hits) <= 1:
        flags.append("research_only_mismatch")
    if profile.years_of_experience >= 12.0 and len(management_hits) >= 3 and len(ownership_hits) <= 1:
        flags.append("hands_off_senior")
    if weak_ai_hits and not career_ai_hits and not production_hits:
        flags.append("framework_only_ai_profile")

    return _unique_preserve_order(flags)


def _behavioral_tie_breaker(signals: dict[str, Any]) -> float:
    if not signals:
        return 0.0
    score = 0.0
    github = _float(signals.get("github_activity_score"))
    assessment = _assessment_score(signals.get("skill_assessment_scores"))
    response_rate = _float(signals.get("recruiter_response_rate"))
    saved = _float(signals.get("saved_by_recruiters_30d"))
    completeness = _float(signals.get("profile_completeness_score"))
    active_days = _days_since_2026_06_02(str(signals.get("last_active_date") or ""))

    if github >= 40:
        score += 0.004
    if assessment >= 70:
        score += 0.004
    if response_rate >= 0.70:
        score += 0.003
    if saved >= 12:
        score += 0.003
    if completeness >= 75:
        score += 0.002
    if active_days is not None and active_days <= 45:
        score += 0.002
    if signals.get("open_to_work_flag") is True:
        score += 0.002
    return min(0.012, score)


def _assessment_score(value: Any) -> float:
    if isinstance(value, dict):
        scores = [_float(item) for item in value.values()]
    elif isinstance(value, list):
        scores = [_float(item.get("score") if isinstance(item, dict) else item) for item in value]
    else:
        return -1.0
    scores = [score for score in scores if score >= 0]
    return max(scores) if scores else -1.0


def _days_since_2026_06_02(value: str) -> int | None:
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", value)
    if not match:
        return None
    year, month, day = (int(part) for part in match.groups())
    return (2026 - year) * 365 + (6 - month) * 30 + (2 - day)


def _term_hits(text: str, terms: set[str]) -> list[str]:
    lowered = (text or "").lower()
    return _term_hits_lower(lowered, terms)


def _term_hits_lower(lowered: str, terms: set[str]) -> list[str]:
    return sorted(term for term in terms if term in lowered)


def _ownership_hits_near_context(text: str) -> list[str]:
    hits: list[str] = []
    for sentence in SENTENCE_SPLIT_RE.split(text or ""):
        lowered = sentence.lower()
        if any(term in lowered for term in TECH_CONTEXT_TERMS):
            hits.extend(term for term in OWNERSHIP_TERMS if term in lowered)
    return sorted(set(hits))


def _best_evidence_sentence(text: str, ai_hits: list[str], production_hits: list[str], ownership_hits: list[str]) -> str:
    wanted_terms = set(ai_hits + production_hits + ownership_hits)
    if not wanted_terms:
        wanted_terms = AI_INFRA_TERMS | PRODUCTION_TERMS | OWNERSHIP_TERMS
    sentences = [normalize_whitespace(sentence) for sentence in SENTENCE_SPLIT_RE.split(text or "") if sentence.strip()]
    if not sentences:
        return ""
    sentences.sort(key=lambda sentence: _sentence_value(sentence, wanted_terms), reverse=True)
    return sentences[0][:220].rstrip()


def _sentence_value(sentence: str, terms: set[str]) -> int:
    lowered = sentence.lower()
    return sum(1 for term in terms if term in lowered)


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
