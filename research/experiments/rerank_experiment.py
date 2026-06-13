"""
Phase 8B — Official-Doc Derived Top-N Reranker (v2 — Phase 8B.1 corrected)

Fixes applied per outputs/phase8b_merge_audit.md:
  Fix 1: Headroom-scaled depth bonus — prevents double-counting Phase 7 calibration.
  Fix 2: Context-pattern eval detection — catches evaluation maturity expressed
         as relevance labeling, click-through, LTR, held-out sets, etc., without
         requiring the exact tokens 'ndcg'/'mrr'/'a/b test'.
"""
from __future__ import annotations

import argparse
import csv
import heapq
import re
import sys
from pathlib import Path

# Monkeypatch TOP_K before importing rank
import backend.competition.rank
backend.competition.rank.TOP_K = 300

from backend.competition.evaluate import _extract_career_signals, _extract_behavioral_signals
from backend.utils.skill_taxonomy import normalize_whitespace
from backend.dataset_intelligence.loader import iter_dataset_records
from backend.competition.redrob_adapter import adapt_redrob_candidate


# ---------------------------------------------------------------------------
# Fix 2 — Deterministic context-pattern evaluation maturity detection
# Catches candidates who demonstrate eval maturity via vocabulary other than
# exact metric tokens (ndcg, mrr, a/b test, etc.).
# Patterns are derived from JD language: "offline benchmarks", "recruiter-
# feedback loops", "keep improving without flying blind" — i.e., the JD
# values measurement discipline expressed in many ways.
# ---------------------------------------------------------------------------

# Each entry: (anchor_phrase, context_words_that_must_appear_in_200char_window)
# context_words=None means the anchor alone implies eval maturity.
_EVAL_CONTEXT_PATTERNS: list[tuple[str, tuple[str, ...] | None]] = [
    ("relevance",       ("metric", "measure", "quality", "label", "judgment", "judgement", "feedback")),
    ("ranking",         ("metric", "measure", "quality", "label", "judgment", "judgement", "improved", "improvement")),
    ("retrieval",       ("metric", "measure", "quality", "label", "improved", "improvement")),
    ("click",           ("through", "data", "feedback", "label")),
    ("learning-to-rank",None),
    ("ltr",             None),
    ("relevance label", None),
    ("relevance feedback", None),
    ("held-out",        None),
    ("held out eval",   None),
    ("human judgment",  None),
    ("human judgement", None),
    ("human label",     None),
    ("eval set",        None),
    ("eval workflow",   None),
    ("offline",         ("eval", "evaluation", "test", "benchmark", "metric")),
]


def _has_eval_context(career_lower: str) -> bool:
    """Return True if career text contains patterns implying evaluation maturity."""
    for anchor, context_words in _EVAL_CONTEXT_PATTERNS:
        if anchor not in career_lower:
            continue
        if context_words is None:
            return True
        pos = career_lower.find(anchor)
        while pos != -1:
            window = career_lower[max(0, pos - 100): pos + 200]
            if any(cw in window for cw in context_words):
                return True
            pos = career_lower.find(anchor, pos + 1)
    return False


# ---------------------------------------------------------------------------
# Fix 1 — Headroom-scaled depth bonus
# Phase 7 calibration already rewards retrieval + eval signals with up to +0.10.
# This bonus fires proportionally to the unused headroom in Phase 7's adjustment,
# so candidates that already received the full P7 bonus get near-zero extra credit.
# Formula: bonus = (1 - p7_adj / P7_MAX_ADJ) * (effective_depth / 4) * MAX_RERANK_BONUS
# ---------------------------------------------------------------------------

_P7_MAX_ADJ: float = 0.100
_MAX_RERANK_BONUS: float = 0.030   # conservative ceiling so no single candidate is over-lifted


def _headroom_depth_bonus(
    p7_adjustment: float,
    career_lower: str,
    career_sigs: dict,
) -> float:
    """Compute a headroom-scaled evidence depth bonus."""
    # Compute effective depth, using context-aware eval detection (Fix 2)
    has_eval = career_sigs["has_eval_maturity"] or _has_eval_context(career_lower)
    has_retrieval = career_sigs["has_retrieval"]
    has_system = career_sigs["has_system"]
    has_career_ev = career_sigs["has_career_evidence"]
    effective_depth = sum([has_eval, has_retrieval, has_system, has_career_ev])

    if effective_depth == 0:
        return 0.0

    # Headroom: 1.0 = P7 calibration gave nothing; 0.0 = P7 already maxed
    headroom = max(0.0, 1.0 - p7_adjustment / _P7_MAX_ADJ)

    return round(headroom * (effective_depth / 4.0) * _MAX_RERANK_BONUS, 6)

