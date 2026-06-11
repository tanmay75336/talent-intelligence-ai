from __future__ import annotations

from typing import TYPE_CHECKING

from backend.models.candidate_intelligence import CandidateIntelligence
from backend.models.evidence import EvidenceSnippet
from backend.models.job_intelligence import JobIntelligence
from backend.models.ranking_result import AdjacentMatch, PillarScore, RankingResult
from backend.models.candidate_profile import CandidateProfile
from backend.reasoning.evidence_quality import classify_evidence, evidence_category, is_strong_evidence

if TYPE_CHECKING:
    from backend.retrieval.evidence_retriever import RetrievalContext

CORE_PILLARS = (
    "semantic_fit",
    "technical_depth",
    "ownership",
    "execution_maturity",
    "learning_velocity",
    "startup_readiness",
    "transferability",
    "communication",
    "domain_relevance",
    "risk",
)

GENERIC_INSIGHT_PATTERNS = (
    "assess communication",
    "validate backend",
    "review scalability",
    "check leadership",
    "evaluate teamwork",
    "confirm ability",
    "technical depth claims need",
    "ownership scope is mentioned lightly",
    "production deployment ownership is not strongly evidenced",
    "direct role alignment is weaker",
    "project-level relevance is not consistently strong",
    "must-have coverage has gaps",
    "resume claims are not backed",
    "direct skill overlap is supported",
    "strong semantic alignment",
    "technical stack depth is backed",
    "shows credible ownership",
    "execution maturity is visible",
    "transferable skills reduce",
)

CATEGORY_CONCEPTS = {
    "deployment ownership": (
        "deployed",
        "deployment",
        "docker",
        "railway",
        "render",
        "vercel",
        "aws",
        "ci/cd",
        "pipeline",
        "production",
    ),
    "AI retrieval implementation": (
        "retrieval",
        "embedding",
        "vector",
        "llm",
        "rag",
        "semantic",
        "ranking",
        "ai reasoning",
        "api integration",
    ),
    "realtime systems": (
        "realtime",
        "real-time",
        "synchronization",
        "websocket",
        "live bidding",
        "reconnect",
        "arbitration",
        "event",
    ),
    "backend implementation": (
        "fastapi",
        "api",
        "backend",
        "service",
        "workflow",
        "postgresql",
        "database",
        "automation",
        "integration",
    ),
    "frontend product execution": (
        "react",
        "next.js",
        "typescript",
        "dashboard",
        "ui",
        "workflow",
        "filtering",
        "analytics",
    ),
    "operational reliability": (
        "monitoring",
        "observability",
        "reliability",
        "rollback",
        "recovery",
        "latency",
        "scaling",
        "load",
    ),
}


def _bounded_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _coverage_ratio(evidence_items: list[EvidenceSnippet]) -> float:
    if not evidence_items:
        return 0.0
    medium_or_high = [item for item in evidence_items if item.evidence_strength in {"high", "medium"}]
    return len(medium_or_high) / len(evidence_items)


def _density_ratio(evidence_items: list[EvidenceSnippet]) -> float:
    if not evidence_items:
        return 0.0
    return min(1.0, len(evidence_items) / 3)


def _confidence_label(evidence_items: list[EvidenceSnippet], contradiction_count: int) -> str:
    coverage = _coverage_ratio(evidence_items)
    density = _density_ratio(evidence_items)
    if contradiction_count == 0 and coverage >= 0.65 and density >= 0.66:
        return "High"
    if contradiction_count <= 1 and (coverage >= 0.4 or density >= 0.33):
        return "Medium"
    return "Low"


def _evidence_for_sources(
    evidence_library: dict[str, EvidenceSnippet],
    source_types: set[str],
    limit: int = 3,
) -> list[EvidenceSnippet]:
    ordered = [
        snippet
        for snippet in evidence_library.values()
        if snippet.source_type in source_types
    ]
    ordered.sort(key=lambda item: {"high": 0, "medium": 1, "low": 2}[item.evidence_strength])
    return ordered[:limit]


