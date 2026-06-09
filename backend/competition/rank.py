from __future__ import annotations

import argparse
import hashlib
import csv
import heapq
import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from backend.competition.evidence_calibrator import (
    EvidenceCalibration,
    best_evidence_for_calibration,
    calibrate_candidate_evidence,
)
from backend.competition.redrob_adapter import adapt_redrob_candidate
from backend.competition.validate_submission import validate_submission
from backend.dataset_intelligence.loader import iter_dataset_records
from backend.intelligence.candidate_engine import build_candidate_intelligence, build_competition_core_signals
from backend.parsers.jd_analyzer import analyze_job_description
from backend.utils.skill_taxonomy import (
    extract_domain_keywords,
    get_active_groups,
    normalize_whitespace,
    unique_preserve_order,
)

TOP_K = 100
MAX_EVIDENCE_ADJUSTMENT = 0.100


@dataclass
class CompetitionCandidate:
    candidate_id: str
    score: float
    reasoning: str = ""
    base_score: float = 0.0
    evidence_adjustment: float = 0.0
    calibration: EvidenceCalibration | None = None
    profile: Any | None = None
    evidence_library: dict[str, Any] | None = None


def run_competition_ranking(candidates_path: str | Path, job_path: str | Path, output_path: str | Path) -> list[CompetitionCandidate]:
    configure_offline_environment()
    job_text = read_job_text(job_path)
    job_analysis = analyze_job_description(job_text)
    job_terms = _important_terms(job_text)
    top_candidates: list[tuple[float, str, CompetitionCandidate]] = []
    seen_candidate_ids: set[str] = set()

    for raw_candidate in iter_dataset_records(candidates_path):
        candidate_profile = adapt_redrob_candidate(raw_candidate)
        if not candidate_profile.candidate_id or candidate_profile.candidate_id in seen_candidate_ids:
            continue
        seen_candidate_ids.add(candidate_profile.candidate_id)
        core_signals = build_competition_core_signals(candidate_profile)
        base_score = _competition_score(candidate_profile, core_signals, job_analysis, job_terms)
        if len(top_candidates) >= TOP_K and base_score + MAX_EVIDENCE_ADJUSTMENT < top_candidates[0][0]:
            continue
        calibration = calibrate_candidate_evidence(candidate_profile)
        score = _calibrated_score(base_score, calibration)
        candidate = CompetitionCandidate(
            candidate_id=candidate_profile.candidate_id,
            score=score,
            base_score=base_score,
            evidence_adjustment=calibration.adjustment,
            calibration=calibration,
            profile=candidate_profile,
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
    for candidate in ranked_candidates:
        if candidate.profile is not None:
            _, evidence_library = build_candidate_intelligence(candidate.profile)
            candidate.reasoning = _competition_reasoning(
                candidate.profile,
                job_analysis,
                evidence_library,
                candidate.calibration,
            )
            candidate.profile = None
            candidate.evidence_library = None
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
    # Use core_skills (excluding contextual AI mentions like OpenAI/LLM/RAG)
    # for precise skill matching to prevent generic AI terms from inflating scores.
    job_core_skills = set(job_analysis.core_skills)
    skill_overlap = _ratio(len(candidate_skills & job_core_skills), len(job_core_skills)) if job_core_skills else 0.0
    # Use all_skills for group-level overlap (broader category matching is OK)
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



def _calibrated_score(base_score: float, calibration: EvidenceCalibration) -> float:
    return round(max(0.0, min(1.0, base_score + calibration.adjustment)), 6)


def _competition_reasoning(
    profile,
    job_analysis,
    evidence_library: dict[str, Any],
    calibration: EvidenceCalibration | None = None,
) -> str:
    current_title = profile.structured_profile.get("current_title") or "candidate"
    current_company = profile.structured_profile.get("current_company") or "current company"
    years = profile.years_of_experience

    # --- Evidence sentence: pick best career evidence, truncate at sentence boundary ---
    evidence = ""
    if calibration:
        evidence = calibration.best_evidence or best_evidence_for_calibration(profile, calibration)
    evidence = evidence or _best_evidence_text(evidence_library) or profile.summary or profile.searchable_profile_text
    evidence = normalize_whitespace(evidence)
    evidence = _truncate_at_sentence(evidence, 180)

    # --- System-level contribution summary ---
    system_type = _system_type_label(calibration)
    jd_connection = _jd_connection_text(calibration, profile, job_analysis)

    # --- Limitations (only if data-supported) ---
    limitation = _evidence_based_limitation(calibration, profile)

    # --- Availability ---
    availability = _availability_text(profile.redrob_signals)

    # --- Assemble ---
    opening = f"{years:.1f}y {current_title} at {current_company}"
    if system_type:
        opening += f" ({system_type})"

    parts = [opening, jd_connection, evidence]
    if limitation:
        parts.append(limitation)
    if availability:
        parts.append(availability)
    return ". ".join(part.strip(" .") for part in parts if part).strip() + "."


def _system_type_label(calibration: EvidenceCalibration | None) -> str:
    """Infer the type of system the candidate has built from career evidence."""
    if not calibration or not calibration.career_ai_infra_hits:
        return ""
    hits = set(calibration.career_ai_infra_hits)
    labels = []
    if hits & {"retrieval", "rag", "semantic search"}:
        labels.append("retrieval")
    if hits & {"ranking", "search ranking"}:
        labels.append("ranking")
    if hits & {"recommendation", "recommender"}:
        labels.append("recommendation")
    if hits & {"embedding", "embeddings"}:
        labels.append("embeddings")
    if hits & {"faiss", "pinecone", "weaviate", "qdrant", "milvus", "elasticsearch", "opensearch", "vector database", "vector search"}:
        labels.append("vector infra")
    if hits & {"model serving", "inference"}:
        labels.append("inference")
    if not labels:
        return ""
    return " + ".join(labels[:3])


def _jd_connection_text(
    calibration: EvidenceCalibration | None,
    profile,
    job_analysis,
) -> str:
    """Generate varied JD connection text based on the type of evidence."""
    if not calibration:
        return "JD alignment based on structured profile data"

    career_hits = calibration.career_ai_infra_hits
    production = calibration.production_hits
    ownership = calibration.ownership_hits

    if not career_hits:
        matched = [s for s in profile.skills if s in set(job_analysis.all_skills)]
        if matched:
            return f"Skill profile aligns via {', '.join(matched[:3])}"
        return "Profile aligns with JD on general technical background"

    # Pick the 2-3 most distinctive career hits (avoid generic ones)
    distinctive_order = [
        "faiss", "pinecone", "weaviate", "qdrant", "milvus", "elasticsearch",
        "opensearch", "semantic search", "vector search", "vector database",
        "ranking", "recommendation", "recommender", "retrieval", "rag",
        "embedding", "embeddings", "model serving", "inference", "ml platform",
    ]
    ordered_hits = sorted(career_hits, key=lambda h: distinctive_order.index(h) if h in distinctive_order else 99)
    hit_text = ", ".join(ordered_hits[:3])

    # Vary phrasing based on evidence + deterministic selector
    if production and ownership:
        verbs = [v for v in ownership if v in {"built", "designed", "architected", "owned", "shipped"}]
        verb = verbs[0] if verbs else "built"
        # Use hash of hit_text to deterministically select a template variant
        variant = int(hashlib.sha256((hit_text + verb).encode("utf-8")).hexdigest(), 16) % 5
        if variant == 0:
            phrase = f"Career shows {verb} production systems around {hit_text}"
        elif variant == 1:
            phrase = f"Hands-on production work in {hit_text} — {verb} and deployed"
        elif variant == 2:
            phrase = f"Demonstrated {verb} and operating {hit_text} in production"
        elif variant == 3:
            phrase = f"Production-proven: {verb} systems using {hit_text}"
        else:
            phrase = f"{verb.capitalize()} production {hit_text} infrastructure with ownership"
        return phrase
    elif production:
        return f"Career evidence in {hit_text} deployed to production"
    elif ownership:
        return f"Career evidence in {hit_text} with engineering ownership"
    else:
        return f"Career mentions {hit_text}"



def _evidence_based_limitation(calibration: EvidenceCalibration | None, profile) -> str:
    """Add a brief limitation ONLY when trap flags or calibration data support it."""
    if not calibration:
        return ""
    flags = calibration.trap_flags
    if not flags:
        return ""
    # Map flags to human-readable short limitations
    flag_text = {
        "wrong_domain_standalone": "limited retrieval/ranking career evidence outside inference",
        "framework_only_ai_profile": "AI experience is primarily framework-level, not systems",
        "research_only_mismatch": "career is research-focused without production shipping evidence",
        "hands_off_senior": "seniority is management-track with limited hands-on ownership",
        "honeypot_weak_evidence": "employer background could not be independently verified",
        "honeypot_fictional_company": "employer background flagged as unverifiable",
        "non_ml_role_ai_keywords": "primary role is outside ML/AI despite related skill tags",
    }
    parts = [flag_text[f] for f in flags if f in flag_text]
    if not parts:
        return ""
    return "Caveat: " + parts[0]


def _availability_text(signals: dict[str, Any]) -> str:
    if not signals:
        return ""
    facts = []
    if signals.get("open_to_work_flag") is True:
        facts.append("open to work")
    notice = signals.get("notice_period_days")
    if isinstance(notice, (int, float)) and notice <= 30:
        facts.append(f"{int(notice)}d notice")
    if signals.get("willing_to_relocate") is True:
        facts.append("willing to relocate")
    response_rate = signals.get("recruiter_response_rate")
    if isinstance(response_rate, (int, float)) and response_rate >= 0.7:
        facts.append(f"{response_rate:.0%} recruiter response")
    github = signals.get("github_activity_score")
    if isinstance(github, (int, float)) and github >= 40:
        facts.append(f"GitHub {github:.0f}")
    return "Signals: " + ", ".join(facts[:3]) if facts else ""


def _truncate_at_sentence(text: str, max_len: int) -> str:
    """Truncate text at the last sentence boundary before max_len."""
    if len(text) <= max_len:
        return text
    # Find last sentence-ending punctuation before max_len
    truncated = text[:max_len]
    for end_char in [".", "!", "?"]:
        last_pos = truncated.rfind(end_char)
        if last_pos > max_len // 3:  # Don't truncate too aggressively
            return truncated[:last_pos + 1].rstrip()
    # No sentence boundary found — truncate at last space
    last_space = truncated.rfind(" ")
    if last_space > max_len // 2:
        return truncated[:last_space].rstrip() + "..."
    return truncated.rstrip() + "..."


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
