from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from backend.storage.db import get_connection


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id() -> str:
    return uuid4().hex


def _json(data: dict | list | None) -> str:
    return json.dumps(data or {}, ensure_ascii=False, sort_keys=True)


def _loads(value: str | None):
    if not value:
        return {}
    return json.loads(value)


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


class BaseRepository:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = db_path

    def _connect(self):
        return get_connection(self.db_path)

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()


class JobRepository(BaseRepository):
    def create_job(self, role_title: str, jd_text: str, job_intelligence: dict) -> dict:
        job_id = _id()
        created_at = _now()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO jobs (id, role_title, jd_text, job_intelligence_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (job_id, role_title or "Untitled role", jd_text, _json(job_intelligence), created_at),
            )
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        job = _row_to_dict(row)
        if not job:
            return None
        job["job_intelligence"] = _loads(job.pop("job_intelligence_json"))
        return job

    def list_jobs(self, limit: int = 25) -> list[dict]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        jobs = []
        for row in rows:
            job = dict(row)
            job["job_intelligence"] = _loads(job.pop("job_intelligence_json"))
            jobs.append(job)
        return jobs


class CandidateRepository(BaseRepository):
    def create_candidate(self, candidate_name: str, resume_text: str, candidate_intelligence: dict) -> dict:
        candidate_id = _id()
        created_at = _now()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO candidates (id, candidate_name, resume_text, candidate_intelligence_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (candidate_id, candidate_name or "Unknown Candidate", resume_text, _json(candidate_intelligence), created_at),
            )
        return self.get_candidate(candidate_id)

    def get_candidate(self, candidate_id: str) -> dict | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        candidate = _row_to_dict(row)
        if not candidate:
            return None
        candidate["candidate_intelligence"] = _loads(candidate.pop("candidate_intelligence_json"))
        return candidate

    def list_candidates(self, limit: int = 50) -> list[dict]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM candidates ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        candidates = []
        for row in rows:
            candidate = dict(row)
            candidate["candidate_intelligence"] = _loads(candidate.pop("candidate_intelligence_json"))
            candidates.append(candidate)
        return candidates


class RankingRunRepository(BaseRepository):
    def create_run(
        self,
        job_id: str,
        rerank_enabled: bool,
        embeddings_enabled: bool,
        retrieval_enabled: bool,
    ) -> dict:
        run_id = _id()
        created_at = _now()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO ranking_runs (id, job_id, rerank_enabled, embeddings_enabled, retrieval_enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, job_id, int(rerank_enabled), int(embeddings_enabled), int(retrieval_enabled), created_at),
            )
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> dict | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT rr.*, j.role_title, j.jd_text, j.job_intelligence_json
                FROM ranking_runs rr
                JOIN jobs j ON j.id = rr.job_id
                WHERE rr.id = ?
                """,
                (run_id,),
            ).fetchone()
        run = _row_to_dict(row)
        if not run:
            return None
        run["rerank_enabled"] = bool(run["rerank_enabled"])
        run["embeddings_enabled"] = bool(run["embeddings_enabled"])
        run["retrieval_enabled"] = bool(run["retrieval_enabled"])
        run["job_intelligence"] = _loads(run.pop("job_intelligence_json"))
        return run

    def list_runs(self, limit: int = 25) -> list[dict]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    rr.*,
                    j.role_title,
                    COUNT(rres.id) AS result_count,
                    MAX(rres.final_score) AS top_score
                FROM ranking_runs rr
                JOIN jobs j ON j.id = rr.job_id
                LEFT JOIN ranking_results rres ON rres.run_id = rr.id
                GROUP BY rr.id
                ORDER BY rr.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        runs = []
        for row in rows:
            run = dict(row)
            run["rerank_enabled"] = bool(run["rerank_enabled"])
            run["embeddings_enabled"] = bool(run["embeddings_enabled"])
            run["retrieval_enabled"] = bool(run["retrieval_enabled"])
            runs.append(run)
        return runs


class RankingResultRepository(BaseRepository):
    def save_result(
        self,
        run_id: str,
        candidate_id: str,
        ranking_result: dict,
        rank_position: int,
    ) -> dict:
        result_id = _id()
        created_at = _now()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO ranking_results (
                    id, run_id, candidate_id, final_score, recommendation, recruiter_confidence,
                    hidden_gem_flag, ranking_result_json, rank_position, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result_id,
                    run_id,
                    candidate_id,
                    float(ranking_result.get("final_score", 0.0)),
                    ranking_result.get("recommendation", "Low Match"),
                    ranking_result.get("recruiter_confidence", "Low"),
                    int(bool(ranking_result.get("hidden_gem_flag", False))),
                    _json(ranking_result),
                    rank_position,
                    created_at,
                ),
            )
        return self.get_result(result_id)

    def get_result(self, result_id: str) -> dict | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM ranking_results WHERE id = ?", (result_id,)).fetchone()
        return self._hydrate_result(row)

    def get_results_for_run(self, run_id: str) -> list[dict]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT r.*, c.candidate_name, c.candidate_intelligence_json
                FROM ranking_results r
                JOIN candidates c ON c.id = r.candidate_id
                WHERE r.run_id = ?
                ORDER BY r.rank_position ASC, r.final_score DESC
                """,
                (run_id,),
            ).fetchall()
        return [self._hydrate_result(row) for row in rows]

    def get_candidate_result(self, run_id: str, candidate_id: str) -> dict | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM ranking_results WHERE run_id = ? AND candidate_id = ?",
                (run_id, candidate_id),
            ).fetchone()
        return self._hydrate_result(row)

    @staticmethod
    def _hydrate_result(row: sqlite3.Row | None) -> dict | None:
        result = _row_to_dict(row)
        if not result:
            return None
        result["hidden_gem_flag"] = bool(result["hidden_gem_flag"])
        result["ranking_result"] = _loads(result.pop("ranking_result_json"))
        if "candidate_intelligence_json" in result:
            result["candidate_intelligence"] = _loads(result.pop("candidate_intelligence_json"))
        return result


class EvidenceRepository(BaseRepository):
    def save_evidence_metadata(self, run_id: str, candidate_id: str, evidence_items: list[dict]) -> None:
        if not evidence_items:
            return
        created_at = _now()
        rows = [
            (
                _id(),
                run_id,
                candidate_id,
                item.get("evidence_id") or item.get("chunk_id") or "",
                item.get("source_type") or "summary",
                item.get("source_label") or "",
                item.get("evidence_strength") or "low",
                item.get("retrieval_score"),
                created_at,
            )
            for item in evidence_items
        ]
        with self._connection() as connection:
            connection.executemany(
                """
                INSERT INTO evidence_metadata (
                    id, run_id, candidate_id, chunk_id, source_type, source_label,
                    evidence_strength, retrieval_score, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def get_candidate_evidence(self, candidate_id: str, run_id: str | None = None) -> list[dict]:
        query = "SELECT * FROM evidence_metadata WHERE candidate_id = ?"
        params: tuple = (candidate_id,)
        if run_id:
            query += " AND run_id = ?"
            params = (candidate_id, run_id)
        query += " ORDER BY created_at ASC"
        with self._connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]
