from __future__ import annotations

from pydantic import BaseModel, Field

from backend.models.candidate_intelligence import CandidateIntelligence
from backend.models.candidate_profile import CandidateProfile
from backend.models.job_intelligence import JobIntelligence


class RetrievalChunk(BaseModel):
    chunk_id: str
    document_id: str
    chunk_type: str
    source_label: str
    text: str
    metadata: dict[str, str | int | float] = Field(default_factory=dict)


def _clean_chunk_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def chunk_candidate_profile(
    candidate_id: str,
    profile: CandidateProfile,
    candidate_intelligence: CandidateIntelligence,
) -> list[RetrievalChunk]:
    chunks: list[RetrievalChunk] = []

    def add_chunk(chunk_type: str, source_label: str, text: str, **metadata: str | int | float):
        cleaned = _clean_chunk_text(text)
        if not cleaned:
            return
        chunks.append(
            RetrievalChunk(
                chunk_id=f"{candidate_id}:{chunk_type}:{len(chunks)}",
                document_id=candidate_id,
                chunk_type=chunk_type,
                source_label=source_label,
                text=cleaned,
                metadata=metadata,
            )
        )

    add_chunk(
        "summary",
        "Profile summary",
        profile.summary or profile.raw_text[:400],
        seniority=profile.seniority_band,
    )

    for index, project in enumerate(profile.projects):
        title = project.splitlines()[0].strip() if project.splitlines() else f"Project {index + 1}"
        add_chunk(
            "project",
            title,
            project,
            index=index,
            inferred_capabilities=", ".join(candidate_intelligence.projects[index].inferred_capabilities)
            if index < len(candidate_intelligence.projects)
            else "",
        )

    for index, experience in enumerate(profile.experience):
        title = experience.splitlines()[0].strip() if experience.splitlines() else f"Experience {index + 1}"
        add_chunk("experience", title, experience, index=index)

    if profile.skills:
        add_chunk("skills", "Skills section", ", ".join(profile.skills), skills_count=len(profile.skills))
    if profile.education:
        add_chunk("education", "Education", "\n".join(profile.education), education_count=len(profile.education))
    if profile.certifications:
        add_chunk(
            "certifications",
            "Certifications",
            "\n".join(profile.certifications),
            certification_count=len(profile.certifications),
        )

    return chunks


def chunk_job_intelligence(job_id: str, job: JobIntelligence) -> list[RetrievalChunk]:
    chunks: list[RetrievalChunk] = []

    def add_chunk(chunk_type: str, source_label: str, text: str, **metadata: str | int | float):
        cleaned = _clean_chunk_text(text)
        if not cleaned:
            return
        chunks.append(
            RetrievalChunk(
                chunk_id=f"{job_id}:{chunk_type}:{len(chunks)}",
                document_id=job_id,
                chunk_type=chunk_type,
                source_label=source_label,
                text=cleaned,
                metadata=metadata,
            )
        )

    add_chunk("role_overview", job.role_title, job.role_title, seniority=job.seniority)
    if job.responsibilities:
        add_chunk("responsibilities", "Responsibilities", ". ".join(job.responsibilities), count=len(job.responsibilities))
    if job.explicit_skills:
        add_chunk("must_haves", "Must-haves", ", ".join(job.explicit_skills), count=len(job.explicit_skills))
    if job.preferred_skills:
        add_chunk("preferreds", "Preferred skills", ", ".join(job.preferred_skills), count=len(job.preferred_skills))
    return chunks
