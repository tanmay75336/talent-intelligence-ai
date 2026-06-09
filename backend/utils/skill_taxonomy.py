import re
from functools import lru_cache

SKILL_ALIASES = {
    "Python": ["python"],
    "Java": ["java"],
    "JavaScript": ["javascript"],
    "TypeScript": ["typescript"],
    "React": ["react", "react.js"],
    "Next.js": ["next.js", "nextjs"],
    "Node.js": ["node.js", "nodejs"],
    "Express": ["express", "express.js"],
    "FastAPI": ["fastapi"],
    "Django": ["django"],
    "Flask": ["flask"],
    "Spring Boot": ["spring boot"],
    "REST APIs": [
        "rest api",
        "rest apis",
        "restful api",
        "restful apis",
        "backend api",
        "backend apis",
        "api development",
    ],
    "GraphQL": ["graphql"],
    "HTML": ["html"],
    "CSS": ["css"],
    "Tailwind CSS": ["tailwind", "tailwind css"],
    "Vite": ["vite"],
    "MongoDB": ["mongodb", "mongo db"],
    "PostgreSQL": ["postgresql", "postgres", "postgre sql"],
    "Supabase": ["supabase"],
    "MySQL": ["mysql"],
    "Redis": ["redis"],
    "Docker": ["docker", "containerization"],
    "Kubernetes": ["kubernetes", "k8s"],
    "AWS": ["aws", "amazon web services"],
    "GCP": ["gcp", "google cloud", "google cloud platform"],
    "Azure": ["azure"],
    "Vercel": ["vercel"],
    "Railway": ["railway"],
    "Render": ["render"],
    "Netlify": ["netlify"],
    "Firebase": ["firebase"],
    "CI/CD": [
        "ci/cd",
        "ci cd",
        "continuous integration",
        "continuous deployment",
        "github actions",
        "gitlab ci",
    ],
    "Git": ["git"],
    "GitHub": ["github"],
    "Machine Learning": ["machine learning", "ml"],
    "AI": ["artificial intelligence", "ai-powered", "ai powered", "ai"],
    "LLM": ["llm", "llms", "large language model", "large language models"],
    "Generative AI": ["generative ai", "genai", "gen ai"],
    "NLP": ["nlp", "natural language processing"],
    "OpenAI": ["openai", "gpt-4", "gpt 4", "chatgpt"],
    "Anthropic": ["anthropic", "claude"],
    "Groq API": ["groq api", "groq"],
    "RAG": [
        "retrieval augmented generation",
        "retrieval-augmented generation",
        "rag",
    ],
    "Vector Database": ["vector database", "vector db", "embedding store"],
    "Elasticsearch": ["elasticsearch", "elastic search"],
    "OpenSearch": ["opensearch", "open search"],
    "FAISS": ["faiss"],
    "Pinecone": ["pinecone"],
    "Weaviate": ["weaviate"],
    "Qdrant": ["qdrant"],
    "Milvus": ["milvus"],
    "Sentence Transformers": ["sentence-transformers", "sentence transformers", "sbert"],
    "Recommendation Systems": ["recommendation system", "recommendation systems", "recommender system", "recommender systems"],
    "Information Retrieval": ["information retrieval"],
    "Search Ranking": ["search ranking", "learning-to-rank", "learning to rank"],
    "PyTorch": ["pytorch"],
    "TensorFlow": ["tensorflow"],
    "scikit-learn": ["scikit-learn", "sklearn"],
    "Hugging Face": ["hugging face", "huggingface", "hugging face transformers"],
    "API Integration": [
        "api integration",
        "api integrations",
        "third-party api",
        "third party api",
        "api integrations",
        "integrated api",
        "integrated apis",
        "payment gateway",
    ],
    "Stripe": ["stripe"],
    "Razorpay": ["razorpay"],
}

