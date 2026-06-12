from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

from backend.competition.evidence_calibrator import calibrate_candidate_evidence
from backend.competition.redrob_adapter import adapt_redrob_candidate
from backend.dataset_intelligence.loader import iter_dataset_records
from backend.utils.skill_taxonomy import normalize_whitespace


AI_INFRASTRUCTURE_TERMS = {
    "retrieval",
    "hybrid retrieval",
    "search ranking",
    "ranking",
    "learning-to-rank",
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
    "rag",
}

PRODUCTION_TERMS = {
    "production",
    "deployed",
    "shipped",
    "scaled",
    "scale",
    "optimized",
    "users",
    "latency",
    "monitoring",
    "observability",
    "pipeline",
    "pipelines",
    "inference",
    "a/b test",
    "ab test",
}

ENGINEERING_TERMS = {
    "python",
    "backend",
    "architecture",
    "distributed",
    "cloud",
    "aws",
    "gcp",
    "azure",
    "kubernetes",
    "docker",
    "spark",
    "kafka",
    "airflow",
    "api",
    "service",
    "services",
}

FOUNDER_FIT_TERMS = {
    "owned",
    "ownership",
    "built from scratch",
    "from scratch",
    "startup",
    "founding",
    "0-1",
    "zero to one",
    "end-to-end",
    "end to end",
    "ambiguous",
    "product",
}

EVALUATION_TERMS = {
    "ndcg",
    "mrr",
    "map",
    "offline evaluation",
    "offline-online",
    "a/b test",
    "ab test",
    "evaluation",
    "feedback loop",
}

WEAKNESS_TERMS = {
    "keyword_heavy": {"interested in", "learning", "transitioning", "self-directed", "side projects"},
    "framework_only": {"langchain", "openai", "chatgpt", "prompt engineering"},
    "research_only": {"research", "paper", "publication", "thesis", "phd"},
    "manager_only": {"managed a team", "supervised", "stakeholder management", "roadmap", "strategy"},
    "wrong_ai_domain": {"computer vision", "image classification", "speech", "tts", "robotics", "gan"},
    "consulting_only": {"consulting", "consultant", "client engagements", "digital transformation strategy"},
}

GENERIC_REASONING_PATTERNS = {
    "great candidate",
    "strong candidate",
    "excellent fit",
    "good fit",
    "strong skills",
    "great ai engineer",
}


