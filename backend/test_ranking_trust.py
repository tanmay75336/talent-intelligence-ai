import copy
import os
import unittest
from unittest.mock import patch

from backend.ranking_benchmark import evaluate_ranked_candidates
from backend.ranking_benchmark_cases import RankingBenchmarkCase
from backend.reasoning.groq_synthesis import _polished_list, groq_synthesis_enabled
from backend.reasoning.ranking_trust import apply_ranking_trust_analysis, apply_recruiter_validation, compare_candidates_pairwise


class RankingTrustTests(unittest.TestCase):
    def test_groq_synthesis_defaults_on_when_key_exists(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}, clear=True):
            self.assertTrue(groq_synthesis_enabled())

    def test_groq_synthesis_can_be_disabled_explicitly(self):
        with patch.dict(
            os.environ,
            {"GROQ_API_KEY": "test-key", "ENABLE_GROQ_SYNTHESIS": "false"},
            clear=True,
        ):
            self.assertFalse(groq_synthesis_enabled())

    def test_groq_polish_cannot_create_new_list_items(self):
        self.assertEqual(_polished_list(["New invented risk"], []), [])
        self.assertEqual(
            _polished_list(["Cleaner wording", "Extra invented item"], ["Original deterministic item"]),
            ["Cleaner wording"],
        )

    def test_buzzword_resume_does_not_outrank_implementation_candidate(self):
        candidates = [
            _candidate(
                "Keyword Stuffer",
                88,
                92,
                "Highly Recommended",
                "High",
                [
                    _evidence(
                        "summary",
                        "Profile summary",
                        "Experienced scalable AI backend platform engineer with Python FastAPI Docker CI/CD AWS monitoring APIs retrieval embeddings and production systems.",
                        "medium",
                    ),
                    _evidence("skills", "Skills", "Python, FastAPI, Docker, AWS, CI/CD, Chroma, APIs", "low"),
                ],
            ),
            _candidate(
                "Implementation Owner",
                84,
                78,
                "Recommended",
                "High",
                [
                    _evidence(
                        "project",
                        "Workflow API",
                        "Built FastAPI orchestration services with PostgreSQL persistence, Docker deployment, CI/CD release checks, and monitoring for failed jobs.",
                    )
                ],
            ),
        ]

        apply_ranking_trust_analysis(candidates)

        self.assertEqual(candidates[0]["candidate_name"], "Implementation Owner")
        self.assertNotEqual(candidates[1]["ranking"]["recommendation"], "Highly Recommended")

    def test_shallow_ai_resume_does_not_outrank_deployment_backend_candidate(self):
        candidates = [
            _candidate(
                "Shallow AI Resume",
                82,
                75,
                "Recommended",
                "High",
                [
                    _evidence("summary", "Profile summary", "Worked with AI, LLMs, embeddings, retrieval, and vector databases.", "medium"),
                    _evidence("skills", "Skills", "AI, LLM, Chroma, OpenAI, Python", "low"),
                ],
                ai_score=72,
            ),
            _candidate(
                "Deployment Backend",
                79,
                65,
                "Recommended",
                "Medium",
                [
                    _evidence(
                        "project",
                        "Ops Platform",
                        "Deployed backend API services with Docker on AWS, configured CI/CD pipelines, and monitored production jobs.",
                    )
                ],
                deployment_score=78,
            ),
        ]

        apply_ranking_trust_analysis(candidates)

        self.assertEqual(candidates[0]["candidate_name"], "Deployment Backend")
        self.assertIn("AI claims", candidates[1]["ranking"]["risks"][0])

    def test_pairwise_rationale_uses_evidence_not_score_gap(self):
        left = _candidate(
            "A",
            84,
            75,
            "Recommended",
            "High",
            [_evidence("project", "API", "Built FastAPI services with Docker deployment and monitoring.")],
        )
        right = _candidate(
            "B",
            82,
            90,
            "Recommended",
            "Medium",
            [_evidence("skills", "Skills", "Python, FastAPI, Docker, AWS, APIs", "low")],
        )

        comparison = compare_candidates_pairwise(left, right)

        self.assertEqual(comparison["preferred"], "left")
        self.assertIn("evidence", comparison["rationale"])
        self.assertNotIn("score", comparison["rationale"].lower())

    def test_pairwise_ranking_is_stable_across_reruns(self):
        candidates = [
            _candidate("Keyword Stuffer", 88, 92, "Highly Recommended", "High", [_evidence("skills", "Skills", "Python FastAPI Docker AWS CI/CD", "low")]),
            _candidate("Implementation Owner", 84, 78, "Recommended", "High", [_evidence("project", "API", "Built FastAPI services with Docker deployment, CI/CD, and monitoring.")]),
            _candidate("Adjacent", 78, 55, "Consider for Interview", "Medium", [_evidence("project", "Realtime", "Built realtime synchronization with backend arbitration and reconnect handling.")]),
        ]
        first = copy.deepcopy(candidates)
        second = copy.deepcopy(candidates)

        apply_ranking_trust_analysis(first)
        apply_ranking_trust_analysis(second)

        self.assertEqual(
            [candidate["candidate_name"] for candidate in first],
            [candidate["candidate_name"] for candidate in second],
        )

    def test_near_tie_reduces_assertiveness(self):
        candidates = [
            _candidate("One", 82, 70, "Highly Recommended", "High", [_evidence("project", "API One", "Built FastAPI services with Docker deployment and monitoring.")]),
            _candidate("Two", 81, 70, "Highly Recommended", "High", [_evidence("project", "API Two", "Built FastAPI services with Docker deployment and monitoring.")]),
        ]

        apply_ranking_trust_analysis(candidates)
        apply_recruiter_validation(candidates)

        self.assertEqual(candidates[0]["ranking"]["recommendation"], "Recommended")
        self.assertEqual(candidates[0]["ranking"]["recruiter_confidence"], "Medium")
        self.assertIn("Closely matched", candidates[0]["ranking"]["recruiter_decision_summary"])
        self.assertEqual(candidates[0]["ranking"]["ordering_confidence"], "Close")
        self.assertEqual(candidates[0]["ranking"]["close_call_with"], ["Two"])

    def test_hidden_gem_requires_strong_implementation_evidence(self):
        candidates = [
            _candidate(
                "Unsupported Hidden Gem",
                72,
                45,
                "Hidden Gem",
                "Medium",
                [_evidence("summary", "Profile", "Adaptable engineer with broad backend and frontend exposure.", "low")],
                adjacency_bonus=6,
                hidden_gem=True,
            )
        ]

        apply_ranking_trust_analysis(candidates)

        self.assertFalse(candidates[0]["ranking"]["hidden_gem_flag"])

    def test_benchmark_evaluator_detects_false_positive_failure(self):
        case = RankingBenchmarkCase(
            name="synthetic",
            jd_text="Need backend engineer.",
            resumes=[],
            expected_order=["Implementation Owner", "Keyword Stuffer"],
            expected_rejections=["Keyword Stuffer"],
            hidden_gems=[],
        )
        result = evaluate_ranked_candidates(
            case,
            [
                _candidate("Keyword Stuffer", 88, 92, "Highly Recommended", "High", []),
                _candidate("Implementation Owner", 84, 78, "Recommended", "High", []),
            ],
        )

        self.assertLess(result.pairwise_accuracy, 1.0)
        self.assertFalse(result.false_positive_pass)

    def test_keyword_stuffer_loses_to_hidden_gem_with_strong_implementation(self):
        candidates = [
            _candidate(
                "Keyword Stuffer",
                86,
                92,
                "Highly Recommended",
                "High",
                [
                    _evidence(
                        "summary",
                        "Profile summary",
                        "Experienced backend AI platform engineer with Python FastAPI Docker CI/CD APIs retrieval embeddings Chroma and scalable production systems.",
                        "medium",
                    ),
                    _evidence("skills", "Skills", "Python, FastAPI, Docker, CI/CD, Chroma, APIs", "low"),
                ],
            ),
            _candidate(
                "Adjacent Hidden Gem",
                69,
                48,
                "Consider for Interview",
                "Medium",
                [
                    _evidence(
                        "project",
                        "Auction Control Room",
                        "Built realtime auction synchronization with backend arbitration, reconnect handling, and PostgreSQL event persistence for live bidding rooms.",
                    )
                ],
                adjacency_bonus=6,
                hidden_gem=True,
            ),
        ]

        apply_ranking_trust_analysis(candidates)

        self.assertEqual(candidates[0]["candidate_name"], "Adjacent Hidden Gem")

    def test_recruiter_validation_empty_when_no_evidence_supported_insight(self):
        candidates = [
            _candidate(
                "Thin Resume",
                62,
                55,
                "Consider for Interview",
                "Medium",
                [_evidence("summary", "Profile", "Adaptable engineer with broad software exposure.", "low")],
            )
        ]

        apply_recruiter_validation(candidates)

        ranking = candidates[0]["ranking"]
        self.assertEqual(ranking["candidate_differentiators"], [])
        self.assertEqual(ranking["decisive_evidence_ids"], [])
        self.assertEqual(ranking["ordering_confidence"], "Low")
        self.assertTrue(ranking["ranking_challenge"])

    def test_recruiter_validation_marks_differentiated_evidence(self):
        candidates = [
            _candidate(
                "Realtime Owner",
                82,
                65,
                "Recommended",
                "High",
                [
                    _evidence(
                        "project",
                        "Auction Platform",
                        "Built realtime auction synchronization with backend arbitration and reconnect handling.",
                    )
                ],
            ),
            _candidate(
                "Deployment Owner",
                81,
                65,
                "Recommended",
                "High",
                [
                    _evidence(
                        "project",
                        "Ops Platform",
                        "Deployed FastAPI services with Docker deployment pipelines and monitoring.",
                    )
                ],
            ),
        ]

        apply_ranking_trust_analysis(candidates)
        apply_recruiter_validation(candidates)

        self.assertTrue(candidates[0]["ranking"]["candidate_differentiators"])
        self.assertTrue(candidates[0]["ranking"]["decisive_evidence_ids"])
        self.assertLessEqual(len(candidates[0]["ranking"]["strengths"]), 2)
        self.assertLessEqual(len(candidates[0]["ranking"]["risks"]), 2)


