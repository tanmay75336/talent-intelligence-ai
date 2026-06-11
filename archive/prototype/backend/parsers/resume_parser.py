import fitz
import re

from backend.models.candidate_profile import CandidateProfile
from backend.utils.skill_taxonomy import (
    extract_skills_from_text,
    get_group_matches,
    normalize_whitespace,
    unique_preserve_order,
)

SECTION_PATTERNS = {
    "summary": {
        "profile summary",
        "summary",
        "professional summary",
        "about",
        "profile",
    },
    "skills": {
        "technical skills",
        "skills",
        "tech stack",
        "core skills",
    },
    "projects": {
        "projects",
        "project experience",
        "selected projects",
        "key projects",
    },
    "experience": {
        "experience",
        "work experience",
        "professional experience",
        "internships",
    },
    "education": {
        "education",
        "academic background",
    },
    "certifications": {
        "certifications",
        "licenses",
        "courses",
        "certificates",
    },
    "achievements": {
        "hackathons and competitions",
        "hackathons & competitions",
        "hackathons",
        "competitions",
        "achievements",
    },
}


def extract_text_from_pdf(pdf_path):
    text = ""
    doc = fitz.open(pdf_path)

    for page in doc:
        text += page.get_text()

    return text


def _normalize_heading(line):
    cleaned = normalize_whitespace(line).lower().strip(":")
    cleaned = cleaned.replace("&", "and")
    return cleaned


def parse_resume_sections(text):
    sections = {"header": []}
    current_section = "header"

    for raw_line in (text or "").splitlines():
        line = normalize_whitespace(raw_line)
        if not line:
            continue

        normalized_heading = _normalize_heading(line)
        matched_section = None
        for section_name, heading_options in SECTION_PATTERNS.items():
            if normalized_heading in heading_options:
                matched_section = section_name
                break

        if matched_section:
            current_section = matched_section
            sections.setdefault(current_section, [])
            continue

        sections.setdefault(current_section, []).append(line)

    return {
        key: "\n".join(value).strip()
        for key, value in sections.items()
        if value
    }


def _is_project_title(line, next_line):
    if not line or len(line.split()) > 8:
        return False

    lower_line = line.lower()
    if any(token in lower_line for token in ["@", "linkedin", "github", "http"]):
        return False

    if re.search(r"\b(20\d{2}|19\d{2})\b", line):
        return False

    if next_line and any(symbol in next_line for symbol in ["·", "|", ","]):
        return True

    return "—" in line or "-" in line


def _split_blocks(section_text, prefer_titles=False):
    lines = [normalize_whitespace(line) for line in (section_text or "").splitlines()]
    lines = [line for line in lines if line]

    blocks = []
    current_block = []

    for index, line in enumerate(lines):
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        starts_new_block = prefer_titles and _is_project_title(line, next_line) and current_block

        if starts_new_block:
            blocks.append("\n".join(current_block))
            current_block = [line]
            continue

        current_block.append(line)

    if current_block:
        blocks.append("\n".join(current_block))

    if len(blocks) == 1:
        rough_blocks = re.split(r"\n{2,}", section_text or "")
        separated = [normalize_whitespace(block) for block in rough_blocks if normalize_whitespace(block)]
        if len(separated) > 1:
            return separated

    return blocks


def _split_project_blocks(section_text):
    lines = [normalize_whitespace(line) for line in (section_text or "").splitlines()]
    lines = [line for line in lines if line]

    blocks = []
    current_block = []

    for index, line in enumerate(lines):
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        is_title_line = (
            len(line.split()) <= 8
            and "·" not in line
            and "|" not in line
            and ":" not in line
            and not re.search(r"\b(20\d{2}|19\d{2})\b", line)
            and not line.lower().startswith(("built", "developed", "created"))
            and (
                "—" in line
                or next_line.count("·") >= 1
                or next_line.lower().startswith(("react", "next.js", "html", "python"))
            )
        )

        if is_title_line and current_block:
            blocks.append("\n".join(current_block))
            current_block = [line]
        else:
            current_block.append(line)

    if current_block:
        blocks.append("\n".join(current_block))

    return [block for block in blocks if block]


def _estimate_years_of_experience(text):
    explicit_years = [
        int(value)
        for value in re.findall(r"(\d+)\+?\s+years?", (text or "").lower())
    ]

    if explicit_years:
        return float(max(explicit_years))

    if re.search(r"\b(current|student|undergraduate|2nd-year|second-year)\b", (text or "").lower()):
        return 0.5

    return 0.0


def _infer_seniority(text, years_of_experience):
    lowered = (text or "").lower()

    if years_of_experience >= 6 or re.search(r"\b(senior|lead|staff|principal)\b", lowered):
        return "senior"

    if years_of_experience >= 3 or re.search(r"\b(mid|intermediate)\b", lowered):
        return "mid"

    if re.search(r"\b(student|intern|undergraduate|graduate)\b", lowered):
        return "student"

    if years_of_experience > 0:
        return "entry"

    return "unknown"


def extract_skills(text):
    return extract_skills_from_text(text)


def extract_candidate_name(text):
    lines = [normalize_whitespace(line) for line in (text or "").splitlines()]

    for line in lines[:12]:
        if len(line) < 3:
            continue
        if any(token in line.lower() for token in ["@", "linkedin", "github", "http", "mumbai"]):
            continue
        if len(line.split()) > 6:
            continue
        if re.search(r"\d", line):
            continue
        return line

    return "Unknown Candidate"


def build_candidate_profile(text, source_name=""):
    sections = parse_resume_sections(text)
    skills_text = sections.get("skills", "")
    projects_text = sections.get("projects", "")
    experience_text = sections.get("experience", "")
    education_text = sections.get("education", "")
    certification_text = sections.get("certifications", "")
    summary_text = sections.get("summary", "")

    all_skills = extract_skills_from_text(
        "\n".join(
            part
            for part in [skills_text, projects_text, experience_text, summary_text, text]
            if part
        )
    )

    projects = _split_project_blocks(projects_text)
    experience = _split_blocks(experience_text, prefer_titles=False)
    education = _split_blocks(education_text, prefer_titles=False)
    certifications = _split_blocks(certification_text, prefer_titles=False)

    years_of_experience = _estimate_years_of_experience(text)

    return CandidateProfile(
        name=extract_candidate_name(text),
        raw_text=text,
        source_name=source_name,
        summary=summary_text or sections.get("header", ""),
        skills=all_skills,
        projects=projects,
        experience=experience,
        education=education,
        certifications=certifications,
        sections=sections,
        deployment_signals=get_group_matches(all_skills, "deployment"),
        ai_signals=get_group_matches(all_skills, "ai"),
        api_signals=get_group_matches(all_skills, "api"),
        years_of_experience=years_of_experience,
        seniority_band=_infer_seniority(text, years_of_experience),
    )
