import logging
import os
import shutil
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from pydantic import BaseModel

from backend.dataset_intelligence.evaluation import compare_ranking_strategies
from backend.dataset_intelligence.loader import load_dataset_bytes
from backend.dataset_intelligence.profiler import profile_dataframe
from backend.intelligence.candidate_engine import build_candidate_intelligence
from backend.intelligence.jd_engine import build_job_intelligence
from backend.parsers.jd_parser import extract_skills_from_jd
from backend.parsers.resume_parser import build_candidate_profile, extract_skills, extract_text_from_pdf
from backend.ranking.pipeline import (
    build_jd_analysis,
    build_jd_intelligence,
    rank_candidate_text,
    rank_resume_files,
)
from backend.reasoning.explanation_builder import build_pairwise_comparison
from backend.reasoning.differentiation import apply_candidate_differentiation
from backend.reasoning.groq_synthesis import apply_optional_groq_synthesis, log_groq_synthesis_startup_status
from backend.reasoning.ranking_trust import apply_ranking_trust_analysis, apply_recruiter_validation
from backend.storage.db import initialize_database
from backend.storage.repositories import JobRepository, RankingRunRepository
from backend.storage.workflows import (
    build_saved_run_comparison,
    build_saved_run_results,
    persist_ranked_workflow,
    public_ranked_candidates,
)
from backend.utils.embeddings import calculate_similarity

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    log_groq_synthesis_startup_status()
    yield


app = FastAPI(lifespan=lifespan)

# Allow frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
DATASET_FOLDER = PROJECT_ROOT / "datasets"

# Create uploads folder if not exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# Request Model
class RankingRequest(BaseModel):
    resumes: list[str]
    jd_text: str


class CandidateCompareInput(BaseModel):
    resume_text: str
    candidate_name: str | None = None


class CandidateCompareRequest(BaseModel):
    jd_text: str
    candidates: list[CandidateCompareInput]


class RankingEvaluationRequest(BaseModel):
    strategies: dict[str, list[str]]
    expected_order: list[str] | None = None
    positive_candidates: list[str] | None = None
    negative_candidates: list[str] | None = None
    hidden_gems: list[str] | None = None
    baseline_strategy: str | None = None


# Home Route
@app.get("/")
def home():

    return {
        "message": "Talent Intelligence AI Backend Running"
    }


def _clamp_limit(limit: int, default: int = 25, maximum: int = 100) -> int:
    if limit <= 0:
        return default
    return min(limit, maximum)


@app.get("/jobs/")
def list_jobs(limit: int = 25):
    return {"jobs": JobRepository().list_jobs(limit=_clamp_limit(limit))}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = JobRepository().get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"job": job}


@app.get("/ranking-runs/")
def list_ranking_runs(limit: int = 25):
    return {"ranking_runs": RankingRunRepository().list_runs(limit=_clamp_limit(limit))}


@app.get("/ranking-runs/{run_id}")
def get_ranking_run(run_id: str):
    run = RankingRunRepository().get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Ranking run not found.")
    return {"run": run}


@app.get("/ranking-runs/{run_id}/results")
def get_ranking_run_results(run_id: str):
    saved_results = build_saved_run_results(run_id)
    if not saved_results:
        raise HTTPException(status_code=404, detail="Ranking run not found.")
    return saved_results


@app.get("/ranking-runs/{run_id}/comparison")
def get_ranking_run_comparison(run_id: str):
    comparison = build_saved_run_comparison(run_id)
    if not comparison:
        raise HTTPException(status_code=404, detail="Ranking run not found.")
    return comparison


@app.post("/dataset/profile/")
async def profile_dataset(file: UploadFile = File(...)):
    try:
        content = await file.read()
        frame = load_dataset_bytes(file.filename or "dataset", content)
        report = profile_dataframe(frame, dataset_name=file.filename or "dataset")
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return report.model_dump()


