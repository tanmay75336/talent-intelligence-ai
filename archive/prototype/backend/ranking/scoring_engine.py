from dataclasses import dataclass
import logging
import math
from typing import TYPE_CHECKING

from backend.ranking.recruiter_reasoning import build_recruiter_reasoning
from backend.utils.embeddings import calculate_similarity_between_text_sets
from backend.utils.skill_taxonomy import (
    extract_skills_from_text,
    get_active_groups,
    get_group_matches,
    infer_adjacent_matches,
    infer_ecosystem_matches,
    unique_preserve_order,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.retrieval.evidence_retriever import RetrievalContext


@dataclass
class ScoringWeights:
    skills_overlap: float = 0.28
    project_relevance: float = 0.24
    semantic_alignment: float = 0.18
    deployment_experience: float = 0.12
    ai_api_experience: float = 0.10
    adjacency_transferability: float = 0.08


DEFAULT_WEIGHTS = ScoringWeights()

IMPLEMENTATION_VERBS = {
    "built",
    "developed",
    "implemented",
    "integrated",
    "deployed",
    "shipped",
    "owned",
    "architected",
    "launched",
    "automated",
    "optimized",
    "designed",
    "delivered",
    "created",
    "managed",
    "improved",
}

ARCHITECTURE_TERMS = {
    "api",
    "apis",
    "backend",
    "database",
    "postgresql",
    "supabase",
    "pipeline",
    "pipelines",
    "deployment",
    "docker",
    "ci/cd",
    "monitoring",
    "semantic",
    "retrieval",
    "embeddings",
    "llm",
    "integration",
    "integrations",
    "services",
    "production",
    "frontend",
    "dashboard",
    "dashboards",
    "ui",
    "react",
    "next.js",
    "typescript",
    "customer-facing",
    "performance",
}


def _safe_ratio(numerator, denominator):
    if denominator <= 0:
        return 0.0

    return numerator / denominator


def _clamp_score(value):
    return round(max(0.0, min(100.0, value)), 2)


def _normalize_final_score(raw_score):
    bounded_score = max(0.0, min(100.0, raw_score))
    if bounded_score <= 12:
        blended_score = (bounded_score * 0.82) + 0.5
    elif bounded_score <= 25:
        blended_score = (bounded_score * 0.90) + 1.2
    elif bounded_score <= 40:
        blended_score = (bounded_score * 0.96) + 4.0
    elif bounded_score <= 65:
        blended_score = (bounded_score * 1.01) + 6.0
    else:
        blended_score = (bounded_score * 0.92) + 9.0

    return _clamp_score(min(blended_score, 95.0))


def _infer_confidence(final_score, component_scores):
    high_components = sum(1 for score in component_scores if score >= 70)
    moderate_components = sum(1 for score in component_scores if score >= 55)

    if final_score >= 80 and high_components >= 3:
        return "High"

    if final_score >= 60 or moderate_components >= 3:
        return "Medium"

    return "Low"


def _confidence_score(component_scores, final_score):
    if not component_scores:
        return 0.0

    average_score = sum(component_scores) / len(component_scores)
    spread = max(component_scores) - min(component_scores)
    consistency_score = max(0.0, 100.0 - (spread * 0.9))
    confidence_score = (average_score * 0.62) + (consistency_score * 0.24) + (final_score * 0.14)

    return _clamp_score(confidence_score)


def _group_coverage_ratio(candidate_skills, jd_skills):
    jd_groups = set(get_active_groups(jd_skills))
    if not jd_groups:
        return 0.0

    candidate_groups = set(get_active_groups(candidate_skills))
    return _safe_ratio(len(candidate_groups & jd_groups), len(jd_groups))


def _transfer_coverage_ratio(target_skills, candidate_skills):
    if not target_skills:
        return 0.0

    adjacent_matches = infer_adjacent_matches(target_skills, candidate_skills)
    ecosystem_matches = infer_ecosystem_matches(target_skills, candidate_skills)
    covered_skills = {
        match["missing_skill"]
        for match in adjacent_matches + ecosystem_matches
    }

    return _safe_ratio(len(covered_skills), len(target_skills))


def _exact_support_ratio(skill_result, retrieval_context: "RetrievalContext | None" = None):
    direct_ratio = float(skill_result.get("required_direct_ratio", 0.0) or 0.0)
    coverage = getattr(retrieval_context, "must_have_coverage", {}) if retrieval_context else {}
    if not coverage:
        return direct_ratio
    strong_coverage = _safe_ratio(
        sum(1 for score in coverage.values() if float(score or 0.0) >= 0.75),
        len(coverage),
    )
    return round(max(direct_ratio, strong_coverage), 4)


def _weak_must_have_ratio(retrieval_context: "RetrievalContext | None" = None):
    coverage = getattr(retrieval_context, "must_have_coverage", {}) if retrieval_context else {}
    if not coverage:
        return 0.0
    weak_count = sum(1 for score in coverage.values() if float(score or 0.0) < 0.2)
    return round(_safe_ratio(weak_count, len(coverage)), 4)


def _retrieval_project_experience_ratio(retrieval_context: "RetrievalContext | None", pillar: str):
    if not retrieval_context:
        return 0.0
    evidence = retrieval_context.pillar_evidence.get(pillar, [])
    if not evidence:
        return 0.0
    authoritative = [item for item in evidence if item.source_type in {"project", "experience"}]
    return round(_safe_ratio(len(authoritative), len(evidence)), 4)


def _generic_engineering_penalty(profile, jd_analysis):
    evidence_text = " ".join(profile.projects + profile.experience).lower()
    if not evidence_text:
        evidence_text = (profile.summary or profile.raw_text or "").lower()
    tokens = [token.strip(".,:;()[]{}").lower() for token in evidence_text.split()]
    token_count = max(1, len(tokens))
    implementation_count = sum(1 for verb in IMPLEMENTATION_VERBS if verb in evidence_text)
    architecture_count = sum(1 for term in ARCHITECTURE_TERMS if term in evidence_text)
    skill_count = len(profile.skills)
    skill_density = min(1.0, skill_count / token_count)
    deployment_support = bool(set(profile.deployment_signals) & set(jd_analysis.deployment_keywords)) or bool(profile.deployment_signals)

    penalty = 0.0
    reasons = []
    if implementation_count <= 1:
        penalty += 0.08
        reasons.append("low_implementation_verb_density")
    if architecture_count <= 2:
        penalty += 0.07
        reasons.append("low_architecture_specificity")
    if skill_density >= 0.16 and implementation_count <= 2:
        penalty += 0.06
        reasons.append("high_skill_density_weak_support")
    if jd_analysis.deployment_keywords and not deployment_support:
        penalty += 0.05
        reasons.append("weak_deployment_evidence")

    return min(0.22, penalty), reasons


def _determine_recommendation(final_score, hidden_gem_flag):
    if hidden_gem_flag and final_score >= 60:
        return "Hidden Gem"

    if final_score >= 85:
        return "Highly Recommended"

    if final_score >= 70:
        return "Recommended"

    if final_score >= 50:
        return "Consider for Interview"

    return "Low Match"


def _seniority_penalty(profile, jd_analysis):
    if "senior" in jd_analysis.seniority_indicators and profile.seniority_band in {
        "student",
        "entry",
    }:
        return 6.0

    if "mid" in jd_analysis.seniority_indicators and profile.seniority_band == "student":
        return 3.0

    return 0.0


def _score_skills_overlap(profile, jd_analysis):
    candidate_skills = set(profile.skills)
    required_skills = jd_analysis.required_skills or jd_analysis.all_skills
    preferred_skills = [
        skill for skill in jd_analysis.preferred_skills if skill not in required_skills
    ]

    matched_required = [skill for skill in required_skills if skill in candidate_skills]
    missing_required = [skill for skill in required_skills if skill not in candidate_skills]
    matched_preferred = [skill for skill in preferred_skills if skill in candidate_skills]
    adjacent_matches = infer_adjacent_matches(missing_required, profile.skills)
    ecosystem_matches = infer_ecosystem_matches(missing_required, profile.skills)

    adjacent_coverage = len({item["missing_skill"] for item in adjacent_matches})
    ecosystem_coverage = len({item["missing_skill"] for item in ecosystem_matches})
    required_direct_ratio = _safe_ratio(len(matched_required), len(required_skills))
    required_effective_ratio = _safe_ratio(
        len(matched_required) + (0.70 * adjacent_coverage) + (0.45 * ecosystem_coverage),
        len(required_skills),
    )
    ecosystem_ratio = _safe_ratio(ecosystem_coverage, len(required_skills))
    preferred_ratio = (
        _safe_ratio(len(matched_preferred), len(preferred_skills))
        if preferred_skills
        else required_effective_ratio
    )
    transferable_ratio = _safe_ratio(adjacent_coverage + ecosystem_coverage, len(required_skills))
    group_coverage_ratio = _group_coverage_ratio(profile.skills, jd_analysis.all_skills)

    frontend_match = bool(get_group_matches(profile.skills, "frontend"))
    backend_match = bool(get_group_matches(profile.skills, "backend"))
    database_match = bool(get_group_matches(profile.skills, "database"))
    deployment_match = bool(get_group_matches(profile.skills, "deployment"))
    api_match = bool(get_group_matches(profile.skills, "api"))
    full_stack_bonus = (
        6.0 if frontend_match and backend_match else 0.0
    ) + (3.0 if frontend_match and backend_match and database_match else 0.0)
    platform_bonus = 5.0 if backend_match and deployment_match and api_match else 0.0
    frontend_bonus = 4.0 if frontend_match and len(get_group_matches(profile.skills, "frontend")) >= 3 else 0.0

    keyword_score = _clamp_score(
        (required_direct_ratio * 50)
        + (required_effective_ratio * 15)
        + (ecosystem_ratio * 10)
        + (preferred_ratio * 10)
        + (transferable_ratio * 8)
        + (group_coverage_ratio * 16)
        + full_stack_bonus
        + platform_bonus
        + frontend_bonus
    )

    return {
        "keyword_score": keyword_score,
        "required_direct_ratio": round(required_direct_ratio, 4),
        "required_effective_ratio": round(required_effective_ratio, 4),
        "preferred_ratio": round(preferred_ratio, 4),
        "group_coverage_ratio": round(group_coverage_ratio, 4),
        "matched_skills": unique_preserve_order(matched_required + matched_preferred),
        "missing_skills": missing_required,
        "adjacent_matches": adjacent_matches,
        "ecosystem_matches": ecosystem_matches,
    }


def _score_project_relevance(profile, jd_analysis, retrieval_context: "RetrievalContext | None" = None):
    if retrieval_context and retrieval_context.pillar_scores.get("semantic_fit"):
        suppression_penalty = _retrieval_suppression_penalty(retrieval_context)
        semantic_fit_scores = retrieval_context.pillar_scores.get("semantic_fit", [])
        execution_scores = retrieval_context.pillar_scores.get("execution_maturity", [])
        technical_scores = retrieval_context.pillar_scores.get("technical_depth", [])
        aggregate = (
            (_safe_ratio(sum(semantic_fit_scores), len(semantic_fit_scores) or 1) * 100 * 0.52)
            + (_safe_ratio(sum(execution_scores), len(execution_scores) or 1) * 100 * 0.28)
            + (_safe_ratio(sum(technical_scores), len(technical_scores) or 1) * 100 * 0.20)
        )
        if suppression_penalty:
            aggregate *= 1.0 - (suppression_penalty * 0.55)
        return _clamp_score(aggregate)

    project_texts = profile.projects or profile.experience or [profile.summary or profile.raw_text]
    target_texts = jd_analysis.responsibilities or jd_analysis.semantic_targets()
    semantic_targets = unique_preserve_order(target_texts + [jd_analysis.raw_text])
    target_skills = jd_analysis.required_skills or jd_analysis.all_skills
    preferred_skills = jd_analysis.preferred_skills

    project_scores = []

    for project_text in project_texts[:6]:
        project_skills = extract_skills_from_text(project_text)
        required_overlap = _safe_ratio(
            len(set(project_skills) & set(target_skills)),
            len(target_skills),
        )
        preferred_overlap = (
            _safe_ratio(
                len(set(project_skills) & set(preferred_skills)),
                len(preferred_skills),
            )
            if preferred_skills
            else required_overlap
        )
        semantic_result = calculate_similarity_between_text_sets(
            [project_text],
            semantic_targets,
            return_diagnostics=True,
        )
        semantic_score = semantic_result["score"]
        domain_overlap = len(
            [
                keyword
                for keyword in jd_analysis.domain_keywords
                if keyword and keyword.lower() in project_text.lower()
            ]
        )
        frontend_bonus = 4 if get_group_matches(project_skills, "frontend") else 0
        backend_bonus = 4 if get_group_matches(project_skills, "backend") else 0
        deployment_bonus = 10 if get_group_matches(project_skills, "deployment") else 0
        ai_bonus = 6 if get_group_matches(project_skills, "ai") else 0
        api_bonus = 5 if get_group_matches(project_skills, "api") else 0
        domain_bonus = min(8, domain_overlap * 2)
        group_support_ratio = _group_coverage_ratio(project_skills, jd_analysis.all_skills)
        transferable_support_ratio = _transfer_coverage_ratio(target_skills, project_skills)
        platform_delivery_bonus = (
            8
            if get_group_matches(project_skills, "deployment")
            and get_group_matches(project_skills, "backend")
            else 0
        )

        project_score = _clamp_score(
            (required_overlap * 32)
            + (preferred_overlap * 10)
            + (semantic_score * 0.36)
            + (group_support_ratio * 100 * 0.12)
            + (transferable_support_ratio * 100 * 0.08)
            + frontend_bonus
            + backend_bonus
            + deployment_bonus
            + ai_bonus
            + api_bonus
            + domain_bonus
            + platform_delivery_bonus
        )
        project_scores.append(project_score)

    if not project_scores:
        return 0.0

    ordered_scores = sorted(project_scores, reverse=True)
    top_scores = ordered_scores[: min(2, len(ordered_scores))]
    return _clamp_score(sum(top_scores) / len(top_scores))


def _score_semantic_alignment(profile, jd_analysis, retrieval_context: "RetrievalContext | None" = None):
    if retrieval_context and retrieval_context.pillar_scores.get("semantic_fit"):
        suppression_penalty = _retrieval_suppression_penalty(retrieval_context)
        semantic_scores = retrieval_context.pillar_scores.get("semantic_fit", [])
        transfer_scores = retrieval_context.pillar_scores.get("transferability", [])
        technical_scores = retrieval_context.pillar_scores.get("technical_depth", [])
        evidence_count = len(retrieval_context.pillar_evidence.get("semantic_fit", []))
        aggregate = (
            (_safe_ratio(sum(semantic_scores), len(semantic_scores) or 1) * 100 * 0.58)
            + (_safe_ratio(sum(transfer_scores), len(transfer_scores) or 1) * 100 * 0.22)
            + (_safe_ratio(sum(technical_scores), len(technical_scores) or 1) * 100 * 0.20)
        )
        if suppression_penalty:
            aggregate *= 1.0 - (suppression_penalty * 0.72)
        return {
            "score": _clamp_score(aggregate),
            "diagnostics": {
                "section_scores": {"retrieved_evidence": round(_clamp_score(aggregate), 2)},
                "section_weights_used": {"retrieval_semantic": 1.0},
                "top_section": "retrieved_evidence",
                "section_details": {
                    "retrieved_evidence": {
                        "mode": "retrieval_embedding",
                        "aggregate_similarity": round(_safe_ratio(sum(semantic_scores), len(semantic_scores) or 1), 4),
                        "source_focus": round(_safe_ratio(sum(semantic_scores), len(semantic_scores) or 1), 4),
                        "target_focus": round(_safe_ratio(sum(transfer_scores), len(transfer_scores) or 1), 4),
                        "coverage_ratio": round(min(1.0, evidence_count / 3), 4),
                        "lexical_alignment": 0.0,
                        "source_chunks": evidence_count,
                        "target_chunks": len(jd_analysis.semantic_targets()),
                        "top_source_matches": [round(float(score), 4) for score in semantic_scores[:5]],
                        "top_target_matches": [round(float(score), 4) for score in transfer_scores[:5]],
                        "raw_section_score": round(_clamp_score(aggregate), 2),
                        "calibrated_section_score": round(_clamp_score(aggregate), 2),
                        "skill_support_ratio": round(_safe_ratio(len(profile.skills), max(1, len(jd_analysis.all_skills))), 4),
                        "group_support_ratio": round(_group_coverage_ratio(profile.skills, jd_analysis.all_skills), 4),
                        "transfer_support_ratio": round(_safe_ratio(sum(transfer_scores), len(transfer_scores) or 1), 4),
                        "domain_support_ratio": round(_safe_ratio(len(jd_analysis.domain_keywords), 10), 4),
                    }
                },
                "retrieval_diagnostics": retrieval_context.diagnostics,
                "calibration_floor_applied": 0.0,
                "must_have_gap_penalty": suppression_penalty,
            },
        }

    jd_targets = jd_analysis.semantic_targets()
    section_scores = []
    section_diagnostics = {}
    jd_skill_set = set(jd_analysis.all_skills)

    section_pairs = [
        (
            "projects",
            profile.projects or profile.experience or [profile.summary or profile.raw_text],
            jd_analysis.responsibilities or jd_targets,
            0.45,
        ),
        (
            "experience",
            profile.experience or profile.projects or [profile.summary or profile.raw_text],
            jd_analysis.responsibilities or jd_targets,
            0.25,
        ),
        (
            "skills",
            ["Skills: " + ", ".join(profile.skills)] if profile.skills else [],
            [
                "Required skills: " + ", ".join(jd_analysis.required_skills)
                if jd_analysis.required_skills
                else "",
                "Preferred skills: " + ", ".join(jd_analysis.preferred_skills)
                if jd_analysis.preferred_skills
                else "",
            ],
            0.20,
        ),
        (
            "certifications",
            profile.certifications or [],
            jd_analysis.preferred_skills or jd_targets,
            0.10,
        ),
    ]

    for section_name, source_texts, target_texts, weight in section_pairs:
        cleaned_targets = [target for target in target_texts if target]
        cleaned_sources = [source for source in source_texts if source]
        if not cleaned_sources or not cleaned_targets:
            continue

        section_result = calculate_similarity_between_text_sets(
            cleaned_sources,
            cleaned_targets,
            return_diagnostics=True,
        )
        raw_section_score = section_result["score"]
        diagnostics = section_result["diagnostics"]
        section_text = "\n".join(cleaned_sources)
        section_skills = set(extract_skills_from_text(section_text))
        skill_support_ratio = _safe_ratio(len(section_skills & jd_skill_set), len(jd_skill_set))
        lexical_support_score = diagnostics["lexical_alignment"] * 100
        domain_support_ratio = _safe_ratio(
            len(
                [
                    keyword
                    for keyword in jd_analysis.domain_keywords
                    if keyword and keyword.lower() in section_text.lower()
                ]
            ),
            max(1, len(jd_analysis.domain_keywords)),
        )
        group_support_ratio = _group_coverage_ratio(section_skills, jd_analysis.all_skills)
        transfer_support_ratio = _transfer_coverage_ratio(list(jd_skill_set), list(section_skills))

        calibrated_section_score = (
            (raw_section_score * 0.42)
            + (skill_support_ratio * 100 * 0.18)
            + (group_support_ratio * 100 * 0.20)
            + (transfer_support_ratio * 100 * 0.12)
            + (lexical_support_score * 0.08)
            + (domain_support_ratio * 100 * 0.10)
        )

        if skill_support_ratio == 0 and group_support_ratio < 0.15 and diagnostics["lexical_alignment"] < 0.05:
            calibrated_section_score = min(
                calibrated_section_score,
                25 + (domain_support_ratio * 20),
            )

        calibrated_section_score = _clamp_score(calibrated_section_score)
        section_scores.append((section_name, calibrated_section_score, weight))
        section_diagnostics[section_name] = {
            **diagnostics,
            "raw_section_score": raw_section_score,
            "calibrated_section_score": calibrated_section_score,
            "skill_support_ratio": round(skill_support_ratio, 4),
            "group_support_ratio": round(group_support_ratio, 4),
            "transfer_support_ratio": round(transfer_support_ratio, 4),
            "domain_support_ratio": round(domain_support_ratio, 4),
        }

    if not section_scores:
        return {
            "score": 0.0,
            "diagnostics": {
                "section_scores": {},
                "section_weights_used": {},
                "calibration_floor_applied": 0.0,
            },
        }

    total_weight = sum(weight for _, _, weight in section_scores)
    weighted_average = sum(score * weight for _, score, weight in section_scores) / total_weight
    top_section_name, top_section_score, _ = max(section_scores, key=lambda item: item[1])
    semantic_score = _clamp_score((weighted_average * 0.68) + (top_section_score * 0.32))

    return {
        "score": semantic_score,
        "diagnostics": {
            "section_scores": {
                section_name: round(section_score, 2)
                for section_name, section_score, _ in section_scores
            },
            "section_weights_used": {
                section_name: weight
                for section_name, _, weight in section_scores
            },
            "top_section": top_section_name,
            "section_details": section_diagnostics,
            "calibration_floor_applied": 0.0,
        },
    }


def _score_deployment(profile, jd_analysis):
    deployment_signals = unique_preserve_order(profile.deployment_signals)
    deployment_matches = set(deployment_signals) & set(jd_analysis.deployment_keywords)
    breadth_ratio = min(1.0, len(deployment_signals) / 4)

    if jd_analysis.deployment_keywords:
        overlap_ratio = _safe_ratio(
            len(deployment_matches),
            len(jd_analysis.deployment_keywords),
        )
        adjacency_ratio = _transfer_coverage_ratio(jd_analysis.deployment_keywords, deployment_signals)
        score = _clamp_score((overlap_ratio * 60) + (breadth_ratio * 24) + (adjacency_ratio * 16))
        if len(deployment_signals) >= 3:
            score = max(score, _clamp_score(55 + (breadth_ratio * 22)))
        return score

    return _clamp_score(45 + (breadth_ratio * 35))


def _score_ai_api(profile, jd_analysis):
    ai_signals = unique_preserve_order(profile.ai_signals)
    api_signals = unique_preserve_order(profile.api_signals)
    ai_matches = set(ai_signals) & set(jd_analysis.ai_keywords)
    api_matches = set(api_signals) & set(jd_analysis.api_keywords)

    ai_breadth = min(1.0, len(ai_signals) / 4)
    api_breadth = min(1.0, len(api_signals) / 4)

    if jd_analysis.ai_keywords or jd_analysis.api_keywords:
        ai_overlap_ratio = _safe_ratio(len(ai_matches), len(jd_analysis.ai_keywords) or 1)
        api_overlap_ratio = _safe_ratio(len(api_matches), len(jd_analysis.api_keywords) or 1)
        ai_transfer_ratio = _transfer_coverage_ratio(jd_analysis.ai_keywords, ai_signals)
        api_transfer_ratio = _transfer_coverage_ratio(jd_analysis.api_keywords, api_signals)

        return _clamp_score(
            (ai_overlap_ratio * 30)
            + (api_overlap_ratio * 18)
            + (ai_transfer_ratio * 18)
            + (api_transfer_ratio * 12)
            + (ai_breadth * 20)
            + (api_breadth * 15)
        )

    return _clamp_score(48 + (ai_breadth * 28) + (api_breadth * 14))


def _score_adjacency(missing_skills, adjacent_matches, retrieval_context: "RetrievalContext | None" = None):
    if retrieval_context and retrieval_context.pillar_scores.get("transferability"):
        suppression_penalty = _retrieval_suppression_penalty(retrieval_context)
        retrieval_scores = retrieval_context.pillar_scores["transferability"]
        retrieval_average = _safe_ratio(sum(retrieval_scores), len(retrieval_scores) or 1) * 100
        if not missing_skills:
            return _clamp_score(max(72.0, retrieval_average) * (1.0 - (suppression_penalty * 0.35)))
        heuristic_score = _clamp_score((_safe_ratio(len({item["missing_skill"] for item in adjacent_matches}), len(missing_skills)) * 68) + 26)
        blended = (heuristic_score * 0.45) + (retrieval_average * 0.55)
        return _clamp_score(blended * (1.0 - (suppression_penalty * 0.45)))

    if not missing_skills:
        return 72.0

    covered_missing = len({item["missing_skill"] for item in adjacent_matches})
    coverage_ratio = _safe_ratio(covered_missing, len(missing_skills))

    return _clamp_score((coverage_ratio * 68) + 26)


def _is_hidden_gem(keyword_score, semantic_score, project_relevance_score):
    return keyword_score < 55 and semantic_score >= 72 and project_relevance_score >= 70


def _retrieval_suppression_penalty(retrieval_context: "RetrievalContext | None") -> float:
    if not retrieval_context:
        return 0.0
    diagnostics = getattr(retrieval_context, "diagnostics", {}) or {}
    suppression = diagnostics.get("must_have_suppression", {})
    if not isinstance(suppression, dict):
        return 0.0
    try:
        base_penalty = max(0.0, float(suppression.get("penalty", 0.0) or 0.0))
    except (TypeError, ValueError):
        return 0.0
    missing = suppression.get("missing", [])
    missing_count = len(missing) if isinstance(missing, list) else 0
    if missing_count <= 0:
        progressive_penalty = 0.0
    elif missing_count == 1:
        progressive_penalty = 0.06
    elif missing_count <= 3:
        progressive_penalty = 0.14
    else:
        progressive_penalty = 0.24
    return max(0.0, min(0.30, max(base_penalty, progressive_penalty)))


def _apply_semantic_inflation_caps(
    semantic_score,
    project_relevance_score,
    adjacency_score,
    exact_support_ratio,
    weak_must_have_ratio,
    project_experience_ratio,
):
    capped_semantic = semantic_score
    capped_project = project_relevance_score
    capped_adjacency = adjacency_score
    caps = []

    if exact_support_ratio < 0.35 and semantic_score >= 68:
        cap = 58.0 if weak_must_have_ratio >= 0.45 else 64.0
        capped_semantic = min(capped_semantic, cap)
        caps.append(f"semantic_cap_low_exact_support_{cap}")
    elif exact_support_ratio < 0.55 and semantic_score >= 78:
        capped_semantic = min(capped_semantic, 74.0)
        caps.append("semantic_cap_moderate_exact_support_74")

    if exact_support_ratio < 0.60 and adjacency_score >= 72:
        capped_adjacency = min(capped_adjacency, 66.0)
        caps.append("adjacency_cap_without_strong_must_have_support")

    if project_experience_ratio < 0.50:
        if project_relevance_score >= 70:
            capped_project = min(capped_project, 62.0)
            caps.append("project_cap_weak_authoritative_evidence")
        if capped_semantic >= 70:
            capped_semantic = min(capped_semantic, 66.0)
            caps.append("semantic_cap_summary_or_skills_dominated")

    return (
        _clamp_score(capped_semantic),
        _clamp_score(capped_project),
        _clamp_score(capped_adjacency),
        caps,
    )


def _benchmark_calibration_adjustment(
    final_score,
    keyword_score,
    semantic_score,
    project_relevance_score,
    deployment_score,
    ai_experience_score,
    exact_support_ratio,
    weak_must_have_ratio,
    generic_penalty,
    hidden_gem_flag,
):
    adjusted = final_score
    reasons = []

    if exact_support_ratio < 0.35 and weak_must_have_ratio >= 0.50:
        adjusted = min(adjusted, 48.0)
        reasons.append("hard_cap_many_missing_must_haves")
    elif exact_support_ratio < 0.55 and adjusted > 85:
        adjusted = min(adjusted, 84.5)
        reasons.append("elite_cap_adjacent_fit")

    if keyword_score < 20 and project_relevance_score < 40 and semantic_score < 55:
        adjusted = min(adjusted, 14.5)
        reasons.append("irrelevant_candidate_cap")
    elif keyword_score < 30 and exact_support_ratio < 0.25 and generic_penalty >= 0.12:
        adjusted = min(adjusted, 18.0)
        reasons.append("generic_low_exact_support_cap")

    if (
        hidden_gem_flag
        and exact_support_ratio >= 0.45
        and project_relevance_score >= 70
        and max(deployment_score, ai_experience_score) >= 65
    ):
        adjusted = max(adjusted, min(final_score, 72.0))
        reasons.append("preserved_hidden_gem_floor")

    return _clamp_score(adjusted), reasons


def _apply_semantic_safety_floor(
    semantic_score,
    project_relevance_score,
    deployment_score,
    ai_experience_score,
    adjacency_score,
    keyword_score,
):
    floors = []

    if project_relevance_score >= 70 and ai_experience_score >= 60:
        floors.append(65.0)

    if project_relevance_score >= 65 and deployment_score >= 70:
        floors.append(62.0)

    if adjacency_score >= 45 and keyword_score >= 40 and project_relevance_score >= 60:
        floors.append(58.0)

    if keyword_score >= 60 and project_relevance_score >= 75:
        floors.append(68.0)

    if keyword_score >= 80 and project_relevance_score >= 70 and deployment_score >= 70:
        floors.append(72.0)

    if deployment_score >= 75 and keyword_score >= 24 and project_relevance_score >= 32:
        floors.append(42.0)

    if deployment_score >= 70 and adjacency_score >= 35 and keyword_score >= 25:
        floors.append(48.0)

    if project_relevance_score >= 50 and keyword_score >= 45 and semantic_score >= 45:
        floors.append(55.0)

    calibrated_score = max([semantic_score] + floors) if floors else semantic_score
    floor_applied = max(0.0, calibrated_score - semantic_score)

    return _clamp_score(calibrated_score), round(floor_applied, 2)


def _calibration_bonus(
    profile,
    keyword_score,
    project_relevance_score,
    semantic_score,
    deployment_score,
    ai_experience_score,
):
    frontend_skills = get_group_matches(profile.skills, "frontend")
    backend_skills = get_group_matches(profile.skills, "backend")
    bonus = 0.0
    rationale = []

    if keyword_score < 60 and project_relevance_score >= 75 and semantic_score >= 60:
        bonus = max(bonus, 9.0)
        rationale.append("strong_adjacent_project_fit")

    if keyword_score < 55 and deployment_score >= 70 and semantic_score >= 50:
        bonus = max(bonus, 6.0)
        rationale.append("platform_adjacency_fit")

    if keyword_score < 45 and len(frontend_skills) >= 3 and project_relevance_score >= 60 and semantic_score >= 55:
        bonus = max(bonus, 5.0)
        rationale.append("frontend_product_fit")

    if keyword_score < 65 and len(frontend_skills) >= 2 and len(backend_skills) >= 2 and project_relevance_score >= 65:
        bonus = max(bonus, 4.0)
        rationale.append("balanced_fullstack_fit")

    if ai_experience_score >= 65 and project_relevance_score >= 70 and keyword_score < 50:
        bonus = max(bonus, 5.0)
        rationale.append("ai_product_fit")

    if keyword_score < 65 and len(backend_skills) >= 2 and deployment_score >= 70 and project_relevance_score >= 45:
        bonus = max(bonus, 10.0)
        rationale.append("backend_platform_fit")

    if keyword_score < 50 and len(frontend_skills) >= 3 and project_relevance_score >= 35 and semantic_score >= 38:
        bonus = max(bonus, 8.0)
        rationale.append("frontend_product_fit")

    if keyword_score < 40 and deployment_score >= 75 and project_relevance_score >= 30:
        bonus = max(bonus, 8.0)
        rationale.append("platform_delivery_fit")

    return bonus, rationale


def score_candidate_profile(profile, jd_analysis, weights=DEFAULT_WEIGHTS, retrieval_context: "RetrievalContext | None" = None):
    retrieval_gap_penalty = _retrieval_suppression_penalty(retrieval_context)
    skill_result = _score_skills_overlap(profile, jd_analysis)
    exact_support_ratio = _exact_support_ratio(skill_result, retrieval_context)
    weak_must_have_ratio = _weak_must_have_ratio(retrieval_context)
    generic_penalty, generic_penalty_reasons = _generic_engineering_penalty(profile, jd_analysis)
    project_relevance_score = _score_project_relevance(profile, jd_analysis, retrieval_context=retrieval_context)
    semantic_result = _score_semantic_alignment(profile, jd_analysis, retrieval_context=retrieval_context)
    semantic_score_raw = semantic_result["score"]
    semantic_score = semantic_score_raw
    deployment_score = _score_deployment(profile, jd_analysis)
    ai_experience_score = _score_ai_api(profile, jd_analysis)
    adjacency_score = _score_adjacency(
        skill_result["missing_skills"],
        skill_result["adjacent_matches"],
        retrieval_context=retrieval_context,
    )
    project_experience_ratio = _retrieval_project_experience_ratio(retrieval_context, "semantic_fit") if retrieval_context else 1.0
    semantic_score, project_relevance_score, adjacency_score, semantic_caps = _apply_semantic_inflation_caps(
        semantic_score,
        project_relevance_score,
        adjacency_score,
        exact_support_ratio,
        weak_must_have_ratio,
        project_experience_ratio,
    )
    semantic_score, semantic_floor_adjustment = _apply_semantic_safety_floor(
        semantic_score,
        project_relevance_score,
        deployment_score,
        ai_experience_score,
        adjacency_score,
        skill_result["keyword_score"],
    )
    semantic_result["diagnostics"]["calibration_floor_applied"] = semantic_floor_adjustment
    semantic_score, project_relevance_score, adjacency_score, post_floor_caps = _apply_semantic_inflation_caps(
        semantic_score,
        project_relevance_score,
        adjacency_score,
        exact_support_ratio,
        weak_must_have_ratio,
        project_experience_ratio,
    )
    semantic_caps.extend([cap for cap in post_floor_caps if cap not in semantic_caps])
    semantic_gap_suppression = 0.0
    if retrieval_gap_penalty:
        semantic_gap_suppression = round(min(16.0, semantic_score * retrieval_gap_penalty * 0.78), 2)
        semantic_score = _clamp_score(semantic_score - semantic_gap_suppression)
    generic_score_suppression = round(min(10.0, generic_penalty * 36.0), 2)
    if generic_score_suppression:
        semantic_score = _clamp_score(semantic_score - (generic_score_suppression * 0.55))
        project_relevance_score = _clamp_score(project_relevance_score - (generic_score_suppression * 0.45))
        adjacency_score = _clamp_score(adjacency_score - (generic_score_suppression * 0.25))

    weighted_raw_score = (
        (skill_result["keyword_score"] * weights.skills_overlap)
        + (project_relevance_score * weights.project_relevance)
        + (semantic_score * weights.semantic_alignment)
        + (deployment_score * weights.deployment_experience)
        + (ai_experience_score * weights.ai_api_experience)
        + (adjacency_score * weights.adjacency_transferability)
    )

    hidden_gem_flag = _is_hidden_gem(
        skill_result["keyword_score"],
        semantic_score,
        project_relevance_score,
    )

    consistency_bonus = (
        3.5
        if min(
            skill_result["keyword_score"],
            project_relevance_score,
            semantic_score,
        )
        >= 65
        else 0.0
    )
    hidden_gem_bonus = 3.0 if hidden_gem_flag else 0.0
    calibration_bonus, calibration_rationale = _calibration_bonus(
        profile,
        skill_result["keyword_score"],
        project_relevance_score,
        semantic_score,
        deployment_score,
        ai_experience_score,
    )
    seniority_penalty = _seniority_penalty(profile, jd_analysis)
    pre_normalized_score = (
        weighted_raw_score
        + consistency_bonus
        + hidden_gem_bonus
        + calibration_bonus
        - seniority_penalty
        - generic_score_suppression
    )
    final_score = _normalize_final_score(pre_normalized_score)
    final_score_before_benchmark_calibration = final_score
    final_score, benchmark_calibration_reasons = _benchmark_calibration_adjustment(
        final_score,
        skill_result["keyword_score"],
        semantic_score,
        project_relevance_score,
        deployment_score,
        ai_experience_score,
        exact_support_ratio,
        weak_must_have_ratio,
        generic_penalty,
        hidden_gem_flag,
    )

    recommendation = _determine_recommendation(final_score, hidden_gem_flag)
    component_scores = [
        skill_result["keyword_score"],
        project_relevance_score,
        semantic_score,
        deployment_score,
        ai_experience_score,
    ]
    confidence_score = _confidence_score(component_scores, final_score)
    recruiter_confidence = _infer_confidence(final_score, component_scores)

    scorecard = {
        "final_score": final_score,
        "keyword_score": skill_result["keyword_score"],
        "semantic_score": semantic_score,
        "adjacency_bonus": round(adjacency_score * weights.adjacency_transferability, 2),
        "matched_skills": skill_result["matched_skills"],
        "missing_skills": skill_result["missing_skills"],
        "adjacent_matches": skill_result["adjacent_matches"],
        "ecosystem_matches": skill_result["ecosystem_matches"],
        "project_relevance_score": project_relevance_score,
        "deployment_score": deployment_score,
        "ai_experience_score": ai_experience_score,
        "hidden_gem_flag": hidden_gem_flag,
        "confidence_score": confidence_score,
        "recruiter_confidence": recruiter_confidence,
        "scoring_diagnostics": {
            "scoring_version": "v2_authoritative_pipeline",
            "raw_scores": {
                "semantic_score_raw": semantic_score_raw,
                "keyword_score_raw": skill_result["keyword_score"],
                "adjacency_bonus": round(adjacency_score * weights.adjacency_transferability, 2),
                "project_relevance_score": project_relevance_score,
                "deployment_score": deployment_score,
                "confidence_score": confidence_score,
            },
            "component_scores": {
                "keyword_score": skill_result["keyword_score"],
                "project_relevance_score": project_relevance_score,
                "semantic_score": semantic_score,
                "deployment_score": deployment_score,
                "ai_experience_score": ai_experience_score,
                "adjacency_score": adjacency_score,
            },
            "coverage_metrics": {
                "required_direct_ratio": skill_result["required_direct_ratio"],
                "required_effective_ratio": skill_result["required_effective_ratio"],
                "preferred_ratio": skill_result["preferred_ratio"],
                "group_coverage_ratio": skill_result["group_coverage_ratio"],
                "exact_skill_support_ratio": exact_support_ratio,
                "weak_must_have_ratio": weak_must_have_ratio,
                "retrieval_project_experience_ratio": project_experience_ratio,
            },
            "semantic_details": semantic_result["diagnostics"],
            "adjustments": {
                "consistency_bonus": consistency_bonus,
                "hidden_gem_bonus": hidden_gem_bonus,
                "calibration_bonus": calibration_bonus,
                "calibration_rationale": calibration_rationale,
                "seniority_penalty": seniority_penalty,
                "semantic_floor_adjustment": semantic_floor_adjustment,
                "semantic_gap_suppression": semantic_gap_suppression,
                "retrieval_must_have_penalty": retrieval_gap_penalty,
                "semantic_inflation_caps": semantic_caps,
                "generic_engineering_penalty": round(generic_penalty, 4),
                "generic_engineering_penalty_reasons": generic_penalty_reasons,
                "generic_score_suppression": generic_score_suppression,
                "final_score_before_benchmark_calibration": final_score_before_benchmark_calibration,
                "benchmark_calibration_reasons": benchmark_calibration_reasons,
                "pre_normalized_score": round(pre_normalized_score, 2),
                "final_score": final_score,
            },
        },
    }

    logger.debug(
        "Scored candidate '%s' | final=%s keyword=%s semantic=%s raw_semantic=%s project=%s deployment=%s ai=%s",
        profile.name,
        final_score,
        skill_result["keyword_score"],
        semantic_score,
        semantic_score_raw,
        project_relevance_score,
        deployment_score,
        ai_experience_score,
    )

    reasoning = build_recruiter_reasoning(profile, jd_analysis, scorecard)

    scorecard["strengths"] = reasoning["strengths"]
    scorecard["weaknesses"] = reasoning["weaknesses"]
    scorecard["recommendation"] = recommendation
    scorecard["recruiter_summary"] = reasoning["recruiter_summary"]

    return scorecard
