from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationTestCase:
    name: str
    jd_text: str
    resume_text: str
    expected_min_score: float
    expected_max_score: float
    expected_band: str


BASE_AI_FULLSTACK_JD = """
We are hiring a Full Stack AI Engineer to build AI-powered recruiter intelligence software.

Responsibilities:
- Build production-ready Next.js and React user interfaces for recruiter workflows.
- Develop FastAPI and Python backend APIs for ranking, semantic search, and data services.
- Integrate AI services, LLM APIs, and third-party APIs into SaaS product experiences.
- Ship deployed products using Vercel, Railway, Docker, PostgreSQL, and Supabase.
- Work across analytics dashboards, startup product delivery, and production systems.

Requirements:
- Strong experience with Python, FastAPI, React, Next.js, TypeScript, REST APIs, and PostgreSQL.
- Experience shipping SaaS applications, API integrations, and deployment pipelines.

Preferred:
- AI, LLM, Groq API, Anthropic, Docker, Supabase, Tailwind CSS, Vercel, Railway.
"""


EVALUATION_TEST_CASES = [
    EvaluationTestCase(
        name="perfect_fit_ai_fullstack",
        jd_text=BASE_AI_FULLSTACK_JD,
        expected_min_score=85,
        expected_max_score=95,
        expected_band="Perfect match",
        resume_text="""
Alex Mercer

PROFILE SUMMARY
Full-stack AI engineer building production SaaS systems with Next.js, FastAPI, PostgreSQL, and LLM API integrations.

TECHNICAL SKILLS
Python, FastAPI, React, Next.js, TypeScript, PostgreSQL, Supabase, Docker, Vercel, Railway, REST APIs, Anthropic, Groq API, Tailwind CSS

PROJECTS
TalentGraph AI
Next.js · TypeScript · FastAPI · PostgreSQL · Docker · Anthropic
Built an AI-powered recruitment intelligence platform with semantic candidate ranking, recruiter dashboards, and production API services.

SignalFlow Recruiter Copilot
React · FastAPI · Supabase · Vercel · Railway · Groq API
Shipped a SaaS workflow product with deployed APIs, AI reasoning, recruiter analytics, and third-party API integrations.

EXPERIENCE
Software Engineer
Developed production-grade full-stack applications, deployment pipelines, and AI-integrated product features for startup teams.

CERTIFICATIONS
AI Engineering Professional Certificate
""",
    ),
    EvaluationTestCase(
        name="strong_adjacent_fit_backend_platform",
        jd_text=BASE_AI_FULLSTACK_JD,
        expected_min_score=70,
        expected_max_score=85,
        expected_band="Strong adjacent fit",
        resume_text="""
Maya Patel

PROFILE SUMMARY
Backend and platform engineer with strong Python API development, deployment automation, and cloud delivery experience.

TECHNICAL SKILLS
Python, FastAPI, Docker, PostgreSQL, Redis, CI/CD, Railway, Render, REST APIs, OpenAI, GitHub

PROJECTS
OpsPilot API Platform
Python · FastAPI · PostgreSQL · Docker · CI/CD
Built API services and workflow automation for a SaaS platform with production deployment pipelines and analytics integrations.

AI Support Assistant
Python · OpenAI · REST APIs · Railway
Integrated AI APIs into internal tools to automate support triage and summarize operational data.

EXPERIENCE
Platform Engineer
Owned backend deployment workflows, production APIs, and cloud reliability for product engineering teams.
""",
    ),
    EvaluationTestCase(
        name="moderate_frontend_only_fit",
        jd_text=BASE_AI_FULLSTACK_JD,
        expected_min_score=45,
        expected_max_score=70,
        expected_band="Moderate fit",
        resume_text="""
Jordan Lee

PROFILE SUMMARY
Frontend engineer specializing in React, Next.js, and design systems for SaaS dashboards.

TECHNICAL SKILLS
React, Next.js, TypeScript, JavaScript, Tailwind CSS, Vercel, HTML, CSS

PROJECTS
GrowthBoard
Next.js · TypeScript · Tailwind CSS · Vercel
Built dashboard interfaces, analytics views, and recruiter-style filtering experiences for internal business teams.

EXPERIENCE
Frontend Developer
Delivered product UI features, performance improvements, and production Vercel deployments for customer-facing apps.
""",
    ),
    EvaluationTestCase(
        name="moderate_devops_fit",
        jd_text=BASE_AI_FULLSTACK_JD,
        expected_min_score=45,
        expected_max_score=70,
        expected_band="Moderate fit",
        resume_text="""
Priya Nair

PROFILE SUMMARY
DevOps engineer focused on containerized deployments, CI/CD, platform automation, and production cloud systems.

TECHNICAL SKILLS
Docker, Kubernetes, AWS, CI/CD, PostgreSQL, GitHub, Python

PROJECTS
DeployBridge
Docker · Kubernetes · AWS · CI/CD
Built deployment pipelines and production infrastructure for multi-service SaaS platforms with backend observability.

EXPERIENCE
DevOps Engineer
Managed deployment reliability, container orchestration, and cloud operations for product engineering teams.
""",
    ),
    EvaluationTestCase(
        name="weak_mismatch_generalist",
        jd_text=BASE_AI_FULLSTACK_JD,
        expected_min_score=15,
        expected_max_score=40,
        expected_band="Weak fit",
        resume_text="""
Samir Khan

PROFILE SUMMARY
General software developer with coursework projects and broad technical exposure.

TECHNICAL SKILLS
Java, HTML, CSS, Git

PROJECTS
Campus Portal
Java · HTML · CSS
Built a student portal for coursework submission and basic user login.

EXPERIENCE
Student Developer
Worked on small academic projects and collaborative assignments.
""",
    ),
    EvaluationTestCase(
        name="irrelevant_candidate",
        jd_text=BASE_AI_FULLSTACK_JD,
        expected_min_score=0,
        expected_max_score=15,
        expected_band="Irrelevant",
        resume_text="""
Neha Sharma

PROFILE SUMMARY
Human resources coordinator with experience in onboarding, policy documentation, and interview scheduling.

TECHNICAL SKILLS
Excel, Communication, Scheduling

EXPERIENCE
HR Coordinator
Managed onboarding workflows, interview scheduling, and people operations support.
""",
    ),
]