SKILL_GROUPS = {
    "frontend": {
        "React",
        "Next.js",
        "JavaScript",
        "TypeScript",
        "HTML",
        "CSS",
        "Tailwind CSS",
        "Vite",
    },
    "backend": {
        "Python",
        "Node.js",
        "Express",
        "FastAPI",
        "Django",
        "Flask",
        "Java",
        "Spring Boot",
        "REST APIs",
        "GraphQL",
    },
    "database": {
        "PostgreSQL",
        "Supabase",
        "MongoDB",
        "MySQL",
        "Redis",
        "Vector Database",
    },
    "deployment": {
        "Docker",
        "Kubernetes",
        "AWS",
        "GCP",
        "Azure",
        "Vercel",
        "Railway",
        "Render",
        "Netlify",
        "CI/CD",
    },
    "ai": {
        "AI",
        "Machine Learning",
        "LLM",
        "Generative AI",
        "NLP",
        "OpenAI",
        "Anthropic",
        "Groq API",
        "RAG",
        "Vector Database",
        "PyTorch",
        "TensorFlow",
        "scikit-learn",
        "Hugging Face",
    },
    "retrieval_infra": {
        "Elasticsearch",
        "OpenSearch",
        "FAISS",
        "Pinecone",
        "Weaviate",
        "Qdrant",
        "Milvus",
        "Vector Database",
        "Sentence Transformers",
        "Recommendation Systems",
        "Information Retrieval",
        "Search Ranking",
    },
    "api": {
        "REST APIs",
        "GraphQL",
        "API Integration",
        "Stripe",
        "Razorpay",
        "FastAPI",
        "Express",
        "Spring Boot",
    },
}

SKILL_ADJACENCY = {
    "Kubernetes": ["Docker", "AWS", "GCP", "Azure", "CI/CD"],
    "Docker": ["Kubernetes", "AWS", "Railway", "Render", "Vercel"],
    "React": ["Next.js", "JavaScript", "TypeScript", "HTML", "CSS"],
    "Next.js": ["React", "TypeScript", "JavaScript", "Vercel", "Tailwind CSS"],
    "FastAPI": ["Python", "REST APIs", "Node.js", "Express"],
    "REST APIs": ["FastAPI", "Express", "Spring Boot", "API Integration"],
    "API Integration": [
        "REST APIs",
        "FastAPI",
        "Express",
        "GraphQL",
        "Stripe",
        "Razorpay",
        "Groq API",
        "OpenAI",
        "Anthropic",
    ],
    "Supabase": ["PostgreSQL", "REST APIs", "Next.js"],
    "PostgreSQL": ["Supabase", "MySQL", "MongoDB"],
    "AWS": ["Docker", "CI/CD", "Vercel", "Railway", "Render", "GCP", "Azure"],
    "Vercel": ["Next.js", "React", "Netlify", "Railway", "Render"],
    "Railway": ["Render", "Vercel", "Docker", "AWS", "CI/CD"],
    "Render": ["Railway", "Vercel", "Docker", "AWS", "CI/CD"],
    "Machine Learning": ["Python", "AI", "LLM", "RAG"],
    "AI": ["Machine Learning", "LLM", "OpenAI", "Anthropic", "Groq API"],
    "LLM": ["AI", "OpenAI", "Anthropic", "RAG", "API Integration"],
    "OpenAI": ["LLM", "AI", "Anthropic", "Groq API", "API Integration"],
    "Anthropic": ["LLM", "AI", "OpenAI", "Groq API", "API Integration"],
    "Groq API": ["LLM", "AI", "OpenAI", "Anthropic", "API Integration"],
    "GraphQL": ["REST APIs", "API Integration", "Node.js"],
}

SKILL_ECOSYSTEM_SUPPORT = {
    "Next.js": {"React", "TypeScript", "JavaScript", "Vercel"},
    "React": {"Next.js", "TypeScript", "JavaScript"},
    "FastAPI": {"Python", "REST APIs"},
    "REST APIs": {"FastAPI", "Express", "Spring Boot", "API Integration"},
    "API Integration": {
        "REST APIs",
        "FastAPI",
        "Express",
        "GraphQL",
        "Stripe",
        "Razorpay",
        "Groq API",
        "OpenAI",
        "Anthropic",
    },
    "PostgreSQL": {"Supabase", "MySQL", "MongoDB"},
    "Kubernetes": {"Docker", "AWS", "GCP", "Azure", "CI/CD"},
}

DOMAIN_KEYWORDS = {
    "ai",
    "analytics",
    "api",
    "automation",
    "dashboard",
    "data",
    "deployment",
    "devops",
    "fintech",
    "full stack",
    "full-stack",
    "hiring",
    "intelligence",
    "monitoring",
    "platform",
    "portfolio",
    "production",
    "recruitment",
    "risk",
    "saas",
    "semantic",
    "startup",
    "workflow",
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "you",
    "your",
    "we",
    "our",
    "will",
    "this",
    "that",
    "are",
    "have",
    "has",
}


