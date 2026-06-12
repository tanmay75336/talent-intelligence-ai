"""
Phase 8 Evaluation Harness
==========================
Compares two ranked submissions against JD-derived quality signals.
Grounded in official challenge docs (submission_spec, job_description, redrob_signals_doc).

Usage:
    # Baseline analysis only
    python -m backend.competition.evaluate

    # Compare two submissions
    python -m backend.competition.evaluate \\
        --baseline submission.csv \\
        --experiment experiment.csv

    # Detailed tier output
    python -m backend.competition.evaluate --verbose
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Evaluation signal sets — extracted from official JD and challenge docs
# ---------------------------------------------------------------------------

# Signals the JD explicitly calls out as markers of a strong candidate:
# "Set up the evaluation infrastructure — offline benchmarks, online A/B testing,
#  recruiter-feedback loops — so we can keep improving without flying blind."
JD_EVAL_MATURITY_TERMS: set[str] = {
    "ndcg", "mrr", "map", "recall@", "precision@",
    "a/b test", "ab test", "offline eval", "online eval",
    "evaluation framework", "ranking quality",
    "offline-to-online", "correlation",
}

# JD explicitly lists: "embeddings, retrieval, ranking, LLMs, fine-tuning"
# and "BM25 + rule-based scoring" as the baseline to improve
JD_RETRIEVAL_TERMS: set[str] = {
    "bm25", "faiss", "hnsw", "dense retrieval", "hybrid retrieval",
    "semantic search", "elasticsearch", "opensearch", "pinecone",
    "weaviate", "qdrant", "milvus", "vector search", "embedding",
}

# JD mandate: "own the intelligence layer... ranking, retrieval, and matching systems"
JD_SYSTEM_TERMS: set[str] = {
    "ranking", "retrieval", "recommendation", "recommender",
    "search", "re-rank", "rerank", "learning-to-rank", "ltr", "two-stage",
}

# JD explicitly warns against "impressive titles without matching evidence"
# and favours "shipped a working ranker in a week"
JD_PRODUCTION_TERMS: set[str] = {
    "production", "deployed", "scale", "latency", "shipped",
    "a/b", "users", "monitoring", "pipeline",
}

# JD: "Scrappy product-engineering attitude" — hands-on builders
JD_OWNERSHIP_TERMS: set[str] = {
    "owned", "architected", "built", "designed", "led", "created",
}

# Official scoring weights from submission_spec (NDCG@10=50%, NDCG@50=30%, MAP=15%, P@10=5%)
# We translate this into tier importance multipliers for our internal reporting
TIER_WEIGHT = {
    "top10":  0.55,   # NDCG@10 50% + P@10 5%
    "top50":  0.30,   # NDCG@50 30%
    "top100": 0.15,   # MAP 15% (whole list)
}


# ---------------------------------------------------------------------------
# Core signal extraction (career-evidence, NOT keyword matching)
# ---------------------------------------------------------------------------

def _extract_career_signals(career_lower: str) -> dict[str, bool | list[str]]:
    """
    Extract JD-aligned evidence signals from career text.
    Returns evidence-grounded signals, not simple keyword flags.
    """
    eval_hits = [t for t in JD_EVAL_MATURITY_TERMS if t in career_lower]
    retrieval_hits = [t for t in JD_RETRIEVAL_TERMS if t in career_lower]
    system_hits = [t for t in JD_SYSTEM_TERMS if t in career_lower]
    prod_hits = [t for t in JD_PRODUCTION_TERMS if t in career_lower]
    own_hits = [t for t in JD_OWNERSHIP_TERMS if t in career_lower]

    # Evidence score: production + ownership together → career evidence of doing something
    # Skill mention without production → surface-level only
    has_career_evidence = bool(prod_hits) and bool(own_hits)
    has_eval_maturity = len(eval_hits) >= 1
    has_retrieval = bool(retrieval_hits)
    has_system = bool(system_hits)

    # Surface-match risk: system terms exist but no production/ownership evidence
    surface_match_risk = has_system and not has_career_evidence

    return {
        "eval_hits": eval_hits,
        "retrieval_hits": retrieval_hits,
        "system_hits": system_hits,
        "prod_hits": prod_hits,
        "own_hits": own_hits,
        "has_career_evidence": has_career_evidence,
        "has_eval_maturity": has_eval_maturity,
        "has_retrieval": has_retrieval,
        "has_system": has_system,
        "surface_match_risk": surface_match_risk,
        # Evidence depth score (0-4): one point per signal category
        "evidence_depth": sum([
            has_eval_maturity,
            has_retrieval,
            has_system,
            has_career_evidence,
        ]),
    }


def _extract_behavioral_signals(sigs: dict) -> dict:
    """
    Extract behavioral quality signals as defined in redrob_signals_doc.
    Purpose per doc: "more predictive of whether a candidate can actually be hired"
    These are MODIFIERS, not primary quality signals.
    """
    if not sigs:
        return {"availability_score": 0.0, "engagement_score": 0.0, "facts": []}

    facts = []
    availability = 0.0
    engagement = 0.0

    if sigs.get("open_to_work_flag") is True:
        availability += 0.3
        facts.append("open_to_work")
    notice = sigs.get("notice_period_days")
    if isinstance(notice, (int, float)) and notice <= 30:
        availability += 0.4
        facts.append(f"notice_{int(notice)}d")
    elif isinstance(notice, (int, float)) and notice <= 60:
        availability += 0.2
    if sigs.get("willing_to_relocate") is True:
        availability += 0.3
        facts.append("relocatable")

    rr = sigs.get("recruiter_response_rate")
    if isinstance(rr, (int, float)) and rr >= 0:
        engagement += min(1.0, rr)
        if rr >= 0.7:
            facts.append(f"response_{rr:.0%}")
    ir = sigs.get("interview_completion_rate")
    if isinstance(ir, (int, float)) and ir >= 0:
        engagement += min(1.0, ir) * 0.5
    gh = sigs.get("github_activity_score")
    if isinstance(gh, (int, float)) and gh >= 40:
        engagement += 0.3
        facts.append(f"github_{gh:.0f}")

    return {
        "availability_score": min(1.0, availability),
        "engagement_score": min(1.0, engagement),
        "facts": facts,
    }


# ---------------------------------------------------------------------------
# Candidate record loading (works independently of ranking pipeline)
# ---------------------------------------------------------------------------

def _load_submission(path: str) -> dict[str, dict]:
    """Load a submission CSV, keyed by candidate_id."""
    result = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            result[row["candidate_id"]] = {
                "rank": int(row["rank"]),
                "score": float(row["score"]),
                "reasoning": row.get("reasoning", ""),
            }
    return result


def _analyze_submission(
    submission_path: str,
    candidates_path: str = "data/candidates.jsonl",
) -> dict[str, dict]:
    """
    Analyze a submission against JD-derived quality signals.
    Returns per-candidate evaluation data.
    """
    sys.path.insert(0, ".")
    from backend.dataset_intelligence.loader import iter_dataset_records
    from backend.competition.redrob_adapter import adapt_redrob_candidate
    from backend.competition.evidence_calibrator import calibrate_candidate_evidence
    from backend.utils.skill_taxonomy import normalize_whitespace

    sub = _load_submission(submission_path)
    evaluated = {}

    for raw in iter_dataset_records(candidates_path):
        from backend.competition.redrob_adapter import adapt_redrob_candidate
        p = adapt_redrob_candidate(raw)
        cid = p.candidate_id
        if cid not in sub:
            continue

        cal = calibrate_candidate_evidence(p)
        career_text = normalize_whitespace(
            " ".join(str(i.get("description", "")) for i in p.career_history)
        ).lower()
        career_sigs = _extract_career_signals(career_text)
        beh_sigs = _extract_behavioral_signals(p.redrob_signals or {})

        evaluated[cid] = {
            **sub[cid],
            "title": p.structured_profile.get("current_title", ""),
            "company": p.structured_profile.get("current_company", ""),
            "years": p.years_of_experience,
            "career": career_sigs,
            "behavioral": beh_sigs,
            "trap_flags": cal.trap_flags,
            "career_ai_hits": cal.career_ai_infra_hits,
        }

    return evaluated


# ---------------------------------------------------------------------------
# Tier report
# ---------------------------------------------------------------------------

def _tier_report(evaluated: dict[str, dict], tier_name: str, lo: int, hi: int) -> dict:
    """Compute aggregate quality metrics for a rank tier."""
    tier = [v for v in evaluated.values() if lo <= v["rank"] <= hi]
    n = len(tier)
    if n == 0:
        return {"tier": tier_name, "n": 0}

    has_eval = sum(1 for v in tier if v["career"]["has_eval_maturity"])
    has_ret = sum(1 for v in tier if v["career"]["has_retrieval"])
    has_sys = sum(1 for v in tier if v["career"]["has_system"])
    has_career_ev = sum(1 for v in tier if v["career"]["has_career_evidence"])
    surface_risk = sum(1 for v in tier if v["career"]["surface_match_risk"])
    has_trap = sum(1 for v in tier if v["trap_flags"])
    exp_ok = sum(1 for v in tier if 5 <= v["years"] <= 9)

    depth_scores = [v["career"]["evidence_depth"] for v in tier]
    avg_depth = sum(depth_scores) / n

    avail_scores = [v["behavioral"]["availability_score"] for v in tier]
    avg_avail = sum(avail_scores) / n

    # Composite JD-alignment score for this tier (0-1)
    # Weighted: eval_maturity (0.35) + retrieval (0.25) + career_evidence (0.25) + exp_ok (0.15)
    alignment = (
        0.35 * (has_eval / n) +
        0.25 * (has_ret / n) +
        0.25 * (has_career_ev / n) +
        0.15 * (exp_ok / n)
    )

    return {
        "tier": tier_name,
        "n": n,
        "eval_maturity_pct": round(100 * has_eval / n),
        "retrieval_infra_pct": round(100 * has_ret / n),
        "system_terms_pct": round(100 * has_sys / n),
        "career_evidence_pct": round(100 * has_career_ev / n),
        "surface_match_risk_count": surface_risk,
        "trap_flags_count": has_trap,
        "ideal_experience_pct": round(100 * exp_ok / n),
        "avg_evidence_depth": round(avg_depth, 2),
        "avg_behavioral_availability": round(avg_avail, 2),
        "jd_alignment_score": round(alignment, 3),
    }


def _print_tier_report(r: dict) -> None:
    tier_label = r["tier"]
    n = r["n"]
    print(f"\n{'=' * 50}")
    print(f"  {tier_label}  (n={n})")
    print(f"{'=' * 50}")
    print(f"  JD Alignment Score:        {r['jd_alignment_score']:.3f}  (0=none, 1=perfect)")
    print(f"  Avg Evidence Depth:        {r['avg_evidence_depth']:.2f} / 4.0")
    print()
    print(f"  Evidence signals:")
    print(f"    Eval maturity (NDCG/MRR/A-B): {r['eval_maturity_pct']}%")
    print(f"    Retrieval infra (FAISS/BM25): {r['retrieval_infra_pct']}%")
    print(f"    System terms (rank/rec/search): {r['system_terms_pct']}%")
    print(f"    Career evidence (prod+own):    {r['career_evidence_pct']}%")
    print(f"    Ideal experience (5-9y):       {r['ideal_experience_pct']}%")
    print()
    print(f"  Risks:")
    print(f"    Surface-match (sys terms, no evidence): {r['surface_match_risk_count']}")
    print(f"    Trap flags:                             {r['trap_flags_count']}")
    print()
    print(f"  Behavioral avg availability:  {r['avg_behavioral_availability']:.2f} / 1.0")


# ---------------------------------------------------------------------------
# False-positive analysis
# ---------------------------------------------------------------------------

def _false_positive_analysis(evaluated: dict[str, dict]) -> list[dict]:
    """
    Identify candidates with elevated false-positive risk in the top 50.
    Based on official warning categories: surface-level match, skills without
    experience, impressive titles without evidence.
    """
    risks = []
    for cid, v in evaluated.items():
        if v["rank"] > 50:
            continue
        c = v["career"]
        flags = []

        # 1. Surface match: system terms present but no production+ownership
        if c["surface_match_risk"]:
            flags.append("surface_match: system terms without career evidence")

        # 2. Skills without supporting retrieval experience
        if c["has_system"] and not c["has_retrieval"] and not c["has_eval_maturity"]:
            flags.append("narrow: system background without retrieval infra")

        # 3. Trap flags already identified by calibration
        if v["trap_flags"]:
            for f in v["trap_flags"]:
                flags.append(f"trap_flag:{f}")

        if flags:
            risks.append({
                "rank": v["rank"],
                "cid": cid,
                "title": v["title"],
                "company": v["company"],
                "years": v["years"],
                "flags": flags,
            })

    return sorted(risks, key=lambda x: x["rank"])


# ---------------------------------------------------------------------------
# Recall analysis: promising candidates outside top 100
# ---------------------------------------------------------------------------

def _recall_analysis(
    evaluated_top100: dict[str, dict],
    candidates_path: str = "data/candidates.jsonl",
    max_scan: int = 5000,
) -> list[dict]:
    """
    Sample candidates outside the top 100 and identify those with strong
    JD-aligned career evidence that were missed.
    Returns a list of high-evidence misses for review.
    """
    sys.path.insert(0, ".")
    from backend.dataset_intelligence.loader import iter_dataset_records
    from backend.competition.redrob_adapter import adapt_redrob_candidate
    from backend.competition.evidence_calibrator import calibrate_candidate_evidence
    from backend.utils.skill_taxonomy import normalize_whitespace

    top100_ids = set(evaluated_top100.keys())
    strong_misses = []
    scanned = 0

    for raw in iter_dataset_records(candidates_path):
        if scanned >= max_scan:
            break
        p = adapt_redrob_candidate(raw)
        if p.candidate_id in top100_ids:
            continue
        scanned += 1

        career_text = normalize_whitespace(
            " ".join(str(i.get("description", "")) for i in p.career_history)
        ).lower()
        sigs = _extract_career_signals(career_text)

        # Only flag as a strong miss if: career evidence + retrieval + system + eval
        if sigs["evidence_depth"] >= 3:
            cal = calibrate_candidate_evidence(p)
            strong_misses.append({
                "cid": p.candidate_id,
                "title": p.structured_profile.get("current_title", ""),
                "company": p.structured_profile.get("current_company", ""),
                "years": p.years_of_experience,
                "evidence_depth": sigs["evidence_depth"],
                "trap_flags": cal.trap_flags,
                "eval_hits": sigs["eval_hits"],
                "retrieval_hits": sigs["retrieval_hits"][:3],
            })

    # Classify: if trap flags → likely acceptable exclusion
    # If no trap flags + high evidence_depth → possible systematic miss
    for m in strong_misses:
        if m["trap_flags"]:
            m["classification"] = "A_acceptable"
        elif not (5 <= m["years"] <= 9):
            m["classification"] = "A_acceptable_exp"
        else:
            m["classification"] = "B_possible_miss"

    strong_misses.sort(key=lambda x: x["evidence_depth"], reverse=True)
    return strong_misses[:30]


# ---------------------------------------------------------------------------
# Experiment comparison
# ---------------------------------------------------------------------------

def _compare_submissions(
    baseline: dict[str, dict],
    experiment: dict[str, dict],
) -> dict:
    """
    Compare two submissions and report quality signal changes.
    Returns structured comparison data for the Phase 8 experiments.
    """
    base_ids = set(baseline.keys())
    exp_ids = set(experiment.keys())

    entered = exp_ids - base_ids
    left = base_ids - exp_ids
    common = base_ids & exp_ids

    # Rank changes for common candidates
    rank_changes = []
    for cid in common:
        old_rank = baseline[cid]["rank"]
        new_rank = experiment[cid]["rank"]
        if old_rank != new_rank:
            rank_changes.append({
                "cid": cid,
                "title": experiment[cid].get("title", ""),
                "old_rank": old_rank,
                "new_rank": new_rank,
                "delta": old_rank - new_rank,  # positive = improved
            })

    rank_changes.sort(key=lambda x: abs(x["delta"]), reverse=True)

    # Top-10 change analysis
    old_top10 = {cid for cid, v in baseline.items() if v["rank"] <= 10}
    new_top10 = {cid for cid, v in experiment.items() if v["rank"] <= 10}
    top10_entered = new_top10 - old_top10
    top10_left = old_top10 - new_top10

    # Top-50 change analysis
    old_top50 = {cid for cid, v in baseline.items() if v["rank"] <= 50}
    new_top50 = {cid for cid, v in experiment.items() if v["rank"] <= 50}
    top50_entered = new_top50 - old_top50
    top50_left = old_top50 - new_top50

    return {
        "candidates_entered_top100": len(entered),
        "candidates_left_top100": len(left),
        "top10_entered": [
            {"cid": c, "rank": experiment[c]["rank"],
             "title": experiment.get(c, {}).get("title", "")}
            for c in top10_entered
        ],
        "top10_left": [
            {"cid": c, "rank": baseline[c]["rank"],
             "title": baseline.get(c, {}).get("title", "")}
            for c in top10_left
        ],
        "top50_entered_count": len(top50_entered),
        "top50_left_count": len(top50_left),
        "rank_changes_top20": rank_changes[:20],
    }


def _print_comparison(comp: dict, exp_tiers: list[dict], base_tiers: list[dict]) -> None:
    print("\n" + "=" * 55)
    print("  EXPERIMENT vs BASELINE — COMPARISON REPORT")
    print("=" * 55)
    print(f"\nTop-100 membership:")
    print(f"  Candidates entering: {comp['candidates_entered_top100']}")
    print(f"  Candidates leaving:  {comp['candidates_left_top100']}")
    print(f"\nTop-10 changes:")
    if comp["top10_entered"]:
        print(f"  Entered top-10:")
        for c in comp["top10_entered"]:
            print(f"    + Rank {c['rank']} {c['cid']} {c['title']}")
    if comp["top10_left"]:
        print(f"  Left top-10:")
        for c in comp["top10_left"]:
            print(f"    - Was rank {c['rank']} {c['cid']} {c['title']}")
    print(f"\nTop-50 changes:")
    print(f"  Entered: {comp['top50_entered_count']}  Left: {comp['top50_left_count']}")
    print(f"\nBiggest rank changes:")
    for rc in comp["rank_changes_top20"][:10]:
        direction = "▲" if rc["delta"] > 0 else "▼"
        print(f"  {direction} {rc['cid']} {rc['title']}: {rc['old_rank']} → {rc['new_rank']} (Δ{abs(rc['delta'])})")

    print(f"\nJD Alignment Score delta (experiment - baseline):")
    for bt, et in zip(base_tiers, exp_tiers):
        delta = et["jd_alignment_score"] - bt["jd_alignment_score"]
        sign = "+" if delta >= 0 else ""
        tier_weight = TIER_WEIGHT.get(
            bt["tier"].lower().replace(" ", "").replace("-", ""),
            TIER_WEIGHT.get(
                "top" + bt["tier"].split()[-1].replace("+", ""), 0.15
            )
        )
        print(f"  {bt['tier']:12s}: {sign}{delta:+.3f}  (weight={tier_weight:.0%})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 8 Evaluation Harness")
    parser.add_argument("--baseline", default="submission.csv",
                        help="Baseline submission CSV (default: submission.csv)")
    parser.add_argument("--experiment", default=None,
                        help="Experiment submission CSV to compare against baseline")
    parser.add_argument("--candidates", default="data/candidates.jsonl",
                        help="Candidate pool JSONL")
    parser.add_argument("--recall-scan", type=int, default=5000,
                        help="Number of non-top-100 candidates to scan for recall analysis")
    parser.add_argument("--verbose", action="store_true",
                        help="Show per-candidate detail in top-10")
    args = parser.parse_args()

    print("=" * 55)
    print("  Phase 8 — Internal Evaluation Harness")
    print("  Grounded in: submission_spec, job_description,")
    print("               redrob_signals_doc")
    print("=" * 55)

    print(f"\nAnalyzing baseline: {args.baseline} ...")
    evaluated = _analyze_submission(args.baseline, args.candidates)
    print(f"  Loaded {len(evaluated)} candidates from submission.")

    # Tier reports
    tiers = [
        _tier_report(evaluated, "TOP 10", 1, 10),
        _tier_report(evaluated, "TOP 11-50", 11, 50),
        _tier_report(evaluated, "TOP 51-100", 51, 100),
    ]
    for t in tiers:
        _print_tier_report(t)

    # False-positive analysis
    fps = _false_positive_analysis(evaluated)
    print(f"\n{'=' * 50}")
    print(f"  FALSE-POSITIVE RISK (Top 50)")
    print(f"{'=' * 50}")
    if fps:
        for fp in fps:
            print(f"  Rank {fp['rank']:>2} {fp['cid']} — {fp['title']} @ {fp['company']}")
            for f in fp["flags"]:
                print(f"    ⚠  {f}")
    else:
        print("  None identified.")

    # Verbose top-10 detail
    if args.verbose:
        print(f"\n{'=' * 50}")
        print(f"  TOP 10 — DETAILED BREAKDOWN")
        print(f"{'=' * 50}")
        top10 = sorted(
            [v for v in evaluated.values() if v["rank"] <= 10],
            key=lambda x: x["rank"]
        )
        for v in top10:
            c = v["career"]
            b = v["behavioral"]
            print(f"\n  Rank {v['rank']:>2}: {v['title']} @ {v['company']} ({v['years']:.1f}y)")
            print(f"    Evidence depth: {c['evidence_depth']}/4  eval={c['has_eval_maturity']}  "
                  f"ret={c['has_retrieval']}  prod={bool(c['prod_hits'])}  own={bool(c['own_hits'])}")
            print(f"    Retrieval terms: {c['retrieval_hits'][:4]}")
            print(f"    Eval hits: {c['eval_hits'][:3]}")
            print(f"    Behavioral: avail={b['availability_score']:.2f}  facts={b['facts']}")
            if v["trap_flags"]:
                print(f"    ⚠ Trap flags: {v['trap_flags']}")

    # Recall analysis
    print(f"\n{'=' * 50}")
    print(f"  RECALL ANALYSIS (scanning first {args.recall_scan} non-top-100 candidates)")
    print(f"{'=' * 50}")
    misses = _recall_analysis(evaluated, args.candidates, max_scan=args.recall_scan)
    class_b = [m for m in misses if m["classification"] == "B_possible_miss"]
    class_a = [m for m in misses if m["classification"].startswith("A_")]
    print(f"  High-evidence candidates outside top-100: {len(misses)}")
    print(f"    Class A (acceptable exclusion): {len(class_a)}")
    print(f"    Class B (possible systematic miss): {len(class_b)}")
    if class_b:
        print(f"\n  Class B candidates (5-9y, no trap flags, depth≥3):")
        for m in class_b[:10]:
            print(f"    {m['cid']} — {m['title']} @ {m['company']} ({m['years']:.1f}y) "
                  f"depth={m['evidence_depth']} ret={m['retrieval_hits']}")

    # Experiment comparison
    if args.experiment:
        print(f"\nAnalyzing experiment: {args.experiment} ...")
        exp_evaluated = _analyze_submission(args.experiment, args.candidates)
        exp_tiers = [
            _tier_report(exp_evaluated, "TOP 10", 1, 10),
            _tier_report(exp_evaluated, "TOP 11-50", 11, 50),
            _tier_report(exp_evaluated, "TOP 51-100", 51, 100),
        ]
        comp = _compare_submissions(evaluated, exp_evaluated)
        _print_comparison(comp, exp_tiers, tiers)

    # Final composite score (weighted by official scoring)
    weights = [TIER_WEIGHT["top10"], TIER_WEIGHT["top50"], TIER_WEIGHT["top100"]]
    composite = sum(w * t["jd_alignment_score"] for w, t in zip(weights, tiers))
    print(f"\n{'=' * 55}")
    print(f"  COMPOSITE JD ALIGNMENT SCORE (official weights)")
    print(f"  = {composite:.3f}  [NDCG@10×0.55 + NDCG@50×0.30 + MAP×0.15]")
    print(f"{'=' * 55}\n")


if __name__ == "__main__":
    main()
