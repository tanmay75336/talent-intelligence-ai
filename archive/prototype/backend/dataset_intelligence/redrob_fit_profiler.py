from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import mean, median
from typing import Any

from backend.dataset_intelligence.loader import iter_dataset_records
from backend.utils.skill_taxonomy import normalize_whitespace


AI_INFRA_TERMS = {
    "embeddings",
    "embedding",
    "retrieval",
    "vector database",
    "vector search",
    "ranking",
    "recommendation",
    "recommender",
    "search systems",
    "semantic search",
    "rag",
    "faiss",
    "pinecone",
    "weaviate",
    "qdrant",
    "milvus",
    "elasticsearch",
    "opensearch",
}
PRODUCTION_TERMS = {
    "deployed",
    "production",
    "users",
    "scale",
    "scaled",
    "latency",
    "monitoring",
    "pipeline",
    "pipelines",
    "inference",
    "serving",
    "observability",
}
AI_SKILL_TERMS = {
    "ai",
    "ml",
    "machine learning",
    "llm",
    "nlp",
    "rag",
    "langchain",
    "openai",
    "embedding",
    "vector",
    "semantic search",
    "fine-tuning",
}
FRAMEWORK_ONLY_TERMS = {"langchain", "openai", "prompt engineering", "chatgpt"}
FOUNDATION_TERMS = {"retrieval", "ranking", "recommendation", "mlops", "vector", "embedding", "model serving"}
RESEARCH_TERMS = {"research", "paper", "papers", "publication", "publications", "academic"}
MANAGEMENT_TERMS = {"manager", "management", "leadership", "operations", "program manager", "project manager"}
TECHNICAL_HANDS_ON_TERMS = {"built", "implemented", "deployed", "designed", "engineered", "coded", "shipped", "optimized"}

NUMERIC_SIGNAL_FIELDS = [
    "profile_completeness_score",
    "profile_views_received_30d",
    "applications_submitted_30d",
    "recruiter_response_rate",
    "avg_response_time_hours",
    "connection_count",
    "endorsements_received",
    "notice_period_days",
    "github_activity_score",
    "search_appearance_30d",
    "saved_by_recruiters_30d",
    "interview_completion_rate",
    "offer_acceptance_rate",
]
BOOLEAN_SIGNAL_FIELDS = ["open_to_work_flag", "willing_to_relocate", "verified_email", "verified_phone", "linkedin_connected"]
DATE_SIGNAL_FIELDS = ["signup_date", "last_active_date"]


