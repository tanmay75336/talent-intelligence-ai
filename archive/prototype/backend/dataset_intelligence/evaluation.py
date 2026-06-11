from __future__ import annotations

from itertools import combinations

from backend.dataset_intelligence.models import RankingEvaluationResult, StrategyComparisonReport
from backend.dataset_intelligence.reporting import build_strategy_markdown_report


def evaluate_ranking(
    strategy_name: str,
    predicted_order: list[str],
    expected_order: list[str] | None = None,
    positive_candidates: list[str] | None = None,
    negative_candidates: list[str] | None = None,
    hidden_gems: list[str] | None = None,
    previous_order: list[str] | None = None,
    top_k_values: tuple[int, ...] = (3, 5, 10),
) -> RankingEvaluationResult:
    predicted_order = _dedupe(predicted_order)
    expected_order = _dedupe(expected_order or [])
    positives = set(positive_candidates or expected_order)
    negatives = set(negative_candidates or [])
    hidden = set(hidden_gems or [])
    notes = []

    pairwise_accuracy = _pairwise_accuracy(predicted_order, expected_order) if expected_order else None
    ranking_accuracy = _ranking_accuracy(predicted_order, expected_order) if expected_order else None
    top_k_quality = {
        f"top_{k}": _top_k_quality(predicted_order, positives, k)
        for k in top_k_values
        if positives
    }
    false_positive_rate = _false_positive_rate(predicted_order, negatives) if negatives else None
    false_negative_rate = _false_negative_rate(predicted_order, positives) if positives else None
    hidden_gem_detection_rate = _hidden_gem_detection(predicted_order, hidden) if hidden else None
    ranking_stability = _pairwise_accuracy(predicted_order, previous_order) if previous_order else None

    if pairwise_accuracy is not None and pairwise_accuracy < 0.75:
        notes.append(f"{strategy_name}: pairwise accuracy is below 0.75.")
    if false_positive_rate is not None and false_positive_rate > 0.25:
        notes.append(f"{strategy_name}: false positive rate is high.")
    if false_negative_rate is not None and false_negative_rate > 0.25:
        notes.append(f"{strategy_name}: false negative rate is high.")
    if hidden_gem_detection_rate is not None and hidden_gem_detection_rate < 1.0:
        notes.append(f"{strategy_name}: not all hidden gems surfaced above the bottom quartile.")

    return RankingEvaluationResult(
        strategy_name=strategy_name,
        candidate_count=len(predicted_order),
        pairwise_accuracy=pairwise_accuracy,
        ranking_accuracy=ranking_accuracy,
        top_k_quality=top_k_quality,
        false_positive_rate=false_positive_rate,
        false_negative_rate=false_negative_rate,
        hidden_gem_detection_rate=hidden_gem_detection_rate,
        ranking_stability=ranking_stability,
        notes=notes,
    )


def compare_ranking_strategies(
    strategies: dict[str, list[str]],
    expected_order: list[str] | None = None,
    positive_candidates: list[str] | None = None,
    negative_candidates: list[str] | None = None,
    hidden_gems: list[str] | None = None,
    baseline_strategy: str | None = None,
) -> StrategyComparisonReport:
    baseline_order = strategies.get(baseline_strategy or "", [])
    results = [
        evaluate_ranking(
            strategy_name=name,
            predicted_order=order,
            expected_order=expected_order,
            positive_candidates=positive_candidates,
            negative_candidates=negative_candidates,
            hidden_gems=hidden_gems,
            previous_order=baseline_order if baseline_order and name != baseline_strategy else None,
        )
        for name, order in strategies.items()
    ]
    report = StrategyComparisonReport(results=results, best_strategy=_best_strategy(results))
    report.markdown_report = build_strategy_markdown_report(report)
    return report


