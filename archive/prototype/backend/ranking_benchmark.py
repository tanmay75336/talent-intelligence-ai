from __future__ import annotations

from dataclasses import dataclass

from backend.ranking.pipeline import rank_candidate_text
from backend.ranking_benchmark_cases import RANKING_BENCHMARKS, RankingBenchmarkCase
from backend.reasoning.ranking_trust import apply_ranking_trust_analysis
from backend.reasoning.differentiation import apply_candidate_differentiation


@dataclass(frozen=True)
class BenchmarkResult:
    case_name: str
    actual_order: list[str]
    expected_order: list[str]
    pairwise_accuracy: float
    false_positive_pass: bool
    hidden_gem_pass: bool
    notes: list[str]


def run_ranking_benchmarks(cases: list[RankingBenchmarkCase] | None = None) -> list[BenchmarkResult]:
    results = []
    for case in cases or RANKING_BENCHMARKS:
        ranked_candidates = [
            rank_candidate_text(
                resume.resume_text,
                case.jd_text,
                source_name=resume.candidate_name,
            )
            for resume in case.resumes
        ]
        ranked_candidates.sort(key=lambda item: item["ranking"]["final_score"], reverse=True)
        apply_ranking_trust_analysis(ranked_candidates)
        apply_candidate_differentiation(ranked_candidates)
        results.append(evaluate_ranked_candidates(case, ranked_candidates))
    return results


def evaluate_ranked_candidates(case: RankingBenchmarkCase, ranked_candidates: list[dict]) -> BenchmarkResult:
    actual_order = [candidate.get("candidate_name", "") for candidate in ranked_candidates]
    comparable_pairs = 0
    correct_pairs = 0

    for left_index, left_name in enumerate(case.expected_order):
        for right_name in case.expected_order[left_index + 1:]:
            if left_name not in actual_order or right_name not in actual_order:
                continue
            comparable_pairs += 1
            if actual_order.index(left_name) < actual_order.index(right_name):
                correct_pairs += 1

    pairwise_accuracy = correct_pairs / comparable_pairs if comparable_pairs else 0.0
    rejection_cutoff = max(1, len(actual_order) // 2)
    false_positive_pass = all(
        rejected not in actual_order[:rejection_cutoff]
        for rejected in case.expected_rejections
    )
    hidden_gem_pass = all(gem in actual_order and actual_order.index(gem) < len(actual_order) - 1 for gem in case.hidden_gems)
    notes = []
    if pairwise_accuracy < 0.8:
        notes.append("Expected ordering pairwise accuracy is below target.")
    if not false_positive_pass:
        notes.append("At least one expected rejection ranked too high.")
    if not hidden_gem_pass:
        notes.append("Expected hidden gem was not preserved above the bottom of the slate.")

    return BenchmarkResult(
        case_name=case.name,
        actual_order=actual_order,
        expected_order=case.expected_order,
        pairwise_accuracy=round(pairwise_accuracy, 4),
        false_positive_pass=false_positive_pass,
        hidden_gem_pass=hidden_gem_pass,
        notes=notes,
    )


if __name__ == "__main__":
    for result in run_ranking_benchmarks():
        print(result)