def _score_risk(scorecard: dict, contradiction_flags: list[str], missing_must_haves: list[str]) -> float:
    risk = 18.0
    risk += len(contradiction_flags) * 12.0
    risk += len(missing_must_haves) * 10.0
    risk += max(0.0, 70.0 - scorecard.get("semantic_score", 0.0)) * 0.12
    risk += max(0.0, 65.0 - scorecard.get("keyword_score", 0.0)) * 0.10
    return _bounded_score(risk)


def _user_friendly_missing(skill: str) -> str:
    lowered = skill.lower()
    if skill in {"Docker", "Kubernetes", "AWS", "GCP", "Azure", "CI/CD"}:
        return "No deployment evidence"
    if "sql" in lowered or skill in {"PostgreSQL", "MySQL", "Supabase"}:
        return "Missing SQL experience"
    if skill == "React":
        return "Limited React exposure"
    return f"Missing {skill} experience"


def _derive_missing_must_haves(
    scorecard: dict,
    candidate_intelligence: CandidateIntelligence,
    evidence_library: dict[str, EvidenceSnippet],
) -> list[str]:
    missing = []
    evidence_text = " ".join(snippet.snippet.lower() for snippet in evidence_library.values())
    for skill in scorecard.get("missing_skills", []):
        friendly_gap = _user_friendly_missing(skill)
        if friendly_gap in missing:
            continue
        if skill.lower() not in evidence_text:
            missing.append(friendly_gap)
    if "No deployment evidence" not in missing and candidate_intelligence.supporting_signals.get("deployment_maturity", 0) < 35:
        deployment_related_missing = {"Docker", "Kubernetes", "AWS", "GCP", "Azure", "CI/CD"} & set(scorecard.get("missing_skills", []))
        if deployment_related_missing:
            missing.append("No deployment evidence")
    return missing[:4]


def _derive_missing_evidence(
    candidate_intelligence: CandidateIntelligence,
    pillar_scores: dict[str, PillarScore],
) -> list[str]:
    missing = []
    if pillar_scores["technical_depth"].confidence == "Low":
        missing.append("Technical depth claims need more concrete implementation evidence.")
    if pillar_scores["ownership"].confidence == "Low":
        missing.append("Ownership scope is mentioned lightly and would benefit from stronger shipped-work proof.")
    if candidate_intelligence.supporting_signals.get("deployment_maturity", 0) < 45:
        missing.append("Production deployment ownership is not strongly evidenced.")
    if candidate_intelligence.supporting_signals.get("ai_capability", 0) >= 50 and pillar_scores["semantic_fit"].confidence == "Low":
        missing.append("AI implementation claims need clearer project-level evidence.")
    return missing[:4]


def _derive_interview_focus_areas(
    pillar_scores: dict[str, PillarScore],
    candidate_intelligence: CandidateIntelligence,
    missing_must_haves: list[str],
) -> list[str]:
    prompts = []
    if any("deployment" in gap.lower() for gap in missing_must_haves):
        prompts.append("Probe production deployment ownership")
    if pillar_scores["technical_depth"].score < 60:
        prompts.append("Validate scalability understanding")
    if pillar_scores["transferability"].score >= 65 and pillar_scores["semantic_fit"].score < 60:
        prompts.append("Test adjacent-skill ramp speed on the target stack")
    if pillar_scores["communication"].confidence == "Low":
        prompts.append("Confirm ability to clearly explain technical tradeoffs")
    if candidate_intelligence.supporting_signals.get("enterprise_readiness", 0) < 45:
        prompts.append("Assess testing and reliability discipline")
    return prompts[:4]


def _is_generic_insight(text: str) -> bool:
    lowered = (text or "").lower()
    return any(pattern in lowered for pattern in GENERIC_INSIGHT_PATTERNS)


def _strong_evidence_items(supporting_evidence: dict[str, list[EvidenceSnippet]]) -> list[EvidenceSnippet]:
    items = []
    seen = set()
    for snippets in supporting_evidence.values():
        for snippet in snippets or []:
            if snippet.evidence_id in seen:
                continue
            seen.add(snippet.evidence_id)
            if is_strong_evidence(snippet):
                items.append(snippet)
    items.sort(
        key=lambda item: (
            0 if item.source_type in {"project", "experience"} else 1,
            -(item.retrieval_score or 0.0),
        )
    )
    return items


