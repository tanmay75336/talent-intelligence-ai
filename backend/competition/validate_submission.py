from __future__ import annotations

import argparse
import csv
from pathlib import Path


REQUIRED_COLUMNS = ["candidate_id", "rank", "score", "reasoning"]


def validate_submission(path: str | Path) -> list[str]:
    submission_path = Path(path)
    errors: list[str] = []
    with submission_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != REQUIRED_COLUMNS:
            errors.append(f"Columns must be exactly: {','.join(REQUIRED_COLUMNS)}")
            return errors
        rows = list(reader)

    if len(rows) != 100:
        errors.append(f"Expected exactly 100 rows, found {len(rows)}.")

    ranks: list[int] = []
    candidate_ids: list[str] = []
    scores: list[float] = []
    for index, row in enumerate(rows, start=2):
        candidate_id = (row.get("candidate_id") or "").strip()
        reasoning = (row.get("reasoning") or "").strip()
        if not candidate_id:
            errors.append(f"Row {index}: candidate_id is empty.")
        if not reasoning:
            errors.append(f"Row {index}: reasoning is empty.")
        candidate_ids.append(candidate_id)

        try:
            ranks.append(int(row.get("rank") or ""))
        except ValueError:
            errors.append(f"Row {index}: rank must be an integer.")

        try:
            scores.append(float(row.get("score") or ""))
        except ValueError:
            errors.append(f"Row {index}: score must be numeric.")

    if sorted(ranks) != list(range(1, 101)):
        errors.append("Ranks must be exactly 1 through 100 once each.")

    duplicate_ids = sorted({candidate_id for candidate_id in candidate_ids if candidate_ids.count(candidate_id) > 1})
    if duplicate_ids:
        errors.append(f"Duplicate candidate IDs found: {', '.join(duplicate_ids[:5])}.")

    for previous, current in zip(scores, scores[1:]):
        if current > previous:
            errors.append("Scores must be monotonically non-increasing.")
            break

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RedRob competition submission CSV.")
    parser.add_argument("submission", help="Path to submission CSV.")
    args = parser.parse_args()
    errors = validate_submission(args.submission)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("Submission is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
