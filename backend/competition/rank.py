from __future__ import annotations

import argparse
import hashlib
import csv
import heapq
import os
import re
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from backend.competition.evidence_calibrator import (
    AI_INFRA_TERMS,
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
from backend.competition.evaluate import _extract_career_signals, _extract_behavioral_signals
from backend.competition.reasoning_generator import generate_prose_reasoning, _extract_career_signals as _prose_career_sigs

TOP_K = 100
MAX_EVIDENCE_ADJUSTMENT = 0.100

# ---------------------------------------------------------------------------
# Phase 8C.4: Production ownership disclaimer detection
# JD requires: "handled embedding drift, index refresh, retrieval-quality
# regression in production" (item 1, Things you absolutely need).
# Candidates who explicitly state another team owned production deployment
# are self-reporting a disqualifier and receive a 0.5x multiplier.
# ---------------------------------------------------------------------------
_PROD_DISCLAIMER_PHRASES: tuple[str, ...] = (
    "production deployment was handled by",
    "deployment was handled by the platform",
    "pure ml side of the work",
    "production was handled by",
    "ops team handled",
    "platform team handled",
    "platform handled the deployment",
    "infra team handled",
)
_PROD_DISCLAIMER_MULTIPLIER: float = 0.5
# ---------------------------------------------------------------------------
# Phase 8B.3 reranker configuration (headroom-scaled depth + behavioral bonuses)
# ---------------------------------------------------------------------------
_RERANK_POOL_SIZE: int = 300

# ---------------------------------------------------------------------------
# Phase 8B.3: Headroom-scaled depth bonus (inlined to avoid circular import
# with rerank_experiment.py which imports rank at module level)
#
# Formula: bonus = (1 - p7_adj / P7_MAX_ADJ) * (effective_depth / 4) * MAX_RERANK_BONUS
# Only adds credit for evidence NOT already captured by Phase 7 calibration.
# ---------------------------------------------------------------------------
_P7_MAX_ADJ: float = 0.100
_MAX_RERANK_BONUS: float = 0.030

# Context-pattern eval detection (verbatim from rerank_experiment.py Fix 2)
_EVAL_CONTEXT_PATTERNS: list[tuple[str, tuple[str, ...] | None]] = [
    ("relevance",         ("metric", "measure", "quality", "label", "judgment", "judgement", "feedback")),
    ("ranking",           ("metric", "measure", "quality", "label", "judgment", "judgement", "improved", "improvement")),
    ("retrieval",         ("metric", "measure", "quality", "label", "improved", "improvement")),
    ("click",             ("through", "data", "feedback", "label")),
    ("learning-to-rank",  None),
    ("ltr",               None),
    ("relevance label",   None),
    ("relevance feedback",None),
    ("held-out",          None),
    ("held out eval",     None),
    ("human judgment",    None),
    ("human judgement",   None),
    ("human label",       None),
    ("eval set",          None),
    ("eval workflow",     None),
    ("offline",           ("eval", "evaluation", "test", "benchmark", "metric")),
]


def _has_eval_context(career_lower: str) -> bool:
    """Return True if career text contains patterns implying evaluation maturity."""
    for anchor, context_words in _EVAL_CONTEXT_PATTERNS:
        if anchor not in career_lower:
            continue
        if context_words is None:
            return True
        pos = career_lower.find(anchor)
        while pos != -1:
            window = career_lower[max(0, pos - 100): pos + 200]
            if any(cw in window for cw in context_words):
                return True
            pos = career_lower.find(anchor, pos + 1)
    return False


def _headroom_depth_bonus(p7_adjustment: float, career_lower: str, career_sigs: dict) -> float:
    """Phase 8B.3 Fix 1: headroom-scaled evidence depth bonus."""
    has_eval = career_sigs["has_eval_maturity"] or _has_eval_context(career_lower)
    has_retrieval = career_sigs["has_retrieval"]
    has_system = career_sigs["has_system"]
    has_career_ev = career_sigs["has_career_evidence"]
    effective_depth = sum([has_eval, has_retrieval, has_system, has_career_ev])
    if effective_depth == 0:
        return 0.0
    headroom = max(0.0, 1.0 - p7_adjustment / _P7_MAX_ADJ)
    return round(headroom * (effective_depth / 4.0) * _MAX_RERANK_BONUS, 6)


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
    """
    Full Phase 8 production pipeline:
      Stage 1: Phase 8C.4 base scoring with production disclaimer detection
               → top-300 heap (wider than top-100 to allow reranker to work)
      Stage 2: Phase 8B.3 reranker (headroom depth bonus + behavioral + surface/trap penalties)
      Stage 3: Phase 8E.1 prose reasoning (spec-compliant plain-language)
    CPU-only. No external API calls.
    """
    pipeline_start = time.time()
    configure_offline_environment()

    # -- Input preparation ---------------------------------------------------
    print(f"[rank] Reading job description: {job_path}", flush=True)
    job_text = read_job_text(job_path)
    job_analysis = analyze_job_description(job_text)
    job_terms = _important_terms(job_text)
    print(f"[rank] JD parsed — {len(job_analysis.core_skills)} core skills, {len(job_terms)} term signals", flush=True)

    # -----------------------------------------------------------------------
    # Stage 1: Phase 8C.4 base scoring — stream all 100K candidates into a
    # top-_RERANK_POOL_SIZE heap. The wider pool gives the Phase 8B.3 reranker
    # room to elevate candidates with strong career evidence that were slightly
    # depressed in the base score.
    # -----------------------------------------------------------------------
    print(f"[rank] Stage 1 — base scoring + evidence calibration (streaming candidates)", flush=True)
    stage1_start = time.time()
    top_pool: list[tuple[float, str, CompetitionCandidate]] = []
    seen_candidate_ids: set[str] = set()
    _progress_interval = 10_000

    for raw_candidate in iter_dataset_records(candidates_path):
        candidate_profile = adapt_redrob_candidate(raw_candidate)
        if not candidate_profile.candidate_id or candidate_profile.candidate_id in seen_candidate_ids:
            continue
        seen_candidate_ids.add(candidate_profile.candidate_id)
        core_signals = build_competition_core_signals(candidate_profile)
        base_score = _competition_score(candidate_profile, core_signals, job_analysis, job_terms)
        if len(top_pool) >= _RERANK_POOL_SIZE and base_score + MAX_EVIDENCE_ADJUSTMENT < top_pool[0][0]:
            pass  # skipped: score too low to enter pool even with max calibration
        else:
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
            if len(top_pool) < _RERANK_POOL_SIZE:
                heapq.heappush(top_pool, heap_item)
            elif heap_item > top_pool[0]:
                heapq.heapreplace(top_pool, heap_item)
        n = len(seen_candidate_ids)
        if n % _progress_interval == 0:
            elapsed = time.time() - stage1_start
            print(f"[rank]   ... {n:>7,} candidates scored  |  pool: {len(top_pool):<3}  |  {elapsed:>3.0f}s elapsed", flush=True)

    stage1_elapsed = time.time() - stage1_start
    print(f"[rank] Stage 1 complete — {len(seen_candidate_ids):,} candidates scored in {stage1_elapsed:.1f}s", flush=True)
    print(f"[rank]   Shortlist pool: {len(top_pool)} candidates (top-{_RERANK_POOL_SIZE} by calibrated score)", flush=True)

    pool = [
        item[2]
        for item in sorted(top_pool, key=lambda item: (-item[2].score, item[2].candidate_id))
    ]

    # Re-load full profiles for the pool (profile was kept in stage 1, but reload
    # to ensure a clean state for evidence extraction).
    print(f"[rank] Reloading {len(pool)} pool profiles for reranking...", flush=True)
    pool_cids = {c.candidate_id for c in pool}
    profiles: dict[str, Any] = {}
    for raw_candidate in iter_dataset_records(candidates_path):
        cid = raw_candidate.get("candidate_id", "")
        if cid in pool_cids:
            profiles[cid] = adapt_redrob_candidate(raw_candidate)
            if len(profiles) == len(pool_cids):
                break

    # -----------------------------------------------------------------------
    # Stage 2: Phase 8B.3 reranker
    # Headroom-scaled evidence depth bonus + behavioral bonus + surface/trap penalties.
    # -----------------------------------------------------------------------
    print(f"[rank] Stage 2 — reranking {len(pool)} candidates (evidence depth + behavioral signals)", flush=True)
    stage2_start = time.time()
    reranked: list[dict[str, Any]] = []
    for c in pool:
        p = profiles[c.candidate_id]
        career_text = normalize_whitespace(
            " ".join(str(item.get("description", "")) for item in p.career_history)
        ).lower()
        career_sigs = _extract_career_signals(career_text)
        beh_sigs = _extract_behavioral_signals(p.redrob_signals or {})

        depth_bonus = _headroom_depth_bonus(c.calibration.adjustment, career_text, career_sigs)
        beh_bonus = (beh_sigs["availability_score"] + beh_sigs["engagement_score"]) * 0.005
        surface_penalty = -0.030 if career_sigs["surface_match_risk"] else 0.0
        trap_penalty = -0.050 if c.calibration.trap_flags else 0.0

        reranked.append({
            "candidate_id": c.candidate_id,
            "score": round(c.score + depth_bonus + beh_bonus + surface_penalty + trap_penalty, 6),
            "calibration": c.calibration,
        })

    reranked.sort(key=lambda x: (-x["score"], x["candidate_id"]))
    top100_items = reranked[:TOP_K]
    stage2_elapsed = time.time() - stage2_start
    print(f"[rank] Stage 2 complete — {len(reranked)} candidates reranked in {stage2_elapsed:.3f}s  →  top {TOP_K} selected", flush=True)

    # -----------------------------------------------------------------------
    # Stage 3: Phase 8E.1 prose reasoning
    # Natural plain-language sentences meeting all 6 Stage 4 spec checks.
    # -----------------------------------------------------------------------
    print(f"[rank] Stage 3 — generating reasoning for {TOP_K} candidates", flush=True)
    stage3_start = time.time()
    ranked_candidates: list[CompetitionCandidate] = []
    for rank_pos, item in enumerate(top100_items, start=1):
        p = profiles[item["candidate_id"]]
        cal = item["calibration"]
        career_text = normalize_whitespace(
            " ".join(str(h.get("description", "")) for h in p.career_history)
        ).lower()
        career_sigs_prose = _prose_career_sigs(career_text)
        reasoning = generate_prose_reasoning(p, cal, career_text, career_sigs_prose, rank_pos)
        ranked_candidates.append(
            CompetitionCandidate(
                candidate_id=item["candidate_id"],
                score=item["score"],
                reasoning=reasoning,
            )
        )
    stage3_elapsed = time.time() - stage3_start
    print(f"[rank] Stage 3 complete — reasoning generated in {stage3_elapsed:.3f}s", flush=True)

    # -- Export + validation -------------------------------------------------
    resolved_output = Path(output_path).resolve()
    print(f"[rank] Writing submission: {resolved_output}", flush=True)
    write_submission_csv(ranked_candidates, output_path)
    errors = validate_submission(output_path)
    if errors:
        raise ValueError("Invalid competition submission: " + " ".join(errors))

    total_elapsed = time.time() - pipeline_start
    print(f"[rank] Validation PASS", flush=True)
    print(f"[rank] ──────────────────────────────────────────", flush=True)
    print(f"[rank]  Candidates processed : {len(seen_candidate_ids):,}", flush=True)
    print(f"[rank]  Shortlist pool size  : {len(pool)}", flush=True)
    print(f"[rank]  Output CSV           : {resolved_output}", flush=True)
    print(f"[rank]  Total runtime        : {total_elapsed:.1f}s", flush=True)
    print(f"[rank] ──────────────────────────────────────────", flush=True)
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


def _career_evidence_score(profile) -> float:
    """
    Phase 8C.4: Normalized count of JD-relevant AI infra terms in career text.
    Applies a 0.5x penalty when the candidate explicitly disclaims production ownership.
    """
    career_text = normalize_whitespace(
        " ".join(str(item.get("description") or "") for item in profile.career_history)
    ).lower()
    if not career_text:
        return 0.0
    hits = sum(1 for term in AI_INFRA_TERMS if term in career_text)
    base_score = min(hits, 5) / 5.0
    if any(phrase in career_text for phrase in _PROD_DISCLAIMER_PHRASES):
        base_score *= _PROD_DISCLAIMER_MULTIPLIER
    return base_score


def _competition_score(profile, core_signals: dict[str, float], job_analysis, job_terms: set[str]) -> float:
    """Phase 8C.4 base score: 6-term weighted formula with career evidence term."""
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
    career_evidence = _career_evidence_score(profile)

    score = (
        skill_overlap    * 0.26
        + group_overlap  * 0.16
        + term_overlap   * 0.18
        + experience_fit * 0.12
        + signal_average * 0.20
        + career_evidence * 0.08
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