def _evidence_quality_profile(supporting_evidence: dict[str, list[EvidenceSnippet]]) -> dict[str, object]:
    all_items = []
    for snippets in supporting_evidence.values():
        all_items.extend(snippets or [])
    if not all_items:
        return {
            "strong_count": 0,
            "weak_ratio": 1.0,
            "skills_or_summary_ratio": 1.0,
            "categories": set(),
        }

    strong_items = [item for item in all_items if is_strong_evidence(item)]
    weak_items = [
        item
        for item in all_items
        if classify_evidence(item.snippet, item.source_type).label == "weak"
    ]
    skills_or_summary = [item for item in all_items if item.source_type in {"skills", "summary"}]
    categories = {
        category
        for category in (evidence_category(item.snippet) for item in strong_items)
        if category
    }
    return {
        "strong_count": len(strong_items),
        "weak_ratio": round(len(weak_items) / len(all_items), 4),
        "skills_or_summary_ratio": round(len(skills_or_summary) / len(all_items), 4),
        "categories": categories,
    }


def _grounded_strengths(
    candidate_intelligence: CandidateIntelligence,
    scorecard: dict,
    supporting_evidence: dict[str, list[EvidenceSnippet]],
) -> list[str]:
    strengths = []
    for item in _strong_evidence_items(supporting_evidence):
        category = evidence_category(item.snippet)
        if not category:
            continue
        insight = _strength_from_evidence(item, category)
        if insight:
            strengths.append(insight)
        if len(strengths) >= 2:
            break

    return _dedupe_quality_insights(strengths, limit=2)


def _grounded_risks(
    scorecard: dict,
    candidate_intelligence: CandidateIntelligence,
    supporting_evidence: dict[str, list[EvidenceSnippet]],
    missing_must_haves: list[str],
) -> list[str]:
    quality = _evidence_quality_profile(supporting_evidence)
    categories = quality["categories"]
    risks = []

    if missing_must_haves:
        risks.append(_specific_must_have_risk(missing_must_haves))

    if quality["strong_count"] == 0:
        risks.append("Most evidence is skill-list or summary-level, so the recommendation should be treated as provisional.")
    elif "operational reliability" not in categories and "deployment ownership" in categories:
        risks.append("Deployment responsibility is visible, but monitoring, rollback, or incident ownership is not clearly evidenced.")
    elif "backend implementation" in categories and "operational reliability" not in categories:
        risks.append("Backend build evidence is credible, but production-scale operation or reliability ownership is not strongly demonstrated.")
    elif "AI retrieval implementation" in categories and "operational reliability" not in categories:
        risks.append("AI implementation is visible, but evaluation, failure handling, or production quality controls are not evidenced.")

    if candidate_intelligence.contradiction_flags and quality["weak_ratio"] >= 0.45:
        risks.extend(candidate_intelligence.contradiction_flags[:1])

    return _dedupe_quality_insights(risks, limit=2)


def _grounded_interview_focus(
    supporting_evidence: dict[str, list[EvidenceSnippet]],
    missing_must_haves: list[str],
) -> list[str]:
    quality = _evidence_quality_profile(supporting_evidence)
    categories = quality["categories"]
    prompts = []

    if "realtime systems" in categories and "operational reliability" not in categories:
        prompts.append("Ask how the realtime system handled reconnects, contention, and failure recovery.")
    if "deployment ownership" in categories and "operational reliability" not in categories:
        prompts.append("Ask what monitoring, rollback, or incident handling existed after deployment.")
    if "AI retrieval implementation" in categories:
        prompts.append("Ask how retrieval quality was evaluated and what failure cases were observed.")
    for gap in missing_must_haves:
        lowered = gap.lower()
        if "sql" in lowered:
            prompts.append("Ask for a concrete SQL schema, query, or performance tuning example.")
        elif "react" in lowered:
            prompts.append("Ask them to walk through a recent React or Next.js feature they owned end to end.")
        elif "deployment" in lowered:
            prompts.append("Ask which deployments they personally owned and what broke in production.")
        elif "missing" in lowered or "limited" in lowered:
            prompts.append(f"Probe the closest project evidence for {gap.replace('Missing ', '').replace('Limited ', '').lower()}.")

    return _dedupe_quality_insights(prompts, limit=2)


