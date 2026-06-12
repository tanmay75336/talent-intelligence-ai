"""
Phase 8E.0 — Reasoning Quality Improvement

RANKING IS FROZEN. Only the reasoning column is modified.

Issues found in phase8c4 reasoning:
  1. Evidence snippet repetition: 25/100 candidates share the same evidence sentence,
     18/100 share another, etc. — because best_evidence_for_calibration pulls from
     shared synthetic career description templates.
  2. JD connection sentence repetition: 19 candidates share one template variant.
  3. No rank-consistency signaling: ranks 90-100 sound identical to ranks 1-10.
  4. The spec's Stage 4 check requires "specific facts from the candidate's profile
     (years of experience, current title, named skills, signal values)" — the
     current reasoning satisfies this for the opening but the middle evidence
     sentence often provides no unique differentiator.

FIX STRATEGY (no ranking changes):
  - Anchor reasoning on profile-unique facts:
      current_title, current_company, yoe, specific skills from matched set,
      evidence depth, evaluation maturity, behavioral signals
  - Use career-text evidence ONLY when it is NOT a shared template prefix
    (detected by checking against known repeated openings)
  - Add rank-appropriate confidence framing for lower ranks
  - Keep all assertions grounded in actual candidate data
  - No scores, ranks, or candidate ordering changes

Output: submission_phase8e0.csv (identical ranks/scores to phase8c4)
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, ".")

from backend.dataset_intelligence.loader import iter_dataset_records
from backend.competition.redrob_adapter import adapt_redrob_candidate
from backend.competition.evidence_calibrator import (
    calibrate_candidate_evidence,
    AI_INFRA_TERMS,
    EVALUATION_MATURITY_TERMS,
)
from backend.competition.evaluate import _extract_career_signals, _extract_behavioral_signals
from backend.utils.skill_taxonomy import normalize_whitespace
from backend.competition.validate_submission import validate_submission


# ---------------------------------------------------------------------------
# Shared template detection — these are the exact prefixes of repeated career
# description templates in the dataset. When the best_evidence sentence starts
# with one of these, we skip it and anchor on profile-unique facts instead.
# ---------------------------------------------------------------------------
_SHARED_TEMPLATE_PREFIXES = (
    "built the document ingestion pipeline",
    "built a content recommendation system serving",
    "the system uses item-item similarity",
    "built and operated production ml pipelines",
    "owned the end-to-end ranking pipeline",
    "the architecture combined bm25 + dense retrieval",
    "reported search-relevance improvement",
    "built and shipped a production recommendation system",
    "built recommendation-style features at a mid-stage startup",
    "developed a semantic search feature for an internal knowledge base",
    "implemented a rag-based customer support chatbot",
    "owned the ranking layer for an e-commerce search product",
    "built a rag-based ranking pipeline serving 50m+",
    "fine-tuned llama-2-7b and mistral-7b",
    "designed the ranking layer for the company's flagship product",
    "led the migration from keyword-based to embedding-based search",
    "built and shipped a production recommendation system at a marketplace product, going from offline experimentation to live a/b test",
    "built a content recommendation system serving 10m+ users",
)

# ---------------------------------------------------------------------------
# Official JD required capabilities — used to select which skills to mention
# ---------------------------------------------------------------------------
RETRIEVAL_SKILLS = {
    "FAISS", "Pinecone", "Weaviate", "Qdrant", "Milvus", "Elasticsearch",
    "OpenSearch", "pgvector", "Sentence Transformers", "Vector Search", "Embeddings",
    "Semantic Search", "BM25", "Information Retrieval",
}
RANKING_SKILLS = {
    "Learning to Rank", "Recommendation Systems", "Search Ranking",
    "Learning-to-Rank", "LTR",
}
EVAL_SKILLS = {
    "MLflow", "Weights & Biases", "Kubeflow",
}
LLM_FINE_TUNE_SKILLS = {
    "LoRA", "QLoRA", "PEFT", "Fine-tuning LLMs", "LLM Fine-tuning",
}


def _is_shared_template(text: str) -> bool:
    """Return True if the evidence snippet starts with a known shared template."""
    t = text.lower().strip()
    return any(t.startswith(prefix) for prefix in _SHARED_TEMPLATE_PREFIXES)


def _pick_unique_skills(profile, n: int = 3) -> list[str]:
    """
    Select the most JD-relevant skills that are actually in the profile.
    Priority order: retrieval infra > ranking > LLM fine-tuning > eval tools
    """
    skills = set(profile.skills)
    result = []
    for group in [RETRIEVAL_SKILLS, RANKING_SKILLS, LLM_FINE_TUNE_SKILLS, EVAL_SKILLS]:
        for skill in profile.skills:  # preserve order from profile
            if skill in group and skill not in result:
                result.append(skill)
            if len(result) >= n:
                return result
    return result[:n]


def _evidence_depth_phrase(depth: int, has_retrieval: bool, has_eval: bool) -> str:
    """Convert depth/signal flags to a concise evidence summary phrase."""
    if depth >= 4 and has_retrieval and has_eval:
        return "full-stack evidence: retrieval systems, evaluation frameworks, and production ownership"
    elif depth >= 4 and has_retrieval:
        return "strong career evidence across retrieval, embeddings, and production systems"
    elif depth >= 3 and has_retrieval:
        return "demonstrated retrieval and production system experience"
    elif depth >= 3 and has_eval:
        return "ranking/ML experience with evaluation rigor"
    elif depth >= 2:
        return "relevant AI/ML career evidence with production context"
    else:
        return "adjacent technical background"


def _rank_confidence_phrase(rank: int, depth: int, has_retrieval: bool, cal) -> str:
    """Generate a rank-appropriate confidence framing."""
    if rank <= 10:
        return ""  # top-10 reasoning stands on its own strength
    elif rank <= 30:
        return ""  # still strong, no hedging needed
    elif rank <= 50:
        if depth < 3 or not has_retrieval:
            return "Ranked in top-50 with some gaps vs top-tier candidates"
        return ""
    elif rank <= 75:
        if cal.trap_flags:
            return f"Boundary candidate: {cal.trap_flags[0].replace('_', ' ')}"
        elif depth < 3:
            return "Included at top-75 boundary; evidence depth lower than top-50"
        return "Qualified at top-75 boundary; solid technical background"
    else:  # 76-100
        if cal.trap_flags:
            return f"Caveat: {cal.trap_flags[0].replace('_', ' ')}"
        elif not has_retrieval:
            return "Included at cutoff; retrieval/vector infra evidence partial"
        else:
            return "Boundary inclusion at rank 76–100; core capabilities present but lower evidence depth"


def _behavioral_facts(signals: dict) -> str:
    """Format behavioral signals as specific facts for Stage 4 review."""
    if not signals:
        return ""
    facts = []
    if signals.get("open_to_work_flag") is True:
        facts.append("open to work")
    notice = signals.get("notice_period_days")
    if isinstance(notice, (int, float)) and notice <= 30:
        facts.append(f"{int(notice)}-day notice period")
    if signals.get("willing_to_relocate") is True:
        facts.append("willing to relocate")
    rr = signals.get("recruiter_response_rate")
    if isinstance(rr, (int, float)) and rr >= 0.7:
        facts.append(f"{rr:.0%} recruiter response rate")
    gh = signals.get("github_activity_score")
    if isinstance(gh, (int, float)) and gh >= 50:
        facts.append(f"GitHub activity score {gh:.0f}")
    interview = signals.get("interview_completion_rate")
    if isinstance(interview, (int, float)) and interview >= 0.8:
        facts.append(f"{interview:.0%} interview completion")
    return (", ".join(facts[:3])) if facts else ""


def _eval_evidence_phrase(career_text: str) -> str:
    """Check for evaluation maturity and return a specific phrase if found."""
    ct = career_text.lower()
    hits = []
    if "ndcg" in ct:
        hits.append("NDCG")
    if "mrr" in ct:
        hits.append("MRR")
    if "a/b test" in ct or "ab test" in ct:
        hits.append("A/B testing")
    if "offline eval" in ct or "offline-to-online" in ct or "offline evaluation" in ct:
        hits.append("offline evaluation")
    if "evaluation framework" in ct:
        hits.append("eval framework design")
    if "recall@" in ct or "precision@" in ct:
        hits.append("retrieval metrics")
    return ", ".join(hits[:2]) if hits else ""


def generate_reasoning(
    profile,
    cal,
    career_text: str,
    career_sigs: dict,
    rank: int,
) -> str:
    """
    Generate a reasoning string grounded in profile-unique facts.

    Design decisions:
    - Sentence 1: leads with the profile's own skills list + ownership verb.
      Each candidate's skills list is genuinely distinct (not from shared templates).
    - Sentence 2: eval quality + behavioral signals + rank-appropriate confidence.
      Also profile-unique (eval metrics, notice period, GitHub score).
    - Deliberately avoids career text content — career descriptions in this dataset
      are shared synthetic templates and would produce identical evidence sentences.

    All assertions are grounded in real candidate data. No hallucination.
    """
    yoe = profile.years_of_experience
    title = profile.structured_profile.get("current_title", "Engineer")
    company = profile.structured_profile.get("current_company", "current employer")
    depth = career_sigs["evidence_depth"]
    has_retrieval = career_sigs["has_retrieval"]
    has_eval = career_sigs["has_eval_maturity"]
    ct_lower = career_text.lower()
    own_hits = set(cal.ownership_hits)
    prod_hits = set(cal.production_hits)
    ai_hits = set(cal.career_ai_infra_hits)

    # ---------------------------------------------------------------
    # YoE context (contributes uniqueness + JD-relevant framing)
    # ---------------------------------------------------------------
    if 5.0 <= yoe <= 9.0:
        yoe_context = f"{yoe:.1f}y {title} at {company}"
    elif yoe < 5.0:
        yoe_context = f"{yoe:.1f}y {title} at {company} — below target 5-9y band"
    else:
        yoe_context = f"{yoe:.1f}y {title} at {company} — above typical target band"

    # ---------------------------------------------------------------
    # Profile-unique skills — the PRIMARY differentiator per candidate.
    # Each candidate's skills list is distinct; career text is shared templates.
    # Retrieval infra first (highest JD relevance), then ranking, then LLM.
    # ---------------------------------------------------------------
    retrieval_skills = [s for s in profile.skills if s in RETRIEVAL_SKILLS]
    ranking_skills   = [s for s in profile.skills if s in RANKING_SKILLS]
    llm_skills       = [s for s in profile.skills if s in LLM_FINE_TUNE_SKILLS]

    skill_parts = []
    if retrieval_skills:
        skill_parts.append(f"retrieval/vector ({', '.join(retrieval_skills[:3])})")
    if ranking_skills:
        skill_parts.append(f"ranking ({', '.join(ranking_skills[:2])})")
    if llm_skills:
        skill_parts.append(f"LLM fine-tuning ({', '.join(llm_skills[:2])})")
    if not skill_parts and profile.skills:
        # Fall back to any skills in profile
        skill_parts.append(", ".join(profile.skills[:4]))

    # ---------------------------------------------------------------
    # Ownership verb
    # ---------------------------------------------------------------
    if "built" in own_hits and prod_hits:
        verb_phrase = "built and shipped"
    elif "owned" in own_hits:
        verb_phrase = "owned"
    elif "designed" in own_hits:
        verb_phrase = "designed"
    elif "shipped" in own_hits:
        verb_phrase = "shipped"
    elif own_hits:
        verb_phrase = sorted(own_hits)[0]
    elif ai_hits:
        verb_phrase = "worked on"
    else:
        verb_phrase = "applied"

    # ---------------------------------------------------------------
    # Sentence 1: "[YoE] [Title] at [Company]; built and shipped:
    #              retrieval/vector (FAISS, Qdrant); ranking (LTR)."
    # ---------------------------------------------------------------
    if skill_parts:
        sentence1 = f"{yoe_context}; {verb_phrase}: {'; '.join(skill_parts)}"
    else:
        sentence1 = yoe_context

    # ---------------------------------------------------------------
    # Evidence quality descriptor (career depth + retrieval + eval)
    # These are from career signals (not shared template text directly)
    # ---------------------------------------------------------------
    eval_phrase = _eval_evidence_phrase(career_text)
    evidence_quals = []
    if depth >= 4:
        evidence_quals.append("multi-role depth")
    elif depth >= 3:
        evidence_quals.append("cross-role evidence")
    if has_retrieval:
        evidence_quals.append("retrieval system career evidence")
    if eval_phrase:
        evidence_quals.append(f"eval: {eval_phrase}")
    elif has_eval:
        evidence_quals.append("evaluation framework experience")

    # ---------------------------------------------------------------
    # Sentence 2: "Career: [evidence quality]; [behavioral facts]; [confidence]."
    # ---------------------------------------------------------------
    s2_parts = []
    if evidence_quals:
        s2_parts.append("Career: " + ", ".join(evidence_quals[:3]))
    beh = _behavioral_facts(profile.redrob_signals or {})
    if beh:
        s2_parts.append(beh)
    confidence = _rank_confidence_phrase(rank, depth, has_retrieval, cal)
    if confidence:
        s2_parts.append(confidence)
    sentence2 = "; ".join(s2_parts)

    # ---------------------------------------------------------------
    # Assemble
    # ---------------------------------------------------------------
    result = sentence1.rstrip(".") + (f". {sentence2}" if sentence2 else "") + "."
    return result

    """
    Generate a reasoning string that:
    1. Opens with profile-unique facts (title, company, YoE)
    2. Names specific JD-relevant skills from the profile
    3. Describes what systems the candidate built — using specific, non-templated evidence
    4. Adds eval/behavioral specifics when available
    5. Includes rank-appropriate confidence framing for 51-100
    6. Keeps each reasoning unique and grounded in the actual profile

    All assertions are grounded in real candidate data.
    No hallucination. No templated evidence snippets.
    """
    yoe = profile.years_of_experience
    title = profile.structured_profile.get("current_title", "Engineer")
    company = profile.structured_profile.get("current_company", "current employer")
    depth = career_sigs["evidence_depth"]
    has_retrieval = career_sigs["has_retrieval"]
    has_eval = career_sigs["has_eval_maturity"]
    has_system = career_sigs["has_system"]

    # ---------------------------------------------------------------
    # Part 1: Opening — profile-unique facts
    # ---------------------------------------------------------------
    opening = f"{yoe:.1f}y {title} at {company}"

    # ---------------------------------------------------------------
    # Part 2: JD-relevant skills (specific to this profile)
    # ---------------------------------------------------------------
    top_skills = _pick_unique_skills(profile, n=3)
    if top_skills:
        skill_phrase = f"Skills include {', '.join(top_skills)}"
    elif profile.skills:
        skill_phrase = f"Technical background in {', '.join(profile.skills[:3])}"
    else:
        skill_phrase = ""

    # ---------------------------------------------------------------
    # Part 3: Career evidence — use only non-templated evidence
    # Prefer eval/retrieval-specific sentences over general ones
    # ---------------------------------------------------------------
    eval_phrase = _eval_evidence_phrase(career_text)
    ct_lower = career_text.lower()

    # Build a specific career evidence phrase from signals, not template text
    ai_hits = set(cal.career_ai_infra_hits)
    prod_hits = set(cal.production_hits)
    own_hits = set(cal.ownership_hits)

    # Collect specific evidence components
    evidence_parts = []

    # Vector infra usage
    vecdb_hits = ai_hits & {"faiss", "pinecone", "weaviate", "qdrant", "milvus",
                             "elasticsearch", "opensearch", "vector database", "vector search",
                             "semantic search"}
    if vecdb_hits:
        evidence_parts.append(f"vector search with {', '.join(sorted(vecdb_hits)[:2])}")

    # RAG / retrieval pattern
    if "rag" in ai_hits:
        evidence_parts.append("RAG pipeline experience")
    elif "retrieval" in ai_hits and not vecdb_hits:
        evidence_parts.append("retrieval system experience")

    # Ranking / recommendation
    rank_hits = ai_hits & {"ranking", "recommendation", "recommender", "search ranking"}
    if rank_hits:
        evidence_parts.append(f"{'ranking' if 'ranking' in rank_hits else 'recommendation'} system work")

    # LLM fine-tuning (specific if present)
    if any(t in ct_lower for t in ["lora", "qlora", "peft", "fine-tun"]):
        evidence_parts.append("LLM fine-tuning")

    # Production ownership style
    if "built" in own_hits and prod_hits:
        ownership_phrase = "built and deployed to production"
    elif "owned" in own_hits:
        ownership_phrase = "owned end-to-end"
    elif "designed" in own_hits:
        ownership_phrase = "designed system architecture"
    elif "shipped" in own_hits:
        ownership_phrase = "shipped to production"
    elif own_hits:
        ownership_phrase = list(own_hits)[0]
    else:
        ownership_phrase = ""

    # Eval framework
    if eval_phrase:
        evidence_parts.append(f"evaluation using {eval_phrase}")

    # Compose evidence sentence
    if evidence_parts and ownership_phrase:
        ev_phrase = f"{ownership_phrase.capitalize()}: {', '.join(evidence_parts[:3])}"
    elif evidence_parts:
        ev_phrase = f"Career evidence in {', '.join(evidence_parts[:3])}"
    elif ownership_phrase:
        ev_phrase = f"Engineering work with {ownership_phrase}"
    else:
        ev_phrase = _evidence_depth_phrase(depth, has_retrieval, has_eval)

    # ---------------------------------------------------------------
    # Part 4: Evaluation specifics or system scale (if not templated)
    # ---------------------------------------------------------------
    extra = ""
    if "50m+" in ct_lower or "50 million" in ct_lower:
        extra = "High-scale experience (50M+ queries)"
    elif "10m+" in ct_lower or "10 million" in ct_lower:
        extra = "Large-scale system (10M+ users)"
    elif "35m+" in ct_lower:
        extra = "Large corpus (35M+ items)"
    elif eval_phrase and "ndcg" in eval_phrase.lower():
        extra = f"Rigorous eval: {eval_phrase}"
    elif "a/b test" in ct_lower:
        extra = "A/B testing infrastructure experience"

    # ---------------------------------------------------------------
    # Part 5: Behavioral signals (specific facts)
    # ---------------------------------------------------------------
    beh = _behavioral_facts(profile.redrob_signals or {})

    # ---------------------------------------------------------------
    # Part 6: Rank-appropriate confidence framing
    # ---------------------------------------------------------------
    confidence = _rank_confidence_phrase(rank, depth, has_retrieval, cal)

    # ---------------------------------------------------------------
    # Assemble — produce a 1-2 sentence result, all facts grounded
    # ---------------------------------------------------------------
    sentences = [opening]
    if skill_phrase:
        sentences.append(skill_phrase)
    sentences.append(ev_phrase)
    if extra and extra not in ev_phrase:
        sentences.append(extra)
    if beh:
        sentences.append(f"Availability: {beh}")
    if confidence:
        sentences.append(confidence)

    text = ". ".join(s.strip(". ") for s in sentences if s) + "."

    # Ensure uniqueness: append a deterministic suffix using candidate_id
    # (prevents two candidates with identical profiles from having identical reasoning)
    # Only add if text < 280 chars and we have room
    if len(text) < 260:
        cid_hash = int(hashlib.sha256(profile.candidate_id.encode()).hexdigest()[:4], 16)
        yoe_band = "ideal experience band" if 5.0 <= yoe <= 9.0 else (
            "experience just below target band" if yoe < 5.0 else "seasoned — above typical range"
        )
        text = text.rstrip(".") + f"; {yoe_band}."

    return text


def run_phase8e0(
    candidates_path: str = "data/candidates.jsonl",
    source_submission: str = "submission_phase8c4.csv",
    output_path: str = "submission_phase8e0.csv",
) -> None:
    """
    Generate improved reasoning for the phase8c4 submission.
    Preserves candidate_id, rank, and score exactly.
    Only the reasoning column changes.
    """
    print("Phase 8E.0: Improving reasoning quality (ranking frozen)...")

    # Load source submission — ranks and scores are truth
    with open(source_submission) as f:
        source_rows = {r["candidate_id"]: r for r in csv.DictReader(f)}
    top100_ids = set(source_rows.keys())

    # Load candidate profiles
    profiles = {}
    for raw in iter_dataset_records(candidates_path):
        cid = raw.get("candidate_id", "")
        if cid in top100_ids:
            profiles[cid] = adapt_redrob_candidate(raw)
        if len(profiles) == len(top100_ids):
            break

    print(f"  Loaded {len(profiles)} profiles. Generating improved reasoning...")

    # Generate reasoning for each candidate
    output_rows = []
    for cid, source_row in source_rows.items():
        rank = int(source_row["rank"])
        score = source_row["score"]
        p = profiles.get(cid)
        if p is None:
            output_rows.append({
                "candidate_id": cid,
                "rank": rank,
                "score": score,
                "reasoning": source_row.get("reasoning", ""),
            })
            continue

        cal = calibrate_candidate_evidence(p)
        career_text = normalize_whitespace(
            " ".join(str(h.get("description", "")) for h in p.career_history)
        ).lower()
        career_sigs = _extract_career_signals(career_text)

        reasoning = generate_reasoning(p, cal, career_text, career_sigs, rank)
        output_rows.append({
            "candidate_id": cid,
            "rank": rank,
            "score": score,
            "reasoning": reasoning,
        })

    # Sort by rank
    output_rows.sort(key=lambda x: int(x["rank"]))

    # Write output
    output = Path(output_path)
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["candidate_id", "rank", "score", "reasoning"])
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"  Written to {output_path}")

    # Validate
    errors = validate_submission(output_path)
    if errors:
        raise ValueError(f"Submission invalid: {errors}")
    print("  Validation passed.")

    # Diff check
    source_ranked = sorted(source_rows.values(), key=lambda x: int(x["rank"]))
    output_ranked = sorted(output_rows, key=lambda x: int(x["rank"]))
    assert len(source_ranked) == len(output_ranked) == 100, "Row count mismatch"
    for s, o in zip(source_ranked, output_ranked):
        assert s["candidate_id"] == o["candidate_id"], f"ID mismatch at rank {s['rank']}"
        assert s["rank"] == str(o["rank"]) or int(s["rank"]) == int(o["rank"]), f"Rank mismatch"
        assert abs(float(s["score"]) - float(o["score"])) < 1e-9, f"Score mismatch at rank {s['rank']}"
    print("  Diff check: 100/100 candidates identical rank+score. Only reasoning changed.")

    # Sample comparison
    print()
    print("=== SAMPLE BEFORE/AFTER (Ranks 1, 5, 50, 97, 100) ===")
    sample_ranks = {1, 5, 50, 97, 100}
    for o in output_ranked:
        if int(o["rank"]) in sample_ranks:
            s = source_rows[o["candidate_id"]]
            print(f"\nRank {o['rank']}:")
            print(f"  BEFORE: {s['reasoning']}")
            print(f"  AFTER:  {o['reasoning']}")

    # Variation check on output
    reasonings = [o["reasoning"] for o in output_rows]
    unique_count = len(set(reasonings))
    print(f"\n=== OUTPUT VARIATION ===")
    print(f"  Unique reasoning strings: {unique_count} / 100")
    from collections import Counter
    # Check 80-char evidence snippets (3rd sentence)
    ev_snippets = []
    for r in reasonings:
        parts = r.split(". ")
        ev_snippets.append(parts[2][:80] if len(parts) >= 3 else r[:80])
    ev_counter = Counter(ev_snippets)
    top_repeats = ev_counter.most_common(5)
    print(f"  Most repeated evidence snippets:")
    for snip, count in top_repeats:
        print(f"    [{count}x] {snip}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default="data/candidates.jsonl")
    parser.add_argument("--source", default="submission_phase8c4.csv")
    parser.add_argument("--output", default="submission_phase8e0.csv")
    args = parser.parse_args()
    run_phase8e0(args.candidates, args.source, args.output)
