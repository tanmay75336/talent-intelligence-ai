from __future__ import annotations

import sqlite3


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        role_title TEXT NOT NULL,
        jd_text TEXT NOT NULL,
        job_intelligence_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS candidates (
        id TEXT PRIMARY KEY,
        candidate_name TEXT NOT NULL,
        resume_text TEXT NOT NULL,
        candidate_intelligence_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ranking_runs (
        id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL,
        rerank_enabled INTEGER NOT NULL DEFAULT 0,
        embeddings_enabled INTEGER NOT NULL DEFAULT 1,
        retrieval_enabled INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ranking_results (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        candidate_id TEXT NOT NULL,
        final_score REAL NOT NULL,
        recommendation TEXT NOT NULL,
        recruiter_confidence TEXT NOT NULL,
        hidden_gem_flag INTEGER NOT NULL DEFAULT 0,
        ranking_result_json TEXT NOT NULL,
        rank_position INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES ranking_runs(id),
        FOREIGN KEY (candidate_id) REFERENCES candidates(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS evidence_metadata (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        candidate_id TEXT NOT NULL,
        chunk_id TEXT NOT NULL,
        source_type TEXT NOT NULL,
        source_label TEXT NOT NULL,
        evidence_strength TEXT NOT NULL,
        retrieval_score REAL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES ranking_runs(id),
        FOREIGN KEY (candidate_id) REFERENCES candidates(id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_ranking_runs_created_at ON ranking_runs(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_ranking_results_run_id ON ranking_results(run_id, rank_position)",
    "CREATE INDEX IF NOT EXISTS idx_evidence_metadata_candidate ON evidence_metadata(candidate_id)",
    "CREATE INDEX IF NOT EXISTS idx_evidence_metadata_run ON evidence_metadata(run_id)",
]


def run_migrations(connection: sqlite3.Connection) -> None:
    for statement in SCHEMA_STATEMENTS:
        connection.execute(statement)
    connection.execute("PRAGMA user_version = 1")
    connection.commit()