def run_top_candidate_audit(
    candidates_path: str | Path = "data/candidates.jsonl",
    submission_path: str | Path = "submission.csv",
    output_dir: str | Path = "outputs",
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    submission_rows = _read_submission(submission_path)
    top50_rows = submission_rows[:50]
    candidates = _load_candidates_for_ids(candidates_path, [row["candidate_id"] for row in top50_rows])

    audits = []
    for row in top50_rows:
        raw_candidate = candidates[row["candidate_id"]]
        audits.append(_audit_candidate(row, raw_candidate))

    close_decisions = _close_rank_decisions(audits)
    reasoning_report = _reasoning_quality_report(submission_rows)
    top10_report = _top10_quality_report(audits, close_decisions, reasoning_report)

    audit_payload = {
        "audit_scope": "current submission ranks 1-50",
        "evaluation_priority": {
            "NDCG@10": "50%",
            "NDCG@50": "30%",
            "MAP": "15%",
            "P@10": "5%",
        },
        "candidates": audits,
        "rank_separation": _rank_separation(audits),
    }

    _write_json(output / "top_candidate_audit.json", audit_payload)
    _write_json(output / "close_rank_decisions.json", close_decisions)
    (output / "reasoning_quality_report.md").write_text(reasoning_report["markdown"], encoding="utf-8")
    (output / "top10_quality_report.md").write_text(top10_report, encoding="utf-8")

    return {
        "top_candidate_audit": audit_payload,
        "close_rank_decisions": close_decisions,
        "reasoning_quality": reasoning_report,
        "top10_quality_report": top10_report,
    }


def _audit_candidate(row: dict[str, str], raw_candidate: dict[str, Any]) -> dict[str, Any]:
    profile = adapt_redrob_candidate(raw_candidate)
    calibration = calibrate_candidate_evidence(profile)
    career_text = normalize_whitespace(" ".join(str(item.get("description") or "") for item in profile.career_history))
    profile_text = normalize_whitespace(" ".join([profile.summary, profile.searchable_profile_text]))
    skill_text = normalize_whitespace(" ".join(profile.skills))
    career_lower = career_text.lower()
    combined_lower = " ".join([profile_text, skill_text]).lower()

    categories = {
        "ai_infrastructure": _hits(career_lower, AI_INFRASTRUCTURE_TERMS),
        "production_evidence": _hits(career_lower, PRODUCTION_TERMS),
        "engineering_depth": _hits(career_lower + " " + combined_lower, ENGINEERING_TERMS),
        "founder_fit": _hits(career_lower + " " + combined_lower, FOUNDER_FIT_TERMS),
        "ranking_retrieval_evaluation": _hits(career_lower, EVALUATION_TERMS),
    }
    weaknesses = _weakness_indicators(career_lower, combined_lower, categories, calibration.trap_flags)
    redrob = profile.redrob_signals
    evidence_excerpt = _best_excerpt(career_text, set(categories["ai_infrastructure"] + categories["production_evidence"]))

    return {
        "candidate_id": row["candidate_id"],
        "current_rank": int(row["rank"]),
        "score": float(row["score"]),
        "current_title": profile.structured_profile.get("current_title", ""),
        "current_company": profile.structured_profile.get("current_company", ""),
        "years_of_experience": profile.years_of_experience,
        "reasoning": row.get("reasoning", ""),
        "evidence_categories": categories,
        "weakness_indicators": weaknesses,
        "calibration": {
            "adjustment": calibration.adjustment,
            "career_ai_infra_hits": calibration.career_ai_infra_hits,
            "production_hits": calibration.production_hits,
            "ownership_hits": calibration.ownership_hits,
            "trap_flags": calibration.trap_flags,
            "behavioral_tie_breaker": calibration.behavioral_tie_breaker,
        },
        "redrob_modifiers": {
            "github_activity_score": redrob.get("github_activity_score"),
            "skill_assessment_scores": redrob.get("skill_assessment_scores"),
            "recruiter_response_rate": redrob.get("recruiter_response_rate"),
            "saved_by_recruiters_30d": redrob.get("saved_by_recruiters_30d"),
            "interview_completion_rate": redrob.get("interview_completion_rate"),
            "last_active_date": redrob.get("last_active_date"),
            "open_to_work_flag": redrob.get("open_to_work_flag"),
            "willing_to_relocate": redrob.get("willing_to_relocate"),
        },
        "evidence_excerpt": evidence_excerpt,
        "audit_summary": _audit_summary(categories, weaknesses),
    }


def _rank_separation(audits: list[dict[str, Any]]) -> dict[str, Any]:
    groups = {
        "rank_1_10": [item for item in audits if item["current_rank"] <= 10],
        "rank_11_25": [item for item in audits if 11 <= item["current_rank"] <= 25],
        "rank_26_50": [item for item in audits if 26 <= item["current_rank"] <= 50],
    }
    return {name: _group_summary(items) for name, items in groups.items()}


def _group_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {}
    return {
        "count": len(items),
        "avg_score": round(mean(item["score"] for item in items), 6),
        "avg_ai_infrastructure_hits": round(mean(len(item["evidence_categories"]["ai_infrastructure"]) for item in items), 2),
        "avg_production_hits": round(mean(len(item["evidence_categories"]["production_evidence"]) for item in items), 2),
        "avg_evaluation_hits": round(mean(len(item["evidence_categories"]["ranking_retrieval_evaluation"]) for item in items), 2),
        "avg_founder_fit_hits": round(mean(len(item["evidence_categories"]["founder_fit"]) for item in items), 2),
        "weakness_counts": dict(Counter(flag for item in items for flag in item["weakness_indicators"])),
        "notable_candidates": [
            {
                "candidate_id": item["candidate_id"],
                "rank": item["current_rank"],
                "score": item["score"],
                "ai_hits": item["evidence_categories"]["ai_infrastructure"][:5],
                "production_hits": item["evidence_categories"]["production_evidence"][:5],
                "weaknesses": item["weakness_indicators"],
            }
            for item in sorted(
                items,
                key=lambda item: (
                    -len(item["evidence_categories"]["ai_infrastructure"]),
                    -len(item["evidence_categories"]["production_evidence"]),
                    item["current_rank"],
                ),
            )[:5]
        ],
    }


def _close_rank_decisions(audits: list[dict[str, Any]], max_gap: float = 0.006) -> dict[str, Any]:
    adjacent = []
    for left, right in zip(audits, audits[1:]):
        gap = round(left["score"] - right["score"], 6)
        if gap <= max_gap:
            adjacent.append(_decision_pair(left, right, gap))

    missed_candidates = []
    top10_min_score = audits[9]["score"] if len(audits) >= 10 else 0.0
    for candidate in audits[10:50]:
        ai_hits = len(candidate["evidence_categories"]["ai_infrastructure"])
        production_hits = len(candidate["evidence_categories"]["production_evidence"])
        if top10_min_score - candidate["score"] <= 0.025 and ai_hits >= 4 and production_hits >= 2:
            missed_candidates.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "rank": candidate["current_rank"],
                    "score": candidate["score"],
                    "score_gap_to_rank10": round(top10_min_score - candidate["score"], 6),
                    "reason_to_review": "near top-10 score with strong retrieval/ranking/vector and production evidence",
                    "ai_hits": candidate["evidence_categories"]["ai_infrastructure"],
                    "production_hits": candidate["evidence_categories"]["production_evidence"],
                    "weaknesses": candidate["weakness_indicators"],
                }
            )

    return {
        "close_score_threshold": max_gap,
        "adjacent_close_decisions": adjacent,
        "possible_missed_top10_candidates_from_ranks_11_50": missed_candidates[:15],
    }