def profile_redrob_dataset(
    candidates_path: str | Path,
    output_dir: str | Path = "outputs",
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    distribution = Counter()
    trap_counts = Counter()
    trap_examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    numeric_values: dict[str, list[float]] = {field: [] for field in NUMERIC_SIGNAL_FIELDS}
    boolean_values: dict[str, Counter] = {field: Counter() for field in BOOLEAN_SIGNAL_FIELDS}
    date_values: dict[str, list[int]] = {field: [] for field in DATE_SIGNAL_FIELDS}
    categorical_values: dict[str, Counter] = {
        "preferred_work_mode": Counter(),
        "country": Counter(),
        "current_industry": Counter(),
        "current_company_size": Counter(),
    }
    assessment_scores: list[float] = []
    total = 0

    for candidate in iter_dataset_records(candidates_path):
        total += 1
        features = extract_candidate_features(candidate)
        distribution[features["fit_bucket"]] += 1
        _update_signal_stats(candidate, numeric_values, boolean_values, date_values, categorical_values, assessment_scores)
        for trap_name in detect_trap_patterns(candidate, features):
            trap_counts[trap_name] += 1
            if len(trap_examples[trap_name]) < 10:
                trap_examples[trap_name].append(_example(candidate, features["evidence"]))

    fit_report = {
        "candidate_count": total,
        "strong_evidence_count": distribution["strong"],
        "medium_evidence_count": distribution["medium"],
        "keyword_only_count": distribution["keyword_only"],
        "unrelated_count": distribution["unrelated"],
        "definitions": {
            "strong": "Career/profile evidence includes AI infrastructure and production evidence.",
            "medium": "Career/profile evidence includes AI infrastructure or production evidence with some AI skill support.",
            "keyword_only": "AI appears in skills/headline/summary but career descriptions lack matching implementation evidence.",
            "unrelated": "No meaningful AI infrastructure, production, or AI keyword evidence detected.",
        },
    }
    trap_report = {
        "candidate_count": total,
        "trap_counts": dict(trap_counts),
        "trap_examples": dict(trap_examples),
        "analysis_note": "Discovery only; no candidates removed or reweighted.",
    }
    behavior_report = {
        "candidate_count": total,
        "numeric_fields": {field: _numeric_summary(values) for field, values in numeric_values.items()},
        "boolean_fields": {field: dict(counter) for field, counter in boolean_values.items()},
        "date_fields_days_since": {field: _numeric_summary(values) for field, values in date_values.items()},
        "categorical_fields": {field: counter.most_common(12) for field, counter in categorical_values.items()},
        "skill_assessment_scores": _numeric_summary(assessment_scores),
        "high_quality_indicator_notes": _behavior_notes(numeric_values, assessment_scores),
    }
    reasoning_inventory = build_reasoning_signal_inventory(fit_report, behavior_report)
    strategy_report = build_strategy_report(fit_report, trap_report, behavior_report)

    _write_json(output / "redrob_fit_distribution_report.json", fit_report)
    _write_json(output / "trap_pattern_report.json", trap_report)
    _write_json(output / "redrob_behavioral_signal_study.json", behavior_report)
    (output / "reasoning_signal_inventory.md").write_text(reasoning_inventory, encoding="utf-8")
    (output / "redrob_dataset_strategy_report.md").write_text(strategy_report, encoding="utf-8")
    return {
        "fit_report": fit_report,
        "trap_report": trap_report,
        "behavior_report": behavior_report,
        "reasoning_inventory": reasoning_inventory,
        "strategy_report": strategy_report,
    }


def extract_candidate_features(candidate: dict[str, Any]) -> dict[str, Any]:
    profile = _dict(candidate.get("profile"))
    career = _list(candidate.get("career_history"))
    skills = _list(candidate.get("skills"))
    career_text = " ".join(str(item.get("description") or "") for item in career if isinstance(item, dict)).lower()
    profile_text = " ".join(str(profile.get(key) or "") for key in ("headline", "summary", "current_title", "current_industry")).lower()
    skill_text = " ".join(str(item.get("name") or "") for item in skills if isinstance(item, dict)).lower()
    all_text = " ".join([career_text, profile_text, skill_text])

    ai_infra_hits = _hits(career_text + " " + profile_text, AI_INFRA_TERMS)
    production_hits = _hits(career_text + " " + profile_text, PRODUCTION_TERMS)
    ai_skill_hits = _hits(skill_text + " " + profile_text, AI_SKILL_TERMS)
    career_ai_hits = _hits(career_text, AI_INFRA_TERMS | AI_SKILL_TERMS)
    keyword_only = bool(ai_skill_hits) and not career_ai_hits
    if ai_infra_hits and production_hits:
        fit_bucket = "strong"
    elif ai_infra_hits or (production_hits and ai_skill_hits):
        fit_bucket = "medium"
    elif keyword_only:
        fit_bucket = "keyword_only"
    else:
        fit_bucket = "unrelated"

    return {
        "fit_bucket": fit_bucket,
        "ai_infra_hits": sorted(ai_infra_hits),
        "production_hits": sorted(production_hits),
        "ai_skill_hits": sorted(ai_skill_hits),
        "career_ai_hits": sorted(career_ai_hits),
        "career_text": career_text,
        "profile_text": profile_text,
        "skill_text": skill_text,
        "all_text": all_text,
        "evidence": _evidence_summary(candidate, sorted(ai_infra_hits), sorted(production_hits), sorted(ai_skill_hits)),
    }


def detect_trap_patterns(candidate: dict[str, Any], features: dict[str, Any] | None = None) -> list[str]:
    features = features or extract_candidate_features(candidate)
    profile = _dict(candidate.get("profile"))
    skills = [item for item in _list(candidate.get("skills")) if isinstance(item, dict)]
    years = _float(profile.get("years_of_experience"))
    ai_skills = [skill for skill in skills if _contains_any(str(skill.get("name", "")).lower(), AI_SKILL_TERMS)]
    low_duration_ai_skills = [
        skill for skill in ai_skills if _float(skill.get("duration_months")) < 12 and _float(skill.get("endorsements")) <= 5
    ]
    advanced_skills = [
        skill for skill in skills if str(skill.get("proficiency", "")).lower() in {"advanced", "expert"}
    ]
    traps = []
    if len(ai_skills) >= 5 and len(low_duration_ai_skills) >= 3 and not features["career_ai_hits"]:
        traps.append("keyword_stuffer")
    if years >= 8 and _contains_any(features["profile_text"], MANAGEMENT_TERMS) and not _contains_any(features["career_text"], TECHNICAL_HANDS_ON_TERMS):
        traps.append("fake_senior_or_hands_off")
    if _contains_any(features["all_text"], FRAMEWORK_ONLY_TERMS) and not _contains_any(features["all_text"], FOUNDATION_TERMS):
        traps.append("framework_only_profile")
    if _contains_any(features["all_text"], RESEARCH_TERMS) and not _contains_any(features["all_text"], PRODUCTION_TERMS):
        traps.append("research_only_mismatch")
    if years < 2 and len(advanced_skills) >= 10:
        traps.append("possible_impossible_profile")
    return traps


def build_reasoning_signal_inventory(fit_report: dict[str, Any], behavior_report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Reasoning Signal Inventory",
            "",
            "## Safe Candidate Facts",
            "- Years of experience: available in `profile.years_of_experience`.",
            "- Current title/company/company size/industry: available in `profile`.",
            "- Career descriptions: available in `career_history.description` and suitable for production/vector/ranking evidence when explicitly present.",
            "- Skills with proficiency, endorsements, and duration: available in `skills`.",
            "- Education and certifications: available as structured arrays.",
            "- RedRob behavioral signals: available in `redrob_signals`, including GitHub activity, assessments, availability, recruiter response, and interview/offer behavior.",
            "",
            "## Reasoning Claims That Need Evidence Checks",
            "- Production systems should be mentioned only when career descriptions include deployed, production, users, scale, latency, monitoring, inference, or pipeline evidence.",
            "- Vector search or retrieval should be mentioned only when profile/career/skills explicitly include retrieval, embeddings, vector databases, FAISS, Pinecone, Weaviate, Qdrant, Milvus, Elasticsearch, or OpenSearch.",
            "- Ranking or recommendation systems should be mentioned only when those words or close variants appear in candidate evidence.",
            "- Availability should cite concrete RedRob fields such as open_to_work_flag, last_active_date, recruiter_response_rate, notice_period_days, or willing_to_relocate.",
            "",
            "## Dataset Evidence Availability",
            f"- Strong AI infrastructure evidence candidates: {fit_report['strong_evidence_count']}",
            f"- Medium evidence candidates: {fit_report['medium_evidence_count']}",
            f"- Keyword-only candidates: {fit_report['keyword_only_count']}",
            f"- Unrelated candidates: {fit_report['unrelated_count']}",
            f"- Skill assessment score summary: {behavior_report['skill_assessment_scores']}",
        ]
    )


