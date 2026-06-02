from __future__ import annotations

from backend.intelligence.normalization import average_score, build_evidence_snippet
from backend.models.candidate_intelligence import (
    CandidateIntelligence,
    EducationSignal,
    ExperienceSignal,
    ProjectSignal,
)
from backend.models.evidence import EvidenceRef, EvidenceSnippet
from backend.models.candidate_profile import CandidateProfile
from backend.utils.skill_taxonomy import extract_domain_keywords, extract_skills_from_text

OWNERSHIP_TERMS = {"owned", "led", "lead", "architected", "end-to-end", "responsible", "built"}
COMMUNICATION_TERMS = {"presented", "collaborated", "documentation", "communicated", "demo", "stakeholders"}
EXECUTION_TERMS = {"shipped", "deployed", "production", "launched", "delivered", "implemented"}
LEARNING_TERMS = {"self-taught", "learned", "hackathon", "prototype", "rapid", "explored"}
TRAJECTORY_TERMS = {"advanced", "scalable", "real-time", "distributed", "optimization", "inference"}
LEADERSHIP_TERMS = {"led", "mentored", "managed", "coordinated", "captained"}
DEPLOYMENT_TERMS = {"docker", "kubernetes", "aws", "gcp", "azure", "vercel", "railway", "render", "ci/cd"}
AI_TERMS = {"llm", "rag", "openai", "anthropic", "ai", "machine learning", "generative ai"}
ENTERPRISE_TERMS = {"testing", "observability", "reliability", "monitoring", "cross-functional", "stakeholders"}


def _signal_score(text: str, terms: set[str], base: float = 25.0, step: float = 14.0) -> float:
    lowered = (text or "").lower()
    hits = sum(1 for term in terms if term in lowered)
    if hits == 0:
        return max(0.0, base - 10.0)
    return min(100.0, round(base + (hits * step), 2))


def _infer_capabilities(text: str) -> list[str]:
    lowered = (text or "").lower()
    capabilities = []
    if "real-time" in lowered or "realtime" in lowered:
        capabilities.append("real-time systems")
    if "multiplayer" in lowered or "concurrent" in lowered or "synchron" in lowered:
        capabilities.append("synchronization")
    if any(term in lowered for term in {"deployed", "vercel", "railway", "docker", "aws", "gcp"}):
        capabilities.append("deployment understanding")
    if any(term in lowered for term in {"api", "backend", "fastapi", "node", "express"}):
        capabilities.append("backend orchestration")
    if any(term in lowered for term in {"dashboard", "analytics", "workflow", "product"}):
        capabilities.append("product ownership")
    if any(term in lowered for term in {"scale", "scalable", "distributed"}):
        capabilities.append("scalability awareness")
    return capabilities[:5]


def _build_project_signals(profile: CandidateProfile) -> tuple[list[ProjectSignal], dict[str, EvidenceSnippet]]:
    signals = []
    evidence_library: dict[str, EvidenceSnippet] = {}
    for index, project in enumerate(profile.projects[:6]):
        evidence_id = f"project_{index}"
        title = project.splitlines()[0].strip() if project.splitlines() else f"Project {index + 1}"
        evidence_library[evidence_id] = build_evidence_snippet(
            evidence_id=evidence_id,
            source_type="project",
            source_label=title,
            snippet=project,
        )
        signals.append(
            ProjectSignal(
                title=title,
                technologies=extract_skills_from_text(project),
                inferred_capabilities=_infer_capabilities(project),
                evidence_id=evidence_id,
            )
        )
    return signals, evidence_library


def _build_experience_signals(profile: CandidateProfile) -> tuple[list[ExperienceSignal], dict[str, EvidenceSnippet]]:
    signals = []
    evidence_library: dict[str, EvidenceSnippet] = {}
    for index, experience in enumerate(profile.experience[:5]):
        evidence_id = f"experience_{index}"
        title = experience.splitlines()[0].strip() if experience.splitlines() else f"Experience {index + 1}"
        evidence_library[evidence_id] = build_evidence_snippet(
            evidence_id=evidence_id,
            source_type="experience",
            source_label=title,
            snippet=experience,
        )
        signals.append(
            ExperienceSignal(
                title=title,
                technologies=extract_skills_from_text(experience),
                inferred_capabilities=_infer_capabilities(experience),
                evidence_id=evidence_id,
            )
        )
    return signals, evidence_library


def _build_summary_evidence(profile: CandidateProfile) -> dict[str, EvidenceSnippet]:
    summary_text = profile.summary or profile.raw_text
    evidence: dict[str, EvidenceSnippet] = {}
    if summary_text:
        evidence["summary_0"] = build_evidence_snippet(
            evidence_id="summary_0",
            source_type="summary",
            source_label="Profile summary",
            snippet=summary_text,
        )
    if profile.skills:
        evidence["skills_0"] = build_evidence_snippet(
            evidence_id="skills_0",
            source_type="skills",
            source_label="Skills",
            snippet=", ".join(profile.skills),
        )
    for index, education in enumerate(profile.education[:2]):
        evidence_id = f"education_{index}"
        evidence[evidence_id] = build_evidence_snippet(
            evidence_id=evidence_id,
            source_type="education",
            source_label="Education",
            snippet=education,
        )
    return evidence