def _decision_pair(left: dict[str, Any], right: dict[str, Any], gap: float) -> dict[str, Any]:
    return {
        "higher_rank": {
            "rank": left["current_rank"],
            "candidate_id": left["candidate_id"],
            "score": left["score"],
            "ai_hits": left["evidence_categories"]["ai_infrastructure"][:6],
            "production_hits": left["evidence_categories"]["production_evidence"][:6],
            "weaknesses": left["weakness_indicators"],
        },
        "lower_rank": {
            "rank": right["current_rank"],
            "candidate_id": right["candidate_id"],
            "score": right["score"],
            "ai_hits": right["evidence_categories"]["ai_infrastructure"][:6],
            "production_hits": right["evidence_categories"]["production_evidence"][:6],
            "weaknesses": right["weakness_indicators"],
        },
        "score_gap": gap,
        "why_current_order_exists": "current score is higher after existing base score plus Phase 4A evidence calibration; this audit does not reorder candidates",
        "audit_note": _close_pair_note(left, right),
    }


def _reasoning_quality_report(submission_rows: list[dict[str, str]]) -> dict[str, Any]:
    sampled = submission_rows[:100]
    problems = []
    phrase_counter = Counter()
    for row in sampled:
        reasoning = row.get("reasoning", "")
        lowered = reasoning.lower()
        phrase_counter[_reasoning_template(lowered)] += 1
        row_problems = []
        if len(reasoning.split()) < 14:
            row_problems.append("too_short")
        if any(pattern in lowered for pattern in GENERIC_REASONING_PATTERNS):
            row_problems.append("generic_praise")
        if "jd match" not in lowered and "jd skill overlap" not in lowered:
            row_problems.append("missing_explicit_jd_connection")
        if "years as" not in lowered:
            row_problems.append("missing_years_title_fact")
        if "..." in reasoning:
            row_problems.append("truncated_evidence")
        if row_problems:
            problems.append({"rank": int(row["rank"]), "candidate_id": row["candidate_id"], "problems": row_problems, "reasoning": reasoning})

    repeated_openers = [
        {"phrase": phrase, "count": count}
        for phrase, count in phrase_counter.most_common()
        if count >= 3
    ]
    markdown = _reasoning_markdown(problems, repeated_openers, sampled)
    return {
        "rows_checked": len(sampled),
        "problem_count": len(problems),
        "problems": problems[:50],
        "repeated_openers": repeated_openers[:20],
        "markdown": markdown,
    }