def _matched_concepts(text: str, category: str, limit: int = 3) -> list[str]:
    lowered = (text or "").lower()
    concepts = []
    for concept in CATEGORY_CONCEPTS.get(category, ()):
        if concept in lowered:
            concepts.append(concept)
        if len(concepts) >= limit:
            break
    return concepts


def _strength_from_evidence(item: EvidenceSnippet, category: str) -> str:
    concepts = _matched_concepts(item.snippet, category)
    if not concepts:
        return ""
    concept_text = ", ".join(concepts)
    if category == "deployment ownership":
        return f"{item.source_label} shows hands-on deployment responsibility through {concept_text}."
    if category == "AI retrieval implementation":
        return f"{item.source_label} gives concrete AI systems evidence through {concept_text}."
    if category == "realtime systems":
        return f"{item.source_label} demonstrates realtime system depth through {concept_text}."
    if category == "backend implementation":
        return f"{item.source_label} shows backend implementation depth through {concept_text}."
    if category == "frontend product execution":
        return f"{item.source_label} shows product UI delivery through {concept_text}."
    if category == "operational reliability":
        return f"{item.source_label} includes operational maturity evidence through {concept_text}."
    return ""


def _specific_must_have_risk(missing_must_haves: list[str]) -> str:
    if not missing_must_haves:
        return ""
    if len(missing_must_haves) == 1:
        return f"{missing_must_haves[0]} limits shortlist confidence for this role."
    return f"Must-have gaps remain in {', '.join(missing_must_haves[:2])}."


def _trust_calibrated_summary(
    candidate_name: str,
    recommendation: str,
    pillar_scores: dict[str, PillarScore],
    supporting_evidence: dict[str, list[EvidenceSnippet]],
    missing_must_haves: list[str],
) -> str:
    quality = _evidence_quality_profile(supporting_evidence)
    strong_items = _strong_evidence_items(supporting_evidence)
    lead = strong_items[0] if strong_items else None

    if lead:
        category = evidence_category(lead.snippet) or "implementation evidence"
        concepts = _matched_concepts(lead.snippet, category)
        if concepts:
            base = f"{candidate_name} is most compelling where {lead.source_label} shows {', '.join(concepts[:3])}"
        else:
            base = f"{candidate_name} has credible {category} from {lead.source_label}"
    else:
        base = f"{candidate_name} has limited strong implementation evidence"

    if missing_must_haves:
        return base + f", but {missing_must_haves[0].lower()} keeps the recommendation from being stronger."

    if quality["strong_count"] == 0 or quality["skills_or_summary_ratio"] >= 0.55:
        return base + "; treat the recommendation as provisional until project-level ownership is validated."

    semantic_score = pillar_scores.get("semantic_fit", PillarScore()).score
    technical_score = pillar_scores.get("technical_depth", PillarScore()).score
    if recommendation in {"Highly Recommended", "Recommended"} and min(semantic_score, technical_score) >= 65:
        return base + " and the evidence is strong enough to justify prioritized recruiter review."

    return base + ", but the evidence is not yet deep enough for an assertive decision."


def _calibrated_confidence(current: str, supporting_evidence: dict[str, list[EvidenceSnippet]]) -> str:
    quality = _evidence_quality_profile(supporting_evidence)
    if quality["strong_count"] == 0 or quality["weak_ratio"] >= 0.70:
        return "Low"
    if current == "High" and (quality["strong_count"] < 2 or quality["skills_or_summary_ratio"] >= 0.45):
        return "Medium"
    return current


def _calibrated_recommendation(current: str, supporting_evidence: dict[str, list[EvidenceSnippet]], missing_must_haves: list[str]) -> str:
    quality = _evidence_quality_profile(supporting_evidence)
    if current == "Highly Recommended" and (missing_must_haves or quality["strong_count"] < 2):
        return "Recommended"
    if current == "Recommended" and quality["strong_count"] == 0:
        return "Consider for Interview"
    return current


