from pydantic import BaseModel, Field

from backend.models.evidence import EvidenceSnippet


class AdjacentMatch(BaseModel):
    missing_skill: str
    related_skill: str


class PillarScore(BaseModel):
    score: float = 0.0
    confidence: str = "Low"
    summary: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class RankingResult(BaseModel):
    final_score: float
    recommendation: str
    recruiter_confidence: str
    pillar_scores: dict[str, PillarScore] = Field(default_factory=dict)

    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    missing_must_haves: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    why_not_selected: list[str] = Field(default_factory=list)
    reasons_ranked_below_stronger_candidates: list[str] = Field(default_factory=list)
    interview_focus_areas: list[str] = Field(default_factory=list)

    supporting_evidence_snippets: dict[str, list[EvidenceSnippet]] = Field(default_factory=dict)

    hidden_gem_flag: bool = False
    recruiter_decision_summary: str = ""
    ats_vs_intelligence_reasoning: str | None = None
    ordering_confidence: str | None = None
    confidence_rationale: str | None = None
    candidate_differentiators: list[str] = Field(default_factory=list)
    decisive_evidence_ids: list[str] = Field(default_factory=list)
    close_call_with: list[str] = Field(default_factory=list)
    could_change_ordering: list[str] = Field(default_factory=list)
    ranking_challenge: list[str] = Field(default_factory=list)

    semantic_score: float = 0.0
    keyword_score: float = 0.0
    adjacency_bonus: float = 0.0
    project_relevance_score: float = 0.0
    deployment_score: float = 0.0
    ai_experience_score: float = 0.0
    confidence_score: float = 0.0
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    adjacent_matches: list[AdjacentMatch] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recruiter_summary: str = ""
    scoring_diagnostics: dict[str, object] = Field(default_factory=dict)