def evaluate_ranked_candidate_trust(ranked_candidates: list[dict]) -> dict[str, float | int]:
    """Lightweight trust-readiness metrics for deterministic ranked outputs."""
    if not ranked_candidates:
        return {
            "candidate_count": 0,
            "close_call_rate": 0.0,
            "high_confidence_rate": 0.0,
            "weak_evidence_high_confidence_count": 0,
            "average_insight_count": 0.0,
        }

    close_count = 0
    high_confidence_count = 0
    weak_evidence_high_confidence_count = 0
    insight_counts = []
    for candidate in ranked_candidates:
        ranking = candidate.get("ranking", {})
        if ranking.get("ordering_confidence") == "Close" or ranking.get("close_call_with"):
            close_count += 1
        if ranking.get("recruiter_confidence") == "High":
            high_confidence_count += 1
        decisive_count = len(ranking.get("decisive_evidence_ids", []) or [])
        if ranking.get("recruiter_confidence") == "High" and decisive_count == 0:
            weak_evidence_high_confidence_count += 1
        insight_counts.append(
            len(ranking.get("strengths", []) or [])
            + len(ranking.get("risks", []) or [])
            + len(ranking.get("interview_focus_areas", []) or [])
        )

    total = len(ranked_candidates)
    return {
        "candidate_count": total,
        "close_call_rate": round(close_count / total, 4),
        "high_confidence_rate": round(high_confidence_count / total, 4),
        "weak_evidence_high_confidence_count": weak_evidence_high_confidence_count,
        "average_insight_count": round(sum(insight_counts) / total, 4),
    }


def _pairwise_accuracy(predicted_order: list[str], expected_order: list[str] | None) -> float:
    if not expected_order:
        return 0.0
    predicted_positions = {candidate: index for index, candidate in enumerate(predicted_order)}
    comparable = 0
    correct = 0
    for left, right in combinations(expected_order, 2):
        if left not in predicted_positions or right not in predicted_positions:
            continue
        comparable += 1
        if predicted_positions[left] < predicted_positions[right]:
            correct += 1
    return round(correct / comparable, 4) if comparable else 0.0


def _ranking_accuracy(predicted_order: list[str], expected_order: list[str]) -> float:
    if not expected_order:
        return 0.0
    predicted_positions = {candidate: index for index, candidate in enumerate(predicted_order)}
    distances = []
    for expected_position, candidate in enumerate(expected_order):
        if candidate not in predicted_positions:
            distances.append(len(expected_order))
        else:
            distances.append(abs(predicted_positions[candidate] - expected_position))
    max_distance = max(1, len(expected_order) - 1)
    normalized = 1.0 - (sum(distances) / (len(distances) * max_distance))
    return round(max(0.0, normalized), 4)


def _top_k_quality(predicted_order: list[str], positives: set[str], k: int) -> float:
    if not positives:
        return 0.0
    top = set(predicted_order[:k])
    return round(len(top & positives) / min(k, len(positives)), 4)


def _false_positive_rate(predicted_order: list[str], negatives: set[str]) -> float:
    if not negatives:
        return 0.0
    cutoff = max(1, len(predicted_order) // 3)
    top = set(predicted_order[:cutoff])
    return round(len(top & negatives) / len(negatives), 4)


def _false_negative_rate(predicted_order: list[str], positives: set[str]) -> float:
    if not positives:
        return 0.0
    cutoff = max(1, len(predicted_order) // 2)
    top_half = set(predicted_order[:cutoff])
    return round(len(positives - top_half) / len(positives), 4)


def _hidden_gem_detection(predicted_order: list[str], hidden_gems: set[str]) -> float:
    if not hidden_gems:
        return 0.0
    bottom_quartile_start = int(len(predicted_order) * 0.75)
    detected = [
        gem
        for gem in hidden_gems
        if gem in predicted_order and predicted_order.index(gem) < bottom_quartile_start
    ]
    return round(len(detected) / len(hidden_gems), 4)


def _best_strategy(results: list[RankingEvaluationResult]) -> str | None:
    if not results:
        return None

    def score(result: RankingEvaluationResult) -> float:
        value = 0.0
        if result.pairwise_accuracy is not None:
            value += result.pairwise_accuracy * 0.35
        if result.ranking_accuracy is not None:
            value += result.ranking_accuracy * 0.25
        if result.false_positive_rate is not None:
            value += (1 - result.false_positive_rate) * 0.18
        if result.false_negative_rate is not None:
            value += (1 - result.false_negative_rate) * 0.12
        if result.hidden_gem_detection_rate is not None:
            value += result.hidden_gem_detection_rate * 0.10
        return value

    return max(results, key=score).strategy_name


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    output = []
    for value in values:
        key = str(value).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(key)
    return output