def _dedupe_quality_insights(items: list[str], limit: int) -> list[str]:
    deduped = []
    seen_shapes = set()
    for item in items:
        if not item or _is_generic_insight(item):
            continue
        shape = " ".join(item.lower().split()[:5])
        if shape in seen_shapes:
            continue
        seen_shapes.add(shape)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def _build_strengths(
    pillar_scores: dict[str, PillarScore],
    scorecard: dict,
    candidate_intelligence: CandidateIntelligence,
) -> list[str]:
    strengths = []
    if pillar_scores["semantic_fit"].score >= 70:
        strengths.append("Strong semantic alignment with the role's core responsibilities.")
    if pillar_scores["technical_depth"].score >= 68:
        strengths.append("Technical stack depth is backed by implementation-level evidence.")
    if pillar_scores["ownership"].score >= 65:
        strengths.append("Shows credible ownership signals across project or delivery work.")
    if pillar_scores["execution_maturity"].score >= 65:
        strengths.append("Execution maturity is visible through shipped or deployment-oriented work.")
    if pillar_scores["transferability"].score >= 68 and scorecard.get("adjacent_matches"):
        strengths.append("Transferable skills reduce the risk of exact-stack gaps.")
    if candidate_intelligence.supporting_signals.get("ai_capability", 0) >= 60:
        strengths.append("AI-related implementation experience strengthens product-building upside.")
    return strengths[:5]


def _build_risks(
    scorecard: dict,
    candidate_intelligence: CandidateIntelligence,
    missing_must_haves: list[str],
) -> list[str]:
    risks = []
    risks.extend(missing_must_haves[:2])
    risks.extend(candidate_intelligence.contradiction_flags[:2])
    if scorecard.get("semantic_score", 0) < 55:
        risks.append("Direct role alignment is weaker than stronger candidates in the pool.")
    if scorecard.get("project_relevance_score", 0) < 55:
        risks.append("Project-level relevance is not consistently strong enough to remove execution doubt.")
    return list(dict.fromkeys(risks))[:5]


def _build_why_not_selected(
    pillar_scores: dict[str, PillarScore],
    missing_must_haves: list[str],
    contradiction_flags: list[str],
) -> list[str]:
    reasons = []
    if missing_must_haves:
        reasons.append(_specific_must_have_risk(missing_must_haves))
    if pillar_scores["semantic_fit"].score < 60:
        reasons.append("The resume shows weaker direct evidence against the role's core responsibilities than stronger candidates.")
    if contradiction_flags:
        reasons.append("Some resume claims need validation before this profile can be safely prioritized.")
    if pillar_scores["execution_maturity"].confidence == "Low":
        reasons.append("Execution maturity is plausible, but the resume does not show enough shipped-work evidence.")
    return reasons[:4]


def _build_decision_summary(
    pillar_scores: dict[str, PillarScore],
    missing_must_haves: list[str],
) -> str:
    positives = []
    if pillar_scores["ownership"].score >= 65:
        positives.append("ownership")
    if pillar_scores["execution_maturity"].score >= 65:
        positives.append("execution maturity")
    if pillar_scores["transferability"].score >= 65:
        positives.append("transferable architecture experience")
    if pillar_scores["semantic_fit"].score >= 70:
        positives.append("direct role alignment")
    if not positives:
        positives.append("adjacent fit potential")

    tail = ""
    if missing_must_haves:
        tail = " despite some must-have gaps."
    elif pillar_scores["semantic_fit"].score < 60:
        tail = " despite weaker exact stack alignment."
    else:
        tail = "."
    return "Recommended because of strong " + ", ".join(positives[:3]) + tail


def _build_ats_reasoning(scorecard: dict, pillar_scores: dict[str, PillarScore]) -> str | None:
    if scorecard.get("keyword_score", 0) < 55 and pillar_scores["transferability"].score >= 65:
        return (
            "Traditional keyword ATS may underrate this candidate because exact term overlap is lighter, "
            "but project evidence shows meaningful transferable technical capability."
        )
    return None


