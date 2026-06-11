from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkResume:
    candidate_name: str
    resume_text: str


@dataclass(frozen=True)
class RankingBenchmarkCase:
    name: str
    jd_text: str
    resumes: list[BenchmarkResume]
    expected_order: list[str]
    expected_rejections: list[str]
    hidden_gems: list[str]


BACKEND_TRUST_JD = """
Hiring a backend platform engineer for recruiter workflow software.

Responsibilities:
- Build Python and FastAPI services for ranking, retrieval, and workflow automation.
- Own PostgreSQL-backed APIs, deployment pipelines, and production reliability.
- Work with Docker, CI/CD, monitoring, and operational debugging.

Requirements:
- Python, FastAPI, PostgreSQL, REST APIs, Docker, CI/CD.
- Evidence of shipped backend systems and deployment ownership.

Preferred:
- Semantic retrieval, embeddings, Chroma, realtime systems, reliability work.
"""


RANKING_BENCHMARKS = [
    RankingBenchmarkCase(
        name="backend_platform_false_positive_suppression",
        jd_text=BACKEND_TRUST_JD,
        expected_order=[
            "Implementation Owner",
            "Deployment Backend",
            "Adjacent Hidden Gem",
            "Keyword Stuffer",
            "Shallow AI Resume",
        ],
        expected_rejections=["Keyword Stuffer", "Shallow AI Resume"],
        hidden_gems=["Adjacent Hidden Gem"],
        resumes=[
            BenchmarkResume(
                candidate_name="Implementation Owner",
                resume_text="""
Implementation Owner

SKILLS
Python, FastAPI, PostgreSQL, Docker, CI/CD, REST APIs

PROJECTS
Recruiter Workflow API
Built FastAPI orchestration services for candidate ranking workflows with PostgreSQL persistence, Docker deployment, CI/CD release checks, and monitoring for failed PDF processing.

EXPERIENCE
Backend Engineer
Owned production API reliability, debugging request failures, and release rollback procedures for internal hiring systems.
""",
            ),
            BenchmarkResume(
                candidate_name="Deployment Backend",
                resume_text="""
Deployment Backend

SKILLS
Python, FastAPI, Docker, AWS, PostgreSQL, REST APIs

PROJECTS
Ops Service Platform
Deployed backend API services with Docker on AWS, configured CI/CD pipelines, and monitored production jobs for workflow automation.
""",
            ),
            BenchmarkResume(
                candidate_name="Adjacent Hidden Gem",
                resume_text="""
Adjacent Hidden Gem

SKILLS
Node.js, Supabase, PostgreSQL, Realtime, APIs

PROJECTS
Auction Control Room
Built realtime auction synchronization with backend arbitration, reconnect handling, and PostgreSQL event persistence for live bidding rooms.
""",
            ),
            BenchmarkResume(
                candidate_name="Keyword Stuffer",
                resume_text="""
Keyword Stuffer

SUMMARY
Experienced full-stack AI backend platform engineer with Python FastAPI PostgreSQL Docker CI/CD AWS monitoring reliability scalable architecture APIs retrieval embeddings Chroma and production systems.

SKILLS
Python, FastAPI, PostgreSQL, Docker, CI/CD, AWS, monitoring, retrieval, embeddings, Chroma, scalable systems, APIs
""",
            ),
            BenchmarkResume(
                candidate_name="Shallow AI Resume",
                resume_text="""
Shallow AI Resume

SUMMARY
Worked with AI and machine learning. Familiar with LLMs, embeddings, vector databases, and retrieval.

SKILLS
AI, LLM, OpenAI, Chroma, Python, APIs

PROJECTS
AI Demo
Created a chatbot demo for coursework.
""",
            ),
        ],
    )
]
