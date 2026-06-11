import importlib.util
from types import SimpleNamespace
import tempfile
import unittest
from pathlib import Path

from backend.evaluation_test_cases import EVALUATION_TEST_CASES
from backend.intelligence.candidate_engine import build_candidate_intelligence
from backend.intelligence.jd_engine import build_job_intelligence
from backend.models.evidence import EvidenceSnippet
from backend.parsers.jd_analyzer import analyze_job_description
from backend.parsers.resume_parser import build_candidate_profile
from backend.ranking.scoring_engine import score_candidate_profile
from backend.retrieval.bm25_retriever import SparseRetriever
from backend.retrieval.chunking import chunk_candidate_profile, chunk_job_intelligence
from backend.retrieval.deduplication import diversify_chunks
from backend.retrieval.rank_fusion import reciprocal_rank_fusion
from backend.retrieval.vector_store import RetrievedChunk


CHROMA_AVAILABLE = bool(importlib.util.find_spec("chromadb"))


class RetrievalUnitTests(unittest.TestCase):
    def test_sparse_retriever_reinforces_exact_must_haves(self):
        retriever = SparseRetriever()
        chunks = [
            _chunk("c1:project:0", "Built live bidding synchronization architecture for realtime rooms."),
            _chunk("c1:project:1", "Created polished frontend dashboards with animations."),
        ]
        retriever.upsert_chunks("candidates", chunks)

        results = retriever.query("candidates", ["realtime synchronization"], top_k=2, where={"document_id": "c1"})

        self.assertTrue(results)
        self.assertEqual(results[0].chunk_id, "c1:project:0")

    def test_rrf_combines_dense_and_sparse_rankings(self):
        dense = [
            _retrieved("a", 0.78, {"dense_score": 0.78}),
            _retrieved("b", 0.72, {"dense_score": 0.72}),
        ]
        sparse = [
            _retrieved("b", 0.82, {"sparse_score": 0.82}),
            _retrieved("c", 0.74, {"sparse_score": 0.74}),
        ]

        fused = reciprocal_rank_fusion({"dense": dense, "sparse": sparse})

        self.assertEqual(fused[0].chunk_id, "b")
        self.assertIn("rrf_score", fused[0].metadata)
        self.assertIn("dense_rank", fused[0].metadata)
        self.assertIn("sparse_rank", fused[0].metadata)

    def test_diversity_suppresses_repetitive_evidence(self):
        chunks = [
            _retrieved("a", 0.95, source_label="Auction Simulator", text="Built realtime live bidding synchronization for auction rooms."),
            _retrieved("b", 0.91, source_label="Auction Simulator", text="Built realtime live bidding synchronization for auction rooms with users."),
            _retrieved("c", 0.84, source_label="Deployment", text="Deployed backend services on AWS with monitoring."),
        ]

        result = diversify_chunks(chunks, limit=3, max_per_source_label=1)

        self.assertEqual([chunk.chunk_id for chunk in result.selected], ["a", "c"])
        self.assertTrue(result.suppressed)


class CalibrationUnitTests(unittest.TestCase):
    def test_adjacent_fit_is_capped_below_elite_without_exact_frontend_support(self):
        case = next(item for item in EVALUATION_TEST_CASES if item.name == "strong_adjacent_fit_backend_platform")
        scorecard = _score_with_fake_retrieval(
            case,
            retrieval_scores=[0.88, 0.84, 0.80],
            covered_skills={"Python", "FastAPI", "REST APIs", "PostgreSQL", "AI", "API Integration"},
        )

        self.assertGreaterEqual(scorecard["final_score"], 70)
        self.assertLessEqual(scorecard["final_score"], 85)

    def test_perfect_fit_keeps_elite_score_with_exact_support(self):
        case = next(item for item in EVALUATION_TEST_CASES if item.name == "perfect_fit_ai_fullstack")
        required = set(analyze_job_description(case.jd_text).required_skills)
        scorecard = _score_with_fake_retrieval(
            case,
            retrieval_scores=[0.92, 0.88, 0.84],
            covered_skills=required,
        )

        self.assertGreaterEqual(scorecard["final_score"], 85)
        self.assertLessEqual(scorecard["final_score"], 95)

    def test_irrelevant_candidate_suppressed_below_fifteen(self):
        case = next(item for item in EVALUATION_TEST_CASES if item.name == "irrelevant_candidate")
        scorecard = _score_with_fake_retrieval(
            case,
            retrieval_scores=[0.28, 0.22, 0.18],
            covered_skills=set(),
        )

        self.assertLess(scorecard["final_score"], 15)
        self.assertIn(
            "irrelevant_candidate_cap",
            scorecard["scoring_diagnostics"]["adjustments"]["benchmark_calibration_reasons"],
        )


