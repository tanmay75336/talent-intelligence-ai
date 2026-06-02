from __future__ import annotations

import argparse
import tempfile
import threading
import time
from pathlib import Path

from backend.competition.rank import run_competition_ranking
from backend.competition.validate_submission import validate_submission
from backend.dataset_intelligence.loader import iter_dataset_records

RUNTIME_LIMIT_SECONDS = 300
MEMORY_LIMIT_GB = 16


class MemorySampler:
    def __init__(self, interval_seconds: float = 1.0) -> None:
        self.interval_seconds = interval_seconds
        self.peak_gb: float | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        try:
            import psutil

            self._process = psutil.Process()
        except Exception:
            self._process = None

    @property
    def available(self) -> bool:
        return self._process is not None

    def start(self) -> None:
        if not self.available:
            return
        self._sample()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self.available:
            return
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=self.interval_seconds * 2)
        self._sample()

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self._sample()

    def _sample(self) -> None:
        if not self._process:
            return
        current_gb = self._process.memory_info().rss / (1024 ** 3)
        self.peak_gb = current_gb if self.peak_gb is None else max(self.peak_gb, current_gb)


def run_benchmark(candidates_path: str | Path, job_path: str | Path) -> dict[str, object]:
    candidate_count = count_candidates(candidates_path)
    sampler = MemorySampler()
    with tempfile.TemporaryDirectory(prefix="redrob_benchmark_") as tmp_dir:
        output_path = Path(tmp_dir) / "redrob_benchmark.csv"
        sampler.start()
        start = time.perf_counter()
        run_competition_ranking(candidates_path, job_path, output_path)
        runtime_seconds = time.perf_counter() - start
        sampler.stop()
        validation_errors = validate_submission(output_path)

    return {
        "candidate_count": candidate_count,
        "runtime_seconds": runtime_seconds,
        "runtime_status": "PASS" if runtime_seconds <= RUNTIME_LIMIT_SECONDS else "FAIL",
        "peak_memory_gb": sampler.peak_gb,
        "memory_status": _memory_status(sampler.peak_gb),
        "submission_validation": "PASS" if not validation_errors else "FAIL",
        "validation_errors": validation_errors,
    }


def count_candidates(candidates_path: str | Path) -> int:
    return sum(1 for _ in iter_dataset_records(candidates_path))


def format_report(result: dict[str, object]) -> str:
    peak_memory = result["peak_memory_gb"]
    peak_memory_text = f"{peak_memory:.3f} GB" if isinstance(peak_memory, float) else "Unavailable"
    lines = [
        "RedRob Benchmark Report",
        "",
        "Candidates processed:",
        str(result["candidate_count"]),
        "",
        "Runtime:",
        f"{result['runtime_seconds']:.2f} seconds",
        "",
        "Limit:",
        f"{RUNTIME_LIMIT_SECONDS} seconds",
        "",
        "Runtime status:",
        str(result["runtime_status"]),
        "",
        "Peak Memory:",
        peak_memory_text,
        "",
        "Memory limit:",
        f"{MEMORY_LIMIT_GB} GB",
        "",
        "Memory status:",
        str(result["memory_status"]),
        "",
        "Submission validation:",
        str(result["submission_validation"]),
    ]
    validation_errors = result.get("validation_errors") or []
    if validation_errors:
        lines.extend(["", "Validation errors:", *[str(error) for error in validation_errors]])
    return "\n".join(lines)


def _memory_status(peak_memory_gb: float | None) -> str:
    if peak_memory_gb is None:
        return "SKIPPED"
    return "PASS" if peak_memory_gb <= MEMORY_LIMIT_GB else "FAIL"


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark offline RedRob competition readiness.")
    parser.add_argument("--candidates", required=True, help="Path to candidates JSON, JSONL, or JSONL.GZ.")
    parser.add_argument("--job", required=True, help="Path to job description .docx or text file.")
    args = parser.parse_args()
    result = run_benchmark(args.candidates, args.job)
    print(format_report(result))
    return 0 if result["runtime_status"] == "PASS" and result["submission_validation"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
