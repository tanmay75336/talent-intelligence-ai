import logging
from pathlib import Path

from backend.parsers.jd_analyzer import analyze_job_description
from backend.parsers.resume_parser import build_candidate_profile, extract_text_from_pdf
from backend.ranking.scoring_engine import score_candidate_profile

logger = logging.getLogger(__name__)


def _validate_non_empty_text(text, label):
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError(f"{label} is empty or unreadable.")

    return cleaned


def build_jd_analysis(jd_text):
    cleaned_jd_text = _validate_non_empty_text(jd_text, "Job description")
    return analyze_job_description(cleaned_jd_text)


def rank_candidate_text(resume_text, jd_text, source_name=""):
    jd_analysis = build_jd_analysis(jd_text)
    cleaned_resume_text = _validate_non_empty_text(resume_text, "Resume text")
    candidate_profile = build_candidate_profile(
        cleaned_resume_text,
        source_name=source_name,
    )
    ranking = score_candidate_profile(candidate_profile, jd_analysis)
    _log_ranking_result(candidate_profile.name, source_name, ranking)

    return {
        "candidate_name": candidate_profile.name,
        "resume_file": source_name,
        "candidate_skills": candidate_profile.skills,
        "ranking": ranking,
    }


def rank_candidate_file(file_path, jd_analysis):
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
    ranking = score_candidate_profile(candidate_profile, jd_analysis)
    _log_ranking_result(candidate_profile.name, path.name, ranking)

    return {
        "candidate_name": candidate_profile.name,
        "resume_file": path.name,
        "candidate_skills": candidate_profile.skills,
        "ranking": ranking,
    }


def rank_resume_files(file_paths, jd_text, return_errors=False):
    ranked_candidates = []
    processing_errors = []
    jd_analysis = build_jd_analysis(jd_text)

    for file_path in file_paths:
        try:
            ranked_candidates.append(rank_candidate_file(file_path, jd_analysis))
        except Exception as error:
            error_message = f"Error processing {file_path}: {error}"
            logger.exception(error_message)
            processing_errors.append(error_message)

    ranked_candidates.sort(
        key=lambda candidate: candidate["ranking"]["final_score"],
        reverse=True,
    )

    if return_errors:
        return ranked_candidates, processing_errors

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