def _candidate(
    name,
    final_score,
    keyword_score,
    recommendation,
    confidence,
    evidence,
    ai_score=35,
    deployment_score=45,
    adjacency_bonus=0,
    hidden_gem=False,
):
    return {
        "candidate_name": name,
        "ranking": {
            "final_score": final_score,
            "keyword_score": keyword_score,
            "semantic_score": 70,
            "project_relevance_score": 68,
            "deployment_score": deployment_score,
            "ai_experience_score": ai_score,
            "adjacency_bonus": adjacency_bonus,
            "recommendation": recommendation,
            "recruiter_confidence": confidence,
            "hidden_gem_flag": hidden_gem,
            "matched_skills": ["Python", "FastAPI"],
            "missing_skills": [],
            "missing_must_haves": [],
            "strengths": [],
            "risks": [],
            "weaknesses": [],
            "interview_focus_areas": [],
            "recruiter_decision_summary": f"{name} has relevant evidence.",
            "recruiter_summary": f"{name} has relevant evidence.",
            "supporting_evidence_snippets": {"semantic_fit": evidence},
            "scoring_diagnostics": {},
        },
    }


def _evidence(source_type, source_label, snippet, strength="high"):
    return {
        "evidence_id": f"{source_label}:{snippet[:20]}",
        "source_type": source_type,
        "source_label": source_label,
        "snippet": snippet,
        "evidence_strength": strength,
    }


if __name__ == "__main__":
    unittest.main()
