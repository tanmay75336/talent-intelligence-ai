import unittest
from unittest.mock import patch

from backend.models.evidence import EvidenceSnippet
from backend.reasoning.differentiation import apply_candidate_differentiation
from backend.reasoning.evidence_quality import classify_evidence, is_strong_evidence
from backend.reasoning.explanation_builder import build_ranking_result
from backend.reasoning.groq_synthesis import apply_optional_groq_synthesis
from backend.models.candidate_intelligence import CandidateIntelligence
from backend.models.candidate_profile import CandidateProfile
from backend.models.job_intelligence import JobIntelligence


class EvidenceQualityTests(unittest.TestCase):
    def test_skill_inventory_is_weak_evidence(self):
        quality = classify_evidence(
            "Python, FastAPI, React, Docker, AWS, PostgreSQL",
            source_type="skills",
        )

        self.assertEqual(quality.label, "weak")

    def test_implementation_with_operations_is_strong_evidence(self):
        quality = classify_evidence(
            "Built realtime auction synchronization with backend arbitration, reconnect handling, and production deployment monitoring.",
            source_type="project",
        )

        self.assertEqual(quality.label, "strong")


class RecruiterReasoningQualityTests(unittest.TestCase):
    def test_weak_evidence_reduces_confidence_and_suppresses_generic_outputs(self):
        profile = CandidateProfile(
            name="Alex",
            raw_text="Alex\nSkills\nPython, FastAPI, React",
            skills=["Python", "FastAPI", "React"],
        )
        candidate_intelligence = _candidate_intelligence("Alex")
        job = _job_intelligence()
        scorecard = _scorecard(recommendation="Recommended", confidence="High")
        evidence = {
            "skills_0": EvidenceSnippet(
                evidence_id="skills_0",
                source_type="skills",
                source_label="Skills",
                snippet="Python, FastAPI, React, Docker",
                evidence_strength="low",
            )
        }

        result = build_ranking_result(profile, job, candidate_intelligence, scorecard, evidence)

        self.assertEqual(result.recruiter_confidence, "Low")
        self.assertEqual(result.recommendation, "Consider for Interview")
        self.assertEqual(result.strengths, [])
        self.assertIn("provisional", result.recruiter_decision_summary)

    def test_run_level_differentiation_adds_unique_strong_signal(self):
        ranked_candidates = [
            {
                "candidate_name": "Maya",
                "ranking": {
                    "final_score": 82,
                    "strengths": ["Backend implementation evidence is grounded in Auction Platform."],
                    "risks": [],
                    "weaknesses": [],
                    "interview_focus_areas": [],
                    "recruiter_decision_summary": "Maya has credible backend implementation.",
                    "supporting_evidence_snippets": {
                        "semantic_fit": [
                            {
                                "evidence_id": "maya_project",
                                "source_type": "project",
                                "source_label": "Auction Platform",
                                "snippet": "Built realtime auction synchronization with backend arbitration and reconnect handling.",
                                "evidence_strength": "high",
                            }
                        ]
                    },
                },
            },
            {
                "candidate_name": "Jordan",
                "ranking": {
                    "final_score": 75,
                    "strengths": ["Backend implementation evidence is grounded in API Project."],
                    "risks": [],
                    "weaknesses": [],
                    "interview_focus_areas": [],
                    "recruiter_decision_summary": "Jordan has credible backend implementation.",
                    "supporting_evidence_snippets": {
                        "semantic_fit": [
                            {
                                "evidence_id": "jordan_project",
                                "source_type": "project",
                                "source_label": "API Project",
                                "snippet": "Built FastAPI services for workflow automation.",
                                "evidence_strength": "high",
                            }
                        ]
                    },
                },
            },
        ]

        apply_candidate_differentiation(ranked_candidates)

        self.assertIn("Distinctive realtime systems signal", ranked_candidates[0]["ranking"]["strengths"][0])
        self.assertLessEqual(len(ranked_candidates[0]["ranking"]["strengths"]), 2)

    def test_specific_evidence_produces_sharper_strength_and_validation(self):
        profile = CandidateProfile(
            name="Maya",
            raw_text="Maya\nBuilt realtime auction synchronization with backend arbitration and reconnect handling.",
            skills=["Python", "FastAPI"],
        )
        candidate_intelligence = _candidate_intelligence("Maya")
        job = _job_intelligence()
        scorecard = _scorecard(recommendation="Recommended", confidence="High")
        evidence = {
            "project_0": EvidenceSnippet(
                evidence_id="project_0",
                source_type="project",
                source_label="Auction Platform",
                snippet="Built realtime auction synchronization with backend arbitration and reconnect handling.",
                evidence_strength="high",
            )
        }

        result = build_ranking_result(profile, job, candidate_intelligence, scorecard, evidence)

        self.assertTrue(any("Auction Platform" in item and "realtime" in item for item in result.strengths))
        self.assertTrue(any("reconnects" in item or "failure recovery" in item for item in result.interview_focus_areas))
        self.assertFalse(any("Validate scalability understanding" in item for item in result.interview_focus_areas))

    def test_groq_misconfiguration_is_reported_without_candidate_retries(self):
        candidates = [_candidate_payload("Maya"), _candidate_payload("Jordan")]
        processing_errors: list[str] = []

        def env_value(name: str, default: str = "") -> str:
            values = {"ENABLE_GROQ_SYNTHESIS": "true", "GROQ_API_KEY": ""}
            return values.get(name, default)

        with patch("backend.reasoning.groq_synthesis._env_value", side_effect=env_value):
            apply_optional_groq_synthesis(candidates, processing_errors=processing_errors)

        self.assertEqual(len(processing_errors), 1)
        self.assertIn("GROQ_API_KEY", processing_errors[0])
        self.assertEqual(
            candidates[0]["ranking"]["scoring_diagnostics"]["ai_synthesis"]["status"],
            "misconfigured",
        )

    def test_groq_runtime_failure_falls_back_once_for_the_run(self):
        candidates = [_candidate_payload("Maya"), _candidate_payload("Jordan")]
        processing_errors: list[str] = []

        with patch.dict("os.environ", {"ENABLE_GROQ_SYNTHESIS": "true", "GROQ_API_KEY": "test-key"}):
            with patch(
                "backend.reasoning.groq_synthesis.synthesize_candidate_reasoning",
                side_effect=RuntimeError("authentication failed"),
            ) as synthesis:
                apply_optional_groq_synthesis(candidates, processing_errors=processing_errors)

        self.assertEqual(synthesis.call_count, 1)
        self.assertEqual(len(processing_errors), 1)
        self.assertEqual(
            candidates[1]["ranking"]["scoring_diagnostics"]["ai_synthesis"]["status"],
            "runtime_error",
        )
        self.assertTrue(candidates[1]["ranking"]["scoring_diagnostics"]["ai_synthesis"]["enabled"])

    def test_groq_polish_cannot_expand_validation_outputs(self):
        candidates = [_candidate_payload("Maya")]
        ranking = candidates[0]["ranking"]
        ranking["candidate_differentiators"] = ["Only candidate with realtime systems evidence from Auction Platform."]
        ranking["could_change_ordering"] = []
        ranking["ranking_challenge"] = ["Must-have gaps mean the recommendation depends on transferable evidence rather than direct proof."]
        ranking["confidence_rationale"] = "Ordering is a close call because nearby candidates have similar evidence strength."

        generated = {
            "summary": "Sharper summary grounded in Auction Platform.",
            "strengths": ["Sharper strength", "Invented extra strength"],
            "risks": ["Invented risk"],
            "interview_validations": ["Invented validation"],
            "candidate_differentiators": ["Sharper differentiator", "Invented differentiator"],
            "could_change_ordering": ["Invented change reason"],
            "ranking_challenge": ["Sharper challenge", "Invented challenge"],
            "confidence_rationale": "Sharper close-call confidence wording.",
        }

        with patch.dict("os.environ", {"ENABLE_GROQ_SYNTHESIS": "true", "GROQ_API_KEY": "test-key"}):
            with patch("backend.reasoning.groq_synthesis.synthesize_candidate_reasoning", return_value=generated):
                apply_optional_groq_synthesis(candidates)

        self.assertEqual(len(ranking["strengths"]), 1)
        self.assertEqual(ranking["could_change_ordering"], [])
        self.assertEqual(len(ranking["candidate_differentiators"]), 1)
        self.assertEqual(len(ranking["ranking_challenge"]), 1)


