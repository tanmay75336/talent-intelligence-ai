from __future__ import annotations

import logging
import os
from pathlib import Path

from backend.storage.repositories import (
    CandidateRepository,
    EvidenceRepository,
    JobRepository,
    RankingResultRepository,
    RankingRunRepository,
)

logger = logging.getLogger(__name__)


def persist_ranked_workflow(
    jd_text: str,
    job_intelligence: dict,
    ranked_candidates: list[dict],
    db_path: str | Path | None = None,
) -> dict:
    job_repo = JobRepository(db_path)
    candidate_repo = CandidateRepository(db_path)
    run_repo = RankingRunRepository(db_path)
    result_repo = RankingResultRepository(db_path)
    evidence_repo = EvidenceRepository(db_path)

    job = job_repo.create_job(
        role_title=job_intelligence.get("role_title", "Untitled role"),
        jd_text=jd_text,
        job_intelligence=job_intelligence,
    )
    run = run_repo.create_run(
        job_id=job["id"],
        rerank_enabled=_env_bool("ENABLE_LLM_RERANK", False),
        embeddings_enabled=_env_bool("ENABLE_EMBEDDINGS", True),
        retrieval_enabled=True,
    )

    for index, ranked_candidate in enumerate(ranked_candidates, start=1):
        storage_payload = ranked_candidate.get("_storage", {})
        candidate = candidate_repo.create_candidate(
            candidate_name=ranked_candidate.get("candidate_name", "Unknown Candidate"),
            resume_text=storage_payload.get("resume_text", ""),
            candidate_intelligence=ranked_candidate.get("candidate_intelligence", {}),
        )
        result_repo.save_result(
            run_id=run["id"],
            candidate_id=candidate["id"],
            ranking_result=ranked_candidate.get("ranking", {}),
            rank_position=index,
        )
        evidence_repo.save_evidence_metadata(
            run_id=run["id"],
            candidate_id=candidate["id"],
            evidence_items=_extract_evidence_items(ranked_candidate.get("ranking", {})),
        )

    return run


def build_saved_run_results(run_id: str, db_path: str | Path | None = None) -> dict | None:
    run_repo = RankingRunRepository(db_path)
    result_repo = RankingResultRepository(db_path)
    run = run_repo.get_run(run_id)
    if not run:
        return None

    ranked_candidates = []
    for result in result_repo.get_results_for_run(run_id):
        candidate_intelligence = result.get("candidate_intelligence", {})
        ranking = result.get("ranking_result", {})
        ranked_candidates.append(
            {
                "candidate_name": result.get("candidate_name", "Unknown Candidate"),
                "candidate_id": result.get("candidate_id"),
                "candidate_skills": candidate_intelligence.get("normalized_skills", ranking.get("matched_skills", [])),
                "candidate_intelligence": candidate_intelligence,
                "ranking": ranking,
            }
        )

    return {
        "ranking_run_id": run["id"],
        "run": run,
        "total_candidates": len(ranked_candidates),
        "ranked_candidates": ranked_candidates,
        "job_intelligence": run.get("job_intelligence", {}),
    }


def build_saved_run_comparison(run_id: str, db_path: str | Path | None = None) -> dict | None:
    saved_results = build_saved_run_results(run_id, db_path=db_path)
    if not saved_results:
        return None

    ranked_candidates = saved_results.get("ranked_candidates", [])
    if len(ranked_candidates) < 2:
        return {
            "ranking_run_id": run_id,
            "comparison": None,
            "message": "At least two saved candidates are required for comparison.",
        }

    left = ranked_candidates[0]
    right = ranked_candidates[1]
    left_ranking = left.get("ranking", {})
    right_ranking = right.get("ranking", {})
    winner = left if left_ranking.get("final_score", 0.0) >= right_ranking.get("final_score", 0.0) else right
    loser = right if winner is left else left

    return {
        "ranking_run_id": run_id,
        "comparison": {
            "winner": winner.get("candidate_name", "Unknown Candidate"),
            "loser": loser.get("candidate_name", "Unknown Candidate"),
            "winner_summary": winner.get("ranking", {}).get("recruiter_decision_summary", ""),
            "loser_summary": loser.get("ranking", {}).get("recruiter_decision_summary", ""),
            "winner_strengths": winner.get("ranking", {}).get("strengths", [])[:3],
            "loser_risks": loser.get("ranking", {}).get("risks", [])[:3],
            "score_delta": round(
                abs(
                    winner.get("ranking", {}).get("final_score", 0.0)
                    - loser.get("ranking", {}).get("final_score", 0.0)
                ),
                2,
            ),
        },
    }


def public_ranked_candidates(ranked_candidates: list[dict]) -> list[dict]:
    return [{key: value for key, value in candidate.items() if key != "_storage"} for candidate in ranked_candidates]


def _extract_evidence_items(ranking: dict) -> list[dict]:
    evidence_by_pillar = ranking.get("supporting_evidence_snippets", {}) or {}
    seen: set[str] = set()
    evidence_items = []
    for snippets in evidence_by_pillar.values():
        for snippet in snippets or []:
            evidence_id = snippet.get("evidence_id") or ""
            if evidence_id in seen:
                continue
            seen.add(evidence_id)
            evidence_items.append(snippet)
    return evidence_items


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}
