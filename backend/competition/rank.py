from __future__ import annotations

import argparse
import csv
import heapq
import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from backend.competition.redrob_adapter import adapt_redrob_candidate
from backend.competition.validate_submission import validate_submission
from backend.dataset_intelligence.loader import iter_dataset_records
from backend.intelligence.candidate_engine import build_candidate_intelligence
from backend.parsers.jd_analyzer import analyze_job_description
from backend.utils.skill_taxonomy import (
    extract_domain_keywords,
    get_active_groups,
    normalize_whitespace,
    unique_preserve_order,
)

TOP_K = 100


@dataclass
class CompetitionCandidate:
    candidate_id: str
    score: float
    reasoning: str


def run_competition_ranking(candidates_path: str | Path, job_path: str | Path, output_path: str | Path) -> list[CompetitionCandidate]:
    configure_offline_environment()
    job_text = read_job_text(job_path)
    job_analysis = analyze_job_description(job_text)
    job_terms = _important_terms(job_text)
    top_candidates: list[tuple[float, str, CompetitionCandidate]] = []
    seen_candidate_ids: set[str] = set()

    for raw_candidate in iter_dataset_records(candidates_path):
        profile = adapt_redrob_candidate(raw_candidate)
        if not profile.candidate_id or profile.candidate_id in seen_candidate_ids:
            continue
        seen_candidate_ids.add(profile.candidate_id)
        candidate_intelligence, evidence_library = build_candidate_intelligence(profile)
        score = _competition_score(profile, candidate_intelligence.core_signals, job_analysis, job_terms)
        reasoning = _competition_reasoning(profile, job_analysis, evidence_library)
        candidate = CompetitionCandidate(
            candidate_id=profile.candidate_id,
            score=score,
            reasoning=reasoning,
        )
        heap_item = (candidate.score, candidate.candidate_id, candidate)
        if len(top_candidates) < TOP_K:
            heapq.heappush(top_candidates, heap_item)
        elif heap_item > top_candidates[0]:
            heapq.heapreplace(top_candidates, heap_item)

    ranked_candidates = [
        item[2]
        for item in sorted(top_candidates, key=lambda item: (-item[2].score, item[2].candidate_id))
    ]
    write_submission_csv(ranked_candidates, output_path)
    errors = validate_submission(output_path)
    if errors:
        raise ValueError("Invalid competition submission: " + " ".join(errors))
    return ranked_candidates


def configure_offline_environment() -> None:
    os.environ["ENABLE_GROQ_SYNTHESIS"] = "0"
    os.environ["ENABLE_LLM_RERANK"] = "0"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["CUDA_VISIBLE_DEVICES"] = ""


def read_job_text(path: str | Path) -> str:
    job_path = Path(path)
    suffix = job_path.suffix.lower()
    if suffix == ".docx":
        return _read_docx_text(job_path)
    return job_path.read_text(encoding="utf-8")


def write_submission_csv(candidates: list[CompetitionCandidate], output_path: str | Path) -> None:
    if len(candidates) != TOP_K:
        raise ValueError(f"Competition submission requires {TOP_K} candidates; got {len(candidates)}.")
    output = Path(output_path)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["candidate_id", "rank", "score", "reasoning"])
        writer.writeheader()
        for rank, candidate in enumerate(candidates, start=1):
            writer.writerow(
                {
                    "candidate_id": candidate.candidate_id,
                    "rank": rank,
                    "score": f"{candidate.score:.6f}",
                    "reasoning": candidate.reasoning,
                }
            )


def _competition_score(profile, core_signals: dict[str, float], job_analysis, job_terms: set[str]) -> float:
    candidate_skills = set(profile.skills)
    job_skills = set(job_analysis.all_skills)
    skill_overlap = _ratio(len(candidate_skills & job_skills), len(job_skills))
    candidate_groups = set(get_active_groups(profile.skills))
    job_groups = set(get_active_groups(job_analysis.all_skills))
    group_overlap = _ratio(len(candidate_groups & job_groups), len(job_groups))
    candidate_terms = _important_terms(profile.searchable_profile_text or profile.raw_text)
    term_overlap = _ratio(len(candidate_terms & job_terms), len(job_terms))
    experience_fit = _experience_fit(profile.years_of_experience)
    signal_average = _ratio(
        core_signals.get("technical_depth", 0.0)
        + core_signals.get("execution_maturity", 0.0)
        + core_signals.get("startup_readiness", 0.0)
        + core_signals.get("transferability", 0.0)
        + core_signals.get("domain_relevance", 0.0),
        500.0,
    )

    score = (
        skill_overlap * 0.34
        + group_overlap * 0.16
        + term_overlap * 0.18
        + experience_fit * 0.12
        + signal_average * 0.20
    )
    return round(max(0.0, min(1.0, score)), 6)


def _competition_reasoning(profile, job_analysis, evidence_library: dict[str, Any]) -> str:
    matched_skills = [skill for skill in profile.skills if skill in set(job_analysis.all_skills)]
    current_title = profile.structured_profile.get("current_title") or "candidate"
    current_company = profile.structured_profile.get("current_company") or "current company"
    years = profile.years_of_experience
    evidence = _best_evidence_text(evidence_library) or profile.summary or profile.searchable_profile_text
    evidence = normalize_whitespace(evidence)
    if len(evidence) > 170:
        evidence = evidence[:167].rstrip() + "..."
    skill_text = ", ".join(matched_skills[:4]) if matched_skills else ", ".join(profile.skills[:4])
    if skill_text:
        return (
            f"{current_title} at {current_company} with {years:.1f} years; profile evidence references {skill_text}. "
            f"{evidence}"
        )
    return f"{current_title} at {current_company} with {years:.1f} years. {evidence}"


def _best_evidence_text(evidence_library: dict[str, Any]) -> str:
    for source_type in ("project", "experience", "summary"):
        for snippet in evidence_library.values():
            if getattr(snippet, "source_type", "") == source_type and getattr(snippet, "snippet", ""):
                return snippet.snippet
    return ""


def _important_terms(text: str) -> set[str]:
    domain_terms = set(extract_domain_keywords(text, limit=30))
    tokens = {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z+\-]{2,}", normalize_whitespace(text).lower())
        if token not in {"and", "the", "for", "with", "that", "this", "you", "your", "our", "from", "into"}
    }
    return set(unique_preserve_order(list(domain_terms) + sorted(tokens))) or tokens


def _experience_fit(years: float) -> float:
    if 5.0 <= years <= 9.0:
        return 1.0
    if 4.0 <= years < 5.0 or 9.0 < years <= 11.0:
        return 0.72
    if 3.0 <= years < 4.0 or 11.0 < years <= 14.0:
        return 0.46
    return 0.22 if years > 0 else 0.0


def _ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _read_docx_text(path: Path) -> str:
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    paragraphs = []
    for paragraph in root.findall(".//w:p", namespace):
        texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        line = normalize_whitespace("".join(texts))
        if line:
            paragraphs.append(line)
    return "\n".join(paragraphs)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run offline RedRob competition ranking.")
    parser.add_argument("--candidates", required=True, help="Path to candidates JSON, JSONL, or JSONL.GZ.")
    parser.add_argument("--job", required=True, help="Path to job description .docx or text file.")
    parser.add_argument("--output", required=True, help="Path to write submission CSV.")
    args = parser.parse_args()
    run_competition_ranking(args.candidates, args.job, args.output)
    print(f"Wrote valid submission to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
