from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StoredJob:
    id: str
    role_title: str
    jd_text: str
    job_intelligence: dict
    created_at: str


@dataclass(frozen=True)
class StoredCandidate:
    id: str
    candidate_name: str
    resume_text: str
    candidate_intelligence: dict
    created_at: str


@dataclass(frozen=True)
class StoredRankingRun:
    id: str
    job_id: str
    rerank_enabled: bool
    embeddings_enabled: bool
    retrieval_enabled: bool
    created_at: str
