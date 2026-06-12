import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.storage.db import initialize_database
from backend.storage.repositories import (
    CandidateRepository,
    EvidenceRepository,
    JobRepository,
    RankingResultRepository,
    RankingRunRepository,
)
from backend.storage.workflows import build_saved_run_results, persist_ranked_workflow


class StorageRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "recruiter_platform.db"
        os.environ["SQLITE_DB_PATH"] = str(self.db_path)
        initialize_database(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()
        os.environ.pop("SQLITE_DB_PATH", None)

    def test_save_and_load_core_records(self):
        job = JobRepository(self.db_path).create_job(
            "AI Engineer",
            "Need Python and retrieval experience.",
            {"role_title": "AI Engineer", "explicit_skills": ["Python"]},
        )
        candidate = CandidateRepository(self.db_path).create_candidate(
            "Alex",
            "Built semantic retrieval systems.",
            {"candidate_name": "Alex", "normalized_skills": ["Python"]},
        )
        run = RankingRunRepository(self.db_path).create_run(
            job["id"],
            rerank_enabled=False,
            embeddings_enabled=True,
            retrieval_enabled=True,
        )
        result = RankingResultRepository(self.db_path).save_result(
            run["id"],
            candidate["id"],
            _ranking_payload(final_score=91.2),
            rank_position=1,
        )
        EvidenceRepository(self.db_path).save_evidence_metadata(
            run["id"],
            candidate["id"],
            _ranking_payload()["supporting_evidence_snippets"]["semantic_fit"],
        )

        self.assertEqual(JobRepository(self.db_path).get_job(job["id"])["role_title"], "AI Engineer")
        self.assertEqual(CandidateRepository(self.db_path).get_candidate(candidate["id"])["candidate_name"], "Alex")
        self.assertEqual(RankingRunRepository(self.db_path).get_run(run["id"])["job_id"], job["id"])
        self.assertEqual(result["ranking_result"]["final_score"], 91.2)
        self.assertEqual(len(EvidenceRepository(self.db_path).get_candidate_evidence(candidate["id"], run["id"])), 1)

    def test_workflow_reopen_preserves_scores_and_evidence(self):
        run = persist_ranked_workflow(
            "Need a backend AI engineer.",
            {"role_title": "Backend AI Engineer", "explicit_skills": ["Python"]},
            [
                {
                    "candidate_name": "Maya",
                    "candidate_skills": ["Python"],
                    "candidate_intelligence": {
                        "candidate_name": "Maya",
                        "normalized_skills": ["Python", "FastAPI"],
                    },
                    "ranking": _ranking_payload(final_score=84.5),
                    "_storage": {"resume_text": "Built FastAPI retrieval services."},
                }
            ],
            db_path=self.db_path,
        )

        reopened = build_saved_run_results(run["id"], db_path=self.db_path)

        self.assertEqual(reopened["total_candidates"], 1)
        ranking = reopened["ranked_candidates"][0]["ranking"]
        self.assertEqual(ranking["final_score"], 84.5)
        self.assertEqual(
            ranking["supporting_evidence_snippets"]["semantic_fit"][0]["snippet"],
            "Built semantic retrieval with FastAPI.",
        )


class StorageApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "api.db"
        os.environ["SQLITE_DB_PATH"] = str(self.db_path)
        initialize_database(self.db_path)

        from backend.main import app

        self.client = TestClient(app)

    def tearDown(self):
        self.temp_dir.cleanup()
        os.environ.pop("SQLITE_DB_PATH", None)

    def test_historical_endpoints_return_saved_data(self):
        run = persist_ranked_workflow(
            "Need React and Python.",
            {"role_title": "Full Stack Engineer", "explicit_skills": ["React", "Python"]},
            [
                {
                    "candidate_name": "Jordan",
                    "candidate_skills": ["React", "Python"],
                    "candidate_intelligence": {
                        "candidate_name": "Jordan",
                        "normalized_skills": ["React", "Python"],
                    },
                    "ranking": _ranking_payload(final_score=78.0),
                    "_storage": {"resume_text": "Shipped React and Python systems."},
                },
                {
                    "candidate_name": "Taylor",
                    "candidate_skills": ["React"],
                    "candidate_intelligence": {
                        "candidate_name": "Taylor",
                        "normalized_skills": ["React"],
                    },
                    "ranking": _ranking_payload(final_score=64.0),
                    "_storage": {"resume_text": "Built React dashboards."},
                }
            ],
            db_path=self.db_path,
        )

        jobs_response = self.client.get("/jobs/")
        clamped_jobs_response = self.client.get("/jobs/?limit=-1")
        runs_response = self.client.get("/ranking-runs/")
        clamped_runs_response = self.client.get("/ranking-runs/?limit=1000")
        run_response = self.client.get(f"/ranking-runs/{run['id']}")
        results_response = self.client.get(f"/ranking-runs/{run['id']}/results")
        comparison_response = self.client.get(f"/ranking-runs/{run['id']}/comparison")

        self.assertEqual(jobs_response.status_code, 200)
        self.assertEqual(clamped_jobs_response.status_code, 200)
        self.assertEqual(runs_response.status_code, 200)
        self.assertEqual(clamped_runs_response.status_code, 200)
        self.assertEqual(run_response.status_code, 200)
        self.assertEqual(results_response.status_code, 200)
        self.assertEqual(results_response.json()["ranked_candidates"][0]["ranking"]["final_score"], 78.0)
        self.assertEqual(comparison_response.status_code, 200)
        self.assertEqual(comparison_response.json()["comparison"]["winner"], "Jordan")

    def test_missing_historical_ids_return_404(self):
        self.assertEqual(self.client.get("/jobs/missing").status_code, 404)
        self.assertEqual(self.client.get("/ranking-runs/missing").status_code, 404)
        self.assertEqual(self.client.get("/ranking-runs/missing/results").status_code, 404)
        self.assertEqual(self.client.get("/ranking-runs/missing/comparison").status_code, 404)

    def test_upload_ranking_succeeds_when_persistence_fails(self):
        import backend.main as backend_main

        original_rank_resume_files = backend_main.rank_resume_files
        original_persist_ranked_workflow = backend_main.persist_ranked_workflow

        def fake_rank_resume_files(file_paths, jd_text, return_errors=False):
            ranked_candidates = [
                {
                    "candidate_name": "Fallback Candidate",
                    "resume_file": "resume.pdf",
                    "candidate_skills": ["Python"],
                    "candidate_intelligence": {"candidate_name": "Fallback Candidate"},
                    "ranking": _ranking_payload(final_score=72.0),
                    "_storage": {"resume_text": "Built Python services."},
                }
            ]
            return ranked_candidates, [], {"role_title": "Backend Engineer"}

        def failing_persist(*args, **kwargs):
            raise RuntimeError("sqlite unavailable")

        backend_main.rank_resume_files = fake_rank_resume_files
        backend_main.persist_ranked_workflow = failing_persist
        try:
            response = self.client.post(
                "/upload-and-rank/",
                data={"jd_text": "Need Python"},
                files={"files": ("resume.pdf", b"fake pdf", "application/pdf")},
            )
        finally:
            backend_main.rank_resume_files = original_rank_resume_files
            backend_main.persist_ranked_workflow = original_persist_ranked_workflow

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["ranked_candidates"][0]["candidate_name"], "Fallback Candidate")
        self.assertNotIn("_storage", payload["ranked_candidates"][0])
        self.assertIsNone(payload["ranking_run_id"])
        self.assertIn("persistence failed", payload["processing_errors"][0])


def _ranking_payload(final_score: float = 88.0):
    return {
        "final_score": final_score,
        "recommendation": "Recommended",
        "recruiter_confidence": "High",
        "hidden_gem_flag": False,
        "matched_skills": ["Python"],
        "supporting_evidence_snippets": {
            "semantic_fit": [
                {
                    "evidence_id": "candidate:project:0",
                    "source_type": "project",
                    "source_label": "Retrieval Platform",
                    "snippet": "Built semantic retrieval with FastAPI.",
                    "evidence_strength": "high",
                    "retrieval_score": 0.92,
                }
            ]
        },
    }


if __name__ == "__main__":
    unittest.main()
