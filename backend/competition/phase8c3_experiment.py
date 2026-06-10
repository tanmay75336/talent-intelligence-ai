"""
Phase 8C.3 — Career Evidence as First-Class Base Score Signal

Architecture change from Phase 8C.2 finding:
  The current system places career evidence (calibration) AFTER base score
  pre-selection. This means candidates whose base score is below the threshold
  are silently excluded before their career evidence is ever evaluated.

This experiment adds a career evidence component DIRECTLY to the base score,
so that demonstrated JD-relevant system-building experience participates in
candidate pre-selection, not just as a post-qualification correction.

Signal design:
  _career_evidence_score(profile) -> float [0.0, 1.0]
  - Scans career_history description text ONLY (same source as calibration's
    career_ai_infra_hits; NOT skills section, NOT summary)
  - Counts AI_INFRA_TERMS matches (retrieval, ranking, embedding, vector DB, etc.)
  - Normalizes: min(count, 5) / 5.0
  - 0.0 = no AI infrastructure in career roles (framework-only, wrong domain, etc.)
  - 1.0 = 5+ distinct AI infra terms across career history

Why 5 as normalization cap:
  The JD names ~5 distinct required system types (retrieval, vector DB, ranking,
  evaluation, embeddings). Saturation at 5 hits rewards breadth of relevant system
  experience without penalizing specialization.

Weight change:
  skill_overlap:       0.34 -> 0.26  (reduce by 0.08)
  career_evidence:     0.00 -> 0.08  (new term)
  group_overlap:       0.16 (unchanged)
  term_overlap:        0.18 (unchanged)
  experience_fit:      0.12 (unchanged)
  signal_average:      0.20 (unchanged)
  TOTAL:               1.00 ✓

Why fund from skill_overlap:
  The JD explicitly says "The right answer is not find candidates whose skills
  section contains the most AI keywords." skill_overlap is the exact-tag skill
  match — precisely what the JD warns against as the dominant signal.
  Reducing it by 0.08 and moving that weight to career evidence directly
  implements the JD's stated hierarchy.

Double-counting analysis:
  career_evidence_score and calibration both use AI_INFRA_TERMS from career text.
  This is intentional: both are career evidence signals at different granularity.
  The base component rewards presence and breadth (is there career AI infra evidence?).
  The calibration rewards quality depth (did they build AND own AND operate in prod?).
  Safety verified: 0% of trap-flagged candidates have 3+ career_ai_hits.
  Trap candidates with 1 hit get +0.016 from new component; trap penalty is >= 0.020.
  Net impact on false positives: zero.

Phase 8B.3 protections preserved:
  - Domain relevance gate (has_domain_relevant_career) unchanged
  - Trap detection unchanged
  - Calibration ceiling unchanged
  - Reranker headroom logic unchanged
"""
from __future__ import annotations

import csv
import heapq
import sys
from pathlib import Path

# Monkeypatch TOP_K before importing rank (collect 300 candidates for pool)
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
    MAX_EVIDENCE_ADJUSTMENT,
    _calibrated_score,
    _experience_fit,
    _important_terms,
    _ratio,
    configure_offline_environment,
    read_job_text,
    _competition_reasoning,
)
from backend.intelligence.candidate_engine import build_competition_core_signals, build_candidate_intelligence
from backend.parsers.jd_analyzer import analyze_job_description
from backend.competition.validate_submission import validate_submission


# ---------------------------------------------------------------------------
# New: lightweight career evidence score (runs at base-score time, before calibration)
# ---------------------------------------------------------------------------

def _career_evidence_score(profile) -> float:
    """
    Normalized count of JD-relevant AI infrastructure terms found in career history
    text ONLY (not skills section, not summary).

    Returns 0.0 (no AI infrastructure career evidence) to 1.0 (5+ distinct hits).
    This signal answers: 'Did this candidate work on relevant AI systems in their
    career roles?' — not 'Did they list AI tools as skills?'

    Normalization cap of 5 reflects the ~5 distinct system types the JD requires:
    retrieval, vector databases, ranking, embeddings, evaluation infrastructure.
    """
    career_text = normalize_whitespace(
        " ".join(str(item.get("description") or "") for item in profile.career_history)
    ).lower()
    if not career_text:
        return 0.0
    hits = sum(1 for term in AI_INFRA_TERMS if term in career_text)
    return min(hits, 5) / 5.0


# ---------------------------------------------------------------------------
# Modified base score: skill_overlap 0.34 -> 0.26, career_evidence 0.00 -> 0.08
# ---------------------------------------------------------------------------

