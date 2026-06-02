from pydantic import BaseModel, Field

from backend.models.evidence import EvidenceRef


class ProjectSignal(BaseModel):
    title: str
    technologies: list[str] = Field(default_factory=list)
    inferred_capabilities: list[str] = Field(default_factory=list)
    evidence_id: str = ""


class ExperienceSignal(BaseModel):
    title: str
    technologies: list[str] = Field(default_factory=list)
    inferred_capabilities: list[str] = Field(default_factory=list)
    evidence_id: str = ""


class EducationSignal(BaseModel):
    title: str
    evidence_id: str = ""


class CandidateIntelligence(BaseModel):
    candidate_name: str
    normalized_skills: list[str] = Field(default_factory=list)
    projects: list[ProjectSignal] = Field(default_factory=list)
    experience_items: list[ExperienceSignal] = Field(default_factory=list)
    education: list[EducationSignal] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    seniority_band: str = "unknown"
    years_experience_estimate: float = 0.0
    core_signals: dict[str, float] = Field(default_factory=dict)
    supporting_signals: dict[str, float] = Field(default_factory=dict)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    contradiction_flags: list[str] = Field(default_factory=list)
