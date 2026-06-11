from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from backend.reasoning.evidence_quality import classify_evidence, evidence_category, quality_weight


STRONG_RECOMMENDATIONS = {"Highly Recommended", "Recommended"}


@dataclass(frozen=True)
class CandidateTrustProfile:
    name: str
    final_score: float
    keyword_score: float
    semantic_score: float
    project_score: float
    deployment_score: float
    ai_score: float
    adjacency_bonus: float
    missing_must_haves: int
    missing_skills: int
    matched_skills: int
    strong_evidence_count: int
    medium_evidence_count: int
    weak_evidence_count: int
    average_evidence_quality: float
    skills_or_summary_ratio: float
    categories: Counter[str]
    false_positive_flags: tuple[str, ...]
    credibility_index: float
    ordering_score: float


def apply_ranking_trust_analysis(ranked_candidates: list[dict]) -> None:
    if not ranked_candidates:
        return

    _apply_false_positive_suppression(ranked_candidates)
    _refine_close_ordering(ranked_candidates)
    _annotate_ordering_stability(ranked_candidates)
    for candidate in ranked_candidates:
        candidate.get("ranking", {}).pop("_ordering_score", None)


def apply_recruiter_validation(ranked_candidates: list[dict]) -> None:
    if not ranked_candidates:
        return

    category_totals = Counter()
    category_examples_by_index = {}
    for index, candidate in enumerate(ranked_candidates):
        examples = _strong_category_examples(candidate)
        category_examples_by_index[index] = examples
        category_totals.update(examples.keys())

    used_shapes: set[str] = set()
    for index, candidate in enumerate(ranked_candidates):
        ranking = candidate.get("ranking", {})
        profile = build_candidate_trust_profile(candidate)
        above = ranked_candidates[index - 1] if index > 0 else None
        below = ranked_candidates[index + 1] if index < len(ranked_candidates) - 1 else None
        neighbor_reviews = _neighbor_reviews(candidate, above, below)

        close_names = [
            review["neighbor_name"]
            for review in neighbor_reviews
            if review["confidence"] == "Low" or review["score_gap"] <= 4 or review["ordering_gap"] <= 5
        ]
        ordering_confidence = _public_ordering_confidence(profile, neighbor_reviews)

        differentiators = _candidate_differentiators(
            index,
            category_examples_by_index,
            category_totals,
            used_shapes,
        )
        challenges = _ranking_challenges(profile)
        could_change = _could_change_ordering(profile, neighbor_reviews)
        decisive_ids = _decisive_evidence_ids(candidate)
        confidence_rationale = _confidence_rationale(profile, ordering_confidence)

        ranking["ordering_confidence"] = ordering_confidence
        ranking["confidence_rationale"] = confidence_rationale
        ranking["candidate_differentiators"] = differentiators
        ranking["decisive_evidence_ids"] = decisive_ids
        ranking["close_call_with"] = close_names[:2]
        ranking["could_change_ordering"] = could_change
        ranking["ranking_challenge"] = challenges

        if ordering_confidence in {"Close", "Low"} and ranking.get("recruiter_confidence") == "High":
            ranking["recruiter_confidence"] = "Medium"
        if profile.strong_evidence_count == 0 and ranking.get("recruiter_confidence") != "Low":
            ranking["recruiter_confidence"] = "Low"

        ranking["strengths"] = _evidence_supported_unique(ranking.get("strengths", []) or [], limit=2)
        ranking["risks"] = _evidence_supported_unique(ranking.get("risks", []) or ranking.get("weaknesses", []) or [], limit=2)
        ranking["weaknesses"] = ranking["risks"]
        ranking["interview_focus_areas"] = _evidence_supported_unique(ranking.get("interview_focus_areas", []) or [], limit=2)

        diagnostics = ranking.setdefault("scoring_diagnostics", {})
        diagnostics["recruiter_validation"] = {
            "ordering_confidence": ordering_confidence,
            "close_call_with": close_names[:2],
            "credibility_index": profile.credibility_index,
            "decisive_evidence_count": len(decisive_ids),
            "challenge_count": len(challenges),
        }


