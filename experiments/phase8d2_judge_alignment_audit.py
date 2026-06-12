"""
Phase 8D.2 — Official-Doc Alignment Audit Script

Derives evaluation criteria ONLY from official challenge documents, then
categorizes all 100K candidates into four agreement groups:

  GROUP A: High current score + strong official alignment  → judge likely correct
  GROUP B: High current score + weak official alignment    → possible over-reward
  GROUP C: Low current score  + strong official alignment  → possible missed candidate
  GROUP D: Low current score  + weak official alignment    → correct rejection

Official criteria (from job_description.docx — JD):
  REQUIRED (hard):
    R1: Production experience with embeddings-based retrieval systems
    R2: Production experience with vector databases / hybrid search infrastructure
    R3: Strong Python / code quality (hard to measure from text; excluded from automated scoring)
    R4: Evaluation framework design (NDCG/MRR/MAP/A-B testing)

  DESIRED (soft, not disqualifiers):
    D1: LLM fine-tuning experience (LoRA, QLoRA, PEFT)
    D2: Learning-to-rank models (XGBoost/neural LTR)
    D3: HR-tech / recruiting / marketplace product experience
    D4: Distributed systems / large-scale inference
    D5: Open-source ML contributions

  DISQUALIFIERS (from JD):
    X1: Pure research / academic only — no production deployment
    X2: Recent (<12mo) LLM framework demo experience only (LangChain/OpenAI calls)
    X3: No production code written in last 18 months (pure architect/manager)
    X4: Primary expertise in CV/speech/robotics without NLP/IR
    X5: Consulting-only career (TCS, Infosys, Wipro, Accenture, Cognizant, Capgemini)
        with no product company experience

  BEHAVIORAL MODIFIER (from redrob_signals_doc.docx):
    B1: Availability signals (open_to_work, notice_period, relocate)
    B2: Engagement signals (response_rate, interview_completion, github)

  HACKATHON-SPECIFIC NOTE (JD "Final note" section):
    The "right answer" is NOT keyword matching in skills section
    A Tier-5 candidate with no "RAG"/"Pinecone" keywords but career history
    showing a recommendation system at a product company IS a fit
    A Marketing Manager with all AI keywords is NOT a fit
    Behavioral signals should down-weight unavailable candidates

Official scoring metric (from submission_spec.docx):
    NDCG@10: 50% weight (top-10 quality matters most)
    NDCG@50: 30% weight
    MAP:     15% weight (whole-list quality)
    P@10:     5% weight

NOTE: R3 (Python code quality) cannot be measured from profile text; excluded.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, ".")

from backend.dataset_intelligence.loader import iter_dataset_records
from backend.competition.redrob_adapter import adapt_redrob_candidate
from backend.competition.evidence_calibrator import (
    calibrate_candidate_evidence,
    AI_INFRA_TERMS,
    EVALUATION_MATURITY_TERMS,
    HONEYPOT_COMPANY_NAMES,
)
from backend.competition.evaluate import _extract_career_signals, _extract_behavioral_signals
from backend.utils.skill_taxonomy import normalize_whitespace


# ---------------------------------------------------------------------------
# Official evaluation criteria derived from job_description.docx
# These are NOT implementation heuristics — they come directly from the JD.
# ---------------------------------------------------------------------------

# R1: Production embeddings-based retrieval (JD: "Things you absolutely need" #1)
# Evidence: worked with embedding models AND deployed to real users AND handled operational aspects
R1_EMBED_TERMS = {
    "embedding", "embeddings", "sentence-transformer", "sentence_transformer",
    "bge", "e5", "openai embeddings", "dense retrieval", "dense vector",
}
R1_PROD_CONTEXT = {
    "deployed", "production", "users", "scale", "drift", "index refresh",
    "retrieval quality", "latency", "monitoring",
}

# R2: Vector database / hybrid search infrastructure (JD: "Things you absolutely need" #2)
# Evidence: named vector DB experience OR hybrid search infrastructure
R2_VECDB_TERMS = {
    "pinecone", "weaviate", "qdrant", "milvus", "opensearch", "elasticsearch",
    "faiss", "hnsw", "pgvector", "vector database", "vector search", "vector store",
}
R2_HYBRID_TERMS = {
    "hybrid retrieval", "hybrid search", "bm25", "sparse", "dense",
}

# R4: Evaluation framework for ranking (JD: "Things you absolutely need" #4)
# Evidence: has thought about evaluation rigorously
R4_EVAL_TERMS = {
    "ndcg", "mrr", "map", "mean average precision", "recall@", "precision@",
    "a/b test", "ab test", "offline eval", "offline-to-online",
    "evaluation framework", "ranking metrics", "ranking quality",
    "offline benchmark", "online eval",
}
# Extended eval evidence (from JD: "recruiter-feedback loops", "offline benchmarks")
R4_EXTENDED_EVAL = {
    "relevance label", "human judgment", "human judgement", "click-through",
    "learning-to-rank", "ltr", "held-out", "offline", "eval set",
}

# Retrieval + ranking system types (JD: "own the intelligence layer... ranking, retrieval, matching")
SYSTEM_TERMS = {
    "ranking", "retrieval", "recommendation", "recommender", "search",
    "re-rank", "rerank", "learning-to-rank", "ltr", "two-stage",
    "candidate retrieval", "candidate ranking",
}

# Disqualifier detection
X1_RESEARCH_TERMS = {"research lab", "academic", "phd research", "research-only", "published paper"}
X2_FRAMEWORK_ONLY = {"langchain", "openai api", "chatgpt api"}  # Only these, no other retrieval/infra
X4_WRONG_DOMAIN = {"computer vision", "image classification", "speech recognition", "robotics", "gan"}
X5_CONSULTING_ONLY = {"tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini"}

# Behavioral signals per redrob_signals_doc.docx
# "down-weight appropriately" per JD final note
BEHAVIOR_STRONG_POSITIVE = {
    "open_to_work": True,
    "notice_period_max": 30,
    "response_rate_min": 0.7,
}


def _official_alignment_score(profile, cal, career_text: str, career_sigs: dict) -> dict:
    """
    Score candidate against OFFICIAL JD criteria only.
    Returns a breakdown dict with individual criterion scores and a total.
    Does NOT use any Phase 8C.4 implementation signals.
    """
    ct = career_text  # already lowercase

    # ----------------------------------------------------------------
    # R1: Production embeddings retrieval experience
    # ----------------------------------------------------------------
    has_embed = bool(R1_EMBED_TERMS & set(t for t in R1_EMBED_TERMS if t in ct))
    has_prod_context = bool(R1_PROD_CONTEXT & set(t for t in R1_PROD_CONTEXT if t in ct))
    r1_score = 1.0 if (has_embed and has_prod_context) else (0.5 if has_embed else 0.0)

    # ----------------------------------------------------------------
    # R2: Vector DB / hybrid search infrastructure
    # ----------------------------------------------------------------
    has_vecdb = bool(any(t in ct for t in R2_VECDB_TERMS))
    has_hybrid = bool(any(t in ct for t in R2_HYBRID_TERMS))
    r2_score = 1.0 if has_vecdb else (0.5 if has_hybrid else 0.0)

    # ----------------------------------------------------------------
    # R4: Evaluation framework
    # ----------------------------------------------------------------
    has_eval_exact = bool(any(t in ct for t in R4_EVAL_TERMS))
    has_eval_extended = bool(any(t in ct for t in R4_EXTENDED_EVAL))
    r4_score = 1.0 if has_eval_exact else (0.5 if has_eval_extended else 0.0)

    # ----------------------------------------------------------------
    # System building: shipped at least one ranking/retrieval/recommendation system
    # (JD: "Has shipped at least one end-to-end ranking, search, or recommendation system")
    # ----------------------------------------------------------------
    has_system = bool(any(t in ct for t in SYSTEM_TERMS))
    has_ownership = bool(cal.ownership_hits)
    has_production = bool(cal.production_hits)
    shipped_system = has_system and has_ownership and has_production

    # ----------------------------------------------------------------
    # Disqualifier checks
    # ----------------------------------------------------------------
    # X1: Pure research only (no production at all)
    x1_pure_research = (bool(any(t in ct for t in X1_RESEARCH_TERMS))
                        and not has_production and not shipped_system)
    # X2: Framework-only (LangChain/OpenAI only, no real infra)
    has_framework_only = (bool(any(t in ct for t in X2_FRAMEWORK_ONLY))
                          and not has_vecdb and not has_embed and r1_score == 0.0)
    # X4: Wrong domain primary
    x4_wrong_domain = (bool(any(t in ct for t in X4_WRONG_DOMAIN))
                       and not has_system and not has_embed and not has_vecdb)
    # X5: Consulting-only (check company in career history)
    company_text = " ".join(
        str(h.get("company", "")).lower() for h in profile.career_history
    )
    all_consulting = (
        all(any(c in h.get("company", "").lower() for c in X5_CONSULTING_ONLY)
            for h in profile.career_history if h.get("company"))
        if profile.career_history else False
    )
    x5_consulting = all_consulting

    has_disqualifier = x1_pure_research or has_framework_only or x4_wrong_domain or x5_consulting
    honeypot = bool(cal.trap_flags and
                    any("honeypot" in f for f in cal.trap_flags))

    # ----------------------------------------------------------------
    # Experience band: JD says 5-9 years ideal, accepts outside band
    # ----------------------------------------------------------------
    yoe = profile.years_of_experience
    yoe_fit = "ideal" if 5.0 <= yoe <= 9.0 else ("acceptable" if 3.0 <= yoe <= 14.0 else "outside")

    # ----------------------------------------------------------------
    # Official alignment score (0.0 – 1.0)
    # Weights: R1=0.35, R2=0.30, R4=0.25, system_built=0.10
    # Reasoning: R1+R2 are absolute requirements (#1 and #2 in JD)
    #            R4 is absolute requirement (#4)
    #            shipped_system is the JD's "ideal candidate" descriptor
    # ----------------------------------------------------------------
    raw = r1_score * 0.35 + r2_score * 0.30 + r4_score * 0.25 + (0.10 if shipped_system else 0.0)
    if has_disqualifier or honeypot:
        raw *= 0.3  # Heavy penalty for official disqualifiers

    return {
        "official_score": round(raw, 4),
        "r1_embed_retrieval": r1_score,
        "r2_vecdb_hybrid": r2_score,
        "r4_eval_framework": r4_score,
        "shipped_system": shipped_system,
        "has_disqualifier": has_disqualifier,
        "honeypot": honeypot,
        "yoe_fit": yoe_fit,
        "disqualifier_types": [
            t for t, v in [
                ("X1:pure_research", x1_pure_research),
                ("X2:framework_only", has_framework_only),
                ("X4:wrong_domain", x4_wrong_domain),
                ("X5:consulting_only", x5_consulting),
            ] if v
        ],
    }


def run_audit(
    candidates_path: str = "data/candidates.jsonl",
    submission_path: str = "submission_phase8c4.csv",
    output_path: str = "outputs/phase8d2_audit_data.csv",
) -> None:
    """Run the full official alignment audit across all 100K candidates."""

    # Load submission ranks
    with open(submission_path) as f:
        ranked = {r["candidate_id"]: int(r["rank"]) for r in csv.DictReader(f)}

    # Thresholds for "high" vs "low" current score
    # "high" = in top-100 (the submission) or estimated to be strong
    # We'll use rank <= 100 as "high current score" (the judge's selection)
    # and rank > 100 OR not ranked as "low current score"
    TOP_N = 100  # judge's final selection
    OFFICIAL_STRONG = 0.50  # official score >= this = strong official alignment
    OFFICIAL_WEAK   = 0.25  # official score < this  = weak official alignment

    groups = {"A": [], "B": [], "C": [], "D": []}
    all_records = []

    print(f"Running official alignment audit on all candidates...")
    scanned = 0

    for raw in iter_dataset_records(candidates_path):
        cid = raw.get("candidate_id", "")
        if not cid:
            continue
        p = adapt_redrob_candidate(raw)
        cal = calibrate_candidate_evidence(p)
        career_text = normalize_whitespace(
            " ".join(str(i.get("description", "")) for i in p.career_history)
        ).lower()
        career_sigs = _extract_career_signals(career_text)
        beh_sigs = _extract_behavioral_signals(p.redrob_signals or {})
        official = _official_alignment_score(p, cal, career_text, career_sigs)

        current_rank = ranked.get(cid)
        judge_selected = current_rank is not None  # in top 100
        high_judge = judge_selected
        os = official["official_score"]
        strong_official = os >= OFFICIAL_STRONG
        weak_official = os < OFFICIAL_WEAK

        # Group assignment
        if high_judge and strong_official:
            group = "A"
        elif high_judge and weak_official:
            group = "B"
        elif not high_judge and strong_official:
            group = "C"
        else:
            group = "D"

        rec = {
            "candidate_id": cid,
            "current_rank": current_rank or 9999,
            "judge_selected": judge_selected,
            "official_score": os,
            "r1": official["r1_embed_retrieval"],
            "r2": official["r2_vecdb_hybrid"],
            "r4": official["r4_eval_framework"],
            "shipped": official["shipped_system"],
            "disqualifier": official["has_disqualifier"],
            "disqualifier_types": "|".join(official["disqualifier_types"]),
            "honeypot": official["honeypot"],
            "yoe": p.years_of_experience,
            "yoe_fit": official["yoe_fit"],
            "calibration_adj": cal.adjustment,
            "career_ai_hits": len(cal.career_ai_infra_hits),
            "depth": career_sigs["evidence_depth"],
            "trap_flags": "|".join(cal.trap_flags),
            "title": p.structured_profile.get("current_title", ""),
            "company": p.structured_profile.get("current_company", ""),
            "group": group,
        }
        groups[group].append(rec)
        all_records.append(rec)
        scanned += 1
        if scanned % 10000 == 0:
            print(f"  {scanned:,} processed...")

    print(f"\nAudit complete. {scanned:,} candidates.")
    print(f"GROUP A (judge correct,  strong official): {len(groups['A'])}")
    print(f"GROUP B (high judge,     weak  official): {len(groups['B'])}")
    print(f"GROUP C (low  judge,     strong official): {len(groups['C'])}")
    print(f"GROUP D (correct reject, weak  official): {len(groups['D'])}")
    print()

    # ----------------------------------------------------------------
    # Detailed Group B analysis: candidates the judge selected but
    # official criteria say shouldn't rank highly
    # ----------------------------------------------------------------
    print("=== GROUP B: HIGH JUDGE, WEAK OFFICIAL ALIGNMENT ===")
    gb_sorted = sorted(groups["B"], key=lambda x: x["current_rank"])
    for r in gb_sorted[:20]:
        print(f"  Rank {r['current_rank']:>3} | official={r['official_score']:.2f} | "
              f"r1={r['r1']:.1f} r2={r['r2']:.1f} r4={r['r4']:.1f} | "
              f"adj={r['calibration_adj']:+.3f} | "
              f"{'DISQ:'+r['disqualifier_types'] if r['disqualifier'] else ''} | "
              f"{r['title'][:28]} @ {r['company'][:18]}")

    print()
    print("=== GROUP C: LOW JUDGE, STRONG OFFICIAL ALIGNMENT (top 30) ===")
    gc_sorted = sorted(groups["C"], key=lambda x: -x["official_score"])
    for r in gc_sorted[:30]:
        print(f"  official={r['official_score']:.2f} | "
              f"r1={r['r1']:.1f} r2={r['r2']:.1f} r4={r['r4']:.1f} | "
              f"depth={r['depth']} | yoe={r['yoe']:.1f} | adj={r['calibration_adj']:+.3f} | "
              f"{r['title'][:28]} @ {r['company'][:18]}")

    # Write full audit data
    Path(output_path).parent.mkdir(exist_ok=True)
    with open(output_path, "w", newline="") as f:
        fieldnames = list(all_records[0].keys())
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(all_records)
    print(f"\nFull audit data written to {output_path}")

    # ----------------------------------------------------------------
    # Summary statistics
    # ----------------------------------------------------------------
    print()
    print("=== TOP-10 OFFICIAL ALIGNMENT SUMMARY ===")
    top10_recs = [r for r in all_records if r["current_rank"] <= 10]
    for r in sorted(top10_recs, key=lambda x: x["current_rank"]):
        print(f"  Rank {r['current_rank']:>2}: off={r['official_score']:.2f} | "
              f"r1={r['r1']:.1f} r2={r['r2']:.1f} r4={r['r4']:.1f} | "
              f"depth={r['depth']} | {r['title'][:25]} @ {r['company'][:18]}")

    print()
    print("=== TOP-100 DISTRIBUTION ===")
    top100_recs = [r for r in all_records if r["current_rank"] <= 100]
    strong = [r for r in top100_recs if r["official_score"] >= OFFICIAL_STRONG]
    medium = [r for r in top100_recs if OFFICIAL_WEAK <= r["official_score"] < OFFICIAL_STRONG]
    weak = [r for r in top100_recs if r["official_score"] < OFFICIAL_WEAK]
    print(f"  Strong official (>={OFFICIAL_STRONG}): {len(strong)} / 100")
    print(f"  Medium official ({OFFICIAL_WEAK}–{OFFICIAL_STRONG}):  {len(medium)} / 100")
    print(f"  Weak official   (<{OFFICIAL_WEAK}):  {len(weak)} / 100")
    print(f"  Mean official score top-100: {sum(r['official_score'] for r in top100_recs)/len(top100_recs):.3f}")
    print()
    print("=== VOCABULARY DEPENDENCY TEST ===")
    # How many Group C (missed) candidates have strong official evidence but
    # low vocab overlap (would fail skill-overlap signal)?
    gc_high_official = [r for r in groups["C"] if r["official_score"] >= 0.65]
    print(f"  Group C with official >= 0.65 (strong miss): {len(gc_high_official)}")
    if gc_high_official:
        print("  Sample:")
        for r in gc_high_official[:10]:
            print(f"    off={r['official_score']:.2f} r1={r['r1']:.1f} r2={r['r2']:.1f} | "
                  f"{r['title'][:25]} @ {r['company'][:18]}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default="data/candidates.jsonl")
    parser.add_argument("--submission", default="submission_phase8c4.csv")
    parser.add_argument("--output", default="outputs/phase8d2_audit_data.csv")
    args = parser.parse_args()
    run_audit(args.candidates, args.submission, args.output)
