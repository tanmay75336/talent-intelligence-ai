import logging
import re
from pathlib import Path

from backend.intelligence.candidate_engine import build_candidate_intelligence
from backend.intelligence.jd_engine import build_job_intelligence
from backend.parsers.jd_analyzer import analyze_job_description
from backend.parsers.resume_parser import build_candidate_profile, extract_text_from_pdf
from backend.retrieval.chunking import chunk_candidate_profile, chunk_job_intelligence
from backend.reasoning.differentiation import apply_candidate_differentiation
from backend.reasoning.explanation_builder import annotate_ranked_order, build_ranking_result
from backend.reasoning.groq_synthesis import apply_optional_groq_synthesis
from backend.reasoning.ranking_trust import apply_ranking_trust_analysis, apply_recruiter_validation
from backend.ranking.scoring_engine import score_candidate_profile

logger = logging.getLogger(__name__)

_VECTOR_STORE = None


def _safe_identifier(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value or "").strip("_").lower()
    return cleaned or "document"


def _get_evidence_retriever():
    global _VECTOR_STORE
    if _VECTOR_STORE is None:
        from backend.retrieval.chroma_store import ChromaVectorStore
        _VECTOR_STORE = ChromaVectorStore()
    from backend.retrieval.evidence_retriever import EvidenceRetriever
    return EvidenceRetriever(_VECTOR_STORE)


def _validate_non_empty_text(text, label):
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError(f"{label} is empty or unreadable.")

    return cleaned


def build_jd_analysis(jd_text):
    cleaned_jd_text = _validate_non_empty_text(jd_text, "Job description")
    return analyze_job_description(cleaned_jd_text)


def build_jd_intelligence(jd_text):
    cleaned_jd_text = _validate_non_empty_text(jd_text, "Job description")
    return build_job_intelligence(cleaned_jd_text)


def rank_candidate_text(resume_text, jd_text, source_name=""):
    jd_analysis = build_jd_analysis(jd_text)
    jd_intelligence = build_jd_intelligence(jd_text)
    cleaned_resume_text = _validate_non_empty_text(resume_text, "Resume text")
    candidate_profile = build_candidate_profile(
        cleaned_resume_text,
        source_name=source_name,
    )
    candidate_intelligence, evidence_library = build_candidate_intelligence(candidate_profile)
    retrieval_context = None
    try:
        job_id = _safe_identifier(jd_intelligence.role_title)
        candidate_id = _safe_identifier(source_name or candidate_profile.name)
        job_chunks = chunk_job_intelligence(job_id, jd_intelligence)
        candidate_chunks = chunk_candidate_profile(candidate_id, candidate_profile, candidate_intelligence)
        retriever = _get_evidence_retriever()
        retriever.index_documents(
            "job_chunks",
            "candidate_chunks",
            job_chunks,
            candidate_chunks,
            job_id=job_id,
            candidate_id=candidate_id,
        )
        retrieval_context = retriever.retrieve_for_candidate(
            jd_intelligence,
            candidate_intelligence,
            job_chunks,
            candidate_chunks,
            "job_chunks",
            "candidate_chunks",
            candidate_id=candidate_id,
            job_id=job_id,
        )
    except Exception as error:
        logger.warning("Retrieval enrichment unavailable for %s: %s", candidate_profile.name, error)

    raw_ranking = score_candidate_profile(candidate_profile, jd_analysis, retrieval_context=retrieval_context)
    ranking = build_ranking_result(
        candidate_profile,
        jd_intelligence,
        candidate_intelligence,
        raw_ranking,
        evidence_library,
        retrieval_context=retrieval_context,
    ).model_dump()
    _log_ranking_result(candidate_profile.name, source_name, ranking)

    return {
        "candidate_name": candidate_profile.name,
        "resume_file": source_name,
        "candidate_skills": candidate_profile.skills,
        "candidate_intelligence": candidate_intelligence.model_dump(),
        "ranking": ranking,
        "job_intelligence": jd_intelligence.model_dump(),
    }