def build_strategy_report(fit_report: dict[str, Any], trap_report: dict[str, Any], behavior_report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# RedRob Dataset Strategy Report",
            "",
            "## 1. Dataset Overview",
            f"- Candidates streamed: {fit_report['candidate_count']}",
            "- Schema includes profile, career history, education, skills, certifications, languages, and RedRob behavioral signals.",
            "",
            "## 2. Senior AI Engineer Signal Availability",
            f"- Strong evidence count: {fit_report['strong_evidence_count']}",
            f"- Medium evidence count: {fit_report['medium_evidence_count']}",
            f"- Keyword-only count: {fit_report['keyword_only_count']}",
            f"- Unrelated count: {fit_report['unrelated_count']}",
            "",
            "## 3. Strong Candidate Patterns",
            "- Career descriptions combine AI infrastructure language with production evidence.",
            "- Skills include retrieval, vector search, ranking, recommendation, Python, NLP, or LLM systems and are backed by work history.",
            "- Behavioral signals may show activity, recruiter responsiveness, GitHub activity, and completed assessments.",
            "",
            "## 4. Weak Candidate Patterns",
            "- AI appears mostly in skills/headline but not in career descriptions.",
            "- Profiles emphasize management, operations, marketing, support, or consulting without hands-on technical delivery.",
            "- Computer vision, speech, or robotics profiles may be adjacent but are weaker without NLP/retrieval/ranking evidence.",
            "",
            "## 5. Trap Risks",
            *[f"- {name}: {count}" for name, count in sorted(trap_report["trap_counts"].items())],
            "",
            "## 6. Behavioral Signal Findings",
            f"- Recruiter response rate: {behavior_report['numeric_fields'].get('recruiter_response_rate')}",
            f"- GitHub activity score: {behavior_report['numeric_fields'].get('github_activity_score')}",
            f"- Saved by recruiters 30d: {behavior_report['numeric_fields'].get('saved_by_recruiters_30d')}",
            f"- Interview completion rate: {behavior_report['numeric_fields'].get('interview_completion_rate')}",
            "",
            "## 7. Recommended Phase 4 Ranking Improvements",
            "- Add evidence-backed boosts for retrieval/ranking/vector-search career descriptions, not just skill tags.",
            "- Add penalties or confidence reductions for keyword-only AI profiles.",
            "- Add behavioral availability as a modifier after technical fit is established.",
            "- Add explicit trap detection diagnostics for review, without silently dropping candidates.",
            "- Strengthen reasoning to cite concrete career-history and RedRob signal facts.",
        ]
    )