@app.post("/dataset/evaluate-rankings/")
async def evaluate_rankings(request: RankingEvaluationRequest):
    if not request.strategies:
        raise HTTPException(status_code=422, detail="At least one ranking strategy is required.")
    report = compare_ranking_strategies(
        strategies=request.strategies,
        expected_order=request.expected_order,
        positive_candidates=request.positive_candidates,
        negative_candidates=request.negative_candidates,
        hidden_gems=request.hidden_gems,
        baseline_strategy=request.baseline_strategy,
    )
    return report.model_dump()


# Resume Upload API
@app.post("/upload-resume/")
async def upload_resume(file: UploadFile = File(...)):
    file_path = UPLOAD_FOLDER / file.filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    extracted_text = extract_text_from_pdf(file_path)
    if not extracted_text.strip():
        raise HTTPException(
            status_code=422,
            detail="The uploaded PDF does not contain readable text.",
        )

    candidate_profile = build_candidate_profile(extracted_text, source_name=file.filename)
    candidate_intelligence, evidence_library = build_candidate_intelligence(candidate_profile)
    skills = extract_skills(extracted_text)

    return {
        "filename": file.filename,
        "candidate_name": candidate_profile.name,
        "message": "Resume uploaded successfully",
        "skills_detected": skills,
        "resume_text": extracted_text[:2000],
        "sections_detected": list(candidate_profile.sections.keys()),
        "deployment_signals": candidate_profile.deployment_signals,
        "ai_signals": candidate_profile.ai_signals,
        "candidate_intelligence": candidate_intelligence.model_dump(),
        "evidence_count": len(evidence_library),
    }


# Job Description Upload API
@app.post("/upload-jd/")
async def upload_jd(jd_text: str):
    try:
        jd_analysis = build_jd_analysis(jd_text)
        jd_intelligence = build_jd_intelligence(jd_text)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return {
        "message": "JD processed successfully",
        "required_skills": jd_analysis.required_skills,
        "preferred_skills": jd_analysis.preferred_skills,
        "responsibilities": jd_analysis.responsibilities,
        "domain_keywords": jd_analysis.domain_keywords,
        "seniority_indicators": jd_analysis.seniority_indicators,
        "job_description": jd_text[:2000],
        "job_intelligence": jd_intelligence.model_dump(),
    }


@app.post("/analyze-jd/")
async def analyze_jd_route(jd_text: str):
    try:
        jd_intelligence = build_jd_intelligence(jd_text)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return {
        "message": "JD intelligence generated successfully",
        "job_intelligence": jd_intelligence.model_dump(),
    }


# Candidate Ranking API
@app.post("/rank-candidate/")
async def rank_candidate(
    resume_text: str,
    jd_text: str
):
    try:
        scored_candidate = rank_candidate_text(resume_text, jd_text)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return {
        "candidate_name": scored_candidate["candidate_name"],
        "candidate_skills": scored_candidate["candidate_skills"],
        "jd_skills": extract_skills_from_jd(jd_text),
        "ranking": scored_candidate["ranking"],
        "candidate_intelligence": scored_candidate.get("candidate_intelligence", {}),
        "job_intelligence": scored_candidate.get("job_intelligence", {}),
    }


# Semantic AI Ranking API
@app.post("/semantic-rank/")
async def semantic_rank(
    resume_text: str,
    jd_text: str
):
    if not resume_text.strip():
        raise HTTPException(status_code=422, detail="Resume text is empty or unreadable.")

    if not jd_text.strip():
        raise HTTPException(status_code=422, detail="Job description is empty or unreadable.")

    semantic_score = calculate_similarity(
        resume_text,
        jd_text
    )

    return {
        "semantic_match_score": semantic_score,
        "message": "Semantic ranking completed"
    }