def _alias_pattern(alias):
    pattern = re.escape(alias.strip())
    pattern = pattern.replace(r"\ ", r"\s+")
    return rf"(?<![A-Za-z0-9]){pattern}(?![A-Za-z0-9])"


@lru_cache(maxsize=1)
def get_skill_patterns():
    return {
        skill: [re.compile(_alias_pattern(alias), re.IGNORECASE) for alias in aliases]
        for skill, aliases in SKILL_ALIASES.items()
    }


def normalize_whitespace(text):
    return re.sub(r"\s+", " ", text or "").strip()


def extract_skills_from_text(text):
    normalized_text = f" {normalize_whitespace(text).lower()} "
    found_skills = []

    for skill, patterns in get_skill_patterns().items():
        if any(pattern.search(normalized_text) for pattern in patterns):
            found_skills.append(skill)

    return unique_preserve_order(found_skills)


def extract_domain_keywords(text, limit=10):
    normalized_text = normalize_whitespace(text).lower()
    found = {keyword for keyword in DOMAIN_KEYWORDS if keyword in normalized_text}

    tokens = re.findall(r"[a-zA-Z][a-zA-Z+\-]{2,}", normalized_text)
    token_counts = {}
    for token in tokens:
        if token in STOPWORDS:
            continue
        token_counts[token] = token_counts.get(token, 0) + 1

    frequent_tokens = sorted(
        (token for token, count in token_counts.items() if count >= 2),
        key=lambda token: (-token_counts[token], token),
    )

    combined = list(found)
    for token in frequent_tokens:
        if token not in combined:
            combined.append(token)

    return combined[:limit]


def unique_preserve_order(items):
    def freeze(value):
        if isinstance(value, dict):
            return tuple((key, freeze(nested_value)) for key, nested_value in sorted(value.items()))
        if isinstance(value, list):
            return tuple(freeze(nested_value) for nested_value in value)
        return value

    seen = set()
    unique_items = []

    for item in items:
        marker = freeze(item)

        if item and marker not in seen:
            seen.add(marker)
            unique_items.append(item)

    return unique_items


def get_group_matches(skills, group_name):
    return sorted(set(skills) & SKILL_GROUPS.get(group_name, set()))


@lru_cache(maxsize=1)
def get_skill_group_map():
    skill_group_map = {}

    for group_name, grouped_skills in SKILL_GROUPS.items():
        for skill in grouped_skills:
            skill_group_map.setdefault(skill, set()).add(group_name)

    return skill_group_map


def get_skill_groups(skill):
    return sorted(get_skill_group_map().get(skill, set()))


def get_active_groups(skills):
    active_groups = set()

    for skill in skills:
        active_groups.update(get_skill_group_map().get(skill, set()))

    return sorted(active_groups)


def infer_adjacent_matches(required_skills, candidate_skills):
    candidate_skill_set = set(candidate_skills)
    adjacent_matches = []

    for required_skill in required_skills:
        for related_skill in SKILL_ADJACENCY.get(required_skill, []):
            if related_skill in candidate_skill_set:
                adjacent_matches.append(
                    {
                        "missing_skill": required_skill,
                        "related_skill": related_skill,
                    }
                )

    return unique_preserve_order(adjacent_matches)


def infer_ecosystem_matches(required_skills, candidate_skills):
    candidate_skill_set = set(candidate_skills)
    ecosystem_matches = []

    for required_skill in required_skills:
        if required_skill in candidate_skill_set:
            continue

        if required_skill in SKILL_ECOSYSTEM_SUPPORT:
            related_skills = sorted(
                candidate_skill_set & SKILL_ECOSYSTEM_SUPPORT[required_skill]
            )
        else:
            related_skills = []
            for group_name in get_skill_groups(required_skill):
                grouped_skills = SKILL_GROUPS.get(group_name, set()) - {required_skill}
                related_group_skills = sorted(candidate_skill_set & grouped_skills)
                if len(related_group_skills) >= 2:
                    related_skills.extend(related_group_skills[:3])

        related_skills = unique_preserve_order(related_skills)
        if related_skills:
            ecosystem_matches.append(
                {
                    "missing_skill": required_skill,
                    "related_skills": related_skills[:3],
                }
            )

    return unique_preserve_order(ecosystem_matches)