@unittest.skipUnless(CHROMA_AVAILABLE, "chromadb is not installed")
class RetrievalIntegrationTests(unittest.TestCase):
    def setUp(self):
        from backend.retrieval.chroma_store import ChromaVectorStore
        from backend.retrieval.evidence_retriever import EvidenceRetriever

        self.temp_dir = tempfile.TemporaryDirectory()
        self.vector_store = ChromaVectorStore(persist_directory=self.temp_dir.name)
        self.retriever = EvidenceRetriever(self.vector_store)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _build_context(self, jd_text: str, resume_text: str, candidate_id: str = "candidate_1"):
        job = build_job_intelligence(jd_text)
        profile = build_candidate_profile(resume_text, source_name=candidate_id)
        intelligence, _ = build_candidate_intelligence(profile)
        job_id = "job_1"
        job_chunks = chunk_job_intelligence(job_id, job)
        candidate_chunks = chunk_candidate_profile(candidate_id, profile, intelligence)
        self.retriever.index_documents(
            "test_job_chunks",
            "test_candidate_chunks",
            job_chunks,
            candidate_chunks,
            job_id=job_id,
            candidate_id=candidate_id,
        )
        return self.retriever.retrieve_for_candidate(
            job,
            intelligence,
            job_chunks,
            candidate_chunks,
            "test_job_chunks",
            "test_candidate_chunks",
            candidate_id=candidate_id,
            job_id=job_id,
        )

    def test_realtime_backend_retrieval(self):
        jd_text = "Need backend engineer with scalable realtime systems experience."
        resume_text = """
        Candidate One

        SUMMARY
        Backend-focused engineer building distributed product systems.

        PROJECTS
        T20 Arena
        Built a multiplayer IPL auction simulator with live bidding synchronization, backend-authoritative rooms, and real-time updates.
        """
        context = self._build_context(jd_text, resume_text)
        semantic_evidence = context.pillar_evidence["semantic_fit"]
        self.assertTrue(semantic_evidence)
        top_snippet = semantic_evidence[0].snippet.lower()
        self.assertTrue("live bidding" in top_snippet or "real-time" in top_snippet or "synchronization" in top_snippet)
        diagnostics = context.diagnostics["pillars"]["semantic_fit"]
        self.assertTrue(diagnostics["dense_rankings"])
        self.assertTrue(diagnostics["sparse_rankings"])
        self.assertTrue(diagnostics["fused_rankings"])

    def test_cloud_deployment_retrieval(self):
        jd_text = "Looking for engineers with cloud deployment experience and production delivery."
        resume_text = """
        Candidate Two

        SUMMARY
        Full-stack engineer who ships customer-facing products.

        PROJECTS
        Portfolio Analytics
        Deployed the platform using AWS, Render, and Vercel with CI/CD automation and production monitoring.
        """
        context = self._build_context(jd_text, resume_text, candidate_id="candidate_2")
        execution_evidence = context.pillar_evidence["execution_maturity"]
        self.assertTrue(execution_evidence)
        top_snippet = execution_evidence[0].snippet.lower()
        self.assertTrue("aws" in top_snippet or "render" in top_snippet or "vercel" in top_snippet)

    def test_transferability_retrieval(self):
        jd_text = "Hiring backend engineers comfortable with API services, scalable systems, and platform delivery."
        resume_text = """
        Candidate Three

        SUMMARY
        Platform engineer with strong Python APIs and deployment ownership.

        PROJECTS
        OpsPilot API Platform
        Built FastAPI workflow services, deployment pipelines, and analytics integrations for a SaaS platform.
        """
        context = self._build_context(jd_text, resume_text, candidate_id="candidate_3")
        transfer_evidence = context.pillar_evidence["transferability"]
        self.assertTrue(transfer_evidence)
        self.assertGreaterEqual(transfer_evidence[0].retrieval_score or 0, 0.2)

    def test_must_have_suppression_for_missing_llm_requirements(self):
        jd_text = "Need AI engineer with LLM engineering, embeddings, semantic retrieval, and vector database experience."
        resume_text = """
        Candidate Four

        SUMMARY
        Frontend engineer focused on visual polish and React landing pages.

        PROJECTS
        Design Studio
        Built responsive UI components and marketing pages with CSS animations.
        """
        context = self._build_context(jd_text, resume_text, candidate_id="candidate_4")

        suppression = context.diagnostics["must_have_suppression"]
        self.assertGreater(suppression["penalty"], 0)
        self.assertTrue(suppression["missing"])

    def test_transferability_expansion_finds_realtime_adjacent_evidence(self):
        jd_text = "Hiring backend engineer for scalable event-driven realtime systems."
        resume_text = """
        Candidate Five

        PROJECTS
        Auction Arena
        Built multiplayer auction rooms with live bidding synchronization and backend-authoritative state updates.
        """
        context = self._build_context(jd_text, resume_text, candidate_id="candidate_5")

        snippets = " ".join(item.snippet.lower() for item in context.pillar_evidence["transferability"])
        self.assertIn("synchronization", snippets)

    def test_evidence_diversity_limits_repeated_source(self):
        jd_text = "Need backend engineer with realtime systems and deployment experience."
        resume_text = """
        Candidate Six

        PROJECTS
        Auction Platform
        Built realtime bidding synchronization and realtime auction rooms.

        Auction Platform
        Built realtime bidding synchronization and realtime auction rooms for admin users.

        Deployment Work
        Deployed backend APIs on Railway with monitoring and production environment variables.
        """
        context = self._build_context(jd_text, resume_text, candidate_id="candidate_6")

        evidence = context.pillar_evidence["semantic_fit"]
        labels = [item.source_label for item in evidence]
        self.assertLessEqual(labels.count("Auction Platform"), 2)
        self.assertTrue(context.diagnostics["pillars"]["semantic_fit"]["suppressed_evidence"])