def compare_candidates_pairwise(left: dict, right: dict) -> dict:
    left_profile = build_candidate_trust_profile(left)
    right_profile = build_candidate_trust_profile(right)
    deltas = {
        "must_have_coverage": _must_have_delta(left_profile, right_profile),
        "implementation_specificity": (left_profile.average_evidence_quality - right_profile.average_evidence_quality) * 18,
        "strong_evidence": (left_profile.strong_evidence_count - right_profile.strong_evidence_count) * 4,
        "deployment_ownership": _category_delta(left_profile, right_profile, "deployment ownership") * 6,
        "operational_complexity": _category_delta(left_profile, right_profile, "operational reliability") * 7,
        "architectural_depth": _architectural_delta(left_profile, right_profile) * 5,
        "execution_maturity": (left_profile.project_score - right_profile.project_score) * 0.08,
        "transferability_quality": _transferability_delta(left_profile, right_profile),
        "false_positive_risk": (len(right_profile.false_positive_flags) - len(left_profile.false_positive_flags)) * 6,
        "baseline_signal": (left_profile.final_score - right_profile.final_score) * 0.18,
    }
    pairwise_delta = round(sum(deltas.values()), 3)

    if abs(pairwise_delta) >= 12:
        confidence = "High"
    elif abs(pairwise_delta) >= 5:
        confidence = "Medium"
    else:
        confidence = "Low"

    if pairwise_delta > 0:
        preferred = "left"
        rationale = _pairwise_rationale(left_profile, right_profile)
    elif pairwise_delta < 0:
        preferred = "right"
        rationale = _pairwise_rationale(right_profile, left_profile)
    else:
        preferred = "tie"
        rationale = "Candidates are closely matched; ordering should be treated as low confidence."

    return {
        "preferred": preferred,
        "confidence": confidence,
        "delta": pairwise_delta,
        "deltas": {key: round(value, 3) for key, value in deltas.items()},
        "rationale": rationale,
        "left_profile": left_profile,
        "right_profile": right_profile,
    }


def build_candidate_trust_profile(candidate: dict) -> CandidateTrustProfile:
    ranking = candidate.get("ranking", {})
    snippets = _all_evidence_snippets(candidate)
    quality_values = [quality_weight(snippet) for snippet in snippets]
    quality_labels = [classify_evidence(snippet.get("snippet", ""), snippet.get("source_type", "summary")).label for snippet in snippets]
    categories = Counter(
        category
        for category in (evidence_category(snippet.get("snippet", "")) for snippet in snippets if _is_strong(snippet))
        if category
    )
    strong_count = quality_labels.count("strong")
    medium_count = quality_labels.count("medium")
    weak_count = quality_labels.count("weak")
    skills_or_summary_count = sum(1 for snippet in snippets if snippet.get("source_type") in {"skills", "summary"})
    average_quality = round(sum(quality_values) / len(quality_values), 4) if quality_values else 0.0
    skills_or_summary_ratio = round(skills_or_summary_count / len(snippets), 4) if snippets else 1.0
    false_positive_flags = _false_positive_flags(candidate, strong_count, average_quality, skills_or_summary_ratio, categories)
    credibility_index = _credibility_index(
        ranking,
        strong_count,
        medium_count,
        weak_count,
        average_quality,
        skills_or_summary_ratio,
        categories,
        false_positive_flags,
    )
    ordering_score = _ordering_score(ranking, credibility_index, false_positive_flags)
    ranking["_ordering_score"] = ordering_score

    return CandidateTrustProfile(
        name=candidate.get("candidate_name", "Unknown Candidate"),
        final_score=float(ranking.get("final_score", 0.0) or 0.0),
        keyword_score=float(ranking.get("keyword_score", 0.0) or 0.0),
        semantic_score=float(ranking.get("semantic_score", 0.0) or 0.0),
        project_score=float(ranking.get("project_relevance_score", 0.0) or 0.0),
        deployment_score=float(ranking.get("deployment_score", 0.0) or 0.0),
        ai_score=float(ranking.get("ai_experience_score", 0.0) or 0.0),
        adjacency_bonus=float(ranking.get("adjacency_bonus", 0.0) or 0.0),
        missing_must_haves=len(ranking.get("missing_must_haves", []) or []),
        missing_skills=len(ranking.get("missing_skills", []) or []),
        matched_skills=len(ranking.get("matched_skills", []) or []),
        strong_evidence_count=strong_count,
        medium_evidence_count=medium_count,
        weak_evidence_count=weak_count,
        average_evidence_quality=average_quality,
        skills_or_summary_ratio=skills_or_summary_ratio,
        categories=categories,
        false_positive_flags=tuple(false_positive_flags),
        credibility_index=credibility_index,
        ordering_score=ordering_score,
    )