def _build_education_signals(profile: CandidateProfile) -> list[EducationSignal]:
    signals = []
    for index, education in enumerate(profile.education[:3]):
        title = education.splitlines()[0] if education.splitlines() else "Education"
        signals.append(EducationSignal(title=title, evidence_id=f"education_{index}"))
    return signals


def _build_contradictions(profile: CandidateProfile, evidence_library: dict[str, EvidenceSnippet]) -> list[str]:
    contradictions = []
    skill_count = len(profile.skills)
    shipped_evidence = [
        snippet
        for snippet in evidence_library.values()
        if snippet.source_type in {"project", "experience"} and snippet.evidence_strength == "high"
    ]
    if skill_count >= 16 and len(shipped_evidence) <= 1:
        contradictions.append("Broad skill inventory is only lightly supported by shipped project evidence.")
    if any(skill in {"AI", "LLM", "Generative AI"} for skill in profile.skills) and not any(
        any(term in snippet.snippet.lower() for term in AI_TERMS)
        for snippet in shipped_evidence
    ):
        contradictions.append("AI-related claims appear in the skills inventory with limited implementation evidence.")
    return contradictions


def build_candidate_intelligence(profile: CandidateProfile) -> tuple[CandidateIntelligence, dict[str, EvidenceSnippet]]:
    combined_text = "\n".join(
        part for part in [profile.summary, profile.raw_text, "\n".join(profile.projects), "\n".join(profile.experience)] if part
    )
    project_signals, project_evidence = _build_project_signals(profile)
    experience_signals, experience_evidence = _build_experience_signals(profile)
    summary_evidence = _build_summary_evidence(profile)

    evidence_library = {
        **project_evidence,
        **experience_evidence,
        **summary_evidence,
    }

    contradiction_flags = _build_contradictions(profile, evidence_library)
    core_signals = {
        "ownership": _signal_score(combined_text, OWNERSHIP_TERMS),
        "communication": _signal_score(combined_text, COMMUNICATION_TERMS, base=18.0, step=10.0),
        "execution_maturity": average_score(
            [
                _signal_score(combined_text, EXECUTION_TERMS, base=30.0, step=16.0),
                min(100.0, len(profile.deployment_signals) * 18.0 + 25.0) if profile.deployment_signals else 20.0,
            ]
        ),
        "learning_velocity": average_score(
            [
                _signal_score(combined_text, LEARNING_TERMS, base=25.0, step=16.0),
                65.0 if len(profile.projects) >= 3 else 48.0,
            ]
        ),
        "startup_readiness": average_score(
            [
                72.0 if len(profile.projects) >= 2 else 45.0,
                _signal_score(combined_text, OWNERSHIP_TERMS | EXECUTION_TERMS, base=24.0, step=12.0),
            ]
        ),
        "technical_depth": average_score(
            [
                min(100.0, len(profile.skills) * 4.2),
                _signal_score(combined_text, TRAJECTORY_TERMS | EXECUTION_TERMS, base=28.0, step=10.0),
            ]
        ),
        "domain_relevance": min(100.0, len(extract_domain_keywords(combined_text)) * 10.0 + 20.0),
        "transferability": average_score(
            [
                68.0 if len(profile.skills) >= 8 else 45.0,
                _signal_score(combined_text, {"api", "analytics", "platform", "workflow", "deployment"}, base=25.0, step=10.0),
            ]
        ),
    }
    supporting_signals = {
        "trajectory": _signal_score(combined_text, TRAJECTORY_TERMS, base=20.0, step=14.0),
        "adaptability": _signal_score(combined_text, {"integrated", "cross-domain", "rapid", "prototype", "varied"}, base=24.0, step=11.0),
        "leadership": _signal_score(combined_text, LEADERSHIP_TERMS, base=18.0, step=18.0),
        "deployment_maturity": _signal_score(combined_text, DEPLOYMENT_TERMS, base=22.0, step=14.0),
        "authenticity": 88.0 if not contradiction_flags else 52.0,
        "ai_capability": _signal_score(combined_text, AI_TERMS, base=18.0, step=16.0),
        "enterprise_readiness": _signal_score(combined_text, ENTERPRISE_TERMS, base=20.0, step=12.0),
        "consistency": max(35.0, 82.0 - (len(contradiction_flags) * 18.0)),
    }

    evidence_refs = [
        EvidenceRef(
            evidence_id=snippet.evidence_id,
            source_type=snippet.source_type,
            source_label=snippet.source_label,
        )
        for snippet in evidence_library.values()
    ]

    intelligence = CandidateIntelligence(
        candidate_name=profile.name,
        normalized_skills=profile.skills,
        projects=project_signals,
        experience_items=experience_signals,
        education=_build_education_signals(profile),
        certifications=profile.certifications,
        domains=extract_domain_keywords(combined_text),
        seniority_band=profile.seniority_band,
        years_experience_estimate=profile.years_of_experience,
        core_signals=core_signals,
        supporting_signals=supporting_signals,
        evidence=evidence_refs,
        contradiction_flags=contradiction_flags,
    )

    return intelligence, evidence_library