def _top10_quality_report(audits: list[dict[str, Any]], close_decisions: dict[str, Any], reasoning_report: dict[str, Any]) -> str:
    top10 = audits[:10]
    rank_sep = _rank_separation(audits)
    missed = close_decisions["possible_missed_top10_candidates_from_ranks_11_50"]
    top10_lines = [
        f"- Rank {item['current_rank']} `{item['candidate_id']}`: {item['years_of_experience']:.1f} years, {item['current_title']}; "
        f"AI hits={item['evidence_categories']['ai_infrastructure'][:5]}, production hits={item['evidence_categories']['production_evidence'][:5]}, weaknesses={item['weakness_indicators'] or []}."
        for item in top10
    ]
    missed_lines = [
        f"- Rank {item['rank']} `{item['candidate_id']}` trails rank 10 by {item['score_gap_to_rank10']:.6f}; AI hits={item['ai_hits'][:6]}, production hits={item['production_hits'][:6]}, weaknesses={item['weaknesses'] or []}."
        for item in missed[:10]
    ] or ["- No rank 11-50 candidate met the near-top10 plus strong-evidence review threshold."]

    decision = _decision_gate(audits, missed, reasoning_report)
    return "\n".join(
        [
            "# Top 10 Quality Report",
            "",
            "## 1. Current Top 10 Summary",
            *top10_lines,
            "",
            "## 2. Why Top Candidates Win",
            "- The top 10 mostly show career-backed retrieval, ranking, recommendation, embeddings, vector search, or inference evidence rather than skills-only claims.",
            "- Several top candidates include production ownership terms such as shipped, production, users, monitoring, latency, or pipelines.",
            "- RedRob behavioral signals are present in reasoning only as secondary facts and do not appear to dominate technical evidence.",
            "",
            "## 3. Rank Separation Analysis",
            f"- Rank 1-10 average AI infrastructure hits: {rank_sep['rank_1_10']['avg_ai_infrastructure_hits']}; average production hits: {rank_sep['rank_1_10']['avg_production_hits']}.",
            f"- Rank 11-25 average AI infrastructure hits: {rank_sep['rank_11_25']['avg_ai_infrastructure_hits']}; average production hits: {rank_sep['rank_11_25']['avg_production_hits']}.",
            f"- Rank 26-50 average AI infrastructure hits: {rank_sep['rank_26_50']['avg_ai_infrastructure_hits']}; average production hits: {rank_sep['rank_26_50']['avg_production_hits']}.",
            "",
            "## 4. Possible Missed Candidates",
            *missed_lines,
            "",
            "## 5. Ranking Weaknesses",
            "- Some top-10 entries are weaker on explicit retrieval/ranking/vector career evidence than nearby ranks 11-20.",
            "- Evaluation framework evidence such as NDCG, MRR, MAP, offline-online correlation, or A/B testing is sparse and not visibly separating the top 10.",
            "- Reasoning is factual but templated in structure, often starting with years/title/company followed by the same JD-match phrase.",
            "",
            "## 6. Reasoning Quality",
            f"- Rows checked: {reasoning_report['rows_checked']}",
            f"- Rows with detected issues: {reasoning_report['problem_count']}",
            "- Main issue: repeated sentence pattern and truncated evidence excerpts, not hallucinated skills.",
            "",
            "## 7. Recommended Phase 5B Changes",
            "- Consider a small top-10 close-call adjustment that prefers career-backed retrieval/ranking/vector evidence over adjacent data-engineering or generic inference evidence when score gaps are tiny.",
            "- Consider adding an explicit evaluation-framework signal for NDCG/MRR/MAP/A/B testing, but only where career history states it.",
            "- Consider improving reasoning variation and adding concise weakness notes for borderline top-10 candidates.",
            "",
            "## 8. Final Decision Gate",
            decision,
        ]
    )