def _candidate_intelligence(name: str) -> CandidateIntelligence:
    return CandidateIntelligence(
        candidate_name=name,
        normalized_skills=["Python", "FastAPI", "React"],
        projects=[],
        experience_items=[],
        education=[],
        certifications=[],
        domains=[],
        seniority_band="entry",
        years_experience_estimate=1.0,
        core_signals={
            "ownership": 45,
            "communication": 35,
            "execution_maturity": 45,
            "learning_velocity": 45,
            "startup_readiness": 45,
            "technical_depth": 45,
            "domain_relevance": 35,
            "transferability": 45,
        },
        supporting_signals={
            "deployment_maturity": 25,
            "ai_capability": 25,
            "enterprise_readiness": 25,
            "adaptability": 35,
        },
        evidence=[],
        contradiction_flags=[],
    )


def _job_intelligence() -> JobIntelligence:
    return JobIntelligence(
        role_title="Backend Engineer",
        explicit_skills=["Python", "FastAPI"],
        preferred_skills=["Docker"],
        responsibilities=["Build backend APIs"],
        domains=[],
        seniority="unknown",
        startup_vs_enterprise="unknown",
        ownership_expectation=35,
        communication_expectation=35,
        evidence=[],
        confidence={},
    )


def _scorecard(recommendation: str, confidence: str) -> dict:
    return {
        "final_score": 78.0,
        "recommendation": recommendation,
        "recruiter_confidence": confidence,
        "semantic_score": 72.0,
        "keyword_score": 70.0,
        "adjacency_bonus": 0.0,
        "project_relevance_score": 65.0,
        "deployment_score": 40.0,
        "ai_experience_score": 25.0,
        "confidence_score": 80.0,
        "matched_skills": ["Python", "FastAPI"],
        "missing_skills": [],
        "adjacent_matches": [],
        "weaknesses": ["Assess communication"],
        "scoring_diagnostics": {},
    }


def _candidate_payload(name: str) -> dict:
    return {
        "candidate_name": name,
        "ranking": {
            "recruiter_decision_summary": f"{name} has credible implementation evidence.",
            "strengths": ["Auction Platform shows backend implementation depth through api."],
            "risks": [],
            "weaknesses": [],
            "interview_focus_areas": [],
            "supporting_evidence_snippets": {
                "semantic_fit": [
                    {
                        "evidence_id": f"{name.lower()}_project",
                        "source_type": "project",
                        "source_label": "Auction Platform",
                        "snippet": "Built realtime auction synchronization with backend arbitration and reconnect handling.",
                        "evidence_strength": "high",
                    }
                ]
            },
            "scoring_diagnostics": {},
        },
    }


if __name__ == "__main__":
    unittest.main()
