import csv
import itertools
import json
import tempfile
import unittest
from pathlib import Path

from backend.competition.rank import run_competition_ranking
from backend.competition.redrob_adapter import adapt_redrob_candidate
from backend.competition.validate_submission import validate_submission
from backend.dataset_intelligence.loader import iter_dataset_records, load_dataset


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


class RedRobDatasetLoadingTests(unittest.TestCase):
    def test_loads_sample_candidates_json(self):
        records = list(iter_dataset_records(DATA_DIR / "sample_candidates.json"))
        frame = load_dataset(DATA_DIR / "sample_candidates.json")

        self.assertTrue(records)
        self.assertIn("candidate_id", records[0])
        self.assertIn("raw_candidate", frame.columns)
        self.assertEqual(frame.iloc[0]["candidate_id"], records[0]["candidate_id"])

    def test_streams_candidates_jsonl(self):
        records = list(itertools.islice(iter_dataset_records(DATA_DIR / "candidates.jsonl"), 3))

        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["candidate_id"], "CAND_0000001")
        self.assertIn("redrob_signals", records[0])


class RedRobAdapterTests(unittest.TestCase):
    def test_adapter_preserves_official_schema_fields(self):
        candidate = next(iter_dataset_records(DATA_DIR / "sample_candidates.json"))
        profile = adapt_redrob_candidate(candidate)

        self.assertEqual(profile.candidate_id, candidate["candidate_id"])
        self.assertEqual(profile.structured_profile, candidate["profile"])
        self.assertEqual(profile.career_history, candidate["career_history"])
        self.assertEqual(profile.skill_records, candidate["skills"])
        self.assertEqual(profile.education_records, candidate["education"])
        self.assertEqual(profile.certification_records, candidate.get("certifications", []))
        self.assertEqual(profile.redrob_signals, candidate["redrob_signals"])
        self.assertIn(candidate["profile"]["headline"], profile.searchable_profile_text)
        self.assertIn(candidate["career_history"][0]["description"], profile.searchable_profile_text)
        self.assertIn(candidate["skills"][0]["name"], profile.searchable_profile_text)


class RedRobSubmissionTests(unittest.TestCase):
    def test_competition_csv_validation_passes(self):
        records = list(itertools.islice(iter_dataset_records(DATA_DIR / "candidates.jsonl"), 100))

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            candidates_path = temp_path / "candidates_100.jsonl"
            output_path = temp_path / "submission.csv"
            with candidates_path.open("w", encoding="utf-8") as handle:
                for record in records:
                    handle.write(json.dumps(record) + "\n")

            run_competition_ranking(
                candidates_path,
                DATA_DIR / "job_description.docx",
                output_path,
            )
            errors = validate_submission(output_path)

            self.assertEqual(errors, [])
            with output_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 100)
            self.assertTrue(all(row["reasoning"].strip() for row in rows))


if __name__ == "__main__":
    unittest.main()
