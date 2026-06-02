from pydantic import BaseModel, Field

from backend.models.evidence import EvidenceRef


class JobIntelligence(BaseModel):
    role_title: str
    explicit_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    seniority: str = "unknown"
    startup_vs_enterprise: str = "unknown"
    ownership_expectation: float = 0.0
    communication_expectation: float = 0.0
    evidence: list[EvidenceRef] = Field(default_factory=list)
    confidence: dict[str, str] = Field(default_factory=dict)