def _apply_false_positive_suppression(ranked_candidates: list[dict]) -> None:
    for candidate in ranked_candidates:
        ranking = candidate.get("ranking", {})
        profile = build_candidate_trust_profile(candidate)
        diagnostics = ranking.setdefault("scoring_diagnostics", {})
        trust = diagnostics.setdefault("ranking_trust", {})
        trust["credibility_index"] = profile.credibility_index
        trust["false_positive_flags"] = list(profile.false_positive_flags)
        trust["ordering_score"] = profile.ordering_score

        if not profile.false_positive_flags:
            continue

        if ranking.get("recommendation") == "Highly Recommended":
            ranking["recommendation"] = "Recommended" if profile.strong_evidence_count >= 1 else "Consider for Interview"
        elif ranking.get("recommendation") == "Recommended" and profile.strong_evidence_count == 0:
            ranking["recommendation"] = "Consider for Interview"
        if profile.strong_evidence_count == 0:
            ranking["hidden_gem_flag"] = False

        if profile.strong_evidence_count == 0 or len(profile.false_positive_flags) >= 2:
            ranking["recruiter_confidence"] = "Low"
        elif ranking.get("recruiter_confidence") == "High":
            ranking["recruiter_confidence"] = "Medium"

        risks = ranking.get("risks", []) or ranking.get("weaknesses", []) or []
        risk = _false_positive_risk_text(profile)
        if risk and risk not in risks:
            ranking["risks"] = [risk] + risks[:1]
            ranking["weaknesses"] = ranking["risks"]


def _refine_close_ordering(ranked_candidates: list[dict]) -> None:
    if len(ranked_candidates) < 2:
        return

    changed = True
    passes = 0
    while changed and passes < len(ranked_candidates):
        changed = False
        passes += 1
        for index in range(len(ranked_candidates) - 1):
            left = ranked_candidates[index]
            right = ranked_candidates[index + 1]
            left_profile = build_candidate_trust_profile(left)
            right_profile = build_candidate_trust_profile(right)
            baseline_gap = left_profile.final_score - right_profile.final_score
            comparison = compare_candidates_pairwise(left, right)
            right_ordering_advantage = right_profile.ordering_score - left_profile.ordering_score
            evidence_override = (
                left_profile.false_positive_flags
                and right_profile.strong_evidence_count > left_profile.strong_evidence_count
                and right_profile.average_evidence_quality - left_profile.average_evidence_quality >= 0.12
                and baseline_gap <= 22
            )
            severe_false_positive_override = (
                len(left_profile.false_positive_flags) >= 2
                and left_profile.strong_evidence_count == 0
                and right_profile.strong_evidence_count > 0
                and right_profile.categories
                and baseline_gap <= 60
            )

            should_swap = (
                comparison["preferred"] == "right"
                and comparison["confidence"] in {"High", "Medium"}
                and (baseline_gap <= 12 or evidence_override or severe_false_positive_override)
                and (
                    comparison["delta"] <= -7
                    or right_ordering_advantage >= 4
                    or evidence_override
                    or severe_false_positive_override
                )
            )
            if should_swap:
                ranked_candidates[index], ranked_candidates[index + 1] = right, left
                changed = True