# Multi Candidate Ranking API
@app.post("/rank-multiple-candidates/")
async def rank_multiple_candidates(
    request: RankingRequest
):
    try:
        all_candidates = [
            rank_candidate_text(resume_text, request.jd_text)
            for resume_text in request.resumes
        ]
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    sorted_candidates = sorted(
        all_candidates,
        key=lambda candidate: candidate["ranking"]["final_score"],
        reverse=True,
    )
    apply_ranking_trust_analysis(sorted_candidates)
    apply_candidate_differentiation(sorted_candidates)
    apply_recruiter_validation(sorted_candidates)
    apply_optional_groq_synthesis(sorted_candidates)

    return {
        "total_candidates": len(sorted_candidates),
        "ranked_candidates": sorted_candidates,
        "job_intelligence": sorted_candidates[0].get("job_intelligence", {}) if sorted_candidates else {},
    }


@app.post("/compare-candidates/")
async def compare_candidates(request: CandidateCompareRequest):
    if len(request.candidates) < 2:
        raise HTTPException(status_code=422, detail="At least two candidates are required for comparison.")

    try:
        ranked_candidates = [
            rank_candidate_text(
                candidate.resume_text,
                request.jd_text,
                source_name=candidate.candidate_name or "",
            )
            for candidate in request.candidates[:2]
        ]
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    ranked_candidates.sort(
        key=lambda candidate: candidate["ranking"]["final_score"],
        reverse=True,
    )
    apply_ranking_trust_analysis(ranked_candidates)
    apply_candidate_differentiation(ranked_candidates)
    apply_recruiter_validation(ranked_candidates)

    return {
        "job_intelligence": ranked_candidates[0].get("job_intelligence", {}),
        "candidates": ranked_candidates,
        "comparison": build_pairwise_comparison(ranked_candidates[0], ranked_candidates[1]),
    }

# Upload and Rank Multiple PDFs
@app.post("/upload-and-rank/")
async def upload_and_rank(
    files: list[UploadFile] = File(...),
    jd_text: str = Form(...)
):
    saved_file_paths = []

    for file in files:
        file_path = UPLOAD_FOLDER / file.filename

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        saved_file_paths.append(str(file_path))

    try:
        ranked_candidates, processing_errors, job_intelligence = rank_resume_files(
            saved_file_paths,
            jd_text,
            return_errors=True,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    ranking_run_id = None
    try:
        saved_run = persist_ranked_workflow(jd_text, job_intelligence, ranked_candidates)
        ranking_run_id = saved_run["id"]
    except Exception as error:
        logger.warning("Ranking completed, but persistence failed: %s", error)
        processing_errors.append(f"Ranking completed, but persistence failed: {error}")

    return {
        "total_candidates": len(ranked_candidates),
        "ranked_candidates": public_ranked_candidates(ranked_candidates),
        "processing_errors": processing_errors,
        "job_intelligence": job_intelligence,
        "ranking_run_id": ranking_run_id,
    }

# Rank Dataset Folder
@app.post("/rank-dataset/")
async def rank_dataset(
    jd_text: str
):
    if not DATASET_FOLDER.exists():
        return {
            "dataset_size": 0,
            "ranked_candidates": [],
            "processing_errors": [
                f"Dataset folder not found: {DATASET_FOLDER}"
            ],
        }

    pdf_files = [str(path) for path in DATASET_FOLDER.rglob("*.pdf")]

    try:
        ranked_candidates, processing_errors, job_intelligence = rank_resume_files(
            pdf_files,
            jd_text,
            return_errors=True,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    logger.info("Ranked %s dataset files from %s", len(pdf_files), DATASET_FOLDER)

    ranking_run_id = None
    try:
        saved_run = persist_ranked_workflow(jd_text, job_intelligence, ranked_candidates)
        ranking_run_id = saved_run["id"]
    except Exception as error:
        logger.warning("Dataset ranking completed, but persistence failed: %s", error)
        processing_errors.append(f"Ranking completed, but persistence failed: {error}")

    return {
        "dataset_size": len(pdf_files),
        "ranked_candidates": public_ranked_candidates(ranked_candidates),
        "processing_errors": processing_errors,
        "job_intelligence": job_intelligence,
        "ranking_run_id": ranking_run_id,
    }