def _build_pillar_scores(
    scorecard: dict,
    candidate_intelligence: CandidateIntelligence,
    evidence_library: dict[str, EvidenceSnippet],
    missing_must_haves: list[str],
    retrieval_context: "RetrievalContext | None" = None,
) -> dict[str, PillarScore]:
    project_evidence = _evidence_for_sources(evidence_library, {"project", "experience"})
    summary_evidence = _evidence_for_sources(evidence_library, {"summary", "skills"})
    education_evidence = _evidence_for_sources(evidence_library, {"education"})

    pillar_evidence = {
        "semantic_fit": project_evidence,
        "technical_depth": project_evidence + summary_evidence[:1],
        "ownership": project_evidence + summary_evidence[:1],
        "execution_maturity": project_evidence,
        "learning_velocity": project_evidence + education_evidence[:1],
        "startup_readiness": project_evidence + summary_evidence[:1],
        "transferability": project_evidence + summary_evidence[:1],
        "communication": summary_evidence,
        "domain_relevance": project_evidence + summary_evidence[:1],
        "risk": summary_evidence,
    }

    pillar_values = {
        "semantic_fit": scorecard.get("semantic_score", 0.0),
        "technical_depth": _bounded_score(
            (scorecard.get("keyword_score", 0.0) * 0.35)
            + (scorecard.get("project_relevance_score", 0.0) * 0.35)
            + (candidate_intelligence.core_signals.get("technical_depth", 0.0) * 0.2)
            + (candidate_intelligence.supporting_signals.get("deployment_maturity", 0.0) * 0.1)
        ),
        "ownership": _bounded_score(candidate_intelligence.core_signals.get("ownership", 0.0)),
        "execution_maturity": _bounded_score(
            (candidate_intelligence.core_signals.get("execution_maturity", 0.0) * 0.55)
            + (scorecard.get("project_relevance_score", 0.0) * 0.25)
            + (scorecard.get("deployment_score", 0.0) * 0.20)
        ),
        "learning_velocity": _bounded_score(candidate_intelligence.core_signals.get("learning_velocity", 0.0)),
        "startup_readiness": _bounded_score(
            (candidate_intelligence.core_signals.get("startup_readiness", 0.0) * 0.50)
            + (candidate_intelligence.core_signals.get("ownership", 0.0) * 0.20)
            + (candidate_intelligence.core_signals.get("execution_maturity", 0.0) * 0.15)
            + (candidate_intelligence.supporting_signals.get("adaptability", 0.0) * 0.15)
        ),
        "transferability": _bounded_score(
            (candidate_intelligence.core_signals.get("transferability", 0.0) * 0.55)
            + (scorecard.get("adjacency_bonus", 0.0) * 4.0)
            + (candidate_intelligence.supporting_signals.get("adaptability", 0.0) * 0.20)
        ),
        "communication": _bounded_score(candidate_intelligence.core_signals.get("communication", 0.0)),
        "domain_relevance": _bounded_score(candidate_intelligence.core_signals.get("domain_relevance", 0.0)),
        "risk": _score_risk(scorecard, candidate_intelligence.contradiction_flags, missing_must_haves),
    }

    pillar_scores = {}
    contradiction_count = len(candidate_intelligence.contradiction_flags)
    for name in CORE_PILLARS:
        evidence_items = (
            retrieval_context.pillar_evidence.get(name, [])
            if retrieval_context and retrieval_context.pillar_evidence.get(name)
            else pillar_evidence.get(name, [])
        )
        score_value = pillar_values[name]
        if retrieval_context and retrieval_context.pillar_scores.get(name) and name != "risk":
            retrieval_average = _safe_ratio(sum(retrieval_context.pillar_scores[name]), len(retrieval_context.pillar_scores[name])) * 100
            score_value = _bounded_score((score_value * 0.72) + (retrieval_average * 0.28))
        pillar_scores[name] = PillarScore(
            score=score_value,
            confidence=_confidence_label(evidence_items, contradiction_count if name != "risk" else 0),
            summary=name.replace("_", " ").title(),
            evidence_ids=[item.evidence_id for item in evidence_items],
        )
    return pillar_scores