def _annotate_ordering_stability(ranked_candidates: list[dict]) -> None:
    for index, candidate in enumerate(ranked_candidates):
        ranking = candidate.get("ranking", {})
        diagnostics = ranking.setdefault("scoring_diagnostics", {})
        trust = diagnostics.setdefault("ranking_trust", {})
        profile = build_candidate_trust_profile(candidate)
        trust["ordering_score"] = profile.ordering_score
        trust["ordering_confidence"] = "High"
        trust["pairwise_rationale"] = []

        if index > 0:
            above = ranked_candidates[index - 1]
            comparison = compare_candidates_pairwise(above, candidate)
            trust["pairwise_rationale"].append(
                {
                    "compared_to": above.get("candidate_name", "Candidate above"),
                    "confidence": comparison["confidence"],
                    "rationale": comparison["rationale"],
                }
            )
            if comparison["confidence"] == "Low":
                trust["ordering_confidence"] = "Close"
                _soften_near_tie_language(candidate)

        if index < len(ranked_candidates) - 1:
            below = ranked_candidates[index + 1]
            comparison = compare_candidates_pairwise(candidate, below)
            if comparison["confidence"] == "Low":
                trust["ordering_confidence"] = "Close"
                _soften_near_tie_language(candidate)


def _soften_near_tie_language(candidate: dict) -> None:
    ranking = candidate.get("ranking", {})
    if ranking.get("recommendation") == "Highly Recommended":
        ranking["recommendation"] = "Recommended"
    if ranking.get("recruiter_confidence") == "High":
        ranking["recruiter_confidence"] = "Medium"
    summary = ranking.get("recruiter_decision_summary", "")
    prefix = "Closely matched with nearby candidates; ordering is driven by evidence quality rather than score precision."
    if summary and prefix.lower() not in summary.lower():
        ranking["recruiter_decision_summary"] = f"{prefix} {summary}"
        ranking["recruiter_summary"] = ranking["recruiter_decision_summary"]


def _all_evidence_snippets(candidate: dict) -> list[dict]:
    ranking = candidate.get("ranking", {})
    evidence_by_pillar = ranking.get("supporting_evidence_snippets", {}) or {}
    snippets = []
    seen = set()
    for evidence_items in evidence_by_pillar.values():
        for item in evidence_items or []:
            if hasattr(item, "model_dump"):
                item = item.model_dump()
            evidence_id = item.get("evidence_id") or item.get("chunk_id") or item.get("snippet", "")
            if evidence_id in seen:
                continue
            seen.add(evidence_id)
            snippets.append(item)
    return snippets


def _strong_project_evidence(candidate: dict) -> list[dict]:
    snippets = [
        snippet
        for snippet in _all_evidence_snippets(candidate)
        if _is_strong(snippet) and snippet.get("source_type") in {"project", "experience"}
    ]
    snippets.sort(key=lambda item: -(float(item.get("retrieval_score") or 0.0)))
    return snippets


def _strong_category_examples(candidate: dict) -> dict[str, dict]:
    examples = {}
    for snippet in _strong_project_evidence(candidate):
        category = evidence_category(snippet.get("snippet", ""))
        if category and category not in examples:
            examples[category] = snippet
    return examples


def _decisive_evidence_ids(candidate: dict) -> list[str]:
    ids = []
    for snippet in _strong_project_evidence(candidate)[:2]:
        evidence_id = snippet.get("evidence_id") or snippet.get("chunk_id")
        if evidence_id and evidence_id not in ids:
            ids.append(evidence_id)
    return ids


