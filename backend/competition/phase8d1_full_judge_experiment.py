"""
Phase 8D.1 — 100K Full Judge Exposure Ceiling Test

Core question:
  Are strong candidates missing because the judge is not good enough (A),
  or because the judge never evaluates them (B)?

What this phase does:
  Removes the early-exit heap filter from Phase 8C.4 so that every one of the
  ~100K candidates receives the FULL Phase 8C.4 evaluation in a single pass:

    1. Base score (_competition_score_c4)         ← TYPE A: candidate-level
    2. Evidence calibration (evidence_calibrator) ← TYPE A: candidate-level
    3. Reranker signals (_headroom_depth_bonus,
       behavioral bonus, surface penalty,
       trap penalty)                              ← TYPE A: candidate-level
    4. Final heap selection (top 300)             ← TYPE B: pool-level (unchanged)
    5. Sort + top 100                             ← TYPE B: pool-level (unchanged)

What is NOT changed:
    - Base score formula or weights
    - Evidence calibration bonuses / penalties
    - Trap detection rules
    - Reranker bonus formulas
    - Heap size (still 300)
    - Final selection threshold (still 100)
    - production disclaimer multiplier (8C.4 feature)

Why single-pass instead of two-pass (like 8C.4):
  8C.4 does two passes: first to find top-300, second to reload profiles for
  reranking. Since all reranker signals are TYPE A (candidate-level, no inter-
  candidate comparison), they can be computed in the same first pass using the
  data already in memory. This avoids a second file read and is ~30% faster.

Component classification (per Task 1 / Task 2):
  TYPE A (runs on all 100K in this experiment):
    - adapt_redrob_candidate
    - build_competition_core_signals
    - _competition_score_c4
    - calibrate_candidate_evidence
    - _calibrated_score
    - _extract_career_signals (for reranker depth)
    - _extract_behavioral_signals (for beh bonus)
    - _headroom_depth_bonus
    - behavioral bonus: (avail + engagement) * 0.005
    - surface_penalty: -0.030 if surface_match_risk
    - trap_penalty: -0.050 if trap_flags

  TYPE B (pool-level, unchanged):
    - heapq sort (maintains top 300 by final score)
    - sort + top 100 slice
    - _competition_reasoning (top 100 only, no change)
    - CSV write

Phase 8C.4 is NOT edited. This is a separate experiment file.
"""
from __future__ import annotations

import csv
import heapq
import time
from pathlib import Path

# Monkeypatch TOP_K before importing rank (same pattern as 8C.4)
import backend.competition.rank
backend.competition.rank.TOP_K = 300

from backend.competition.evaluate import _extract_career_signals, _extract_behavioral_signals
from backend.competition.rerank_experiment import _headroom_depth_bonus
from backend.utils.skill_taxonomy import normalize_whitespace, get_active_groups
from backend.dataset_intelligence.loader import iter_dataset_records
from backend.competition.redrob_adapter import adapt_redrob_candidate
from backend.competition.evidence_calibrator import (
    AI_INFRA_TERMS,
    calibrate_candidate_evidence,
)
from backend.competition.rank import (
    CompetitionCandidate,
    _calibrated_score,
    _experience_fit,
    _important_terms,
    _ratio,
    configure_offline_environment,
    read_job_text,
    _competition_reasoning,
)
from backend.intelligence.candidate_engine import (
    build_competition_core_signals,
    build_candidate_intelligence,
)
from backend.parsers.jd_analyzer import analyze_job_description
from backend.competition.validate_submission import validate_submission


# ---------------------------------------------------------------------------
# Phase 8C.4 production disclaimer phrases — carried forward unchanged
# ---------------------------------------------------------------------------

_PROD_DISCLAIMER_PHRASES: tuple[str, ...] = (
    "production deployment was handled by",
    "deployment was handled by the platform",
    "pure ml side of the work",
    "production was handled by",
    "ops team handled",
    "platform team handled",
    "platform handled the deployment",
    "infra team handled",
)

_PROD_DISCLAIMER_MULTIPLIER: float = 0.5


def _career_evidence_score(profile) -> float:
    """
    Identical to Phase 8C.4's _career_evidence_score().
    Counts AI_INFRA_TERMS hits in career text; applies 0.5× multiplier when
    explicit production ownership disclaimers are detected.
    No formula change from 8C.4.
    """
    career_text = normalize_whitespace(
        " ".join(str(item.get("description") or "") for item in profile.career_history)
    ).lower()
    if not career_text:
        return 0.0
    hits = sum(1 for term in AI_INFRA_TERMS if term in career_text)
    base_score = min(hits, 5) / 5.0
    if any(phrase in career_text for phrase in _PROD_DISCLAIMER_PHRASES):
        base_score *= _PROD_DISCLAIMER_MULTIPLIER
    return base_score


