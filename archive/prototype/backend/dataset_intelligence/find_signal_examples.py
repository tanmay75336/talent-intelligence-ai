from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from backend.dataset_intelligence.loader import iter_dataset_records
from backend.dataset_intelligence.redrob_fit_profiler import detect_trap_patterns, extract_candidate_features


EXAMPLE_CATEGORIES = (
    "great_senior_ai_engineer_fit",
    "keyword_stuffer",
    "strong_ml_bad_availability",
    "strong_behavior_weak_jd_fit",
    "possible_hidden_gems",
)


def find_signal_examples(
    candidates_path: str | Path,
    output_path: str | Path = "outputs/example_candidates.json",
    limit_per_category: int = 20,
) -> dict[str, list[dict[str, Any]]]:
    examples: dict[str, list[dict[str, Any]]] = {category: [] for category in EXAMPLE_CATEGORIES}
    for candidate in iter_dataset_records(candidates_path):
        features = extract_candidate_features(candidate)
        for category in _candidate_example_categories(candidate, features):
            if len(examples[category]) < limit_per_category:
                examples[category].append(_candidate_evidence(candidate, features))
        if all(len(items) >= limit_per_category for items in examples.values()):
            break

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(examples, indent=2), encoding="utf-8")
    return examples


def _candidate_example_categories(candidate: dict[str, Any], features: dict[str, Any]) -> list[str]:
    profile = _dict(candidate.get("profile"))
    signals = _dict(candidate.get("redrob_signals"))
    years = _float(profile.get("years_of_experience"))
    traps = set(detect_trap_patterns(candidate, features))
    strong_behavior = (
        _float(signals.get("github_activity_score")) >= 65
        or _float(signals.get("recruiter_response_rate")) >= 0.65
        or _float(signals.get("saved_by_recruiters_30d")) >= 25
    )
    bad_availability = (
        not bool(signals.get("open_to_work_flag"))
        or _float(signals.get("recruiter_response_rate")) < 0.25
        or _float(signals.get("notice_period_days")) >= 120
    )

    categories = []
    if features["fit_bucket"] == "strong" and 5 <= years <= 9 and not traps:
        categories.append("great_senior_ai_engineer_fit")
    if "keyword_stuffer" in traps:
        categories.append("keyword_stuffer")
    if features["fit_bucket"] in {"strong", "medium"} and bad_availability:
        categories.append("strong_ml_bad_availability")
    if strong_behavior and features["fit_bucket"] in {"keyword_only", "unrelated"}:
        categories.append("strong_behavior_weak_jd_fit")
    if features["fit_bucket"] == "medium" and strong_behavior and not traps:
        categories.append("possible_hidden_gems")
    return categories


def _candidate_evidence(candidate: dict[str, Any], features: dict[str, Any]) -> dict[str, Any]:
    profile = _dict(candidate.get("profile"))
    signals = _dict(candidate.get("redrob_signals"))
    return {
        "candidate_id": candidate.get("candidate_id"),
        "evidence": {
            "current_title": profile.get("current_title"),
            "years_of_experience": profile.get("years_of_experience"),
            "fit_bucket": features["fit_bucket"],
            "ai_infra_hits": features["ai_infra_hits"][:8],
            "production_hits": features["production_hits"][:8],
            "ai_skill_hits": features["ai_skill_hits"][:8],
            "career_evidence": features["evidence"]["career_evidence"],
            "redrob_signals": {
                "open_to_work_flag": signals.get("open_to_work_flag"),
                "last_active_date": signals.get("last_active_date"),
                "recruiter_response_rate": signals.get("recruiter_response_rate"),
                "notice_period_days": signals.get("notice_period_days"),
                "github_activity_score": signals.get("github_activity_score"),
                "saved_by_recruiters_30d": signals.get("saved_by_recruiters_30d"),
                "interview_completion_rate": signals.get("interview_completion_rate"),
            },
        },
    }


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Find RedRob manual-inspection signal examples.")
    parser.add_argument("--candidates", default="data/candidates.jsonl")
    parser.add_argument("--output", default="outputs/example_candidates.json")
    args = parser.parse_args()
    find_signal_examples(args.candidates, args.output)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