def _neighbor_reviews(candidate: dict, above: dict | None, below: dict | None) -> list[dict]:
    reviews = []
    current_profile = build_candidate_trust_profile(candidate)
    for neighbor in (above, below):
        if not neighbor:
            continue
        neighbor_profile = build_candidate_trust_profile(neighbor)
        if current_profile.ordering_score >= neighbor_profile.ordering_score:
            comparison = compare_candidates_pairwise(candidate, neighbor)
        else:
            comparison = compare_candidates_pairwise(neighbor, candidate)
        reviews.append(
            {
                "neighbor_name": neighbor.get("candidate_name", "Nearby candidate"),
                "confidence": comparison["confidence"],
                "rationale": comparison["rationale"],
                "score_gap": abs(current_profile.final_score - neighbor_profile.final_score),
                "ordering_gap": abs(current_profile.ordering_score - neighbor_profile.ordering_score),
                "neighbor_profile": neighbor_profile,
            }
        )
    return reviews


def _public_ordering_confidence(profile: CandidateTrustProfile, neighbor_reviews: list[dict]) -> str:
    if profile.strong_evidence_count == 0 or len(profile.false_positive_flags) >= 2:
        return "Low"
    if any(review["confidence"] == "Low" or review["score_gap"] <= 4 or review["ordering_gap"] <= 5 for review in neighbor_reviews):
        return "Close"
    if profile.strong_evidence_count >= 2 and profile.missing_must_haves == 0 and profile.credibility_index >= 45:
        return "High"
    return "Medium"


def _candidate_differentiators(
    index: int,
    category_examples_by_index: dict[int, dict[str, dict]],
    category_totals: Counter[str],
    used_shapes: set[str],
) -> list[str]:
    examples = category_examples_by_index.get(index, {})
    if not examples:
        return []
    candidates = []
    for category, snippet in examples.items():
        source_label = snippet.get("source_label", "resume evidence")
        if category_totals[category] == 1:
            candidates.append(f"Only candidate in this slate with strong {category} evidence from {source_label}.")
        else:
            candidates.append(f"Strong {category} evidence from {source_label} is one of this candidate's clearer separators.")
    selected = []
    for text in candidates:
        shape = _shape(text)
        if shape in used_shapes:
            continue
        used_shapes.add(shape)
        selected.append(text)
        if len(selected) >= 1:
            break
    return selected


def _ranking_challenges(profile: CandidateTrustProfile) -> list[str]:
    challenges = []
    risk = _false_positive_risk_text(profile)
    if risk:
        challenges.append(risk)
    if profile.missing_must_haves:
        challenges.append("Must-have gaps mean the recommendation depends on transferable evidence rather than direct proof.")
    if profile.strong_evidence_count == 0:
        challenges.append("No strong project or experience evidence is available to defend an assertive ranking.")
    return _evidence_supported_unique(challenges, limit=2)


def _could_change_ordering(profile: CandidateTrustProfile, neighbor_reviews: list[dict]) -> list[str]:
    if not neighbor_reviews:
        return []
    close = any(review["confidence"] == "Low" or review["score_gap"] <= 4 or review["ordering_gap"] <= 5 for review in neighbor_reviews)
    if not close and profile.missing_must_haves == 0 and profile.strong_evidence_count >= 2:
        return []
    items = []
    if profile.missing_must_haves:
        items.append("Concrete evidence for the missing must-have requirements could change the ordering.")
    if profile.strong_evidence_count <= 1:
        items.append("Stronger project or experience evidence could materially change recruiter confidence.")
    if close:
        items.append("Nearby candidates are close enough that interview validation could reasonably change the order.")
    return _evidence_supported_unique(items, limit=2)


def _confidence_rationale(profile: CandidateTrustProfile, ordering_confidence: str) -> str | None:
    if profile.strong_evidence_count == 0:
        return "Low confidence because the ranking is not backed by strong project or experience evidence."
    if ordering_confidence == "Close":
        return "Ordering is a close call because nearby candidates have similar evidence strength."
    if profile.missing_must_haves:
        return "Confidence is limited by explicit must-have gaps despite supporting evidence."
    if profile.false_positive_flags:
        return "Confidence is moderated because some ranking signals rely on weak or keyword-heavy evidence."
    if ordering_confidence == "High":
        return "High confidence because strong evidence, must-have support, and nearby ordering checks are consistent."
    return "Moderate confidence because the evidence supports the ranking but is not decisive enough for high certainty."


