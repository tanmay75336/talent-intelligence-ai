import logging
import os
import shutil
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from pathlib import Path

from backend.parsers.jd_parser import extract_skills_from_jd
from backend.parsers.resume_parser import build_candidate_profile, extract_skills, extract_text_from_pdf
from backend.ranking.pipeline import build_jd_analysis, rank_candidate_text, rank_resume_files
from backend.utils.embeddings import calculate_similarity

logger = logging.getLogger(__name__)

app = FastAPI()

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


# Home Route
@app.get("/")
def home():

    return {
        "message": "Talent Intelligence AI Backend Running"
    }


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
    }


# Job Description Upload API
@app.post("/upload-jd/")
async def upload_jd(jd_text: str):
    try:
        jd_analysis = build_jd_analysis(jd_text)
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

    return {
        "total_candidates": len(sorted_candidates),
        "ranked_candidates": sorted_candidates
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
        ranked_candidates, processing_errors = rank_resume_files(
            saved_file_paths,
            jd_text,
            return_errors=True,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return {
        "total_candidates": len(ranked_candidates),
        "ranked_candidates": ranked_candidates,
        "processing_errors": processing_errors,
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
        ranked_candidates, processing_errors = rank_resume_files(
            pdf_files,
            jd_text,
            return_errors=True,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    logger.info("Ranked %s dataset files from %s", len(pdf_files), DATASET_FOLDER)

    return {
        "dataset_size": len(pdf_files),
        "ranked_candidates": ranked_candidates,
        "processing_errors": processing_errors,
    }