def _competition_score_c4(profile, core_signals: dict, job_analysis, job_terms: set) -> float:
    """
    Identical to Phase 8C.4's _competition_score_c4(). No formula change.
    Weights: skill=0.26, group=0.16, term=0.18, experience=0.12, signal=0.20, career=0.08
    """
    candidate_skills = set(profile.skills)
    job_core_skills = set(job_analysis.core_skills)
    skill_overlap = (
        _ratio(len(candidate_skills & job_core_skills), len(job_core_skills))
        if job_core_skills else 0.0
    )
    candidate_groups = set(get_active_groups(profile.skills))
    job_groups = set(get_active_groups(job_analysis.all_skills))
    group_overlap = _ratio(len(candidate_groups & job_groups), len(job_groups))
    candidate_terms = _important_terms(profile.searchable_profile_text or profile.raw_text)
    term_overlap = _ratio(len(candidate_terms & job_terms), len(job_terms))
    experience_fit = _experience_fit(profile.years_of_experience)
    signal_average = _ratio(
        core_signals.get("technical_depth", 0.0)
        + core_signals.get("execution_maturity", 0.0)
        + core_signals.get("startup_readiness", 0.0)
        + core_signals.get("transferability", 0.0)
        + core_signals.get("domain_relevance", 0.0),
        500.0,
    )
    career_evidence = _career_evidence_score(profile)

    score = (
        skill_overlap    * 0.26
        + group_overlap  * 0.16
        + term_overlap   * 0.18
        + experience_fit * 0.12
        + signal_average * 0.20
        + career_evidence * 0.08
    )
    return round(max(0.0, min(1.0, score)), 6)


def run_phase8d1(candidates_path: str, job_path: str, output_path: str) -> None:
    t_start = time.time()
    print("Phase 8D.1: Full Judge Exposure — 100K candidates, no early exit.")
    configure_offline_environment()
    job_text = read_job_text(job_path)
    job_analysis = analyze_job_description(job_text)
    job_terms = _important_terms(job_text)

    # Heap maintains top 300 by FINAL score (after all TYPE A signals applied).
    # Tuple: (final_score, candidate_id, profile, calibration, base_score, calibrated_score)
    top_heap: list = []
    seen: set = set()
    total_scanned = 0
    reached_calibration = 0
    entered_heap = 0

    # -------------------------------------------------------------------------
    # SINGLE PASS over all 100K candidates.
    # Every candidate gets the full TYPE A evaluation — no early exit.
    # The heap is still size 300 for pool-level selection (TYPE B).
    # -------------------------------------------------------------------------
    for raw in iter_dataset_records(candidates_path):
        p = adapt_redrob_candidate(raw)
        if not p.candidate_id or p.candidate_id in seen:
            continue
        seen.add(p.candidate_id)
        total_scanned += 1

        # TYPE A: Base score
        core = build_competition_core_signals(p)
        base = _competition_score_c4(p, core, job_analysis, job_terms)

        # TYPE A: Evidence calibration — NO EARLY EXIT (key difference from 8C.4)
        cal = calibrate_candidate_evidence(p)
        reached_calibration += 1
        calibrated = _calibrated_score(base, cal)

        # TYPE A: Reranker signals (computed in same pass, no second file read)
        career_text = normalize_whitespace(
            " ".join(str(i.get("description", "")) for i in p.career_history)
        ).lower()
        career_sigs = _extract_career_signals(career_text)
        beh_sigs = _extract_behavioral_signals(p.redrob_signals or {})

        depth_bonus     = _headroom_depth_bonus(cal.adjustment, career_text, career_sigs)
        beh_bonus       = (beh_sigs["availability_score"] + beh_sigs["engagement_score"]) * 0.005
        surface_penalty = -0.030 if career_sigs["surface_match_risk"] else 0.0
        trap_penalty    = -0.050 if cal.trap_flags else 0.0

        final_score = calibrated + depth_bonus + beh_bonus + surface_penalty + trap_penalty

        # TYPE B: Pool-level heap maintenance
        item = (final_score, p.candidate_id, p, cal, base, calibrated)
        if len(top_heap) < 300:
            heapq.heappush(top_heap, item)
            entered_heap += 1
        elif item > top_heap[0]:
            heapq.heapreplace(top_heap, item)
            entered_heap += 1

    t_scan = time.time()
    print(f"  Scanned: {total_scanned:,} | Calibrated: {reached_calibration:,} | Heap entries: {entered_heap}")
    print(f"  Scan+eval time: {t_scan - t_start:.1f}s")

    # TYPE B: Sort heap, take top 100
    sorted_pool = sorted(top_heap, key=lambda x: (-x[0], x[1]))
    top100 = sorted_pool[:100]

    print("  Generating reasoning for top 100...")
    output = Path(output_path)
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["candidate_id", "rank", "score", "reasoning"])
        writer.writeheader()
        for rank_pos, (final_score, cid, p, cal, base, calibrated) in enumerate(top100, start=1):
            _, evidence_library = build_candidate_intelligence(p)
            reasoning = _competition_reasoning(p, job_analysis, evidence_library, cal)
            writer.writerow({
                "candidate_id": cid,
                "rank":         rank_pos,
                "score":        f"{final_score:.6f}",
                "reasoning":    reasoning,
            })

    t_end = time.time()
    print(f"  Reasoning + write time: {t_end - t_scan:.1f}s")
    print(f"  Total runtime: {t_end - t_start:.1f}s")

    errors = validate_submission(output_path)
    if errors:
        raise ValueError("Invalid submission: " + " ".join(errors))
    print(f"  Written valid submission to {output_path}")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Phase 8D.1: 100K full judge exposure.")
    parser.add_argument("--candidates", default="data/candidates.jsonl")
    parser.add_argument("--job",        default="data/job_description.docx")
    parser.add_argument("--output",     default="submission_phase8d1.csv")
    args = parser.parse_args()
    run_phase8d1(args.candidates, args.job, args.output)


if __name__ == "__main__":
    main()