def _evidence_supported_unique(items: list[str], limit: int) -> list[str]:
    selected = []
    seen = set()
    for item in items:
        cleaned = " ".join(str(item or "").split())
        if not cleaned:
            continue
        if _generic_or_weak_text(cleaned):
            continue
        shape = _shape(cleaned)
        if shape in seen:
            continue
        seen.add(shape)
        selected.append(cleaned)
        if len(selected) >= limit:
            break
    return selected


def _generic_or_weak_text(text: str) -> bool:
    lowered = text.lower()
    generic_patterns = (
        "validate scalability understanding",
        "confirm ability",
        "assess communication",
        "validate backend",
        "stronger fit",
        "better alignment",
        "more relevant",
    )
    return any(pattern in lowered for pattern in generic_patterns)


def _shape(text: str) -> str:
    words = [
        word.strip(".,:;()[]{}").lower()
        for word in text.split()
        if len(word.strip(".,:;()[]{}")) > 2
    ]
    return " ".join(words[:7])


def _is_strong(snippet: dict) -> bool:
    return classify_evidence(snippet.get("snippet", ""), snippet.get("source_type", "summary")).label == "strong"


def _false_positive_flags(
    candidate: dict,
    strong_count: int,
    average_quality: float,
    skills_or_summary_ratio: float,
    categories: Counter[str],
) -> list[str]:
    ranking = candidate.get("ranking", {})
    flags = []
    keyword_score = float(ranking.get("keyword_score", 0.0) or 0.0)
    final_score = float(ranking.get("final_score", 0.0) or 0.0)
    ai_score = float(ranking.get("ai_experience_score", 0.0) or 0.0)
    adjacency_bonus = float(ranking.get("adjacency_bonus", 0.0) or 0.0)

    if keyword_score >= 70 and strong_count == 0:
        flags.append("keyword_overlap_without_implementation_evidence")
    if keyword_score >= 65 and skills_or_summary_ratio >= 0.55 and average_quality < 0.35:
        flags.append("skill_inventory_dominated")
    if ai_score >= 60 and not categories.get("AI retrieval implementation"):
        flags.append("ai_signal_without_strong_ai_evidence")
    if final_score >= 85 and strong_count < 2:
        flags.append("elite_score_under_supported")
    if adjacency_bonus >= 5 and strong_count == 0:
        flags.append("adjacent_fit_without_strong_evidence")

    return flags


def _credibility_index(
    ranking: dict,
    strong_count: int,
    medium_count: int,
    weak_count: int,
    average_quality: float,
    skills_or_summary_ratio: float,
    categories: Counter[str],
    false_positive_flags: list[str],
) -> float:
    value = average_quality * 44
    value += min(24, strong_count * 8)
    value += min(8, medium_count * 2)
    value += min(12, len(categories) * 3)
    if categories.get("operational reliability"):
        value += 8
    if categories.get("deployment ownership"):
        value += 5
    value -= min(18, weak_count * 3)
    value -= skills_or_summary_ratio * 14
    value -= len(false_positive_flags) * 9
    value -= len(ranking.get("missing_must_haves", []) or []) * 5
    return round(max(0.0, min(100.0, value)), 3)


def _ordering_score(ranking: dict, credibility_index: float, false_positive_flags: list[str]) -> float:
    final_score = float(ranking.get("final_score", 0.0) or 0.0)
    missing_must_haves = len(ranking.get("missing_must_haves", []) or [])
    penalty = len(false_positive_flags) * 5.5 + missing_must_haves * 4
    return round(final_score + ((credibility_index - 50.0) * 0.18) - penalty, 3)