def run_reranker(candidates_path: str, job_path: str, output_path: str):
    print("Running base ranking to collect top 300...")
    import backend.competition.rank
    from backend.competition.rank import (
        read_job_text, analyze_job_description, _important_terms,
        _competition_score, _calibrated_score, MAX_EVIDENCE_ADJUSTMENT,
        CompetitionCandidate
    )
    from backend.intelligence.candidate_engine import build_competition_core_signals
    from backend.competition.evidence_calibrator import calibrate_candidate_evidence
    
    backend.competition.rank.configure_offline_environment()
    job_text = read_job_text(job_path)
    job_analysis = analyze_job_description(job_text)
    job_terms = _important_terms(job_text)
    top_candidates = []
    seen = set()

    for raw in iter_dataset_records(candidates_path):
        p = adapt_redrob_candidate(raw)
        if not p.candidate_id or p.candidate_id in seen:
            continue
        seen.add(p.candidate_id)
        core = build_competition_core_signals(p)
        base = _competition_score(p, core, job_analysis, job_terms)
        if len(top_candidates) >= 300 and base + MAX_EVIDENCE_ADJUSTMENT < top_candidates[0][0]:
            continue
        cal = calibrate_candidate_evidence(p)
        score = _calibrated_score(base, cal)
        c = CompetitionCandidate(
            candidate_id=p.candidate_id, score=score, base_score=base,
            evidence_adjustment=cal.adjustment, calibration=cal, profile=p
        )
        item = (score, c.candidate_id, c)
        if len(top_candidates) < 300:
            heapq.heappush(top_candidates, item)
        elif item > top_candidates[0]:
            heapq.heapreplace(top_candidates, item)
            
    pool_candidates = [item[2] for item in sorted(top_candidates, key=lambda x: (-x[0], x[1]))]
    
    # We need the full profiles to extract evidence
    # We load only the 300 we care about
    print("Loading profiles for reranking...")
    cids_in_pool = {c.candidate_id for c in pool_candidates}
    profiles = {}
    for raw in iter_dataset_records(candidates_path):
        if raw.get("candidate_id") in cids_in_pool:
            p = adapt_redrob_candidate(raw)
            profiles[p.candidate_id] = p
            if len(profiles) == len(cids_in_pool):
                break

    print("Applying official-signal evidence reranker...")
    reranked = []
    for c in pool_candidates:
        cid = c.candidate_id
        p = profiles[cid]
        
        career_text = normalize_whitespace(" ".join(str(i.get("description", "")) for i in p.career_history)).lower()
        career_sigs = _extract_career_signals(career_text)
        beh_sigs = _extract_behavioral_signals(p.redrob_signals or {})
        
        # FIX 1 — Headroom-scaled depth bonus (replaces blanket depth*0.015)
        # Only adds credit for evidence NOT already captured by Phase 7 calibration.
        depth_bonus = _headroom_depth_bonus(c.calibration.adjustment, career_text, career_sigs)

        # Behavioral modifier — not double-counted by Phase 7 (Phase 7 uses only as tie-breaker
        # when career_ai_hits OR production_hits are present; the full engagement+availability
        # score here is independent). Max ~0.010.
        beh_bonus = (beh_sigs["availability_score"] + beh_sigs["engagement_score"]) * 0.005

        # Surface match penalty: system keywords without production/ownership evidence
        surface_penalty = -0.030 if career_sigs["surface_match_risk"] else 0.0

        # Trap flag penalty — reinforces Phase 7 trap detection for borderline cases
        trap_penalty = -0.050 if c.calibration.trap_flags else 0.0

        rerank_score = c.score + depth_bonus + beh_bonus + surface_penalty + trap_penalty
        
        reranked.append({
            "candidate_id": cid,
            "old_score": c.score,
            "new_score": rerank_score,
            "reasoning": c.reasoning
        })
        
    # Sort by new score descending, tie break by candidate ID ascending
    reranked.sort(key=lambda x: (-x["new_score"], x["candidate_id"]))
    
    # Take top 100
    top100 = reranked[:100]
    
    print("Generating reasoning for top 100...")
    from backend.competition.rank import _competition_reasoning
    from backend.intelligence.candidate_engine import build_candidate_intelligence
    for c in top100:
        p = profiles[c["candidate_id"]]
        _, evidence_library = build_candidate_intelligence(p)
        # We need the original calibration to generate reasoning properly
        # Find the original CompetitionCandidate object
        orig_c = next(x for x in pool_candidates if x.candidate_id == c["candidate_id"])
        c["reasoning"] = _competition_reasoning(
            p,
            job_analysis,
            evidence_library,
            orig_c.calibration,
        )

    print(f"Writing {len(top100)} candidates to {output_path}...")
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["candidate_id", "rank", "score", "reasoning"])
        writer.writeheader()
        for rank, c in enumerate(top100, start=1):
            writer.writerow({
                "candidate_id": c["candidate_id"],
                "rank": rank,
                "score": f"{c['new_score']:.6f}",
                "reasoning": c["reasoning"]
            })
    print("Done.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default="data/candidates.jsonl")
    parser.add_argument("--job", default="data/job_description.docx")
    parser.add_argument("--output", default="submission_phase8b3.csv")
    args = parser.parse_args()
    
    run_reranker(args.candidates, args.job, args.output)

if __name__ == "__main__":
    main()