def _decision_gate(audits: list[dict[str, Any]], missed: list[dict[str, Any]], reasoning_report: dict[str, Any]) -> str:
    top10_weak = [
        item
        for item in audits[:10]
        if len(item["evidence_categories"]["ai_infrastructure"]) <= 1
        or any(flag in item["weakness_indicators"] for flag in {"framework_only", "research_only", "manager_only", "wrong_ai_domain"})
    ]
    if len(top10_weak) >= 6 or (len(top10_weak) >= 4 and len(missed) >= 12):
        return "C: Major ranking flaw discovered. Recommend deeper redesign."
    if top10_weak or missed or reasoning_report["problem_count"] >= 10:
        return "B: Small calibration issue found. Recommend Phase 5B minor adjustment."
    return "A: Top10 quality strong. No ranking change recommended."


def _reasoning_markdown(problems: list[dict[str, Any]], repeated_openers: list[dict[str, Any]], rows: list[dict[str, str]]) -> str:
    problem_lines = [
        f"- Rank {item['rank']} `{item['candidate_id']}`: {', '.join(item['problems'])}."
        for item in problems[:25]
    ] or ["- No reasoning problems detected by heuristic checks."]
    repeated_lines = [
        f"- `{item['phrase']}` repeated {item['count']} times."
        for item in repeated_openers[:10]
    ] or ["- No repeated opener appeared 3 or more times."]
    return "\n".join(
        [
            "# Reasoning Quality Report",
            "",
            "## Scope",
            f"- Rows checked: {len(rows)}",
            "- Checks: factual specificity, JD connection, repeated phrasing, generic language, missing years/title facts, and truncation.",
            "",
            "## Detected Problems",
            *problem_lines,
            "",
            "## Repeated Phrases",
            *repeated_lines,
            "",
            "## Audit Judgment",
            "- Reasoning generally cites candidate facts and JD connections.",
            "- The largest manual-review risk is repeated template structure and some truncated evidence snippets.",
            "- No hallucination is asserted by this automated audit; flagged items require manual review before any Phase 5B change.",
        ]
    )


def _reasoning_template(lowered: str) -> str:
    parts = []
    if " years as " in lowered:
        parts.append("starts_with_years_title_company")
    if "jd match is backed by career evidence" in lowered:
        parts.append("jd_match_career_evidence")
    if "jd skill overlap includes" in lowered:
        parts.append("jd_skill_overlap")
    if "redrob signals show" in lowered:
        parts.append("redrob_signal_sentence")
    return " + ".join(parts) if parts else lowered.split(".")[0][:80]


