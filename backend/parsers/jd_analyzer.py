from dataclasses import dataclass, field
import re

from backend.utils.skill_taxonomy import (
    extract_domain_keywords,
    extract_skills_from_text,
    get_group_matches,
    normalize_whitespace,
    unique_preserve_order,
)

SECTION_HEADERS = {
    "responsibilities": [
        "responsibilities",
        "what you will do",
        "what you'll do",
        "role overview",
        "day to day",
    ],
    "requirements": [
        "requirements",
        "must have",
        "must-have",
        "qualifications",
        "what we're looking for",
        "what we are looking for",
    ],
    "preferred": [
        "preferred",
        "nice to have",
        "good to have",
        "bonus",
        "preferred qualifications",
    ],
}

SENIORITY_PATTERNS = {
    "entry": r"\b(entry level|junior|graduate|intern|associate|0-2 years?)\b",
    "mid": r"\b(mid|3-5 years?|intermediate)\b",
    "senior": r"\b(senior|lead|staff|principal|6\+ years?|7\+ years?|8\+ years?)\b",
}


@dataclass
class JDAnalysis:
    raw_text: str
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    domain_keywords: list[str] = field(default_factory=list)
    seniority_indicators: list[str] = field(default_factory=list)
    semantic_focus_phrases: list[str] = field(default_factory=list)
    deployment_keywords: list[str] = field(default_factory=list)
    ai_keywords: list[str] = field(default_factory=list)
    api_keywords: list[str] = field(default_factory=list)

    @property
    def all_skills(self):
        return unique_preserve_order(self.required_skills + self.preferred_skills)

    def semantic_targets(self):
        targets = []

        if self.responsibilities:
            targets.extend(self.responsibilities[:6])

        if self.semantic_focus_phrases:
            targets.extend(self.semantic_focus_phrases[:6])

        if self.required_skills:
            targets.append("Required skills: " + ", ".join(self.required_skills))

        if self.preferred_skills:
            targets.append("Preferred skills: " + ", ".join(self.preferred_skills))

        if not targets:
            targets.append(self.raw_text)

        return targets


def _normalize_heading(line):
    cleaned = normalize_whitespace(line).lower().strip(":")
    cleaned = cleaned.replace("&", "and")
    return cleaned


def _split_sections(text):
    sections = {"general": []}
    current_section = "general"

    for raw_line in (text or "").splitlines():
        line = normalize_whitespace(raw_line)
        if not line:
            continue

        normalized_heading = _normalize_heading(line)
        matched_section = None
        for section_name, headings in SECTION_HEADERS.items():
            if normalized_heading in headings:
                matched_section = section_name
                break

        if matched_section:
            current_section = matched_section
            sections.setdefault(current_section, [])
            continue

        sections.setdefault(current_section, []).append(line)

    return {key: "\n".join(value) for key, value in sections.items() if value}


def _extract_bullets(section_text):
    bullets = []

    for line in (section_text or "").splitlines():
        cleaned = normalize_whitespace(line.lstrip("-*•"))
        if len(cleaned.split()) >= 4:
            bullets.append(cleaned)

    return bullets


def _extract_semantic_phrases(jd_text):
    candidates = []
    sentences = re.split(r"(?<=[.!?])\s+|\n", jd_text or "")

    for sentence in sentences:
        cleaned = normalize_whitespace(sentence)
        word_count = len(cleaned.split())
        if 5 <= word_count <= 22:
            candidates.append(cleaned)

    return unique_preserve_order(candidates)[:8]


def _extract_seniority_indicators(jd_text):
    normalized_text = (jd_text or "").lower()
    indicators = []

    for label, pattern in SENIORITY_PATTERNS.items():
        if re.search(pattern, normalized_text):
            indicators.append(label)

    return indicators


def analyze_job_description(jd_text):
    cleaned_text = normalize_whitespace(jd_text)
    sections = _split_sections(jd_text)

    required_text = "\n".join(
        part
        for part in [sections.get("requirements", ""), sections.get("general", "")]
        if part
    )
    preferred_text = sections.get("preferred", "")
    responsibilities = _extract_bullets(sections.get("responsibilities", "")) or _extract_semantic_phrases(
        sections.get("responsibilities", "") or sections.get("general", "")
    )

    required_skills = extract_skills_from_text(required_text)
    preferred_skills = [
        skill
        for skill in extract_skills_from_text(preferred_text)
        if skill not in required_skills
    ]

    if not required_skills:
        required_skills = extract_skills_from_text(cleaned_text)[:8]

    domain_keywords = extract_domain_keywords(cleaned_text)
    seniority_indicators = _extract_seniority_indicators(cleaned_text)
    semantic_focus_phrases = _extract_semantic_phrases(cleaned_text)

    all_skills = unique_preserve_order(required_skills + preferred_skills)

    return JDAnalysis(
        raw_text=jd_text,
        required_skills=required_skills,
        preferred_skills=preferred_skills,
        responsibilities=responsibilities,
        domain_keywords=domain_keywords,
        seniority_indicators=seniority_indicators,
        semantic_focus_phrases=semantic_focus_phrases,
        deployment_keywords=get_group_matches(all_skills, "deployment"),
        ai_keywords=get_group_matches(all_skills, "ai"),
        api_keywords=get_group_matches(all_skills, "api"),
    )
