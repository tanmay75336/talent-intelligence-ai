from __future__ import annotations

from dataclasses import dataclass

from backend.intelligence.normalization import infer_evidence_strength
from backend.models.candidate_intelligence import CandidateIntelligence
from backend.models.evidence import EvidenceSnippet
from backend.models.job_intelligence import JobIntelligence
from backend.retrieval.bm25_retriever import SparseRetriever
from backend.retrieval.chunking import RetrievalChunk
from backend.retrieval.deduplication import dedupe_by_chunk_id, diversify_chunks
from backend.retrieval.rank_fusion import reciprocal_rank_fusion
from backend.retrieval.vector_store import RetrievedChunk, VectorStore

PILLAR_QUERY_BUILDERS = {
    "semantic_fit": lambda job: [
        job.role_title,
        *job.responsibilities[:3],
        ", ".join(job.explicit_skills[:8]),
    ],
    "technical_depth": lambda job: [
        "technical implementation depth",
        ", ".join(job.explicit_skills[:8]),
        *job.responsibilities[:2],
    ],
    "ownership": lambda job: [
        "ownership end-to-end delivery built led deployed",
        *job.responsibilities[:2],
    ],
    "execution_maturity": lambda job: [
        "shipped production deployed integrations platform delivery",
        *job.responsibilities[:2],
    ],
    "learning_velocity": lambda job: [
        "rapid learning adaptable complex projects hackathon growth",
        job.role_title,
    ],
    "startup_readiness": lambda job: [
        "startup ownership ambiguity breadth shipping",
        job.role_title,
        job.startup_vs_enterprise,
    ],
    "transferability": lambda job: [
        "adjacent technologies similar architecture ecosystem overlap transferable skills",
        ", ".join(job.explicit_skills[:8]),
    ],
    "communication": lambda job: [
        "communication collaboration stakeholder explanation demo",
        job.role_title,
    ],
    "domain_relevance": lambda job: [
        " ".join(job.domains[:8]),
        job.role_title,
    ],
}

PILLAR_CHUNK_PRIORITIES = {
    "semantic_fit": {"project": 1.0, "experience": 0.96, "summary": 0.8, "skills": 0.7},
    "technical_depth": {"project": 1.0, "experience": 0.95, "skills": 0.82, "summary": 0.7},
    "ownership": {"project": 1.0, "experience": 0.98, "summary": 0.75},
    "execution_maturity": {"project": 1.0, "experience": 0.98, "skills": 0.7},
    "learning_velocity": {"project": 1.0, "summary": 0.85, "education": 0.8},
    "startup_readiness": {"project": 1.0, "experience": 0.95, "summary": 0.82},
    "transferability": {"project": 1.0, "experience": 0.95, "skills": 0.86, "summary": 0.75},
    "communication": {"summary": 1.0, "experience": 0.8, "project": 0.7},
    "domain_relevance": {"project": 1.0, "experience": 0.9, "summary": 0.82},
}


PILLAR_SIGNAL_TERMS = {
    "ownership": ("owned", "led", "built", "delivered", "launched", "end-to-end", "architected"),
    "execution_maturity": ("deployed", "production", "shipped", "integrated", "ci/cd", "monitoring", "scalable"),
    "technical_depth": ("architecture", "implementation", "api", "database", "synchronization", "pipeline"),
    "startup_readiness": ("launched", "owned", "rapid", "mvp", "built", "shipped", "ambiguous"),
    "transferability": ("synchronization", "realtime", "real-time", "event", "architecture", "platform", "deployment"),
    "domain_relevance": ("domain", "platform", "workflow", "analytics", "automation"),
}

CONCEPT_EXPANSIONS = {
    "realtime": "multiplayer live bidding synchronization websocket event streams pubsub rooms realtime updates",
    "real-time": "multiplayer live bidding synchronization websocket event streams pubsub rooms realtime updates",
    "backend": "api services backend orchestration database auth integrations queues services",
    "scalable": "distributed systems concurrency caching load production architecture",
    "cloud": "aws render railway vercel docker ci/cd deployment production monitoring",
    "deployment": "aws render railway vercel docker ci/cd deployment production monitoring",
    "llm": "large language models embeddings vector database semantic search rag retrieval chroma",
    "embedding": "embeddings vector database semantic search rag retrieval chroma",
    "semantic retrieval": "embeddings vector database semantic search rag retrieval chroma",
}


