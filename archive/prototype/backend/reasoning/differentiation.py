from __future__ import annotations

from collections import Counter

from backend.reasoning.evidence_quality import evidence_category, is_strong_evidence


def apply_candidate_differentiation(ranked_candidates: list[dict]) -> None:
    if len(ranked_candidates) < 2:
        for candidate in ranked_candidates:
            _trim_candidate_outputs(candidate)
        return

    category_by_candidate: dict[int, Counter[str]] = {}
    category_totals: Counter[str] = Counter()
    category_best: dict[str, tuple[int, int]] = {}

    for index, candidate in enumerate(ranked_candidates):
        counter = Counter(_strong_categories(candidate))
        category_by_candidate[index] = counter
        category_totals.update(counter.keys())
        for category, count in counter.items():
            previous = category_best.get(category)
            if previous is None or count > previous[1]:
                category_best[category] = (index, count)

    used_shapes: set[str] = set()
    for index, candidate in enumerate(ranked_candidates):
        ranking = candidate.get("ranking", {})
        strengths = []
        risks = []
        counter = category_by_candidate.get(index, Counter())
        example_by_category = _category_examples(candidate)

        for category in counter:
            if category_totals[category] == 1:
                strengths.append(_unique_strength_text(category, example_by_category.get(category)))

        for category, best in category_best.items():
            best_index, best_count = best
            if best_index == index and best_count >= 2 and category_totals[category] > 1:
                strengths.append(_best_strength_text(category, example_by_category.get(category)))

        if "backend implementation" in counter and "operational reliability" not in counter:
            risks.append("Backend implementation is credible, but reliability, monitoring, or recovery ownership is not as clear.")
        if "deployment ownership" in counter and "operational reliability" not in counter:
            risks.append("Deployment ownership is visible, but post-deployment reliability evidence is limited.")
        if not counter:
            risks.append("This candidate has less project or experience-level evidence than stronger profiles in the slate.")

        existing_strengths = ranking.get("strengths", []) or []
        existing_risks = ranking.get("risks", []) or ranking.get("weaknesses", []) or []
        ranking["strengths"] = _dedupe_across_slate(strengths + existing_strengths, used_shapes, limit=2)
        ranking["risks"] = _dedupe_local(risks + existing_risks, limit=2)
        ranking["weaknesses"] = ranking["risks"]
        ranking["interview_focus_areas"] = _dedupe_local(ranking.get("interview_focus_areas", []) or [], limit=2)

        if strengths:
            ranking["recruiter_decision_summary"] = _summary_with_differentiator(
                ranking.get("recruiter_decision_summary", ""),
                strengths[0],
            )
            ranking["recruiter_summary"] = ranking["recruiter_decision_summary"]

        _trim_candidate_outputs(candidate)


def _strong_categories(candidate: dict) -> list[str]:
    ranking = candidate.get("ranking", {})
    snippets_by_pillar = ranking.get("supporting_evidence_snippets", {}) or {}
    categories = []
    seen_snippets = set()
    for snippets in snippets_by_pillar.values():
        for snippet in snippets or []:
            evidence_id = snippet.get("evidence_id") or snippet.get("chunk_id") or snippet.get("snippet", "")
            if evidence_id in seen_snippets:
                continue
            seen_snippets.add(evidence_id)
            if not is_strong_evidence(snippet):
                continue
            category = evidence_category(snippet.get("snippet", ""))
            if category:
                categories.append(category)
    return categories


def _category_examples(candidate: dict) -> dict[str, dict]:
    ranking = candidate.get("ranking", {})
    snippets_by_pillar = ranking.get("supporting_evidence_snippets", {}) or {}
    examples = {}
    seen_snippets = set()
    for snippets in snippets_by_pillar.values():
        for snippet in snippets or []:
            evidence_id = snippet.get("evidence_id") or snippet.get("chunk_id") or snippet.get("snippet", "")
            if evidence_id in seen_snippets or not is_strong_evidence(snippet):
                continue
            seen_snippets.add(evidence_id)
            category = evidence_category(snippet.get("snippet", ""))
            if category and category not in examples:
                examples[category] = snippet
    return examples


def _unique_strength_text(category: str, snippet: dict | None) -> str:
    if snippet:
        return f"Distinctive {category} signal from {snippet.get('source_label', 'resume evidence')}."
    return f"Distinctive {category} signal compared with this slate."


def _best_strength_text(category: str, snippet: dict | None) -> str:
    if snippet:
        return f"Strongest {category} evidence in the slate comes from {snippet.get('source_label', 'resume evidence')}."
    return f"Strongest {category} evidence in the compared slate."


def _summary_with_differentiator(summary: str, differentiator: str) -> str:
    cleaned = (summary or "").strip()
    if not cleaned:
        return differentiator
    if differentiator.lower() in cleaned.lower():
        return cleaned
    return f"{differentiator} {cleaned}"


def _trim_candidate_outputs(candidate: dict) -> None:
    ranking = candidate.get("ranking", {})
    ranking["strengths"] = _dedupe_local(ranking.get("strengths", []) or [], limit=2)
    ranking["risks"] = _dedupe_local(ranking.get("risks", []) or ranking.get("weaknesses", []) or [], limit=2)
    ranking["weaknesses"] = ranking["risks"]
    ranking["interview_focus_areas"] = _dedupe_local(ranking.get("interview_focus_areas", []) or [], limit=2)


def _dedupe_across_slate(items: list[str], used_shapes: set[str], limit: int) -> list[str]:
    selected = []
    for item in _dedupe_local(items, limit=8):
        shape = _shape(item)
        if shape in used_shapes and not item.lower().startswith(("only candidate", "strongest")):
            continue
        used_shapes.add(shape)
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def _dedupe_local(items: list[str], limit: int) -> list[str]:
    selected = []
    seen = set()
    for item in items:
        cleaned = " ".join((item or "").split())
        if not cleaned:
            continue
        shape = _shape(cleaned)
        if shape in seen:
            continue
        seen.add(shape)
        selected.append(cleaned)
        if len(selected) >= limit:
            break
    return selected


def _shape(text: str) -> str:
    words = [
        word.strip(".,:;()[]{}").lower()
        for word in text.split()
        if len(word.strip(".,:;()[]{}")) > 2
    ]
    return " ".join(words[:6])
