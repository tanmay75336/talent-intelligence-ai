from dataclasses import dataclass, field
from typing import Any


@dataclass
class CandidateProfile:
    name: str
    raw_text: str
    candidate_id: str = ""
    source_name: str = ""
    summary: str = ""
    skills: list[str] = field(default_factory=list)
    skill_records: list[dict[str, Any]] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    experience: list[str] = field(default_factory=list)
    career_history: list[dict[str, Any]] = field(default_factory=list)
    education: list[str] = field(default_factory=list)
    education_records: list[dict[str, Any]] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    certification_records: list[dict[str, Any]] = field(default_factory=list)
    sections: dict[str, str] = field(default_factory=dict)
    deployment_signals: list[str] = field(default_factory=list)
    ai_signals: list[str] = field(default_factory=list)
    api_signals: list[str] = field(default_factory=list)
    years_of_experience: float = 0.0
    seniority_band: str = "unknown"
    searchable_profile_text: str = ""
    redrob_signals: dict[str, Any] = field(default_factory=dict)
    raw_candidate: dict[str, Any] = field(default_factory=dict)
    structured_profile: dict[str, Any] = field(default_factory=dict)

    def semantic_sections(self):
        sections = []

        if self.summary:
            sections.append(self.summary)

        sections.extend(self.projects[:4])
        sections.extend(self.experience[:3])

        if self.skills:
            sections.append("Skills: " + ", ".join(self.skills))

        if not sections:
            sections.append(self.raw_text)

        return sections

    def combined_project_text(self):
        return "\n".join(self.projects)

    def combined_experience_text(self):
        return "\n".join(self.experience)