def rank_candidate_file(file_path, jd_analysis, jd_intelligence):
    path = Path(file_path)
    resume_text = extract_text_from_pdf(path)
    cleaned_resume_text = _validate_non_empty_text(
        resume_text,
        f"Extracted resume text from {path.name}",
    )
    candidate_profile = build_candidate_profile(
        cleaned_resume_text,
        source_name=path.name,
    )
    candidate_intelligence, evidence_library = build_candidate_intelligence(candidate_profile)
    retrieval_context = None
    try:
        job_id = _safe_identifier(jd_intelligence.role_title)
        candidate_id = _safe_identifier(path.name or candidate_profile.name)
        job_chunks = chunk_job_intelligence(job_id, jd_intelligence)
        candidate_chunks = chunk_candidate_profile(candidate_id, candidate_profile, candidate_intelligence)
        retriever = _get_evidence_retriever()
        retriever.index_documents(
            "job_chunks",
            "candidate_chunks",
            job_chunks,
            candidate_chunks,
            job_id=job_id,
            candidate_id=candidate_id,
        )
        retrieval_context = retriever.retrieve_for_candidate(
            jd_intelligence,
            candidate_intelligence,
            job_chunks,
            candidate_chunks,
            "job_chunks",
            "candidate_chunks",
            candidate_id=candidate_id,
            job_id=job_id,
        )
    except Exception as error:
        logger.warning("Retrieval enrichment unavailable for %s: %s", candidate_profile.name, error)

    raw_ranking = score_candidate_profile(candidate_profile, jd_analysis, retrieval_context=retrieval_context)
    ranking = build_ranking_result(
        candidate_profile,
        jd_intelligence,
        candidate_intelligence,
        raw_ranking,
        evidence_library,
        retrieval_context=retrieval_context,
    ).model_dump()
    _log_ranking_result(candidate_profile.name, path.name, ranking)

    return {
        "candidate_name": candidate_profile.name,
        "resume_file": path.name,
        "candidate_skills": candidate_profile.skills,
        "candidate_intelligence": candidate_intelligence.model_dump(),
        "ranking": ranking,
        "_storage": {
            "resume_text": cleaned_resume_text,
        },
    }


def rank_resume_files(file_paths, jd_text, return_errors=False):
    ranked_candidates = []
    processing_errors = []
    jd_analysis = build_jd_analysis(jd_text)
    jd_intelligence = build_jd_intelligence(jd_text)

    for file_path in file_paths:
        try:
            ranked_candidates.append(rank_candidate_file(file_path, jd_analysis, jd_intelligence))
        except Exception as error:
            error_message = f"Error processing {file_path}: {error}"
            logger.exception(error_message)
            processing_errors.append(error_message)

    ranked_candidates.sort(
        key=lambda candidate: candidate["ranking"]["final_score"],
        reverse=True,
    )
    apply_ranking_trust_analysis(ranked_candidates)
    apply_candidate_differentiation(ranked_candidates)
    apply_recruiter_validation(ranked_candidates)
    apply_optional_groq_synthesis(ranked_candidates, processing_errors=processing_errors)
    annotate_ranked_order(ranked_candidates)

    if return_errors:
        return ranked_candidates, processing_errors, jd_intelligence.model_dump()

    return ranked_candidates


def _log_ranking_result(candidate_name, source_name, ranking):
    diagnostics = ranking.get("scoring_diagnostics", {})
    raw_scores = diagnostics.get("raw_scores", {})

    logger.info(
        "Ranked candidate '%s' from '%s' | final=%s semantic=%s raw_semantic=%s keyword=%s",
        candidate_name,
        source_name or "inline_text",
        ranking.get("final_score"),
        ranking.get("semantic_score"),
        raw_scores.get("semantic_score_raw"),
        ranking.get("keyword_score"),
    )
