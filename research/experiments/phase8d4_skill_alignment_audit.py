"""
Phase 8D.4 — Skill Signal Evidence Alignment Audit

For every candidate in the top 100, measure whether the confidence added
by skill-derived signals (skill_overlap, group_overlap) is supported by
actual candidate evidence in the complete profile.

Classification per candidate-skill pair:

  GROUP A — SUPPORTED
    The claimed skill maps to a JD-relevant capability, AND the career history
    or project evidence demonstrates that capability was actually exercised.
    Vocabulary-flexible: equivalent terms and tool families count.

  GROUP B — UNCERTAIN
    The claimed skill maps to a JD-relevant capability, BUT available evidence
    is insufficient to confirm OR deny. Missing detail is not treated as false.

  GROUP C — UNSUPPORTED
    The claimed skill maps to a JD-relevant capability, BUT complete available
    evidence clearly does not support the implied capability.
    Only flagged when there is a clear, unambiguous mismatch.

Official Requirements being tested (from job_description.docx):
  R1: Production embeddings-based retrieval systems
  R2: Vector DB / hybrid search infrastructure
  R4: Evaluation framework design for ranking

JD core_skills (extracted by jd_analyzer):
  High-specificity (strong evidence when present in career):
    Elasticsearch, FAISS, Milvus, OpenSearch, Pinecone, Qdrant, Sentence Transformers, Weaviate
  Medium-specificity (useful but generic):
    AI, Machine Learning, LLM, OpenAI, Recommendation Systems, Search Ranking, GitHub
  Low-specificity (nearly universal for this role):
    Python

The audit measures only the HIGH-SPECIFICITY skills.
These are the skills where listing the name implies a specific capability (R1/R2).
Medium and low-specificity skills are not audited (not diagnostic enough).
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, ".")

from backend.dataset_intelligence.loader import iter_dataset_records
from backend.competition.redrob_adapter import adapt_redrob_candidate
from backend.competition.evidence_calibrator import calibrate_candidate_evidence, AI_INFRA_TERMS
from backend.competition.evaluate import _extract_career_signals
from backend.utils.skill_taxonomy import normalize_whitespace, get_active_groups
from backend.parsers.jd_analyzer import analyze_job_description
from backend.competition.rank import read_job_text, _important_terms, _ratio, _experience_fit
from backend.intelligence.candidate_engine import build_competition_core_signals
from backend.competition.phase8c4_experiment import _competition_score_c4, _career_evidence_score

# ---------------------------------------------------------------------------
# HIGH-SPECIFICITY JD SKILLS — the ones that imply specific retrieval/vector
# capabilities per the JD.  These are the only ones worth auditing.
# (Low-spec skills like Python, AI, Machine Learning are not diagnostic.)
# ---------------------------------------------------------------------------

# Vector DB / embedding infrastructure skills (map to R1+R2 from JD)
HIGH_SPEC_SKILLS_R1R2 = {
    "Elasticsearch", "FAISS", "Milvus", "OpenSearch", "Pinecone",
    "Qdrant", "Sentence Transformers", "Weaviate",
}

# Retrieval/search system skills (map to JD mandate: "ranking, retrieval, matching")
HIGH_SPEC_SKILLS_SYSTEM = {
    "Recommendation Systems", "Search Ranking",
}

ALL_HIGH_SPEC = HIGH_SPEC_SKILLS_R1R2 | HIGH_SPEC_SKILLS_SYSTEM

# ---------------------------------------------------------------------------
# CAREER EVIDENCE TERMS — what we look for in career text to corroborate
# each high-specificity skill (flexible vocabulary — NOT the exact skill name)
# ---------------------------------------------------------------------------

# Evidence that the candidate actually worked on retrieval or vector search
RETRIEVAL_CAREER_EVIDENCE = {
    # direct retrieval work
    "retrieval", "search", "semantic search", "vector search", "nearest neighbor",
    "ann", "hnsw", "approximate nearest",
    # embedding systems
    "embedding", "embeddings", "sentence-transformer", "dense retrieval",
    "dense vector", "sparse", "hybrid",
    # vector infra tools (any, not just the one claimed in skills)
    "faiss", "pinecone", "weaviate", "qdrant", "milvus", "opensearch",
    "elasticsearch", "pgvector", "vector database",
    # retrieval system patterns
    "bm25", "inverted index", "query expansion", "re-rank", "rerank",
}

# Evidence of production system ownership (R1 requirement)
PRODUCTION_OWNERSHIP_EVIDENCE = {
    "deployed", "production", "users", "scale", "latency", "monitoring",
    "serving", "shipped", "launched",
}

# Evidence of recommendation / ranking system building (for Search Ranking / Rec Systems skills)
RANKING_SYSTEM_EVIDENCE = {
    "ranking", "recommendation", "recommender", "learning-to-rank", "ltr",
    "collaborative filtering", "matrix factorization", "re-ranking",
    "search product", "discovery feed", "ranking layer", "ranking pipeline",
}

# STRONG disconfirming evidence — career history shows a clearly different domain
DISCONFIRMING_DOMAINS = {
    # CV / image work (per JD explicit not-wanted: "computer vision... without NLP/IR")
    "computer vision", "image classification", "image moderation", "object detection",
    "resnet", "yolo", "segmentation", "face recognition",
    # Speech / audio
    "speech recognition", "text-to-speech", "tts", "asr", "audio",
    # Pure data/analytics (no retrieval)
    "supply chain", "demand forecasting", "churn prediction", "fraud detection",
    # Explicit self-disclaimers (Phase 8C.4 already handles this)
    "production deployment was handled by", "pure ml side of the work",
    "deployment was handled by the platform",
}


def _classify_skill_alignment(
    skill: str,
    career_text: str,
    profile,
    cal,
) -> tuple[str, str]:
    """
    Returns (group, reason) for a single high-specificity matched skill.

    group: 'A' (supported), 'B' (uncertain), 'C' (unsupported)
    reason: brief explanation
    """
    ct = career_text  # lowercase

    # Check for disconfirming domain first — career history shows a clearly
    # different domain, making the skill claim implausible
    has_disconfirm = any(t in ct for t in DISCONFIRMING_DOMAINS)

    # For R1+R2 skills (vector DB / embedding infra)
    if skill in HIGH_SPEC_SKILLS_R1R2:
        has_retrieval_work = any(t in ct for t in RETRIEVAL_CAREER_EVIDENCE)
        has_prod_work = any(t in ct for t in PRODUCTION_OWNERSHIP_EVIDENCE)

        if has_retrieval_work and has_prod_work and not has_disconfirm:
            return "A", f"career shows retrieval/vector work in production context"
        elif has_retrieval_work and not has_disconfirm:
            return "B", f"retrieval work found in career but production context unclear"
        elif has_disconfirm and not has_retrieval_work:
            return "C", f"career shows unrelated domain ({[t for t in DISCONFIRMING_DOMAINS if t in ct][:2]}); no retrieval evidence"
        elif not has_retrieval_work:
            return "C", f"no retrieval/vector work found in career history"
        else:
            return "B", "mixed signals — disconfirming domain but some retrieval evidence"

    # For ranking/recommendation system skills
    if skill in HIGH_SPEC_SKILLS_SYSTEM:
        has_ranking_work = any(t in ct for t in RANKING_SYSTEM_EVIDENCE)
        has_prod_work = any(t in ct for t in PRODUCTION_OWNERSHIP_EVIDENCE)

        if has_ranking_work and has_prod_work:
            return "A", f"career demonstrates ranking/recommendation system work in production"
        elif has_ranking_work:
            return "B", f"ranking/recommendation work found but production context unclear"
        elif has_disconfirm and not has_ranking_work:
            return "C", f"career shows unrelated domain, no ranking/recommendation evidence"
        else:
            return "B", "ranking system work not clearly demonstrated"

    # Fallback (should not happen if called only for high-spec skills)
    return "B", "skill not in high-specificity set"


def compute_skill_contribution(
    profile, job_core_skills: set, job_groups: set
) -> dict:
    """Compute the exact skill-derived score contribution for this candidate."""
    candidate_skills = set(profile.skills)
    matched_skills = candidate_skills & job_core_skills
    skill_overlap = (
        _ratio(len(matched_skills), len(job_core_skills)) if job_core_skills else 0.0
    )
    candidate_groups = set(get_active_groups(profile.skills))
    matched_groups = candidate_groups & job_groups
    group_overlap = _ratio(len(matched_groups), len(job_groups))

    skill_contribution = skill_overlap * 0.26
    group_contribution = group_overlap * 0.16
    total_skill_signal = skill_contribution + group_contribution

    return {
        "matched_skills": sorted(matched_skills),
        "high_spec_matched": sorted(matched_skills & ALL_HIGH_SPEC),
        "skill_overlap": round(skill_overlap, 3),
        "group_overlap": round(group_overlap, 3),
        "matched_groups": sorted(matched_groups),
        "skill_contribution_to_base": round(skill_contribution, 4),
        "group_contribution_to_base": round(group_contribution, 4),
        "total_skill_signal": round(total_skill_signal, 4),
    }


def run_audit(
    candidates_path: str = "data/candidates.jsonl",
    submission_path: str = "submission_phase8c4.csv",
    output_path: str = "outputs/phase8d4_audit_data.csv",
) -> None:
    """Run the skill alignment audit on all top-100 candidates."""

    # Load job description signals
    job_text = read_job_text("data/job_description.docx")
    job_analysis = analyze_job_description(job_text)
    job_terms = _important_terms(job_text)
    job_core_skills = set(job_analysis.core_skills)
    job_groups = set(get_active_groups(job_analysis.all_skills))

    # Load submission
    with open(submission_path) as f:
        submission = {
            r["candidate_id"]: {"rank": int(r["rank"]), "score": float(r["score"])}
            for r in csv.DictReader(f)
        }
    top100_ids = set(submission.keys())

    results = []
    group_counts = {"A": 0, "B": 0, "C": 0}
    unsupported_by_tier = {"top10": [], "top50": [], "top100": []}

    print("Running Phase 8D.4 skill alignment audit on top-100 candidates...")

    for raw in iter_dataset_records(candidates_path):
        cid = raw.get("candidate_id", "")
        if cid not in top100_ids:
            continue

        p = adapt_redrob_candidate(raw)
        cal = calibrate_candidate_evidence(p)
        career_text = normalize_whitespace(
            " ".join(str(h.get("description", "")) for h in p.career_history)
        ).lower()
        cs = _extract_career_signals(career_text)
        core_sigs = build_competition_core_signals(p)

        rank = submission[cid]["rank"]
        base_score = _competition_score_c4(p, core_sigs, job_analysis, job_terms)
        total_score = base_score + cal.adjustment
        skill_data = compute_skill_contribution(p, job_core_skills, job_groups)

        # Classify each high-specificity matched skill
        per_skill_groups = {}
        for skill in skill_data["high_spec_matched"]:
            grp, reason = _classify_skill_alignment(skill, career_text, p, cal)
            per_skill_groups[skill] = (grp, reason)

        # Overall candidate skill alignment
        if not skill_data["high_spec_matched"]:
            # No high-specificity skills matched — skill signal is based on
            # medium/low spec skills only. Cannot audit directly.
            overall_group = "B"
            overall_reason = "no high-specificity skills matched JD; signal from generic skills only"
        elif all(g == "A" for g, _ in per_skill_groups.values()):
            overall_group = "A"
            overall_reason = "all high-spec matched skills corroborated by career evidence"
        elif any(g == "C" for g, _ in per_skill_groups.values()):
            # At least one unsupported skill — is it the main driver?
            unsupported_skills = [s for s, (g, _) in per_skill_groups.items() if g == "C"]
            overall_group = "C"
            overall_reason = f"unsupported skill(s): {unsupported_skills}"
        else:
            overall_group = "B"
            overall_reason = "some evidence present but not all skills fully corroborated"

        group_counts[overall_group] += 1

        # Determine the counterfactual: what would base_score be without skill signals?
        # skill_contribution + group_contribution = total_skill_signal
        counterfactual_base = base_score - skill_data["total_skill_signal"]
        # Skill signal impact on final rank (approximate)
        skill_signal_impact = skill_data["total_skill_signal"]

        rec = {
            "candidate_id": cid,
            "rank": rank,
            "base_score": round(base_score, 4),
            "calibration_adj": round(cal.adjustment, 4),
            "total_score": round(total_score, 4),
            "skill_alignment_group": overall_group,
            "skill_alignment_reason": overall_reason,
            "high_spec_matched": "|".join(skill_data["high_spec_matched"]),
            "per_skill_groups": "; ".join(
                f"{s}:{g}" for s, (g, _) in per_skill_groups.items()
            ),
            "skill_overlap": skill_data["skill_overlap"],
            "group_overlap": skill_data["group_overlap"],
            "skill_contribution": skill_data["skill_contribution_to_base"],
            "group_contribution": skill_data["group_contribution_to_base"],
            "total_skill_signal": skill_data["total_skill_signal"],
            "counterfactual_base_no_skill": round(counterfactual_base, 4),
            "career_evidence": _career_evidence_score(p),
            "depth": cs["evidence_depth"],
            "has_retrieval": cs["has_retrieval"],
            "has_eval": cs["has_eval_maturity"],
            "trap_flags": "|".join(cal.trap_flags),
            "title": p.structured_profile.get("current_title", ""),
            "company": p.structured_profile.get("current_company", ""),
            "yoe": p.years_of_experience,
        }
        results.append(rec)

        if overall_group == "C":
            tier = "top10" if rank <= 10 else ("top50" if rank <= 50 else "top100")
            unsupported_by_tier[tier].append(rec)

        top100_ids.discard(cid)
        if not top100_ids:
            break

    # Sort by rank
    results.sort(key=lambda x: x["rank"])

    print(f"\nAudit complete. {len(results)} candidates analyzed.")
    print(f"GROUP A (supported):   {group_counts['A']}")
    print(f"GROUP B (uncertain):   {group_counts['B']}")
    print(f"GROUP C (unsupported): {group_counts['C']}")
    print()

    # ---------------------------------------------------------------
    # Print unsupported cases by tier
    # ---------------------------------------------------------------
    for tier in ["top10", "top50", "top100"]:
        cases = unsupported_by_tier[tier]
        if cases:
            print(f"=== GROUP C in {tier.upper()} ({len(cases)} cases) ===")
            for r in sorted(cases, key=lambda x: x["rank"]):
                print(f"  Rank {r['rank']:>3} | total={r['total_score']:.4f} | "
                      f"skill_signal={r['total_skill_signal']:.3f} | "
                      f"cf_no_skill={r['counterfactual_base_no_skill']:.4f} | "
                      f"{r['skill_alignment_reason'][:60]} | "
                      f"{r['title'][:22]} @ {r['company'][:15]}")
            print()

    # ---------------------------------------------------------------
    # Ranking impact analysis: would GROUP C candidates rank differently
    # without skill signal?
    # ---------------------------------------------------------------
    print("=== RANKING IMPACT ANALYSIS ===")
    group_c = [r for r in results if r["skill_alignment_group"] == "C"]
    group_a = [r for r in results if r["skill_alignment_group"] == "A"]
    group_b = [r for r in results if r["skill_alignment_group"] == "B"]

    if group_c:
        # For each Group C candidate: compute what rank they'd have if
        # their skill signal were removed (replaced with 0)
        # Compare with Group A/B candidate they'd swap with
        print("Group C candidates — counterfactual ranking if skill signal removed:")
        for r in sorted(group_c, key=lambda x: x["rank"]):
            # Find the first Group A/B candidate whose total_score is
            # between cf_no_skill and original total
            cf_total = r["counterfactual_base_no_skill"] + r["calibration_adj"]
            displaced_by = [
                a for a in results
                if a["total_score"] > cf_total and a["rank"] > r["rank"]
                and a["skill_alignment_group"] in ("A", "B")
            ]
            print(f"  Rank {r['rank']:>3}: total={r['total_score']:.4f} → cf={cf_total:.4f} | "
                  f"skill_signal={r['total_skill_signal']:.3f} | "
                  f"trap_flags={r['trap_flags'] or 'none'} | "
                  f"unsupported_skills={r['high_spec_matched']} | "
                  f"{r['title'][:22]} @ {r['company'][:15]}")
            if displaced_by:
                d = displaced_by[0]
                print(f"    Would be displaced by Rank {d['rank']}: total={d['total_score']:.4f} | "
                      f"{d['title'][:22]} @ {d['company'][:15]}")
        print()

    # ---------------------------------------------------------------
    # Signal statistics by group
    # ---------------------------------------------------------------
    def avg(lst, key):
        vals = [v[key] for v in lst if v[key] is not None]
        return sum(vals) / len(vals) if vals else 0.0

    print("=== SIGNAL STATISTICS BY GROUP ===")
    print(f"{'Metric':30} {'Group A':>10} {'Group B':>10} {'Group C':>10}")
    for metric in ["skill_overlap", "group_overlap", "total_skill_signal",
                   "career_evidence", "depth", "calibration_adj"]:
        a_val = avg(group_a, metric)
        b_val = avg(group_b, metric)
        c_val = avg(group_c, metric)
        print(f"  {metric:28} {a_val:>10.3f} {b_val:>10.3f} {c_val:>10.3f}")
    print()

    # ---------------------------------------------------------------
    # Write full results
    # ---------------------------------------------------------------
    Path(output_path).parent.mkdir(exist_ok=True)
    with open(output_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)
    print(f"Full audit data written to {output_path}")

    # ---------------------------------------------------------------
    # Top-10 detail
    # ---------------------------------------------------------------
    print()
    print("=== TOP-10 FULL DETAIL ===")
    for r in results[:10]:
        print(f"  Rank {r['rank']:>2}: [{r['skill_alignment_group']}] total={r['total_score']:.4f} | "
              f"skill_signal={r['total_skill_signal']:.3f} | "
              f"depth={r['depth']} eval={r['has_eval']} | "
              f"high_spec={r['high_spec_matched'] or 'NONE'} | "
              f"{r['title'][:22]} @ {r['company'][:15]}")
        if r["per_skill_groups"]:
            print(f"       per-skill: {r['per_skill_groups']}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default="data/candidates.jsonl")
    parser.add_argument("--submission", default="submission_phase8c4.csv")
    parser.add_argument("--output", default="outputs/phase8d4_audit_data.csv")
    args = parser.parse_args()
    run_audit(args.candidates, args.submission, args.output)