def _query_texts_for_pillar(job: JobIntelligence, pillar: str) -> list[str]:
    builder = PILLAR_QUERY_BUILDERS.get(pillar, PILLAR_QUERY_BUILDERS["semantic_fit"])
    queries = [text for text in builder(job) if text and text.strip()]
    job_text = " ".join(
        [
            job.role_title,
            " ".join(job.explicit_skills),
            " ".join(job.responsibilities),
            " ".join(job.domains),
        ]
    ).lower()
    for trigger, expansion in CONCEPT_EXPANSIONS.items():
        if trigger in job_text:
            queries.append(expansion)
            if pillar == "transferability":
                queries.append(f"transferable adjacent capability: {expansion}")
    if job.explicit_skills:
        queries.append("explicit must-have skills: " + ", ".join(job.explicit_skills[:10]))
    return queries


def _weighted_score(chunk: RetrievedChunk, pillar: str) -> float:
    priority = PILLAR_CHUNK_PRIORITIES.get(pillar, {}).get(chunk.chunk_type, 0.72)
    dense_score = float(chunk.metadata.get("dense_score", 0.0) or 0.0)
    sparse_score = float(chunk.metadata.get("sparse_score", 0.0) or 0.0)
    fused_score = float(chunk.metadata.get("fused_score", chunk.retrieval_score) or 0.0)
    strength = infer_evidence_strength(chunk.text)
    strength_factor = {"high": 1.12, "medium": 1.0, "low": 0.82}[strength]
    specificity = {
        "project": 1.0,
        "experience": 0.95,
        "skills": 0.62,
        "summary": 0.68,
        "education": 0.58,
        "certifications": 0.62,
    }.get(chunk.chunk_type, 0.64)
    recency = _recency_factor(chunk)
    signal = _pillar_signal_multiplier(chunk.text, pillar)
    score = (
        (fused_score * 0.42)
        + (dense_score * 0.24)
        + (sparse_score * 0.18)
        + (priority * 0.10)
        + (specificity * 0.06)
    )
    return round(max(0.0, min(1.0, score * strength_factor * recency * signal)), 4)


def _recency_factor(chunk: RetrievedChunk) -> float:
    index = chunk.metadata.get("index")
    if not isinstance(index, int | float):
        return 1.0
    if index <= 0:
        return 1.04
    if index == 1:
        return 1.0
    return 0.96


def _pillar_signal_multiplier(text: str, pillar: str) -> float:
    terms = PILLAR_SIGNAL_TERMS.get(pillar, ())
    lowered = text.lower()
    matched = sum(1 for term in terms if term in lowered)
    if matched >= 3:
        return 1.1
    if matched >= 1:
        return 1.05
    if pillar in {"ownership", "execution_maturity"} and "skills" in lowered:
        return 0.9
    return 1.0


def _retrieval_debug_rows(chunks: list[RetrievedChunk]) -> list[dict[str, str | float]]:
    return [
        {
            "chunk_id": chunk.chunk_id,
            "source_label": chunk.source_label,
            "chunk_type": chunk.chunk_type,
            "score": round(chunk.retrieval_score, 4),
            "dense_score": round(float(chunk.metadata.get("dense_score", 0.0) or 0.0), 4),
            "sparse_score": round(float(chunk.metadata.get("sparse_score", 0.0) or 0.0), 4),
            "fused_score": round(float(chunk.metadata.get("fused_score", chunk.retrieval_score) or 0.0), 4),
        }
        for chunk in chunks
    ]


def _must_have_coverage(
    explicit_skills: list[str],
    candidate_chunks: list[RetrievalChunk],
    sparse_retriever: SparseRetriever,
    candidate_namespace: str,
    candidate_id: str,
) -> dict[str, float]:
    coverage: dict[str, float] = {}
    candidate_text = " ".join(chunk.text.lower() for chunk in candidate_chunks)
    for skill in explicit_skills:
        lowered = skill.lower().strip()
        if not lowered:
            continue
        if lowered in candidate_text:
            coverage[skill] = 1.0
            continue
        sparse_hits = sparse_retriever.query(
            candidate_namespace,
            [skill],
            top_k=3,
            where={"document_id": candidate_id},
        )
        best_sparse = max((hit.retrieval_score for hit in sparse_hits), default=0.0)
        coverage[skill] = round(0.75 if best_sparse >= 0.08 else best_sparse, 4)
    return coverage


def _suppression_diagnostics(must_have_coverage: dict[str, float]) -> dict[str, str | float | list[str]]:
    if not must_have_coverage:
        return {"penalty": 0.0, "reason": "no_explicit_must_haves", "missing": []}
    weak = [skill for skill, score in must_have_coverage.items() if score < 0.2]
    weak_ratio = len(weak) / len(must_have_coverage)
    penalty = min(0.18, weak_ratio * 0.18)
    reason = "explicit_must_have_coverage_weak" if penalty else "must_haves_covered"
    return {"penalty": round(penalty, 4), "reason": reason, "missing": weak}