def _chunk(chunk_id: str, text: str):
    from backend.retrieval.chunking import RetrievalChunk

    return RetrievalChunk(
        chunk_id=chunk_id,
        document_id=chunk_id.split(":")[0],
        chunk_type="project",
        source_label="Project",
        text=text,
        metadata={},
    )


def _retrieved(
    chunk_id: str,
    score: float,
    metadata: dict[str, str | int | float] | None = None,
    source_label: str = "Project",
    text: str = "Built production backend systems.",
):
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id="c1",
        chunk_type="project",
        source_label=source_label,
        text=text,
        metadata=metadata or {},
        retrieval_score=score,
    )


def _score_with_fake_retrieval(case, retrieval_scores: list[float], covered_skills: set[str]):
    jd_analysis = analyze_job_description(case.jd_text)
    profile = build_candidate_profile(case.resume_text, source_name=case.name)
    required_skills = jd_analysis.required_skills
    coverage = {skill: (1.0 if skill in covered_skills else 0.0) for skill in required_skills}
    evidence = [
        EvidenceSnippet(
            evidence_id="fake_project",
            source_type="project",
            source_label="Project",
            snippet="Built production API services with deployment pipelines and integrations.",
            evidence_strength="high",
            retrieval_score=retrieval_scores[0] if retrieval_scores else 0.0,
        ),
        EvidenceSnippet(
            evidence_id="fake_experience",
            source_type="experience",
            source_label="Experience",
            snippet="Owned backend delivery and production platform work.",
            evidence_strength="high",
            retrieval_score=retrieval_scores[1] if len(retrieval_scores) > 1 else 0.0,
        ),
    ]
    retrieval_context = SimpleNamespace(
        pillar_scores={
            "semantic_fit": retrieval_scores,
            "execution_maturity": retrieval_scores,
            "technical_depth": retrieval_scores,
            "transferability": retrieval_scores,
        },
        pillar_evidence={
            "semantic_fit": evidence,
            "execution_maturity": evidence,
            "technical_depth": evidence,
            "transferability": evidence,
        },
        must_have_coverage=coverage,
        diagnostics={
            "must_have_suppression": {
                "penalty": 0.0,
                "missing": [skill for skill, score in coverage.items() if score < 0.2],
            }
        },
    )
    return score_candidate_profile(profile, jd_analysis, retrieval_context=retrieval_context)


if __name__ == "__main__":
    unittest.main()
