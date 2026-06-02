import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from backend.dataset_intelligence.evaluation import compare_ranking_strategies, evaluate_ranking
from backend.dataset_intelligence.loader import load_dataset
from backend.dataset_intelligence.profiler import profile_dataframe, profile_dataset_path


class DatasetProfilingTests(unittest.TestCase):
    def test_profiles_unknown_candidate_csv_without_fixed_schema(self):
        frame = pd.DataFrame(
            [
                {
                    "candidate_id": "1",
                    "headline": "Senior Backend Engineer",
                    "skills": "Python, FastAPI, PostgreSQL, Docker",
                    "projects": "Built deployment pipeline and backend APIs for recruiter workflow platform.",
                    "years_experience": 6,
                    "last_active_days": 3,
                    "profile_completion": 0.92,
                },
                {
                    "candidate_id": "2",
                    "headline": "Frontend Developer",
                    "skills": "React, TypeScript, Tailwind",
                    "projects": "Built dashboard UI and analytics filters.",
                    "years_experience": 3,
                    "last_active_days": 25,
                    "profile_completion": 0.74,
                },
                {
                    "candidate_id": "3",
                    "headline": None,
                    "skills": "",
                    "projects": None,
                    "years_experience": None,
                    "last_active_days": 120,
                    "profile_completion": 0.31,
                },
            ]
        )

        report = profile_dataframe(frame, dataset_name="unknown_candidates.csv")

        self.assertEqual(report.row_count, 3)
        self.assertGreaterEqual(len(report.fields), 7)
        self.assertIn("skills", {item.category for item in report.signal_inventory})
        self.assertIn("projects", {item.category for item in report.signal_inventory})
        self.assertTrue(any(item.name == "profile_quality" for item in report.proposed_candidate_signals))
        self.assertIn("Dataset Readiness Report", report.markdown_report)

    def test_loads_nested_json_candidate_export(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "profiles.json"
            path.write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "name": "Maya",
                                "current": {"title": "Platform Engineer"},
                                "activity": {"posts": 4, "last_active": "2026-05-01"},
                                "certifications": ["AWS"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            frame = load_dataset(path)
            report = profile_dataset_path(path)

        self.assertIn("current.title", frame.columns)
        self.assertTrue(any("platform_activity" in field.signal_categories for field in report.fields))
        self.assertTrue(any("certifications" in field.signal_categories for field in report.fields))


class RankingEvaluationLayerTests(unittest.TestCase):
    def test_evaluates_ranking_order_and_strategy_comparison(self):
        expected = ["A", "B", "C", "D"]
        baseline = ["A", "C", "B", "D"]
        improved = ["A", "B", "C", "D"]

        result = evaluate_ranking(
            "baseline",
            baseline,
            expected_order=expected,
            positive_candidates=["A", "B"],
            negative_candidates=["D"],
            hidden_gems=["C"],
        )
        comparison = compare_ranking_strategies(
            {"baseline": baseline, "improved": improved},
            expected_order=expected,
            positive_candidates=["A", "B"],
            negative_candidates=["D"],
            hidden_gems=["C"],
            baseline_strategy="baseline",
        )

        self.assertLess(result.pairwise_accuracy or 0, 1.0)
        self.assertEqual(comparison.best_strategy, "improved")
        self.assertIn("Ranking Evaluation Report", comparison.markdown_report)


class DatasetApiTests(unittest.TestCase):
    def test_dataset_profile_endpoint_returns_structured_report(self):
        from backend.main import app

        client = TestClient(app)
        csv_content = (
            "name,title,skills,projects\n"
            "Maya,Backend Engineer,\"Python, FastAPI\",Built API services\n"
            "Jordan,Frontend Engineer,\"React, TypeScript\",Built dashboard UI\n"
        )

        response = client.post(
            "/dataset/profile/",
            files={"file": ("candidates.csv", csv_content.encode("utf-8"), "text/csv")},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["dataset_name"], "candidates.csv")
        self.assertIn("signal_inventory", payload)
        self.assertIn("markdown_report", payload)

    def test_ranking_evaluation_endpoint_returns_metrics(self):
        from backend.main import app

        client = TestClient(app)
        response = client.post(
            "/dataset/evaluate-rankings/",
            json={
                "strategies": {"baseline": ["A", "C", "B"], "candidate": ["A", "B", "C"]},
                "expected_order": ["A", "B", "C"],
                "positive_candidates": ["A", "B"],
                "negative_candidates": ["C"],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["best_strategy"], "candidate")
        self.assertIn("markdown_report", payload)


if __name__ == "__main__":
    unittest.main()

