from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from backend.competition.rank import read_job_text
from backend.utils.skill_taxonomy import extract_skills_from_text, normalize_whitespace


MUST_HAVE_SIGNAL_GROUPS = {
    "ai_ml": [
        "machine learning systems",
        "embeddings",
        "retrieval systems",
        "ranking systems",
        "recommendation systems",
        "nlp",
        "llm systems",
    ],
    "vector_search": [
        "faiss",
        "pinecone",
        "weaviate",
        "qdrant",
        "milvus",
        "elasticsearch",
        "opensearch",
    ],
    "production_ml": [
        "deployed ml",
        "inference",
        "model serving",
        "monitoring",
        "evaluation",
    ],
    "ranking_evaluation": [
        "ndcg",
        "mrr",
        "map",
        "a/b testing",
    ],
    "engineering": [
        "python",
        "backend systems",
        "distributed systems",
        "cloud",
    ],
    "founder_team_fit": [
        "startup experience",
        "ownership",
        "built",
        "shipped",
        "scaled",
    ],
}

NEGATIVE_SIGNAL_GROUPS = {
    "pure_research_only": ["pure research", "academic labs", "research-only"],
    "wrapper_only_ai": ["langchain", "openai", "wrappers", "framework enthusiasts"],
    "tutorial_projects_only": ["tutorial", "demo"],
    "no_production_deployment": ["without any production deployment", "no production deployment"],
    "management_only": ["management-only", "hasn't written production code"],
    "consulting_only": ["consulting firms", "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini"],
    "unrelated_specialty": ["computer vision", "speech", "robotics"],
}

TERM_ALIASES = {
    "machine learning systems": ["modern ml systems", "machine learning", "ml systems"],
    "embeddings": ["embedding", "embeddings", "sentence-transformers", "bge", "e5"],
    "retrieval systems": ["retrieval", "hybrid retrieval", "retrieval systems"],
    "ranking systems": ["ranking", "ranker", "ranking systems"],
    "recommendation systems": ["recommendation system", "recommendation systems", "recommendations"],
    "nlp": ["nlp", "natural language"],
    "llm systems": ["llm", "llms", "fine-tuning", "lora", "qlora"],
    "deployed ml": ["deployed", "production deployment", "real users"],
    "model serving": ["model serving", "serving"],
    "a/b testing": ["a/b testing", "ab testing"],
    "backend systems": ["backend", "backend systems"],
    "distributed systems": ["distributed systems", "large-scale"],
    "startup experience": ["startup", "series a", "founding"],
    "ownership": ["own", "owned", "ownership"],
    "scaled": ["scale", "scaled", "scalable"],
}


def analyze_jd_signals(job_path: str | Path, output_path: str | Path = "outputs/jd_signal_profile.json") -> dict[str, Any]:
    job_text = read_job_text(job_path)
    normalized = normalize_whitespace(job_text).lower()
    profile = {
        "job_path": str(job_path),
        "role_title": _role_title(job_text),
        "documented_experience_range": _experience_range(job_text),
        "extracted_skills": extract_skills_from_text(job_text),
        "must_have_positive_signals": _group_hits(normalized, MUST_HAVE_SIGNAL_GROUPS),
        "negative_jd_signals": _group_hits(normalized, NEGATIVE_SIGNAL_GROUPS),
        "analysis_note": "Signal extraction only; no ranking weights or scoring changes applied.",
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return profile


def _group_hits(text: str, groups: dict[str, list[str]]) -> dict[str, list[dict[str, Any]]]:
    output = {}
    for group, terms in groups.items():
        output[group] = [
            {
                "signal": term,
                "present_in_jd": _term_present(text, term),
                "aliases_checked": TERM_ALIASES.get(term, [term]),
            }
            for term in terms
        ]
    return output


def _term_present(text: str, term: str) -> bool:
    return any(alias.lower() in text for alias in TERM_ALIASES.get(term, [term]))


def _role_title(job_text: str) -> str:
    first_line = (job_text or "").splitlines()[0] if job_text else ""
    return first_line.replace("Job Description:", "").strip() or "Unknown role"


def _experience_range(job_text: str) -> str:
    match = re.search(r"\b(\d+)\s*[–-]\s*(\d+)\s+years?\b", job_text or "", re.IGNORECASE)
    return f"{match.group(1)}-{match.group(2)} years" if match else "not detected"


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze JD-grounded RedRob signals.")
    parser.add_argument("--job", default="data/job_description.docx")
    parser.add_argument("--output", default="outputs/jd_signal_profile.json")
    args = parser.parse_args()
    analyze_jd_signals(args.job, args.output)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