def build_ranking_result(
    profile: CandidateProfile,
    job_intelligence: JobIntelligence,
    candidate_intelligence: CandidateIntelligence,
    scorecard: dict,
    evidence_library: dict[str, EvidenceSnippet],
    retrieval_context: "RetrievalContext | None" = None,
) -> RankingResult:
    missing_must_haves = _derive_missing_must_haves(scorecard, candidate_intelligence, evidence_library)
    pillar_scores = _build_pillar_scores(
        scorecard,
        candidate_intelligence,
        evidence_library,
        missing_must_haves,
        retrieval_context=retrieval_context,
    )
    missing_evidence = _derive_missing_evidence(candidate_intelligence, pillar_scores)
    interview_focus_areas = _derive_interview_focus_areas(pillar_scores, candidate_intelligence, missing_must_haves)
    strengths = _build_strengths(pillar_scores, scorecard, candidate_intelligence)
    risks = _build_risks(scorecard, candidate_intelligence, missing_must_haves)
    why_not_selected = _build_why_not_selected(
        pillar_scores,
        missing_must_haves,
        candidate_intelligence.contradiction_flags,
    )
    supporting_evidence = {}
    for pillar, score in pillar_scores.items():
        retrieved = retrieval_context.pillar_evidence.get(pillar, []) if retrieval_context else []
        if retrieved:
            supporting_evidence[pillar] = retrieved
        else:
            supporting_evidence[pillar] = [
                evidence_library[evidence_id]
                for evidence_id in score.evidence_ids
                if evidence_id in evidence_library
            ]

    grounded_strengths = _grounded_strengths(candidate_intelligence, scorecard, supporting_evidence)
    grounded_risks = _grounded_risks(
        scorecard,
        candidate_intelligence,
        supporting_evidence,
        missing_must_haves,
    )
    grounded_interview_focus = _grounded_interview_focus(supporting_evidence, missing_must_haves)
    if grounded_strengths:
        strengths = grounded_strengths
    else:
        strengths = []
    risks = grounded_risks
    interview_focus_areas = grounded_interview_focus
    missing_evidence = _dedupe_quality_insights(missing_evidence, limit=2)
    calibrated_confidence = _calibrated_confidence(
        scorecard.get("recruiter_confidence", "Low"),
        supporting_evidence,
    )
    calibrated_recommendation = _calibrated_recommendation(
        scorecard.get("recommendation", "Low Match"),
        supporting_evidence,
        missing_must_haves,
    )
    recruiter_decision_summary = _trust_calibrated_summary(
        profile.name,
        calibrated_recommendation,
        pillar_scores,
        supporting_evidence,
        missing_must_haves,
    )

    result = RankingResult(
        final_score=scorecard.get("final_score", 0.0),
        recommendation=calibrated_recommendation,
        recruiter_confidence=calibrated_confidence,
        pillar_scores=pillar_scores,
        strengths=strengths,
        risks=risks,
        missing_must_haves=missing_must_haves,
        missing_evidence=missing_evidence,
        why_not_selected=why_not_selected,
        interview_focus_areas=interview_focus_areas,
        supporting_evidence_snippets=supporting_evidence,
        hidden_gem_flag=scorecard.get("hidden_gem_flag", False),
        recruiter_decision_summary=recruiter_decision_summary,
        ats_vs_intelligence_reasoning=_build_ats_reasoning(scorecard, pillar_scores),
        semantic_score=scorecard.get("semantic_score", 0.0),
        keyword_score=scorecard.get("keyword_score", 0.0),
        adjacency_bonus=scorecard.get("adjacency_bonus", 0.0),
        project_relevance_score=scorecard.get("project_relevance_score", 0.0),
        deployment_score=scorecard.get("deployment_score", 0.0),
        ai_experience_score=scorecard.get("ai_experience_score", 0.0),
        confidence_score=scorecard.get("confidence_score", 0.0),
        matched_skills=scorecard.get("matched_skills", []),
        missing_skills=scorecard.get("missing_skills", []),
        adjacent_matches=[AdjacentMatch(**match) for match in scorecard.get("adjacent_matches", [])],
        weaknesses=risks,
        recruiter_summary=recruiter_decision_summary,
        scoring_diagnostics=scorecard.get("scoring_diagnostics", {}),
    )
    return result