def _weakness_indicators(
    career_lower: str,
    combined_lower: str,
    categories: dict[str, list[str]],
    trap_flags: list[str],
) -> list[str]:
    weaknesses = list(trap_flags)
    career_ai_count = len(categories["ai_infrastructure"])
    production_count = len(categories["production_evidence"])
    if any(term in combined_lower for term in WEAKNESS_TERMS["keyword_heavy"]) and career_ai_count == 0:
        weaknesses.append("keyword_heavy")
    if any(term in combined_lower for term in WEAKNESS_TERMS["framework_only"]) and career_ai_count <= 1 and production_count <= 1:
        weaknesses.append("framework_only")
    if any(term in career_lower for term in WEAKNESS_TERMS["research_only"]) and production_count == 0:
        weaknesses.append("research_only")
    if any(term in career_lower for term in WEAKNESS_TERMS["manager_only"]) and career_ai_count <= 1:
        weaknesses.append("manager_only")
    if any((term in career_lower) or (term in combined_lower) for term in WEAKNESS_TERMS["wrong_ai_domain"]) and career_ai_count <= 1:
        weaknesses.append("wrong_ai_domain")
    if any(term in career_lower for term in WEAKNESS_TERMS["consulting_only"]) and career_ai_count <= 1:
        weaknesses.append("consulting_only")
    return _unique(weaknesses)


def _audit_summary(categories: dict[str, list[str]], weaknesses: list[str]) -> str:
    if categories["ai_infrastructure"] and categories["production_evidence"] and not weaknesses:
        return "Strong JD fit: career-backed AI infrastructure and production evidence."
    if categories["ai_infrastructure"] and categories["production_evidence"]:
        return "Strong evidence with weaknesses to manually review."
    if categories["production_evidence"]:
        return "Production evidence present, but AI retrieval/ranking specificity is weaker."
    if categories["ai_infrastructure"]:
        return "AI infrastructure terms present, but production ownership evidence is weaker."
    return "Weak top-50 fit by JD-specific AI infrastructure evidence."


def _close_pair_note(left: dict[str, Any], right: dict[str, Any]) -> str:
    left_ai = len(left["evidence_categories"]["ai_infrastructure"])
    right_ai = len(right["evidence_categories"]["ai_infrastructure"])
    left_prod = len(left["evidence_categories"]["production_evidence"])
    right_prod = len(right["evidence_categories"]["production_evidence"])
    if right_ai > left_ai and right_prod >= left_prod:
        return "Lower-ranked candidate appears stronger on AI infrastructure evidence; manual top-order review is warranted."
    if left_ai >= right_ai and left_prod >= right_prod:
        return "Higher-ranked candidate has comparable or stronger audited evidence."
    return "Evidence tradeoff is mixed; no automatic conclusion."


def _best_excerpt(text: str, wanted_terms: set[str]) -> str:
    sentences = [normalize_whitespace(part) for part in text.replace("\n", " ").split(".") if part.strip()]
    if not sentences:
        return ""
    if not wanted_terms:
        return sentences[0][:220]
    sentences.sort(key=lambda sentence: sum(1 for term in wanted_terms if term in sentence.lower()), reverse=True)
    return sentences[0][:220]


def _hits(lowered: str, terms: set[str]) -> list[str]:
    return sorted(term for term in terms if term in lowered)


def _read_submission(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows.sort(key=lambda row: int(row["rank"]))
    return rows


def _load_candidates_for_ids(candidates_path: str | Path, candidate_ids: list[str]) -> dict[str, dict[str, Any]]:
    wanted = set(candidate_ids)
    found: dict[str, dict[str, Any]] = {}
    for candidate in iter_dataset_records(candidates_path):
        candidate_id = candidate.get("candidate_id")
        if candidate_id in wanted:
            found[candidate_id] = candidate
            if len(found) == len(wanted):
                break
    missing = wanted - set(found)
    if missing:
        raise ValueError(f"Missing candidates from dataset: {sorted(missing)[:5]}")
    return found


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit current RedRob top candidates without changing ranking.")
    parser.add_argument("--candidates", default="data/candidates.jsonl", help="Path to candidates JSONL/JSONL.GZ/JSON.")
    parser.add_argument("--submission", default="submission.csv", help="Path to current competition submission CSV.")
    parser.add_argument("--output-dir", default="outputs", help="Directory for audit reports.")
    args = parser.parse_args()
    run_top_candidate_audit(args.candidates, args.submission, args.output_dir)
    print(f"Wrote top candidate audit reports to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