def _competition_score_c3(profile, core_signals: dict, job_analysis, job_terms: set) -> float:
    """
    Phase 8C.3 base score.

    Change vs Phase 8B.3:
      - skill_overlap weight: 0.34 -> 0.26
      - career_evidence weight: 0.00 -> 0.08 (new first-class signal)

    Rationale: JD says career evidence of building retrieval/ranking systems is
    'absolutely needed', while skill tags are explicitly called 'a trap'. Moving
    0.08 weight from exact skill tag matching to career evidence directly implements
    this priority ordering.
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
        skill_overlap   * 0.26   # was 0.34
        + group_overlap * 0.16
        + term_overlap  * 0.18
        + experience_fit * 0.12
        + signal_average * 0.20
        + career_evidence * 0.08  # new: JD-relevant career system evidence
    )
    return round(max(0.0, min(1.0, score)), 6)


# ---------------------------------------------------------------------------
# Full ranking run with new base score + Phase 8B.3 calibration + reranker
# ---------------------------------------------------------------------------

def run_phase8c3(candidates_path: str, job_path: str, output_path: str) -> None:
    print("Phase 8C.3: Running base ranking with career evidence in base score...")
    configure_offline_environment()
    job_text = read_job_text(job_path)
    job_analysis = analyze_job_description(job_text)
    job_terms = _important_terms(job_text)

    top_candidates: list = []
    seen: set = set()

    for raw in iter_dataset_records(candidates_path):
        p = adapt_redrob_candidate(raw)
        if not p.candidate_id or p.candidate_id in seen:
            continue
        seen.add(p.candidate_id)
        core = build_competition_core_signals(p)
        base = _competition_score_c3(p, core, job_analysis, job_terms)
        # Pre-selection uses the new base score (career evidence participates here)
        if len(top_candidates) >= 300 and base + MAX_EVIDENCE_ADJUSTMENT < top_candidates[0][0]:
            continue
        cal = calibrate_candidate_evidence(p)
        score = _calibrated_score(base, cal)
        c = CompetitionCandidate(
            candidate_id=p.candidate_id,
            score=score,
            base_score=base,
            evidence_adjustment=cal.adjustment,
            calibration=cal,
            profile=p,
        )
        item = (score, c.candidate_id, c)
        if len(top_candidates) < 300:
            heapq.heappush(top_candidates, item)
        elif item > top_candidates[0]:
            heapq.heapreplace(top_candidates, item)

    pool = [item[2] for item in sorted(top_candidates, key=lambda x: (-x[0], x[1]))]
    print(f"  Top-300 pool collected. Loading full profiles...")

    cids_in_pool = {c.candidate_id for c in pool}
    profiles: dict = {}
    for raw in iter_dataset_records(candidates_path):
        cid = raw.get("candidate_id")
        if cid in cids_in_pool:
            profiles[cid] = adapt_redrob_candidate(raw)
            if len(profiles) == len(cids_in_pool):
                break

    print("  Applying Phase 8B.3 reranker (headroom depth + behavioral)...")
    reranked = []
    for c in pool:
        p = profiles[c.candidate_id]
        career_text = normalize_whitespace(
            " ".join(str(i.get("description", "")) for i in p.career_history)
        ).lower()
        career_sigs = _extract_career_signals(career_text)
        beh_sigs = _extract_behavioral_signals(p.redrob_signals or {})

        depth_bonus = _headroom_depth_bonus(c.calibration.adjustment, career_text, career_sigs)
        beh_bonus = (beh_sigs["availability_score"] + beh_sigs["engagement_score"]) * 0.005
        surface_penalty = -0.030 if career_sigs["surface_match_risk"] else 0.0
        trap_penalty = -0.050 if c.calibration.trap_flags else 0.0

        rerank_score = c.score + depth_bonus + beh_bonus + surface_penalty + trap_penalty
        reranked.append({
            "candidate_id": c.candidate_id,
            "old_score": c.score,
            "new_score": rerank_score,
            "calibration": c.calibration,
        })

    reranked.sort(key=lambda x: (-x["new_score"], x["candidate_id"]))
    top100 = reranked[:100]

    print("  Generating reasoning for top 100...")
    for item in top100:
        p = profiles[item["candidate_id"]]
        _, evidence_library = build_candidate_intelligence(p)
        item["reasoning"] = _competition_reasoning(
            p, job_analysis, evidence_library, item["calibration"]
        )

    # Write CSV directly — do NOT use write_submission_csv which validates len==TOP_K
    # (TOP_K is monkeypatched to 300 for pool collection above).
    output = Path(output_path)
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["candidate_id", "rank", "score", "reasoning"])
        writer.writeheader()
        for rank_pos, item in enumerate(top100, start=1):
            writer.writerow({
                "candidate_id": item["candidate_id"],
                "rank": rank_pos,
                "score": f"{item['new_score']:.6f}",
                "reasoning": item["reasoning"],
            })
    errors = validate_submission(output_path)
    if errors:
        raise ValueError("Invalid submission: " + " ".join(errors))
    print(f"  Written valid submission to {output_path}")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Phase 8C.3 career evidence experiment.")
    parser.add_argument("--candidates", default="data/candidates.jsonl")
    parser.add_argument("--job", default="data/job_description.docx")
    parser.add_argument("--output", default="submission_phase8c3.csv")
    args = parser.parse_args()
    run_phase8c3(args.candidates, args.job, args.output)


if __name__ == "__main__":
    main()
