from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.dataset_intelligence.profiler import profile_dataset_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile unknown hiring datasets for ranking readiness.")
    parser.add_argument("dataset", help="Path to a CSV, JSON, JSONL, or NDJSON dataset.")
    parser.add_argument("--json", action="store_true", help="Print the structured report as JSON instead of markdown.")
    parser.add_argument("--output", help="Optional path to write the report.")
    args = parser.parse_args()

    report = profile_dataset_path(args.dataset)
    content = report.model_dump_json(indent=2) if args.json else report.markdown_report

    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
    else:
        print(content)


if __name__ == "__main__":
    main()