def _update_signal_stats(
    candidate: dict[str, Any],
    numeric_values: dict[str, list[float]],
    boolean_values: dict[str, Counter],
    date_values: dict[str, list[int]],
    categorical_values: dict[str, Counter],
    assessment_scores: list[float],
) -> None:
    profile = _dict(candidate.get("profile"))
    signals = _dict(candidate.get("redrob_signals"))
    for field in NUMERIC_SIGNAL_FIELDS:
        value = _float(signals.get(field), default=None)
        if value is not None:
            numeric_values[field].append(value)
    salary = _dict(signals.get("expected_salary_range_inr_lpa"))
    for key in ("min", "max"):
        field = f"expected_salary_range_inr_lpa.{key}"
        numeric_values.setdefault(field, [])
        value = _float(salary.get(key), default=None)
        if value is not None:
            numeric_values[field].append(value)
    for field in BOOLEAN_SIGNAL_FIELDS:
        if field in signals:
            boolean_values[field][str(bool(signals.get(field)))] += 1
    for field in DATE_SIGNAL_FIELDS:
        days = _days_since(signals.get(field))
        if days is not None:
            date_values[field].append(days)
    categorical_values["preferred_work_mode"][str(signals.get("preferred_work_mode", "missing"))] += 1
    categorical_values["country"][str(profile.get("country", "missing"))] += 1
    categorical_values["current_industry"][str(profile.get("current_industry", "missing"))] += 1
    categorical_values["current_company_size"][str(profile.get("current_company_size", "missing"))] += 1
    assessment = _dict(signals.get("skill_assessment_scores"))
    for value in assessment.values():
        numeric_value = _float(value, default=None)
        if numeric_value is not None:
            assessment_scores.append(numeric_value)


def _behavior_notes(numeric_values: dict[str, list[float]], assessment_scores: list[float]) -> list[str]:
    notes = []
    for field in (
        "github_activity_score",
        "recruiter_response_rate",
        "saved_by_recruiters_30d",
        "search_appearance_30d",
        "interview_completion_rate",
        "offer_acceptance_rate",
    ):
        summary = _numeric_summary(numeric_values.get(field, []))
        notes.append(f"{field}: median={summary.get('median')}, p90={summary.get('p90')}, count={summary.get('count')}")
    notes.append(f"skill_assessment_scores: {_numeric_summary(assessment_scores)}")
    return notes


def _numeric_summary(values: list[float]) -> dict[str, float | int | None]:
    cleaned = sorted(value for value in values if value is not None and not math.isnan(value))
    if not cleaned:
        return {"count": 0, "min": None, "max": None, "mean": None, "median": None, "p25": None, "p75": None, "p90": None, "p95": None}
    return {
        "count": len(cleaned),
        "min": round(cleaned[0], 4),
        "max": round(cleaned[-1], 4),
        "mean": round(mean(cleaned), 4),
        "median": round(median(cleaned), 4),
        "p25": round(_percentile(cleaned, 0.25), 4),
        "p75": round(_percentile(cleaned, 0.75), 4),
        "p90": round(_percentile(cleaned, 0.90), 4),
        "p95": round(_percentile(cleaned, 0.95), 4),
    }


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    index = (len(values) - 1) * pct
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return values[int(index)]
    return values[lower] + ((values[upper] - values[lower]) * (index - lower))


def _evidence_summary(candidate: dict[str, Any], ai_hits: list[str], production_hits: list[str], skill_hits: list[str]) -> dict[str, Any]:
    profile = _dict(candidate.get("profile"))
    career = _list(candidate.get("career_history"))
    first_description = ""
    for item in career:
        if isinstance(item, dict) and item.get("description"):
            first_description = normalize_whitespace(str(item.get("description")))
            break
    return {
        "candidate_id": candidate.get("candidate_id"),
        "title": profile.get("current_title"),
        "years_of_experience": profile.get("years_of_experience"),
        "ai_infra_hits": ai_hits[:8],
        "production_hits": production_hits[:8],
        "skill_hits": skill_hits[:8],
        "career_evidence": first_description[:240],
    }


def _example(candidate: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    return {"candidate_id": candidate.get("candidate_id"), "evidence": evidence}


def _hits(text: str, terms: set[str]) -> set[str]:
    return {term for term in terms if term in text}


def _contains_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _float(value: Any, default: float | None = 0.0) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _days_since(value: Any) -> int | None:
    if not value:
        return None
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None
    return (date(2026, 6, 2) - parsed).days


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile RedRob dataset fit and signal distributions.")
    parser.add_argument("--candidates", default="data/candidates.jsonl")
    parser.add_argument("--output-dir", default="outputs")
    args = parser.parse_args()
    profile_redrob_dataset(args.candidates, args.output_dir)
    print(f"Wrote RedRob dataset intelligence outputs to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
