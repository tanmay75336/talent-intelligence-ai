"""
Phase 8C.4 — Production Ownership Disclaimer Detection

Diagnosis from Phase 8C.3 merge audit (outputs/phase8c3_merge_audit.md)
and Phase 8C.4 validation:

CONFIRMED GENERAL ISSUE:
  10 candidates contain explicit self-reported language stating that they
  did NOT own production deployment:
    "pure ml side of the work; production deployment was handled by the platform team"
  
  These candidates still receive:
    A) career_evidence_score = 0.6 in base score (have 'ranking'/'recommendation'/'inference')
    B) calibration bonus "production ownership is backed by work history" (+0.008–0.024)
       because PRODUCTION_TERMS counts the word 'production' even when the sentence
       says 'production deployment was handled by [others]'
  
  Combined, these candidates rank 59–99 despite explicitly disclaiming production
  ownership — which the JD calls "absolutely needed" (item 1).

WHAT THE JD SAYS:
  "Production experience with embeddings-based retrieval systems... we care that
  you've handled embedding drift, index refresh, retrieval-quality regression in
  production." (Item 1, "Things you absolutely need")
  
  "If you've spent your career in pure research environments without any production
  deployment — we will not move forward." (Disqualifier 1)
  
  A candidate who explicitly says "production deployment was handled by the platform
  team" is self-reporting a disqualifier. The JD is unambiguous about this.

WHAT CHANGED vs PHASE 8C.3:
  One addition to _career_evidence_score():
  
  If career text contains EXPLICIT PRODUCTION DISCLAIMER phrases:
    "production deployment was handled by"
    "pure ml side of the work"
    "deployment was handled by the platform"
    "production was handled by"
    "ops team handled"
  
  Then career_evidence_score is reduced by 50% (multiplied by 0.5).
  
  Why 0.5 (not 0.0)?
    The candidate may still have some career evidence of building ML systems
    (collaborative filtering, re-ranking models). Zero would be too aggressive.
    0.5 ensures they remain in scope but no longer outrank candidates who
    genuinely owned production systems end-to-end.
  
  Why not fix the calibration bonus?
    That is a deeper, separate issue. The production_hits counter is context-blind.
    Fixing it would require sentence-level production context analysis — a larger
    change than warranted here. The base score correction is sufficient to address
    the ordering issue without destabilizing calibration behavior.
  
  Why not hardcode these candidates?
    The fix is on a general phrase pattern, not on candidate IDs or companies.
    Any candidate whose career text contains this specific disclaimer language
    receives the 0.5 multiplier — regardless of who they are.

PHASE 8B.3 PROTECTIONS:
  All Phase 8B.3 and 8C.3 protections unchanged.
  No calibration modified.
  No reranker modified.
  No weights changed.
"""
from __future__ import annotations

import csv
import heapq
import sys
from pathlib import Path

# Monkeypatch TOP_K before importing rank
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
# Production ownership disclaimer phrases — derived from JD language
# "Things you absolutely need: handled... retrieval-quality regression in production"
# These phrases indicate the candidate is self-reporting they did NOT own production.
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

_PROD_DISCLAIMER_MULTIPLIER: float = 0.5  # reduce career_evidence_score by half


def _career_evidence_score(profile) -> float:
    """
    Normalized count of JD-relevant AI infrastructure terms found in career history
    text ONLY (same source as calibration's career_ai_infra_hits).

    Phase 8C.4 addition:
      If career text contains explicit production ownership disclaimer language
      (candidate self-reports that production deployment was NOT their responsibility),
      the score is multiplied by 0.5.

      Rationale: The JD requires "handled embedding drift, index refresh,
      retrieval-quality regression in production." A candidate who explicitly
      says "production deployment was handled by the platform team" is
      self-reporting the absence of this requirement.

      The multiplier is 0.5 (not 0.0) because the candidate may still have
      career evidence of building the ML/ranking layer — just not the production
      operations piece. They remain in scope but no longer outrank candidates
      who owned the full stack.
    """
    career_text = normalize_whitespace(
        " ".join(str(item.get("description") or "") for item in profile.career_history)
    ).lower()
    if not career_text:
        return 0.0
    hits = sum(1 for term in AI_INFRA_TERMS if term in career_text)
    base_score = min(hits, 5) / 5.0
    # Apply disclaimer multiplier if candidate explicitly disclaims production ownership
    if any(phrase in career_text for phrase in _PROD_DISCLAIMER_PHRASES):
        base_score *= _PROD_DISCLAIMER_MULTIPLIER
    return base_score


def _competition_score_c4(profile, core_signals: dict, job_analysis, job_terms: set) -> float:
    """
    Phase 8C.4 base score. Identical to 8C.3 except _career_evidence_score()
    now applies a 0.5 multiplier when explicit production ownership disclaimers
    are detected in career text.
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


def run_phase8c4(candidates_path: str, job_path: str, output_path: str) -> None:
    print("Phase 8C.4: Running with production disclaimer detection...")
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
        base = _competition_score_c4(p, core, job_analysis, job_terms)
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

    print("  Applying Phase 8B.3 reranker...")
    reranked = []
    for c in pool:
        p = profiles[c.candidate_id]
        career_text = normalize_whitespace(
            " ".join(str(i.get("description", "")) for i in p.career_history)
        ).lower()
        career_sigs = _extract_career_signals(career_text)
        beh_sigs = _extract_behavioral_signals(p.redrob_signals or {})

        depth_bonus    = _headroom_depth_bonus(c.calibration.adjustment, career_text, career_sigs)
        beh_bonus      = (beh_sigs["availability_score"] + beh_sigs["engagement_score"]) * 0.005
        surface_penalty = -0.030 if career_sigs["surface_match_risk"] else 0.0
        trap_penalty    = -0.050 if c.calibration.trap_flags else 0.0

        reranked.append({
            "candidate_id": c.candidate_id,
            "old_score":    c.score,
            "new_score":    c.score + depth_bonus + beh_bonus + surface_penalty + trap_penalty,
            "calibration":  c.calibration,
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

    output = Path(output_path)
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["candidate_id", "rank", "score", "reasoning"])
        writer.writeheader()
        for rank_pos, item in enumerate(top100, start=1):
            writer.writerow({
                "candidate_id": item["candidate_id"],
                "rank":         rank_pos,
                "score":        f"{item['new_score']:.6f}",
                "reasoning":    item["reasoning"],
            })

    errors = validate_submission(output_path)
    if errors:
        raise ValueError("Invalid submission: " + " ".join(errors))
    print(f"  Written valid submission to {output_path}")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Phase 8C.4 production disclaimer experiment.")
    parser.add_argument("--candidates", default="data/candidates.jsonl")
    parser.add_argument("--job",        default="data/job_description.docx")
    parser.add_argument("--output",     default="submission_phase8c4.csv")
    args = parser.parse_args()
    run_phase8c4(args.candidates, args.job, args.output)


if __name__ == "__main__":
    main()