def annotate_ranked_order(ranked_candidates: list[dict]) -> None:
    if not ranked_candidates:
        return

    winner = ranked_candidates[0]
    winner_ranking = winner["ranking"]
    winner_ranking["reasons_ranked_below_stronger_candidates"] = []

    for index, candidate in enumerate(ranked_candidates[1:], start=1):
        current = candidate["ranking"]
        stronger = ranked_candidates[index - 1]["ranking"]
        reasons = []
        for pillar in ("execution_maturity", "technical_depth", "ownership", "semantic_fit"):
            stronger_score = stronger["pillar_scores"][pillar]["score"]
            current_score = current["pillar_scores"][pillar]["score"]
            if stronger_score - current_score >= 8:
                reasons.append(_rank_below_reason(pillar, stronger, current))
                break
        if not reasons and current["missing_must_haves"]:
            reasons.append(_specific_must_have_risk(current["missing_must_haves"]))
        if not reasons and current["recruiter_confidence"] == "Low":
            reasons.append("Ranked lower because the supporting evidence is thinner or less implementation-specific.")
        current["reasons_ranked_below_stronger_candidates"] = reasons[:3]

        if not current["why_not_selected"]:
            current["why_not_selected"] = reasons[:2]


def build_pairwise_comparison(left: dict, right: dict) -> dict:
    from backend.reasoning.ranking_trust import compare_candidates_pairwise

    left_ranking = left["ranking"]
    right_ranking = right["ranking"]
    initial_pairwise = compare_candidates_pairwise(left, right)
    if initial_pairwise["preferred"] == "left":
        winner = left
    elif initial_pairwise["preferred"] == "right":
        winner = right
    else:
        winner = left if left_ranking["final_score"] >= right_ranking["final_score"] else right
    loser = right if winner is left else left
    winner_ranking = winner["ranking"]
    loser_ranking = loser["ranking"]
    pairwise = compare_candidates_pairwise(winner, loser)

    differences = []
    for pillar in ("execution_maturity", "technical_depth", "ownership", "transferability", "semantic_fit"):
        winner_score = winner_ranking["pillar_scores"][pillar]["score"]
        loser_score = loser_ranking["pillar_scores"][pillar]["score"]
        delta = abs(winner_score - loser_score)
        if delta >= 5:
            differences.append(_pairwise_difference_text(pillar, winner, loser))
    if not differences:
        if pairwise["confidence"] == "Low":
            differences.append(
                f"{winner['candidate_name']} and {loser['candidate_name']} are close; ordering depends on the small evidence-quality edge visible in the current resume evidence."
            )

    return {
        "winner": winner["candidate_name"],
        "loser": loser["candidate_name"],
        "winner_summary": winner_ranking["recruiter_decision_summary"],
        "loser_summary": loser_ranking["recruiter_decision_summary"],
        "key_differences": [pairwise["rationale"]] + differences[:3],
        "ordering_confidence": pairwise["confidence"],
        "winner_strengths": winner_ranking["strengths"][:3],
        "loser_risks": loser_ranking["risks"][:3],
    }


def _rank_below_reason(pillar: str, stronger: dict, current: dict) -> str:
    labels = {
        "execution_maturity": "less shipped or production-oriented execution evidence",
        "technical_depth": "less implementation depth in the resume evidence",
        "ownership": "less evidence of end-to-end ownership",
        "semantic_fit": "less direct evidence for the role's core responsibilities",
        "transferability": "less credible transfer evidence from adjacent work",
    }
    return f"Ranked lower because this profile shows {labels.get(pillar, 'weaker supporting evidence')} than the candidate above."


def _pairwise_difference_text(pillar: str, winner: dict, loser: dict) -> str:
    labels = {
        "execution_maturity": "stronger shipped-work or production execution evidence",
        "technical_depth": "deeper implementation evidence",
        "ownership": "clearer end-to-end ownership evidence",
        "transferability": "more credible adjacent capability evidence",
        "semantic_fit": "more direct evidence against the role's core responsibilities",
    }
    return f"{winner['candidate_name']} separates from {loser['candidate_name']} through {labels.get(pillar, 'stronger evidence')}."