@dataclass
class RetrievalContext:
    candidate_id: str
    job_id: str
    candidate_chunks: list[RetrievalChunk]
    job_chunks: list[RetrievalChunk]
    pillar_evidence: dict[str, list[EvidenceSnippet]]
    pillar_scores: dict[str, list[float]]
    must_have_coverage: dict[str, float]
    diagnostics: dict[str, object]


class EvidenceRetriever:
    def __init__(self, vector_store: VectorStore, sparse_retriever: SparseRetriever | None = None):
        self.vector_store = vector_store
        self.sparse_retriever = sparse_retriever or SparseRetriever()

    def index_documents(
        self,
        job_namespace: str,
        candidate_namespace: str,
        job_chunks: list[RetrievalChunk],
        candidate_chunks: list[RetrievalChunk],
        job_id: str,
        candidate_id: str,
    ) -> None:
        self.vector_store.delete_document_chunks(job_namespace, job_id)
        self.vector_store.delete_document_chunks(candidate_namespace, candidate_id)
        self.vector_store.upsert_chunks(job_namespace, job_chunks)
        self.vector_store.upsert_chunks(candidate_namespace, candidate_chunks)
        self.sparse_retriever.delete_document_chunks(job_namespace, job_id)
        self.sparse_retriever.delete_document_chunks(candidate_namespace, candidate_id)
        self.sparse_retriever.upsert_chunks(job_namespace, job_chunks)
        self.sparse_retriever.upsert_chunks(candidate_namespace, candidate_chunks)

    def retrieve_for_candidate(
        self,
        job: JobIntelligence,
        candidate: CandidateIntelligence,
        job_chunks: list[RetrievalChunk],
        candidate_chunks: list[RetrievalChunk],
        job_namespace: str,
        candidate_namespace: str,
        candidate_id: str,
        job_id: str,
    ) -> RetrievalContext:
        pillar_evidence: dict[str, list[EvidenceSnippet]] = {}
        pillar_scores: dict[str, list[float]] = {}
        diagnostics: dict[str, object] = {"pillars": {}}
        must_have_coverage = _must_have_coverage(
            job.explicit_skills,
            candidate_chunks,
            self.sparse_retriever,
            candidate_namespace,
            candidate_id,
        )
        diagnostics["must_have_coverage"] = must_have_coverage
        diagnostics["must_have_suppression"] = _suppression_diagnostics(must_have_coverage)

        for pillar in PILLAR_QUERY_BUILDERS:
            query_texts = _query_texts_for_pillar(job, pillar)
            dense_results = self.vector_store.query(
                candidate_namespace,
                query_texts,
                top_k=8,
                where={"document_id": candidate_id},
            )
            sparse_results = self.sparse_retriever.query(
                candidate_namespace,
                query_texts,
                top_k=8,
                where={"document_id": candidate_id},
            )
            dense_results = dedupe_by_chunk_id(dense_results)
            sparse_results = dedupe_by_chunk_id(sparse_results)
            fused_results = reciprocal_rank_fusion(
                {"dense": dense_results, "sparse": sparse_results},
                top_k=10,
            )
            fused_results.sort(key=lambda item: _weighted_score(item, pillar), reverse=True)
            diversity_result = diversify_chunks(
                fused_results,
                limit=3,
                max_per_source_label=2 if pillar in {"technical_depth", "semantic_fit"} else 1,
            )
            candidate_results = diversity_result.selected

            pillar_scores[pillar] = [_weighted_score(item, pillar) for item in candidate_results]
            pillar_evidence[pillar] = [
                EvidenceSnippet(
                    evidence_id=item.chunk_id,
                    source_type=item.chunk_type if item.chunk_type in {"project", "experience", "summary", "skills", "education", "jd"} else "summary",
                    source_label=item.source_label,
                    snippet=item.text,
                    evidence_strength=infer_evidence_strength(item.text, item.chunk_type),
                    retrieval_score=round(_weighted_score(item, pillar), 4),
                )
                for item in candidate_results
            ]
            diagnostics["pillars"][pillar] = {
                "queries": query_texts,
                "dense_rankings": _retrieval_debug_rows(dense_results),
                "sparse_rankings": _retrieval_debug_rows(sparse_results),
                "fused_rankings": _retrieval_debug_rows(fused_results),
                "selected_evidence": _retrieval_debug_rows(candidate_results),
                "suppressed_evidence": diversity_result.suppressed,
            }

        return RetrievalContext(
            candidate_id=candidate_id,
            job_id=job_id,
            candidate_chunks=candidate_chunks,
            job_chunks=job_chunks,
            pillar_evidence=pillar_evidence,
            pillar_scores=pillar_scores,
            must_have_coverage=must_have_coverage,
            diagnostics=diagnostics,
        )