def _must_have_delta(left: CandidateTrustProfile, right: CandidateTrustProfile) -> float:
    left_missing = left.missing_must_haves + _unsupported_coverage_penalty(left)
    right_missing = right.missing_must_haves + _unsupported_coverage_penalty(right)
    left_matched = left.matched_skills * _supported_match_factor(left)
    right_matched = right.matched_skills * _supported_match_factor(right)
    return (right_missing - left_missing) * 8 + (left_matched - right_matched) * 0.7


def _unsupported_coverage_penalty(profile: CandidateTrustProfile) -> int:
    if profile.strong_evidence_count > 0:
        return 0
    penalty = 0
    if "keyword_overlap_without_implementation_evidence" in profile.false_positive_flags:
        penalty += 2
    if "skill_inventory_dominated" in profile.false_positive_flags:
        penalty += 1
    return penalty


def _supported_match_factor(profile: CandidateTrustProfile) -> float:
    if profile.strong_evidence_count > 0:
        return 1.0
    if profile.false_positive_flags:
        return 0.35
    return 0.65


def _category_delta(left: CandidateTrustProfile, right: CandidateTrustProfile, category: str) -> int:
    return min(2, left.categories.get(category, 0)) - min(2, right.categories.get(category, 0))


def _architectural_delta(left: CandidateTrustProfile, right: CandidateTrustProfile) -> int:
    architecture_categories = {"backend implementation", "realtime systems", "AI retrieval implementation"}
    left_count = sum(1 for category in architecture_categories if left.categories.get(category))
    right_count = sum(1 for category in architecture_categories if right.categories.get(category))
    return left_count - right_count


def _transferability_delta(left: CandidateTrustProfile, right: CandidateTrustProfile) -> float:
    left_supported = left.adjacency_bonus if left.strong_evidence_count else left.adjacency_bonus * 0.25
    right_supported = right.adjacency_bonus if right.strong_evidence_count else right.adjacency_bonus * 0.25
    return (left_supported - right_supported) * 0.7


def _pairwise_rationale(winner: CandidateTrustProfile, loser: CandidateTrustProfile) -> str:
    reasons = []
    if winner.missing_must_haves < loser.missing_must_haves:
        reasons.append("must-have coverage is cleaner")
    if winner.strong_evidence_count > loser.strong_evidence_count:
        reasons.append("implementation evidence is materially stronger")
    if winner.average_evidence_quality - loser.average_evidence_quality >= 0.10:
        reasons.append("resume credibility is better supported by concrete evidence")
    if winner.categories.get("deployment ownership", 0) > loser.categories.get("deployment ownership", 0):
        reasons.append("deployment ownership is more explicit")
    if winner.categories.get("operational reliability", 0) > loser.categories.get("operational reliability", 0):
        reasons.append("operational reliability evidence is stronger")
    if loser.false_positive_flags and not winner.false_positive_flags:
        reasons.append("the other profile relies more on weak or keyword-heavy evidence")
    if not reasons:
        reasons.append("the evidence profile is slightly stronger")
    return f"{winner.name} ranks higher because " + ", ".join(reasons[:3]) + "."


def _false_positive_risk_text(profile: CandidateTrustProfile) -> str:
    if "ai_signal_without_strong_ai_evidence" in profile.false_positive_flags:
        return "AI claims are not supported by strong implementation-level AI evidence."
    if "keyword_overlap_without_implementation_evidence" in profile.false_positive_flags:
        return "Keyword overlap is not backed by strong implementation evidence."
    if "skill_inventory_dominated" in profile.false_positive_flags:
        return "The resume is dominated by skill inventory evidence rather than shipped-work proof."
    if "elite_score_under_supported" in profile.false_positive_flags:
        return "The score is stronger than the available implementation evidence supports."
    if "adjacent_fit_without_strong_evidence" in profile.false_positive_flags:
        return "Adjacent-fit signal lacks strong project evidence."
    return ""
